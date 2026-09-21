import pytest
from django.core.management import call_command
from django.urls import reverse

from ki_radar.accounts.models import User
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.demo_architecture_data import INVOICE_USE_CASE_KEY
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.workflow import build_process_analysis_journey


@pytest.fixture(autouse=True)
def enable_demo_seed(settings):
    settings.DEBUG = True


@pytest.fixture
def coordinator(db):
    call_command("seed_demo_data", demo_user_password="Issue-58-Solution-Demo-2026!")
    return User.objects.get(username="demo_ki_koordinator")


def _complete_process(coordinator) -> ProcessAnalysis:
    reference = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    value_stream = ValueStream.objects.create(
        name="Test Value Stream für Lösungsoptionen",
        description="Testfall für die geführte Lösungswahl.",
        business_unit=reference.business_unit,
        owner=reference.business_owner,
        created_by=coordinator,
        trigger="Ein Bedarf liegt vor.",
        outcome="Ein Ergebnis wurde erzeugt.",
        scope_in="Vom Bedarf bis zum Ergebnis.",
        status=ValueStream.Status.ACTIVE,
    )
    ValueStreamFocus.objects.create(
        value_stream=value_stream,
        business_domain=BusinessDomain.PROCUREMENT,
        capability="Lösungswahl testen",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.MEDIUM,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Der Value Stream wurde für die Lösungswahl ausgewählt.",
        updated_by=coordinator,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Vorgang bearbeiten",
        description="Den Vorgang fachlich bearbeiten.",
        actors="Fachbereich",
        systems="Fachanwendung",
        documents="Vorgangsdaten",
        pain_points="Manuelle Nacharbeit",
        baseline_metrics="Zwanzig Minuten je Vorgang",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Vorgangsbearbeitung",
        status=ProcessAnalysis.Status.TARGET_DEFINED,
        scope_start="Der Vorgang geht ein.",
        scope_end="Der Vorgang ist abgeschlossen.",
        trigger="Eingang eines Vorgangs.",
        outcome="Nachvollziehbar bearbeiteter Vorgang.",
        current_flow="Vorgang prüfen, bearbeiten und dokumentieren.",
        roles="Fachbereich bearbeitet und bestätigt.",
        systems="Fachanwendung und Dateiablage.",
        data_objects="Vorgang, Nachweis und Entscheidung.",
        business_rules="Pflichtangaben müssen vollständig sein.",
        handoffs="Rückfragen gehen an den Antragsteller.",
        bottlenecks="Unvollständige Angaben verursachen Nacharbeit.",
        exceptions="Sonderfälle benötigen eine manuelle Prüfung.",
        baseline_metrics="Zwanzig Minuten je Vorgang.",
        target_state_principles=(
            "Einfache Fälle standardisieren, Entscheidungen beim Menschen belassen."
        ),
        analyzed_by=coordinator,
    )


def _candidate_option(process: ProcessAnalysis, coordinator) -> SolutionOption:
    return SolutionOption.objects.create(
        process_analysis=process,
        name="Regelbasierte Vorprüfung",
        option_type=SolutionOption.OptionType.RULE_AUTOMATION,
        recommendation=SolutionOption.Recommendation.CANDIDATE,
        description="Pflichtangaben regelbasiert prüfen.",
        expected_value="Nacharbeit früh reduzieren.",
        feasibility="high",
        data_requirements="Strukturierte Vorgangsdaten.",
        application_impact="Ergänzung der Fachanwendung.",
        integration_impact="Keine zusätzliche Integration.",
        technology_constraints="Regeln müssen nachvollziehbar bleiben.",
        risks="Sonderfälle dürfen nicht abgewiesen werden.",
        architecture_fit="Geeignet für eindeutige Pflichtprüfungen.",
        created_by=coordinator,
    )


@pytest.mark.django_db
def test_complete_process_without_options_points_to_first_option(coordinator):
    process = _complete_process(coordinator)

    journey = build_process_analysis_journey(process, coordinator)
    steps = {step.key: step for step in journey.steps}

    assert journey.next_action == steps["solution"]
    assert journey.next_action.action_label == "Erste Lösungsoption ergänzen"
    assert journey.next_action.url == reverse(
        "architecture:solution_option_create",
        kwargs={"process_pk": process.pk},
    )
    assert "Noch keine Lösungsoption" in journey.next_action.reason
    assert steps["use_case"].state == "upcoming"


@pytest.mark.django_db
def test_candidate_option_keeps_solution_choice_current(coordinator):
    process = _complete_process(coordinator)
    _candidate_option(process, coordinator)

    journey = build_process_analysis_journey(process, coordinator)
    steps = {step.key: step for step in journey.steps}

    assert journey.next_action == steps["solution"]
    assert journey.next_action.action_label == "Lösungsoptionen vergleichen"
    assert journey.next_action.url == reverse(
        "architecture:solution_option_compare", kwargs={"pk": process.pk}
    )
    assert "1 Lösungsoption liegt vor" in journey.next_action.reason
    assert steps["use_case"].state == "upcoming"


@pytest.mark.django_db
def test_preferred_ai_option_advances_to_use_case(coordinator):
    process = _complete_process(coordinator)
    option = _candidate_option(process, coordinator)
    option.option_type = SolutionOption.OptionType.ASSISTANT
    option.recommendation = SolutionOption.Recommendation.PREFERRED
    option.save(update_fields=["option_type", "recommendation", "updated_at"])

    journey = build_process_analysis_journey(process, coordinator)
    steps = {step.key: step for step in journey.steps}

    assert steps["solution"].state == "complete"
    assert journey.next_action == steps["use_case"]
    assert journey.next_action.state == "current"


@pytest.mark.django_db
def test_preferred_non_ai_option_finishes_discovery_without_forcing_use_case(coordinator):
    process = _complete_process(coordinator)
    option = _candidate_option(process, coordinator)
    option.recommendation = SolutionOption.Recommendation.PREFERRED
    option.save(update_fields=["recommendation", "updated_at"])

    journey = build_process_analysis_journey(process, coordinator)
    steps = {step.key: step for step in journey.steps}

    assert option.starts_ai_use_case is False
    assert steps["solution"].state == "complete"
    assert steps["use_case"].state == "optional"
    assert journey.next_action is None
    assert "Nicht-KI-Lösung" in journey.completion_message


@pytest.mark.django_db
def test_first_option_action_is_visible_on_process_page(client, coordinator):
    process = _complete_process(coordinator)
    client.force_login(coordinator)

    response = client.get(process.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert 'id="loesungsoptionen"' in content
    assert content.count("Erste Lösungsoption ergänzen") == 1
    assert "Erste Option ergänzen" not in content
    assert "Weitere Option ergänzen" not in content


@pytest.mark.django_db
def test_candidate_options_are_guided_to_comparison_page(client, coordinator):
    process = _complete_process(coordinator)
    _candidate_option(process, coordinator)
    client.force_login(coordinator)

    response = client.get(process.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert "Lösungsoptionen vergleichen" in content
    assert "Lösungsentscheidung offen" in content
    assert "Weitere Option ergänzen" in content
    assert "Erste Option ergänzen" not in content
    assert "Lösungsoptionen vergleichen" in content
