from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from ki_radar.accelerator.candidate_snapshot import (
    CandidateSnapshotError,
    CandidateValidity,
    candidate_validity,
    canonical_text_hash,
    canonicalize_text,
    create_adoption_candidates,
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
from ki_radar.use_cases.models import UseCase


def make_value_stream(*, business_unit, owner, name="Café Beschaffung"):
    return ValueStream.objects.create(
        name=name,
        business_unit=business_unit,
        owner=owner,
        status=ValueStream.Status.ACTIVE,
        trigger="Bedarf entsteht",
        outcome="Bestellung ist ausgelöst",
        scope_in="Bedarf bis Bestellung",
        created_by=owner,
    )


def make_use_case(*, business_unit, owner, title="Angebotsvergleich"):
    return UseCase.objects.create(
        title=title,
        problem_statement="Der Vergleich ist langsam.",
        business_unit=business_unit,
        affected_process="Beschaffung",
        business_owner=owner,
        expected_benefit="Bearbeitungszeit senken",
        submitter=owner,
    )


def make_analysis(*, session, actor, field_name, suggested_value, target_type=None):
    session.status = CaptureSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.expires_at = timezone.now() + timedelta(days=90)
    session.save(update_fields=["status", "completed_at", "expires_at", "updated_at"])
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=actor,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=session.revision,
        source_hash="a" * 64,
        capture_type=session.capture_type,
        catalog_version=CATALOG_VERSION_V1,
        answer_schema_version=ANSWER_SCHEMA_VERSION,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
        finished_at=timezone.now(),
    )
    suggestion = CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=target_type or session.capture_type,
        target_field=field_name,
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value=suggested_value,
        source_question="identity",
        source_excerpt=str(suggested_value),
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Direkte Aussage",
    )
    return analysis, suggestion


def test_canonicalization_treats_only_format_equivalents_as_equal():
    decomposed = "  Cafe\u0301  \r\nZweite Zeile\t  "
    composed = "Café\nZweite Zeile"

    assert canonicalize_text(decomposed) == composed
    assert canonical_text_hash(decomposed) == canonical_text_hash(composed)
    assert canonical_text_hash("A  B") != canonical_text_hash("A B")
    assert canonical_text_hash("Zeile 1\nZeile 2") != canonical_text_hash("Zeile 1 Zeile 2")


def test_canonicalization_rejects_non_text_values():
    with pytest.raises(TypeError, match="Nur Textwerte"):
        canonicalize_text(7)  # type: ignore[arg-type]


@pytest.mark.django_db
def test_candidate_captures_canonical_field_snapshot(owner, business_unit):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    bind_capture_target(actor=owner, session_id=session.pk, target_id=target.pk)
    analysis, suggestion = make_analysis(
        session=session,
        actor=owner,
        field_name="name",
        suggested_value="  Strategische Beschaffung\r\n",
    )

    candidates = create_adoption_candidates(analysis_id=analysis.pk)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.suggestion == suggestion
    assert candidate.target_object_type == CaptureSession.CaptureType.VALUE_STREAM
    assert candidate.target_object_id == target.pk
    assert candidate.target_field == "name"
    assert candidate.proposed_value == "Strategische Beschaffung"
    assert candidate.previous_value == "Café Beschaffung"
    assert candidate.previous_value_hash == canonical_text_hash(target.name)
    assert candidate.target_updated_at == target.updated_at
    assert candidate.source_revision == session.revision
    assert candidate.source_hash == analysis.source_hash


@pytest.mark.django_db
def test_candidate_creation_is_idempotent_per_suggestion(owner, business_unit):
    target = make_use_case(business_unit=business_unit, owner=owner)
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    bind_capture_target(actor=owner, session_id=session.pk, target_id=target.pk)
    analysis, _suggestion = make_analysis(
        session=session,
        actor=owner,
        field_name="title",
        suggested_value="Schneller Angebotsvergleich",
    )

    first = create_adoption_candidates(analysis_id=analysis.pk)
    second = create_adoption_candidates(analysis_id=analysis.pk)

    assert first[0].pk == second[0].pk
    assert FieldAdoptionCandidate.objects.count() == 1


@pytest.mark.django_db
def test_candidate_creation_requires_successful_bound_matching_analysis(owner, business_unit):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        status=CaptureAnalysis.Status.FAILED,
        source_revision=0,
        source_hash="b" * 64,
        capture_type=session.capture_type,
        catalog_version=CATALOG_VERSION_V1,
        answer_schema_version=ANSWER_SCHEMA_VERSION,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
        finished_at=timezone.now(),
    )

    with pytest.raises(CandidateSnapshotError, match="erfolgreiche Analysen"):
        create_adoption_candidates(analysis_id=analysis.pk)


@pytest.mark.django_db
def test_candidate_creation_ignores_grouped_and_wrong_target_suggestions(owner, business_unit):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    bind_capture_target(actor=owner, session_id=session.pk, target_id=target.pk)
    analysis, _suggestion = make_analysis(
        session=session,
        actor=owner,
        field_name="name",
        suggested_value="Nicht passend",
        target_type=CaptureFieldSuggestion.TargetObjectType.USE_CASE,
    )
    CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM,
        target_field="description",
        target_group_key="phase-1",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Gruppiert",
        source_question="flow",
        source_excerpt="Gruppiert",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Direkte Aussage",
    )

    assert create_adoption_candidates(analysis_id=analysis.pk) == []


@pytest.mark.django_db
def test_candidate_validity_distinguishes_stale_inactive_and_missing(owner, business_unit):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    bind_capture_target(actor=owner, session_id=session.pk, target_id=target.pk)
    analysis, _suggestion = make_analysis(
        session=session,
        actor=owner,
        field_name="name",
        suggested_value="Strategische Beschaffung",
    )
    candidate = create_adoption_candidates(analysis_id=analysis.pk)[0]

    assert candidate_validity(candidate) == CandidateValidity.VALID

    session.revision += 1
    session.save(update_fields=["revision", "updated_at"])
    candidate = FieldAdoptionCandidate.objects.select_related("suggestion__analysis__session").get(
        pk=candidate.pk
    )
    assert candidate_validity(candidate) == CandidateValidity.STALE

    session.revision -= 1
    session.save(update_fields=["revision", "updated_at"])
    target.status = ValueStream.Status.ARCHIVED
    target.save(update_fields=["status", "updated_at"])
    candidate = FieldAdoptionCandidate.objects.select_related("suggestion__analysis__session").get(
        pk=candidate.pk
    )
    assert candidate_validity(candidate) == CandidateValidity.TARGET_INACTIVE

    target.delete()
    candidate = FieldAdoptionCandidate.objects.select_related("suggestion__analysis__session").get(
        pk=candidate.pk
    )
    assert candidate_validity(candidate) == CandidateValidity.TARGET_MISSING


@pytest.mark.django_db
def test_candidate_validity_rejects_unsupported_version(owner, business_unit):
    target = make_use_case(business_unit=business_unit, owner=owner)
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    bind_capture_target(actor=owner, session_id=session.pk, target_id=target.pk)
    analysis, _suggestion = make_analysis(
        session=session,
        actor=owner,
        field_name="title",
        suggested_value="Schneller Angebotsvergleich",
    )
    candidate = create_adoption_candidates(analysis_id=analysis.pk)[0]
    candidate.prompt_version = "0.9"
    candidate.save(update_fields=["prompt_version", "updated_at"])

    assert candidate_validity(candidate) == CandidateValidity.STALE
