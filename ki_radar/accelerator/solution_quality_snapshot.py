from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .solution_generation_effective import build_validated_effective_solution_payload
from .solution_generation_sources import SOURCE_SCHEMA_VERSION, SolutionGenerationSourceContext
from .solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
    QUALITY_CONTRACT_VERSION,
    REPAIR_PROMPT_VERSION,
    REPAIR_SCHEMA_VERSION,
)


@dataclass(frozen=True)
class SolutionQualitySnapshot:
    snapshot_hash: str
    document: dict[str, Any]


def build_solution_quality_snapshot(
    *,
    preview_payload: dict[str, Any],
    source_context: SolutionGenerationSourceContext,
) -> SolutionQualitySnapshot:
    """Freeze the deterministically valid preview plus the V1 quality contract.

    The snapshot intentionally binds semantic contract versions but not the
    provider model name. Model identity remains execution provenance; a model
    rollout alone must not make an otherwise unchanged quality contract stale.
    """

    effective_payload = build_validated_effective_solution_payload(
        preview_payload,
        source_context,
    )
    document: dict[str, Any] = {
        "quality_contract_version": QUALITY_CONTRACT_VERSION,
        "process_analysis_id": source_context.process_analysis_id,
        "process_version": source_context.process_version,
        "source_hash": source_context.source_hash,
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "generation_prompt_version": effective_payload["prompt_version"],
        "generation_schema_version": effective_payload["schema_version"],
        "critic_prompt_version": CRITIC_PROMPT_VERSION,
        "critic_schema_version": CRITIC_SCHEMA_VERSION,
        "repair_prompt_version": REPAIR_PROMPT_VERSION,
        "repair_schema_version": REPAIR_SCHEMA_VERSION,
        "effective_payload": effective_payload,
    }
    serialized = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return SolutionQualitySnapshot(
        snapshot_hash=hashlib.sha256(serialized).hexdigest(),
        document=document,
    )
