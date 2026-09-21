from decimal import Decimal

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.core.demo_architecture_data import INVOICE_USE_CASE_KEY
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.services import hand_over_package
from ki_radar.reviews.models import Review
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.models import UseCase


@pytest.fixture
def running_pilot(settings):
    settings.DEBUG = True
    call_command("seed_demo_data", demo_user_password="Issue-42-Demo-2026!")
    coordinator = User.objects.get(username="demo_ki_koordinator")
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    package = use_case.delivery_packages.get(version=1)
    assert package.status == DeliveryPackage.Status.READY

    hand_over_package(package, coordinator)
    package.refresh_from_db()
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
    return coordinator, use_case, pilot_start


@pytest.mark.django_db
def test_running_pilot_is_primary_and_next_gate_is_visible(client, running_pilot):
    coordinator, use_case, _pilot_start = running_pilot
    use_case.one_time_cost = None
    use_case.save(update_fields=["one_time_cost", "updated_at"])
    client.force_login(coordinator)

    response = client.get(reverse("use_cases:detail", kwargs={"pk": use_case.pk}))
    content = response.content.decode()
    gate_codes = {detail.code for detail in response.context["gate_blocker_details"]}

    assert response.status_code == 200
    assert response.context["journey"].next_action.key == "pilot"
    assert response.context["journey"].next_action.action_label == "Pilot öffnen"
    assert response.context["decision_check"].title == "Nächstes Gate: Produktiv setzen"
    assert response.context["decision_check"].state_label == "Pilot läuft"
    assert response.context["blocker_details"] == []
    assert "missing_one_time_cost" not in gate_codes
    assert "Nächstes Gate" in content
    assert "Produktiv setzen" in content
    assert "Readiness offen: Einmalige Kosten" in content
    assert "Produktiv setzen: Blockiert" not in content


@pytest.mark.django_db
def test_register_shows_running_pilot_instead_of_general_blocker(client, running_pilot):
    coordinator, use_case, _pilot_start = running_pilot
    use_case.recurring_cost = None
    use_case.save(update_fields=["recurring_cost", "updated_at"])
    client.force_login(coordinator)

    response = client.get(reverse("use_cases:list"))
    content = response.content.decode()
    row = next(item for item in response.context["use_cases"] if item.pk == use_case.pk)

    assert response.status_code == 200
    assert row.decision_check.title == "Produktiv setzen"
    assert row.register_state_label == "Pilot läuft"
    assert row.register_state == "review"
    assert row.register_state_detail.startswith("Produktivsetzung:")
    assert "Pilot läuft" in content
    assert "Produktivsetzung:" in content


@pytest.mark.django_db
def test_outcome_decision_becomes_primary_only_after_complete_measurement(
    client,
    running_pilot,
):
    coordinator, use_case, pilot_start = running_pilot
    client.force_login(coordinator)

    before = client.get(reverse("use_cases:detail", kwargs={"pk": use_case.pk}))
    assert before.context["journey"].next_action.key == "pilot"

    use_case.metric_actual = Decimal("2.8")
    use_case.metric_measurement_period = "Vier Wochen ab Pilotstart"
    use_case.metric_measured_at = pilot_start
    use_case.metric_evidence_url = "https://example.com/pilot-measurement"
    use_case.save(
        update_fields=[
            "metric_actual",
            "metric_measurement_period",
            "metric_measured_at",
            "metric_evidence_url",
            "updated_at",
        ]
    )

    after = client.get(reverse("use_cases:detail", kwargs={"pk": use_case.pk}))
    steps = {step.key: step for step in after.context["journey"].steps}

    assert after.status_code == 200
    assert steps["pilot"].state == "complete"
    assert steps["measurement"].state == "complete"
    assert steps["outcome_decision"].state == "current"
    assert after.context["journey"].next_action.key == "outcome_decision"
    assert after.context["decision_check"].title == "Produktiv setzen"
