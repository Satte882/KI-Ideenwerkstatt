from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from ki_radar.accelerator.models import (
    AcceleratorLLMQuota,
    CaptureAnalysis,
    CaptureFieldSuggestion,
    CaptureSession,
)


def _completed_session(owner):
    now = timezone.now()
    return CaptureSession.objects.create(
        owner=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        catalog_version="1.0",
        schema_version="1.0",
        status=CaptureSession.Status.COMPLETED,
        completed_at=now,
        expires_at=now + timedelta(days=90),
    )


def _analysis(session, owner, **overrides):
    values = {
        "session": session,
        "requested_by": owner,
        "source_revision": session.revision,
        "source_hash": "a" * 64,
        "capture_type": session.capture_type,
        "catalog_version": session.catalog_version,
        "answer_schema_version": session.schema_version,
        "prompt_version": "1.0",
        "extraction_schema_version": "1.0",
    }
    values.update(overrides)
    return CaptureAnalysis.objects.create(**values)


@pytest.mark.django_db
def test_capture_analysis_persists_source_and_provider_metadata(owner):
    session = _completed_session(owner)

    analysis = _analysis(session, owner)

    assert analysis.status == CaptureAnalysis.Status.RUNNING
    assert analysis.provider == "openrouter"
    assert analysis.source_revision == session.revision
    assert analysis.source_hash == "a" * 64
    assert analysis.open_questions == []
    assert analysis.contradictions == []


@pytest.mark.django_db
def test_only_one_running_analysis_per_session_and_source_hash(owner):
    session = _completed_session(owner)
    _analysis(session, owner)

    with pytest.raises(IntegrityError), transaction.atomic():
        _analysis(session, owner)

    finished_at = timezone.now()
    completed = _analysis(
        session,
        owner,
        status=CaptureAnalysis.Status.SUCCESS,
        finished_at=finished_at,
    )
    assert completed.finished_at == finished_at


@pytest.mark.django_db
def test_terminal_analysis_requires_finished_timestamp(owner):
    session = _completed_session(owner)

    with pytest.raises(IntegrityError), transaction.atomic():
        _analysis(session, owner, status=CaptureAnalysis.Status.FAILED)


@pytest.mark.django_db
def test_suggestion_supports_future_target_binding_and_local_group(owner):
    session = _completed_session(owner)
    analysis = _analysis(session, owner)

    suggestion = CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM_STAGE,
        target_field="value_stream.stages[].name",
        target_group_key="angebot-prufen",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Angebot prüfen",
        source_question="vs_stages",
        source_excerpt="Angebot prüfen",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Explizit genannt.",
    )

    assert suggestion.target_object_id is None
    assert suggestion.target_group_key == "angebot-prufen"


@pytest.mark.django_db
def test_suggestion_target_is_unique_within_analysis_and_group(owner):
    session = _completed_session(owner)
    analysis = _analysis(session, owner)
    values = {
        "analysis": analysis,
        "target_object_type": CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM_STAGE,
        "target_field": "value_stream.stages[].name",
        "target_group_key": "angebot-prufen",
        "field_type": CaptureFieldSuggestion.FieldType.TEXT,
        "suggested_value": "Angebot prüfen",
        "source_question": "vs_stages",
        "source_excerpt": "Angebot prüfen",
        "uncertainty": CaptureFieldSuggestion.Uncertainty.LOW,
        "uncertainty_reason": "Explizit genannt.",
    }
    CaptureFieldSuggestion.objects.create(**values)

    with pytest.raises(IntegrityError), transaction.atomic():
        CaptureFieldSuggestion.objects.create(**values)


@pytest.mark.django_db
def test_quota_scope_requires_exactly_the_matching_owner(owner):
    session = _completed_session(owner)
    today = timezone.localdate()

    AcceleratorLLMQuota.objects.create(
        scope=AcceleratorLLMQuota.Scope.CONTEXT,
        quota_date=today,
        session=session,
    )
    AcceleratorLLMQuota.objects.create(
        scope=AcceleratorLLMQuota.Scope.USER,
        quota_date=today,
        user=owner,
    )
    AcceleratorLLMQuota.objects.create(
        scope=AcceleratorLLMQuota.Scope.GLOBAL,
        quota_date=today,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        AcceleratorLLMQuota.objects.create(
            scope=AcceleratorLLMQuota.Scope.USER,
            quota_date=today + timedelta(days=1),
            session=session,
        )


@pytest.mark.django_db
def test_quota_is_unique_per_scope_subject_and_day(owner):
    today = timezone.localdate()
    AcceleratorLLMQuota.objects.create(
        scope=AcceleratorLLMQuota.Scope.USER,
        quota_date=today,
        user=owner,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        AcceleratorLLMQuota.objects.create(
            scope=AcceleratorLLMQuota.Scope.USER,
            quota_date=today,
            user=owner,
        )


@pytest.mark.django_db
def test_session_deletion_removes_analysis_suggestions_and_context_quota(owner):
    session = _completed_session(owner)
    analysis = _analysis(session, owner)
    CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM,
        target_field="value_stream.name",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Beschaffung",
        source_question="vs_context",
        source_excerpt="Beschaffung",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Explizit genannt.",
    )
    AcceleratorLLMQuota.objects.create(
        scope=AcceleratorLLMQuota.Scope.CONTEXT,
        quota_date=timezone.localdate(),
        session=session,
    )

    session.delete()

    assert CaptureAnalysis.objects.count() == 0
    assert CaptureFieldSuggestion.objects.count() == 0
    assert AcceleratorLLMQuota.objects.count() == 0
