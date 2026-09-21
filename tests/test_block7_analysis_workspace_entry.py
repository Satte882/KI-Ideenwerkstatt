from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun
from ki_radar.accelerator.solution_generation_contract import (
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
)
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


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
    ValueStreamFocus.objects.create(
        value_stream=stream,
        business_domain=BusinessDomain.PROCUREMENT,
        capability="Supplier Sourcing und Angebotsvergleich",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.MEDIUM,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Der Angebotsvergleich ist die ausgewählte Fokusphase.",
        updated_by=owner,
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


def add_manual_option(process, owner):
    return SolutionOption.objects.create(
        process_analysis=process,
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        name="Bestehende organisatorische Option",
        description="Verantwortlichkeiten werden organisatorisch geklärt.",
        expected_value="Weniger manuelle Rückfragen.",
        created_by=owner,
    )


def make_successful_run(owner, process):
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
        preview_payload={},
    )


@pytest.mark.django_db
def test_analysis_workspace_offers_manual_and_ai_entries_on_real_user_path(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    add_manual_option(process, owner)
    client.force_login(owner)

    response = client.get(reverse("architecture:process_analysis_detail", args=[process.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    start_url = reverse("accelerator:solution_generation_start", args=[process.pk])
    assert "Weitere Option ergänzen" in content
    assert "3 Lösungsentwürfe mit KI erstellen" in content
    assert f'action="{start_url}"' in content
    generation_form = content.split(f'action="{start_url}"', 1)[1].split("</form>", 1)[0]
    assert "disabled" not in generation_form


@pytest.mark.django_db
def test_analysis_workspace_disables_ai_entry_and_explains_missing_readiness(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    process.current_flow = ""
    process.save(update_fields=["current_flow", "updated_at"])
    add_manual_option(process, owner)
    client.force_login(owner)

    response = client.get(reverse("architecture:process_analysis_detail", args=[process.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    start_url = reverse("accelerator:solution_generation_start", args=[process.pk])
    assert "Weitere Option ergänzen" in content
    assert "3 Lösungsentwürfe mit KI erstellen</button>" in content
    assert "disabled" in content
    assert f'action="{start_url}"' not in content
    assert "KI-Generierung noch nicht möglich" in content
    assert "Ist-Ablauf" in content


@pytest.mark.django_db
def test_analysis_workspace_links_latest_preview_and_flags_stale_source(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    run = make_successful_run(owner, process)
    process.current_flow = "Der Ist-Ablauf wurde nach der Generierung geändert."
    process.save(update_fields=["current_flow", "updated_at"])
    client.force_login(owner)

    response = client.get(reverse("architecture:process_analysis_detail", args=[process.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    preview_url = reverse("accelerator:solution_generation_preview", args=[run.pk])
    assert "Letzten KI-Entwurf ansehen" in content
    assert f'href="{preview_url}"' in content
    assert "Der letzte KI-Entwurf basiert auf einem älteren Prozessstand" in content
