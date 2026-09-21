import pytest
from django.core.management import call_command
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.architecture.models import ProcessAnalysis, SolutionOption, ValueStream
from ki_radar.core.demo_architecture_data import (
    APPLICANT_USE_CASE_KEY,
    CUSTOMER_USE_CASE_KEY,
    DIRECT_INTAKE_KEY,
    DOCUMENT_USE_CASE_KEY,
    INVOICE_USE_CASE_KEY,
    ORDER_STREAM_KEY,
    SUPPLIER_STREAM_KEY,
)
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.workflow import (
    build_process_analysis_journey,
    build_use_case_journey,
)


@pytest.fixture(autouse=True)
def enable_demo_seed(settings):
    settings.DEBUG = True


@pytest.fixture
def seeded_demo(db):
    call_command("seed_demo_data", demo_user_password="Guided-Journey-Demo-2026!")
    return User.objects.get(username="demo_ki_koordinator")


@pytest.mark.django_db
def test_invoice_demo_has_complete_discovery_chain_and_ready_delivery(seeded_demo):
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)

    journey = build_use_case_journey(use_case, seeded_demo)
    steps = {step.key: step for step in journey.steps}

    assert journey.path_label.startswith("Aus Value Stream")
    assert list(steps) == [
        "value_stream",
        "focus",
        "process",
        "solution",
        "use_case",
        "assessment",
        "governance",
        "approval",
        "delivery",
    ]
    assert all(
        steps[key].state == "complete"
        for key in [
            "value_stream",
            "focus",
            "process",
            "solution",
            "use_case",
            "assessment",
            "governance",
            "approval",
        ]
    )
    assert steps["delivery"].state == "current"
    assert journey.next_action == steps["delivery"]
    assert use_case.delivery_packages.get(version=1).status == DeliveryPackage.Status.READY


@pytest.mark.django_db
def test_incomplete_supplier_discovery_points_to_missing_process_information(seeded_demo):
    value_stream = ValueStream.objects.get(demo_key=SUPPLIER_STREAM_KEY)
    process = ProcessAnalysis.objects.get(stage__value_stream=value_stream)

    journey = build_process_analysis_journey(process, seeded_demo)

    assert journey.path_label == "Systematische Discovery"
    assert journey.next_action is not None
    assert journey.next_action.key == "process"
    assert journey.next_action.state == "blocked"
    assert "Datenobjekte und Dokumente" in journey.next_action.details
    assert "Baseline und Prozesskennzahlen" in journey.next_action.details


@pytest.mark.django_db
def test_non_ai_preferred_option_finishes_discovery_without_use_case(seeded_demo):
    value_stream = ValueStream.objects.get(demo_key=ORDER_STREAM_KEY)
    process = ProcessAnalysis.objects.get(stage__value_stream=value_stream)
    preferred = process.solution_options.get(recommendation=SolutionOption.Recommendation.PREFERRED)

    journey = build_process_analysis_journey(process, seeded_demo)
    steps = {step.key: step for step in journey.steps}

    assert preferred.option_type == SolutionOption.OptionType.RULE_AUTOMATION
    assert process.use_case_origins.count() == 0
    assert journey.next_action is None
    assert "Nicht-KI-Lösung" in journey.completion_message
    assert steps["focus"].state == "complete"
    assert steps["use_case"].state == "optional"


@pytest.mark.django_db
def test_direct_intake_with_missing_data_source_is_actionable(seeded_demo):
    use_case = UseCase.objects.get(demo_key=DIRECT_INTAKE_KEY)

    journey = build_use_case_journey(use_case, seeded_demo)
    steps = {step.key: step for step in journey.steps}

    assert journey.path_label == "Direkter Intake"
    assert steps["value_stream"].state == "optional"
    assert steps["focus"].state == "optional"
    assert journey.next_action is not None
    assert journey.next_action.key == "assessment"
    assert journey.next_action.state == "current"
    assert steps["use_case"].state == "complete"


@pytest.mark.django_db
def test_pending_conditional_approval_is_visible_as_next_action(seeded_demo):
    use_case = UseCase.objects.get(demo_key=CUSTOMER_USE_CASE_KEY)

    journey = build_use_case_journey(use_case, seeded_demo)

    assert journey.next_action is not None
    assert journey.next_action.key == "approval"
    assert journey.next_action.state == "blocked"
    assert "zweite unabhängige Bestätigung" in journey.next_action.reason
    assert use_case.approval_decisions.get().is_pending_second_approval is True


@pytest.mark.django_db
def test_stopped_demo_ends_without_delivery_action(seeded_demo):
    use_case = UseCase.objects.get(demo_key=APPLICANT_USE_CASE_KEY)

    journey = build_use_case_journey(use_case, seeded_demo)
    steps = {step.key: step for step in journey.steps}

    assert use_case.decision_status == UseCase.DecisionStatus.NOT_PURSUED
    assert journey.next_action is None
    assert "fachlich beendet" in journey.completion_message
    assert steps["delivery"].state == "optional"


@pytest.mark.django_db
def test_handed_over_demo_is_a_consistent_running_pilot(seeded_demo):
    use_case = UseCase.objects.get(demo_key=DOCUMENT_USE_CASE_KEY)
    package = use_case.delivery_packages.get(version=1)

    journey = build_use_case_journey(use_case, seeded_demo)

    assert package.status == DeliveryPackage.Status.HANDED_OVER
    assert package.external_delivery_url
    assert use_case.status == UseCase.Status.PILOT
    assert use_case.pilot_start == timezone.localdate(package.handed_over_at)
    assert all(step.key != "pilot_start" for step in journey.steps)


@pytest.mark.django_db
def test_demo_key_survives_title_change_and_cleanup(seeded_demo):
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    original_pk = use_case.pk
    use_case.title = "Temporär umbenannter Demo-Fall"
    use_case.save(update_fields=["title", "updated_at"])

    call_command("seed_demo_data", demo_user_password="Guided-Journey-Demo-2026!")

    restored = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    assert restored.pk == original_pk
    assert restored.title == "[DEMO] Automatische Rechnungspruefung"
    assert UseCase.objects.filter(demo_key=INVOICE_USE_CASE_KEY).count() == 1

    call_command("clear_demo_data")
    assert UseCase.objects.filter(pk=original_pk).exists() is False


@pytest.mark.django_db
def test_guided_components_are_visible_on_detail_pages(client, seeded_demo):
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    supplier_process = ProcessAnalysis.objects.get(
        stage__value_stream__demo_key=SUPPLIER_STREAM_KEY
    )
    client.force_login(seeded_demo)

    use_case_response = client.get(use_case.get_absolute_url())
    process_response = client.get(supplier_process.get_absolute_url())
    dashboard_response = client.get("/")

    assert use_case_response.status_code == 200
    assert process_response.status_code == 200
    assert dashboard_response.status_code == 200
    use_case_content = use_case_response.content.decode()
    assert 'id="decision-state"' in use_case_content
    assert 'id="lifecycle-orientation"' in use_case_content
    assert "Nächster Schritt" in process_response.content.decode()
    assert "Meine Aufgaben" in dashboard_response.content.decode()
