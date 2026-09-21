from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
from django.forms.models import model_to_dict
from django.test import override_settings

from ki_radar.accelerator.models import SolutionQualityRun
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
from ki_radar.accelerator.solution_generation_effective import (
    build_validated_effective_solution_payload,
)
from ki_radar.accelerator.solution_generation_service import generate_solution_preview
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.accelerator.solution_generation_validation import (
    validate_solution_generation_payload,
)
from ki_radar.accelerator.solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
    REPAIR_PROMPT_VERSION,
    REPAIR_SCHEMA_VERSION,
)
from ki_radar.accelerator.solution_repair_contract import SolutionRepairContractError
from ki_radar.accelerator.solution_repair_service import run_targeted_solution_repair
from ki_radar.architecture.architecture_advisor import explain_architecture
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

REPAIRED_BOTTLENECK_TEXT = (
    "Die Assistenz adressiert den dokumentierten Engpass der manuellen Rückfragen gezielt."
)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


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


def _critic_payload(*, repairable: bool) -> dict[str, object]:
    return {
        "schema_version": CRITIC_SCHEMA_VERSION,
        "prompt_version": CRITIC_PROMPT_VERSION,
        "findings": [
            {
                "criterion": "bottleneck_fit",
                "option": "assistant",
                "field": "bottleneck_coverage",
                "finding": (
                    "Der Engpassbezug benötigt nach dem maschinellen Repair eine manuelle "
                    "fachliche Prüfung."
                    if not repairable
                    else "Der Engpassbezug sollte präziser beschrieben werden."
                ),
                "source_ids": ["process.bottlenecks"],
                "repairable": repairable,
                "related_targets": [],
            }
        ],
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
                    REPAIRED_BOTTLENECK_TEXT,
                    "process.bottlenecks",
                ),
            }
        ],
    }


def _provider_result(payload: dict[str, object], *, model: str) -> OpenRouterResult:
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
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


class DeterministicRealDemoProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.responses_by_input: dict[tuple[str, str], str] = {}

    def _record(
        self,
        *,
        stage: str,
        kwargs: dict[str, object],
        payload: dict[str, object],
    ) -> OpenRouterResult:
        messages = kwargs.get("messages")
        if not isinstance(messages, list):
            raise AssertionError(f"Unexpected {stage} provider input: messages missing")
        canonical_input = json.dumps(
            messages, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        input_hash = hashlib.sha256(canonical_input.encode("utf-8")).hexdigest()
        output = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        key = (stage, input_hash)
        previous = self.responses_by_input.setdefault(key, output)
        if previous != output:
            raise AssertionError(f"Non-deterministic provider output for {stage}")
        self.calls.append(stage)
        return _provider_result(payload, model=f"deterministic/{stage}")

    def generation(self, **kwargs) -> OpenRouterResult:
        messages = kwargs.get("messages")
        if not isinstance(messages, list) or len(messages) != 2:
            raise AssertionError("Unexpected generation provider input")
        try:
            document = json.loads(str(messages[1]["content"]))
            facts = {
                fact["source_id"]: fact["value"]
                for fact in document["untrusted_source_data"]["facts"]
            }
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise AssertionError("Unknown generation input rejected fail-closed") from exc
        if (
            document.get("task") != "solution_option_drafts"
            or facts.get("process.name") != "Synthetischer Angebotsvergleich"
        ):
            raise AssertionError("Unknown generation input rejected fail-closed")
        return self._record(stage="generation", kwargs=kwargs, payload=_generation_payload())

    def critic(self, **kwargs) -> OpenRouterResult:
        messages = kwargs.get("messages")
        if not isinstance(messages, list) or len(messages) != 2:
            raise AssertionError("Unexpected critic provider input")
        try:
            document = json.loads(str(messages[1]["content"]))
            lane_index = list(OPTION_LANES).index("assistant")
            field_index = list(GENERATED_OPTION_FIELDS).index("bottleneck_coverage")
            target_text = document["options"][lane_index][field_index][0]
        except (KeyError, TypeError, ValueError, IndexError, json.JSONDecodeError) as exc:
            raise AssertionError("Unknown critic input rejected fail-closed") from exc

        if target_text == "assistant: bottleneck coverage":
            return self._record(
                stage="initial_critic",
                kwargs=kwargs,
                payload=_critic_payload(repairable=True),
            )
        if target_text == REPAIRED_BOTTLENECK_TEXT:
            return self._record(
                stage="final_critic",
                kwargs=kwargs,
                payload=_critic_payload(repairable=False),
            )
        raise AssertionError("Unknown critic target state rejected fail-closed")

    def repair(self, **kwargs) -> OpenRouterResult:
        messages = kwargs.get("messages")
        if not isinstance(messages, list) or len(messages) != 2:
            raise AssertionError("Unexpected repair provider input")
        try:
            document = json.loads(str(messages[1]["content"]))
            allowed_targets = document["allowed_targets"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise AssertionError("Unknown repair input rejected fail-closed") from exc
        if allowed_targets != [{"option": "assistant", "field": "bottleneck_coverage"}]:
            raise AssertionError("Unknown repair target rejected fail-closed")
        return self._record(stage="repair", kwargs=kwargs, payload=_repair_payload())


def _make_process(owner, business_unit) -> ProcessAnalysis:
    demo = _fixture()["real_demo"]
    stream_data = demo["value_stream"]
    process_data = demo["process_analysis"]
    stream = ValueStream.objects.create(
        name=stream_data["name"],
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
        name=process_data["name"],
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


def _make_option(process: ProcessAnalysis, owner, *, name: str) -> SolutionOption:
    return SolutionOption.objects.create(
        process_analysis=process,
        name=name,
        option_type=SolutionOption.OptionType.ASSISTANT,
        recommendation=SolutionOption.Recommendation.CANDIDATE,
        evaluation_status=SolutionOption.EvaluationStatus.ASSESSED,
        description="Synthetische bestehende Vergleichsoption.",
        expected_value="Synthetisch dokumentierter Nutzen.",
        bottleneck_coverage="Synthetisch dokumentierter Engpassbezug.",
        feasibility=SolutionOption.Effort.HIGH,
        data_requirements="Synthetische Angebotsdaten.",
        application_impact="Demo-ERP.",
        integration_impact="Synthetische Schnittstelle.",
        integration_effort=SolutionOption.Effort.MEDIUM,
        technology_constraints="Synthetische Testumgebung.",
        risks="Synthetisch dokumentiertes Risiko.",
        architecture_fit="Synthetisch dokumentierter Architecture Fit.",
        created_by=owner,
    )


def _protected_option_state(options: list[SolutionOption]) -> dict[str, dict[str, str]]:
    return {
        str(option.pk): {
            "feasibility": option.feasibility,
            "integration_effort": option.integration_effort,
            "evaluation_status": option.evaluation_status,
            "recommendation": option.recommendation,
        }
        for option in options
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


def _validated_raw_preview(run, process: ProcessAnalysis) -> dict[str, object]:
    source_context = build_solution_generation_source_context(process)
    return validate_solution_generation_payload(
        {
            "schema_version": run.preview_payload["schema_version"],
            "prompt_version": run.preview_payload["prompt_version"],
            "options": run.preview_payload["options"],
        },
        source_context,
    )


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_architecture_real_demo_runs_productive_paths_with_deterministic_provider(
    owner,
    business_unit,
):
    fixture = _fixture()
    assert fixture["data_classification"] == "synthetic_anonymized"
    assert fixture["real_demo"]["synthetic"] is True
    assert fixture["real_demo"]["contains_personal_data"] is False

    process = _make_process(owner, business_unit)
    options = [
        _make_option(process, owner, name="Advisor Controlled LLM"),
        _make_option(process, owner, name="Advisor Fixed Workflow"),
        _make_option(process, owner, name="Advisor Assessment Open"),
    ]
    option_state_before = _protected_option_state(options)
    process_before = model_to_dict(process)
    stream_before = model_to_dict(process.stage.value_stream)
    gates_before = _gate_counts()

    advisor_cases = {case["case_id"]: case for case in fixture["advisor_cases"]}
    selected_case_ids = (
        "advisor_canonical_controlled_llm",
        "advisor_adversarial_high_complexity_fixed_workflow",
        "advisor_adversarial_dynamic_claim_fixed_flow",
    )
    explanations = []
    for option, case_id in zip(options, selected_case_ids, strict=True):
        case = advisor_cases[case_id]
        assessment = save_solution_architecture_assessment(
            solution_option=option,
            answers=case["answers"],
            actor=owner,
        )
        assert assessment.architecture_mode == case["expected"]["mode"]
        assert assessment.reason_codes == case["expected"]["reason_codes"]
        explanations.append(
            explain_architecture(assessment.architecture_mode, assessment.reason_codes)
        )

    assert explanations[0].why_pattern
    assert explanations[0].why_no_agent
    assert explanations[1].mode == "llm_workflow"
    assert explanations[1].why_no_agent
    assert explanations[2].mode == "assessment_open"
    assert explanations[2].why_pattern
    assert explanations[2].open_points

    quality_cases = {case["case_id"]: case for case in fixture["quality_cases"]}
    assert quality_cases["quality_full_path_call_cap"]["expected"]["provider_calls_max"] == 4
    assert (
        quality_cases["quality_remaining_final_finding_human_review"]["expected"][
            "human_review_required"
        ]
        is True
    )

    provider = DeterministicRealDemoProvider()
    with (
        patch(
            "ki_radar.accelerator.solution_generation_service.request_openrouter",
            side_effect=provider.generation,
        ),
        patch(
            "ki_radar.accelerator.solution_critic_service.request_openrouter",
            side_effect=provider.critic,
        ),
        patch(
            "ki_radar.accelerator.solution_repair_service.request_openrouter",
            side_effect=provider.repair,
        ),
    ):
        generation = generate_solution_preview(
            actor=owner,
            process_analysis_id=process.pk,
        )
        validated_before = _validated_raw_preview(generation, process)
        preview_before_repair = deepcopy(generation.preview_payload)

        initial = run_initial_solution_critic(solution_generation_run_id=generation.pk)
        assert initial.status == SolutionQualityRun.Status.SUCCESS
        initial_findings = initial.result_payload["findings"]
        assert len(initial_findings) == 1
        assert initial_findings[0]["criterion"] == "bottleneck_fit"
        assert initial_findings[0]["option"] == "assistant"
        assert initial_findings[0]["field"] == "bottleneck_coverage"
        assert initial_findings[0]["source_ids"] == ["process.bottlenecks"]
        assert initial_findings[0]["repairable"] is True

        repair = run_targeted_solution_repair(
            solution_generation_run_id=generation.pk,
            actor=owner,
        )
        assert repair.status == SolutionQualityRun.Status.SUCCESS

        generation.refresh_from_db()
        validated_after_raw = _validated_raw_preview(generation, process)
        source_context = build_solution_generation_source_context(process)
        validated_after_effective = build_validated_effective_solution_payload(
            generation.preview_payload,
            source_context,
        )
        assert validated_before == validated_after_raw
        assert generation.preview_payload["options"] == preview_before_repair["options"]
        assert "machine_repair" in generation.preview_payload
        assert (
            validated_after_effective["options"]["assistant"]["bottleneck_coverage"]["text"]
            == REPAIRED_BOTTLENECK_TEXT
        )

        final = run_final_solution_critic(solution_generation_run_id=generation.pk)
        assert final.status == SolutionQualityRun.Status.SUCCESS
        final_findings = final.result_payload["findings"]
        assert len(final_findings) == 1
        assert final_findings[0]["repairable"] is False
        assert bool(final_findings) is True

        with pytest.raises(SolutionRepairContractError) as exc_info:
            run_targeted_solution_repair(
                solution_generation_run_id=generation.pk,
                actor=owner,
            )
        assert exc_info.value.code == "repair_attempt_consumed"

    assert provider.calls == ["generation", "initial_critic", "repair", "final_critic"]
    assert len(provider.calls) == 4
    assert len(provider.responses_by_input) == 4
    assert SolutionQualityRun.objects.filter(solution_generation_run=generation).count() == 3
    assert (
        SolutionQualityRun.objects.filter(
            solution_generation_run=generation,
            step_type=SolutionQualityRun.StepType.REPAIR,
        ).count()
        == 1
    )

    process.refresh_from_db()
    process.stage.value_stream.refresh_from_db()
    for option in options:
        option.refresh_from_db()
    assert _protected_option_state(options) == option_state_before
    assert model_to_dict(process) == process_before
    assert model_to_dict(process.stage.value_stream) == stream_before
    assert _gate_counts() == gates_before
