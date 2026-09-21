from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .models import CaptureAnalysis, CaptureSession

CAPTURE_PURGE_GRACE_DAYS = 7


def _expirable_sessions(*, checked_now):
    running_session_ids = list(
        CaptureAnalysis.objects.filter(status=CaptureAnalysis.Status.RUNNING).values_list(
            "session_id", flat=True
        )
    )
    sessions = CaptureSession.objects.filter(
        status__in=[CaptureSession.Status.DRAFT, CaptureSession.Status.COMPLETED],
        expires_at__lte=checked_now,
    )
    if running_session_ids:
        sessions = sessions.exclude(pk__in=running_session_ids)
    return sessions


def expire_due_capture_sessions(*, now=None, owner=None) -> int:
    """Move overdue editable or completed captures to the terminal expired state."""
    checked_now = now or timezone.now()
    sessions = _expirable_sessions(checked_now=checked_now)
    if owner is not None:
        sessions = sessions.filter(owner=owner)
    return sessions.update(
        status=CaptureSession.Status.EXPIRED,
        expired_at=checked_now,
        updated_at=checked_now,
    )


def expire_capture_session_if_due(session: CaptureSession, *, now=None) -> CaptureSession:
    checked_now = now or timezone.now()
    expirable_states = {CaptureSession.Status.DRAFT, CaptureSession.Status.COMPLETED}
    if session.status not in expirable_states or session.expires_at > checked_now:
        return session
    if session.analyses.filter(status=CaptureAnalysis.Status.RUNNING).exists():
        return session

    updated = (
        _expirable_sessions(checked_now=checked_now)
        .filter(pk=session.pk)
        .update(
            status=CaptureSession.Status.EXPIRED,
            expired_at=checked_now,
            updated_at=checked_now,
        )
    )
    if updated:
        session.status = CaptureSession.Status.EXPIRED
        session.expired_at = checked_now
        session.updated_at = checked_now
    else:
        session.refresh_from_db()
    return session


def purge_terminal_capture_sessions(
    *,
    now=None,
    grace_days: int = CAPTURE_PURGE_GRACE_DAYS,
) -> int:
    """Physically remove expired or discarded sessions after the grace period."""
    if grace_days < 0:
        raise ValueError("Die Karenzzeit darf nicht negativ sein.")

    checked_now = now or timezone.now()
    cutoff = checked_now - timedelta(days=grace_days)
    sessions = CaptureSession.objects.filter(
        Q(
            status=CaptureSession.Status.EXPIRED,
            expired_at__isnull=False,
            expired_at__lte=cutoff,
        )
        | Q(
            status=CaptureSession.Status.DISCARDED,
            discarded_at__isnull=False,
            discarded_at__lte=cutoff,
        )
    )
    deleted_count = sessions.count()
    sessions.delete()
    return deleted_count
