from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone

from ki_radar.accelerator import structured_process_adoption
from ki_radar.accelerator.models import CaptureFieldSuggestion
from ki_radar.accelerator.structured_models import (
    StructuredAdoptionBatch,
    StructuredAdoptionItem,
)
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
)

pytestmark = pytest.mark.django_db


REQUIRED_PROCESS_VALUES = {
    "name": "Angebotsprüfung",
    "scope_start": "Angebot liegt vor",
    "scope_end": "Angebot ist freigegeben",
    "trigger": "Ein Einkaufsvorgang benötigt ein Angebot",
    "outcome": "Das wirtschaftlichste Angebot ist ausgewählt",
    "current_flow": "Einkauf vergleicht Angebote manuell.",
    "roles": "Einkauf, Fachbereich",
    "systems": "ERP, Tabellenkalkulation",
    "data_objects": "Angebote, Bestellanforderung",
    "bottlenecks": "Medienbruch und manueller Vergleich",
    "baseline_metrics": "11 Minuten je Vergleich",
}


def _value_stream(owner, business_unit, name="Beschaffung"):
    return ValueStream.objects.create(
        name=name,
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf ist freigegeben.",
        outcome="Bestellung ist ausgelöst.",
        scope_in="Von Bedarf bis Bestellung.",
        created_by=owner,
    )


def _batch(value_stream, owner, suffix="a"):
    analysis_id = uuid4()
    return StructuredAdoptionBatch.objects.create(
        session_id_snapshot=uuid4(),
        analysis_id_snapshot=analysis_id,
        actor_id_snapshot=owner.id,
        target_object_type=StructuredAdoptionBatch.TargetObjectType.VALUE_STREAM,
        target_object_id=value_stream.id,
        source_revision=3,
        interpretation_version="1",
        idempotency_key=suffix * 64,
        selected_graph_hash="f" * 64,
        created_by=owner,
    )


def _confirmed_process_item(
    *,
    batch,
    owner,
    stage_reference,
    values=None,
    depends_on=None,
    edited=False,
):
    process_values = dict(REQUIRED_PROCESS_VALUES if values is None else values)
    decision = (
        StructuredAdoptionItem.Decision.CONFIRMED_EDITED
        if edited
        else StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL
    )
    return StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key="process-01",
        candidate_kind=StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS,
        target_group_key="process-01",
        depends_on=depends_on,
        dependency_key_snapshot=(depends_on.local_key if depends_on is not None else ""),
        proposed_snapshot={"stage_reference": stage_reference.snapshot()},
        interpretation_snapshot={"fields": process_values} if not edited else {},
        decision_snapshot={"edited_fields": process_values} if edited else {},
        source_snapshot={
            "analysis_id": str(batch.analysis_id_snapshot),
            "extraction_schema_version": "1",
            "suggestion_ids": [str(uuid4())],
            "question_ids": ["process_analysis"],
            "excerpt_hashes": ["a" * 64],
        },
        status=StructuredAdoptionItem.Status.CONFIRMED,
        decision=decision,
        confirmed_by=owner,
        confirmed_by_id_snapshot=owner.id,
        confirmed_at=timezone.now(),
    )


def _suggestion(*, batch, target_field, value):
    return SimpleNamespace(
        id=uuid4(),
        analysis_id=batch.analysis_id_snapshot,
        extraction_schema_version="1",
        target_object_type=CaptureFieldSuggestion.TargetObjectType.PROCESS_ANALYSIS,
        target_group_key="process-01",
        target_field=target_field,
        field_type="text",
        suggested_value=value,
        source_question="process_analysis",
        source_excerpt=f"Quelle für {target_field}",
    )


def test_process_suggestions_form_one_catalogued_item(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    batch = _batch(value_stream, owner)
    suggestions = [
        _suggestion(
            batch=batch,
            target_field=f"process_analysis.{field_name}",
            value=value,
        )
        for field_name, value in REQUIRED_PROCESS_VALUES.items()
    ]

    groups = structured_process_adoption.group_process_suggestions(suggestions)

    assert len(groups) == 1
    group = groups[0]
    assert group.local_key == "process-01"
    assert group.values["name"] == "Angebotsprüfung"
    assert group.source_snapshot["analysis_id"] == str(batch.analysis_id_snapshot)
    assert group.source_snapshot["extraction_schema_version"] == "1"
    assert "source_excerpt" not in group.source_snapshot

    defaults = structured_process_adoption.process_item_defaults(
        group,
        stage_reference=structured_process_adoption.StageReference.local("stage-01"),
    )
    assert defaults["candidate_kind"] == StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS
    assert defaults["dependency_key_snapshot"] == "stage-01"
    assert defaults["proposed_snapshot"]["stage_reference"] == {
        "kind": "local",
        "local_key": "stage-01",
    }


def test_process_grouping_rejects_missing_required_field(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    batch = _batch(value_stream, owner)
    incomplete = dict(REQUIRED_PROCESS_VALUES)
    incomplete.pop("bottlenecks")
    suggestions = [
        _suggestion(
            batch=batch,
            target_field=f"process_analysis.{field_name}",
            value=value,
        )
        for field_name, value in incomplete.items()
    ]

    with pytest.raises(structured_process_adoption.StructuredProcessError):
        structured_process_adoption.group_process_suggestions(suggestions)


def test_existing_stage_reference_creates_unvalidated_draft(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    stage = ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Angebot prüfen",
    )
    batch = _batch(value_stream, owner)
    item = _confirmed_process_item(
        batch=batch,
        owner=owner,
        stage_reference=structured_process_adoption.StageReference.existing(stage.id),
    )

    result = structured_process_adoption.adopt_process_item(
        value_stream_id=value_stream.id,
        item=item,
    )

    process = ProcessAnalysis.objects.get(pk=result.process_analysis_id)
    assert process.stage == stage
    assert process.status == ProcessAnalysis.Status.DRAFT
    assert process.analyzed_by == owner
    assert process.validations.count() == 0
    assert process.solution_options.count() == 0
    assert ProcessValidation.objects.count() == 0
    assert SolutionOption.objects.count() == 0
    assert process.source_snapshot["schema"] == "accelerator.process_analysis.v1"
    assert process.source_snapshot["capture"]["revision"] == 3
    assert process.source_snapshot["stage_reference"] == {
        "kind": "existing",
        "stage_id": str(stage.id),
        "resolved_stage_id": str(stage.id),
    }
    item.refresh_from_db()
    assert item.status == StructuredAdoptionItem.Status.ADOPTED
    assert item.created_object_id == process.id


def test_local_stage_reference_resolves_only_adopted_dependency(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    stage = ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Angebot prüfen",
    )
    batch = _batch(value_stream, owner)
    stage_item = StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key="stage-01",
        candidate_kind=StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE,
        target_group_key="stage-01",
        status=StructuredAdoptionItem.Status.ADOPTED,
        decision=StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
        created_object_id=stage.id,
        resolved_at=timezone.now(),
    )
    item = _confirmed_process_item(
        batch=batch,
        owner=owner,
        stage_reference=structured_process_adoption.StageReference.local("stage-01"),
        depends_on=stage_item,
        edited=True,
    )

    result = structured_process_adoption.adopt_process_item(
        value_stream_id=value_stream.id,
        item=item,
    )

    process = ProcessAnalysis.objects.get(pk=result.process_analysis_id)
    assert process.stage == stage
    assert process.status == ProcessAnalysis.Status.DRAFT
    assert process.source_snapshot["stage_reference"] == {
        "kind": "local",
        "local_key": "stage-01",
        "resolved_stage_id": str(stage.id),
    }


def test_local_reference_rejects_unadopted_stage_dependency(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    batch = _batch(value_stream, owner)
    stage_item = StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key="stage-01",
        candidate_kind=StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE,
        target_group_key="stage-01",
        status=StructuredAdoptionItem.Status.CONFIRMED,
        decision=StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
    )
    item = _confirmed_process_item(
        batch=batch,
        owner=owner,
        stage_reference=structured_process_adoption.StageReference.local("stage-01"),
        depends_on=stage_item,
    )

    with pytest.raises(structured_process_adoption.StructuredProcessReferenceError):
        structured_process_adoption.adopt_process_item(
            value_stream_id=value_stream.id,
            item=item,
        )

    assert ProcessAnalysis.objects.count() == 0
    item.refresh_from_db()
    assert item.status == StructuredAdoptionItem.Status.CONFIRMED


def test_existing_stage_from_other_value_stream_is_rejected(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    other_stream = _value_stream(owner, business_unit, name="Vertrieb")
    foreign_stage = ValueStreamStage.objects.create(
        value_stream=other_stream,
        sequence=1,
        name="Anfrage prüfen",
    )
    batch = _batch(value_stream, owner)
    item = _confirmed_process_item(
        batch=batch,
        owner=owner,
        stage_reference=structured_process_adoption.StageReference.existing(foreign_stage.id),
    )

    with pytest.raises(structured_process_adoption.StructuredProcessReferenceError):
        structured_process_adoption.adopt_process_item(
            value_stream_id=value_stream.id,
            item=item,
        )

    assert ProcessAnalysis.objects.count() == 0


def test_process_form_failure_rolls_back_item_and_analysis(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    stage = ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Angebot prüfen",
    )
    batch = _batch(value_stream, owner)
    invalid_values = dict(REQUIRED_PROCESS_VALUES)
    invalid_values["name"] = "X" * 201
    item = _confirmed_process_item(
        batch=batch,
        owner=owner,
        stage_reference=structured_process_adoption.StageReference.existing(stage.id),
        values=invalid_values,
    )

    with pytest.raises(structured_process_adoption.StructuredProcessValidationError) as exc_info:
        structured_process_adoption.adopt_process_item(
            value_stream_id=value_stream.id,
            item=item,
        )

    assert "name" in exc_info.value.errors
    assert ProcessAnalysis.objects.count() == 0
    item.refresh_from_db()
    assert item.status == StructuredAdoptionItem.Status.CONFIRMED
    assert item.created_object_id is None
