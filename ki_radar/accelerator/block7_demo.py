from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
)
from ki_radar.core.openrouter import OpenRouterResult
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.governance.models import GovernanceAssessment, GovernanceReview
from ki_radar.reviews.models import Review
from ki_radar.use_cases.models import UseCase

from . import block6_demo
from .models import SolutionGenerationRun
from .solution_generation_adoption import adopt_solution_generation_bundle
from .solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from .solution_generation_service import generate_solution_preview
from .solution_generation_sources import build_solution_generation_source_context

PROCESS_NAME = "Angebotsvergleich"
LANE_TITLES = {
    "organizational": "Vergleichsprozess standardisieren",
    "rule_automation": "Regelbasierten Angebotsvergleich automatisieren",
    "assistant": "Assistierten Angebotsvergleich einsetzen",
}
LANE_LABELS = {
    "organizational": "Organisatorischer Entwurf",
    "rule_automation": "Regelbasierter Entwurf",
    "assistant": "Assistenzentwurf",
}
FIELD_SOURCE_IDS = {
    "name": "process.name",
    "description": "process.current_flow",
    "expected_value": "process.current_flow",
    "bottleneck_coverage": "process.bottlenecks",
    "data_requirements": "process.data_objects",
    "application_impact": "process.systems",
    "integration_impact": "process.systems",
    "technology_constraints": "process.systems",
    "risks": "process.bottlenecks",
    "architecture_fit": "process.systems",
}


def _statement(*, lane: str, field_name: str) -> dict[str, object]:
    if field_name == "name":
        text = LANE_TITLES[lane]
    else:
        field_label = field_name.replace("_", " ")
        text = f"{LANE_LABELS[lane]}: {field_label} wird aus dem Angebotsvergleich abgeleitet."

    assumptions = []
    if lane == "assistant" and field_name == "risks":
        assumptions.append("Fachliche Prüfung bleibt vor jeder Auswahlentscheidung erforderlich.")

    open_evidence = []
    if lane == "assistant" and field_name == "technology_constraints":
        open_evidence.append("Betriebs- und Datenschutzleitplanken für Assistenzlösung klären.")

    return {
        "text": text,
        "source_ids": [FIELD_SOURCE_IDS[field_name]],
        "assumptions": assumptions,
        "open_evidence": open_evidence,
        "uncertainty": {
            "level": "low",
            "reason": "Der Entwurf bleibt bis zur fachlichen Prüfung unverbindlich.",
        },
    }


def _provider_payload() -> dict[str, object]:
    options = {}
    for lane in OPTION_LANES:
        lane_payload = {}
        for field_name in GENERATED_OPTION_FIELDS:
            lane_payload[field_name] = _statement(lane=lane, field_name=field_name)
        options[lane] = lane_payload

    return {
        "schema_version": GENERATION_SCHEMA_VERSION,
        "prompt_version": GENERATION_PROMPT_VERSION,
        "options": options,
    }


def _provider_result() -> OpenRouterResult:
    content = json.dumps(_provider_payload(), ensure_ascii=False)
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
        "cost": 0,
    }
    return OpenRouterResult(
        content=content,
        model="real-demo/deterministic",
        usage=usage,
        output_chars=len(content),
        finish_reason="stop",
    )


def _gate_snapshot() -> dict[str, int]:
    return {
        "process_validation": ProcessValidation.objects.count(),
        "solution_selection": SolutionSelectionDecision.objects.count(),
        "use_case": UseCase.objects.count(),
        "governance_assessment": GovernanceAssessment.objects.count(),
        "governance_review": GovernanceReview.objects.count(),
        "delivery_package": DeliveryPackage.objects.count(),
        "lifecycle_review": Review.objects.count(),
    }


def _gate_report(before: dict[str, int], after: dict[str, int]) -> dict[str, bool]:
    report = {}
    for key, value in before.items():
        report[f"{key}_unchanged"] = after[key] == value
    return report


def _preview_evidence(preview_payload: dict[str, object]) -> dict[str, bool]:
    statements = []
    options = preview_payload["options"]
    for lane in OPTION_LANES:
        for field_name in GENERATED_OPTION_FIELDS:
            statements.append(options[lane][field_name])

    has_uncertainty = True
    for statement in statements:
        uncertainty = statement["uncertainty"]
        if not uncertainty["level"] or not uncertainty["reason"]:
            has_uncertainty = False

    return {
        "has_sources": all(item["source_ids"] for item in statements),
        "has_assumptions": any(item["assumptions"] for item in statements),
        "has_open_evidence": any(item["open_evidence"] for item in statements),
        "has_uncertainty": has_uncertainty,
    }


def _rollback_report(*, actor: User, source_process: ProcessAnalysis) -> dict[str, object]:
    rollback_process = ProcessAnalysis.objects.create(
        stage=source_process.stage,
        name="Angebotsvergleich Rollback-Nachweis",
        scope_start=source_process.scope_start,
        scope_end=source_process.scope_end,
        trigger=source_process.trigger,
        outcome=source_process.outcome,
        current_flow=source_process.current_flow,
        roles=source_process.roles,
        systems=source_process.systems,
        data_objects=source_process.data_objects,
        bottlenecks=source_process.bottlenecks,
        baseline_metrics=source_process.baseline_metrics,
        analyzed_by=actor,
    )
    context = build_solution_generation_source_context(rollback_process)
    now = timezone.now()
    preview_payload = _provider_payload()
    preview_payload["source_context"] = context.provider_payload()
    preview_payload["edits"] = {}

    run = SolutionGenerationRun.objects.create(
        process_analysis=rollback_process,
        process_version=rollback_process.version,
        source_hash=context.source_hash,
        requested_by=actor,
        status=SolutionGenerationRun.Status.SUCCESS,
        model_name="real-demo/deterministic",
        prompt_version=GENERATION_PROMPT_VERSION,
        generation_schema_version=GENERATION_SCHEMA_VERSION,
        finished_at=now,
        expires_at=now + timedelta(days=1),
        preview_payload=preview_payload,
    )

    original_save = SolutionOption.save
    save_calls = 0

    def fail_second_save(instance, *args, **kwargs):
        nonlocal save_calls
        save_calls += 1
        if save_calls == 2:
            raise RuntimeError("simulated persistence failure")
        return original_save(instance, *args, **kwargs)

    error = ""
    with patch.object(SolutionOption, "save", new=fail_second_save):
        try:
            adopt_solution_generation_bundle(actor=actor, run_id=run.pk)
        except RuntimeError as exc:
            if str(exc) != "simulated persistence failure":
                raise
            error = "simulated_persistence_failure"

    if not error:
        raise AssertionError("Der erwartete Rollback-Fehler wurde nicht ausgelöst.")

    run.refresh_from_db()
    option_count = SolutionOption.objects.filter(process_analysis=rollback_process).count()
    report = {
        "error": error,
        "option_count": option_count,
        "adoption_recorded": "adoption" in run.preview_payload,
    }
    rollback_process.delete()
    return report


def run_block7_real_demo() -> dict[str, object]:
    block6_demo.run_block6_real_demo()
    actor = User.objects.get(username=block6_demo.DEMO_USERNAME)
    process = ProcessAnalysis.objects.get(
        stage__value_stream__demo_key=block6_demo.VALUE_STREAM_DEMO_KEY,
        name=PROCESS_NAME,
    )
    source_context = build_solution_generation_source_context(process)
    gates_before = _gate_snapshot()

    provider_path = "ki_radar.accelerator.solution_generation_service.request_openrouter"
    with patch(provider_path, return_value=_provider_result()) as provider_mock:
        run = generate_solution_preview(actor=actor, process_analysis_id=process.pk)

    preview_evidence = _preview_evidence(run.preview_payload)
    adoption = adopt_solution_generation_bundle(actor=actor, run_id=run.pk)
    gates_after = _gate_snapshot()
    rollback = _rollback_report(actor=actor, source_process=process)

    options = []
    for lane, option in zip(OPTION_LANES, adoption.options, strict=True):
        options.append(
            {
                "lane": lane,
                "name": option.name,
                "option_type": option.option_type,
                "evaluation_status": option.evaluation_status,
                "recommendation": option.recommendation,
                "feasibility": option.feasibility,
                "integration_effort": option.integration_effort,
            }
        )

    generation = {
        "provider_mode": "deterministic_ci_double",
        "provider_calls": provider_mock.call_count,
        "status": run.status,
        "schema_version": run.generation_schema_version,
        "prompt_version": run.prompt_version,
        "lanes": list(OPTION_LANES),
        "preview_option_count": len(run.preview_payload["options"]),
    }
    generation.update(preview_evidence)

    return {
        "marker": "[Real-DEMO]",
        "schema_version": "1",
        "path": "solution_generation",
        "source_setup": "block6_real_demo",
        "process": {
            "name": process.name,
            "status": process.status,
            "validation_state": source_context.validation_state,
            "required_source_gaps": list(source_context.missing_required),
        },
        "generation": generation,
        "adoption": {
            "created": adoption.created,
            "option_count": len(adoption.options),
            "options": options,
        },
        "gates": _gate_report(gates_before, gates_after),
        "rollback": rollback,
    }
