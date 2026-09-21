from datetime import timedelta

import pytest
from django.apps import apps
from django.utils import timezone

from ki_radar.accelerator.models import CaptureSession


@pytest.mark.django_db
def test_capture_session_defaults_to_editable_draft(owner):
    session = CaptureSession.objects.create(
        owner=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Beschaffung",
        catalog_version="1.0",
        schema_version="1.0",
        required_question_count=10,
        answered_required_count=5,
        expires_at=timezone.now() + timedelta(days=30),
    )

    assert session.status == CaptureSession.Status.DRAFT
    assert session.revision == 0
    assert session.save_count == 0
    assert session.answers == {}
    assert session.progress_percent == 50
    assert session.is_editable is True


@pytest.mark.django_db
def test_multiple_parallel_drafts_per_owner_and_capture_type_are_allowed(owner):
    common = {
        "owner": owner,
        "capture_type": CaptureSession.CaptureType.USE_CASE,
        "catalog_version": "1.0",
        "schema_version": "1.0",
        "expires_at": timezone.now() + timedelta(days=30),
    }

    first = CaptureSession.objects.create(working_title="Erster Entwurf", **common)
    second = CaptureSession.objects.create(working_title="Zweiter Entwurf", **common)

    assert first.pk != second.pk
    assert (
        CaptureSession.objects.filter(
            owner=owner,
            capture_type=CaptureSession.CaptureType.USE_CASE,
            status=CaptureSession.Status.DRAFT,
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_deleting_owner_removes_temporary_capture_sessions(owner):
    CaptureSession.objects.create(
        owner=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        catalog_version="1.0",
        schema_version="1.0",
        expires_at=timezone.now() + timedelta(days=30),
    )

    owner.delete()

    assert CaptureSession.objects.count() == 0


@pytest.mark.django_db
def test_terminal_status_is_not_reported_as_editable(owner):
    session = CaptureSession.objects.create(
        owner=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        catalog_version="1.0",
        schema_version="1.0",
        status=CaptureSession.Status.COMPLETED,
        completed_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=30),
    )

    assert session.is_editable is False


def test_capture_session_has_no_simple_history_model():
    assert "historicalcapturesession" not in apps.all_models.get("accelerator", {})
