import pytest

from ki_radar.delivery.evidence_mapper import (
    direct_mapping_for,
    direct_target_fields,
    map_direct_delivery_fields,
)
from ki_radar.delivery.evidence_mapping_contract import TransformKind, mapping_spec
from ki_radar.delivery.evidence_snapshot import (
    DeliveryEvidenceSnapshot,
    EvidenceFact,
    FieldEvidence,
    evidence_hash,
)

EXPECTED_DIRECT_FIELDS = {
    "problem_context",
    "target_outcome",
    "in_scope",
    "out_of_scope",
    "users_and_scenarios",
    "solution_outline",
    "system_context",
    "data_context",
    "integrations",
    "human_oversight",
    "operations_and_support",
    "risks",
}
EXPECTED_COMPOSED_FIELDS = {
    "measurement_plan",
    "acceptance_criteria",
    "handover_notes",
    "system_landscape",
    "data_flows",
}


def make_field(target_field, value, *, source_kind=None, source_field=None):
    spec = mapping_spec(target_field)
    rule = spec.sources[0]
    kind = source_kind or rule.kind
    field_name = source_field or rule.fields[0]
    facts = ()
    if value is not None:
        facts = (
            EvidenceFact(
                source_kind=kind,
                source_id=f"{kind}-1",
                source_field=field_name,
                value=value,
                source_version="source-v1",
                semantic_version="semantic-v1",
                priority=rule.priority,
            ),
        )
    payload = {
        "target_field": target_field,
        "value": value,
        "source_kind": kind,
        "source_field": field_name,
    }
    return FieldEvidence(
        target_field=target_field,
        facts=facts,
        evidence_hash=evidence_hash(payload),
    )


def make_snapshot(overrides=None):
    overrides = overrides or {}
    fields = []
    for target_field in direct_target_fields():
        default_value = f"Wert {target_field}"
        value = overrides.get(target_field, default_value)
        fields.append(make_field(target_field, value))
    field_tuple = tuple(fields)
    field_hashes = {field.target_field: field.evidence_hash for field in field_tuple}
    return DeliveryEvidenceSnapshot(
        use_case_id="use-case-1",
        mapping_contract_version="block8.v1",
        generated_at="2026-08-08T08:00:00+00:00",
        sources=(),
        fields=field_tuple,
        evidence_hash=evidence_hash(field_hashes),
    )


def test_ap3_targets_exactly_non_composed_v1_fields():
    target_fields = set(direct_target_fields())
    assert target_fields == EXPECTED_DIRECT_FIELDS
    assert not (target_fields & EXPECTED_COMPOSED_FIELDS)
    allowed_transforms = {
        TransformKind.DIRECT,
        TransformKind.PRIORITY_FIRST_NON_EMPTY,
    }
    for target_field in direct_target_fields():
        assert mapping_spec(target_field).transform in allowed_transforms


def test_direct_mapping_is_reproducible_and_provider_free():
    first = map_direct_delivery_fields(make_snapshot())
    second = map_direct_delivery_fields(make_snapshot())

    assert first == second
    mapped_fields = {mapping.target_field for mapping in first}
    assert mapped_fields == EXPECTED_DIRECT_FIELDS
    assert all(not mapping.is_gap for mapping in first)


def test_direct_mapping_uses_canonical_text_without_generating_content():
    snapshot = make_snapshot({"system_context": "  ERP\r\nCRM  "})
    mapping = direct_mapping_for(snapshot, "system_context")

    assert mapping.value == "ERP\nCRM"
    assert mapping.is_gap is False


def test_missing_required_evidence_remains_empty_gap_without_placeholder():
    snapshot = make_snapshot({"human_oversight": None})
    mapping = direct_mapping_for(snapshot, "human_oversight")

    assert mapping.value == ""
    assert mapping.is_gap is True
    assert mapping.sources == ()


def test_mapping_metadata_keeps_source_identity_and_versions():
    snapshot = make_snapshot()
    mapping = direct_mapping_for(snapshot, "problem_context")

    assert len(mapping.sources) == 1
    source = mapping.sources[0]
    assert source.source_kind == "use_case"
    assert source.source_id == "use_case-1"
    assert source.source_field == "problem_statement"
    assert source.source_version == "source-v1"
    assert source.semantic_version == "semantic-v1"
    assert mapping.evidence_hash == snapshot.field("problem_context").evidence_hash


def test_priority_selection_is_consumed_from_snapshot_without_reinterpreting_sources():
    field = make_field(
        "in_scope",
        "Beschaffungsbedarf bis Bestellung",
        source_kind="value_stream",
        source_field="scope_in",
    )
    snapshot = DeliveryEvidenceSnapshot(
        use_case_id="use-case-1",
        mapping_contract_version="block8.v1",
        generated_at="2026-08-08T08:00:00+00:00",
        sources=(),
        fields=(field,),
        evidence_hash=field.evidence_hash,
    )
    mapping = direct_mapping_for(snapshot, "in_scope")

    assert mapping.value == "Beschaffungsbedarf bis Bestellung"
    assert mapping.sources[0].source_kind == "value_stream"
    assert mapping.sources[0].source_field == "scope_in"


def test_composed_field_is_deferred_to_ap4():
    snapshot = DeliveryEvidenceSnapshot(
        use_case_id="use-case-1",
        mapping_contract_version="block8.v1",
        generated_at="2026-08-08T08:00:00+00:00",
        sources=(),
        fields=(make_field("measurement_plan", "Metrik"),),
        evidence_hash="snapshot-hash",
    )

    with pytest.raises(ValueError, match="Komposition"):
        direct_mapping_for(snapshot, "measurement_plan")


def test_direct_mapping_fails_closed_if_snapshot_contains_multiple_active_facts():
    first = make_field("problem_context", "Problem A").facts[0]
    second = EvidenceFact(
        source_kind="use_case",
        source_id="use_case-2",
        source_field="problem_statement",
        value="Problem B",
        source_version="source-v2",
        semantic_version="semantic-v2",
        priority=2,
    )
    field = FieldEvidence(
        target_field="problem_context",
        facts=(first, second),
        evidence_hash="field-hash",
    )
    snapshot = DeliveryEvidenceSnapshot(
        use_case_id="use-case-1",
        mapping_contract_version="block8.v1",
        generated_at="2026-08-08T08:00:00+00:00",
        sources=(),
        fields=(field,),
        evidence_hash="snapshot-hash",
    )

    with pytest.raises(ValueError, match="höchstens eine aktive Evidence-Quelle"):
        direct_mapping_for(snapshot, "problem_context")
