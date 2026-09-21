import pytest
from django.core.management import call_command
from django.urls import reverse

from ki_radar.accounts.models import User
from ki_radar.core.demo_architecture_data import INVOICE_USE_CASE_KEY
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.services import current_decision_check


@pytest.fixture
def lifecycle_case(settings):
    settings.DEBUG = True
    call_command("seed_demo_data", demo_user_password="Issue-41-Demo-2026!")
    coordinator = User.objects.get(username="demo_ki_koordinator")
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    return coordinator, use_case


@pytest.mark.django_db
def test_post_approval_lifecycle_checks_use_distinct_gate_titles(lifecycle_case):
    _coordinator, use_case = lifecycle_case
    expected_titles = {
        UseCase.Status.REVIEW: "Pilot starten",
        UseCase.Status.PILOT: "Produktiv setzen",
        UseCase.Status.OPERATION: "Betrieb fortführen",
        UseCase.Status.ENDED: "Beendet",
    }

    for status, expected_title in expected_titles.items():
        use_case.status = status
        use_case.save(update_fields=["status", "updated_at"])

        assert current_decision_check(use_case).title == expected_title


@pytest.mark.django_db
def test_pilot_detail_labels_open_go_live_requirements_as_lifecycle_gate(
    client,
    lifecycle_case,
):
    coordinator, use_case = lifecycle_case
    use_case.status = UseCase.Status.PILOT
    use_case.one_time_cost = None
    use_case.save(update_fields=["status", "one_time_cost", "updated_at"])
    client.force_login(coordinator)

    response = client.get(reverse("use_cases:detail", kwargs={"pk": use_case.pk}))
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["decision_check"].title == "Produktiv setzen"
    assert response.context["decision_check"].state == "blocked"
    assert '<h2 id="decision-readiness-title">Produktiv setzen</h2>' in content
    assert '<span class="badge state-blocked">Blockiert</span>' in content
    assert "Produktiv setzen · Blockiert" not in content
    assert "Freigabe blockiert" not in content
