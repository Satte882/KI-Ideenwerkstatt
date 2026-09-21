import pytest
from django.urls import reverse

from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.services import create_capture_session, save_capture_session
from ki_radar.architecture.models import ValueStream
from ki_radar.use_cases.models import UseCase


def required_answers(capture_type: str) -> dict[str, str]:
    catalog = get_capture_catalog(capture_type)
    return {key: f"Antwort für {key}" for key in catalog.required_question_keys}


@pytest.mark.django_db
def test_value_stream_capture_start_requires_existing_permission(client, owner, reader):
    url = reverse("accelerator:value_stream_start")

    client.force_login(reader)
    assert client.get(url).status_code == 403
    assert client.post(url, {"working_title": "Nicht erlaubt"}).status_code == 403
    assert CaptureSession.objects.count() == 0

    client.force_login(owner)
    response = client.post(url, {"working_title": "Beschaffung"})

    session = CaptureSession.objects.get()
    assert response.status_code == 302
    assert response.url == reverse(
        "accelerator:capture_step",
        kwargs={"session_id": session.pk, "step": 1},
    )
    assert session.capture_type == CaptureSession.CaptureType.VALUE_STREAM
    assert session.owner == owner


@pytest.mark.django_db
def test_wizard_uses_native_semantic_textareas_without_custom_input_control(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Beschaffung",
    )
    client.force_login(owner)

    response = client.get(
        reverse(
            "accelerator:capture_step",
            kwargs={"session_id": session.pk, "step": 1},
        )
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "<textarea" in content
    assert "data-capture-question=" in content
    assert "contenteditable" not in content
    assert "oninput=" not in content
    assert "onkeydown=" not in content
    assert "<label" in content


@pytest.mark.django_db
def test_wizard_saves_section_and_moves_forward(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    client.force_login(owner)
    first_section = get_capture_catalog("value_stream").sections[0]
    first_question = first_section.questions[0]

    response = client.post(
        reverse(
            "accelerator:capture_step",
            kwargs={"session_id": session.pk, "step": 1},
        ),
        {
            "revision": 0,
            first_question.key: "  Beschaffung bis Bestellung  ",
            "action": "next",
        },
    )

    session.refresh_from_db()
    assert response.status_code == 302
    assert response.url == reverse(
        "accelerator:capture_step",
        kwargs={"session_id": session.pk, "step": 2},
    )
    assert session.answers[first_question.key] == "Beschaffung bis Bestellung"
    assert session.revision == 1
    assert session.save_count == 1


@pytest.mark.django_db
def test_get_navigation_between_wizard_steps_does_not_change_revision(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    original_updated_at = session.updated_at
    client.force_login(owner)

    for step in (1, 2, 1):
        response = client.get(
            reverse(
                "accelerator:capture_step",
                kwargs={"session_id": session.pk, "step": step},
            )
        )
        assert response.status_code == 200

    session.refresh_from_db()
    assert session.revision == 0
    assert session.save_count == 0
    assert session.updated_at == original_updated_at


@pytest.mark.django_db
def test_stale_wizard_post_returns_conflict_without_overwrite(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    question_key = get_capture_catalog("value_stream").sections[0].questions[0].key
    save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=0,
        answer_updates={question_key: "Aktueller Wert"},
    )
    client.force_login(owner)

    response = client.post(
        reverse(
            "accelerator:capture_step",
            kwargs={"session_id": session.pk, "step": 1},
        ),
        {
            "revision": 0,
            question_key: "Veralteter Wert",
            "action": "save",
        },
    )

    session.refresh_from_db()
    assert response.status_code == 409
    assert "Zwischenzeitliche Änderung erkannt" in response.content.decode()
    assert session.answers[question_key] == "Aktueller Wert"
    assert session.revision == 1


@pytest.mark.django_db
def test_review_blocks_incomplete_completion_without_creating_domain_objects(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    client.force_login(owner)

    response = client.post(
        reverse("accelerator:capture_review", kwargs={"session_id": session.pk}),
        {"revision": 0, "action": "complete"},
    )

    session.refresh_from_db()
    assert response.status_code == 200
    assert "kann noch nicht abgeschlossen werden" in response.content.decode()
    assert session.status == CaptureSession.Status.DRAFT
    assert ValueStream.objects.count() == 0
    assert UseCase.objects.count() == 0


@pytest.mark.django_db
def test_complete_value_stream_capture_is_immutable_and_creates_no_domain_object(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    session = save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=0,
        answer_updates=required_answers("value_stream"),
    )
    client.force_login(owner)

    response = client.post(
        reverse("accelerator:capture_review", kwargs={"session_id": session.pk}),
        {"revision": session.revision, "action": "complete"},
    )

    session.refresh_from_db()
    assert response.status_code == 302
    assert session.status == CaptureSession.Status.COMPLETED
    assert session.completed_at is not None
    assert ValueStream.objects.count() == 0
    assert UseCase.objects.count() == 0

    wizard_response = client.get(
        reverse(
            "accelerator:capture_step",
            kwargs={"session_id": session.pk, "step": 1},
        )
    )
    assert wizard_response.status_code == 302
    assert wizard_response.url == reverse(
        "accelerator:capture_review",
        kwargs={"session_id": session.pk},
    )


@pytest.mark.django_db
def test_foreign_capture_sessions_are_not_exposed(client, owner, other_owner):
    value_stream = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    use_case = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )

    client.force_login(other_owner)
    for session in (value_stream, use_case):
        assert (
            client.get(
                reverse(
                    "accelerator:capture_step",
                    kwargs={"session_id": session.pk, "step": 1},
                )
            ).status_code
            == 404
        )


@pytest.mark.django_db
def test_unsupported_catalog_is_shown_read_only(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    CaptureSession.objects.filter(pk=session.pk).update(catalog_version="0.9")
    client.force_login(owner)

    step_response = client.get(
        reverse(
            "accelerator:capture_step",
            kwargs={"session_id": session.pk, "step": 1},
        )
    )
    review_response = client.get(
        reverse("accelerator:capture_review", kwargs={"session_id": session.pk})
    )

    assert step_response.status_code == 302
    assert review_response.status_code == 200
    assert "Katalogversion nicht verfügbar" in review_response.content.decode()
    assert "Erfassung abschließen" not in review_response.content.decode()
