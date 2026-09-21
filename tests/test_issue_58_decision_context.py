import pytest
from django.core.management import call_command
from django.urls import reverse

from ki_radar.accounts.models import User
from ki_radar.core.demo_architecture_data import (
    INVOICE_STREAM_NAME,
    INVOICE_USE_CASE_KEY,
)
from ki_radar.use_cases.models import UseCase


@pytest.fixture(autouse=True)
def enable_demo_seed(settings):
    settings.DEBUG = True


@pytest.fixture
def coordinator(db):
    call_command("seed_demo_data", demo_user_password="Issue-58-Context-Demo-2026!")
    return User.objects.get(username="demo_ki_koordinator")


@pytest.fixture
def architecture_use_case(coordinator):
    return UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)


@pytest.mark.django_db
def test_assessment_page_keeps_value_stream_journey_context(
    client,
    coordinator,
    architecture_use_case,
):
    client.force_login(coordinator)

    response = client.get(
        reverse(
            "use_cases:assessment_create",
            kwargs={"pk": architecture_use_case.pk},
        )
    )
    content = response.content.decode()
    journey = response.context["journey"]

    assert response.status_code == 200
    assert INVOICE_STREAM_NAME in journey.path_label
    assert INVOICE_STREAM_NAME in content
    assert "Strukturierte Bewertung" in content
    assert 'aria-label="Lokale Initiative"' in content
    assert 'aria-label="Phasen des Arbeitsmodells"' in content


@pytest.mark.django_db
def test_decision_page_keeps_value_stream_journey_context(
    client,
    coordinator,
    architecture_use_case,
):
    client.force_login(coordinator)

    response = client.get(
        reverse(
            "use_cases:approval_decision_create",
            kwargs={"pk": architecture_use_case.pk},
        )
    )
    content = response.content.decode()
    journey = response.context["journey"]

    assert response.status_code == 200
    assert INVOICE_STREAM_NAME in journey.path_label
    assert INVOICE_STREAM_NAME in content
    assert "Verbindliche Entscheidung" in content
    assert 'aria-label="Lokale Initiative"' in content
    assert 'aria-label="Phasen des Arbeitsmodells"' in content
