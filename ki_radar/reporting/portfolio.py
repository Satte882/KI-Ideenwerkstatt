from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlencode

from django.db.models import (
    Case,
    CharField,
    Count,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)

from ki_radar.accounts.models import BusinessUnit
from ki_radar.use_cases.models import DecisionAssessment, UseCase

LEVEL_ORDER = [UseCase.Level.LOW, UseCase.Level.MEDIUM, UseCase.Level.HIGH]
MATRIX_ROW_ORDER = [UseCase.Level.HIGH, UseCase.Level.MEDIUM, UseCase.Level.LOW]
VALID_LEVELS = set(LEVEL_ORDER)
LEVEL_LABELS = dict(UseCase.Level.choices)
STATUS_LABELS = dict(UseCase.Status.choices)
DECISION_STATUS_LABELS = dict(UseCase.DecisionStatus.choices)
SOLUTION_LABELS = dict(UseCase.SolutionType.choices)

GROUP_CONFIG = {
    "business_unit": ("business_unit__name", "Organisationseinheit", None),
    "solution_type": ("solution_type", "Lösungstyp", SOLUTION_LABELS),
    "lifecycle": ("status", "Lifecycle", STATUS_LABELS),
    "decision_status": ("decision_status", "Entscheidungsstatus", DECISION_STATUS_LABELS),
}

CELL_HINTS = {
    (UseCase.Level.HIGH, UseCase.Level.HIGH): "Bevorzugter Bereich",
    (UseCase.Level.HIGH, UseCase.Level.MEDIUM): "Nutzenstark, genauer prüfen",
    (UseCase.Level.HIGH, UseCase.Level.LOW): "Strategisch interessant, schwer umsetzbar",
    (UseCase.Level.MEDIUM, UseCase.Level.HIGH): "Pragmatische Kandidaten",
    (UseCase.Level.MEDIUM, UseCase.Level.MEDIUM): "Vertiefte Prüfung sinnvoll",
    (UseCase.Level.MEDIUM, UseCase.Level.LOW): "Aufwand kritisch prüfen",
    (UseCase.Level.LOW, UseCase.Level.HIGH): "Einfache Optimierung mit begrenztem Nutzen",
    (UseCase.Level.LOW, UseCase.Level.MEDIUM): "Niedrige Priorität",
    (UseCase.Level.LOW, UseCase.Level.LOW): "Eher nicht verfolgen",
}


def annotated_portfolio_queryset() -> QuerySet[UseCase]:
    """Return one-query portfolio data annotated from the newest assessment.

    The assessment already stores low/medium/high categories. Those values map directly to the
    matrix and avoid artificial numeric thresholds. Confidence is reproduced as a database
    expression from the same factors as DecisionAssessment.confidence_level.
    """

    latest = DecisionAssessment.objects.filter(use_case=OuterRef("pk")).order_by("-version")
    queryset = (
        UseCase.objects.filter(is_archived=False)
        .select_related("business_unit", "business_owner")
        .annotate(
            portfolio_assessment_id=Subquery(latest.values("id")[:1]),
            portfolio_business_value=Subquery(latest.values("business_value")[:1]),
            portfolio_technical_feasibility=Subquery(latest.values("technical_feasibility")[:1]),
            portfolio_evidence_quality=Subquery(latest.values("evidence_quality")[:1]),
            portfolio_evidence_recency=Subquery(latest.values("evidence_recency")[:1]),
            portfolio_evidence_coverage=Subquery(latest.values("evidence_coverage")[:1]),
            portfolio_independent_review=Subquery(latest.values("independent_review")[:1]),
            portfolio_assumptions_resolved=Subquery(latest.values("assumptions_resolved")[:1]),
        )
    )
    return queryset.annotate(
        portfolio_confidence=Case(
            When(portfolio_assessment_id__isnull=True, then=Value("")),
            When(
                Q(
                    portfolio_evidence_quality__gte=(
                        DecisionAssessment.EvidenceQuality.REPRESENTATIVE
                    ),
                    portfolio_evidence_recency__gte=DecisionAssessment.ConfidenceFactor.SOLID,
                    portfolio_evidence_coverage__gte=DecisionAssessment.ConfidenceFactor.SOLID,
                    portfolio_independent_review__gte=(DecisionAssessment.ConfidenceFactor.SOLID),
                    portfolio_assumptions_resolved__gte=(DecisionAssessment.ConfidenceFactor.SOLID),
                ),
                then=Value(UseCase.Level.HIGH),
            ),
            When(
                Q(
                    portfolio_evidence_quality__gte=(
                        DecisionAssessment.EvidenceQuality.EXPERT_OPINION
                    ),
                    portfolio_evidence_recency__gte=DecisionAssessment.ConfidenceFactor.LIMITED,
                    portfolio_evidence_coverage__gte=DecisionAssessment.ConfidenceFactor.LIMITED,
                    portfolio_independent_review__gte=(DecisionAssessment.ConfidenceFactor.LIMITED),
                    portfolio_assumptions_resolved__gte=(
                        DecisionAssessment.ConfidenceFactor.LIMITED
                    ),
                ),
                then=Value(UseCase.Level.MEDIUM),
            ),
            default=Value(UseCase.Level.LOW),
            output_field=CharField(),
        )
    )


def _selected_filters(params: Mapping[str, str]) -> dict[str, str]:
    business_unit = str(params.get("business_unit", "")).strip()
    if not business_unit.isdecimal() or int(business_unit) <= 0:
        business_unit = ""

    return {
        "business_unit": business_unit,
        "lifecycle": str(params.get("lifecycle", "")).strip(),
        "decision_status": str(params.get("decision_status", "")).strip(),
        "solution_type": str(params.get("solution_type", "")).strip(),
        "confidence": str(params.get("confidence", "")).strip(),
    }


def _apply_filters(
    queryset: QuerySet[UseCase],
    selected: dict[str, str],
) -> QuerySet[UseCase]:
    if selected["business_unit"]:
        queryset = queryset.filter(business_unit_id=selected["business_unit"])
    if selected["lifecycle"] in STATUS_LABELS:
        queryset = queryset.filter(status=selected["lifecycle"])
    if selected["decision_status"] in DECISION_STATUS_LABELS:
        queryset = queryset.filter(decision_status=selected["decision_status"])
    if selected["solution_type"] in SOLUTION_LABELS:
        queryset = queryset.filter(solution_type=selected["solution_type"])
    if selected["confidence"] in LEVEL_LABELS:
        queryset = queryset.filter(portfolio_confidence=selected["confidence"])
    return queryset


def _unclassified_reason(item: UseCase) -> str:
    if item.portfolio_assessment_id is None:
        return "Keine strukturierte Bewertung"
    if item.portfolio_business_value not in VALID_LEVELS:
        return "Wirtschaftlicher Nutzen fehlt oder ist ungültig"
    if item.portfolio_technical_feasibility not in VALID_LEVELS:
        return "Technische Machbarkeit fehlt oder ist ungültig"
    return "Bewertung ist nicht vollständig einordenbar"


def _decorate_item(item: UseCase) -> None:
    item.portfolio_business_value_label = LEVEL_LABELS.get(
        item.portfolio_business_value,
        "Nicht bestimmbar",
    )
    item.portfolio_technical_feasibility_label = LEVEL_LABELS.get(
        item.portfolio_technical_feasibility,
        "Nicht bestimmbar",
    )
    item.portfolio_confidence_label = LEVEL_LABELS.get(
        item.portfolio_confidence,
        "Nicht bestimmbar",
    )
    item.portfolio_is_not_pursued = item.decision_status == UseCase.DecisionStatus.NOT_PURSUED


def _matrix_context(
    items: list[UseCase],
) -> tuple[list[dict], list[UseCase], list[dict]]:
    cells = {(business, technical): [] for business in LEVEL_ORDER for technical in LEVEL_ORDER}
    classified: list[UseCase] = []
    unclassified: list[dict] = []

    for item in items:
        _decorate_item(item)
        if (
            item.portfolio_business_value in VALID_LEVELS
            and item.portfolio_technical_feasibility in VALID_LEVELS
        ):
            cells[(item.portfolio_business_value, item.portfolio_technical_feasibility)].append(
                item
            )
            classified.append(item)
        else:
            unclassified.append({"item": item, "reason": _unclassified_reason(item)})

    rows = []
    for business in MATRIX_ROW_ORDER:
        row_cells = []
        for technical in LEVEL_ORDER:
            row_cells.append(
                {
                    "business_value": business,
                    "technical_feasibility": technical,
                    "technical_label": LEVEL_LABELS[technical],
                    "hint": CELL_HINTS[(business, technical)],
                    "items": cells[(business, technical)],
                }
            )
        rows.append(
            {
                "business_value": business,
                "business_label": LEVEL_LABELS[business],
                "cells": row_cells,
            }
        )
    return rows, classified, unclassified


def _landscape_context(queryset: QuerySet[UseCase], group: str) -> list[dict]:
    group_field, _group_label, choice_labels = GROUP_CONFIG[group]
    unclassified_filter = (
        Q(portfolio_assessment_id__isnull=True)
        | Q(portfolio_business_value__isnull=True)
        | Q(portfolio_technical_feasibility__isnull=True)
        | ~Q(portfolio_business_value__in=VALID_LEVELS)
        | ~Q(portfolio_technical_feasibility__in=VALID_LEVELS)
    )
    annotations = {
        "total": Count("id"),
        "unclassified_total": Count("id", filter=unclassified_filter),
        "confidence_high": Count(
            "id",
            filter=Q(portfolio_confidence=UseCase.Level.HIGH),
        ),
        "confidence_medium": Count(
            "id",
            filter=Q(portfolio_confidence=UseCase.Level.MEDIUM),
        ),
        "confidence_low": Count(
            "id",
            filter=Q(portfolio_confidence=UseCase.Level.LOW),
        ),
    }
    for status, _label in UseCase.DecisionStatus.choices:
        annotations[f"status_{status}"] = Count("id", filter=Q(decision_status=status))

    rows = queryset.values(group_field).annotate(**annotations).order_by(group_field)
    groups = []
    for row in rows:
        raw_value = row[group_field]
        label = choice_labels.get(raw_value, raw_value) if choice_labels else raw_value
        label = label or "Nicht zugeordnet"
        groups.append(
            {
                "key": raw_value or "unassigned",
                "label": label,
                "total": row["total"],
                "unclassified_total": row["unclassified_total"],
                "confidence_counts": [
                    {
                        "key": UseCase.Level.HIGH,
                        "label": "Hoch",
                        "count": row["confidence_high"],
                    },
                    {
                        "key": UseCase.Level.MEDIUM,
                        "label": "Mittel",
                        "count": row["confidence_medium"],
                    },
                    {
                        "key": UseCase.Level.LOW,
                        "label": "Niedrig",
                        "count": row["confidence_low"],
                    },
                ],
                "status_counts": [
                    {
                        "key": status,
                        "label": label,
                        "count": row[f"status_{status}"],
                    }
                    for status, label in UseCase.DecisionStatus.choices
                    if row[f"status_{status}"]
                ],
            }
        )
    return groups


def _group_links(params: Mapping[str, str]) -> list[dict]:
    links = []
    for key, (_field, label, _choices) in GROUP_CONFIG.items():
        query = {name: value for name, value in params.items() if value and name != "group"}
        query["group"] = key
        links.append({"key": key, "label": label, "query": urlencode(query)})
    return links


def build_portfolio_context(params: Mapping[str, str]) -> dict:
    selected = _selected_filters(params)
    queryset = _apply_filters(annotated_portfolio_queryset(), selected)
    explicit_not_pursued = selected["decision_status"] == UseCase.DecisionStatus.NOT_PURSUED
    include_not_pursued = str(params.get("include_not_pursued", "")) == "1"
    show_not_pursued = include_not_pursued or explicit_not_pursued
    not_pursued_total = queryset.filter(decision_status=UseCase.DecisionStatus.NOT_PURSUED).count()
    if not show_not_pursued:
        queryset = queryset.exclude(decision_status=UseCase.DecisionStatus.NOT_PURSUED)

    group = str(params.get("group", "business_unit"))
    if group not in GROUP_CONFIG:
        group = "business_unit"

    items = list(queryset.order_by("business_unit__name", "short_id"))
    matrix_rows, classified, unclassified = _matrix_context(items)
    return {
        "matrix_rows": matrix_rows,
        "classified_items": classified,
        "unclassified_items": unclassified,
        "visible_total": len(items),
        "classified_total": len(classified),
        "unclassified_total": len(unclassified),
        "not_pursued_total": not_pursued_total,
        "show_not_pursued": show_not_pursued,
        "selected": selected,
        "business_units": BusinessUnit.objects.filter(is_active=True).order_by("name"),
        "lifecycle_choices": UseCase.Status.choices,
        "decision_status_choices": UseCase.DecisionStatus.choices,
        "solution_type_choices": UseCase.SolutionType.choices,
        "confidence_choices": UseCase.Level.choices,
        "landscape_groups": _landscape_context(queryset, group),
        "landscape_group": group,
        "landscape_group_label": GROUP_CONFIG[group][1],
        "landscape_expanded": bool(params.get("group")),
        "group_links": _group_links(params),
    }
