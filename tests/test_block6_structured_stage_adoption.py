from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone

from ki_radar.accelerator import structured_stage_adoption
from ki_radar.accelerator.models import CaptureFieldSuggestion
from ki_radar.accelerator.structured_models import (
    StructuredAdoptionBatch,
    StructuredAdoptionItem,
)
from ki_radar.architecture.models import ValueStream, ValueStreamStage

pytestmark = pytest.mark.django_db


def _value_stream(owner, business_unit):
    return ValueStream.objects.create(
        name="Beschaffung",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf ist freigegeben.",
        outcome="Bestellung ist ausgelöst.",
        scope_in="Von Bedarf bis Bestellung.",
        created_by=owner,
    )


def _batch(value_stream, owner, suffix="a"):
    return StructuredAdoptionBatch.objects.create(
        session_id_snapshot=uuid4(),
        analysis_id_snapshot=uuid4(),
        actor_id_snapshot=owner.id,
        target_object_type=StructuredAdoptionBatch.TargetObjectType.VALUE_STREAM,
        target_object_id=value_stream.id,
        source_revision=1,
        interpretation_version="1",
        idempotency_key=suffix * 64,
        selected_graph_hash="f" * 64,
        created_by=owner,
    )


def _stage_item(*, batch, local_key, sequence, name, edited=False):
    fields = {
        "sequence": sequence,
        "name": name,
        "description": f"Beschreibung {name}",
    }
    decision = (
        StructuredAdoptionItem.Decision.CONFIRMED_EDITED
        if edited
        else StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL
    )
    return StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key=local_key,
        candidate_kind=StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE,
        target_group_key=local_key,
        status=StructuredAdoptionItem.Status.CONFIRMED,
        decision=decision,
        interpretation_snapshot={"fields": fields} if not edited else {},
        decision_snapshot={"edited_fields": fields} if edited else {},
    )


def _suggestion(*, group_key, target_field, field_type, value, question):
    return SimpleNamespace(
        id=uuid4(),
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM_STAGE,
        target_group_key=group_key,
        target_field=target_field,
        field_type=field_type,
        suggested_value=value,
        source_question=question,
        source_excerpt=f"Quelle für {group_key} und {target_field}",
    )


def test_stage_suggestions_are_grouped_by_target_group_key():
    suggestions = [
        _suggestion(
            group_key="stage-02",
            target_field="value_stream.stages[].name",
            field_type="text",
            value="Bestellung auslösen",
            question="vs_stages",
        ),
        _suggestion(
            group_key="stage-01",
            target_field="value_stream.stages[].sequence",
            field_type="integer",
            value=1,
            question="vs_stages",
        ),
        _suggestion(
            group_key="stage-02",
            target_field="value_stream.stages[].sequence",
            field_type="integer",
            value=2,
            question="vs_stages",
        ),
        _suggestion(
            group_key="stage-01",
            target_field="value_stream.stages[].name",
            field_type="text",
            value="Angebot prüfen",
            question="vs_stages",
        ),
    ]

    groups = structured_stage_adoption.group_stage_suggestions(suggestions)

    assert [group.local_key for group in groups] == ["stage-01", "stage-02"]
    assert groups[0].values["sequence"] == 1
    assert groups[0].values["name"] == "Angebot prüfen"
    defaults = structured_stage_adoption.stage_item_defaults(groups[0])
    assert defaults["local_key"] == "stage-01"
    assert defaults["target_group_key"] == "stage-01"
    assert defaults["proposed_snapshot"]["fields"]["sequence"] == 1
    assert defaults["source_snapshot"]["suggestion_ids"]
    assert "source_excerpt" not in defaults["source_snapshot"]


def test_stage_grouping_rejects_missing_required_field():
    suggestions = [
        _suggestion(
            group_key="stage-01",
            target_field="value_stream.stages[].name",
            field_type="text",
            value="Angebot prüfen",
            question="vs_stages",
        )
    ]

    with pytest.raises(structured_stage_adoption.StructuredStageError):
        structured_stage_adoption.group_stage_suggestions(suggestions)


def test_stage_grouping_rejects_duplicate_local_sequence():
    suggestions = []
    for group_key, name in (("stage-01", "Angebot prüfen"), ("stage-02", "Freigeben")):
        suggestions.extend(
            [
                _suggestion(
                    group_key=group_key,
                    target_field="value_stream.stages[].sequence",
                    field_type="integer",
                    value=1,
                    question="vs_stages",
                ),
                _suggestion(
                    group_key=group_key,
                    target_field="value_stream.stages[].name",
                    field_type="text",
                    value=name,
                    question="vs_stages",
                ),
            ]
        )

    with pytest.raises(structured_stage_adoption.StructuredStageConflict):
        structured_stage_adoption.group_stage_suggestions(suggestions)


def test_confirmed_stage_items_are_written_through_stage_form(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    batch = _batch(value_stream, owner)
    first = _stage_item(
        batch=batch,
        local_key="stage-01",
        sequence=1,
        name="Angebot prüfen",
    )
    second = _stage_item(
        batch=batch,
        local_key="stage-02",
        sequence=2,
        name="Bestellung auslösen",
        edited=True,
    )

    result = structured_stage_adoption.adopt_stage_items(
        value_stream_id=value_stream.id,
        items=[second, first],
    )

    stages = list(value_stream.stages.order_by("sequence"))
    assert [stage.name for stage in stages] == ["Angebot prüfen", "Bestellung auslösen"]
    assert set(result.created_stage_ids) == {"stage-01", "stage-02"}
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == StructuredAdoptionItem.Status.ADOPTED
    assert first.created_object_id == stages[0].id
    assert second.created_object_id == stages[1].id


def test_database_sequence_collision_blocks_all_new_stages(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Bestehende Phase",
    )
    batch = _batch(value_stream, owner)
    first = _stage_item(
        batch=batch,
        local_key="stage-01",
        sequence=1,
        name="Kollidierende Phase",
    )
    second = _stage_item(
        batch=batch,
        local_key="stage-02",
        sequence=2,
        name="Neue Phase",
    )

    with pytest.raises(structured_stage_adoption.StructuredStageConflict):
        structured_stage_adoption.adopt_stage_items(
            value_stream_id=value_stream.id,
            items=[first, second],
        )

    assert value_stream.stages.count() == 1
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == StructuredAdoptionItem.Status.CONFIRMED
    assert second.status == StructuredAdoptionItem.Status.CONFIRMED


def test_form_failure_rolls_back_complete_stage_set(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    batch = _batch(value_stream, owner)
    valid = _stage_item(
        batch=batch,
        local_key="stage-01",
        sequence=1,
        name="Angebot prüfen",
    )
    invalid = _stage_item(
        batch=batch,
        local_key="stage-02",
        sequence=2,
        name="X" * 201,
    )

    with pytest.raises(structured_stage_adoption.StructuredStageValidationError) as exc_info:
        structured_stage_adoption.adopt_stage_items(
            value_stream_id=value_stream.id,
            items=[valid, invalid],
        )

    assert "name" in exc_info.value.errors["stage-02"]
    assert value_stream.stages.count() == 0
    valid.refresh_from_db()
    invalid.refresh_from_db()
    assert valid.status == StructuredAdoptionItem.Status.CONFIRMED
    assert invalid.status == StructuredAdoptionItem.Status.CONFIRMED


def test_invalid_stage_cascades_to_confirmed_process_item(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    batch = _batch(value_stream, owner)
    stage = _stage_item(
        batch=batch,
        local_key="stage-01",
        sequence=1,
        name="Angebot prüfen",
    )
    process = StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key="process-01",
        candidate_kind=StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS,
        depends_on=stage,
        dependency_key_snapshot=stage.local_key,
        status=StructuredAdoptionItem.Status.CONFIRMED,
        decision=StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
        confirmed_by=owner,
        confirmed_by_id_snapshot=owner.id,
        confirmed_at=timezone.now(),
    )

    updated = structured_stage_adoption.cascade_invalidate_stage_dependents(
        stage_item=stage,
        stage_state=StructuredAdoptionItem.Status.REJECTED,
    )

    assert updated == 1
    process.refresh_from_db()
    assert process.status == StructuredAdoptionItem.Status.DEPENDENCY_INVALID
    assert process.decision == StructuredAdoptionItem.Decision.PENDING
    assert process.confirmed_by is None
    assert process.confirmed_at is None
    assert process.error_code == "stage_dependency_rejected"


def test_non_invalidating_stage_state_keeps_dependency_confirmation(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    batch = _batch(value_stream, owner)
    stage = _stage_item(
        batch=batch,
        local_key="stage-01",
        sequence=1,
        name="Angebot prüfen",
    )
    process = StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key="process-01",
        candidate_kind=StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS,
        depends_on=stage,
        dependency_key_snapshot=stage.local_key,
        status=StructuredAdoptionItem.Status.CONFIRMED,
        decision=StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
        confirmed_by=owner,
        confirmed_by_id_snapshot=owner.id,
        confirmed_at=timezone.now(),
    )

    updated = structured_stage_adoption.cascade_invalidate_stage_dependents(
        stage_item=stage,
        stage_state=StructuredAdoptionItem.Status.CONFIRMED,
    )

    assert updated == 0
    process.refresh_from_db()
    assert process.status == StructuredAdoptionItem.Status.CONFIRMED
    assert process.confirmed_by == owner
