from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from ki_radar.accelerator.catalogs import (
    CURRENT_CATALOG_VERSIONS,
    CaptureAnswerValidationError,
    UnsupportedCaptureCatalog,
    get_capture_catalog,
)
from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.services import (
    CaptureRevisionConflict,
    CaptureStateError,
    complete_capture_session,
    create_capture_session,
    discard_capture_session,
    get_owned_capture_session,
    save_capture_session,
)


def required_answers(capture_type: str) -> dict[str, str]:
    catalog = get_capture_catalog(capture_type)
    return {key: f"Antwort für {key}" for key in catalog.required_question_keys}


@pytest.mark.django_db
def test_create_uses_current_version_and_existing_permissions(owner):
    value_stream = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="  Beschaffung  ",
    )
    use_case = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )

    assert value_stream.working_title == "Beschaffung"
    assert value_stream.catalog_version == "1.0"
    assert value_stream.schema_version == "1.0"
    assert value_stream.required_question_count > 0
    assert use_case.required_question_count > 0
    assert value_stream.owner == owner
    assert use_case.owner == owner


@pytest.mark.django_db
def test_reader_cannot_create_capture_session(reader):
    with pytest.raises(PermissionDenied):
        create_capture_session(
            actor=reader,
            capture_type=CaptureSession.CaptureType.USE_CASE,
        )

    assert CaptureSession.objects.count() == 0


@pytest.mark.django_db
def test_save_merges_answers_updates_revision_progress_and_expiry(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    old_expiry = timezone.now() + timedelta(days=1)
    CaptureSession.objects.filter(pk=session.pk).update(expires_at=old_expiry)
    first_key, second_key = get_capture_catalog("use_case").required_question_keys[:2]

    saved = save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=0,
        answer_updates={first_key: "  Erste Antwort  "},
        working_title="Erster Use Case",
    )
    saved = save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=1,
        answer_updates={second_key: "Zweite Antwort"},
    )

    assert saved.answers[first_key] == "Erste Antwort"
    assert saved.answers[second_key] == "Zweite Antwort"
    assert saved.working_title == "Erster Use Case"
    assert saved.revision == 2
    assert saved.save_count == 2
    assert saved.answered_required_count == 2
    assert saved.expires_at > old_expiry


@pytest.mark.django_db
def test_stale_write_never_overwrites_newer_revision(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    question_key = get_capture_catalog("use_case").required_question_keys[0]
    save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=0,
        answer_updates={question_key: "Aktueller Wert"},
    )

    with pytest.raises(CaptureRevisionConflict, match="zwischenzeitlich geändert"):
        save_capture_session(
            actor=owner,
            session_id=session.pk,
            expected_revision=0,
            answer_updates={question_key: "Veralteter Wert"},
        )

    session.refresh_from_db()
    assert session.answers[question_key] == "Aktueller Wert"
    assert session.revision == 1
    assert session.save_count == 1


@pytest.mark.django_db
def test_read_and_wizard_navigation_do_not_change_revision(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    original_updated_at = session.updated_at

    first_read = get_owned_capture_session(actor=owner, session_id=session.pk)
    second_read = get_owned_capture_session(actor=owner, session_id=session.pk)

    assert first_read.revision == 0
    assert second_read.revision == 0
    assert second_read.updated_at == original_updated_at


@pytest.mark.django_db
def test_foreign_owner_cannot_resolve_session(owner, other_owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )

    with pytest.raises(CaptureSession.DoesNotExist):
        get_owned_capture_session(actor=other_owner, session_id=session.pk)


@pytest.mark.django_db
def test_permission_is_rechecked_for_existing_session(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    owner.groups.clear()

    with pytest.raises(PermissionDenied):
        get_owned_capture_session(actor=owner, session_id=session.pk)


@pytest.mark.django_db
def test_completion_requires_all_required_answers_and_is_irreversible(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )

    with pytest.raises(CaptureAnswerValidationError, match="Pflichtantwort fehlt"):
        complete_capture_session(actor=owner, session_id=session.pk, expected_revision=0)

    session.refresh_from_db()
    assert session.status == CaptureSession.Status.DRAFT
    assert session.revision == 0

    session = save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=0,
        answer_updates=required_answers("use_case"),
    )
    completed = complete_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=session.revision,
    )

    assert completed.status == CaptureSession.Status.COMPLETED
    assert completed.completed_at is not None
    assert completed.revision == 2
    assert completed.answered_required_count == completed.required_question_count

    with pytest.raises(CaptureStateError, match="nicht mehr bearbeitbar"):
        save_capture_session(
            actor=owner,
            session_id=session.pk,
            expected_revision=completed.revision,
            answer_updates={},
        )


@pytest.mark.django_db
def test_discard_is_irreversible_and_does_not_require_supported_catalog(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    CaptureSession.objects.filter(pk=session.pk).update(catalog_version="0.9")

    discarded = discard_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=0,
    )

    assert discarded.status == CaptureSession.Status.DISCARDED
    assert discarded.discarded_at is not None
    assert discarded.revision == 1

    with pytest.raises(CaptureStateError):
        discard_capture_session(
            actor=owner,
            session_id=session.pk,
            expected_revision=1,
        )


@pytest.mark.django_db
def test_supported_stored_catalog_is_used_after_current_version_changes(owner, monkeypatch):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    monkeypatch.setitem(CURRENT_CATALOG_VERSIONS, "value_stream", "2.0")
    question_key = get_capture_catalog("value_stream", "1.0").required_question_keys[0]

    saved = save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=0,
        answer_updates={question_key: "Antwort aus Katalog 1.0"},
    )

    assert saved.catalog_version == "1.0"
    assert saved.answers[question_key] == "Antwort aus Katalog 1.0"


@pytest.mark.django_db
def test_unsupported_stored_catalog_blocks_editing_without_data_change(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    CaptureSession.objects.filter(pk=session.pk).update(catalog_version="0.9")

    with pytest.raises(UnsupportedCaptureCatalog, match="nicht mehr unterstützt"):
        save_capture_session(
            actor=owner,
            session_id=session.pk,
            expected_revision=0,
            answer_updates={},
        )

    session.refresh_from_db()
    assert session.catalog_version == "0.9"
    assert session.revision == 0
    assert session.answers == {}
