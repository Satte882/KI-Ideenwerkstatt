"""Regression tests for Block 6 security, rollback, gate, and responsive layout invariants."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from django.utils import timezone

from ki_radar.accelerator import (
    structured_adoption_orchestrator,
    structured_process_adoption,
)
from ki_radar.accelerator.structured_models import (
    StructuredAdoptionAudit,
    StructuredAdoptionBatch,
    StructuredAdoptionItem,
)
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.use_cases.models import UseCase

pytestmark = pytest.mark.django_db


PROCESS_VALUES = {
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


def _use_case(owner, business_unit):
    return UseCase.objects.create(
        title="Rechnungsprüfung beschleunigen",
        problem_statement="Die Prüfung dauert zu lange.",
        business_unit=business_unit,
        affected_process="Rechnungsprüfung",
        business_owner=owner,
        submitter=owner,
        expected_benefit="Kürzere Bearbeitungszeit",
        metric_name="Bearbeitungszeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="min",
        metric_baseline=Decimal("10"),
        metric_target=Decimal("8"),
        metric_measurement_method="Zeitmessung in 20 Fällen",
    )


def _value_stream(owner, business_unit, *, name="Beschaffung"):
    return ValueStream.objects.create(
        name=name,
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf ist freigegeben.",
        outcome="Bestellung ist ausgelöst.",
        scope_in="Von Bedarf bis Bestellung.",
        created_by=owner,
    )


def _batch(*, target, owner, target_type, marker):
    return StructuredAdoptionBatch.objects.create(
        session_id_snapshot=uuid4(),
        analysis_id_snapshot=uuid4(),
        actor_id_snapshot=owner.id,
        target_object_type=target_type,
        target_object_id=target.id,
        source_revision=1,
        interpretation_version="1",
        idempotency_key=marker * 64,
        selected_graph_hash="f" * 64,
        created_by=owner,
    )


def _seal_batch(batch):
    items = tuple(batch.items.order_by("local_key", "id"))
    graph_hash = structured_adoption_orchestrator.build_selected_graph_hash(items)
    idempotency_key = structured_adoption_orchestrator.build_idempotency_key(
        session_id=batch.session_id_snapshot,
        analysis_id=batch.analysis_id_snapshot,
        target_object_type=batch.target_object_type,
        target_object_id=batch.target_object_id,
        selected_graph_hash=graph_hash,
        interpretation_version=batch.interpretation_version,
    )
    batch.selected_graph_hash = graph_hash
    batch.idempotency_key = idempotency_key
    batch.save(update_fields=["selected_graph_hash", "idempotency_key", "updated_at"])
    return idempotency_key


def _metric_item(*, batch, owner, use_case):
    return StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key="metric-baseline",
        candidate_kind=StructuredAdoptionItem.CandidateKind.METRIC_SET,
        target_path="use_case.metric.baseline",
        interpretation_snapshot={"value": "12"},
        field_snapshot={
            "hash": structured_adoption_orchestrator.structured_metric_adoption.metric_value_hash(
                use_case.metric_baseline
            )
        },
        status=StructuredAdoptionItem.Status.CONFIRMED,
        decision=StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
        confirmed_by=owner,
        confirmed_by_id_snapshot=owner.id,
        confirmed_at=timezone.now(),
    )


def _stage_item(*, batch, owner, local_key="stage-01", sequence=1):
    fields = {
        "sequence": sequence,
        "name": "Angebot prüfen",
        "description": "Angebote werden formal geprüft.",
        "actors": "Einkauf",
        "systems": "ERP",
        "documents": "Angebote",
        "pain_points": "Manueller Vergleich",
        "baseline_metrics": "11 Minuten",
    }
    return StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key=local_key,
        candidate_kind=StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE,
        target_group_key=local_key,
        proposed_snapshot={"fields": fields},
        interpretation_snapshot={"fields": fields},
        status=StructuredAdoptionItem.Status.CONFIRMED,
        decision=StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
        confirmed_by=owner,
        confirmed_by_id_snapshot=owner.id,
        confirmed_at=timezone.now(),
    )


def _process_item(
    *,
    batch,
    owner,
    local_key="process-01",
    stage_item=None,
    existing_stage=None,
):
    if stage_item is not None:
        reference = {
            "kind": structured_process_adoption.StageReferenceKind.LOCAL,
            "local_key": stage_item.local_key,
        }
        dependency_key = stage_item.local_key
    else:
        reference = {
            "kind": structured_process_adoption.StageReferenceKind.EXISTING,
            "stage_id": str(existing_stage.id),
        }
        dependency_key = ""
    return StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key=local_key,
        candidate_kind=StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS,
        target_group_key=local_key,
        depends_on=stage_item,
        dependency_key_snapshot=dependency_key,
        proposed_snapshot={"stage_reference": reference},
        interpretation_snapshot={"fields": PROCESS_VALUES},
        source_snapshot={
            "analysis_id": str(batch.analysis_id_snapshot),
            "extraction_schema_version": "1",
            "suggestion_ids": [str(uuid4())],
            "question_ids": ["process_analysis"],
            "excerpt_hashes": ["a" * 64],
        },
        status=StructuredAdoptionItem.Status.CONFIRMED,
        decision=StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
        confirmed_by=owner,
        confirmed_by_id_snapshot=owner.id,
        confirmed_at=timezone.now(),
    )


def _value_stream_graph(
    owner,
    business_unit,
    *,
    value_stream=None,
    marker="a",
    sequence=1,
):
    value_stream = value_stream or _value_stream(owner, business_unit)
    batch = _batch(
        target=value_stream,
        owner=owner,
        target_type=StructuredAdoptionBatch.TargetObjectType.VALUE_STREAM,
        marker=marker,
    )
    stage_item = _stage_item(
        batch=batch,
        owner=owner,
        local_key=f"stage-{marker}",
        sequence=sequence,
    )
    process_item = _process_item(
        batch=batch,
        owner=owner,
        local_key=f"process-{marker}",
        stage_item=stage_item,
    )
    key = _seal_batch(batch)
    return value_stream, batch, stage_item, process_item, key


def _commit(*, batch, owner, key):
    return structured_adoption_orchestrator.commit_structured_batch(
        batch_id=batch.id,
        actor=owner,
        idempotency_key=key,
    )


def test_use_case_metric_commit_preserves_red_gate_state(owner, business_unit):
    use_case = _use_case(owner, business_unit)
    original_gate_state = {
        "status": use_case.status,
        "decision_status": use_case.decision_status,
        "priority": use_case.priority,
        "pilot_start": use_case.pilot_start,
        "planned_pilot_end": use_case.planned_pilot_end,
        "privacy_review_completed": use_case.privacy_review_completed,
        "security_review_completed": use_case.security_review_completed,
        "legal_review_completed": use_case.legal_review_completed,
    }
    batch = _batch(
        target=use_case,
        owner=owner,
        target_type=StructuredAdoptionBatch.TargetObjectType.USE_CASE,
        marker="u",
    )
    _metric_item(batch=batch, owner=owner, use_case=use_case)
    key = _seal_batch(batch)

    _commit(batch=batch, owner=owner, key=key)

    use_case.refresh_from_db()
    assert use_case.metric_baseline == Decimal("12")
    assert {
        "status": use_case.status,
        "decision_status": use_case.decision_status,
        "priority": use_case.priority,
        "pilot_start": use_case.pilot_start,
        "planned_pilot_end": use_case.planned_pilot_end,
        "privacy_review_completed": use_case.privacy_review_completed,
        "security_review_completed": use_case.security_review_completed,
        "legal_review_completed": use_case.legal_review_completed,
    } == original_gate_state


def test_value_stream_commit_creates_only_unvalidated_drafts(owner, business_unit):
    value_stream, batch, _, process_item, key = _value_stream_graph(
        owner,
        business_unit,
        marker="g",
    )
    original_status = value_stream.status

    _commit(batch=batch, owner=owner, key=key)

    value_stream.refresh_from_db()
    process_item.refresh_from_db()
    process = ProcessAnalysis.objects.get(pk=process_item.created_object_id)
    assert value_stream.status == original_status == ValueStream.Status.DRAFT
    assert process.status == ProcessAnalysis.Status.DRAFT
    assert ProcessValidation.objects.filter(process_analysis=process).count() == 0
    assert SolutionOption.objects.filter(process_analysis=process).count() == 0
    assert SolutionSelectionDecision.objects.filter(process_analysis=process).count() == 0


@pytest.mark.parametrize("failure_point", ["success_audit", "batch_completion"])
def test_terminal_failures_roll_back_complete_value_stream_graph(
    owner,
    business_unit,
    monkeypatch,
    failure_point,
):
    value_stream, batch, stage_item, process_item, key = _value_stream_graph(
        owner,
        business_unit,
        marker="r" if failure_point == "success_audit" else "s",
    )

    if failure_point == "success_audit":

        def fail_success_audit(**kwargs):
            raise RuntimeError("simulierter Fehler beim Erfolgs-Audit")

        monkeypatch.setattr(
            structured_adoption_orchestrator,
            "_record_success_audit",
            fail_success_audit,
        )
    else:
        original_save = StructuredAdoptionBatch.save

        def fail_committed_save(self, *args, **kwargs):
            if self.status == StructuredAdoptionBatch.Status.COMMITTED:
                raise RuntimeError("simulierter Fehler beim Batchabschluss")
            return original_save(self, *args, **kwargs)

        monkeypatch.setattr(StructuredAdoptionBatch, "save", fail_committed_save)

    with pytest.raises(structured_adoption_orchestrator.StructuredCommitError):
        _commit(batch=batch, owner=owner, key=key)

    batch.refresh_from_db()
    stage_item.refresh_from_db()
    process_item.refresh_from_db()
    assert batch.status == StructuredAdoptionBatch.Status.FAILED
    assert ValueStreamStage.objects.filter(value_stream=value_stream).count() == 0
    assert ProcessAnalysis.objects.filter(stage__value_stream=value_stream).count() == 0
    assert stage_item.status == StructuredAdoptionItem.Status.CONFIRMED
    assert stage_item.created_object_id is None
    assert process_item.status == StructuredAdoptionItem.Status.CONFIRMED
    assert process_item.created_object_id is None
    failure_audit = StructuredAdoptionAudit.objects.get(
        batch=batch,
        event=StructuredAdoptionAudit.Event.FAILED,
    )
    assert failure_audit.error_code == "unexpected_commit_failure"


def test_foreign_existing_stage_reference_fails_closed(owner, business_unit):
    target_stream = _value_stream(owner, business_unit, name="Zielprozess")
    foreign_stream = _value_stream(owner, business_unit, name="Fremdprozess")
    foreign_stage = ValueStreamStage.objects.create(
        value_stream=foreign_stream,
        sequence=1,
        name="Fremde Phase",
    )
    batch = _batch(
        target=target_stream,
        owner=owner,
        target_type=StructuredAdoptionBatch.TargetObjectType.VALUE_STREAM,
        marker="f",
    )
    _process_item(
        batch=batch,
        owner=owner,
        existing_stage=foreign_stage,
    )
    key = _seal_batch(batch)

    with pytest.raises(structured_adoption_orchestrator.StructuredCommitError) as exc_info:
        _commit(batch=batch, owner=owner, key=key)

    batch.refresh_from_db()
    assert exc_info.value.step == "process_analysis"
    assert batch.status == StructuredAdoptionBatch.Status.FAILED
    assert ValueStreamStage.objects.filter(value_stream=target_stream).count() == 0
    assert ProcessAnalysis.objects.filter(stage__value_stream=target_stream).count() == 0
    assert ProcessAnalysis.objects.filter(stage=foreign_stage).count() == 0


def test_deleted_root_target_fails_before_reservation(owner, business_unit):
    value_stream, batch, _, _, key = _value_stream_graph(
        owner,
        business_unit,
        marker="d",
    )
    value_stream.delete()

    with pytest.raises(structured_adoption_orchestrator.StructuredCommitError) as exc_info:
        _commit(batch=batch, owner=owner, key=key)

    batch.refresh_from_db()
    assert exc_info.value.error_code == "target_missing"
    assert batch.status == StructuredAdoptionBatch.Status.OPEN
    assert batch.attempt_count == 0


def test_manipulated_dependency_key_is_rejected_before_domain_write(owner, business_unit):
    value_stream, batch, _, process_item, _ = _value_stream_graph(
        owner,
        business_unit,
        marker="m",
    )
    process_item.dependency_key_snapshot = "stage-manipulated"
    process_item.save(update_fields=["dependency_key_snapshot", "updated_at"])
    key = _seal_batch(batch)

    with pytest.raises(structured_adoption_orchestrator.StructuredCommitError) as exc_info:
        _commit(batch=batch, owner=owner, key=key)

    batch.refresh_from_db()
    assert exc_info.value.error_code == "dependency_key_mismatch"
    assert batch.status == StructuredAdoptionBatch.Status.FAILED
    assert ValueStreamStage.objects.filter(value_stream=value_stream).count() == 0
    assert ProcessAnalysis.objects.filter(stage__value_stream=value_stream).count() == 0


def test_competing_batches_cannot_duplicate_sequence_or_process(owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    _, first_batch, _, _, first_key = _value_stream_graph(
        owner,
        business_unit,
        value_stream=value_stream,
        marker="1",
        sequence=1,
    )
    _, second_batch, second_stage, second_process, second_key = _value_stream_graph(
        owner,
        business_unit,
        value_stream=value_stream,
        marker="2",
        sequence=1,
    )

    _commit(batch=first_batch, owner=owner, key=first_key)
    with pytest.raises(structured_adoption_orchestrator.StructuredCommitError) as exc_info:
        _commit(batch=second_batch, owner=owner, key=second_key)

    second_batch.refresh_from_db()
    second_stage.refresh_from_db()
    second_process.refresh_from_db()
    assert exc_info.value.step == "value_stream_stages"
    assert second_batch.status == StructuredAdoptionBatch.Status.CONFLICT
    assert ValueStreamStage.objects.filter(value_stream=value_stream).count() == 1
    assert ProcessAnalysis.objects.filter(stage__value_stream=value_stream).count() == 1
    assert second_stage.status == StructuredAdoptionItem.Status.CONFIRMED
    assert second_stage.created_object_id is None
    assert second_process.status == StructuredAdoptionItem.Status.CONFIRMED
    assert second_process.created_object_id is None


def test_structured_review_is_responsive_without_horizontal_overflow():
    template = (
        Path(__file__).resolve().parents[1] / "templates" / "accelerator" / "structured_review.html"
    ).read_text(encoding="utf-8")

    assert "<table" not in template
    assert "overflow-x" not in template
    assert "white-space: nowrap" not in template
    assert "min-width:" not in template
    assert "d-flex" in template
    assert "flex-wrap" in template
    assert "row g-3" in template
    assert "text-break" in template
    assert "col-lg-4" in template
    assert "col-md-4" in template
