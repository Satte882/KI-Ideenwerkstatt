from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.forms.models import model_to_dict
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun, SolutionQualityRun
from ki_radar.accelerator.solution_critic_service import (
    run_final_solution_critic,
    run_initial_solution_critic,
)
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from ki_radar.accelerator.solution_generation_service import (
    SolutionGenerationError,
    generate_solution_preview,
)
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.accelerator.solution_generation_validation import validate_solution_generation_payload
from ki_radar.accelerator.solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
    REPAIR_PROMPT_VERSION,
    REPAIR_SCHEMA_VERSION,
)
from ki_radar.accelerator.solution_repair_service import run_targeted_solution_repair
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.openrouter import OpenRouterResult
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.governance.models import GovernanceAssessment, GovernanceReview
from ki_radar.reviews.models import Review
from ki_radar.use_cases.models import UseCase

VALID_LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "17",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "100000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "4096",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "10",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "20",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "100",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS": "8192",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT": "4",
    "ACCELERATOR_SOLUTION_CRITIC_MAX_INPUT_CHARS": "100000",
    "ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS": "30",
}

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
        name="Beschaffung AP10 Regression",
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
        name="Angebotsvergleich AP10",
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


def _generation_payload() -> dict[str, object]:
    options: dict[str, dict[str, object]] = {}
    for lane in OPTION_LANES:
        option: dict[str, object] = {}
        for field_name in GENERATED_OPTION_FIELDS:
            option[field_name] = _statement(
                f"{lane}: {field_name.replace('_', ' ')}",
                FIELD_SOURCES[field_name],
            )
        option["name"]["text"] = f"Option {lane}"
        options[lane] = option
    return {
        "schema_version": GENERATION_SCHEMA_VERSION,
        "prompt_version": GENERATION_PROMPT_VERSION,
        "options": options,
    }


def _make_generation_run(owner, business_unit) -> SolutionGenerationRun:
    process = _make_process(owner, business_unit)
    source_context = build_solution_generation_source_context(process)
    validated = validate_solution_generation_payload(_generation_payload(), source_context)
    preview_payload = {
        "schema_version": validated["schema_version"],
        "prompt_version": validated["prompt_version"],
        "source_context": source_context.provider_payload(),
        "options": validated["options"],
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
        expires_at=timezone.now() + timedelta(days=30),
        preview_payload=preview_payload,
    )


def _critic_payload(*, repairable: bool) -> dict[str, object]:
    findings = []
    if repairable:
        findings.append(
            {
                "criterion": "bottleneck_fit",
                "option": "assistant",
                "field": "bottleneck_coverage",
                "finding": "Der Engpassbezug sollte präziser beschrieben werden.",
                "source_ids": ["process.bottlenecks"],
                "repairable": True,
                "related_targets": [],
            }
        )
    return {
        "schema_version": CRITIC_SCHEMA_VERSION,
        "prompt_version": CRITIC_PROMPT_VERSION,
        "findings": findings,
    }


def _provider_result(payload: dict[str, object], *, model: str) -> OpenRouterResult:
    content = json.dumps(payload, ensure_ascii=False)
    return OpenRouterResult(
        content=content,
        model=model,
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 80,
            "total_tokens": 180,
            "cost": "0.0002",
        },
        output_chars=len(content),
        finish_reason="stop",
    )


def _repair_payload() -> dict[str, object]:
    return {
        "schema_version": REPAIR_SCHEMA_VERSION,
        "prompt_version": REPAIR_PROMPT_VERSION,
        "patches": [
            {
                "option": "assistant",
                "field": "bottleneck_coverage",
                "statement": _statement(
                    "Die Assistenz adressiert gezielt die manuelle Übertragung im Engpass.",
                    "process.bottlenecks",
                ),
            }
        ],
    }


def _gate_counts() -> dict[str, int]:
    return {
        "process_validation": ProcessValidation.objects.count(),
        "selection": SolutionSelectionDecision.objects.count(),
        "use_case": UseCase.objects.count(),
        "governance_assessment": GovernanceAssessment.objects.count(),
        "governance_review": GovernanceReview.objects.count(),
        "delivery_package": DeliveryPackage.objects.count(),
        "lifecycle_review": Review.objects.count(),
    }


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_invalid_generation_is_rejected_before_initial_critic_is_scheduled(
    owner,
    business_unit,
):
    process = _make_process(owner, business_unit)
    before = _gate_counts()
    invalid_payload = {
        "schema_version": GENERATION_SCHEMA_VERSION,
        "prompt_version": GENERATION_PROMPT_VERSION,
        "options": {},
    }

    with (
        patch(
            "ki_radar.accelerator.solution_generation_service.request_openrouter",
            return_value=_provider_result(invalid_payload, model="test/generator"),
        ),
        patch("ki_radar.accelerator.solution_quality_signals.transaction.on_commit") as on_commit,
        patch("ki_radar.accelerator.solution_critic_service.request_openrouter") as critic_provider,
        pytest.raises(SolutionGenerationError) as exc_info,
    ):
        generate_solution_preview(actor=owner, process_analysis_id=process.pk)

    assert exc_info.value.code == "invalid_generation_payload"
    on_commit.assert_not_called()
    critic_provider.assert_not_called()
    run = SolutionGenerationRun.objects.get(process_analysis=process)
    assert run.status == SolutionGenerationRun.Status.FAILED
    assert run.preview_payload == {}
    assert not SolutionQualityRun.objects.filter(solution_generation_run=run).exists()
    assert not SolutionOption.objects.filter(process_analysis=process).exists()
    assert _gate_counts() == before


@pytest.mark.django_db
def test_repair_endpoint_rechecks_existing_value_stream_permission(
    client,
    owner,
    business_unit,
):
    run = _make_generation_run(owner, business_unit)
    outsider = owner.__class__.objects.create_user(username="ap10-outsider", password="secret")
    before = _gate_counts()
    client.force_login(outsider)

    with patch(
        "ki_radar.accelerator.solution_generation_views.run_targeted_solution_repair"
    ) as repair_service:
        response = client.post(reverse("accelerator:solution_generation_repair", args=[run.pk]))

    assert response.status_code == 403
    repair_service.assert_not_called()
    assert not SolutionOption.objects.filter(process_analysis=run.process_analysis).exists()
    assert _gate_counts() == before


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_complete_quality_path_preserves_domain_gate_and_adoption_boundaries(
    owner,
    business_unit,
):
    run = _make_generation_run(owner, business_unit)
    process = run.process_analysis
    process_before = model_to_dict(process)
    stream_before = model_to_dict(process.stage.value_stream)
    gates_before = _gate_counts()

    critic_results = [
        _provider_result(_critic_payload(repairable=True), model="test/critic-initial"),
        _provider_result(_critic_payload(repairable=False), model="test/critic-final"),
    ]
    with (
        patch(
            "ki_radar.accelerator.solution_critic_service.request_openrouter",
            side_effect=critic_results,
        ) as critic_provider,
        patch(
            "ki_radar.accelerator.solution_repair_service.request_openrouter",
            return_value=_provider_result(_repair_payload(), model="test/repair"),
        ) as repair_provider,
    ):
        initial = run_initial_solution_critic(solution_generation_run_id=run.pk)
        repair = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )
        final = run_final_solution_critic(solution_generation_run_id=run.pk)

    assert initial.status == SolutionQualityRun.Status.SUCCESS
    assert repair.status == SolutionQualityRun.Status.SUCCESS
    assert final.status == SolutionQualityRun.Status.SUCCESS
    assert critic_provider.call_count == 2
    assert repair_provider.call_count == 1

    run.refresh_from_db()
    process.refresh_from_db()
    process.stage.value_stream.refresh_from_db()
    assert "machine_repair" in run.preview_payload
    assert "adoption" not in run.preview_payload
    assert not SolutionOption.objects.filter(process_analysis=process).exists()
    assert not SolutionSelectionDecision.objects.filter(process_analysis=process).exists()
    assert model_to_dict(process) == process_before
    assert model_to_dict(process.stage.value_stream) == stream_before
    assert _gate_counts() == gates_before
