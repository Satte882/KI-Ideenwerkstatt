from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import ProcessAnalysis
from .process_findings import humanize_process_text


def _payload_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_supported_hypothesis(payload: Mapping[str, Any]) -> str:
    for item in payload.get("hypotheses", []):
        if not isinstance(item, Mapping):
            continue
        if str(item.get("status") or "") != "supported":
            continue
        statement = humanize_process_text(item.get("statement"))
        if statement:
            return statement
    return ""


def _first_calculation(payload: Mapping[str, Any]) -> str:
    for item in payload.get("calculations", []):
        if not isinstance(item, Mapping):
            continue
        summary = humanize_process_text(item.get("summary"))
        if summary:
            return summary
    return ""


def build_process_decision_surface(
    *,
    process_analysis: ProcessAnalysis,
    latest_materialization,
    journey,
) -> dict[str, Any] | None:
    if latest_materialization is None:
        return None

    payload = _payload_mapping(latest_materialization.brief_revision.payload)
    recommendation = _payload_mapping(payload.get("recommendation"))

    situation = humanize_process_text(process_analysis.diagnostic_observations)
    if not situation:
        problem = _payload_mapping(payload.get("problem"))
        situation = humanize_process_text(problem.get("statement"))
    if not situation:
        situation = humanize_process_text(process_analysis.bottlenecks)

    finding = humanize_process_text(process_analysis.confirmed_causes)
    if not finding:
        finding = _first_supported_hypothesis(payload)
    if not finding:
        finding = _first_calculation(payload)
    if not finding:
        finding = humanize_process_text(process_analysis.baseline_metrics)

    recommendation_summary = humanize_process_text(recommendation.get("summary"))
    if not recommendation_summary:
        recommendation_summary = (
            "Noch keine evidenzbasierte Empfehlung aus einem übernommenen Decision Brief."
        )
    recommendation_rationale = humanize_process_text(recommendation.get("rationale"))

    next_action = getattr(journey, "next_action", None)
    if next_action is not None:
        next_label = getattr(next_action, "label", "")
        next_reason = getattr(next_action, "reason", "")
    else:
        next_label = "Aktueller Discovery-Stand abgeschlossen"
        next_reason = getattr(journey, "completion_message", "")
        if not next_reason:
            next_reason = (
                "Für diesen Prozess ist derzeit kein weiterer verpflichtender "
                "Discovery-Schritt offen."
            )

    if not situation:
        situation = "Noch kein kompakter Situationskontext dokumentiert."
    if not finding:
        finding = "Noch kein belastbarer Kernbefund dokumentiert."

    next_step = {
        "label": next_label,
        "reason": next_reason,
    }

    return {
        "situation": situation,
        "finding": finding,
        "recommendation": recommendation_summary,
        "recommendation_rationale": recommendation_rationale,
        "next_step": next_step,
        "run_id": str(latest_materialization.run_id),
        "materialization_id": str(latest_materialization.pk),
    }
