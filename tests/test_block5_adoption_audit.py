from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from ki_radar.accelerator.adoption_service import (
    AdoptionOutcome,
    adopt_field_candidate,
    reject_field_candidate,
)
from ki_radar.accelerator.candidate_snapshot import (
    canonical_text_hash,
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
    FieldAdoptionAudit,
    FieldAdoptionCandidate,
)
from ki_radar.accelerator.retention import purge_terminal_capture_sessions
from ki_radar.accelerator.services import create_capture_session
from ki_radar.accelerator.target_binding import bind_capture_target
from ki_radar.architecture.models import ValueStream


@pytest.fixture(autouse=True)
def enable_field_adoption(settings):
    settings.ACCELERATOR_FIELD_ADOPTION_ENABLED = True


def make_candidate(*, owner, business_unit, field_name="description"):
    target = ValueStream.objects.create(
        name="Beschaffung",
        business_unit=business_unit,
        owner=owner,
        status=ValueStream.Status.ACTIVE,
        description="Bestehende Beschreibung",
        trigger="Bedarf entsteht",
        outcome="Bestellung ist ausgelöst",
        scope_in="Bedarf bis Bestellung",
        created_by=owner,
    )
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    bind_capture_target(actor=owner, session_id=session.pk, target_id=target.pk)
    session.status = CaptureSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.expires_at = timezone.now() + timedelta(days=90)
    session.save(update_fields=["status", "completed_at", "expires_at", "updated_at"])
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=session.revision,
        source_hash="a" * 64,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        catalog_version=CATALOG_VERSION_V1,
        answer_schema_version=ANSWER_SCHEMA_VERSION,
        provider="openrouter",
        model_name="test/model",
        prompt_version=EXTRACTION_PROMPT_VERSION,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
        finished_at=timezone.now(),
        prompt_tokens=120,
        completion_tokens=30,
        total_tokens=150,
        cost=Decimal("0.001234"),
    )
    suggestion = CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=CaptureSession.CaptureType.VALUE_STREAM,
        target_field=field_name,
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Neue geprüfte Beschreibung",
        source_question="identity",
        source_excerpt="Vertraulicher Rohtext, der nicht dupliziert werden darf.",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Direkte Aussage",
    )
    candidate = create_adoption_candidates(analysis_id=analysis.pk)[0]
    return target, session, analysis, suggestion, candidate


@pytest.mark.django_db
def test_adoption_audit_captures_minimal_provenance_and_cost(owner, business_unit):
    target, session, analysis, suggestion, candidate = make_candidate(
        owner=owner,
        business_unit=business_unit,
    )

    result = adopt_field_candidate(
        candidate_id=candidate.pk,
        actor=owner,
        edited_value="Bearbeitete Beschreibung",
    )

    audit = FieldAdoptionAudit.objects.get(candidate_id_snapshot=candidate.pk)
    assert result.outcome == AdoptionOutcome.ADOPTED_EDITED
    assert audit.candidate == candidate
    assert audit.suggestion == suggestion
    assert audit.analysis == analysis
    assert audit.session == session
    assert audit.actor == owner
    assert audit.analysis_id_snapshot == analysis.pk
    assert audit.target_object_id == target.pk
    assert audit.previous_value == "Bestehende Beschreibung"
    assert audit.proposed_value == "Neue geprüfte Beschreibung"
    assert audit.edited_value == "Bearbeitete Beschreibung"
    assert audit.final_value == "Bearbeitete Beschreibung"
    assert audit.source_question == "identity"
    assert audit.source_excerpt_hash == canonical_text_hash(suggestion.source_excerpt)
    assert not hasattr(audit, "source_excerpt")
    assert audit.provider == "openrouter"
    assert audit.model_name == "test/model"
    assert audit.prompt_tokens == 120
    assert audit.completion_tokens == 30
    assert audit.total_tokens == 150
    assert audit.cost == Decimal("0.001234")


@pytest.mark.django_db
def test_idempotent_repeat_does_not_duplicate_audit(owner, business_unit):
    _target, _session, _analysis, _suggestion, candidate = make_candidate(
        owner=owner,
        business_unit=business_unit,
    )

    first = reject_field_candidate(candidate_id=candidate.pk, actor=owner)
    second = reject_field_candidate(candidate_id=candidate.pk, actor=owner)

    assert first.outcome == AdoptionOutcome.REJECTED
    assert second.outcome == AdoptionOutcome.REJECTED
    assert second.idempotent is True
    assert FieldAdoptionAudit.objects.filter(candidate_id_snapshot=candidate.pk).count() == 1
    audit = FieldAdoptionAudit.objects.get(candidate_id_snapshot=candidate.pk)
    assert audit.action == FieldAdoptionAudit.Action.REJECT
    assert audit.final_value == "Bestehende Beschreibung"


@pytest.mark.django_db
def test_purge_removes_capture_graph_but_preserves_minimal_audit(owner, business_unit):
    _target, session, analysis, suggestion, candidate = make_candidate(
        owner=owner,
        business_unit=business_unit,
    )
    candidate_id = candidate.pk
    suggestion_id = suggestion.pk
    analysis_id = analysis.pk
    session_id = session.pk
    adopt_field_candidate(candidate_id=candidate.pk, actor=owner)
    old = timezone.now() - timedelta(days=8)
    session.status = CaptureSession.Status.DISCARDED
    session.discarded_at = old
    session.save(update_fields=["status", "discarded_at", "updated_at"])

    assert purge_terminal_capture_sessions(now=timezone.now()) == 1

    assert not CaptureSession.objects.filter(pk=session_id).exists()
    assert not CaptureAnalysis.objects.filter(pk=analysis_id).exists()
    assert not CaptureFieldSuggestion.objects.filter(pk=suggestion_id).exists()
    assert not FieldAdoptionCandidate.objects.filter(pk=candidate_id).exists()
    audit = FieldAdoptionAudit.objects.get(candidate_id_snapshot=candidate_id)
    assert audit.candidate is None
    assert audit.suggestion is None
    assert audit.analysis is None
    assert audit.session is None
    assert audit.session_id_snapshot == session_id
    assert audit.analysis_id_snapshot == analysis_id


@pytest.mark.django_db
def test_purge_removes_open_candidate_without_creating_audit(owner, business_unit):
    _target, session, _analysis, _suggestion, candidate = make_candidate(
        owner=owner,
        business_unit=business_unit,
    )
    candidate_id = candidate.pk
    old = timezone.now() - timedelta(days=8)
    session.status = CaptureSession.Status.DISCARDED
    session.discarded_at = old
    session.save(update_fields=["status", "discarded_at", "updated_at"])

    purge_terminal_capture_sessions(now=timezone.now())

    assert not FieldAdoptionCandidate.objects.filter(pk=candidate_id).exists()
    assert not FieldAdoptionAudit.objects.filter(candidate_id_snapshot=candidate_id).exists()
