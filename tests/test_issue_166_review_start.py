"""Intake -> human lifecycle review -> assessment, without status/assessment fixtures."""

from copy import deepcopy

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from test_guided_intake_hard_gates import assessment_data, complete_intake_data
from test_issue_146_outcome_contract import bind_process, confirmed, outcome_process, select

from ki_radar.accounts.permissions import GROUP_COORDINATOR
from ki_radar.core.templatetags.workflow_tags import workflow_steps
from ki_radar.reviews.models import Review
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.initiatives import bind_initiative
from ki_radar.use_cases.lean_intake import WIZARD_STEPS
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.services import (
    approval_check,
    create_decision_assessment,
    create_use_case_from_selected_solution,
    intake_blockers,
    submit_approval_decision,
)
from ki_radar.use_cases.status_dimensions import (
    build_use_case_status_dimensions,
    current_work_check,
)
from ki_radar.use_cases.workflow import build_use_case_journey

pytestmark = pytest.mark.django_db


def capture_direct(client, owner, business_unit):
    client.force_login(owner)
    data = complete_intake_data(business_unit, owner)
    for step in range(1, 6):
        fields = WIZARD_STEPS[step]["form"].base_fields
        response = client.post(
            reverse("use_cases:intake_step", args=[step]),
            {name: value for name, value in data.items() if name in fields},
        )
        assert response.status_code == 302, response.context["form"].errors
    response = client.post(reverse("use_cases:intake_step", args=[6]), follow=True)
    assert response.status_code == 200
    assert "Der Prüfungsstart steht aus." in response.content.decode()
    return UseCase.objects.get(submitter=owner)


def review_data():
    return {
        "review_date": timezone.localdate(),
        "decision": Review.Decision.START_REVIEW,
        "new_status": UseCase.Status.REVIEW,
        "rationale": "Intake fachlich gesichtet; strukturierte Prüfung bewusst starten.",
    }


@pytest.mark.parametrize("route", ["direct", "selected_solution"])
@pytest.mark.parametrize("multiple_roles", [False, True])
def test_real_postgres_journey(client, owner, coordinator, business_unit, route, multiple_roles):
    # This acceptance test deliberately requires the production database engine.
    assert connection.vendor == "postgresql"
    if route == "direct":
        case = capture_direct(client, owner, business_unit)
        decision = None
    else:
        process = outcome_process(owner, business_unit)
        bind_process(owner, process)
        decision = select(owner, process, ai=True)
        frozen = deepcopy(decision.comparison_snapshot)
        result = create_use_case_from_selected_solution(decision=decision, actor=owner)
        assert result.created
        case = result.use_case
        assert case.architecture_origin.solution_option == decision.selected_option
        assert case.initiative_id == process.initiative_id

    assert (case.status, case.decision_status) == ("idea", "ready")
    assert not case.reviews.exists()
    assert not case.decision_assessments.exists()
    owner_journey = build_use_case_journey(case, owner)
    assert owner_journey.next_action.key == "review_start"
    assert owner_journey.next_action.url is None
    assert "Prüfungsstart steht aus" in owner_journey.next_action.reason
    dimensions = build_use_case_status_dimensions(case, owner_journey)
    assert dimensions.lifecycle.label == "Idee"
    assert dimensions.assessment.label == "Prüfungsstart ausstehend"
    assert current_work_check(case).title == "Prüfung starten"

    actor = coordinator
    if multiple_roles:
        owner.groups.add(Group.objects.get(name=GROUP_COORDINATOR))
        actor = owner
    client.force_login(actor)
    response = client.get(case.get_absolute_url())
    journey = response.context["journey"]
    assert journey.next_action.key == "review_start"
    assert journey.next_action.action_label == "Prüfung starten"
    review_url = reverse("reviews:create", args=[case.pk])
    assert journey.next_action.url == review_url
    assert "Bereit zur Bewertung" not in response.content.decode()
    assert "Prüfungsstart ausstehend" in response.content.decode()
    assert reverse("use_cases:assessment_create", args=[case.pk]) not in response.content.decode()
    rail = workflow_steps(journey, response.wsgi_request)
    assessment_phase = next(step for step in rail if step["key"] == "assessment")
    assert assessment_phase["state"] == "current"
    assert assessment_phase["label"] == "Prüfung & Bewertung"
    assert assessment_phase["local_url"] == review_url
    dashboard = client.get(reverse("reporting:dashboard"))
    assert "Prüfung starten" in dashboard.content.decode()
    review_form = client.get(review_url).context["form"]
    assert review_form["decision"].value() == Review.Decision.START_REVIEW
    assert review_form["new_status"].value() == UseCase.Status.REVIEW
    response = client.post(review_url, review_data())
    assert response.status_code == 302, response.context["form"].errors
    case.refresh_from_db()
    assert (case.status, case.decision_status) == ("review", "ready")
    review = case.reviews.get()
    assert (review.previous_status, review.new_status, review.reviewer) == ("idea", "review", actor)
    assert review.rationale == review_data()["rationale"]
    assert review.history.get().history_user == actor
    assert case.history.first().history_user == actor
    assert case.history.filter(status="idea").exists()
    assert build_use_case_journey(case, actor).next_action.action_label == "Bewertung anlegen"

    assessment_url = reverse("use_cases:assessment_create", args=[case.pk])
    assert client.get(assessment_url).status_code == 200
    response = client.post(assessment_url, assessment_data())
    assert response.status_code == 302, response.context["form"].errors
    assessment = case.decision_assessments.get()
    assert assessment.assessed_by == actor
    assert assessment.recommendation == "approved"
    case.refresh_from_db()
    assert case.decision_status == "ready"
    assert not case.approval_decisions.exists()
    # A different coordinator still needs the existing outcome/governance gates.
    check = approval_check(use_case=case, target_status="approved", governance_confirmed=True)
    assert check.blockers
    assert any("Governance" in blocker for blocker in check.blockers)
    if route == "direct":
        assert any("Outcome" in blocker or "Vorhaben" in blocker for blocker in check.blockers)
    else:
        decision.refresh_from_db()
        assert decision.comparison_snapshot == frozen

    if route == "direct":
        bind_initiative(initiative=confirmed(owner), artifact=case, actor=owner)
        case.refresh_from_db()
    with pytest.raises(ValidationError, match="verschieden"):
        submit_approval_decision(
            use_case=case,
            actor=actor,
            data={"decision_status": "approved", "rationale": "Selbstfreigabe"},
        )

    # A repeated command cannot create a second decision or history change.
    history_count = case.history.count()
    response = client.post(review_url, review_data())
    assert response.status_code == 200
    assert "nicht zulässig" in response.content.decode()
    assert case.reviews.count() == 1
    assert case.history.count() == history_count


@pytest.mark.parametrize("role", ["owner", "reader"])
def test_unprivileged_roles_cannot_start_review_or_assess(
    request, client, owner, business_unit, role
):
    case = capture_direct(client, owner, business_unit)
    actor = request.getfixturevalue(role)
    client.force_login(actor)
    assert build_use_case_journey(case, actor).next_action.url is None
    for url in (
        reverse("reviews:create", args=[case.pk]),
        reverse("use_cases:assessment_create", args=[case.pk]),
    ):
        assert client.get(url).status_code == 403
        assert client.post(url, review_data()).status_code == 403
    with pytest.raises(PermissionDenied):
        create_review(use_case=case, actor=actor, data=review_data())
    case.refresh_from_db()
    assert case.status == "idea"
    assert not case.reviews.exists()


def test_direct_assessment_from_idea_does_not_skip_review(
    client, owner, coordinator, business_unit
):
    case = capture_direct(client, owner, business_unit)
    client.force_login(coordinator)
    url = reverse("use_cases:assessment_create", args=[case.pk])
    for response in (client.get(url), client.post(url, assessment_data())):
        assert response.status_code == 302
        assert response.url == case.get_absolute_url()
    with pytest.raises(ValidationError, match="Review"):
        create_decision_assessment(use_case=case, actor=coordinator, data=assessment_data())
    assert not case.decision_assessments.exists()
    assert not case.reviews.exists()


def test_missing_intake_has_permitted_correction_not_assessment(
    client, owner, coordinator, reader, business_unit
):
    case = capture_direct(client, owner, business_unit)
    case.title = ""
    case.save()
    assert intake_blockers(case)
    for actor in (owner, coordinator):
        journey = build_use_case_journey(case, actor)
        assert journey.next_action.key == "use_case"
        assert journey.next_action.url
        assert journey.next_action.details
        assert next(step for step in journey.steps if step.key == "review_start").url is None
        assert next(step for step in journey.steps if step.key == "assessment").url is None
    assert build_use_case_journey(case, reader).next_action.url is None


def test_existing_technical_admin_coordinator_capability_is_preserved(
    client, owner, technical_admin, business_unit
):
    case = capture_direct(client, owner, business_unit)
    action = build_use_case_journey(case, technical_admin).next_action
    assert action.action_label == "Prüfung starten"
    client.force_login(technical_admin)
    assert client.post(action.url, review_data()).status_code == 302
    assert case.reviews.get().reviewer == technical_admin


def test_selected_solution_origin_gates_stay_effective(owner, business_unit):
    process = outcome_process(owner, business_unit)
    with pytest.raises(ValidationError):
        select(owner, process, ai=True)
    bind_process(owner, process)
    decision = select(owner, process, ai=True)
    frozen = deepcopy(decision.comparison_snapshot)
    option = decision.selected_option
    option.description = "Geänderter Lösungsstand"
    option.save()
    with pytest.raises(ValidationError, match="Lösungsstand"):
        create_use_case_from_selected_solution(decision=decision, actor=owner)
    assert not UseCase.objects.exists()
    decision.refresh_from_db()
    assert decision.comparison_snapshot == frozen
