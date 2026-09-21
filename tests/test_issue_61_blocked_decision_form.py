import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.accounts.permissions import GROUP_COORDINATOR
from ki_radar.core.demo_architecture_data import INVOICE_USE_CASE_KEY
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.governance.services import create_screening_review_artifacts
from ki_radar.use_cases.models import UseCase


@pytest.fixture(autouse=True)
def enable_demo_seed(settings):
    settings.DEBUG = True


def _set_governance_screening(use_case, *, privacy_required=False):
    use_case.governance_reviews.all().delete()
    use_case.governance_assessments.all().delete()
    reviewer = use_case.decision_assessments.first().assessed_by
    screening = GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=reviewer,
        basis_version="Issue 61",
        privacy_review_required=privacy_required,
        result=(
            GovernanceAssessment.Result.PRIVACY
            if privacy_required
            else GovernanceAssessment.Result.NO_FLAGS
        ),
        privacy_review_rationale=(
            "Datenschutzprüfung ist für diesen Test erforderlich."
            if privacy_required
            else "Keine Datenschutzprüfung erforderlich."
        ),
    )
    create_screening_review_artifacts(assessment=screening, actor=reviewer)


@pytest.fixture
def prepared_use_case(db):
    call_command("seed_demo_data", demo_user_password="Issue-61-Decision-Demo-2026!")
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    use_case.delivery_packages.all().delete()
    use_case.approval_decisions.all().delete()
    use_case.status = UseCase.Status.IDEA
    use_case.decision_status = UseCase.DecisionStatus.READY
    use_case.privacy_review_required = False
    use_case.privacy_review_completed = False
    use_case.security_review_required = False
    use_case.security_review_completed = False
    use_case.legal_review_required = False
    use_case.legal_review_completed = False
    use_case.save()
    _set_governance_screening(use_case)
    return use_case


@pytest.fixture
def assessing_coordinator(prepared_use_case):
    return prepared_use_case.decision_assessments.first().assessed_by


@pytest.fixture
def independent_coordinator(db):
    user = User.objects.create_user(
        username="issue61_independent_coordinator",
        password="Issue-61-Independent-2026!",
        first_name="Alex",
        last_name="Freigabe",
    )
    user.groups.add(Group.objects.get(name=GROUP_COORDINATOR))
    return user


def _decision_url(use_case, status=None):
    url = reverse("use_cases:approval_decision_create", kwargs={"pk": use_case.pk})
    return f"{url}?decision_status={status}" if status else url


@pytest.mark.django_db
def test_role_blocker_is_visible_before_form_and_routes_to_assignment(
    client, prepared_use_case, assessing_coordinator
):
    client.force_login(assessing_coordinator)

    response = client.get(_decision_url(prepared_use_case))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Rollen und Personentrennung" in content
    assert "Aktuell entscheidende Person" in content
    assert assessing_coordinator.get_display_name() in content
    assert "Bewertende und entscheidende Person müssen verschieden sein" in content
    assert 'id="decision-blockers"' in content
    assert 'id="decision-form"' not in content
    assert "Andere KI-Koordination zuweisen" in content
    expected_target = (
        reverse("use_cases:edit", kwargs={"pk": prepared_use_case.pk})
        + "?highlight=coordinator#field-coordinator"
    )
    assert expected_target in content


@pytest.mark.django_db
def test_open_governance_review_is_visible_readiness_for_positive_approval(
    client, prepared_use_case, independent_coordinator
):
    _set_governance_screening(prepared_use_case, privacy_required=True)
    client.force_login(independent_coordinator)

    response = client.get(_decision_url(prepared_use_case, UseCase.DecisionStatus.APPROVED))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Datenschutzprüfung" in content
    assert "Readiness offen: Datenschutzprüfung" in content
    assert 'id="decision-form"' in content
    assert 'id="decision-blockers"' not in content


@pytest.mark.django_db
def test_negative_decision_form_can_open_despite_positive_governance_blocker(
    client, prepared_use_case, independent_coordinator
):
    _set_governance_screening(prepared_use_case, privacy_required=True)
    client.force_login(independent_coordinator)

    response = client.get(_decision_url(prepared_use_case, UseCase.DecisionStatus.DEFERRED))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'id="decision-form"' in content
    assert "Ausgewählter Prüfpfad: Zurückgestellt" in content
    assert 'id="decision-blockers"' not in content


@pytest.mark.django_db
def test_unblocked_form_explains_governance_confirmation_and_warns_on_unsaved_data(
    client, prepared_use_case, independent_coordinator
):
    client.force_login(independent_coordinator)

    response = client.get(_decision_url(prepared_use_case, UseCase.DecisionStatus.APPROVED))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'id="decision-form"' in content
    assert 'data-initially-dirty="false"' in content
    assert (
        "Sie ersetzt weder offene Fachprüfungen noch die erforderliche Personentrennung" in content
    )
    assert "beforeunload" in content


@pytest.mark.django_db
def test_invalid_post_keeps_bound_form_marked_as_unsaved(
    client, prepared_use_case, independent_coordinator
):
    client.force_login(independent_coordinator)

    response = client.post(
        _decision_url(prepared_use_case, UseCase.DecisionStatus.APPROVED),
        {
            "decision_status": UseCase.DecisionStatus.APPROVED,
            "rationale": "",
            "governance_confirmed": "on",
            "conditions": "",
            "condition_owner": "",
            "condition_due_date": "",
        },
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert 'id="decision-form"' in content
    assert 'data-initially-dirty="true"' in content
    assert not prepared_use_case.approval_decisions.exists()
