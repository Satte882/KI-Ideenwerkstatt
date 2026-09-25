from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ProcessAnalysis

SOURCE_LABELS = {
    "diagnostic_observations": "Beobachtung / Problem",
    "bottlenecks": "Bottlenecks und Ursachen",
    "baseline_metrics": "Baseline und Prozesskennzahlen",
}

_FIELD_LABELS = {
    "approval_hours": "Freigabedauer (Stunden)",
    "approver_available": "Freigeber verfügbar",
    "queue_retries": "Queue-Wiederholungen",
    "missing_info": "fehlende Informationen",
    "total_eligible": "Gesamtzahl freigabepflichtiger Vorgänge",
    "escalations": "Eskalationen",
}

_TOOL_LABELS = {
    "compare_groups": "Gruppenvergleich",
    "profile_csv": "Datenprüfung",
    "search_sources": "Quellensuche",
    "read_source": "Quellenprüfung",
}

_HYPOTHESIS_STATUS_LABELS = {
    "supported": "Durch Evidenz gestützt",
    "refuted": "Durch Evidenz nicht gestützt",
    "conflicting": "Widersprüchliche Evidenz",
    "open": "Noch offen",
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


def humanize_process_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    for status, label in _HYPOTHESIS_STATUS_LABELS.items():
        text = re.sub(rf"\[{re.escape(status)}\]\s*", f"{label}: ", text)

    for field_name, label in _FIELD_LABELS.items():
        text = re.sub(rf"\b{re.escape(field_name)}\b", label, text)
    for tool_name, label in _TOOL_LABELS.items():
        text = re.sub(rf"\b{re.escape(tool_name)}\b", label, text)

    text = re.sub(
        r"\s*\|\s*Population:.*?(?=\s*\|\s*Grenzen:|$)",
        "",
        text,
    )
    text = re.sub(
        r"\s*\|\s*Grenzen:.*?(?=\s*\|\s*Nachweis:|$)",
        "",
        text,
    )
    text = re.sub(r"\s*\|\s*Nachweis:.*$", "", text)
    text = re.sub(r"\btool-result:[0-9a-f-]+\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsource-sha256:[0-9a-f]+\b", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", text).strip(" ·|")


def _split_entries(value: str, *, limit: int) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text:
        return ()

    lines = [
        humanize_process_text(
            re.sub(r"^\s*(?:(?:[-\u2013\u2014\u2022*]|\d+[.)])\s+)", "", line).strip()
        )
        for line in text.splitlines()
        if line.strip()
    ]
    lines = [line for line in lines if line]
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
