from __future__ import annotations

import copy
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.models import (
    AcceleratorLLMQuota,
    SolutionGenerationRun,
    SolutionQualityRun,
)
from ki_radar.accelerator.solution_critic_contract import validate_solution_critic_payload
from ki_radar.accelerator.solution_critic_service import (
    run_final_solution_critic,
    run_initial_solution_critic,
)
from ki_radar.accelerator.solution_generation_adoption import adopt_solution_generation_bundle
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.accelerator.solution_generation_validation import validate_solution_generation_payload
from ki_radar.accelerator.solution_quality_snapshot import build_solution_quality_snapshot
from ki_radar.accelerator.solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
    REPAIR_PROMPT_VERSION,
    REPAIR_SCHEMA_VERSION,
)
from ki_radar.accelerator.solution_repair_contract import SolutionRepairContractError
from ki_radar.accelerator.solution_repair_service import run_targeted_solution_repair
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.governance.models import GovernanceAssessment, GovernanceReview
from ki_radar.reviews.models import Review
from ki_radar.use_cases.models import UseCase

VALID_LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "17",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "100000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "4096",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "10",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "10",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "30",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS": "8192",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT": "10",
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


def _make_process(owner, business_unit, *, suffix: str) -> ProcessAnalysis:
    stream = ValueStream.objects.create(
        name=f"Beschaffung AP10 {suffix}",
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
        name=f"Angebotsvergleich AP10 {suffix}",
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


def _make_run(owner, business_unit, *, suffix: str) -> SolutionGenerationRun:
    process = _make_process(owner, business_unit, suffix=suffix)
    source_context = build_solution_generation_source_context(process)
    raw_options: dict[str, dict[str, object]] = {}
    for lane in OPTION_LANES:
        option: dict[str, object] = {}
        for field_name in GENERATED_OPTION_FIELDS:
            option[field_name] = _statement(
                f"{lane}: {field_name.replace('_', ' ')}",
                FIELD_SOURCES[field_name],
            )
        option["name"]["text"] = f"Option {lane}"
        raw_options[lane] = option
    validated = validate_solution_generation_payload(
        {
            "schema_version": GENERATION_SCHEMA_VERSION,
            "prompt_version": GENERATION_PROMPT_VERSION,
            "options": raw_options,
        },
        source_context,
    )
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


def _critic_payload(*, repairable: bool, text: str) -> dict[str, object]:
    finding: dict[str, object] = {
        "criterion": "bottleneck_fit",
        "option": "assistant",
        "field": "bottleneck_coverage",
        "finding": text,
        "source_ids": ["process.bottlenecks"],
        "repairable": repairable,
        "related_targets": [],
    }
    return {
        "schema_version": CRITIC_SCHEMA_VERSION,
        "prompt_version": CRITIC_PROMPT_VERSION,
        "findings": [finding],
    }


def _make_initial_critic(
    run: SolutionGenerationRun,
    *,
    repairable: bool,
    text: str = "Der Engpassbezug sollte fachlich präziser beschrieben werden.",
) -> SolutionQualityRun:
    source_context = build_solution_generation_source_context(run.process_analysis)
    snapshot = build_solution_quality_snapshot(
        preview_payload=run.preview_payload,
        source_context=source_context,
    )
    result_payload = validate_solution_critic_payload(
        _critic_payload(repairable=repairable, text=text),
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


def _make_empty_initial_critic(run: SolutionGenerationRun) -> SolutionQualityRun:
    source_context = build_solution_generation_source_context(run.process_analysis)
    snapshot = build_solution_quality_snapshot(
        preview_payload=run.preview_payload,
        source_context=source_context,
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
        result_payload={
            "schema_version": CRITIC_SCHEMA_VERSION,
            "prompt_version": CRITIC_PROMPT_VERSION,
            "findings": [],
        },
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
                    "Das Assistenzsystem unterstützt gezielt die manuelle Übertragung im Engpass.",
                    "process.bottlenecks",
                ),
            }
        ],
    }


def _provider_result(payload: dict[str, object], *, model: str) -> OpenRouterResult:
    body = json.dumps(payload, ensure_ascii=False)
    return OpenRouterResult(
        content=body,
        model=model,
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 100,
            "total_tokens": 200,
            "cost": "0.0002",
        },
        output_chars=len(body),
        finish_reason="stop",
    )


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
def test_unauthorized_user_cannot_start_quality_workflow_or_repair(
    client,
    owner,
    business_unit,
):
    run = _make_run(owner, business_unit, suffix="permissions")
    _make_initial_critic(run, repairable=True)
    outsider = owner.__class__.objects.create_user(username="ap10-outsider", password="secret")
    client.force_login(outsider)

    with patch(
        "ki_radar.accelerator.solution_generation_views.generate_solution_preview"
    ) as generation_service:
        start_response = client.post(
            reverse("accelerator:solution_generation_start", args=[run.process_analysis_id])
        )

    with patch(
        "ki_radar.accelerator.solution_generation_views.run_targeted_solution_repair"
    ) as repair_service:
        repair_response = client.post(
            reverse("accelerator:solution_generation_repair", args=[run.pk])
        )

    assert start_response.status_code == 403
    assert repair_response.status_code == 403
    generation_service.assert_not_called()
    repair_service.assert_not_called()
    assert SolutionQualityRun.objects.filter(solution_generation_run=run).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("quality_case", ["empty", "blindtext_nonrepairable"])
def test_quality_result_never_blocks_adoption_or_creates_gate_state(
    owner,
    business_unit,
    quality_case,
):
    run = _make_run(owner, business_unit, suffix=quality_case)
    if quality_case == "empty":
        _make_empty_initial_critic(run)
    else:
        _make_initial_critic(
            run,
            repairable=False,
            text="Lorem ipsum dolor sit amet; dieser Blindtext bleibt nur ein Critic-Finding.",
        )
    before = _gate_counts()

    result = adopt_solution_generation_bundle(actor=owner, run_id=run.pk)

    assert result.created is True
    options = list(SolutionOption.objects.filter(process_analysis=run.process_analysis))
    assert len(options) == 3
    assert _gate_counts() == before
    assert all(
        option.evaluation_status == SolutionOption.EvaluationStatus.DRAFT for option in options
    )
    assert all(option.feasibility == SolutionOption.Effort.NOT_ASSESSED for option in options)
    assert all(
        option.integration_effort == SolutionOption.Effort.NOT_ASSESSED for option in options
    )
    assert all(
        option.recommendation == SolutionOption.Recommendation.CANDIDATE for option in options
    )


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_repair_changes_only_bound_preview_and_never_writes_domain_gate_state(
    owner,
    business_unit,
):
    run = _make_run(owner, business_unit, suffix="repair-domain-invariance")
    _make_initial_critic(run, repairable=True)
    before_gates = _gate_counts()
    before_process = copy.deepcopy(
        {
            field.name: getattr(run.process_analysis, field.name)
            for field in run.process_analysis._meta.concrete_fields
            if field.name not in {"updated_at"}
        }
    )

    with patch(
        "ki_radar.accelerator.solution_repair_service.request_openrouter",
        return_value=_provider_result(_repair_payload(), model="test/repair"),
    ) as request_mock:
        repair = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    run.refresh_from_db()
    run.process_analysis.refresh_from_db()
    after_process = {
        field.name: getattr(run.process_analysis, field.name)
        for field in run.process_analysis._meta.concrete_fields
        if field.name not in {"updated_at"}
    }
    assert request_mock.call_count == 1
    assert repair.status == SolutionQualityRun.Status.SUCCESS
    assert "machine_repair" in run.preview_payload
    assert not SolutionOption.objects.filter(process_analysis=run.process_analysis).exists()
    assert after_process == before_process
    assert _gate_counts() == before_gates


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_initial_critic_http_and_exception_failures_are_terminal_without_retry(
    owner,
    business_unit,
):
    for suffix, failure, expected_code in (
        (
            "critic-http",
            OpenRouterUnavailable("HTTP 401", code="unauthorized"),
            "unauthorized",
        ),
        ("critic-exception", RuntimeError("provider exploded"), "internal_error"),
    ):
        run = _make_run(owner, business_unit, suffix=suffix)
        preview_before = copy.deepcopy(run.preview_payload)
        with patch(
            "ki_radar.accelerator.solution_critic_service.request_openrouter",
            side_effect=failure,
        ) as request_mock:
            first = run_initial_solution_critic(solution_generation_run_id=run.pk)
            second = run_initial_solution_critic(solution_generation_run_id=run.pk)

        run.refresh_from_db()
        assert request_mock.call_count == 1
        assert first.pk == second.pk
        assert first.status == SolutionQualityRun.Status.FAILED
        assert first.error_code == expected_code
        assert run.preview_payload == preview_before


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_repair_http_exception_and_quota_failures_preserve_preview_and_one_shot(
    owner,
    business_unit,
):
    scenarios = (
        ("repair-http", OpenRouterUnavailable("HTTP 429", code="rate_limit"), "rate_limit"),
        ("repair-exception", RuntimeError("provider exploded"), "internal_error"),
    )
    for suffix, failure, expected_code in scenarios:
        run = _make_run(owner, business_unit, suffix=suffix)
        _make_initial_critic(run, repairable=True)
        preview_before = copy.deepcopy(run.preview_payload)
        with patch(
            "ki_radar.accelerator.solution_repair_service.request_openrouter",
            side_effect=failure,
        ) as request_mock:
            first = run_targeted_solution_repair(
                solution_generation_run_id=run.pk,
                actor=owner,
            )
            with pytest.raises(SolutionRepairContractError) as consumed:
                run_targeted_solution_repair(
                    solution_generation_run_id=run.pk,
                    actor=owner,
                )

        run.refresh_from_db()
        assert request_mock.call_count == 1
        assert consumed.value.code == "repair_attempt_consumed"
        assert first.status == SolutionQualityRun.Status.FAILED
        assert first.error_code == expected_code
        assert run.preview_payload == preview_before

    quota_run = _make_run(owner, business_unit, suffix="repair-quota")
    _make_initial_critic(quota_run, repairable=True)
    preview_before = copy.deepcopy(quota_run.preview_payload)
    AcceleratorLLMQuota.objects.update_or_create(
        scope=AcceleratorLLMQuota.Scope.USER,
        quota_date=timezone.localdate(),
        user=owner,
        defaults={"calls": 10},
    )
    with patch("ki_radar.accelerator.solution_repair_service.request_openrouter") as request_mock:
        failed = run_targeted_solution_repair(
            solution_generation_run_id=quota_run.pk,
            actor=owner,
        )

    quota_run.refresh_from_db()
    request_mock.assert_not_called()
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "user_quota_exceeded"
    assert quota_run.preview_payload == preview_before


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_final_critic_http_exception_and_quota_failures_preserve_repaired_preview(
    owner,
    business_unit,
):
    def successful_repair(suffix: str) -> SolutionGenerationRun:
        run = _make_run(owner, business_unit, suffix=suffix)
        _make_initial_critic(run, repairable=True)
        with patch(
            "ki_radar.accelerator.solution_repair_service.request_openrouter",
            return_value=_provider_result(_repair_payload(), model="test/repair"),
        ):
            repair = run_targeted_solution_repair(
                solution_generation_run_id=run.pk,
                actor=owner,
            )
        assert repair.status == SolutionQualityRun.Status.SUCCESS
        run.refresh_from_db()
        return run

    for suffix, failure, expected_code in (
        (
            "final-http",
            OpenRouterUnavailable("HTTP 503", code="provider_unavailable"),
            "provider_unavailable",
        ),
        ("final-exception", RuntimeError("provider exploded"), "internal_error"),
    ):
        run = successful_repair(suffix)
        preview_before = copy.deepcopy(run.preview_payload)
        with patch(
            "ki_radar.accelerator.solution_critic_service.request_openrouter",
            side_effect=failure,
        ) as request_mock:
            first = run_final_solution_critic(solution_generation_run_id=run.pk)
            second = run_final_solution_critic(solution_generation_run_id=run.pk)

        run.refresh_from_db()
        assert request_mock.call_count == 1
        assert first.pk == second.pk
        assert first.status == SolutionQualityRun.Status.FAILED
        assert first.error_code == expected_code
        assert run.preview_payload == preview_before

    quota_run = successful_repair("final-quota")
    preview_before = copy.deepcopy(quota_run.preview_payload)
    user_quota = AcceleratorLLMQuota.objects.get(
        scope=AcceleratorLLMQuota.Scope.USER,
        quota_date=timezone.localdate(),
        user=owner,
    )
    user_quota.calls = 10
    user_quota.save(update_fields=["calls", "updated_at"])
    with patch("ki_radar.accelerator.solution_critic_service.request_openrouter") as request_mock:
        failed = run_final_solution_critic(solution_generation_run_id=quota_run.pk)

    quota_run.refresh_from_db()
    request_mock.assert_not_called()
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "user_quota_exceeded"
    assert quota_run.preview_payload == preview_before
