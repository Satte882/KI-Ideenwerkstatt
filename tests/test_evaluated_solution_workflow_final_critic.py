from __future__ import annotations

import copy
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import transaction
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun, SolutionQualityRun
from ki_radar.accelerator.solution_critic_contract import validate_solution_critic_payload
from ki_radar.accelerator.solution_critic_service import (
    FinalSolutionCriticError,
    run_final_solution_critic,
    run_initial_solution_critic,
)
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from ki_radar.accelerator.solution_generation_effective import (
    build_validated_effective_solution_payload,
)
from ki_radar.accelerator.solution_generation_preview import (
    update_solution_generation_preview_edits,
)
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.accelerator.solution_generation_validation import validate_solution_generation_payload
from ki_radar.accelerator.solution_quality_runs import (
    mark_solution_quality_step_failed,
    mark_solution_quality_step_success,
)
from ki_radar.accelerator.solution_quality_snapshot import build_solution_quality_snapshot
from ki_radar.accelerator.solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
    REPAIR_PROMPT_VERSION,
    REPAIR_SCHEMA_VERSION,
)
from ki_radar.accelerator.solution_repair_contract import (
    SolutionRepairContractError,
    reserve_solution_repair_attempt,
)
from ki_radar.accelerator.solution_repair_service import run_targeted_solution_repair
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable

VALID_LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "17",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "100000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "4096",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "2",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "10",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "30",
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
        name="Beschaffung Final Critic",
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


def _valid_generation_payload() -> dict[str, object]:
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
    validated = validate_solution_generation_payload(_valid_generation_payload(), source_context)
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
        preview_payload=preview_payload,
        expires_at=timezone.now() + timedelta(days=30),
    )


def _critic_payload(*, repairable: bool = True) -> dict[str, object]:
    return {
        "schema_version": CRITIC_SCHEMA_VERSION,
        "prompt_version": CRITIC_PROMPT_VERSION,
        "findings": [
            {
                "criterion": "bottleneck_fit",
                "option": "assistant",
                "field": "bottleneck_coverage",
                "finding": "Der Engpassbezug sollte fachlich präziser beschrieben werden.",
                "source_ids": ["process.bottlenecks"],
                "repairable": repairable,
                "related_targets": [],
            }
        ],
    }


def _critic_provider_result(payload=None) -> OpenRouterResult:
    body = json.dumps(payload or _critic_payload(), ensure_ascii=False)
    return OpenRouterResult(
        content=body,
        model="test/critic",
        usage={
            "prompt_tokens": 150,
            "completion_tokens": 90,
            "total_tokens": 240,
            "cost": "0.000321",
        },
        output_chars=len(body),
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
                    "Das Assistenzsystem unterstützt gezielt die manuelle Übertragung im Engpass.",
                    "process.bottlenecks",
                ),
            }
        ],
    }


def _repair_provider_result() -> OpenRouterResult:
    body = json.dumps(_repair_payload(), ensure_ascii=False)
    return OpenRouterResult(
        content=body,
        model="test/repair",
        usage={
            "prompt_tokens": 180,
            "completion_tokens": 110,
            "total_tokens": 290,
            "cost": "0.000456",
        },
        output_chars=len(body),
        finish_reason="stop",
    )


def _make_initial_critic(run: SolutionGenerationRun) -> SolutionQualityRun:
    source_context = build_solution_generation_source_context(run.process_analysis)
    snapshot = build_solution_quality_snapshot(
        preview_payload=run.preview_payload,
        source_context=source_context,
    )
    result_payload = validate_solution_critic_payload(_critic_payload(), source_context)
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


def _persist_successful_repair(run: SolutionGenerationRun) -> SolutionQualityRun:
    reservation = reserve_solution_repair_attempt(
        solution_generation_run_id=run.pk,
        actor=run.requested_by,
    )
    repair_run = reservation.run
    plan = reservation.plan
    source_context = build_solution_generation_source_context(run.process_analysis)
    candidate_preview = copy.deepcopy(run.preview_payload)
    candidate_preview["machine_repair"] = {
        "quality_run_id": str(repair_run.pk),
        "input_hash": plan.snapshot_hash,
        "prompt_version": repair_run.prompt_version,
        "schema_version": repair_run.output_schema_version,
        "patches": copy.deepcopy(_repair_payload()["patches"]),
    }
    build_validated_effective_solution_payload(candidate_preview, source_context)
    output_snapshot = build_solution_quality_snapshot(
        preview_payload=candidate_preview,
        source_context=source_context,
    )
    run.preview_payload = candidate_preview
    run.save(update_fields=["preview_payload", "updated_at"])
    return mark_solution_quality_step_success(
        run_id=repair_run.pk,
        result_payload={
            "repair_payload": _repair_payload(),
            "finding_ids": list(plan.finding_ids),
            "input_hash": plan.snapshot_hash,
            "output_snapshot_hash": output_snapshot.snapshot_hash,
        },
        model_name="test/repair",
        output_chars=321,
        prompt_tokens=180,
        completion_tokens=110,
        total_tokens=290,
    )


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_final_critic_uses_same_structured_contract_once_and_preserves_repaired_preview(
    owner,
    business_unit,
):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    repair_run = _persist_successful_repair(run)
    run.refresh_from_db()
    preview_before = copy.deepcopy(run.preview_payload)

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=_critic_provider_result(_critic_payload(repairable=False)),
    ) as request_mock:
        final_run = run_final_solution_critic(solution_generation_run_id=run.pk)
        repeated = run_final_solution_critic(solution_generation_run_id=run.pk)

    assert request_mock.call_count == 1
    kwargs = request_mock.call_args.kwargs
    assert kwargs["max_tokens"] == 4096
    assert kwargs["timeout_seconds"] == 17
    assert kwargs["temperature"] is None
    assert kwargs["provider"] == {"require_parameters": True}
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    source_id_enum = kwargs["response_format"]["json_schema"]["schema"]["properties"]["findings"][
        "items"
    ]["properties"]["source_ids"]["items"]["enum"]
    assert source_id_enum == sorted(
        fact["source_id"] for fact in run.preview_payload["source_context"]["facts"]
    )

    final_run.refresh_from_db()
    run.refresh_from_db()
    assert final_run.step_type == SolutionQualityRun.StepType.FINAL_CRITIC
    assert final_run.status == SolutionQualityRun.Status.SUCCESS
    assert final_run.prompt_version == CRITIC_PROMPT_VERSION
    assert final_run.output_schema_version == CRITIC_SCHEMA_VERSION
    assert final_run.input_hash == repair_run.result_payload["output_snapshot_hash"]
    assert final_run.model_name == "test/critic"
    assert final_run.total_tokens == 240
    assert final_run.result_payload["findings"][0]["repairable"] is False
    assert repeated.pk == final_run.pk
    assert run.preview_payload == preview_before


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_final_critic_requires_successful_repair_before_any_provider_call(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    reservation = reserve_solution_repair_attempt(
        solution_generation_run_id=run.pk,
        actor=owner,
    )
    mark_solution_quality_step_failed(run_id=reservation.run.pk, error_code="timeout")

    with (
        patch(
            "ki_radar.accelerator.solution_critic_service.request_openrouter",
            return_value=_critic_provider_result(),
        ) as request_mock,
        pytest.raises(FinalSolutionCriticError) as exc_info,
    ):
        run_final_solution_critic(solution_generation_run_id=run.pk)

    assert exc_info.value.code == "final_critic_repair_unavailable"
    assert request_mock.call_count == 0
    assert not SolutionQualityRun.objects.filter(
        solution_generation_run=run,
        step_type=SolutionQualityRun.StepType.FINAL_CRITIC,
    ).exists()


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_final_critic_stale_binding_is_terminal_before_provider_and_preserves_preview(
    owner,
    business_unit,
):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    _persist_successful_repair(run)
    update_solution_generation_preview_edits(
        run_id=run.pk,
        edits={
            "organizational": {
                "description": "Human Review nach erfolgreichem Repair.",
            }
        },
    )
    run.refresh_from_db()
    preview_before = copy.deepcopy(run.preview_payload)

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=_critic_provider_result(),
    ) as request_mock:
        final_run = run_final_solution_critic(solution_generation_run_id=run.pk)

    run.refresh_from_db()
    assert request_mock.call_count == 0
    assert final_run.status == SolutionQualityRun.Status.FAILED
    assert final_run.error_code == "final_critic_stale"
    assert run.preview_payload == preview_before


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_final_critic_provider_failure_preserves_preview_and_consumes_attempt(
    owner,
    business_unit,
):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    _persist_successful_repair(run)
    run.refresh_from_db()
    preview_before = copy.deepcopy(run.preview_payload)

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        side_effect=OpenRouterUnavailable("Provider timeout", code="timeout"),
    ) as request_mock:
        failed = run_final_solution_critic(solution_generation_run_id=run.pk)

    assert request_mock.call_count == 1
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "timeout"

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=_critic_provider_result(),
    ) as retry_mock:
        repeated = run_final_solution_critic(solution_generation_run_id=run.pk)

    run.refresh_from_db()
    assert retry_mock.call_count == 0
    assert repeated.pk == failed.pk
    assert repeated.status == SolutionQualityRun.Status.FAILED
    assert run.preview_payload == preview_before


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_remaining_final_findings_end_in_human_review_without_second_repair(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    _persist_successful_repair(run)

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=_critic_provider_result(_critic_payload(repairable=True)),
    ):
        final_run = run_final_solution_critic(solution_generation_run_id=run.pk)

    assert final_run.status == SolutionQualityRun.Status.SUCCESS
    assert final_run.result_payload["findings"][0]["repairable"] is True

    with (
        patch(
            "ki_radar.accelerator.solution_repair_service.request_openrouter",
            return_value=_repair_provider_result(),
        ) as repair_mock,
        pytest.raises(SolutionRepairContractError) as exc_info,
    ):
        run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    assert exc_info.value.code == "repair_attempt_consumed"
    assert repair_mock.call_count == 0
    assert (
        SolutionQualityRun.objects.filter(
            solution_generation_run=run,
            step_type=SolutionQualityRun.StepType.REPAIR,
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
@override_settings(**VALID_LIMITS)
def test_successful_repair_persistence_schedules_exactly_one_final_critic(owner, business_unit):
    with patch(
        "ki_radar.accelerator.solution_quality_signals.run_initial_solution_critic"
    ) as initial_signal_mock:
        run = _make_generation_run(owner, business_unit)
    assert initial_signal_mock.call_count == 1
    _make_initial_critic(run)

    with (
        patch(
            "ki_radar.accelerator.solution_critic_service.request_openrouter",
            return_value=_critic_provider_result(_critic_payload(repairable=False)),
        ) as request_mock,
        transaction.atomic(),
    ):
        repair_run = _persist_successful_repair(run)

    assert repair_run.status == SolutionQualityRun.Status.SUCCESS
    assert request_mock.call_count == 1
    final_run = SolutionQualityRun.objects.get(
        solution_generation_run=run,
        step_type=SolutionQualityRun.StepType.FINAL_CRITIC,
    )
    assert final_run.status == SolutionQualityRun.Status.SUCCESS
    assert final_run.input_hash == repair_run.result_payload["output_snapshot_hash"]


@pytest.mark.django_db(transaction=True)
@override_settings(**VALID_LIMITS)
def test_failed_repair_persistence_never_schedules_final_critic(owner, business_unit):
    with patch(
        "ki_radar.accelerator.solution_quality_signals.run_initial_solution_critic"
    ) as initial_signal_mock:
        run = _make_generation_run(owner, business_unit)
    assert initial_signal_mock.call_count == 1
    _make_initial_critic(run)
    reservation = reserve_solution_repair_attempt(
        solution_generation_run_id=run.pk,
        actor=owner,
    )

    with (
        patch(
            "ki_radar.accelerator.solution_quality_signals.run_final_solution_critic"
        ) as final_signal_mock,
        transaction.atomic(),
    ):
        failed = mark_solution_quality_step_failed(
            run_id=reservation.run.pk,
            error_code="timeout",
        )

    assert failed.status == SolutionQualityRun.Status.FAILED
    assert final_signal_mock.call_count == 0
    assert not SolutionQualityRun.objects.filter(
        solution_generation_run=run,
        step_type=SolutionQualityRun.StepType.FINAL_CRITIC,
    ).exists()


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_workflow_has_hard_maximum_of_four_model_calls_including_generation(owner, business_unit):
    run = _make_generation_run(owner, business_unit)

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        side_effect=[
            _critic_provider_result(_critic_payload(repairable=True)),
            _critic_provider_result(_critic_payload(repairable=True)),
        ],
    ) as critic_mock:
        initial = run_initial_solution_critic(solution_generation_run_id=run.pk)
        repeated_initial = run_initial_solution_critic(solution_generation_run_id=run.pk)
        assert initial.pk == repeated_initial.pk

        with patch(
            "ki_radar.accelerator.solution_repair_service.request_openrouter",
            return_value=_repair_provider_result(),
        ) as repair_mock:
            repair = run_targeted_solution_repair(
                solution_generation_run_id=run.pk,
                actor=owner,
            )
            with pytest.raises(SolutionRepairContractError) as repair_exc:
                run_targeted_solution_repair(
                    solution_generation_run_id=run.pk,
                    actor=owner,
                )
            assert repair_exc.value.code == "repair_attempt_consumed"

        final = run_final_solution_critic(solution_generation_run_id=run.pk)
        repeated_final = run_final_solution_critic(solution_generation_run_id=run.pk)

    assert initial.status == SolutionQualityRun.Status.SUCCESS
    assert repair.status == SolutionQualityRun.Status.SUCCESS
    assert final.status == SolutionQualityRun.Status.SUCCESS
    assert repeated_final.pk == final.pk
    assert critic_mock.call_count == 2
    assert repair_mock.call_count == 1
    generation_model_calls = 1
    assert generation_model_calls + critic_mock.call_count + repair_mock.call_count == 4
    assert SolutionQualityRun.objects.filter(solution_generation_run=run).count() == 3


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_final_critic_truncated_output_is_terminal_and_preserves_repaired_preview(
    owner,
    business_unit,
):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    _persist_successful_repair(run)
    run.refresh_from_db()
    preview_before = copy.deepcopy(run.preview_payload)
    body = json.dumps(_critic_payload(), ensure_ascii=False)
    truncated_result = OpenRouterResult(
        content=body,
        model="test/critic",
        usage={},
        output_chars=len(body),
        finish_reason="length",
    )

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=truncated_result,
    ) as request_mock:
        failed = run_final_solution_critic(solution_generation_run_id=run.pk)

    run.refresh_from_db()
    assert request_mock.call_count == 1
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "output_truncated"
    assert run.preview_payload == preview_before

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=_critic_provider_result(),
    ) as retry_mock:
        repeated = run_final_solution_critic(solution_generation_run_id=run.pk)

    assert retry_mock.call_count == 0
    assert repeated.pk == failed.pk
    assert repeated.status == SolutionQualityRun.Status.FAILED


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
@pytest.mark.parametrize("content", ["{", "[]"])
def test_final_critic_invalid_response_is_terminal_and_preserves_repaired_preview(
    owner,
    business_unit,
    content,
):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    _persist_successful_repair(run)
    run.refresh_from_db()
    preview_before = copy.deepcopy(run.preview_payload)
    invalid_result = OpenRouterResult(
        content=content,
        model="test/critic",
        usage={},
        output_chars=len(content),
        finish_reason="stop",
    )

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=invalid_result,
    ) as request_mock:
        failed = run_final_solution_critic(solution_generation_run_id=run.pk)

    run.refresh_from_db()
    assert request_mock.call_count == 1
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "invalid_response"
    assert run.preview_payload == preview_before

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=_critic_provider_result(),
    ) as retry_mock:
        repeated = run_final_solution_critic(solution_generation_run_id=run.pk)

    assert retry_mock.call_count == 0
    assert repeated.pk == failed.pk
    assert repeated.status == SolutionQualityRun.Status.FAILED
