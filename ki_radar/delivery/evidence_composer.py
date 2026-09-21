from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .evidence_mapping_contract import V1_DELIVERY_FIELD_MAPPINGS, TransformKind, mapping_spec
from .evidence_snapshot import DeliveryEvidenceSnapshot, EvidenceFact, normalize_evidence_value

COMPOSED_FIELD_LABELS = {
    "measurement_plan": {
        "metric_name": "Metrik",
        "metric_type": "Metriktyp",
        "metric_direction": "Richtung",
        "metric_unit": "Einheit",
        "metric_baseline": "Baseline",
        "metric_target": "Ziel",
        "metric_measurement_method": "Messmethode",
        "metric_measurement_period": "Messzeitraum",
    },
    "acceptance_criteria": {
        "success_criterion": "Erfolgskriterium",
        "metric_name": "Metrik",
        "metric_direction": "Richtung",
        "metric_unit": "Einheit",
        "metric_baseline": "Baseline",
        "metric_target": "Ziel",
    },
    "handover_notes": {
        "decision_status": "Freigabestatus",
        "rationale": "Begründung",
        "conditions": "Auflagen",
        "condition_owner_id": "Auflagenverantwortung-ID",
        "condition_due_date": "Auflagenfrist",
        "finalized_at": "Finalisiert am",
    },
    "system_landscape": {
        "source_systems": "Quellsysteme",
        "application_impact": "Anwendungsauswirkung",
    },
    "data_flows": {
        "data_sources": "Datenquellen",
        "interface_description": "Schnittstelle",
        "integration_impact": "Integrationsauswirkung",
    },
}


@dataclass(frozen=True, slots=True)
class ComposedMappingSource:
    source_kind: str
    source_id: str
    source_field: str
    value: Any
    source_version: str
    semantic_version: str
    priority: int


@dataclass(frozen=True, slots=True)
class ComposedFieldMapping:
    target_field: str
    section_key: str
    value: str
    evidence_hash: str
    is_gap: bool
    sources: tuple[ComposedMappingSource, ...]


def compose_delivery_fields(
    snapshot: DeliveryEvidenceSnapshot,
) -> tuple[ComposedFieldMapping, ...]:
    """Compose all structured V1 fields without writing Delivery state or calling a provider."""

    mappings = []
    for target_field in composed_target_fields():
        mappings.append(compose_field(snapshot, target_field))
    return tuple(mappings)


def compose_field(
    snapshot: DeliveryEvidenceSnapshot,
    target_field: str,
) -> ComposedFieldMapping:
    spec = mapping_spec(target_field)
    if spec.transform is not TransformKind.COMPOSE_STRUCTURED:
        message = f"Delivery-Feld ist kein Kompositionsfeld: {target_field}"
        raise ValueError(message)

    field_evidence = snapshot.field(target_field)
    fact_index = _fact_index(field_evidence.facts)
    render_facts = _usable_facts(spec.sources, fact_index)
    source_facts = _source_facts(spec.sources, fact_index)
    return ComposedFieldMapping(
        target_field=target_field,
        section_key=spec.section_key,
        value=_render_composed_value(target_field, render_facts),
        evidence_hash=field_evidence.evidence_hash,
        is_gap=not bool(render_facts),
        sources=tuple(_source_metadata(fact) for fact in source_facts),
    )


def composed_target_fields() -> tuple[str, ...]:
    target_fields = []
    for target_field, spec in V1_DELIVERY_FIELD_MAPPINGS.items():
        if spec.transform is TransformKind.COMPOSE_STRUCTURED:
            target_fields.append(target_field)
    return tuple(target_fields)


def _fact_index(facts: tuple[EvidenceFact, ...]) -> dict[tuple[str, int, str], EvidenceFact]:
    index = {}
    for fact in facts:
        key = (fact.source_kind, fact.priority, fact.source_field)
        if key in index:
            message = f"Doppelte Evidence für Kompositionsschlüssel: {key}"
            raise ValueError(message)
        index[key] = fact
    return index


def _usable_facts(source_rules, fact_index) -> tuple[EvidenceFact, ...]:
    facts = []
    for rule in source_rules:
        rule_facts = _facts_for_rule(rule, fact_index)
        required = []
        for field_name in rule.required_fields:
            key = (rule.kind, rule.priority, field_name)
            required.append(fact_index.get(key))
        if any(fact is None or _fact_is_empty(fact) for fact in required):
            continue
        non_empty = [fact for fact in rule_facts if not _fact_is_empty(fact)]
        if non_empty:
            facts.extend(non_empty)
    return tuple(facts)


def _source_facts(source_rules, fact_index) -> tuple[EvidenceFact, ...]:
    facts = []
    for rule in source_rules:
        for fact in _facts_for_rule(rule, fact_index):
            if not _fact_is_empty(fact):
                facts.append(fact)
    return tuple(facts)


def _facts_for_rule(rule, fact_index) -> tuple[EvidenceFact, ...]:
    facts = []
    for field_name in rule.fields:
        fact = fact_index.get((rule.kind, rule.priority, field_name))
        if fact is not None:
            facts.append(fact)
    return tuple(facts)


def _render_composed_value(target_field: str, facts: tuple[EvidenceFact, ...]) -> str:
    labels = COMPOSED_FIELD_LABELS[target_field]
    lines = []
    for fact in facts:
        try:
            label = labels[fact.source_field]
        except KeyError as exc:
            message = f"Kein Kompositionslabel für {target_field}.{fact.source_field}"
            raise ValueError(message) from exc
        lines.append(f"{label}: {_render_value(fact.value)}")
    return "\n".join(lines)


def _render_value(value: Any) -> str:
    normalized = normalize_evidence_value(value)
    if isinstance(normalized, dict | list):
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "" if normalized is None else str(normalized)


def _fact_is_empty(fact: EvidenceFact) -> bool:
    normalized = normalize_evidence_value(fact.value)
    return normalized is None or normalized == "" or normalized == [] or normalized == {}


def _source_metadata(fact: EvidenceFact) -> ComposedMappingSource:
    return ComposedMappingSource(
        source_kind=fact.source_kind,
        source_id=fact.source_id,
        source_field=fact.source_field,
        value=normalize_evidence_value(fact.value),
        source_version=fact.source_version,
        semantic_version=fact.semantic_version,
        priority=fact.priority,
    )
