from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from ki_radar.accelerator.solution_generation_service import (
    SolutionGenerationQuotaExceeded,
)
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    SolutionSelectionDecision,
    ValueStream,
    ValueStreamStage,
)

LANE_LABELS = {
    "organizational": "Organisatorischer Entwurf",
    "rule_automation": "Regelbasierter Entwurf",
    "assistant": "Assistenzentwurf",
}


def make_process(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Freigegebener Bedarf",
        outcome="Bestellung ausgelöst",
        scope_in="Bedarf bis Bestellung",
        strategic_objective="Durchlaufzeit reduzieren",
        constraints="EU-Datenhaltung und menschliche Freigabe",
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=2,
        name="Angebote vergleichen",
        description="Angebote fachlich vergleichen",
        actors="Einkauf",
        systems="ERP",
        documents="Angebote",
        pain_points="Manueller Vergleich",
        baseline_metrics="11 Minuten pro Vergleich",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        scope_start="Angebote liegen vor",
        scope_end="Auswahl ist dokumentiert",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Auswahl",
        current_flow="Angebote werden manuell gegenübergestellt.",
        roles="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        data_objects="Angebote und Kriterienkatalog",
        business_rules="Vier-Augen-Prinzip bei Freigabe",
        handoffs="Einkauf übergibt an Fachbereich",
        bottlenecks="Manuelle Übertragung verursacht Wartezeit.",
        exceptions="Fehlende Pflichtangaben werden nachgefordert.",
        baseline_metrics="11 Minuten pro Vergleich",
        target_state_principles="Nachvollziehbar und assistierend",
        analyzed_by=owner,
    )


def statement(text, *, assumptions=None, open_evidence=None):
    return {
        "text": text,
        "source_ids": ["process.current_flow"],
        "assumptions": assumptions or [],
        "open_evidence": open_evidence or [],
        "uncertainty": {
            "level": "low",
            "reason": "Direkt aus dem dokumentierten Ist-Ablauf abgeleitet.",
        },
    }


def preview_payload(process):
    context = build_solution_generation_source_context(process)
    options = {}
    for lane in OPTION_LANES:
        option = {}
        for field_name in GENERATED_OPTION_FIELDS:
            option[field_name] = statement(f"{LANE_LABELS[lane]} - {field_name}")
        options[lane] = option
    options["assistant"]["risks"] = statement(
        "Assistenzentwurf - Risiken",
        assumptions=["Nutzer prüfen Vorschläge vor der Freigabe."],
    )
    options["assistant"]["technology_constraints"] = statement(
        "Assistenzentwurf - Technologieleitplanken",
        open_evidence=["Betriebsmodell des späteren Assistenzsystems klären."],
    )
    return {
        "schema_version": GENERATION_SCHEMA_VERSION,
        "prompt_version": GENERATION_PROMPT_VERSION,
        "source_context": context.provider_payload(),
        "options": options,
        "edits": {},
    }


def make_run(owner, process):
    context = build_solution_generation_source_context(process)
    return SolutionGenerationRun.objects.create(
        process_analysis=process,
        process_version=process.version,
        source_hash=context.source_hash,
        requested_by=owner,
        status=SolutionGenerationRun.Status.SUCCESS,
        prompt_version=GENERATION_PROMPT_VERSION,
        generation_schema_version=GENERATION_SCHEMA_VERSION,
        finished_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=1),
        preview_payload=preview_payload(process),
    )


def edit_post_data(run):
    data = {}
    for lane in OPTION_LANES:
        for field_name in GENERATED_OPTION_FIELDS:
            data[f"{lane}__{field_name}"] = run.preview_payload["options"][lane][field_name]["text"]
    return data


@pytest.mark.django_db
def test_compare_offers_manual_and_ai_entries_equally(client, owner, business_unit):
    process = make_process(owner, business_unit)
    client.force_login(owner)

    response = client.get(reverse("architecture:solution_option_compare", args=[process.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Option ergänzen" in content
    assert "3 Lösungsentwürfe mit KI erstellen" in content
    assert "Quellstand: Entwurfsquelle - noch nicht formal validiert" in content
    before_label = content.split("3 Lösungsentwürfe mit KI erstellen", 1)[0][-150:]
    assert "disabled" not in before_label


@pytest.mark.django_db
def test_compare_explains_missing_generation_readiness(client, owner, business_unit):
    process = make_process(owner, business_unit)
    process.current_flow = ""
    process.save(update_fields=["current_flow", "updated_at"])
    client.force_login(owner)

    response = client.get(reverse("architecture:solution_option_compare", args=[process.pk]))

    content = response.content.decode()
    assert "KI-Generierung noch nicht möglich" in content
    assert "Ist-Ablauf" in content
    assert "3 Lösungsentwürfe mit KI erstellen</button>" in content
    assert "disabled" in content


@pytest.mark.django_db
def test_generation_start_redirects_to_preview_without_domain_write(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    client.force_login(owner)

    with patch(
        "ki_radar.accelerator.solution_generation_views.generate_solution_preview",
        return_value=run,
    ) as generate_mock:
        response = client.post(reverse("accelerator:solution_generation_start", args=[process.pk]))

    assert response.status_code == 302
    expected = reverse("accelerator:solution_generation_preview", args=[run.pk])
    assert response.url == f"{expected}#solution-generation-result"
    generate_mock.assert_called_once_with(actor=owner, process_analysis_id=process.pk)
    assert not SolutionOption.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
def test_generation_start_renders_quota_failure_as_safe_message(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    client.force_login(owner)

    with patch(
        "ki_radar.accelerator.solution_generation_views.generate_solution_preview",
        side_effect=SolutionGenerationQuotaExceeded(
            "Diese Prozessanalyse hat das tägliche Generierungslimit erreicht.",
            code="context_quota_exceeded",
        ),
    ):
        response = client.post(
            reverse("accelerator:solution_generation_start", args=[process.pk]),
            follow=True,
        )

    content = response.content.decode()
    assert response.status_code == 200
    assert "tägliche Generierungslimit erreicht" in content
    assert not SolutionOption.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
def test_preview_shows_shared_sources_provenance_and_unassessed_boundary(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    client.force_login(owner)

    response = client.get(reverse("accelerator:solution_generation_preview", args=[run.pk]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Gemeinsame Ausgangslage" in content
    assert "Ist-Ablauf" in content
    assert "Angebote werden manuell gegenübergestellt." in content
    assert "Organisatorische Änderung" in content
    assert "Regelbasierte Automatisierung" in content
    assert "KI-/Assistenzlösung" in content
    assert "Quellen" in content
    assert "Annahmen" in content
    assert "Offene Evidenz" in content
    assert "Unsicherheit" in content
    assert "KI-Entwurf" in content
    assert "noch nicht fachlich bewertet" in content
    assert "Machbarkeit bewerten" not in content
    assert "Integrationsaufwand bewerten" not in content
    assert "Bevorzugte Option" not in content


@pytest.mark.django_db
def test_preview_edit_persists_only_human_text_delta_without_decision_fields(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    client.force_login(owner)
    data = edit_post_data(run)
    data["assistant__description"] = "Vom Nutzer präzisierter Assistenzentwurf."

    response = client.post(
        reverse("accelerator:solution_generation_preview", args=[run.pk]),
        data=data,
    )

    assert response.status_code == 302
    run.refresh_from_db()
    assert run.preview_payload["edits"] == {
        "assistant": {"description": "Vom Nutzer präzisierter Assistenzentwurf."}
    }
    assert not SolutionOption.objects.filter(process_analysis=process).exists()
    assert not SolutionSelectionDecision.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
def test_stale_preview_is_visible_but_not_editable(client, owner, business_unit):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    process.current_flow = "Der Ablauf wurde nach der Generierung fachlich geändert."
    process.save(update_fields=["current_flow", "updated_at"])
    client.force_login(owner)

    response = client.get(reverse("accelerator:solution_generation_preview", args=[run.pk]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Veralteter Quellstand" in content
    assert "Bearbeitung ist gesperrt" in content
    assert 'name="assistant__description"' not in content


@pytest.mark.django_db
def test_preview_uses_responsive_cards_without_comparison_table(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    client.force_login(owner)

    response = client.get(reverse("accelerator:solution_generation_preview", args=[run.pk]))

    content = response.content.decode()
    assert "col-12 col-xl-4" in content
    assert "<table" not in content
    assert "min-width" not in content
