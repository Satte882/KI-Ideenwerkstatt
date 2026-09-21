from __future__ import annotations

from dataclasses import asdict

from .evidence_mapping_contract import LLMRestTask, mapping_spec
from .mapping_integration import (
    ARCHITECTURE_MAPPING_FIELDS,
    block8_mapping_source_differences,
    build_existing_package_refresh_plan,
    delivery_mapping_is_legacy,
)
from .mapping_refresh import MappingStatus
from .permissions import can_edit_package

ARCHITECTURE_FIELD_LABELS = {
    "system_landscape": "Ist-/Ziel-Systemlandschaft",
    "data_flows": "Daten- und Informationsflüsse",
}
SOURCE_KIND_LABELS = {
    "use_case": "Use Case",
    "value_stream": "Value Stream",
    "solution_selection_snapshot": "Ausgewählte Lösungsoption",
    "approval_decision": "Finale Freigabe",
}
STATUS_LABELS = {
    MappingStatus.MAPPED: "Gemappt",
    MappingStatus.GAP: "Lücke",
    MappingStatus.CONFLICT: "Konflikt",
    MappingStatus.STALE: "Quelle geändert",
}


def build_delivery_mapping_status(package, user=None) -> dict:
    """Build a read-only UI model from the existing Block-8 mapping state."""

    if delivery_mapping_is_legacy(package):
        return {
            "is_legacy": True,
            "mapped_count": 0,
            "gap_count": 0,
            "conflict_count": 0,
            "stale_source_count": 0,
            "fields": [],
        }

    plan = build_existing_package_refresh_plan(package)
    source_differences = {
        item["package_field"]: item for item in block8_mapping_source_differences(package)
    }
    editable = bool(user is not None and can_edit_package(user, package))
    rows = []
    for decision in plan.decisions:
        source_changed = bool(source_differences.get(decision.target_field, {}).get("changed"))
        status = decision.status
        display_status = status
        if source_changed and status is MappingStatus.MAPPED:
            display_status = MappingStatus.STALE
        current_value = _current_delivery_value(package, decision.target_field)
        conflict = asdict(decision.conflict) if decision.conflict is not None else None
        spec = mapping_spec(decision.target_field)
        rows.append(
            {
                "target_field": decision.target_field,
                "field_label": _field_label(package, decision.target_field),
                "section_key": decision.section_key,
                "status": display_status.value,
                "status_label": STATUS_LABELS[display_status],
                "source_changed": source_changed,
                "current_value": current_value,
                "mapped_value": decision.mapped_value,
                "candidate_value": conflict["candidate_value"] if conflict else decision.value,
                "conflict": conflict,
                "sources": [_present_source(source) for source in decision.sources],
                "can_refine": bool(
                    editable
                    and display_status is MappingStatus.MAPPED
                    and spec.llm_rest_task is LLMRestTask.LANGUAGE_COMPACTION
                ),
            }
        )

    return {
        "is_legacy": False,
        "mapped_count": sum(row["status"] == MappingStatus.MAPPED for row in rows),
        "gap_count": sum(row["status"] == MappingStatus.GAP for row in rows),
        "conflict_count": sum(row["status"] == MappingStatus.CONFLICT for row in rows),
        "stale_source_count": sum(row["source_changed"] for row in rows),
        "fields": rows,
    }


def _current_delivery_value(package, target_field: str) -> str:
    if target_field in ARCHITECTURE_MAPPING_FIELDS:
        return str(getattr(package.architecture_artifacts, target_field) or "")
    return str(getattr(package, target_field) or "")


def _field_label(package, target_field: str) -> str:
    if target_field in ARCHITECTURE_FIELD_LABELS:
        return ARCHITECTURE_FIELD_LABELS[target_field]
    return str(package._meta.get_field(target_field).verbose_name)


def _present_source(source) -> dict[str, str | int]:
    raw = asdict(source) if not isinstance(source, dict) else source
    kind = str(raw.get("source_kind") or "")
    return {
        "kind": kind,
        "label": SOURCE_KIND_LABELS.get(kind, kind or "Quelle"),
        "source_id": str(raw.get("source_id") or ""),
        "source_field": str(raw.get("source_field") or ""),
        "source_version": str(raw.get("source_version") or ""),
        "semantic_version": str(raw.get("semantic_version") or ""),
        "priority": int(raw.get("priority") or 0),
    }
