from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from .evidence_mapping_contract import (
    LEGACY_PLACEHOLDER_FRAGMENTS,
    MAPPING_CONTRACT_VERSION,
)

BLOCK8_MAPPING_MANIFEST_KEY = "block8_mapping"


class MappingStatus(StrEnum):
    MAPPED = "mapped"
    GAP = "gap"
    CONFLICT = "conflict"
    STALE = "stale"


class RefreshAction(StrEnum):
    WRITE = "write"
    NOOP = "noop"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class MappingConflict:
    previous_mapped_value: str
    current_value: str
    candidate_value: str
    previous_evidence_hash: str
    candidate_evidence_hash: str


@dataclass(frozen=True, slots=True)
class FieldRefreshDecision:
    target_field: str
    section_key: str
    status: MappingStatus
    action: RefreshAction
    value: str
    evidence_hash: str
    mapped_value: str
    sources: tuple[dict[str, Any], ...]
    conflict: MappingConflict | None = None


@dataclass(frozen=True, slots=True)
class MappingRefreshPlan:
    values: dict[str, str]
    source_manifest: dict[str, Any]
    decisions: tuple[FieldRefreshDecision, ...]

    @property
    def changed_fields(self) -> tuple[str, ...]:
        changed_fields = []
        for decision in self.decisions:
            if decision.action is RefreshAction.WRITE:
                changed_fields.append(decision.target_field)
        return tuple(changed_fields)

    @property
    def conflict_fields(self) -> tuple[str, ...]:
        conflict_fields = []
        for decision in self.decisions:
            if decision.status is MappingStatus.CONFLICT:
                conflict_fields.append(decision.target_field)
        return tuple(conflict_fields)


def plan_mapping_refresh(
    *,
    current_values: dict[str, str],
    candidates,
    source_manifest: dict[str, Any] | None = None,
    stale_fields: set[str] | frozenset[str] = frozenset(),
) -> MappingRefreshPlan:
    """Plan a conflict-safe refresh without mutating Delivery state."""

    source_manifest = dict(source_manifest or {})
    previous_mapping = dict(source_manifest.get(BLOCK8_MAPPING_MANIFEST_KEY) or {})
    previous_fields = dict(previous_mapping.get("fields") or {})
    values = dict(current_values)
    decisions = []

    for candidate in candidates:
        target_field = candidate.target_field
        decision = plan_field_refresh(
            current_value=values.get(target_field, ""),
            candidate=candidate,
            previous_entry=previous_fields.get(target_field),
            source_stale=target_field in stale_fields,
        )
        decisions.append(decision)
        if decision.action is RefreshAction.WRITE:
            values[target_field] = decision.value

    field_entries = {}
    for decision in decisions:
        field_entries[decision.target_field] = _manifest_entry(decision)
    mapping_manifest = {
        "contract_version": MAPPING_CONTRACT_VERSION,
        "fields": field_entries,
    }
    source_manifest[BLOCK8_MAPPING_MANIFEST_KEY] = mapping_manifest
    return MappingRefreshPlan(
        values=values,
        source_manifest=source_manifest,
        decisions=tuple(decisions),
    )


def plan_field_refresh(
    *,
    current_value: str,
    candidate,
    previous_entry: dict[str, Any] | None,
    source_stale: bool = False,
) -> FieldRefreshDecision:
    current = "" if current_value is None else str(current_value)
    previous = dict(previous_entry or {})
    previous_hash = str(previous.get("evidence_hash") or "")
    previous_mapped_value = str(previous.get("mapped_value") or "")
    candidate_value = "" if candidate.value is None else str(candidate.value)
    sources = tuple(asdict(source) for source in candidate.sources)

    if source_stale:
        return _decision(
            candidate=candidate,
            status=MappingStatus.STALE,
            action=RefreshAction.NOOP,
            value=current,
            mapped_value=previous_mapped_value,
            sources=sources,
        )

    if not previous:
        return _plan_legacy_or_new(
            current=current,
            candidate=candidate,
            candidate_value=candidate_value,
            sources=sources,
        )

    previous_status = str(previous.get("status") or "")
    if previous_status == MappingStatus.GAP:
        return _plan_from_gap(
            current=current,
            candidate=candidate,
            candidate_value=candidate_value,
            previous_hash=previous_hash,
            sources=sources,
        )

    same_evidence = previous_hash == candidate.evidence_hash
    current_matches_last = _same_text(current, previous_mapped_value)

    if candidate.is_gap:
        if same_evidence:
            return _decision(
                candidate=candidate,
                status=MappingStatus.GAP,
                action=RefreshAction.NOOP,
                value=current,
                mapped_value=previous_mapped_value,
                sources=sources,
            )
        if current_matches_last:
            return _decision(
                candidate=candidate,
                status=MappingStatus.STALE,
                action=RefreshAction.NOOP,
                value=current,
                mapped_value=previous_mapped_value,
                sources=sources,
            )
        return _conflict_decision(
            current=current,
            candidate=candidate,
            candidate_value=candidate_value,
            previous_hash=previous_hash,
            previous_mapped_value=previous_mapped_value,
            sources=sources,
        )

    if same_evidence:
        return _decision(
            candidate=candidate,
            status=MappingStatus.MAPPED,
            action=RefreshAction.NOOP,
            value=current,
            mapped_value=previous_mapped_value or candidate_value,
            sources=sources,
        )

    if current_matches_last or not _has_content(current):
        return _decision(
            candidate=candidate,
            status=MappingStatus.MAPPED,
            action=RefreshAction.WRITE,
            value=candidate_value,
            mapped_value=candidate_value,
            sources=sources,
        )

    if _same_text(current, candidate_value):
        return _decision(
            candidate=candidate,
            status=MappingStatus.MAPPED,
            action=RefreshAction.NOOP,
            value=current,
            mapped_value=candidate_value,
            sources=sources,
        )

    return _conflict_decision(
        current=current,
        candidate=candidate,
        candidate_value=candidate_value,
        previous_hash=previous_hash,
        previous_mapped_value=previous_mapped_value,
        sources=sources,
    )


def is_legacy_placeholder(value: str | None) -> bool:
    normalized = _normalize_text(value)
    if not normalized:
        return False
    return any(_normalize_text(fragment) in normalized for fragment in LEGACY_PLACEHOLDER_FRAGMENTS)


def _plan_legacy_or_new(*, current, candidate, candidate_value, sources):
    if candidate.is_gap:
        return _decision(
            candidate=candidate,
            status=MappingStatus.GAP,
            action=RefreshAction.NOOP,
            value=current,
            mapped_value="",
            sources=sources,
        )
    if not _has_content(current) or is_legacy_placeholder(current):
        return _decision(
            candidate=candidate,
            status=MappingStatus.MAPPED,
            action=RefreshAction.WRITE,
            value=candidate_value,
            mapped_value=candidate_value,
            sources=sources,
        )
    if _same_text(current, candidate_value):
        return _decision(
            candidate=candidate,
            status=MappingStatus.MAPPED,
            action=RefreshAction.NOOP,
            value=current,
            mapped_value=candidate_value,
            sources=sources,
        )
    return _conflict_decision(
        current=current,
        candidate=candidate,
        candidate_value=candidate_value,
        previous_hash="",
        previous_mapped_value="",
        sources=sources,
    )


def _plan_from_gap(*, current, candidate, candidate_value, previous_hash, sources):
    if candidate.is_gap:
        return _decision(
            candidate=candidate,
            status=MappingStatus.GAP,
            action=RefreshAction.NOOP,
            value=current,
            mapped_value="",
            sources=sources,
        )
    if not _has_content(current) or is_legacy_placeholder(current):
        return _decision(
            candidate=candidate,
            status=MappingStatus.MAPPED,
            action=RefreshAction.WRITE,
            value=candidate_value,
            mapped_value=candidate_value,
            sources=sources,
        )
    if _same_text(current, candidate_value):
        return _decision(
            candidate=candidate,
            status=MappingStatus.MAPPED,
            action=RefreshAction.NOOP,
            value=current,
            mapped_value=candidate_value,
            sources=sources,
        )
    return _conflict_decision(
        current=current,
        candidate=candidate,
        candidate_value=candidate_value,
        previous_hash=previous_hash,
        previous_mapped_value="",
        sources=sources,
    )


def _conflict_decision(
    *,
    current,
    candidate,
    candidate_value,
    previous_hash,
    previous_mapped_value,
    sources,
):
    conflict = MappingConflict(
        previous_mapped_value=previous_mapped_value,
        current_value=current,
        candidate_value=candidate_value,
        previous_evidence_hash=previous_hash,
        candidate_evidence_hash=candidate.evidence_hash,
    )
    return _decision(
        candidate=candidate,
        status=MappingStatus.CONFLICT,
        action=RefreshAction.CONFLICT,
        value=current,
        mapped_value=previous_mapped_value,
        sources=sources,
        conflict=conflict,
    )


def _decision(
    *,
    candidate,
    status,
    action,
    value,
    mapped_value,
    sources,
    conflict=None,
):
    return FieldRefreshDecision(
        target_field=candidate.target_field,
        section_key=candidate.section_key,
        status=status,
        action=action,
        value=value,
        evidence_hash=candidate.evidence_hash,
        mapped_value=mapped_value,
        sources=sources,
        conflict=conflict,
    )


def _manifest_entry(decision: FieldRefreshDecision) -> dict[str, Any]:
    entry = {
        "status": decision.status.value,
        "section_key": decision.section_key,
        "evidence_hash": decision.evidence_hash,
        "mapped_value": decision.mapped_value,
        "sources": list(decision.sources),
    }
    if decision.conflict is not None:
        entry["conflict"] = asdict(decision.conflict)
    return entry


def _has_content(value: str | None) -> bool:
    return bool(_normalize_text(value))


def _same_text(left: str | None, right: str | None) -> bool:
    return _normalize_text(left) == _normalize_text(right)


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    normalized = str(value).replace("\r\n", "\n")
    normalized = normalized.replace("\r", "\n")
    return " ".join(normalized.split()).casefold()
