from __future__ import annotations

from decimal import Decimal
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
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage
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


def _batch(*, target, owner, target_type, placeholder="a"):
    return StructuredAdoptionBatch.objects.create(
        session_id_snapshot=uuid4(),
        analysis_id_snapshot=uuid4(),
        actor_id_snapshot=owner.id,
        target_object_type=target_type,
        target_object_id=target.id,
        source_revision=1,
        interpretation_version="1",
        idempotency_key=placeholder * 64,
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


def _confirmed_metric_item(*, batch, owner, use_case):
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


def _confirmed_stage_item(*, batch, owner):
    return StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key="stage-01",
        candidate_kind=StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE,
        target_group_key="stage-01",
        proposed_snapshot={
            "fields": {
                "sequence": 1,
                "name": "Angebot prüfen",
                "description": "Angebote werden formal geprüft.",
                "actors": "Einkauf",
                "systems": "ERP",
                "documents": "Angebote",
                "pain_points": "Manueller Vergleich",
                "baseline_metrics": "11 Minuten",
            }
        },
        interpretation_snapshot={
            "fields": {
                "sequence": 1,
                "name": "Angebot prüfen",
                "description": "Angebote werden formal geprüft.",
                "actors": "Einkauf",
                "systems": "ERP",
                "documents": "Angebote",
                "pain_points": "Manueller Vergleich",
                "baseline_metrics": "11 Minuten",
            }
        },
        status=StructuredAdoptionItem.Status.CONFIRMED,
        decision=StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
        confirmed_by=owner,
        confirmed_by_id_snapshot=owner.id,
        confirmed_at=timezone.now(),
    )


def _confirmed_process_item(*, batch, owner, stage_item):
    return StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key="process-01",
        candidate_kind=StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS,
        target_group_key="process-01",
        depends_on=stage_item,
        dependency_key_snapshot=stage_item.local_key,
        proposed_snapshot={
            "stage_reference": {
                "kind": structured_process_adoption.StageReferenceKind.LOCAL,
                "local_key": stage_item.local_key,
            }
        },
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


def _value_stream_graph(owner, business_unit, placeholder="b"):
    value_stream = _value_stream(owner, business_unit)
    batch = _batch(
        target=value_stream,
        owner=owner,
        target_type=StructuredAdoptionBatch.TargetObjectType.VALUE_STREAM,
        placeholder=placeholder,
    )
    stage_item = _confirmed_stage_item(batch=batch, owner=owner)
    process_item = _confirmed_process_item(
        batch=batch,
        owner=owner,
        stage_item=stage_item,
    )
    key = _seal_batch(batch)
    return value_stream, batch, stage_item, process_item, key


def test_use_case_group_commits_and_replays_idempotently(owner, business_unit):
    use_case = _use_case(owner, business_unit)
    batch = _batch(
        target=use_case,
        owner=owner,
        target_type=StructuredAdoptionBatch.TargetObjectType.USE_CASE,
    )
    item = _confirmed_metric_item(batch=batch, owner=owner, use_case=use_case)
    key = _seal_batch(batch)

    result = structured_adoption_orchestrator.commit_structured_batch(
        batch_id=batch.id,
        actor=owner,
        idempotency_key=key,
    )
    replay = structured_adoption_orchestrator.commit_structured_batch(
        batch_id=batch.id,
        actor=owner,
        idempotency_key=key,
    )

    use_case.refresh_from_db()
    batch.refresh_from_db()
    item.refresh_from_db()
    assert use_case.metric_baseline == Decimal("12")
    assert batch.status == StructuredAdoptionBatch.Status.COMMITTED
    assert batch.attempt_count == 1
    assert item.status == StructuredAdoptionItem.Status.ADOPTED
    assert result.outcome == structured_adoption_orchestrator.StructuredCommitOutcome.COMMITTED
    assert replay.outcome == structured_adoption_orchestrator.StructuredCommitOutcome.REPLAYED
    assert replay.result_snapshot == result.result_snapshot
    assert (
        StructuredAdoptionAudit.objects.filter(
            batch=batch,
            event=StructuredAdoptionAudit.Event.COMMITTED,
        ).count()
        == 1
    )


def test_value_stream_group_creates_stage_and_process_once(owner, business_unit):
    value_stream, batch, stage_item, process_item, key = _value_stream_graph(
        owner,
        business_unit,
    )

    first = structured_adoption_orchestrator.commit_structured_batch(
        batch_id=batch.id,
        actor=owner,
        idempotency_key=key,
    )
    second = structured_adoption_orchestrator.commit_structured_batch(
        batch_id=batch.id,
        actor=owner,
        idempotency_key=key,
    )

    batch.refresh_from_db()
    stage_item.refresh_from_db()
    process_item.refresh_from_db()
    process = ProcessAnalysis.objects.get(pk=process_item.created_object_id)
    assert batch.status == StructuredAdoptionBatch.Status.COMMITTED
    assert batch.attempt_count == 1
    assert ValueStreamStage.objects.filter(value_stream=value_stream).count() == 1
    assert ProcessAnalysis.objects.filter(stage__value_stream=value_stream).count() == 1
    assert stage_item.status == StructuredAdoptionItem.Status.ADOPTED
    assert process_item.status == StructuredAdoptionItem.Status.ADOPTED
    assert process.status == ProcessAnalysis.Status.DRAFT
    assert second.outcome == structured_adoption_orchestrator.StructuredCommitOutcome.REPLAYED
    assert second.result_snapshot == first.result_snapshot


def test_process_failure_rolls_back_stage_and_retry_is_safe(
    owner,
    business_unit,
    monkeypatch,
):
    value_stream, batch, stage_item, process_item, key = _value_stream_graph(
        owner,
        business_unit,
        placeholder="c",
    )
    original = structured_adoption_orchestrator.structured_process_adoption.adopt_process_item

    def fail_process(*, value_stream_id, item):
        raise RuntimeError("simulierter Fehler nach Phasenanlage")

    monkeypatch.setattr(
        structured_adoption_orchestrator.structured_process_adoption,
        "adopt_process_item",
        fail_process,
    )
    with pytest.raises(structured_adoption_orchestrator.StructuredCommitError):
        structured_adoption_orchestrator.commit_structured_batch(
            batch_id=batch.id,
            actor=owner,
            idempotency_key=key,
        )

    batch.refresh_from_db()
    stage_item.refresh_from_db()
    process_item.refresh_from_db()
    assert batch.status == StructuredAdoptionBatch.Status.FAILED
    assert batch.attempt_count == 1
    assert ValueStreamStage.objects.filter(value_stream=value_stream).count() == 0
    assert ProcessAnalysis.objects.filter(stage__value_stream=value_stream).count() == 0
    assert stage_item.status == StructuredAdoptionItem.Status.CONFIRMED
    assert stage_item.created_object_id is None
    assert process_item.status == StructuredAdoptionItem.Status.CONFIRMED
    audit = StructuredAdoptionAudit.objects.get(
        batch=batch,
        event=StructuredAdoptionAudit.Event.FAILED,
    )
    assert audit.step == "process_analysis"
    assert audit.item_local_key == "process-01"
    assert audit.error_code == "domain_validation_failed"

    monkeypatch.setattr(
        structured_adoption_orchestrator.structured_process_adoption,
        "adopt_process_item",
        original,
    )
    result = structured_adoption_orchestrator.commit_structured_batch(
        batch_id=batch.id,
        actor=owner,
        idempotency_key=key,
    )

    batch.refresh_from_db()
    assert result.outcome == structured_adoption_orchestrator.StructuredCommitOutcome.COMMITTED
    assert batch.status == StructuredAdoptionBatch.Status.COMMITTED
    assert batch.attempt_count == 2
    assert ValueStreamStage.objects.filter(value_stream=value_stream).count() == 1
    assert ProcessAnalysis.objects.filter(stage__value_stream=value_stream).count() == 1


def test_foreign_business_owner_cannot_reserve_batch(owner, other_owner, business_unit):
    use_case = _use_case(owner, business_unit)
    batch = _batch(
        target=use_case,
        owner=owner,
        target_type=StructuredAdoptionBatch.TargetObjectType.USE_CASE,
        placeholder="d",
    )
    _confirmed_metric_item(batch=batch, owner=owner, use_case=use_case)
    key = _seal_batch(batch)

    with pytest.raises(structured_adoption_orchestrator.StructuredCommitPermissionDenied):
        structured_adoption_orchestrator.commit_structured_batch(
            batch_id=batch.id,
            actor=other_owner,
            idempotency_key=key,
        )

    batch.refresh_from_db()
    assert batch.status == StructuredAdoptionBatch.Status.OPEN
    assert batch.attempt_count == 0


def test_changed_item_graph_fails_before_domain_write(owner, business_unit):
    use_case = _use_case(owner, business_unit)
    batch = _batch(
        target=use_case,
        owner=owner,
        target_type=StructuredAdoptionBatch.TargetObjectType.USE_CASE,
        placeholder="e",
    )
    item = _confirmed_metric_item(batch=batch, owner=owner, use_case=use_case)
    key = _seal_batch(batch)
    item.interpretation_snapshot = {"value": "14"}
    item.save(update_fields=["interpretation_snapshot", "updated_at"])

    with pytest.raises(structured_adoption_orchestrator.StructuredCommitError) as exc_info:
        structured_adoption_orchestrator.commit_structured_batch(
            batch_id=batch.id,
            actor=owner,
            idempotency_key=key,
        )

    use_case.refresh_from_db()
    batch.refresh_from_db()
    assert exc_info.value.error_code == "selected_graph_changed"
    assert use_case.metric_baseline == Decimal("10")
    assert batch.status == StructuredAdoptionBatch.Status.FAILED
    audit = StructuredAdoptionAudit.objects.get(batch=batch)
    assert audit.step == "revalidation"
    assert audit.error_code == "selected_graph_changed"


def test_processing_batch_is_not_reentered(owner, business_unit):
    use_case = _use_case(owner, business_unit)
    batch = _batch(
        target=use_case,
        owner=owner,
        target_type=StructuredAdoptionBatch.TargetObjectType.USE_CASE,
        placeholder="f",
    )
    _confirmed_metric_item(batch=batch, owner=owner, use_case=use_case)
    key = _seal_batch(batch)
    batch.status = StructuredAdoptionBatch.Status.PROCESSING
    batch.processing_by = owner
    batch.processing_started_at = timezone.now()
    batch.attempt_count = 1
    batch.save(
        update_fields=[
            "status",
            "processing_by",
            "processing_started_at",
            "attempt_count",
            "updated_at",
        ]
    )

    with pytest.raises(structured_adoption_orchestrator.StructuredBatchBusy):
        structured_adoption_orchestrator.commit_structured_batch(
            batch_id=batch.id,
            actor=owner,
            idempotency_key=key,
        )

    batch.refresh_from_db()
    assert batch.status == StructuredAdoptionBatch.Status.PROCESSING
    assert batch.attempt_count == 1


def test_lock_order_is_fixed():
    assert structured_adoption_orchestrator.LOCK_ORDER[:4] == (
        "batch",
        "root_target",
        "existing_stages",
        "items",
    )
