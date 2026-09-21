from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.services import (
    CaptureStateError,
    create_capture_session,
    discard_capture_session,
    get_owned_capture_session,
    save_capture_session,
)


@pytest.mark.django_db
def test_due_draft_expires_on_service_load_and_cannot_be_saved(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Überfälliger Entwurf",
    )
    CaptureSession.objects.filter(pk=session.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    loaded = get_owned_capture_session(actor=owner, session_id=session.pk)

    assert loaded.status == CaptureSession.Status.EXPIRED
    assert loaded.expired_at is not None
    with pytest.raises(CaptureStateError, match="nicht mehr bearbeitbar"):
        save_capture_session(
            actor=owner,
            session_id=session.pk,
            expected_revision=loaded.revision,
            answer_updates={},
        )


@pytest.mark.django_db
def test_discard_is_irreversible(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    discarded = discard_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=0,
    )

    with pytest.raises(CaptureStateError, match="nicht mehr bearbeitbar"):
        discard_capture_session(
            actor=owner,
            session_id=session.pk,
            expected_revision=discarded.revision,
        )


@pytest.mark.django_db
def test_retention_command_expires_due_drafts_and_purges_only_old_terminal_sessions(
    owner,
):
    now = timezone.now()
    due_draft = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Jetzt ablaufen",
    )
    old_expired = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Alt abgelaufen",
    )
    old_discarded = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Alt verworfen",
    )
    recent_discarded = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Neu verworfen",
    )
    completed = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Abgeschlossen",
    )

    CaptureSession.objects.filter(pk=due_draft.pk).update(expires_at=now - timedelta(seconds=1))
    CaptureSession.objects.filter(pk=old_expired.pk).update(
        status=CaptureSession.Status.EXPIRED,
        expired_at=now - timedelta(days=8),
    )
    CaptureSession.objects.filter(pk=old_discarded.pk).update(
        status=CaptureSession.Status.DISCARDED,
        discarded_at=now - timedelta(days=8),
    )
    CaptureSession.objects.filter(pk=recent_discarded.pk).update(
        status=CaptureSession.Status.DISCARDED,
        discarded_at=now - timedelta(days=1),
    )
    CaptureSession.objects.filter(pk=completed.pk).update(
        status=CaptureSession.Status.COMPLETED,
        completed_at=now - timedelta(days=120),
    )

    output = StringIO()
    call_command("purge_capture_sessions", stdout=output)

    due_draft.refresh_from_db()
    assert due_draft.status == CaptureSession.Status.EXPIRED
    assert due_draft.expired_at is not None
    assert not CaptureSession.objects.filter(pk=old_expired.pk).exists()
    assert not CaptureSession.objects.filter(pk=old_discarded.pk).exists()
    assert CaptureSession.objects.filter(pk=recent_discarded.pk).exists()
    assert CaptureSession.objects.filter(pk=completed.pk).exists()
    assert "1 abgelaufen, 2 physisch gelöscht" in output.getvalue()

    second_output = StringIO()
    call_command("purge_capture_sessions", stdout=second_output)
    assert "0 abgelaufen, 0 physisch gelöscht" in second_output.getvalue()


@pytest.mark.django_db
def test_retention_command_rejects_negative_grace_period():
    with pytest.raises(CommandError, match="darf nicht negativ"):
        call_command("purge_capture_sessions", grace_days=-1)
