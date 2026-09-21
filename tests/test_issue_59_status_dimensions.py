import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.core.demo_architecture_data import INVOICE_USE_CASE_KEY
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.governance.services import create_screening_review_artifacts
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.status_dimensions import (
    build_use_case_status_dimensions,
    current_work_check,
)
from ki_radar.use_cases.workflow import build_use_case_journey


@pytest.fixture(autouse=True)
def enable_demo_seed(settings):
    settings.DEBUG = True


@pytest.fixture
def coordinator(db):
    call_command("seed_demo_data", demo_user_password="Issue-59-Status-Demo-2026!")
    return User.objects.get(username="demo_ki_koordinator")


@pytest.fixture
def use_case(coordinator):
    return UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)


def _remove_decision_chain(use_case):
    use_case.delivery_packages.all().delete()
    use_case.approval_decisions.all().delete()
    use_case.decision_assessments.all().delete()


def _set_open_privacy_review(use_case, coordinator):
    use_case.governance_reviews.all().delete()
    use_case.governance_assessments.all().delete()
    screening = GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=coordinator,
        basis_version="Issue 59",
        privacy_review_required=True,
        result=GovernanceAssessment.Result.PRIVACY,
        privacy_review_rationale="Datenschutzprüfung ist für diesen Test erforderlich.",
    )
    create_screening_review_artifacts(assessment=screening, actor=coordinator)


@pytest.mark.django_db
def test_complete_intake_without_assessment_is_only_assessment_ready(coordinator, use_case):
    _remove_decision_chain(use_case)
    use_case.status = UseCase.Status.IDEA
    use_case.decision_status = UseCase.DecisionStatus.READY
    use_case.save(update_fields=["status", "decision_status", "updated_at"])

    check = current_work_check(use_case)
    journey = build_use_case_journey(use_case, coordinator)
    dimensions = build_use_case_status_dimensions(use_case, journey)

    assert check.title == "Bewertung anlegen"
    assert check.state_label == "Bewertungsbereit"
    assert dimensions.assessment.label == "Bewertungsbereit"
    assert dimensions.approval.label == "Bewertung erforderlich"
    assert dimensions.lifecycle.label == "Idee"


@pytest.mark.django_db
def test_assessment_with_open_governance_keeps_approval_actionable(coordinator, use_case):
    use_case.delivery_packages.all().delete()
    use_case.approval_decisions.all().delete()
    use_case.status = UseCase.Status.IDEA
    use_case.save(update_fields=["status", "updated_at"])
    _set_open_privacy_review(use_case, coordinator)

    check = current_work_check(use_case)
    journey = build_use_case_journey(use_case, coordinator)
    dimensions = build_use_case_status_dimensions(use_case, journey)

    assert dimensions.assessment.label == "Bewertung v1 vorhanden"
    assert check.state_label == "Entscheidung möglich"
    assert any("Readiness offen: Datenschutzprüfung" in item for item in check.warnings)
    assert dimensions.approval.label == "Entscheidung möglich"
    assert dimensions.measurement.label != dimensions.lifecycle.label


@pytest.mark.django_db
def test_final_approval_remains_separate_from_lifecycle_and_measurement(coordinator, use_case):
    journey = build_use_case_journey(use_case, coordinator)
    dimensions = build_use_case_status_dimensions(use_case, journey)

    assert dimensions.assessment.label == "Bewertung v1 vorhanden"
    assert dimensions.approval.label == "Freigegeben"
    assert dimensions.lifecycle.label == use_case.get_status_display()
    assert dimensions.measurement.label == use_case.metric_result_label
    assert dimensions.next_lifecycle_decision


@pytest.mark.django_db
def test_detail_page_consolidates_status_dimensions_into_authoritative_sections(
    client, coordinator, use_case
):
    client.force_login(coordinator)

    response = client.get(reverse("use_cases:detail", kwargs={"pk": use_case.pk}))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Aktueller Arbeitszustand" not in content
    assert 'id="status-dimensions"' not in content
    assert content.count("Nächste Lifecycle-Entscheidung") == 1
    assert 'aria-label="Lifecycle-Orientierung"' in content
    assert "Belastbare Freigabeentscheidung" in content
    assert "Primäre Erfolgsmetrik" in content
