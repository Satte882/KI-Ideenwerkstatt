from decimal import Decimal

import pytest

from ki_radar.delivery.evidence_composer import (
    COMPOSED_FIELD_LABELS,
    compose_delivery_fields,
    compose_field,
    composed_target_fields,
)
from ki_radar.delivery.evidence_mapping_contract import mapping_spec
from ki_radar.delivery.evidence_snapshot import (
    DeliveryEvidenceSnapshot,
    EvidenceFact,
    FieldEvidence,
    evidence_hash,
)

EXPECTED_COMPOSED_FIELDS = {
    "measurement_plan",
    "acceptance_criteria",
    "handover_notes",
    "system_landscape",
    "data_flows",
}


def make_field(target_field, values):
    spec = mapping_spec(target_field)
    facts = []
    for rule in spec.sources:
        for field_name in rule.fields:
            facts.append(
                EvidenceFact(
                    source_kind=rule.kind,
                    source_id=f"{rule.kind}-{rule.priority}",
                    source_field=field_name,
                    value=values.get(field_name),
                    source_version=f"{rule.kind}-v1",
                    semantic_version=f"{rule.kind}-semantic-v1",
                    priority=rule.priority,
                )
            )
    payload = {"target_field": target_field, "values": values}
    return FieldEvidence(
        target_field=target_field,
        facts=tuple(facts),
        evidence_hash=evidence_hash(payload),
    )


def make_snapshot(field):
    return DeliveryEvidenceSnapshot(
        use_case_id="use-case-1",
        mapping_contract_version="block8.v1",
        generated_at="2026-08-08T08:00:00+00:00",
        sources=(),
        fields=(field,),
        evidence_hash=field.evidence_hash,
    )


def test_ap4_targets_exactly_composed_v1_fields_and_labels_cover_contract():
    assert set(composed_target_fields()) == EXPECTED_COMPOSED_FIELDS
    for target_field in composed_target_fields():
        spec = mapping_spec(target_field)
        contract_fields = set()
        for source in spec.sources:
            contract_fields.update(source.fields)
        assert set(COMPOSED_FIELD_LABELS[target_field]) == contract_fields


def test_measurement_plan_is_deterministic_independent_of_fact_input_order():
    values = {
        "metric_name": "Bearbeitungszeit",
        "metric_type": "duration",
        "metric_direction": "lower",
        "metric_unit": "min",
        "metric_baseline": Decimal("11.000"),
        "metric_target": Decimal("8.2500"),
        "metric_measurement_method": "Zeitmessung",
        "metric_measurement_period": "Pilot",
    }
    field = make_field("measurement_plan", values)
    reversed_field = FieldEvidence(
        target_field=field.target_field,
        facts=tuple(reversed(field.facts)),
        evidence_hash=field.evidence_hash,
    )

    first = compose_field(make_snapshot(field), "measurement_plan")
    second = compose_field(make_snapshot(reversed_field), "measurement_plan")
    expected_lines = [
        "Metrik: Bearbeitungszeit",
        "Metriktyp: duration",
        "Richtung: lower",
        "Einheit: min",
        "Baseline: 11",
        "Ziel: 8.25",
        "Messmethode: Zeitmessung",
        "Messzeitraum: Pilot",
    ]

    assert first == second
    assert first.value == "\n".join(expected_lines)
    assert first.evidence_hash == field.evidence_hash
    assert first.is_gap is False


def test_incomplete_required_measurement_rule_remains_gap_but_keeps_source_evidence():
    field = make_field(
        "measurement_plan",
        {
            "metric_name": "Bearbeitungszeit",
            "metric_baseline": Decimal("11"),
            "metric_target": Decimal("8.25"),
            "metric_measurement_method": None,
        },
    )

    mapping = compose_field(make_snapshot(field), "measurement_plan")
    source_fields = {source.source_field for source in mapping.sources}

    assert mapping.value == ""
    assert mapping.is_gap is True
    assert source_fields == {
        "metric_name",
        "metric_baseline",
        "metric_target",
    }


def test_acceptance_criteria_uses_each_complete_rule_without_inventing_missing_metrics():
    field = make_field(
        "acceptance_criteria",
        {
            "success_criterion": "Zielwert im Pilot erreicht",
            "metric_name": "Bearbeitungszeit",
            "metric_target": None,
        },
    )

    mapping = compose_field(make_snapshot(field), "acceptance_criteria")

    assert mapping.value == "Erfolgskriterium: Zielwert im Pilot erreicht"
    assert mapping.is_gap is False
    assert "konkretisieren" not in mapping.value.lower()


def test_system_landscape_composes_confirmed_domain_and_solution_snapshot_facts():
    field = make_field(
        "system_landscape",
        {
            "source_systems": "ERP",
            "application_impact": "Bestehendes ERP bleibt führend",
        },
    )

    mapping = compose_field(make_snapshot(field), "system_landscape")
    expected = "Quellsysteme: ERP\nAnwendungsauswirkung: Bestehendes ERP bleibt führend"

    assert mapping.value == expected
    assert [source.source_kind for source in mapping.sources] == [
        "use_case",
        "solution_selection_snapshot",
    ]


def test_data_flows_omits_empty_optional_fact_and_keeps_later_confirmed_source():
    field = make_field(
        "data_flows",
        {
            "data_sources": "Angebote",
            "interface_description": "",
            "integration_impact": "Bestehende ERP API",
        },
    )

    mapping = compose_field(make_snapshot(field), "data_flows")
    expected = "Datenquellen: Angebote\nIntegrationsauswirkung: Bestehende ERP API"

    assert mapping.value == expected
    assert "Schnittstelle:" not in mapping.value


def test_handover_notes_requires_existing_final_approval_facts():
    complete = make_field(
        "handover_notes",
        {
            "decision_status": "approved_with_conditions",
            "rationale": "Freigabe nach fachlicher Prüfung",
            "conditions": "Pilot auf Einkauf begrenzen",
            "condition_owner_id": "owner-1",
            "condition_due_date": "2026-08-31",
            "finalized_at": "2026-08-08T07:45:00+00:00",
        },
    )
    incomplete = make_field(
        "handover_notes",
        {
            "decision_status": "approved_with_conditions",
            "rationale": "Freigabe nach fachlicher Prüfung",
            "finalized_at": None,
        },
    )

    mapped = compose_field(make_snapshot(complete), "handover_notes")
    gap = compose_field(make_snapshot(incomplete), "handover_notes")

    assert "Freigabestatus: approved_with_conditions" in mapped.value
    assert "Finalisiert am: 2026-08-08T07:45:00+00:00" in mapped.value
    assert mapped.is_gap is False
    assert gap.value == ""
    assert gap.is_gap is True


def test_compose_delivery_fields_is_provider_free_and_reproducible():
    snapshots = []
    for target_field in composed_target_fields():
        spec = mapping_spec(target_field)
        values = {}
        for rule in spec.sources:
            for field_name in rule.fields:
                values[field_name] = f"Wert {field_name}"
        snapshots.append(make_field(target_field, values))
    snapshot = DeliveryEvidenceSnapshot(
        use_case_id="use-case-1",
        mapping_contract_version="block8.v1",
        generated_at="2026-08-08T08:00:00+00:00",
        sources=(),
        fields=tuple(snapshots),
        evidence_hash="snapshot-hash",
    )

    first = compose_delivery_fields(snapshot)
    second = compose_delivery_fields(snapshot)
    mapped_fields = {mapping.target_field for mapping in first}

    assert first == second
    assert mapped_fields == EXPECTED_COMPOSED_FIELDS


def test_direct_field_is_rejected_by_composer():
    field = FieldEvidence(
        target_field="problem_context",
        facts=(),
        evidence_hash="field-hash",
    )

    with pytest.raises(ValueError, match="kein Kompositionsfeld"):
        compose_field(make_snapshot(field), "problem_context")


def test_duplicate_composition_evidence_fails_closed():
    field = make_field(
        "system_landscape",
        {
            "source_systems": "ERP",
            "application_impact": "ERP bleibt führend",
        },
    )
    duplicate_facts = list(field.facts)
    duplicate_facts.append(field.facts[0])
    duplicate_field = FieldEvidence(
        target_field=field.target_field,
        facts=tuple(duplicate_facts),
        evidence_hash=field.evidence_hash,
    )

    with pytest.raises(ValueError, match="Doppelte Evidence"):
        compose_field(make_snapshot(duplicate_field), "system_landscape")
