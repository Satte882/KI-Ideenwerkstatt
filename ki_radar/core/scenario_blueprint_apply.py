from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q

from ki_radar.architecture.forms import (
    ProcessAnalysisForm,
    SolutionOptionForm,
    ValueStreamForm,
    ValueStreamStageForm,
)
from ki_radar.architecture.models import (
    EvidenceBasis,
    ProcessAnalysis,
    SolutionOption,
    TimeToValue,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.use_cases.forms import UseCaseForm
from ki_radar.use_cases.models import UseCase

from .scenario_blueprint_diff import BlueprintGraphDiff, DiffStatus, build_blueprint_diff
from .scenario_blueprint_provenance import origin_source_snapshot, process_source_snapshot
from .scenario_blueprint_validation import ResolvedBlueprint, validate_blueprint


class BlueprintApplyError(RuntimeError):
    """Raised when a validated blueprint cannot be applied atomically."""


class BlueprintConflictError(BlueprintApplyError):
    def __init__(self, diff: BlueprintGraphDiff):
        self.diff = diff
        super().__init__("Blueprint-Apply blockiert: Der Szenariograph ist nicht vollständig neu.")


@dataclass(frozen=True)
class BlueprintApplyResult:
    scenario_key: str
    schema_version: str
    checksum: str
    result: str
    created_counts: dict[str, int]
    object_ids: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pick(source: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: source[field] for field in fields}


def _form_failure(label: str, form) -> BlueprintApplyError:
    messages = []
    for field, errors in form.errors.get_json_data().items():
        for error in errors:
            messages.append(f"{label}.{field}: {error['message']}")
    return BlueprintApplyError("Formvalidierung fehlgeschlagen: " + " | ".join(messages))


def _save_value_stream(resolved: ResolvedBlueprint) -> ValueStream:
    payload = resolved.payload["value_stream"]
    focus = payload["focus"]
    fields = (
        "name",
        "status",
        "description",
        "trigger",
        "outcome",
        "scope_in",
        "scope_out",
        "strategic_objective",
        "stakeholders",
        "constraints",
    )
    data = _pick(payload, fields)
    data.update(
        {
            "business_unit": resolved.business_unit.pk,
            "owner": resolved.actors["value_stream_owner"].pk,
            "business_domain": focus["business_domain"],
            "capability": focus["capability"],
            "strategic_impact": "",
            "economic_potential": "",
            "pain_intensity": "",
            "data_accessibility": "",
            "change_effort": "",
            "focus_status": focus["status"],
            "focus_rationale": "",
        }
    )
    form = ValueStreamForm(data=data)
    if not form.is_valid():
        raise _form_failure("value_stream", form)
    value_stream = form.save(commit=False)
    value_stream.demo_key = payload["key"]
    value_stream.created_by = resolved.actors["creator"]
    value_stream.save()
    return value_stream


def _save_stages(
    resolved: ResolvedBlueprint,
    value_stream: ValueStream,
) -> dict[str, ValueStreamStage]:
    fields = (
        "sequence",
        "name",
        "description",
        "actors",
        "systems",
        "documents",
        "pain_points",
        "baseline_metrics",
    )
    result = {}
    stages = sorted(
        resolved.payload["value_stream"]["stages"],
        key=lambda item: item["sequence"],
    )
    for payload in stages:
        form = ValueStreamStageForm(data=_pick(payload, fields))
        if not form.is_valid():
            raise _form_failure(f"stage.{payload['key']}", form)
        stage = form.save(commit=False)
        stage.value_stream = value_stream
        stage.save()
        result[payload["key"]] = stage
    return result


def _save_process(
    resolved: ResolvedBlueprint,
    stages: dict[str, ValueStreamStage],
) -> ProcessAnalysis:
    payload = resolved.payload["process_analysis"]
    fields = (
        "name",
        "status",
        "scope_start",
        "scope_end",
        "trigger",
        "outcome",
        "current_flow",
        "roles",
        "systems",
        "data_objects",
        "business_rules",
        "handoffs",
        "bottlenecks",
        "exceptions",
        "baseline_metrics",
        "target_state_principles",
    )
    form = ProcessAnalysisForm(data=_pick(payload, fields))
    if not form.is_valid():
        raise _form_failure("process_analysis", form)
    stage = stages[payload["stage_key"]]
    process = form.save(commit=False)
    process.stage = stage
    process.analyzed_by = resolved.actors["creator"]
    process.source_snapshot = process_source_snapshot(resolved, stage=stage)
    process.save()
    return process


def _save_options(
    resolved: ResolvedBlueprint,
    process: ProcessAnalysis,
) -> dict[str, SolutionOption]:
    fields = (
        "name",
        "option_type",
        "evaluation_status",
        "description",
        "expected_value",
        "bottleneck_coverage",
        "feasibility",
        "data_requirements",
        "application_impact",
        "integration_effort",
        "integration_impact",
        "technology_constraints",
        "risks",
        "architecture_fit",
    )
    result = {}
    for payload in sorted(
        resolved.payload["solution_options"],
        key=lambda item: item["key"],
    ):
        data = _pick(payload, fields)
        data.update(
            {
                "evidence_basis": EvidenceBasis.HYPOTHESIS,
                "time_to_value": TimeToValue.NOT_ASSESSED,
            }
        )
        form = SolutionOptionForm(data=data)
        if not form.is_valid():
            raise _form_failure(f"solution_option.{payload['key']}", form)
        option = form.save(commit=False)
        option.process_analysis = process
        option.recommendation = SolutionOption.Recommendation.CANDIDATE
        option.created_by = resolved.actors["creator"]
        option.save()
        result[payload["key"]] = option
    return result


def _save_use_case(resolved: ResolvedBlueprint) -> UseCase:
    payload = resolved.payload["use_case"]
    metric = payload["metric"]
    classification = payload["classification"]
    fields = (
        "title",
        "summary",
        "problem_statement",
        "affected_process",
        "target_users",
        "priority",
        "solution_type",
        "hosting_type",
        "provider",
        "product_name",
        "model_name",
        "source_systems",
        "data_sources",
        "interface_description",
        "intended_users",
        "intended_purpose",
        "expected_benefit",
        "benefit_category",
        "one_time_cost",
        "recurring_cost",
        "business_value",
        "technical_feasibility",
        "data_readiness",
        "risk_complexity",
        "human_oversight",
        "support_responsibility",
    )
    data = _pick(payload, fields)
    data.update(
        {
            "business_unit": resolved.business_unit.pk,
            "business_domain": classification["business_domain"],
            "business_capability": classification["capability"],
            "process_area": classification["process_area"],
            "business_owner": resolved.actors["business_owner"].pk,
            "coordinator": resolved.actors["coordinator"].pk,
            "technical_owner": resolved.actors["technical_owner"].pk,
            "metric_name": metric["name"],
            "metric_type": metric["type"],
            "metric_direction": metric["direction"],
            "metric_unit": metric["unit"],
            "metric_baseline": metric["baseline"],
            "metric_target": metric["target"],
            "metric_measurement_method": metric["measurement_method"],
        }
    )
    form = UseCaseForm(data=data)
    if not form.is_valid():
        raise _form_failure("use_case", form)
    use_case = form.save(commit=False)
    use_case.demo_key = payload["key"]
    use_case.submitter = resolved.actors["creator"]
    use_case.status = UseCase.Status.IDEA
    use_case.decision_status = UseCase.DecisionStatus.CLARIFICATION
    use_case.save()
    form.save_m2m()
    return use_case


def _lock_scenario_keys(resolved: ResolvedBlueprint) -> None:
    stream = resolved.payload["value_stream"]
    use_case = resolved.payload["use_case"]
    list(
        ValueStream.objects.select_for_update().filter(
            Q(demo_key=stream["key"]) | Q(name=stream["name"])
        )
    )
    list(
        UseCase.objects.select_for_update().filter(
            Q(demo_key=use_case["key"]) | Q(title=use_case["title"])
        )
    )


def _no_change_result(resolved: ResolvedBlueprint) -> BlueprintApplyResult:
    stream_key = resolved.payload["value_stream"]["key"]
    use_case_key = resolved.payload["use_case"]["key"]
    stream = ValueStream.objects.get(demo_key=stream_key)
    use_case = UseCase.objects.get(demo_key=use_case_key)
    return BlueprintApplyResult(
        scenario_key=resolved.payload["scenario_key"],
        schema_version=resolved.payload["schema_version"],
        checksum=resolved.checksum,
        result=DiffStatus.NO_CHANGE.value,
        created_counts={},
        object_ids={
            "value_stream": str(stream.pk),
            "use_case": str(use_case.pk),
        },
    )


def apply_blueprint(resolved: ResolvedBlueprint) -> BlueprintApplyResult:
    initial_diff = build_blueprint_diff(resolved)
    if initial_diff.is_no_change:
        return _no_change_result(resolved)
    if not initial_diff.can_apply:
        raise BlueprintConflictError(initial_diff)

    try:
        with transaction.atomic():
            _lock_scenario_keys(resolved)
            current = validate_blueprint(resolved.payload)
            locked_diff = build_blueprint_diff(current)
            if locked_diff.is_no_change:
                return _no_change_result(current)
            if not locked_diff.can_apply:
                raise BlueprintConflictError(locked_diff)

            value_stream = _save_value_stream(current)
            stages = _save_stages(current, value_stream)
            process = _save_process(current, stages)
            options = _save_options(current, process)
            use_case = _save_use_case(current)
            origin_data = current.payload["origin"]
            origin_stage = stages[origin_data["stage_key"]]
            origin_option = options[origin_data["solution_option_key"]]
            origin = UseCaseOrigin.objects.create(
                use_case=use_case,
                stage=origin_stage,
                process_analysis=process,
                solution_option=origin_option,
                source_snapshot=origin_source_snapshot(
                    current,
                    stage=origin_stage,
                    process_analysis=process,
                    solution_option=origin_option,
                ),
            )

            post_diff = build_blueprint_diff(current)
            if not post_diff.is_no_change:
                raise BlueprintApplyError(
                    "Post-Apply-Prüfung fehlgeschlagen; der vollständige Graph wird verworfen."
                )
            return BlueprintApplyResult(
                scenario_key=current.payload["scenario_key"],
                schema_version=current.payload["schema_version"],
                checksum=current.checksum,
                result=DiffStatus.CREATE.value,
                created_counts={
                    "value_streams": 1,
                    "stages": len(stages),
                    "process_analyses": 1,
                    "solution_options": len(options),
                    "use_cases": 1,
                    "origins": 1,
                },
                object_ids={
                    "value_stream": str(value_stream.pk),
                    "process_analysis": str(process.pk),
                    "use_case": str(use_case.pk),
                    "origin": str(origin.pk),
                },
            )
    except BlueprintApplyError:
        raise
    except IntegrityError as exc:
        raise BlueprintApplyError(
            "Blueprint konnte wegen eines konkurrierenden "
            "Datenbankkonflikts nicht angewendet werden."
        ) from exc
