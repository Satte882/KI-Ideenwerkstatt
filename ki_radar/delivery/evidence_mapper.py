from __future__ import annotations

from dataclasses import dataclass

from .evidence_mapping_contract import V1_DELIVERY_FIELD_MAPPINGS, TransformKind, mapping_spec
from .evidence_snapshot import DeliveryEvidenceSnapshot, EvidenceFact, normalize_evidence_value

DIRECT_MAPPING_TRANSFORMS = frozenset(
    {
        TransformKind.DIRECT,
        TransformKind.PRIORITY_FIRST_NON_EMPTY,
    }
)


@dataclass(frozen=True, slots=True)
class DirectMappingSource:
    source_kind: str
    source_id: str
    source_field: str
    source_version: str
    semantic_version: str
    priority: int


@dataclass(frozen=True, slots=True)
class DirectFieldMapping:
    target_field: str
    section_key: str
    value: str
    evidence_hash: str
    is_gap: bool
    sources: tuple[DirectMappingSource, ...]


def map_direct_delivery_fields(
    snapshot: DeliveryEvidenceSnapshot,
) -> tuple[DirectFieldMapping, ...]:
    """Map all non-composed V1 fields without writing Delivery state."""

    mappings = []
    for target_field in direct_target_fields():
        mappings.append(direct_mapping_for(snapshot, target_field))
    return tuple(mappings)


def direct_mapping_for(
    snapshot: DeliveryEvidenceSnapshot,
    target_field: str,
) -> DirectFieldMapping:
    spec = mapping_spec(target_field)
    if spec.transform not in DIRECT_MAPPING_TRANSFORMS:
        message = f"Delivery-Feld benötigt deterministische Komposition: {target_field}"
        raise ValueError(message)

    field_evidence = snapshot.field(target_field)
    facts = tuple(fact for fact in field_evidence.facts if not _fact_is_empty(fact))
    if len(facts) > 1:
        message = f"Direktes Mapping erwartet höchstens eine aktive Evidence-Quelle: {target_field}"
        raise ValueError(message)

    value = _render_direct_fact(facts[0]) if facts else ""
    sources = tuple(_source_metadata(fact) for fact in facts)
    return DirectFieldMapping(
        target_field=target_field,
        section_key=spec.section_key,
        value=value,
        evidence_hash=field_evidence.evidence_hash,
        is_gap=not bool(facts),
        sources=sources,
    )


def direct_target_fields() -> tuple[str, ...]:
    target_fields = []
    for target_field, spec in V1_DELIVERY_FIELD_MAPPINGS.items():
        if spec.transform in DIRECT_MAPPING_TRANSFORMS:
            target_fields.append(target_field)
    return tuple(target_fields)


def _render_direct_fact(fact: EvidenceFact) -> str:
    normalized = normalize_evidence_value(fact.value)
    if normalized is None:
        return ""
    if isinstance(normalized, dict | list):
        message = (
            f"Direktes Text-Mapping akzeptiert keine strukturierte Evidence: {fact.source_field}"
        )
        raise ValueError(message)
    return str(normalized)


def _fact_is_empty(fact: EvidenceFact) -> bool:
    normalized = normalize_evidence_value(fact.value)
    return normalized is None or normalized == "" or normalized == [] or normalized == {}


def _source_metadata(fact: EvidenceFact) -> DirectMappingSource:
    return DirectMappingSource(
        source_kind=fact.source_kind,
        source_id=fact.source_id,
        source_field=fact.source_field,
        source_version=fact.source_version,
        semantic_version=fact.semantic_version,
        priority=fact.priority,
    )
