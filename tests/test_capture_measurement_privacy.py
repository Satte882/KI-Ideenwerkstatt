from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.services import (
    MAX_ACTIVE_ENTRY_SECONDS_PER_SAVE,
    complete_capture_session,
    create_capture_session,
    save_capture_session,
)


def required_answers(capture_type: str) -> dict[str, str]:
    catalog = get_capture_catalog(capture_type)
    return {key: f"Antwort für {key}" for key in catalog.required_question_keys}


@pytest.mark.django_db
def test_active_entry_seconds_are_accumulated_and_capped_per_save(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    question_key = get_capture_catalog("use_case").required_question_keys[0]

    saved = save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=0,
        answer_updates={question_key: "Erste Antwort"},
        active_entry_seconds_delta=20,
    )
    saved = save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=1,
        answer_updates={},
        active_entry_seconds_delta=999_999,
    )

    assert saved.active_entry_seconds == 20 + MAX_ACTIVE_ENTRY_SECONDS_PER_SAVE
    assert saved.save_count == 2


@pytest.mark.django_db
def test_invalid_active_entry_seconds_do_not_change_session(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )

    with pytest.raises(ValidationError, match="aktive Eingabezeit"):
        save_capture_session(
            actor=owner,
            session_id=session.pk,
            expected_revision=0,
            answer_updates={},
            active_entry_seconds_delta=-1,
        )

    session.refresh_from_db()
    assert session.active_entry_seconds == 0
    assert session.save_count == 0
    assert session.revision == 0
    assert session.answers == {}


@pytest.mark.django_db
def test_calendar_duration_remains_separate_from_active_entry_time(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    old_created_at = timezone.now() - timedelta(days=3)
    CaptureSession.objects.filter(pk=session.pk).update(created_at=old_created_at)
    saved = save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=0,
        answer_updates=required_answers("use_case"),
        active_entry_seconds_delta=120,
    )

    completed = complete_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=saved.revision,
    )
    completed.refresh_from_db()

    assert completed.active_entry_seconds == 120
    assert completed.completed_at is not None
    assert completed.completed_at - completed.created_at > timedelta(days=2)


@pytest.mark.django_db
def test_wizard_remains_functional_without_client_time_measurement(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    question_key = get_capture_catalog("value_stream").sections[0].questions[0].key
    client.force_login(owner)

    response = client.post(
        reverse(
            "accelerator:capture_step",
            kwargs={"session_id": session.pk, "step": 1},
        ),
        {
            "revision": 0,
            question_key: "Antwort ohne JavaScript",
            "action": "save",
        },
    )

    session.refresh_from_db()
    assert response.status_code == 302
    assert session.answers[question_key] == "Antwort ohne JavaScript"
    assert session.active_entry_seconds == 0


@pytest.mark.django_db
def test_wizard_marks_post_data_sensitive_and_persists_only_aggregate_time(
    client,
    owner,
    caplog,
):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    question_key = get_capture_catalog("use_case").sections[0].questions[0].key
    sensitive_answer_text = "Streng vertrauliche Rohantwort 4711"
    client.force_login(owner)

    response = client.post(
        reverse(
            "accelerator:capture_step",
            kwargs={"session_id": session.pk, "step": 1},
        ),
        {
            "revision": 0,
            "active_entry_seconds": 42,
            question_key: sensitive_answer_text,
            "action": "save",
        },
    )

    session.refresh_from_db()
    assert response.status_code == 302
    assert response.wsgi_request.sensitive_post_parameters == "__ALL__"
    assert session.active_entry_seconds == 42
    assert sensitive_answer_text not in caplog.text


def test_active_time_script_collects_no_detailed_user_telemetry():
    script_path = Path(settings.BASE_DIR) / "static" / "js" / "capture-active-time.js"
    script = script_path.read_text(encoding="utf-8")

    assert "data-capture-question" in script
    assert "focusin" in script
    assert "visibilitychange" in script
    assert "submit" in script
    for prohibited_token in (
        "keydown",
        "keyup",
        "keypress",
        "dataLayer",
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
    ):
        assert prohibited_token not in script
