import pytest
from django.core.management import call_command
from django.urls import reverse

from ki_radar.accounts.models import User
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage
from ki_radar.core.demo_architecture_data import INVOICE_USE_CASE_KEY
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.workflow import build_value_stream_journey


@pytest.fixture(autouse=True)
def enable_demo_seed(settings):
    settings.DEBUG = True


@pytest.fixture
def coordinator(db):
    call_command("seed_demo_data", demo_user_password="Issue-58-Demo-2026!")
    return User.objects.get(username="demo_ki_koordinator")


def _selected_value_stream(coordinator, *, status: str) -> ValueStream:
    reference = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    value_stream = ValueStream.objects.create(
        name="Test Value Stream für Issue 58",
        description="Testfall für die geführte Phasenerfassung.",
        business_unit=reference.business_unit,
        owner=reference.business_owner,
        created_by=coordinator,
        trigger="Ein Bedarf liegt vor.",
        outcome="Ein Ergebnis wurde erzeugt.",
        scope_in="Vom Bedarf bis zum Ergebnis.",
        status=status,
    )
    ValueStreamFocus.objects.create(
        value_stream=value_stream,
        business_domain=BusinessDomain.PROCUREMENT,
        capability="Test Capability",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.MEDIUM,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Der Value Stream wurde für die Prozessanalyse ausgewählt.",
        updated_by=coordinator,
    )
    ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Bedarf aufnehmen",
        description="Den Bedarf strukturiert aufnehmen.",
        actors="Fachbereich",
        systems="Formular",
        documents="Bedarfsbeschreibung",
        pain_points="Unvollständige Angaben",
        baseline_metrics="Zehn Minuten je Vorgang",
    )
    return value_stream


@pytest.mark.django_db
def test_draft_value_stream_keeps_phase_completion_as_next_action(coordinator):
    value_stream = _selected_value_stream(coordinator, status=ValueStream.Status.DRAFT)

    journey = build_value_stream_journey(value_stream, coordinator)
    steps = {step.key: step for step in journey.steps}

    assert journey.next_action == steps["value_stream"]
    assert journey.next_action.state == "current"
    assert journey.next_action.action_label == "Phase ergänzen"
    assert journey.next_action.url == reverse(
        "architecture:stage_create",
        kwargs={"stream_pk": value_stream.pk},
    )
    assert steps["process"].state == "upcoming"
    assert "Abschluss der Phasenerfassung" in steps["process"].reason


@pytest.mark.django_db
def test_active_value_stream_requires_explicit_focus_stage_selection(coordinator):
    value_stream = _selected_value_stream(coordinator, status=ValueStream.Status.ACTIVE)

    journey = build_value_stream_journey(value_stream, coordinator)
    steps = {step.key: step for step in journey.steps}

    assert journey.next_action == steps["process"]
    assert journey.next_action.action_label == "Fokusphase auswählen"
    assert journey.next_action.url == f"{value_stream.get_absolute_url()}#end-to-end-phasen"
    assert "bewusst die Phase" in journey.next_action.reason


@pytest.mark.django_db
def test_value_stream_page_disables_process_analysis_while_phase_structure_is_draft(
    client,
    coordinator,
):
    value_stream = _selected_value_stream(coordinator, status=ValueStream.Status.DRAFT)
    client.force_login(coordinator)

    response = client.get(value_stream.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert "Phasenerfassung noch offen" in content
    assert "Erst Phasenerfassung abschließen" in content
    assert "Prozess im Detail analysieren" not in content
    assert "Use Case direkt aus Phase ableiten" not in content


@pytest.mark.django_db
def test_direct_process_url_cannot_bypass_draft_phase_gate(client, coordinator):
    value_stream = _selected_value_stream(coordinator, status=ValueStream.Status.DRAFT)
    stage = value_stream.stages.get()
    client.force_login(coordinator)

    response = client.get(
        reverse(
            "architecture:process_analysis_create",
            kwargs={"stage_id": stage.pk},
        )
    )

    assert response.status_code == 302
    assert response.url == value_stream.get_absolute_url()
    assert ProcessAnalysis.objects.filter(stage=stage).exists() is False


@pytest.mark.django_db
def test_active_value_stream_page_offers_stage_choice_without_preselecting_first_stage(
    client,
    coordinator,
):
    value_stream = _selected_value_stream(coordinator, status=ValueStream.Status.ACTIVE)
    client.force_login(coordinator)

    response = client.get(value_stream.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert "Fokusphase auswählen" in content
    assert "Prozess im Detail analysieren" in content
    assert "Value Stream bearbeiten" in content
    assert "Abgekürzter Pfad ohne Prozessanalyse und Lösungsvergleich" in content
