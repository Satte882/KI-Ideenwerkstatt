from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ProcessAnalysis

SOURCE_LABELS = {
    "diagnostic_observations": "Beobachtung / Problem",
    "bottlenecks": "Bottlenecks und Ursachen",
    "baseline_metrics": "Baseline und Prozesskennzahlen",
}


@dataclass(frozen=True)
class ProcessFinding:
    text: str
    source_field: str
    source_label: str
    source_anchor: str


@dataclass(frozen=True)
class ProcessFindingGroup:
    key: str
    label: str
    items: tuple[ProcessFinding, ...]


def _split_entries(value: str, *, limit: int) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text:
        return ()

    lines = [
        re.sub(r"^\s*(?:(?:[-\u2013\u2014\u2022*]|\d+[.)])\s+)", "", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]
    if len(lines) == 1 and ";" in lines[0]:
        lines = [part.strip() for part in lines[0].split(";") if part.strip()]
    return tuple(lines[:limit])


def _findings_for_field(
    process_analysis: ProcessAnalysis,
    field_name: str,
    *,
    limit: int,
) -> tuple[ProcessFinding, ...]:
    return tuple(
        ProcessFinding(
            text=text,
            source_field=field_name,
            source_label=SOURCE_LABELS[field_name],
            source_anchor=f"analysis-{field_name.replace('_', '-')}",
        )
        for text in _split_entries(getattr(process_analysis, field_name, ""), limit=limit)
    )


def build_process_findings(
    process_analysis: ProcessAnalysis,
) -> tuple[ProcessFindingGroup, ...]:
    problem_field = (
        "diagnostic_observations"
        if process_analysis.diagnostic_observations.strip()
        else "bottlenecks"
    )
    groups = [
        ProcessFindingGroup(
            key="problem",
            label="Problem",
            items=_findings_for_field(
                process_analysis,
                problem_field,
                limit=1,
            ),
        ),
        ProcessFindingGroup(
            key="scale",
            label="Größenordnung",
            items=_findings_for_field(
                process_analysis,
                "baseline_metrics",
                limit=2,
            ),
        ),
    ]
    return tuple(group for group in groups if group.items)
