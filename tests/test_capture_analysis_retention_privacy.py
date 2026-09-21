from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator import analysis_service
from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.models import CaptureAnalysis, CaptureFieldSuggestion, CaptureSession
from ki_radar.accelerator.retention import (
    expire_capture_session_if_due,
    expire_due_capture_sessions,
    purge_terminal_capture_sessions,
)
from ki_radar.accelerator.retention_policy import (
    CaptureRetentionConfigurationError,
    get_completed_capture_retention_days,
)
from ki_radar.accelerator.services import (
    complete_capture_session,
    create_capture_session,
    save_capture_session,
)

LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "15",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "50000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "700",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "3",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "20",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "100",
}


def _complete(owner):
    session = create_capture_session(actor=owner, capture_type="value_stream")
    catalog = get_capture_catalog("value_stream", session.catalog_version)
    session = save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=session.revision,
        answer_updates={question.key: f"SENSIBEL-{question.key}" for question in catalog.questions},
    )
    return complete_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=session.revision,
    )


@pytest.mark.parametrize("value", ["30", "90", "365"])
def test_completed_retention_accepts_configured_range(value):
    with override_settings(ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS=value):
        assert get_completed_capture_retention_days() == int(value)


@pytest.mark.parametrize("value", ["29", "366", "invalid", True])
def test_completed_retention_rejects_invalid_configuration(value):
    with (
        override_settings(ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS=value),
        pytest.raises(CaptureRetentionConfigurationError),
    ):
        get_completed_capture_retention_days()


@pytest.mark.django_db
@override_settings(ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS="90")
def test_completion_sets_configured_retention_instead_of_draft_window(owner):
    before = timezone.now()

    session = _complete(owner)

    assert before + timedelta(days=89, hours=23) < session.expires_at
    assert session.expires_at < before + timedelta(days=90, minutes=1)


@pytest.mark.django_db
@override_settings(**LIMITS, ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS="120")
def test_explicit_analysis_refreshes_completed_retention(owner):
    session = _complete(owner)
    old_expiry = timezone.now() + timedelta(days=10)
    CaptureSession.objects.filter(pk=session.pk).update(expires_at=old_expiry)

    analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    session.refresh_from_db()
    assert session.expires_at > timezone.now() + timedelta(days=119)


@pytest.mark.django_db
def test_due_completed_session_expires_but_running_analysis_protects_it(owner):
    session = _complete(owner)
    overdue = timezone.now() - timedelta(days=1)
    CaptureSession.objects.filter(pk=session.pk).update(expires_at=overdue)
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        source_revision=session.revision,
        source_hash="a" * 64,
        capture_type=session.capture_type,
        catalog_version=session.catalog_version,
        answer_schema_version=session.schema_version,
        prompt_version="1.0",
        extraction_schema_version="1.0",
    )

    assert expire_due_capture_sessions() == 0
    analysis.status = CaptureAnalysis.Status.FAILED
    analysis.finished_at = timezone.now()
    analysis.save(update_fields=["status", "finished_at", "updated_at"])

    assert expire_due_capture_sessions() == 1
    session.refresh_from_db()
    assert session.status == CaptureSession.Status.EXPIRED


@pytest.mark.django_db
def test_single_session_expiry_handles_completed_status(owner):
    session = _complete(owner)
    CaptureSession.objects.filter(pk=session.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    session.refresh_from_db()

    result = expire_capture_session_if_due(session)

    assert result.status == CaptureSession.Status.EXPIRED
    assert result.expired_at is not None


@pytest.mark.django_db
def test_physical_purge_cascades_analyses_and_suggestions(owner):
    session = _complete(owner)
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=session.revision,
        source_hash="a" * 64,
        capture_type=session.capture_type,
        catalog_version=session.catalog_version,
        answer_schema_version=session.schema_version,
        prompt_version="1.0",
        extraction_schema_version="1.0",
        finished_at=timezone.now(),
    )
    CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type="value_stream",
        target_field="value_stream.name",
        field_type="text",
        suggested_value="Beschaffung",
        source_question="vs_context",
        source_excerpt="SENSIBEL-vs_context",
        uncertainty="low",
        uncertainty_reason="Explizit.",
    )
    old = timezone.now() - timedelta(days=8)
    CaptureSession.objects.filter(pk=session.pk).update(
        status=CaptureSession.Status.EXPIRED,
        expired_at=old,
    )

    assert purge_terminal_capture_sessions(now=timezone.now(), grace_days=7) == 1
    assert CaptureSession.objects.count() == 0
    assert CaptureAnalysis.objects.count() == 0
    assert CaptureFieldSuggestion.objects.count() == 0


@pytest.mark.django_db
def test_analysis_technical_log_contains_no_capture_or_suggestion_text(owner, monkeypatch):
    session = _complete(owner)
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        status=CaptureAnalysis.Status.FAILED,
        source_revision=session.revision,
        source_hash="b" * 64,
        capture_type=session.capture_type,
        catalog_version=session.catalog_version,
        answer_schema_version=session.schema_version,
        prompt_version="1.0",
        extraction_schema_version="1.0",
        finished_at=timezone.now(),
        error_code="timeout",
    )
    logged = []

    def capture_log(message, *args):
        logged.append(message % args)

    monkeypatch.setattr(analysis_service.logger, "info", capture_log)
    analysis_service.log_capture_analysis(analysis)
    log_text = " ".join(logged)

    assert "purpose=capture_extraction" in log_text
    assert "status=failed" in log_text
    assert "SENSIBEL" not in log_text
    assert "Beschaffung" not in log_text
