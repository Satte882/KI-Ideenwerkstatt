from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from ki_radar.architecture.permissions import can_manage_architecture
from ki_radar.use_cases.permissions import can_create_use_case

from .catalogs import (
    CURRENT_CATALOG_VERSIONS,
    CaptureAnswerValidationError,
    CaptureType,
    catalog_progress,
    get_capture_catalog,
    validate_answer_document,
)
from .models import CaptureSession
from .retention import expire_capture_session_if_due
from .retention_policy import completed_capture_expiry

CAPTURE_DRAFT_RETENTION_DAYS = 30
MAX_ACTIVE_ENTRY_SECONDS_PER_SAVE = 900


class CaptureRevisionConflict(RuntimeError):
    """Raised when a stale form attempts to overwrite a newer draft revision."""


class CaptureStateError(RuntimeError):
    """Raised when an operation is not allowed for the current lifecycle state."""


def _assert_capture_type(capture_type: str) -> CaptureType:
    allowed = {choice for choice, _label in CaptureSession.CaptureType.choices}
    if capture_type not in allowed:
        raise ValidationError({"capture_type": "Unbekannte Capture-Art."})
    return capture_type


def _can_manage_capture(actor, capture_type: str) -> bool:
    if capture_type == CaptureSession.CaptureType.VALUE_STREAM:
        return can_manage_architecture(actor)
    if capture_type == CaptureSession.CaptureType.USE_CASE:
        return can_create_use_case(actor)
    return False


def _assert_capture_permission(actor, capture_type: str) -> None:
    if not _can_manage_capture(actor, capture_type):
        raise PermissionDenied("Für diese geführte Erfassung fehlt die Berechtigung.")


def _normalize_working_title(value: str | None) -> str:
    normalized = (value or "").strip()
    if len(normalized) > 200:
        raise ValidationError({"working_title": "Die Arbeitsbezeichnung ist zu lang."})
    return normalized


def _bounded_active_entry_seconds(value: object) -> int:
    try:
        seconds = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            {"active_entry_seconds": "Die aktive Eingabezeit ist ungültig."}
        ) from exc
    if seconds < 0:
        raise ValidationError({"active_entry_seconds": "Die aktive Eingabezeit ist ungültig."})
    return min(seconds, MAX_ACTIVE_ENTRY_SECONDS_PER_SAVE)


def _draft_expiry(now=None):
    return (now or timezone.now()) + timedelta(days=CAPTURE_DRAFT_RETENTION_DAYS)


def create_capture_session(*, actor, capture_type: str, working_title: str = "") -> CaptureSession:
    checked_type = _assert_capture_type(capture_type)
    _assert_capture_permission(actor, checked_type)
    catalog = get_capture_catalog(checked_type)

    return CaptureSession.objects.create(
        owner=actor,
        capture_type=checked_type,
        working_title=_normalize_working_title(working_title),
        catalog_version=catalog.version,
        schema_version=catalog.schema_version,
        required_question_count=len(catalog.required_question_keys),
        expires_at=_draft_expiry(),
    )


def get_owned_capture_session(*, actor, session_id) -> CaptureSession:
    session = CaptureSession.objects.get(pk=session_id, owner=actor)
    _assert_capture_permission(actor, session.capture_type)
    return expire_capture_session_if_due(session)


def _locked_owned_session(*, actor, session_id) -> CaptureSession:
    session = CaptureSession.objects.select_for_update().get(pk=session_id, owner=actor)
    _assert_capture_permission(actor, session.capture_type)
    return expire_capture_session_if_due(session)


def _assert_editable(session: CaptureSession) -> None:
    if session.status != CaptureSession.Status.DRAFT:
        raise CaptureStateError("Diese Erfassung ist nicht mehr bearbeitbar.")


def _assert_revision(session: CaptureSession, expected_revision: int) -> None:
    if session.revision != expected_revision:
        raise CaptureRevisionConflict(
            "Die Erfassung wurde zwischenzeitlich geändert. Laden Sie den aktuellen Stand neu."
        )


def _stored_catalog(session: CaptureSession):
    catalog = get_capture_catalog(session.capture_type, session.catalog_version)
    if session.schema_version != catalog.schema_version:
        raise CaptureAnswerValidationError(
            [
                "Die gespeicherte Antwortschema-Version passt nicht zum Fragenkatalog. "
                "Die Erfassung bleibt schreibgeschützt."
            ]
        )
    return catalog


@transaction.atomic
def save_capture_session(
    *,
    actor,
    session_id,
    expected_revision: int,
    answer_updates: object,
    working_title: str | None = None,
    active_entry_seconds_delta: object = 0,
) -> CaptureSession:
    session = _locked_owned_session(actor=actor, session_id=session_id)
    _assert_editable(session)
    _assert_revision(session, expected_revision)
    catalog = _stored_catalog(session)
    bounded_active_seconds = _bounded_active_entry_seconds(active_entry_seconds_delta)

    current_answers = validate_answer_document(catalog, session.answers)
    if not isinstance(answer_updates, dict):
        raise CaptureAnswerValidationError(["Antwortänderungen müssen ein JSON-Objekt sein."])
    merged_answers = {**current_answers, **answer_updates}
    normalized_answers = validate_answer_document(catalog, merged_answers)
    completed_count, required_count = catalog_progress(catalog, normalized_answers)

    session.answers = normalized_answers
    session.answered_required_count = completed_count
    session.required_question_count = required_count
    session.active_entry_seconds += bounded_active_seconds
    if working_title is not None:
        session.working_title = _normalize_working_title(working_title)
    session.revision += 1
    session.save_count += 1
    session.expires_at = _draft_expiry()
    session.save(
        update_fields=[
            "answers",
            "answered_required_count",
            "required_question_count",
            "active_entry_seconds",
            "working_title",
            "revision",
            "save_count",
            "expires_at",
            "updated_at",
        ]
    )
    return session


@transaction.atomic
def complete_capture_session(*, actor, session_id, expected_revision: int) -> CaptureSession:
    session = _locked_owned_session(actor=actor, session_id=session_id)
    _assert_editable(session)
    _assert_revision(session, expected_revision)
    catalog = _stored_catalog(session)
    normalized_answers = validate_answer_document(
        catalog,
        session.answers,
        require_complete=True,
    )
    completed_count, required_count = catalog_progress(catalog, normalized_answers)
    now = timezone.now()

    session.answers = normalized_answers
    session.answered_required_count = completed_count
    session.required_question_count = required_count
    session.status = CaptureSession.Status.COMPLETED
    session.completed_at = now
    session.expires_at = completed_capture_expiry(now=now)
    session.revision += 1
    session.save(
        update_fields=[
            "answers",
            "answered_required_count",
            "required_question_count",
            "status",
            "completed_at",
            "expires_at",
            "revision",
            "updated_at",
        ]
    )
    return session


@transaction.atomic
def discard_capture_session(*, actor, session_id, expected_revision: int) -> CaptureSession:
    session = _locked_owned_session(actor=actor, session_id=session_id)
    _assert_editable(session)
    _assert_revision(session, expected_revision)
    now = timezone.now()

    session.status = CaptureSession.Status.DISCARDED
    session.discarded_at = now
    session.revision += 1
    session.save(update_fields=["status", "discarded_at", "revision", "updated_at"])
    return session


def current_catalog_version(capture_type: str) -> str:
    checked_type = _assert_capture_type(capture_type)
    return CURRENT_CATALOG_VERSIONS[checked_type]
