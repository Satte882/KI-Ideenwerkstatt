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
def test_use_case_capture_start_uses_existing_permission(client, owner, reader):
    url = reverse("accelerator:use_case_start")

    client.force_login(reader)
    assert client.get(url).status_code == 403
    assert client.post(url, {"working_title": "Nicht erlaubt"}).status_code == 403
    assert CaptureSession.objects.count() == 0

    client.force_login(owner)
    response = client.post(url, {"working_title": "Angebotsvergleich"})

    session = CaptureSession.objects.get()
    assert response.status_code == 302
    assert response.url == reverse(
        "accelerator:capture_step",
        kwargs={"session_id": session.pk, "step": 1},
    )
    assert session.capture_type == CaptureSession.CaptureType.USE_CASE
    assert session.owner == owner


@pytest.mark.django_db
def test_use_case_wizard_uses_native_textareas_and_use_case_labels(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Angebotsvergleich",
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
    assert "Geführte Use-Case-Erfassung" in content
    assert "welches konkrete Problem" in content
    assert "<textarea" in content
    assert "contenteditable" not in content
    assert "oninput=" not in content
    assert "onkeydown=" not in content
    assert reverse("use_cases:list") in content


@pytest.mark.django_db
def test_use_case_wizard_saves_and_moves_to_next_section(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    client.force_login(owner)
    first_question = get_capture_catalog("use_case").sections[0].questions[0]

    response = client.post(
        reverse(
            "accelerator:capture_step",
            kwargs={"session_id": session.pk, "step": 1},
        ),
        {
            "revision": 0,
            first_question.key: "  Manueller Angebotsvergleich dauert zu lange.  ",
            "action": "next",
        },
    )

    session.refresh_from_db()
    assert response.status_code == 302
    assert response.url == reverse(
        "accelerator:capture_step",
        kwargs={"session_id": session.pk, "step": 2},
    )
    assert session.answers[first_question.key] == "Manueller Angebotsvergleich dauert zu lange."
    assert session.revision == 1


@pytest.mark.django_db
def test_use_case_capture_completes_without_creating_domain_objects(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Angebotsvergleich",
    )
    session = save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=0,
        answer_updates=required_answers("use_case"),
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
    assert UseCase.objects.count() == 0
    assert ValueStream.objects.count() == 0

    review = client.get(reverse("accelerator:capture_review", kwargs={"session_id": session.pk}))
    content = review.content.decode()
    assert "Geführte Use-Case-Erfassung" in content
    assert "keine Fachobjekte" in content
    assert reverse("use_cases:list") in content


@pytest.mark.django_db
def test_existing_direct_use_case_intake_remains_available(client, owner):
    client.force_login(owner)

    response = client.get(reverse("use_cases:create"))

    assert response.status_code == 200
    assert "Problem verstehen" in response.content.decode()
    assert CaptureSession.objects.count() == 0
    assert UseCase.objects.count() == 0


@pytest.mark.django_db
def test_value_stream_and_use_case_capture_use_their_own_overview_links(client, owner):
    value_stream = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    use_case = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    client.force_login(owner)

    value_stream_response = client.get(
        reverse(
            "accelerator:capture_step",
            kwargs={"session_id": value_stream.pk, "step": 1},
        )
    )
    use_case_response = client.get(
        reverse(
            "accelerator:capture_step",
            kwargs={"session_id": use_case.pk, "step": 1},
        )
    )

    assert reverse("architecture:value_stream_list") in value_stream_response.content.decode()
    assert reverse("use_cases:list") in use_case_response.content.decode()
