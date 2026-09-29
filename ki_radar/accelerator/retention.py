from __future__ import annotations

import shutil
from contextlib import suppress
from datetime import timedelta
from pathlib import Path

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .investigation_ingestion import _managed_source_root
from .investigation_models import InvestigationSourceFolder
from .models import CaptureAnalysis, CaptureSession

CAPTURE_PURGE_GRACE_DAYS = 7


def _unshared_managed_capture_path(
    *, session: CaptureSession, folder: InvestigationSourceFolder
) -> Path | None:
    """Return only a managed capture path that no other source folder uses."""
    root = _managed_source_root()
    expected = root / f"capture-{session.pk}" / str(folder.pk)
    path = Path(folder.root_path)
    if path != expected:
        raise ValueError("Der Discovery-Quellenpfad liegt nicht im verwalteten Capture-Bereich.")
    if (
        InvestigationSourceFolder.objects.filter(root_path=folder.root_path)
        .exclude(pk=folder.pk)
        .exists()
    ):
        return None
    if not path.exists():
        return None
    if not path.is_dir() or path.resolve(strict=True) != expected:
        raise ValueError("Der Discovery-Quellenpfad ist kein sicherer verwalteter Ordner.")
    return path


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
    deleted_count = 0
    for session_id in list(sessions.values_list("pk", flat=True)):
        with transaction.atomic():
            session = sessions.select_for_update().filter(pk=session_id).first()
            if session is None:
                continue
            folders = list(
                InvestigationSourceFolder.objects.select_for_update().filter(
                    capture_session=session
                )
            )
            paths = [
                path
                for folder in folders
                if (path := _unshared_managed_capture_path(session=session, folder=folder))
                is not None
            ]
            for path in paths:
                shutil.rmtree(path)
                # Another managed folder may still belong to this capture.
                with suppress(OSError):
                    path.parent.rmdir()
            session.delete()
            deleted_count += 1
    return deleted_count
