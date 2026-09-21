from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from ki_radar.accelerator.candidate_snapshot import create_adoption_candidates
from ki_radar.accelerator.candidate_state import (
    CandidateTransitionError,
    complete_candidate,
    reserve_candidate,
)
from ki_radar.accelerator.catalogs import ANSWER_SCHEMA_VERSION, CATALOG_VERSION_V1
from ki_radar.accelerator.extraction_contract import (
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SCHEMA_VERSION,
)
from ki_radar.accelerator.models import (
    CaptureAnalysis,
    CaptureFieldSuggestion,
    CaptureSession,
    FieldAdoptionCandidate,
)
from ki_radar.accelerator.services import create_capture_session
from ki_radar.accelerator.target_binding import bind_capture_target
from ki_radar.architecture.models import ValueStream


def make_value_stream(*, business_unit, owner):
    return ValueStream.objects.create(
        name="Beschaffung",
        business_unit=business_unit,
        owner=owner,
        status=ValueStream.Status.ACTIVE,
        trigger="Bedarf entsteht",
        outcome="Bestellung ist ausgelöst",
        scope_in="Bedarf bis Bestellung",
        created_by=owner,
    )


def make_analysis(*, session, actor, source_hash, field_name="name", value="Neuer Name"):
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=actor,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=session.revision,
        source_hash=source_hash,
        capture_type=session.capture_type,
        catalog_version=CATALOG_VERSION_V1,
        answer_schema_version=ANSWER_SCHEMA_VERSION,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
        finished_at=timezone.now(),
    )
    CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=session.capture_type,
        target_field=field_name,
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value=value,
        source_question="identity",
        source_excerpt=value,
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Direkte Aussage",
    )
    return analysis


def make_candidate(*, actor, business_unit, field_name="name", value="Neuer Name"):
    target = make_value_stream(business_unit=business_unit, owner=actor)
    session = create_capture_session(
        actor=actor,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    bind_capture_target(actor=actor, session_id=session.pk, target_id=target.pk)
    session.status = CaptureSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.expires_at = timezone.now() + timedelta(days=90)
    session.save(update_fields=["status", "completed_at", "expires_at", "updated_at"])
    analysis = make_analysis(
        session=session,
        actor=actor,
        source_hash="a" * 64,
        field_name=field_name,
        value=value,
    )
    return create_adoption_candidates(analysis_id=analysis.pk)[0], session, target


@pytest.mark.django_db
def test_reservation_is_atomic_compare_and_swap(owner, business_unit):
    candidate, _session, _target = make_candidate(
        actor=owner,
        business_unit=business_unit,
    )

    first = reserve_candidate(candidate_id=candidate.pk, actor=owner)
    second = reserve_candidate(candidate_id=candidate.pk, actor=owner)

    assert first.acquired is True
    assert first.candidate.status == FieldAdoptionCandidate.Status.PROCESSING
    assert first.candidate.processing_by == owner
    assert first.candidate.processing_started_at is not None
    assert second.acquired is False
    assert second.candidate.status == FieldAdoptionCandidate.Status.PROCESSING


@pytest.mark.django_db
def test_terminal_completion_is_idempotent(owner, business_unit):
    candidate, _session, _target = make_candidate(
        actor=owner,
        business_unit=business_unit,
    )
    reserve_candidate(candidate_id=candidate.pk, actor=owner)

    first = complete_candidate(
        candidate_id=candidate.pk,
        actor=owner,
        status=FieldAdoptionCandidate.Status.REJECTED,
    )
    second = complete_candidate(
        candidate_id=candidate.pk,
        actor=owner,
        status=FieldAdoptionCandidate.Status.REJECTED,
    )

    assert first.status == FieldAdoptionCandidate.Status.REJECTED
    assert first.resolved_at is not None
    assert second.pk == first.pk
    with pytest.raises(CandidateTransitionError):
        complete_candidate(
            candidate_id=candidate.pk,
            actor=owner,
            status=FieldAdoptionCandidate.Status.FAILED,
        )


@pytest.mark.django_db
def test_wrong_actor_cannot_complete_reservation(owner, other_owner, business_unit):
    candidate, _session, _target = make_candidate(
        actor=owner,
        business_unit=business_unit,
    )
    reserve_candidate(candidate_id=candidate.pk, actor=owner)

    with pytest.raises(CandidateTransitionError):
        complete_candidate(
            candidate_id=candidate.pk,
            actor=other_owner,
            status=FieldAdoptionCandidate.Status.REJECTED,
        )

    candidate.refresh_from_db()
    assert candidate.status == FieldAdoptionCandidate.Status.PROCESSING


@pytest.mark.django_db
def test_terminal_candidate_cannot_be_reserved_again(owner, business_unit):
    candidate, _session, _target = make_candidate(
        actor=owner,
        business_unit=business_unit,
    )
    reserve_candidate(candidate_id=candidate.pk, actor=owner)
    complete_candidate(
        candidate_id=candidate.pk,
        actor=owner,
        status=FieldAdoptionCandidate.Status.REJECTED,
    )

    repeated = reserve_candidate(candidate_id=candidate.pk, actor=owner)

    assert repeated.acquired is False
    assert repeated.candidate.status == FieldAdoptionCandidate.Status.REJECTED


@pytest.mark.django_db
def test_new_candidate_supersedes_older_open_candidate(owner, business_unit):
    first, session, target = make_candidate(
        actor=owner,
        business_unit=business_unit,
        value="Erster Vorschlag",
    )
    second_analysis = make_analysis(
        session=session,
        actor=owner,
        source_hash="b" * 64,
        value="Zweiter Vorschlag",
    )

    second = create_adoption_candidates(analysis_id=second_analysis.pk)[0]

    first.refresh_from_db()
    assert first.status == FieldAdoptionCandidate.Status.SUPERSEDED
    assert first.resolved_at is not None
    assert first.error_code == "superseded_by_new_candidate"
    assert second.status == FieldAdoptionCandidate.Status.OPEN
    assert second.target_object_id == target.pk
    assert (
        FieldAdoptionCandidate.objects.filter(
            target_object_id=target.pk,
            target_field="name",
            status=FieldAdoptionCandidate.Status.OPEN,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_new_field_does_not_supersede_other_open_field(owner, business_unit):
    first, session, _target = make_candidate(
        actor=owner,
        business_unit=business_unit,
        field_name="name",
    )
    second_analysis = make_analysis(
        session=session,
        actor=owner,
        source_hash="c" * 64,
        field_name="description",
        value="Neue Beschreibung",
    )

    second = create_adoption_candidates(analysis_id=second_analysis.pk)[0]

    first.refresh_from_db()
    assert first.status == FieldAdoptionCandidate.Status.OPEN
    assert second.status == FieldAdoptionCandidate.Status.OPEN


@pytest.mark.django_db
def test_database_allows_only_one_open_candidate_per_target_field(owner, business_unit):
    candidate, _session, _target = make_candidate(
        actor=owner,
        business_unit=business_unit,
    )
    other_suggestion = CaptureFieldSuggestion.objects.create(
        analysis=candidate.suggestion.analysis,
        target_object_type=candidate.target_object_type,
        target_field="name_duplicate",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Doppelt",
        source_question="identity",
        source_excerpt="Doppelt",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Direkte Aussage",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        FieldAdoptionCandidate.objects.create(
            suggestion=other_suggestion,
            target_object_type=candidate.target_object_type,
            target_object_id=candidate.target_object_id,
            target_field=candidate.target_field,
            proposed_value="Doppelt",
            previous_value=candidate.previous_value,
            previous_value_hash=candidate.previous_value_hash,
            target_updated_at=candidate.target_updated_at,
            source_revision=candidate.source_revision,
            source_hash=candidate.source_hash,
            catalog_version=candidate.catalog_version,
            answer_schema_version=candidate.answer_schema_version,
            prompt_version=candidate.prompt_version,
            extraction_schema_version=candidate.extraction_schema_version,
        )


@pytest.mark.django_db
def test_database_rejects_incomplete_processing_state(owner, business_unit):
    candidate, _session, _target = make_candidate(
        actor=owner,
        business_unit=business_unit,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        FieldAdoptionCandidate.objects.filter(pk=candidate.pk).update(
            status=FieldAdoptionCandidate.Status.PROCESSING,
        )
