from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from ki_radar.use_cases.models import UseCase

from .evidence_mapping_contract import (
    MAPPING_CONTRACT_VERSION,
    V1_DELIVERY_FIELD_MAPPINGS,
    DeliveryFieldMappingSpec,
    MultiSourcePolicy,
    SourceRule,
)

_AUTO = object()


@dataclass(frozen=True, slots=True)
class EvidenceSourceSnapshot:
    kind: str
    source_id: str
    version: str
    semantic_version: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class EvidenceFact:
    source_kind: str
    source_id: str
    source_field: str
    value: Any
    source_version: str
    semantic_version: str
    priority: int

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "source_field": self.source_field,
            "value": normalize_evidence_value(self.value),
            "semantic_version": self.semantic_version,
            "priority": self.priority,
        }


@dataclass(frozen=True, slots=True)
class FieldEvidence:
    target_field: str
    facts: tuple[EvidenceFact, ...]
    evidence_hash: str

    @property
    def has_non_empty_evidence(self) -> bool:
        return any(not _is_empty(fact.value) for fact in self.facts)


@dataclass(frozen=True, slots=True)
class DeliveryEvidenceSnapshot:
    use_case_id: str
    mapping_contract_version: str
    generated_at: str
    sources: tuple[EvidenceSourceSnapshot, ...]
    fields: tuple[FieldEvidence, ...]
    evidence_hash: str

    def field(self, target_field: str) -> FieldEvidence:
        for field_evidence in self.fields:
            if field_evidence.target_field == target_field:
                return field_evidence
        raise KeyError(target_field)

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "use_case_id": self.use_case_id,
            "mapping_contract_version": self.mapping_contract_version,
            "fields": {
                field.target_field: field.evidence_hash
                for field in sorted(self.fields, key=lambda item: item.target_field)
            },
        }


def normalize_evidence_value(value: Any) -> Any:
    """Return a JSON-safe canonical value used exclusively for semantic equality."""

    if value is None:
        return None
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if isinstance(value, bool | int):
        return value
    if isinstance(value, Decimal):
        if value == 0:
            return "0"
        return format(value.normalize(), "f")
    if isinstance(value, float):
        return format(value, ".17g")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): normalize_evidence_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, set | frozenset):
        normalized_items = [normalize_evidence_value(item) for item in value]
        return sorted(normalized_items, key=_canonical_json)
    if isinstance(value, tuple | list):
        return [normalize_evidence_value(item) for item in value]
    return str(value).strip()


def evidence_hash(payload: Any) -> str:
    canonical = _canonical_json(normalize_evidence_value(payload))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_delivery_evidence_snapshot(
    use_case,
    *,
    origin=_AUTO,
    selection_decision=_AUTO,
    approval_decision=_AUTO,
    generated_at: datetime | None = None,
) -> DeliveryEvidenceSnapshot:
    """Build the canonical Block-8 evidence view without writing Delivery state."""

    resolved_origin = _resolve_origin(use_case) if origin is _AUTO else origin
    resolved_selection = (
        _resolve_selection_decision(resolved_origin)
        if selection_decision is _AUTO
        else selection_decision
    )
    resolved_approval = (
        _resolve_final_positive_approval(use_case)
        if approval_decision is _AUTO
        else approval_decision
    )
    selected_snapshot = _selected_solution_snapshot(resolved_selection)

    source_context = {
        "use_case": use_case,
        "value_stream": _value_stream_from_origin(resolved_origin),
        "solution_selection_snapshot": selected_snapshot,
        "approval_decision": resolved_approval,
    }
    source_metadata = _source_metadata(
        use_case=use_case,
        origin=resolved_origin,
        selection_decision=resolved_selection,
        approval_decision=resolved_approval,
        selected_snapshot=selected_snapshot,
    )

    fields = tuple(
        _build_field_evidence(spec, source_context=source_context, source_metadata=source_metadata)
        for spec in V1_DELIVERY_FIELD_MAPPINGS.values()
    )
    semantic_payload = {
        "use_case_id": str(use_case.pk),
        "mapping_contract_version": MAPPING_CONTRACT_VERSION,
        "fields": {
            field.target_field: field.evidence_hash
            for field in sorted(fields, key=lambda item: item.target_field)
        },
    }
    snapshot_time = generated_at or timezone.now()
    return DeliveryEvidenceSnapshot(
        use_case_id=str(use_case.pk),
        mapping_contract_version=MAPPING_CONTRACT_VERSION,
        generated_at=snapshot_time.isoformat(),
        sources=tuple(
            sorted(source_metadata.values(), key=lambda item: (item.kind, item.source_id))
        ),
        fields=fields,
        evidence_hash=evidence_hash(semantic_payload),
    )


def _build_field_evidence(
    spec: DeliveryFieldMappingSpec,
    *,
    source_context: dict[str, Any],
    source_metadata: dict[str, EvidenceSourceSnapshot],
) -> FieldEvidence:
    rules = spec.sources
    if spec.multi_source_policy is MultiSourcePolicy.PRIORITY:
        selected_rule = next(
            (
                rule
                for rule in sorted(rules, key=lambda item: item.priority)
                if _rule_is_applicable(rule, source_context)
            ),
            None,
        )
        rules = (selected_rule,) if selected_rule is not None else ()

    facts: list[EvidenceFact] = []
    for rule in rules:
        source = source_context.get(rule.kind)
        metadata = source_metadata.get(rule.kind)
        if source is None or metadata is None:
            continue
        facts.extend(_facts_for_rule(rule, source=source, metadata=metadata))

    ordered_facts = tuple(
        sorted(
            facts,
            key=lambda fact: (
                fact.priority,
                fact.source_kind,
                fact.source_id,
                fact.source_field,
            ),
        )
    )
    semantic_payload = {
        "mapping_contract_version": MAPPING_CONTRACT_VERSION,
        "target_field": spec.target_field,
        "facts": [fact.semantic_payload() for fact in ordered_facts],
    }
    return FieldEvidence(
        target_field=spec.target_field,
        facts=ordered_facts,
        evidence_hash=evidence_hash(semantic_payload),
    )


def _facts_for_rule(
    rule: SourceRule,
    *,
    source: Any,
    metadata: EvidenceSourceSnapshot,
) -> list[EvidenceFact]:
    return [
        EvidenceFact(
            source_kind=rule.kind,
            source_id=metadata.source_id,
            source_field=field_name,
            value=_source_value(source, field_name),
            source_version=metadata.version,
            semantic_version=metadata.semantic_version,
            priority=rule.priority,
        )
        for field_name in rule.fields
    ]


def _rule_is_applicable(rule: SourceRule, source_context: dict[str, Any]) -> bool:
    if (
        rule.constraint == "fallback_when_no_architecture_value_stream"
        and source_context.get("value_stream") is not None
    ):
        return False
    return _rule_has_usable_evidence(rule, source_context.get(rule.kind))


def _rule_has_usable_evidence(rule: SourceRule, source: Any) -> bool:
    if source is None:
        return False
    required_values = [_source_value(source, name) for name in rule.required_fields]
    if required_values and any(_is_empty(value) for value in required_values):
        return False
    return any(not _is_empty(_source_value(source, name)) for name in rule.fields)


def _source_value(source: Any, field_name: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _source_metadata(
    *,
    use_case,
    origin,
    selection_decision,
    approval_decision,
    selected_snapshot,
) -> dict[str, EvidenceSourceSnapshot]:
    metadata = {
        "use_case": EvidenceSourceSnapshot(
            kind="use_case",
            source_id=str(use_case.pk),
            version=_iso(getattr(use_case, "updated_at", None)),
            semantic_version="",
            updated_at=_iso(getattr(use_case, "updated_at", None)),
        )
    }
    value_stream = _value_stream_from_origin(origin)
    if value_stream is not None:
        metadata["value_stream"] = EvidenceSourceSnapshot(
            kind="value_stream",
            source_id=str(value_stream.pk),
            version=_iso(getattr(value_stream, "updated_at", None)),
            semantic_version="",
            updated_at=_iso(getattr(value_stream, "updated_at", None)),
        )
    if selection_decision is not None and selected_snapshot is not None:
        metadata["solution_selection_snapshot"] = EvidenceSourceSnapshot(
            kind="solution_selection_snapshot",
            source_id=str(selection_decision.pk),
            version=f"decision:{selection_decision.pk}",
            semantic_version=str(selection_decision.pk),
            updated_at=_iso(getattr(selection_decision, "decided_at", None)),
        )
    if approval_decision is not None:
        assessment_version = getattr(
            getattr(approval_decision, "assessment", None), "version", None
        )
        semantic_version = f"approval:{approval_decision.pk}"
        if assessment_version is not None:
            semantic_version += f":assessment-v{assessment_version}"
        metadata["approval_decision"] = EvidenceSourceSnapshot(
            kind="approval_decision",
            source_id=str(approval_decision.pk),
            version=_iso(getattr(approval_decision, "finalized_at", None)),
            semantic_version=semantic_version,
            updated_at=_iso(getattr(approval_decision, "created_at", None)),
        )
    return metadata


def _resolve_origin(use_case):
    try:
        return use_case.architecture_origin
    except ObjectDoesNotExist:
        return None


def _resolve_selection_decision(origin):
    process_analysis = getattr(origin, "process_analysis", None)
    if process_analysis is None:
        return None
    return process_analysis.solution_selection_decisions.select_related("selected_option").first()


def _resolve_final_positive_approval(use_case):
    positive_statuses = (
        UseCase.DecisionStatus.APPROVED,
        UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
    )
    return (
        use_case.approval_decisions.filter(
            decision_status__in=positive_statuses,
            finalized_at__isnull=False,
        )
        .select_related("assessment")
        .order_by("-finalized_at", "-created_at")
        .first()
    )


def _selected_solution_snapshot(selection_decision):
    if selection_decision is None:
        return None
    selected_option_id = str(selection_decision.selected_option_id)
    for option_snapshot in selection_decision.comparison_snapshot or []:
        if str(option_snapshot.get("id", "")) == selected_option_id:
            return option_snapshot
    return None


def _value_stream_from_origin(origin):
    stage = getattr(origin, "stage", None)
    return getattr(stage, "value_stream", None)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, Mapping | list | tuple | set | frozenset):
        return not value
    return False


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _iso(value: datetime | date | None) -> str:
    return value.isoformat() if value else ""
