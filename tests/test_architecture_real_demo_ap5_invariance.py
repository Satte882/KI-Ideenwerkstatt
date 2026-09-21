from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier, Lock
from unittest.mock import patch

import pytest
from django.db import close_old_connections
from django.forms.models import model_to_dict
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun, SolutionQualityRun
from ki_radar.accelerator.solution_critic_contract import validate_solution_critic_payload
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
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.accelerator.solution_generation_validation import (
    validate_solution_generation_payload,
)
from ki_radar.accelerator.solution_quality_snapshot import build_solution_quality_snapshot
from ki_radar.accelerator.solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
    REPAIR_PROMPT_VERSION,
    REPAIR_SCHEMA_VERSION,
)
from ki_radar.accelerator.solution_repair_contract import SolutionRepairContractError
from ki_radar.accelerator.solution_repair_service import run_targeted_solution_repair
from ki_radar.architecture.architecture_assessment import save_solution_architecture_assessment
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

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "architecture_real_demo_v1.json"

VALID_LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "17",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "100000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "4096",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "10",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "20",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "100",
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


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _make_process(owner, business_unit, *, suffix: str) -> ProcessAnalysis:
    demo = _fixture()["real_demo"]
    stream_data = demo["value_stream"]
    process_data = demo["process_analysis"]
    stream = ValueStream.objects.create(
        name=f"{stream_data['name']} {suffix}",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger=stream_data["trigger"],
        outcome=stream_data["outcome"],
        scope_in=stream_data["scope_in"],
        strategic_objective=stream_data["strategic_objective"],
        constraints=stream_data["constraints"],
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name=process_data["stage_name"],
        description=process_data["stage_description"],
        actors=process_data["actors"],
        systems=process_data["systems"],
        documents=process_data["documents"],
        pain_points=process_data["pain_points"],
        baseline_metrics=process_data["baseline_metrics"],
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name=f"{process_data['name']} {suffix}",
        scope_start=process_data["scope_start"],
        scope_end=process_data["scope_end"],
        trigger=process_data["trigger"],
        outcome=process_data["outcome"],
        current_flow=process_data["current_flow"],
        roles=process_data["roles"],
        systems=process_data["systems"],
        data_objects=process_data["data_objects"],
        business_rules=process_data["business_rules"],
        handoffs=process_data["handoffs"],
        bottlenecks=process_data["bottlenecks"],
        exceptions=process_data["exceptions"],
        baseline_metrics=process_data["baseline_metrics"],
        target_state_principles=process_data["target_state_principles"],
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
            "reason": "Direkt aus der synthetischen Referenzquelle abgeleitet.",
        },
    }


def _make_generation_run(owner, business_unit, *, suffix: str) -> SolutionGenerationRun:
    process = _make_process(owner, business_unit, suffix=suffix)
    source_context = build_solution_generation_source_context(process)
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
    validated = validate_solution_generation_payload(
        {
            "schema_version": GENERATION_SCHEMA_VERSION,
            "prompt_version": GENERATION_PROMPT_VERSION,
            "options": options,
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


def _seed_initial_critic(run: SolutionGenerationRun) -> SolutionQualityRun:
    source_context = build_solution_generation_source_context(run.process_analysis)
    snapshot = build_solution_quality_snapshot(
        preview_payload=run.preview_payload,
        source_context=source_context,
    )
    result_payload = validate_solution_critic_payload(
        _critic_payload(repairable=True),
        source_context,
    )
    existing_runs = SolutionQualityRun.objects.filter(
        solution_generation_run=run,
        step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
    )
    existing = existing_runs.first()
    if existing is not None:
        return existing
    return SolutionQualityRun.objects.create(
        solution_generation_run=run,
        requested_by=run.requested_by,
        step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
        status=SolutionQualityRun.Status.SUCCESS,
        provider="deterministic-test-prerequisite",
        model_name="contract-seed",
        prompt_version=CRITIC_PROMPT_VERSION,
        output_schema_version=CRITIC_SCHEMA_VERSION,
        input_hash=snapshot.snapshot_hash,
        finished_at=timezone.now(),
        result_payload=result_payload,
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
                    "Die Assistenz adressiert gezielt den synthetisch dokumentierten Engpass.",
                    "process.bottlenecks",
                ),
            }
        ],
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


def _manual_option(run: SolutionGenerationRun, owner) -> SolutionOption:
    return SolutionOption.objects.create(
        process_analysis=run.process_analysis,
        name="Bestehende manuelle Vergleichsoption",
        option_type=SolutionOption.OptionType.ASSISTANT,
        recommendation=SolutionOption.Recommendation.PREFERRED,
        evaluation_status=SolutionOption.EvaluationStatus.ASSESSED,
        description="Manuell gepflegte Option vor #213.",
        expected_value="Manuell dokumentierter Nutzen.",
        bottleneck_coverage="Manuell dokumentierter Engpassbezug.",
        feasibility=SolutionOption.Effort.HIGH,
        data_requirements="Synthetische Angebotsdaten.",
        application_impact="Demo-ERP.",
        integration_impact="Manuell dokumentierte Schnittstelle.",
        integration_effort=SolutionOption.Effort.MEDIUM,
        technology_constraints="Synthetische Testumgebung.",
        risks="Manuell dokumentiertes Risiko.",
        architecture_fit="Manuell dokumentierter Architecture Fit.",
        created_by=owner,
    )


def _protected_option_state(option: SolutionOption) -> dict[str, str]:
    return {
        "feasibility": option.feasibility,
        "integration_effort": option.integration_effort,
        "evaluation_status": option.evaluation_status,
        "recommendation": option.recommendation,
    }


@pytest.mark.django_db(transaction=True)
@override_settings(**VALID_LIMITS)
def test_concurrent_repair_triggers_create_one_reservation_and_one_provider_call(
    owner,
    business_unit,
):
    with patch("ki_radar.accelerator.solution_quality_signals.run_initial_solution_critic"):
        run = _make_generation_run(owner, business_unit, suffix="repair-race")
    initial = _seed_initial_critic(run)
    assert initial.status == SolutionQualityRun.Status.SUCCESS

    barrier = Barrier(2)
    provider_lock = Lock()
    provider_calls = 0

    def repair_provider(**kwargs):
        nonlocal provider_calls
        with provider_lock:
            provider_calls += 1
        return _provider_result(_repair_payload(), model="test/repair")

    def trigger_repair() -> tuple[str, str]:
        close_old_connections()
        try:
            barrier.wait()
            repaired = run_targeted_solution_repair(
                solution_generation_run_id=run.pk,
                actor=owner,
            )
            return "success", str(repaired.pk)
        except SolutionRepairContractError as exc:
            return "error", exc.code
        finally:
            close_old_connections()

    with (
        patch(
            "ki_radar.accelerator.solution_repair_service.request_openrouter",
            side_effect=repair_provider,
        ),
        patch("ki_radar.accelerator.solution_quality_signals.run_final_solution_critic"),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        outcomes = list(executor.map(lambda _: trigger_repair(), range(2)))

    assert sorted(status for status, _ in outcomes) == ["error", "success"]
    assert [code for status, code in outcomes if status == "error"] == ["repair_attempt_consumed"]
    assert provider_calls == 1
    repair_runs = SolutionQualityRun.objects.filter(
        solution_generation_run=run,
        step_type=SolutionQualityRun.StepType.REPAIR,
    )
    assert repair_runs.count() == 1
    assert repair_runs.get().status == SolutionQualityRun.Status.SUCCESS

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=_provider_result(_critic_payload(repairable=False), model="test/final-critic"),
    ):
        final = run_final_solution_critic(solution_generation_run_id=run.pk)
    assert final.status == SolutionQualityRun.Status.SUCCESS

    with (
        patch("ki_radar.accelerator.solution_repair_service.request_openrouter") as second_provider,
        pytest.raises(SolutionRepairContractError) as exc_info,
    ):
        run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )
    assert exc_info.value.code == "repair_attempt_consumed"
    second_provider.assert_not_called()
    assert repair_runs.count() == 1


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_manual_option_and_plain_block7_preview_preserve_all_protected_gate_state(
    owner,
    business_unit,
):
    run = _make_generation_run(owner, business_unit, suffix="backward-compatible")
    process = run.process_analysis
    manual_option = _manual_option(run, owner)
    protected_before = _protected_option_state(manual_option)
    process_before = model_to_dict(process)
    stream_before = model_to_dict(process.stage.value_stream)
    gates_before = _gate_counts()

    assert "fixture_version" not in run.preview_payload
    assert "real_demo" not in run.preview_payload
    assert "machine_repair" not in run.preview_payload

    assessment = save_solution_architecture_assessment(
        solution_option=manual_option,
        answers={
            "simpler_solution_sufficient": "no",
            "semantic_reasoning_required": "yes",
            "multiple_known_ai_steps_required": "no",
            "dynamic_orchestration_required": "yes",
        },
        actor=owner,
    )
    assert assessment.architecture_mode == "bounded_agent"

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
    manual_option.refresh_from_db()
    process.refresh_from_db()
    process.stage.value_stream.refresh_from_db()

    assert _protected_option_state(manual_option) == protected_before
    assert SolutionOption.objects.filter(process_analysis=process).count() == 1
    assert model_to_dict(process) == process_before
    assert model_to_dict(process.stage.value_stream) == stream_before
    assert _gate_counts() == gates_before
    assert "machine_repair" in run.preview_payload
    assert "fixture_version" not in run.preview_payload
    assert "real_demo" not in run.preview_payload
