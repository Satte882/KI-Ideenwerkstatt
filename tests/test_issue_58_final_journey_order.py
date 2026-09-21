import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.accounts.permissions import GROUP_COORDINATOR
from ki_radar.core.demo_architecture_data import INVOICE_STREAM_NAME, INVOICE_USE_CASE_KEY
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.workflow import build_use_case_journey


@pytest.fixture(autouse=True)
def enable_demo_seed(settings):
    settings.DEBUG = True


@pytest.fixture
def coordinator(db):
    call_command("seed_demo_data", demo_user_password="Issue-58-Final-Demo-2026!")
    return User.objects.get(username="demo_ki_koordinator")


@pytest.fixture
def independent_coordinator(coordinator):
    user = User.objects.create_user(
        username="issue58_final_coordinator",
        password="Issue-58-Final-Independent-2026!",
        first_name="Alex",
        last_name="Journey",
    )
    user.groups.add(Group.objects.get(name=GROUP_COORDINATOR))
    return user


@pytest.fixture
def assessed_use_case(coordinator):
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    use_case.delivery_packages.all().delete()
    use_case.approval_decisions.all().delete()
    use_case.governance_reviews.all().delete()
    use_case.governance_assessments.all().delete()
    use_case.status = UseCase.Status.IDEA
    use_case.decision_status = UseCase.DecisionStatus.READY
    use_case.privacy_review_required = False
    use_case.privacy_review_completed = False
    use_case.security_review_required = False
    use_case.security_review_completed = False
    use_case.legal_review_required = False
    use_case.legal_review_completed = False
    use_case.save()
    return use_case


def _screening(use_case, coordinator, *, privacy_required=False):
    screening = GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=coordinator,
        basis_version="Governance-Leitlinie 1.0",
        privacy_review_required=privacy_required,
        result=GovernanceAssessment.Result.CLARIFICATION,
        rationale="Screening für die abschließende Journey-Abnahme.",
    )
    use_case.privacy_review_required = privacy_required
    use_case.privacy_review_completed = False
    use_case.save()
    return screening


@pytest.mark.django_db
def test_assessment_is_followed_by_governance_screening(assessed_use_case, independent_coordinator):
    journey = build_use_case_journey(assessed_use_case, independent_coordinator)
    steps = {step.key: step for step in journey.steps}
    keys = [step.key for step in journey.steps]

    assert keys.index("assessment") < keys.index("governance") < keys.index("approval")
    assert journey.next_action == steps["governance"]
    assert steps["governance"].state == "current"
    assert steps["governance"].action_label == "Governance-Screening durchführen"
    assert steps["approval"].state == "current"


@pytest.mark.django_db
def test_required_governance_review_is_readiness_for_approval(
    assessed_use_case, coordinator, independent_coordinator
):
    _screening(assessed_use_case, coordinator, privacy_required=True)

    journey = build_use_case_journey(assessed_use_case, independent_coordinator)
    steps = {step.key: step for step in journey.steps}

    assert journey.next_action == steps["governance"]
    assert steps["governance"].state == "current"
    assert steps["governance"].action_label == "Datenschutzprüfung durchführen"
    assert steps["governance"].details == ("Datenschutzprüfung",)
    assert steps["approval"].state == "current"


@pytest.mark.django_db
def test_completed_governance_advances_to_approval(
    assessed_use_case, coordinator, independent_coordinator
):
    _screening(assessed_use_case, coordinator)

    journey = build_use_case_journey(assessed_use_case, independent_coordinator)
    steps = {step.key: step for step in journey.steps}

    assert steps["governance"].state == "complete"
    assert journey.next_action == steps["approval"]
    assert steps["approval"].state == "current"


@pytest.mark.django_db
def test_final_positive_approval_advances_to_delivery(coordinator):
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    use_case.delivery_packages.all().delete()

    journey = build_use_case_journey(use_case, coordinator)
    steps = {step.key: step for step in journey.steps}

    assert steps["assessment"].state == "complete"
    assert steps["governance"].state == "complete"
    assert steps["approval"].state == "complete"
    assert journey.next_action == steps["delivery"]
    assert steps["delivery"].state == "current"


@pytest.mark.django_db
def test_governance_workspace_keeps_value_stream_and_local_journey_context(
    client, assessed_use_case, coordinator, independent_coordinator
):
    _screening(assessed_use_case, coordinator, privacy_required=True)
    client.force_login(independent_coordinator)

    response = client.get(
        reverse(
            "governance:review",
            kwargs={"use_case_id": assessed_use_case.pk, "review_type": "privacy"},
        )
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert INVOICE_STREAM_NAME in content
    assert "Governance" in content
    assert 'aria-label="Lokale Initiative"' in content
    assert 'aria-label="Phasen des Arbeitsmodells"' in content
    assert "sidebar-local-current" in content
