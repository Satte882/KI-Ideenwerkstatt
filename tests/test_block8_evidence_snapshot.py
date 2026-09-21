from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from ki_radar.delivery.evidence_snapshot import (
    _resolve_final_positive_approval,
    build_delivery_evidence_snapshot,
    evidence_hash,
    normalize_evidence_value,
)
from ki_radar.use_cases.models import UseCase


def make_use_case(**overrides):
    values = {
        "pk": "use-case-1",
        "updated_at": datetime(2026, 8, 8, 8, 0, tzinfo=UTC),
        "problem_statement": "Manueller Angebotsvergleich",
        "expected_benefit": "Bearbeitungszeit reduzieren",
        "summary": "Angebote strukturiert vergleichen",
        "affected_process": "Lieferantenauswahl",
        "target_users": "Einkauf",
        "intended_users": "Einkauf",
        "intended_purpose": "Angebote vergleichbar machen",
        "source_systems": "ERP",
        "data_sources": "Angebote",
        "interface_description": "ERP API",
        "human_oversight": "Einkauf bestätigt das Ergebnis",
        "support_responsibility": "IT Application Management",
        "metric_name": "Bearbeitungszeit",
        "metric_type": "duration",
        "metric_direction": "lower",
        "metric_unit": "min",
        "metric_baseline": Decimal("11.0000"),
        "metric_target": Decimal("8.2500"),
        "metric_measurement_method": "Zeitmessung",
        "metric_measurement_period": "Pilot",
        "success_criterion": "Zielwert erreicht",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_origin(*, scope_in="Beschaffungsbedarf bis Bestellung", scope_out="Zahlung"):
    value_stream = SimpleNamespace(
        pk="value-stream-1",
        updated_at=datetime(2026, 8, 8, 7, 0, tzinfo=UTC),
        scope_in=scope_in,
        scope_out=scope_out,
    )
    stage = SimpleNamespace(value_stream=value_stream)
    return SimpleNamespace(stage=stage, process_analysis=None)


def make_selection_decision(*, description="Snapshot-Beschreibung"):
    return SimpleNamespace(
        pk="decision-1",
        selected_option_id="option-1",
        decided_at=datetime(2026, 8, 8, 7, 30, tzinfo=UTC),
        comparison_snapshot=[
            {
                "id": "option-1",
                "description": description,
                "application_impact": "Bestehendes ERP bleibt führend",
                "integration_impact": "Bestehende ERP API",
                "risks": "Fehlerhafte Angebotsdaten",
                "updated_at": "2026-08-01T12:00:00+00:00",
            }
        ],
        selected_option=SimpleNamespace(
            description="Später mutierter Live-Wert",
            application_impact="Später mutierter Live-Wert",
            integration_impact="Später mutierter Live-Wert",
            risks="Später mutierter Live-Wert",
        ),
    )


def make_approval(*, finalized_at=None):
    return SimpleNamespace(
        pk="approval-1",
        decision_status=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
        rationale="Freigabe nach fachlicher Prüfung",
        conditions="Pilot auf Einkauf begrenzen",
        condition_owner_id="owner-1",
        condition_due_date=None,
        finalized_at=finalized_at or datetime(2026, 8, 8, 7, 45, tzinfo=UTC),
        created_at=datetime(2026, 8, 8, 7, 40, tzinfo=UTC),
        assessment=SimpleNamespace(version=3),
    )


def build_snapshot(use_case=None, **overrides):
    return build_delivery_evidence_snapshot(
        use_case or make_use_case(),
        origin=overrides.pop("origin", make_origin()),
        selection_decision=overrides.pop("selection_decision", make_selection_decision()),
        approval_decision=overrides.pop("approval_decision", make_approval()),
        **overrides,
    )


def test_normalization_is_structured_and_not_rendered_text_based():
    first = {
        "metric": Decimal("8.2500"),
        "labels": {"B", "A"},
        "note": "  Zeile 1\r\nZeile 2  ",
    }
    second = {
        "note": "Zeile 1\nZeile 2",
        "labels": {"A", "B"},
        "metric": Decimal("8.25"),
    }

    assert normalize_evidence_value(first) == normalize_evidence_value(second)
    assert evidence_hash(first) == evidence_hash(second)


def test_volatile_timestamps_do_not_change_semantic_hashes():
    approval = make_approval()
    first = build_snapshot(
        approval_decision=approval,
        generated_at=datetime(2026, 8, 8, 8, 0, tzinfo=UTC),
    )
    changed_use_case = make_use_case(updated_at=datetime(2026, 8, 9, 8, 0, tzinfo=UTC))
    changed_origin = make_origin()
    changed_origin.stage.value_stream.updated_at = datetime(2026, 8, 9, 7, 0, tzinfo=UTC)
    second = build_snapshot(
        changed_use_case,
        origin=changed_origin,
        approval_decision=approval,
        generated_at=datetime(2026, 8, 9, 8, 0, tzinfo=UTC),
    )
    first_fields = {field.target_field: field.evidence_hash for field in first.fields}
    second_fields = {field.target_field: field.evidence_hash for field in second.fields}

    assert first.generated_at != second.generated_at
    assert first.sources != second.sources
    assert first.evidence_hash == second.evidence_hash
    assert first_fields == second_fields


def test_final_approval_timestamp_is_semantic_handover_evidence():
    first = build_snapshot()
    changed_approval = make_approval(finalized_at=datetime(2026, 8, 9, 7, 45, tzinfo=UTC))
    second = build_snapshot(approval_decision=changed_approval)
    first_handover = first.field("handover_notes").evidence_hash
    second_handover = second.field("handover_notes").evidence_hash
    first_problem = first.field("problem_context").evidence_hash
    second_problem = second.field("problem_context").evidence_hash

    assert first_handover != second_handover
    assert first_problem == second_problem
    assert first.evidence_hash != second.evidence_hash


def test_semantic_source_change_changes_relevant_field_and_snapshot_hash():
    first = build_snapshot()
    second = build_snapshot(make_use_case(problem_statement="Neuer bestätigter Problemkontext"))
    first_problem = first.field("problem_context").evidence_hash
    second_problem = second.field("problem_context").evidence_hash
    first_target = first.field("target_outcome").evidence_hash
    second_target = second.field("target_outcome").evidence_hash

    assert first_problem != second_problem
    assert first_target == second_target
    assert first.evidence_hash != second.evidence_hash


def test_value_stream_scope_wins_over_lower_priority_use_case_fallback():
    first = build_snapshot(make_use_case(summary="Fallback A"))
    second = build_snapshot(make_use_case(summary="Fallback B"))
    first_scope = first.field("in_scope")
    second_scope = second.field("in_scope")

    assert [(fact.source_kind, fact.value) for fact in first_scope.facts] == [
        ("value_stream", "Beschaffungsbedarf bis Bestellung")
    ]
    assert first_scope.evidence_hash == second_scope.evidence_hash


def test_use_case_scope_fallback_is_used_only_without_architecture_value_stream():
    snapshot = build_snapshot(
        make_use_case(summary="Nur bestätigter Use-Case-Scope"),
        origin=None,
        selection_decision=None,
    )
    actual = [
        (fact.source_kind, fact.source_field, fact.value)
        for fact in snapshot.field("in_scope").facts
    ]

    assert actual == [("use_case", "summary", "Nur bestätigter Use-Case-Scope")]


def test_solution_specific_evidence_comes_from_immutable_comparison_snapshot():
    snapshot = build_snapshot(
        make_use_case(intended_purpose="", summary=""),
        selection_decision=make_selection_decision(
            description="Zum Entscheidungszeitpunkt bestätigt"
        ),
    )
    solution = snapshot.field("solution_outline")
    all_values = [fact.value for field in snapshot.fields for fact in field.facts]

    assert [(fact.source_kind, fact.value) for fact in solution.facts] == [
        ("solution_selection_snapshot", "Zum Entscheidungszeitpunkt bestätigt")
    ]
    assert "Später mutierter Live-Wert" not in all_values


def test_selected_snapshot_timestamp_is_not_part_of_semantic_hash():
    first_decision = make_selection_decision()
    second_decision = make_selection_decision()
    second_decision.comparison_snapshot[0]["updated_at"] = "2030-01-01T00:00:00+00:00"
    first = build_snapshot(selection_decision=first_decision)
    second = build_snapshot(selection_decision=second_decision)
    first_hash = first.field("system_landscape").evidence_hash
    second_hash = second.field("system_landscape").evidence_hash

    assert first_hash == second_hash
    assert first.evidence_hash == second.evidence_hash


class FakeApprovalQuery:
    def __init__(self, result):
        self.result = result
        self.filter_kwargs = None
        self.related = None
        self.ordering = None

    def filter(self, **kwargs):
        self.filter_kwargs = kwargs
        return self

    def select_related(self, *fields):
        self.related = fields
        return self

    def order_by(self, *fields):
        self.ordering = fields
        return self

    def first(self):
        return self.result


def test_approval_resolution_requires_final_positive_existing_decision():
    approval = make_approval()
    manager = FakeApprovalQuery(approval)
    use_case = SimpleNamespace(approval_decisions=manager)

    assert _resolve_final_positive_approval(use_case) is approval
    assert manager.filter_kwargs == {
        "decision_status__in": (
            UseCase.DecisionStatus.APPROVED,
            UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
        ),
        "finalized_at__isnull": False,
    }
    assert manager.related == ("assessment",)
    assert manager.ordering == ("-finalized_at", "-created_at")
