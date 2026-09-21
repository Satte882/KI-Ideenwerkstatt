from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun, SolutionQualityRun
from ki_radar.accelerator.solution_critic_contract import validate_solution_critic_payload
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.accelerator.solution_quality_snapshot import build_solution_quality_snapshot
from ki_radar.accelerator.solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
    REPAIR_PROMPT_VERSION,
    REPAIR_SCHEMA_VERSION,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage

PREVIEW_ROUTE = "accelerator:solution_generation_preview"
REPAIR_ROUTE = "accelerator:solution_generation_repair"
CRITIC_PROVIDER = "ki_radar.accelerator.solution_critic_service.request_openrouter"
REPAIR_PROVIDER = "ki_radar.accelerator.solution_repair_service.request_openrouter"
REPAIR_VIEW_SERVICE = "ki_radar.accelerator.solution_generation_views.run_targeted_solution_repair"

FIELD_SOURCES = {
    "name": "process.current_flow",
    "description": "process.current_flow",
    "expected_value": "process.bottlenecks",
    "bottleneck_coverage": "process.bottlenecks",
    "data_requirements": "process.data_objects",
    "application_impact": "process.systems",
    "integration_impact": "process.systems",
    "technology_constraints": "value_stream.constraints",
    "risks": "process.exceptions",
    "architecture_fit": "process.target_state_principles",
}


def _make_process(owner, business_unit) -> ProcessAnalysis:
    stream = ValueStream.objects.create(
        name="Beschaffung AP9 Preview",
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
        name="Angebotsvergleich AP9",
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


def _statement(text: str, source_id: str) -> dict[str, object]:
    return {
        "text": text,
        "source_ids": [source_id],
        "assumptions": [],
        "open_evidence": [],
        "uncertainty": {
            "level": "low",
            "reason": "Direkt aus der angegebenen Quelle abgeleitet.",
        },
    }


def _make_run(owner, business_unit) -> SolutionGenerationRun:
    process = _make_process(owner, business_unit)
    source_context = build_solution_generation_source_context(process)
    options: dict[str, dict[str, object]] = {}
    for lane in OPTION_LANES:
        option: dict[str, object] = {}
        for field_name in GENERATED_OPTION_FIELDS:
            text = f"{lane}: {field_name.replace('_', ' ')}"
            option[field_name] = _statement(text, FIELD_SOURCES[field_name])
        options[lane] = option

    preview_payload = {
        "schema_version": GENERATION_SCHEMA_VERSION,
        "prompt_version": GENERATION_PROMPT_VERSION,
        "source_context": source_context.provider_payload(),
        "options": options,
        "edits": {},
    }
    return SolutionGenerationRun.objects.create(
        process_analysis=process,
        process_version=source_context.process_version,
        source_hash=source_context.source_hash,
        requested_by=owner,
        status=SolutionGenerationRun.Status.SUCCESS,
        provider="openrouter",
        model_name="test/generator",
        prompt_version=GENERATION_PROMPT_VERSION,
        generation_schema_version=GENERATION_SCHEMA_VERSION,
        started_at=timezone.now() - timedelta(seconds=1),
        finished_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=1),
        preview_payload=preview_payload,
    )


def _make_initial_critic(
    run: SolutionGenerationRun,
    *,
    repairable: bool,
) -> SolutionQualityRun:
    source_context = build_solution_generation_source_context(run.process_analysis)
    snapshot = build_solution_quality_snapshot(
        preview_payload=run.preview_payload,
        source_context=source_context,
    )
    finding = {
        "criterion": "bottleneck_fit",
        "option": "assistant",
        "field": "bottleneck_coverage",
        "finding": "Der Engpassbezug muss präziser aus der dokumentierten Ursache hervorgehen.",
        "source_ids": ["process.bottlenecks"],
        "repairable": repairable,
        "related_targets": [],
    }
    result_payload = validate_solution_critic_payload(
        {
            "schema_version": CRITIC_SCHEMA_VERSION,
            "prompt_version": CRITIC_PROMPT_VERSION,
            "findings": [finding],
        },
        source_context,
    )
    return SolutionQualityRun.objects.create(
        solution_generation_run=run,
        requested_by=run.requested_by,
        step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
        status=SolutionQualityRun.Status.SUCCESS,
        provider="openrouter",
        model_name="test/critic",
        prompt_version=CRITIC_PROMPT_VERSION,
        output_schema_version=CRITIC_SCHEMA_VERSION,
        input_hash=snapshot.snapshot_hash,
        started_at=timezone.now() - timedelta(seconds=1),
        finished_at=timezone.now(),
        result_payload=result_payload,
    )


def _apply_machine_repair(
    run: SolutionGenerationRun,
    initial_critic: SolutionQualityRun,
) -> str:
    repaired_text = (
        "Adressiert den dokumentierten Engpass durch eine assistierende Prüfung "
        "und weist die verbleibende fachliche Unsicherheit ausdrücklich aus."
    )
    repair_run = SolutionQualityRun.objects.create(
        solution_generation_run=run,
        requested_by=run.requested_by,
        step_type=SolutionQualityRun.StepType.REPAIR,
        status=SolutionQualityRun.Status.SUCCESS,
        provider="openrouter",
        model_name="test/repair",
        prompt_version=REPAIR_PROMPT_VERSION,
        output_schema_version=REPAIR_SCHEMA_VERSION,
        input_hash=initial_critic.input_hash,
        started_at=timezone.now() - timedelta(seconds=1),
        finished_at=timezone.now(),
        result_payload={},
    )
    preview_payload = dict(run.preview_payload)
    preview_payload["machine_repair"] = {
        "quality_run_id": str(repair_run.pk),
        "input_hash": initial_critic.input_hash,
        "prompt_version": REPAIR_PROMPT_VERSION,
        "schema_version": REPAIR_SCHEMA_VERSION,
        "patches": [
            {
                "option": "assistant",
                "field": "bottleneck_coverage",
                "statement": _statement(repaired_text, "process.bottlenecks"),
            }
        ],
    }
    run.preview_payload = preview_payload
    run.save(update_fields=["preview_payload", "updated_at"])
    return repaired_text


@pytest.mark.django_db
def test_preview_shows_repairable_finding_without_provider_call(
    client,
    owner,
    business_unit,
):
    run = _make_run(owner, business_unit)
    _make_initial_critic(run, repairable=True)
    client.force_login(owner)

    with patch(CRITIC_PROVIDER) as critic_provider, patch(REPAIR_PROVIDER) as repair_provider:
        response = client.get(reverse(PREVIEW_ROUTE, args=[run.pk]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "KI-Qualitätsprüfung" in content
    assert "keine Bewertung oder Lösungsempfehlung" in content
    assert "Passung zum Engpass" in content
    assert "Bottleneck-Abdeckung" in content
    assert "Engpassbezug muss präziser" in content
    assert "Maschinell reparierbar" in content
    assert "Reparierbare Findings einmalig korrigieren" in content
    critic_provider.assert_not_called()
    repair_provider.assert_not_called()


@pytest.mark.django_db
def test_preview_renders_machine_repair_with_structured_finding_binding(
    client,
    owner,
    business_unit,
):
    run = _make_run(owner, business_unit)
    initial_critic = _make_initial_critic(run, repairable=True)
    repaired_text = _apply_machine_repair(run, initial_critic)
    client.force_login(owner)

    response = client.get(reverse(PREVIEW_ROUTE, args=[run.pk]))

    assert response.status_code == 200
    assert response.context["form"]["assistant__bottleneck_coverage"].value() == repaired_text
    assistant_preview = next(
        option for option in response.context["preview_options"] if option["lane"] == "assistant"
    )
    bottleneck_field = next(
        field for field in assistant_preview["fields"] if field["name"] == "bottleneck_coverage"
    )
    assert bottleneck_field["text"] == repaired_text
    assert bottleneck_field["sources"] == [
        {
            "source_id": "process.bottlenecks",
            "label": "Bottlenecks",
        }
    ]
    finding = response.context["quality_findings"][0]
    assert finding["option"] == "assistant"
    assert finding["field"] == "bottleneck_coverage"
    assert finding["field_label"] == "Bottleneck-Abdeckung"
    assert finding["sources"] == bottleneck_field["sources"]
    assert repaired_text in response.content.decode()


@pytest.mark.django_db
def test_human_edit_after_repair_uses_repaired_baseline_and_preserves_binding(
    client,
    owner,
    business_unit,
):
    run = _make_run(owner, business_unit)
    initial_critic = _make_initial_critic(run, repairable=True)
    repaired_text = _apply_machine_repair(run, initial_critic)
    client.force_login(owner)

    preview_response = client.get(reverse(PREVIEW_ROUTE, args=[run.pk]))
    form_data = {
        field_name: preview_response.context["form"][field_name].value()
        for field_name in preview_response.context["form"].fields
    }
    human_edit = "Der erwartete Beitrag wurde im Human Review präzisiert."
    form_data["assistant__expected_value"] = human_edit

    response = client.post(reverse(PREVIEW_ROUTE, args=[run.pk]), data=form_data)

    assert response.status_code == 302
    run.refresh_from_db()
    assert run.preview_payload["edits"] == {
        "assistant": {
            "expected_value": human_edit,
        }
    }
    assert run.preview_payload["machine_repair"]["patches"][0]["statement"]["text"] == (
        repaired_text
    )

    follow_up = client.get(reverse(PREVIEW_ROUTE, args=[run.pk]))
    finding = follow_up.context["quality_findings"][0]
    assert finding["option"] == "assistant"
    assert finding["field"] == "bottleneck_coverage"
    assert finding["sources"][0]["source_id"] == "process.bottlenecks"
    assert follow_up.context["form"]["assistant__bottleneck_coverage"].value() == repaired_text
    assert follow_up.context["form"]["assistant__expected_value"].value() == human_edit


@pytest.mark.django_db
def test_nonrepairable_finding_goes_to_human_review(
    client,
    owner,
    business_unit,
):
    run = _make_run(owner, business_unit)
    _make_initial_critic(run, repairable=False)
    client.force_login(owner)

    response = client.get(reverse(PREVIEW_ROUTE, args=[run.pk]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Manuell prüfen" in content
    assert "Human Review" in content
    assert "Reparierbare Findings einmalig korrigieren" not in content
    assert "Bearbeitungen speichern" in content
    assert "ausgewählte ki-lösungsoptionen hinzufügen" in content.lower()


@pytest.mark.django_db
def test_human_edit_makes_repair_stale_without_provider_call(
    client,
    owner,
    business_unit,
):
    run = _make_run(owner, business_unit)
    _make_initial_critic(run, repairable=True)
    payload = dict(run.preview_payload)
    payload["edits"] = {
        "assistant": {
            "description": "Nach Critic manuell präzisiert.",
        },
    }
    run.preview_payload = payload
    run.save(update_fields=["preview_payload", "updated_at"])
    client.force_login(owner)

    with patch(REPAIR_PROVIDER) as repair_provider:
        response = client.get(reverse(PREVIEW_ROUTE, args=[run.pk]))

    content = response.content.decode()
    stale_message = "Vorschau wurde seit der Prüfung bearbeitet, Reparatur nicht mehr möglich."
    assert response.status_code == 200
    assert stale_message in content
    assert "Reparierbare Findings einmalig korrigieren" not in content
    assert "Bearbeitungen speichern" in content
    repair_provider.assert_not_called()


@pytest.mark.django_db
def test_repair_endpoint_calls_existing_service_once(
    client,
    owner,
    business_unit,
):
    run = _make_run(owner, business_unit)
    _make_initial_critic(run, repairable=True)
    client.force_login(owner)

    successful_repair = SimpleNamespace(status=SolutionQualityRun.Status.SUCCESS)
    with patch(REPAIR_VIEW_SERVICE, return_value=successful_repair) as repair_service:
        response = client.post(reverse(REPAIR_ROUTE, args=[run.pk]))

    assert response.status_code == 302
    assert response.url.endswith("#solution-generation-quality")
    repair_service.assert_called_once_with(
        solution_generation_run_id=run.pk,
        actor=owner,
    )


@pytest.mark.django_db
def test_source_stale_repair_is_rejected_before_service_call(
    client,
    owner,
    business_unit,
):
    run = _make_run(owner, business_unit)
    _make_initial_critic(run, repairable=True)
    process = run.process_analysis
    process.current_flow = "Der fachliche Quellstand wurde nach der Prüfung geändert."
    process.save(update_fields=["current_flow", "updated_at"])
    client.force_login(owner)

    with patch(REPAIR_VIEW_SERVICE) as repair_service:
        response = client.post(reverse(REPAIR_ROUTE, args=[run.pk]))

    assert response.status_code == 302
    assert response.url.endswith("#solution-generation-quality")
    repair_service.assert_not_called()
