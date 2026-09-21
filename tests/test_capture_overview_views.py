import pytest
from django.urls import reverse

from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.services import create_capture_session


@pytest.mark.django_db
def test_capture_list_shows_only_own_sessions_and_keeps_parallel_drafts_distinct(
    client,
    owner,
    other_owner,
):
    first = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Angebotsvergleich A",
    )
    second = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Angebotsvergleich B",
    )
    value_stream = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Beschaffung",
    )
    foreign = create_capture_session(
        actor=other_owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Fremder Entwurf",
    )
    client.force_login(owner)

    response = client.get(reverse("accelerator:capture_list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Angebotsvergleich A" in content
    assert "Angebotsvergleich B" in content
    assert "Beschaffung" in content
    assert "Fremder Entwurf" not in content
    assert str(first.pk)[:8] in content
    assert str(second.pk)[:8] in content
    assert str(value_stream.pk)[:8] in content
    assert str(foreign.pk)[:8] not in content
    assert content.count("Fortsetzen") == 3


@pytest.mark.django_db
def test_capture_list_rechecks_current_capture_permission(client, reader):
    client.force_login(reader)

    response = client.get(reverse("accelerator:capture_list"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_value_stream_list_exposes_guided_start_and_own_draft_count(client, owner):
    create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Erster Value Stream",
    )
    create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Zweiter Value Stream",
    )
    client.force_login(owner)

    response = client.get(reverse("architecture:value_stream_list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert reverse("accelerator:value_stream_start") in content
    assert reverse("accelerator:capture_list") in content
    assert "Meine Erfassungen (2)" in content
    assert "2 offene Value-Stream-Entwürfe" in content
    assert reverse("architecture:value_stream_create") in content


@pytest.mark.django_db
def test_use_case_list_exposes_guided_start_and_own_draft_count(client, owner):
    create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Use Case A",
    )
    create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Use Case B",
    )
    create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Value Stream A",
    )
    client.force_login(owner)

    response = client.get(reverse("use_cases:list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert reverse("accelerator:use_case_start") in content
    assert reverse("accelerator:capture_list") in content
    assert "Meine Erfassungen (3)" in content
    assert "2 offene Use-Case-Entwürfe" in content
    assert reverse("use_cases:create") in content


@pytest.mark.django_db
def test_foreign_drafts_do_not_affect_list_counts(client, owner, other_owner):
    create_capture_session(
        actor=other_owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Fremder Use Case",
    )
    client.force_login(owner)

    use_case_response = client.get(reverse("use_cases:list"))
    value_stream_response = client.get(reverse("architecture:value_stream_list"))

    assert "Meine Erfassungen" not in use_case_response.content.decode()
    assert "Meine Erfassungen" not in value_stream_response.content.decode()
