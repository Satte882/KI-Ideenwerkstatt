from __future__ import annotations

import copy
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun, SolutionQualityRun
from ki_radar.accelerator.solution_critic_service import run_initial_solution_critic
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
from ki_radar.accelerator.solution_repair_service import run_targeted_solution_repair
from ki_radar.architecture.architecture_assessment import save_solution_architecture_assessment
from ki_radar.architecture.architecture_assessment_models import SolutionArchitectureAssessment
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.openrouter import OpenRouterResult

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "architecture_real_demo_v1.json"

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

SEMANTIC_CASE_IDS = (
    "quality_distinctiveness_near_identical",
    "quality_missing_bottleneck_reference",
    "quality_unsubstantiated_qualitative_claim",
    "quality_explicit_assumption_positive_control",
    "quality_unnecessary_architecture_complexity",
    "quality_structured_finding_reference",
)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _quality_case(case_id: str) -> dict[str, object]:
    return next(case for case in _fixture()["quality_cases"] if case["case_id"] == case_id)


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


def _critic_payload(case: dict[str, object]) -> dict[str, object]:
    expected = case["expected"]
    if not expected["finding_expected"]:
        findings = []
    else:
        target = expected["target"]
        findings = [
            {
                "criterion": expected["criterion"],
                "option": target["option"],
                "field": target["field"],
                "finding": case["description"],
                "source_ids": target["source_ids"],
                "repairable": expected["repairable"],
                "related_targets": [],
            }
        ]
    return {
        "schema_version": CRITIC_SCHEMA_VERSION,
        "prompt_version": CRITIC_PROMPT_VERSION,
        "findings": findings,
    }


def _repair_payload() -> dict[str, object]:
    return {
        "schema_version": REPAIR_SCHEMA_VERSION,
        "prompt_version": REPAIR_PROMPT_VERSION,
        "patches": [
            {
                "option": "assistant",
                "field": "bottleneck_coverage",
                "statement": _statement(
                    "Die Assistenz adressiert den synthetisch dokumentierten Engpass gezielt.",
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


def _make_manual_option(run: SolutionGenerationRun, owner) -> SolutionOption:
    return SolutionOption.objects.create(
        process_analysis=run.process_analysis,
        name="Manuelle Architektur-Referenzoption",
        option_type=SolutionOption.OptionType.ASSISTANT,
        description="Manuell angelegte Option für die Isolation der beiden Fähigkeiten.",
        expected_value="Keine automatische fachliche Entscheidung.",
        bottleneck_coverage="Adressiert die synthetische manuelle Übertragung.",
        data_requirements="Synthetische Angebote.",
        application_impact="Demo-ERP.",
        integration_impact="Keine produktive Integration.",
        technology_constraints="Synthetische Testumgebung.",
        risks="Keine automatische Freigabe.",
        architecture_fit="Assistierend und begrenzt.",
        created_by=owner,
    )


def _advisor_state(assessment: SolutionArchitectureAssessment) -> dict[str, object]:
    return {
        "simpler_solution_sufficient": assessment.simpler_solution_sufficient,
        "semantic_reasoning_required": assessment.semantic_reasoning_required,
        "multiple_known_ai_steps_required": assessment.multiple_known_ai_steps_required,
        "dynamic_orchestration_required": assessment.dynamic_orchestration_required,
        "architecture_mode": assessment.architecture_mode,
        "reason_codes": copy.deepcopy(assessment.reason_codes),
        "ruleset_version": assessment.ruleset_version,
        "version": assessment.version,
        "assessed_by_id": assessment.assessed_by_id,
    }


@pytest.mark.django_db
@pytest.mark.parametrize("case_id", SEMANTIC_CASE_IDS)
@override_settings(**VALID_LIMITS)
def test_fixture_quality_case_round_trips_through_productive_initial_critic(
    owner,
    business_unit,
    case_id,
):
    case = _quality_case(case_id)
    run = _make_generation_run(owner, business_unit, suffix=case_id)

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=_provider_result(_critic_payload(case), model="test/critic"),
    ) as request_mock:
        quality_run = run_initial_solution_critic(solution_generation_run_id=run.pk)

    assert request_mock.call_count == 1
    assert quality_run.status == SolutionQualityRun.Status.SUCCESS
    findings = quality_run.result_payload["findings"]
    expected = case["expected"]
    assert bool(findings) is expected["finding_expected"]

    if not findings:
        assert expected["criterion"] is None
        return

    finding = findings[0]
    target = expected["target"]
    assert finding["criterion"] == expected["criterion"]
    assert finding["option"] == target["option"]
    assert finding["field"] == target["field"]
    assert finding["source_ids"] == sorted(target["source_ids"])
    assert finding["repairable"] is expected["repairable"]
    assert finding["finding_id"].startswith("finding_")


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_advisor_assessment_does_not_change_quality_snapshot_or_critic_input(
    owner,
    business_unit,
):
    run = _make_generation_run(owner, business_unit, suffix="advisor-to-quality")
    source_context = build_solution_generation_source_context(run.process_analysis)
    snapshot_before = build_solution_quality_snapshot(
        preview_payload=run.preview_payload,
        source_context=source_context,
    )
    option = _make_manual_option(run, owner)
    assessment = save_solution_architecture_assessment(
        solution_option=option,
        answers={
            "simpler_solution_sufficient": "no",
            "semantic_reasoning_required": "yes",
            "multiple_known_ai_steps_required": "no",
            "dynamic_orchestration_required": "yes",
        },
        actor=owner,
    )
    snapshot_after = build_solution_quality_snapshot(
        preview_payload=run.preview_payload,
        source_context=build_solution_generation_source_context(run.process_analysis),
    )

    assert assessment.architecture_mode == "bounded_agent"
    assert snapshot_after.snapshot_hash == snapshot_before.snapshot_hash
    assert snapshot_after.document == snapshot_before.document

    case = _quality_case("quality_missing_bottleneck_reference")
    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=_provider_result(_critic_payload(case), model="test/critic"),
    ) as request_mock:
        quality_run = run_initial_solution_critic(solution_generation_run_id=run.pk)

    serialized_call = json.dumps(request_mock.call_args.kwargs, default=str, sort_keys=True)
    assert quality_run.status == SolutionQualityRun.Status.SUCCESS
    assert "bounded_agent" not in serialized_call
    assert "architecture-advisor-v1" not in serialized_call
    assert "dynamic_orchestration_required" not in serialized_call


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_critic_and_repair_do_not_change_persisted_advisor_assessment(
    owner,
    business_unit,
):
    run = _make_generation_run(owner, business_unit, suffix="quality-to-advisor")
    option = _make_manual_option(run, owner)
    assessment = save_solution_architecture_assessment(
        solution_option=option,
        answers={
            "simpler_solution_sufficient": "no",
            "semantic_reasoning_required": "yes",
            "multiple_known_ai_steps_required": "no",
            "dynamic_orchestration_required": "yes",
        },
        actor=owner,
    )
    advisor_before = _advisor_state(assessment)
    case = _quality_case("quality_missing_bottleneck_reference")

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=_provider_result(_critic_payload(case), model="test/critic"),
    ):
        critic_run = run_initial_solution_critic(solution_generation_run_id=run.pk)

    with patch(
        "ki_radar.accelerator.solution_repair_service.request_openrouter",
        return_value=_provider_result(_repair_payload(), model="test/repair"),
    ):
        repair_run = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    assessment.refresh_from_db()
    assert critic_run.status == SolutionQualityRun.Status.SUCCESS
    assert repair_run.status == SolutionQualityRun.Status.SUCCESS
    assert _advisor_state(assessment) == advisor_before
