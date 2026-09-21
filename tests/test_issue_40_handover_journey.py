import pytest
from django.core.management import call_command
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.core.demo_architecture_data import INVOICE_USE_CASE_KEY
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.services import hand_over_package
from ki_radar.reviews.models import Review
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.workflow import build_delivery_package_journey


def _seed_handed_over_package(settings):
    settings.DEBUG = True
    call_command("seed_demo_data", demo_user_password="Issue-40-Demo-2026!")
    coordinator = User.objects.get(username="demo_ki_koordinator")
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    package = use_case.delivery_packages.get(version=1)
    assert package.status == DeliveryPackage.Status.READY
    hand_over_package(package, coordinator)
    package.refresh_from_db()
    return coordinator, use_case, package


@pytest.mark.django_db
def test_handover_keeps_pilot_start_visible_and_does_not_complete_journey(
    client,
    settings,
):
    coordinator, _use_case, package = _seed_handed_over_package(settings)

    journey = build_delivery_package_journey(package, coordinator)
    steps = {step.key: step for step in journey.steps}

    assert steps["delivery"].state == "complete"
    assert journey.next_action is not None
    assert journey.next_action.key == "pilot_start"
    assert journey.next_action.action_label == "Pilot starten"
    assert journey.completion_message == ""

    client.force_login(coordinator)
    response = client.get(package.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["journey"].next_action.key == "pilot_start"
    assert "Pilot starten" in content
    assert "Journey abgeschlossen" not in content


@pytest.mark.django_db
def test_started_pilot_does_not_complete_overall_journey_on_delivery_page(
    client,
    settings,
):
    coordinator, use_case, package = _seed_handed_over_package(settings)
    pilot_start = timezone.localdate(package.handed_over_at)
    create_review(
        use_case=use_case,
        actor=coordinator,
        data={
            "review_date": timezone.localdate(),
            "pilot_start": pilot_start,
            "decision": Review.Decision.START_PILOT,
            "new_status": UseCase.Status.PILOT,
            "rationale": "Delivery ist übergeben; der Pilot wird fachlich gestartet.",
            "go_live_exception_confirmed": False,
            "open_actions": "",
            "action_owner": None,
            "action_due_date": None,
            "next_review_date": use_case.next_review_date,
        },
    )
    use_case.refresh_from_db()

    journey = build_delivery_package_journey(package, coordinator)

    assert use_case.status == UseCase.Status.PILOT
    assert journey.completion_message == ""

    client.force_login(coordinator)
    response = client.get(package.get_absolute_url())

    assert response.status_code == 200
    assert response.context["journey"].completion_message == ""
    assert "Journey abgeschlossen" not in response.content.decode()
