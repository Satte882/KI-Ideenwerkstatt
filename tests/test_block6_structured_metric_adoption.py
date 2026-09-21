from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from ki_radar.accelerator import structured_metric_adoption
from ki_radar.accelerator.structured_models import (
    StructuredAdoptionBatch,
    StructuredAdoptionItem,
)
from ki_radar.use_cases.models import UseCase

pytestmark = pytest.mark.django_db


def _use_case(owner, business_unit, **overrides):
    values = {
        "title": "Rechnungsprüfung beschleunigen",
        "problem_statement": "Die Prüfung dauert zu lange.",
        "business_unit": business_unit,
        "affected_process": "Rechnungsprüfung",
        "business_owner": owner,
        "submitter": owner,
        "expected_benefit": "Kürzere Bearbeitungszeit",
        "metric_name": "Bearbeitungszeit",
        "metric_type": UseCase.MetricType.DURATION,
        "metric_direction": UseCase.MetricDirection.LOWER,
        "metric_unit": "min",
        "metric_baseline": Decimal("10"),
        "metric_target": Decimal("8"),
        "metric_measurement_method": "Zeitmessung in 20 Fällen",
    }
    values.update(overrides)
    return UseCase.objects.create(**values)


def _batch(use_case, owner, suffix="a"):
    return StructuredAdoptionBatch.objects.create(
        session_id_snapshot=uuid4(),
        analysis_id_snapshot=uuid4(),
        actor_id_snapshot=owner.id,
        target_object_type=StructuredAdoptionBatch.TargetObjectType.USE_CASE,
        target_object_id=use_case.id,
        source_revision=1,
        interpretation_version="1",
        idempotency_key=suffix * 64,
        selected_graph_hash="f" * 64,
        created_by=owner,
    )


def _confirmed_item(
    *,
    batch,
    local_key,
    target_path,
    current_value,
    value=None,
    edited_value=None,
):
    decision = (
        StructuredAdoptionItem.Decision.CONFIRMED_EDITED
        if edited_value is not None
        else StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL
    )
    return StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key=local_key,
        candidate_kind=StructuredAdoptionItem.CandidateKind.METRIC_SET,
        target_path=target_path,
        status=StructuredAdoptionItem.Status.CONFIRMED,
        decision=decision,
        interpretation_snapshot={"value": value} if value is not None else {},
        decision_snapshot=({"edited_value": edited_value} if edited_value is not None else {}),
        field_snapshot={"hash": structured_metric_adoption.metric_value_hash(current_value)},
    )


def test_partial_confirmation_uses_current_database_for_other_fields(owner, business_unit):
    use_case = _use_case(owner, business_unit)
    batch = _batch(use_case, owner)
    baseline = _confirmed_item(
        batch=batch,
        local_key="metric-baseline",
        target_path="use_case.metric.baseline",
        current_value=use_case.metric_baseline,
        value="12",
    )

    result = structured_metric_adoption.adopt_metric_items(
        use_case_id=use_case.id,
        actor=owner,
        items=[baseline],
    )

    use_case.refresh_from_db()
    assert use_case.metric_baseline == Decimal("12")
    assert use_case.metric_target == Decimal("8")
    assert result.sources["metric_baseline"] == baseline.decision
    assert result.sources["metric_target"] == StructuredAdoptionItem.Decision.CURRENT_DATABASE


def test_confirmed_edited_value_is_used(owner, business_unit):
    use_case = _use_case(owner, business_unit)
    batch = _batch(use_case, owner)
    metric_name = _confirmed_item(
        batch=batch,
        local_key="metric-name",
        target_path="use_case.metric.name",
        current_value=use_case.metric_name,
        edited_value="Durchlaufzeit je Rechnung",
    )

    result = structured_metric_adoption.adopt_metric_items(
        use_case_id=use_case.id,
        actor=owner,
        items=[metric_name],
    )

    use_case.refresh_from_db()
    assert use_case.metric_name == "Durchlaufzeit je Rechnung"
    assert result.changed_fields == {"metric_name"}


def test_only_confirmed_field_snapshot_causes_conflict(owner, business_unit):
    use_case = _use_case(owner, business_unit)
    batch = _batch(use_case, owner)
    baseline = _confirmed_item(
        batch=batch,
        local_key="metric-baseline",
        target_path="use_case.metric.baseline",
        current_value=use_case.metric_baseline,
        value="12",
    )
    use_case.metric_baseline = Decimal("11")
    use_case.metric_unit = "Minuten"
    use_case.save(update_fields=["metric_baseline", "metric_unit", "updated_at"])

    with pytest.raises(structured_metric_adoption.StructuredMetricConflict):
        structured_metric_adoption.adopt_metric_items(
            use_case_id=use_case.id,
            actor=owner,
            items=[baseline],
        )

    use_case.refresh_from_db()
    assert use_case.metric_baseline == Decimal("11")
    assert use_case.metric_unit == "Minuten"


def test_percent_range_failure_rolls_back_complete_metric_group(owner, business_unit):
    use_case = _use_case(
        owner,
        business_unit,
        metric_type=UseCase.MetricType.PERCENT,
        metric_direction=UseCase.MetricDirection.HIGHER,
        metric_unit="%",
        metric_baseline=Decimal("50"),
        metric_target=Decimal("70"),
    )
    batch = _batch(use_case, owner)
    baseline = _confirmed_item(
        batch=batch,
        local_key="metric-baseline",
        target_path="use_case.metric.baseline",
        current_value=use_case.metric_baseline,
        value="120",
    )
    name = _confirmed_item(
        batch=batch,
        local_key="metric-name",
        target_path="use_case.metric.name",
        current_value=use_case.metric_name,
        value="Automatisierungsquote",
    )

    with pytest.raises(structured_metric_adoption.StructuredMetricValidationError) as exc_info:
        structured_metric_adoption.adopt_metric_items(
            use_case_id=use_case.id,
            actor=owner,
            items=[baseline, name],
        )

    use_case.refresh_from_db()
    assert "metric_baseline" in exc_info.value.errors
    assert use_case.metric_baseline == Decimal("50")
    assert use_case.metric_name == "Bearbeitungszeit"


def test_direction_consistency_failure_does_not_write_partial_state(owner, business_unit):
    use_case = _use_case(owner, business_unit)
    batch = _batch(use_case, owner)
    direction = _confirmed_item(
        batch=batch,
        local_key="metric-direction",
        target_path="use_case.metric.direction",
        current_value=use_case.metric_direction,
        value=UseCase.MetricDirection.HIGHER,
    )

    with pytest.raises(structured_metric_adoption.StructuredMetricValidationError) as exc_info:
        structured_metric_adoption.adopt_metric_items(
            use_case_id=use_case.id,
            actor=owner,
            items=[direction],
        )

    use_case.refresh_from_db()
    assert "metric_target" in exc_info.value.errors
    assert use_case.metric_direction == UseCase.MetricDirection.LOWER
    assert use_case.metric_baseline == Decimal("10")
    assert use_case.metric_target == Decimal("8")
