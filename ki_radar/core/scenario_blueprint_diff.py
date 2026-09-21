from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from django.core.exceptions import ObjectDoesNotExist

from ki_radar.architecture.focus import get_value_stream_focus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase

from .scenario_blueprint_validation import ResolvedBlueprint


class DiffStatus(StrEnum):
    CREATE = "CREATE"
    NO_CHANGE = "NO_CHANGE"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class FieldDifference:
    field: str
    current: Any
    expected: Any


@dataclass(frozen=True)
class ObjectDifference:
    object_type: str
    key: str
    status: DiffStatus
    differences: tuple[FieldDifference, ...] = ()


@dataclass(frozen=True)
class BlueprintGraphDiff:
    scenario_key: str
    schema_version: str
    checksum: str
    objects: tuple[ObjectDifference, ...]

    @property
    def has_conflicts(self) -> bool:
        return any(item.status == DiffStatus.CONFLICT for item in self.objects)

    @property
    def is_create(self) -> bool:
        return bool(self.objects) and all(item.status == DiffStatus.CREATE for item in self.objects)

    @property
    def is_no_change(self) -> bool:
        return bool(self.objects) and all(
            item.status == DiffStatus.NO_CHANGE for item in self.objects
        )

    @property
    def can_apply(self) -> bool:
        return self.is_create and not self.has_conflicts

    @property
    def graph_status(self) -> DiffStatus:
        if self.has_conflicts:
            return DiffStatus.CONFLICT
        if self.is_no_change:
            return DiffStatus.NO_CHANGE
        if self.is_create:
            return DiffStatus.CREATE
        return DiffStatus.CONFLICT

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.update(
            {
                "graph_status": self.graph_status.value,
                "has_conflicts": self.has_conflicts,
                "can_apply": self.can_apply,
                "dry_run": True,
                "data_changed": False,
            }
        )
        for item in result["objects"]:
            item["status"] = item["status"].value
        return result


STREAM_FIELDS = (
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
STAGE_FIELDS = (
    "sequence",
    "name",
    "description",
    "actors",
    "systems",
    "documents",
    "pain_points",
    "baseline_metrics",
)
PROCESS_FIELDS = (
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
OPTION_FIELDS = (
    "name",
    "option_type",
    "recommendation",
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
USE_CASE_FIELDS = (
    "title",
    "status",
    "decision_status",
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


def _display(value: Any) -> Any:
    if hasattr(value, "pk"):
        return str(value.pk)
    return value


def _model_values(instance: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: getattr(instance, field) for field in fields}


def _payload_values(payload: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: payload[field] for field in fields}


def _compare_values(
    current: dict[str, Any], expected: dict[str, Any]
) -> tuple[FieldDifference, ...]:
    return tuple(
        FieldDifference(
            field=field,
            current=_display(current.get(field)),
            expected=_display(expected[field]),
        )
        for field in sorted(expected)
        if current.get(field) != expected[field]
    )


def _object_diff(
    object_type: str,
    key: str,
    instance: Any | None,
    current: dict[str, Any] | None,
    expected: dict[str, Any],
) -> ObjectDifference:
    if instance is None:
        return ObjectDifference(object_type, key, DiffStatus.CREATE)
    differences = _compare_values(current or {}, expected)
    status = DiffStatus.CONFLICT if differences else DiffStatus.NO_CHANGE
    return ObjectDifference(object_type, key, status, differences)


def _expected_stream(resolved: ResolvedBlueprint) -> dict[str, Any]:
    data = resolved.payload["value_stream"]
    expected = _payload_values(data, STREAM_FIELDS)
    expected.update(
        {
            "business_unit": resolved.business_unit.pk,
            "owner": resolved.actors["value_stream_owner"].pk,
        }
    )
    return expected


def _current_stream(stream: ValueStream) -> dict[str, Any]:
    current = _model_values(stream, STREAM_FIELDS)
    current.update(
        {
            "business_unit": stream.business_unit_id,
            "owner": stream.owner_id,
        }
    )
    return current


def _focus_diff(stream: ValueStream | None, resolved: ResolvedBlueprint) -> ObjectDifference:
    if stream is None:
        return ObjectDifference("value_stream_focus", "focus", DiffStatus.CREATE)
    focus = get_value_stream_focus(stream)
    if focus is None:
        return ObjectDifference("value_stream_focus", "focus", DiffStatus.CONFLICT)
    source = resolved.payload["value_stream"]["focus"]
    expected = {
        "business_domain": source["business_domain"],
        "capability": source["capability"],
        "status": source["status"],
        "strategic_impact": "",
        "economic_potential": "",
        "pain_intensity": "",
        "data_accessibility": "",
        "change_effort": "",
        "rationale": "",
    }
    current = {field: getattr(focus, field) for field in expected}
    return _object_diff("value_stream_focus", "focus", focus, current, expected)


def _expected_use_case(resolved: ResolvedBlueprint) -> dict[str, Any]:
    data = resolved.payload["use_case"]
    metric = data["metric"]
    expected = _payload_values(data, USE_CASE_FIELDS)
    expected.update(
        {
            "business_unit": resolved.business_unit.pk,
            "submitter": resolved.actors["creator"].pk,
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
    return expected


def _current_use_case(use_case: UseCase) -> dict[str, Any]:
    current = _model_values(use_case, USE_CASE_FIELDS)
    current.update(
        {
            "business_unit": use_case.business_unit_id,
            "submitter": use_case.submitter_id,
            "business_owner": use_case.business_owner_id,
            "coordinator": use_case.coordinator_id,
            "technical_owner": use_case.technical_owner_id,
            "metric_name": use_case.metric_name,
            "metric_type": use_case.metric_type,
            "metric_direction": use_case.metric_direction,
            "metric_unit": use_case.metric_unit,
            "metric_baseline": use_case.metric_baseline,
            "metric_target": use_case.metric_target,
            "metric_measurement_method": use_case.metric_measurement_method,
        }
    )
    return current


def _classification_diff(use_case: UseCase | None, resolved: ResolvedBlueprint) -> ObjectDifference:
    if use_case is None:
        return ObjectDifference("use_case_classification", "classification", DiffStatus.CREATE)
    try:
        classification = use_case.classification
    except ObjectDoesNotExist:
        return ObjectDifference(
            "use_case_classification",
            "classification",
            DiffStatus.CONFLICT,
        )
    fields = ("business_domain", "capability", "process_area")
    return _object_diff(
        "use_case_classification",
        "classification",
        classification,
        _model_values(classification, fields),
        _payload_values(resolved.payload["use_case"]["classification"], fields),
    )


def _forbidden_state_differences(
    stream: ValueStream | None,
    process: ProcessAnalysis | None,
    options: list[SolutionOption],
    use_case: UseCase | None,
) -> list[ObjectDifference]:
    result: list[ObjectDifference] = []
    if process is not None and ProcessValidation.objects.filter(process_analysis=process).exists():
        result.append(ObjectDifference("process_validation", "forbidden", DiffStatus.CONFLICT))
    if (
        process is not None
        and SolutionSelectionDecision.objects.filter(process_analysis=process).exists()
    ):
        result.append(
            ObjectDifference(
                "solution_selection_decision",
                "forbidden",
                DiffStatus.CONFLICT,
            )
        )
    if any(option.recommendation != SolutionOption.Recommendation.CANDIDATE for option in options):
        result.append(ObjectDifference("solution_preference", "forbidden", DiffStatus.CONFLICT))
    if stream is not None and stream.status != ValueStream.Status.DRAFT:
        result.append(ObjectDifference("value_stream_state", "forbidden", DiffStatus.CONFLICT))
    if use_case is None:
        return result

    forbidden_counts = {
        "decision_assessment": DecisionAssessment.objects.filter(use_case=use_case).count(),
        "approval_decision": ApprovalDecision.objects.filter(use_case=use_case).count(),
        "governance_assessment": GovernanceAssessment.objects.filter(use_case=use_case).count(),
        "delivery_package": DeliveryPackage.objects.filter(use_case=use_case).count(),
    }
    result.extend(
        ObjectDifference(object_type, "forbidden", DiffStatus.CONFLICT)
        for object_type, count in sorted(forbidden_counts.items())
        if count
    )
    lifecycle = {
        "pilot_start": use_case.pilot_start,
        "actual_end_date": use_case.actual_end_date,
        "metric_actual": use_case.metric_actual,
        "metric_measured_at": use_case.metric_measured_at,
        "realized_result": use_case.realized_result,
        "ending_reason": use_case.ending_reason,
        "is_archived": use_case.is_archived,
    }
    differences = tuple(
        FieldDifference(field, _display(value), None)
        for field, value in sorted(lifecycle.items())
        if value not in (None, "", False)
    )
    if differences:
        result.append(
            ObjectDifference(
                "use_case_lifecycle",
                "forbidden",
                DiffStatus.CONFLICT,
                differences,
            )
        )
    return result


def _append_stage_diffs(
    objects: list[ObjectDifference],
    stream: ValueStream | None,
    stream_data: dict[str, Any],
) -> dict[str, ValueStreamStage | None]:
    current = {stage.sequence: stage for stage in stream.stages.all()} if stream is not None else {}
    by_key: dict[str, ValueStreamStage | None] = {}
    for data in sorted(stream_data["stages"], key=lambda item: item["sequence"]):
        stage = current.get(data["sequence"])
        by_key[data["key"]] = stage
        objects.append(
            _object_diff(
                "value_stream_stage",
                data["key"],
                stage,
                _model_values(stage, STAGE_FIELDS) if stage is not None else None,
                _payload_values(data, STAGE_FIELDS),
            )
        )
    if stream is not None and len(current) != len(stream_data["stages"]):
        objects.append(ObjectDifference("value_stream_stages", "cardinality", DiffStatus.CONFLICT))
    return by_key


def _append_option_diffs(
    objects: list[ObjectDifference],
    process: ProcessAnalysis | None,
    option_payloads: list[dict[str, Any]],
    origin_key: str,
) -> tuple[list[SolutionOption], SolutionOption | None]:
    current = list(process.solution_options.all()) if process is not None else []
    by_name = {option.name: option for option in current}
    selected = None
    for data in sorted(option_payloads, key=lambda item: item["key"]):
        option = by_name.get(data["name"])
        if data["key"] == origin_key:
            selected = option
        objects.append(
            _object_diff(
                "solution_option",
                data["key"],
                option,
                _model_values(option, OPTION_FIELDS) if option is not None else None,
                _payload_values(data, OPTION_FIELDS),
            )
        )
    if process is not None and len(current) != len(option_payloads):
        objects.append(ObjectDifference("solution_options", "cardinality", DiffStatus.CONFLICT))
    return current, selected


def build_blueprint_diff(resolved: ResolvedBlueprint) -> BlueprintGraphDiff:
    payload = resolved.payload
    stream_data = payload["value_stream"]
    use_case_data = payload["use_case"]
    stream = ValueStream.objects.filter(demo_key=stream_data["key"]).first()
    use_case = UseCase.objects.filter(demo_key=use_case_data["key"]).first()
    objects: list[ObjectDifference] = []

    stream_collision = ValueStream.objects.filter(name=stream_data["name"]).exclude(
        demo_key=stream_data["key"]
    )
    if stream is None and stream_collision.exists():
        objects.append(ObjectDifference("value_stream", stream_data["key"], DiffStatus.CONFLICT))
    else:
        objects.append(
            _object_diff(
                "value_stream",
                stream_data["key"],
                stream,
                _current_stream(stream) if stream is not None else None,
                _expected_stream(resolved),
            )
        )
    objects.append(_focus_diff(stream, resolved))
    stages = _append_stage_diffs(objects, stream, stream_data)

    process_data = payload["process_analysis"]
    process_stage = stages.get(process_data["stage_key"])
    process = None
    if process_stage is not None:
        process = ProcessAnalysis.objects.filter(
            stage=process_stage,
            name=process_data["name"],
        ).first()
    objects.append(
        _object_diff(
            "process_analysis",
            process_data["key"],
            process,
            _model_values(process, PROCESS_FIELDS) if process is not None else None,
            _payload_values(process_data, PROCESS_FIELDS),
        )
    )
    current_options, selected_option = _append_option_diffs(
        objects,
        process,
        payload["solution_options"],
        payload["origin"]["solution_option_key"],
    )

    use_case_collision = UseCase.objects.filter(title=use_case_data["title"]).exclude(
        demo_key=use_case_data["key"]
    )
    if use_case is None and use_case_collision.exists():
        objects.append(ObjectDifference("use_case", use_case_data["key"], DiffStatus.CONFLICT))
    else:
        objects.append(
            _object_diff(
                "use_case",
                use_case_data["key"],
                use_case,
                _current_use_case(use_case) if use_case is not None else None,
                _expected_use_case(resolved),
            )
        )
    objects.append(_classification_diff(use_case, resolved))

    origin = (
        UseCaseOrigin.objects.filter(use_case=use_case).first() if use_case is not None else None
    )
    expected_origin = {
        "stage": process_stage.pk if process_stage is not None else None,
        "process_analysis": process.pk if process is not None else None,
        "solution_option": selected_option.pk if selected_option is not None else None,
    }
    current_origin = None
    if origin is not None:
        current_origin = {
            "stage": origin.stage_id,
            "process_analysis": origin.process_analysis_id,
            "solution_option": origin.solution_option_id,
        }
    objects.append(
        _object_diff(
            "use_case_origin",
            "origin",
            origin,
            current_origin,
            expected_origin,
        )
    )
    objects.extend(_forbidden_state_differences(stream, process, current_options, use_case))

    statuses = {item.status for item in objects}
    if DiffStatus.CREATE in statuses and DiffStatus.NO_CHANGE in statuses:
        objects.append(ObjectDifference("scenario_graph", "partial", DiffStatus.CONFLICT))
    return BlueprintGraphDiff(
        scenario_key=payload["scenario_key"],
        schema_version=payload["schema_version"],
        checksum=resolved.checksum,
        objects=tuple(objects),
    )
