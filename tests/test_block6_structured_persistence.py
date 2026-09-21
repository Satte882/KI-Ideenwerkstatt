from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
from ki_radar.accelerator.structured_models import (
    StructuredAdoptionAudit,
    StructuredAdoptionBatch,
    StructuredAdoptionItem,
)

pytestmark = pytest.mark.django_db


_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _session(owner):
    return CaptureSession.objects.create(
        owner=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        catalog_version="1",
        schema_version="1",
        expires_at=timezone.now() + timedelta(days=1),
    )


def _analysis(session, owner):
    return CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=0,
        source_hash=_HASH_A,
        capture_type=session.capture_type,
        catalog_version="1",
        answer_schema_version="1",
        prompt_version="1",
        extraction_schema_version="1",
        finished_at=timezone.now(),
    )


def _batch(session, analysis, owner):
    return StructuredAdoptionBatch.objects.create(
        session=session,
        analysis=analysis,
        created_by=owner,
        session_id_snapshot=session.id,
        analysis_id_snapshot=analysis.id,
        actor_id_snapshot=owner.id,
        target_object_type=StructuredAdoptionBatch.TargetObjectType.USE_CASE,
        target_object_id=session.id,
        source_revision=analysis.source_revision,
        interpretation_version="1",
        idempotency_key=_HASH_A,
        selected_graph_hash=_HASH_B,
    )


def test_batch_idempotency_key_is_unique(owner):
    session = _session(owner)
    analysis = _analysis(session, owner)
    _batch(session, analysis, owner)

    with pytest.raises(IntegrityError), transaction.atomic():
        _batch(session, analysis, owner)


def test_item_local_key_is_unique_per_batch(owner):
    session = _session(owner)
    analysis = _analysis(session, owner)
    batch = _batch(session, analysis, owner)
    StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key="metric-baseline",
        candidate_kind=StructuredAdoptionItem.CandidateKind.METRIC_SET,
        target_path="use_case.metric.baseline",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        StructuredAdoptionItem.objects.create(
            batch=batch,
            local_key="metric-baseline",
            candidate_kind=StructuredAdoptionItem.CandidateKind.METRIC_SET,
            target_path="use_case.metric.target",
        )


def test_dependency_must_stay_inside_batch(owner):
    first_session = _session(owner)
    first_analysis = _analysis(first_session, owner)
    first_batch = _batch(first_session, first_analysis, owner)

    second_session = _session(owner)
    second_analysis = _analysis(second_session, owner)
    second_analysis.source_hash = _HASH_B
    second_analysis.save(update_fields=["source_hash"])
    second_batch = StructuredAdoptionBatch.objects.create(
        session=second_session,
        analysis=second_analysis,
        created_by=owner,
        session_id_snapshot=second_session.id,
        analysis_id_snapshot=second_analysis.id,
        actor_id_snapshot=owner.id,
        target_object_type=StructuredAdoptionBatch.TargetObjectType.USE_CASE,
        target_object_id=second_session.id,
        source_revision=0,
        interpretation_version="1",
        idempotency_key="c" * 64,
        selected_graph_hash="d" * 64,
    )
    stage = StructuredAdoptionItem.objects.create(
        batch=first_batch,
        local_key="stage-01",
        candidate_kind=StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE,
    )
    process = StructuredAdoptionItem(
        batch=second_batch,
        local_key="process-01",
        candidate_kind=StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS,
        depends_on=stage,
        dependency_key_snapshot=stage.local_key,
    )

    with pytest.raises(ValidationError):
        process.full_clean()


def test_capture_deletion_retains_batch_items_and_audit(owner):
    session = _session(owner)
    analysis = _analysis(session, owner)
    batch = _batch(session, analysis, owner)
    item = StructuredAdoptionItem.objects.create(
        batch=batch,
        local_key="metric-type",
        candidate_kind=StructuredAdoptionItem.CandidateKind.METRIC_SET,
        target_path="use_case.metric.type",
        source_snapshot={"question_ids": ["metric"], "excerpt_hashes": [_HASH_B]},
    )
    audit = StructuredAdoptionAudit.objects.create(
        batch=batch,
        item=item,
        actor=owner,
        batch_id_snapshot=batch.id,
        item_id_snapshot=item.id,
        session_id_snapshot=session.id,
        analysis_id_snapshot=analysis.id,
        actor_id_snapshot=owner.id,
        target_object_type=batch.target_object_type,
        target_object_id=batch.target_object_id,
        idempotency_key=batch.idempotency_key,
        event=StructuredAdoptionAudit.Event.CREATED,
        outcome="stored",
    )

    session.delete()

    batch.refresh_from_db()
    assert batch.session is None
    assert batch.analysis is None
    assert StructuredAdoptionItem.objects.filter(pk=item.pk).exists()
    assert StructuredAdoptionAudit.objects.filter(pk=audit.pk).exists()


def test_persistence_models_do_not_duplicate_capture_raw_data():
    forbidden_fields = {
        "answers",
        "provider_response",
        "source_excerpt",
        "raw_response",
    }
    for model in (
        StructuredAdoptionBatch,
        StructuredAdoptionItem,
        StructuredAdoptionAudit,
    ):
        field_names = {field.name for field in model._meta.fields}
        assert forbidden_fields.isdisjoint(field_names)
