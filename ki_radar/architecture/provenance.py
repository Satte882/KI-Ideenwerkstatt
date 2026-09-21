from __future__ import annotations

from datetime import datetime
from typing import Any


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _source(*, kind: str, label: str, obj, field: str, value: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "label": label,
        "id": str(obj.pk),
        "field": field,
        "value": "" if value is None else str(value),
        "updated_at": _iso(getattr(obj, "updated_at", None)),
    }


def build_process_source_snapshot(stage) -> dict[str, dict[str, Any]]:
    value_stream = stage.value_stream
    values = {
        "name": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="name",
            value=stage.name,
        ),
        "trigger": _source(
            kind="value_stream",
            label="Value Stream",
            obj=value_stream,
            field="trigger",
            value=value_stream.trigger,
        ),
        "outcome": _source(
            kind="value_stream_stage" if stage.description else "value_stream",
            label="Value-Stream-Phase" if stage.description else "Value Stream",
            obj=stage if stage.description else value_stream,
            field="description" if stage.description else "outcome",
            value=stage.description or value_stream.outcome,
        ),
        "roles": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="actors",
            value=stage.actors,
        ),
        "systems": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="systems",
            value=stage.systems,
        ),
        "data_objects": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="documents",
            value=stage.documents,
        ),
        "bottlenecks": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="pain_points",
            value=stage.pain_points,
        ),
        "baseline_metrics": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="baseline_metrics",
            value=stage.baseline_metrics,
        ),
    }
    return values


def build_use_case_source_snapshot(*, stage, process_analysis=None, solution_option=None) -> dict:
    if process_analysis is None:
        return {
            "title": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="name",
                value=stage.name,
            ),
            "affected_process": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="name",
                value=stage.name,
            ),
            "summary": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="description",
                value=stage.description,
            ),
            "target_users": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="actors",
                value=stage.actors,
            ),
            "source_systems": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="systems",
                value=stage.systems,
            ),
            "problem_statement": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="pain_points",
                value=stage.pain_points,
            ),
        }

    snapshot = {
        "affected_process": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process_analysis,
            field="name",
            value=process_analysis.name,
        ),
        "summary": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process_analysis,
            field="current_flow",
            value=process_analysis.current_flow,
        ),
        "problem_statement": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process_analysis,
            field="bottlenecks",
            value=process_analysis.bottlenecks,
        ),
        "target_users": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process_analysis,
            field="roles",
            value=process_analysis.roles,
        ),
        "source_systems": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process_analysis,
            field="systems",
            value=process_analysis.systems,
        ),
        "intended_users": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process_analysis,
            field="roles",
            value=process_analysis.roles,
        ),
    }
    if solution_option is not None:
        snapshot.update(
            {
                "title": _source(
                    kind="solution_option",
                    label="Lösungsoption",
                    obj=solution_option,
                    field="name",
                    value=solution_option.name,
                ),
                "intended_purpose": _source(
                    kind="solution_option",
                    label="Lösungsoption",
                    obj=solution_option,
                    field="description",
                    value=solution_option.description,
                ),
                "expected_benefit": _source(
                    kind="solution_option",
                    label="Lösungsoption",
                    obj=solution_option,
                    field="expected_value",
                    value=solution_option.expected_value,
                ),
                "data_sources": _source(
                    kind=(
                        "solution_option"
                        if solution_option.data_requirements
                        else "process_analysis"
                    ),
                    label=(
                        "Lösungsoption" if solution_option.data_requirements else "Prozessanalyse"
                    ),
                    obj=(
                        solution_option if solution_option.data_requirements else process_analysis
                    ),
                    field=(
                        "data_requirements" if solution_option.data_requirements else "data_objects"
                    ),
                    value=solution_option.data_requirements or process_analysis.data_objects,
                ),
            }
        )
    return snapshot


def source_differences(
    snapshot: dict,
    *,
    stage,
    process_analysis=None,
    solution_option=None,
) -> list[dict]:
    objects = {
        "value_stream": stage.value_stream,
        "value_stream_stage": stage,
        "process_analysis": process_analysis,
        "solution_option": solution_option,
    }
    differences = []
    for target_field, source in (snapshot or {}).items():
        obj = objects.get(source.get("kind"))
        field = source.get("field")
        if obj is None or not field:
            continue
        current = "" if getattr(obj, field, None) is None else str(getattr(obj, field))
        previous = str(source.get("value") or "")
        if current != previous:
            differences.append(
                {
                    "target_field": target_field,
                    "source_label": source.get("label", "Quelle"),
                    "source_field": field,
                    "previous": previous,
                    "current": current,
                }
            )
    return differences
