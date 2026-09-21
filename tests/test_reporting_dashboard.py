import pytest
from django.urls import reverse

from ki_radar.use_cases.models import UseCase


@pytest.mark.django_db
def test_dashboard_handles_active_use_case_without_decision_due_date(
    client, coordinator, owner, business_unit
):
    UseCase.objects.create(
        title="Use Case ohne Review-Datum",
        problem_statement="Ein frueher Ideenstand hat noch keinen Termin.",
        business_unit=business_unit,
        affected_process="Anfrageprozess",
        business_owner=owner,
        coordinator=coordinator,
        expected_benefit="Bessere Priorisierung",
        status=UseCase.Status.REVIEW,
    )
    client.force_login(coordinator)

    response = client.get(reverse("reporting:dashboard"))

    assert response.status_code == 200
    assert response.context["overdue_total"] == 0
    assert response.context["due_soon_total"] == 0
