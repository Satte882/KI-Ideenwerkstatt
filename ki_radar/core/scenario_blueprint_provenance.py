from __future__ import annotations

from typing import Any

from ki_radar.architecture.provenance import (
    build_process_source_snapshot,
    build_use_case_source_snapshot,
)

from .scenario_blueprint_validation import ResolvedBlueprint

BLUEPRINT_METADATA_KEY = "_blueprint"


def blueprint_metadata(
    resolved: ResolvedBlueprint,
    *,
    object_type: str,
    object_key: str,
) -> dict[str, str]:
    return {
        "source": "scenario_blueprint",
        "scenario_key": resolved.payload["scenario_key"],
        "schema_version": resolved.payload["schema_version"],
        "checksum": resolved.checksum,
        "object_type": object_type,
        "object_key": object_key,
    }


def process_source_snapshot(
    resolved: ResolvedBlueprint,
    *,
    stage,
) -> dict[str, Any]:
    snapshot = build_process_source_snapshot(stage)
    snapshot[BLUEPRINT_METADATA_KEY] = blueprint_metadata(
        resolved,
        object_type="process_analysis",
        object_key=resolved.payload["process_analysis"]["key"],
    )
    return snapshot


def origin_source_snapshot(
    resolved: ResolvedBlueprint,
    *,
    stage,
    process_analysis,
    solution_option,
) -> dict[str, Any]:
    snapshot = build_use_case_source_snapshot(
        stage=stage,
        process_analysis=process_analysis,
        solution_option=solution_option,
    )
    snapshot[BLUEPRINT_METADATA_KEY] = blueprint_metadata(
        resolved,
        object_type="use_case_origin",
        object_key="origin",
    )
    return snapshot
