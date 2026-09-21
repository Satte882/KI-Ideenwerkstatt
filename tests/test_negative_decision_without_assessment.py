import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from ki_radar.use_cases.models import ApprovalDecision, UseCase
from ki_radar.use_cases.services import approval_check, submit_approval_decision
from ki_radar.use_cases.workflow import build_use_case_journey


def _use_case(owner, business_unit):
    return UseCase.objects.create(
        title="Frühe Portfolioentscheidung",
        problem_statement="Das Vorhaben soll früh bewertet oder beendet werden.",
        business_unit=business_unit,
        affected_process="Kernprozess",
        submitter=owner,
        business_owner=owner,
        expected_benefit="Nur bei ausreichendem Nutzen weiterverfolgen.",
        status=UseCase.Status.REVIEW,
    )


def _negative_decision_data(status):
    return {
        "decision_status": status,
        "rationale": "Der Use Case wird bewusst ohne weitere Bewertung gestoppt.",
        "governance_confirmed": False,
        "conditions": "",
        "condition_owner": None,
        "condition_due_date": None,
        "second_approval_assignee": None,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [UseCase.DecisionStatus.DEFERRED, UseCase.DecisionStatus.NOT_PURSUED],
)
def test_negative_decision_without_assessment_is_readiness_not_enforcement(
    owner,
    coordinator,
    business_unit,
    status,
):
    use_case = _use_case(owner, business_unit)

    check = approval_check(use_case=use_case, target_status=status, actor=coordinator)

    assert check.blockers == []
    assert any("Keine strukturierte Bewertung" in warning for warning in check.warnings)

    decision = submit_approval_decision(
        use_case=use_case,
        actor=coordinator,
        data=_negative_decision_data(status),
    )

    use_case.refresh_from_db()
    assert decision.assessment_id is None
    assert decision.finalized_at is not None
    assert use_case.decision_status == status


@pytest.mark.django_db
def test_positive_approval_without_assessment_remains_enforcement(
    owner,
    coordinator,
    business_unit,
):
    use_case = _use_case(owner, business_unit)

    check = approval_check(
        use_case=use_case,
        target_status=UseCase.DecisionStatus.APPROVED,
        actor=coordinator,
    )
    assert "Aktuelle strukturierte Bewertung" in check.blockers

    with pytest.raises(ValidationError, match="Aktuelle strukturierte Bewertung"):
        submit_approval_decision(
            use_case=use_case,
            actor=coordinator,
            data={
                **_negative_decision_data(UseCase.DecisionStatus.APPROVED),
            },
        )

    assert ApprovalDecision.objects.filter(use_case=use_case).exists() is False


@pytest.mark.django_db
def test_negative_decision_without_assessment_is_reachable_in_ui(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = _use_case(owner, business_unit)
    client.force_login(coordinator)

    response = client.get(reverse("use_cases:approval_decision_create", kwargs={"pk": use_case.pk}))

    assert response.status_code == 200
    choices = dict(response.context["form"].fields["decision_status"].choices)
    assert set(choices) == {
        UseCase.DecisionStatus.DEFERRED,
        UseCase.DecisionStatus.NOT_PURSUED,
    }

    journey = build_use_case_journey(use_case, coordinator)
    approval_step = next(step for step in journey.steps if step.key == "approval")
    assert approval_step.state == "current"
    assert approval_step.url == reverse(
        "use_cases:approval_decision_create",
        kwargs={"pk": use_case.pk},
    )

    detail_response = client.get(use_case.get_absolute_url())
    assert detail_response.status_code == 200
    detail_html = detail_response.content.decode()
    assert 'data-testid="assessment-negative-decision-action"' in detail_html
    assert "Zurückstellen / nicht weiterverfolgen" in detail_html
