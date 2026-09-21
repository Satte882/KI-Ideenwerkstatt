import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from ki_radar.reviews.models import Review
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.models import DecisionAssessment, UseCase
from ki_radar.use_cases.services import apply_status_transition, create_decision_assessment


def _use_case(*, owner, business_unit, status=UseCase.Status.IDEA):
    return UseCase.objects.create(
        title="Workflow-Guard Regression",
        problem_statement="Gezielter Regressionstest für Lifecycle-Guards.",
        business_unit=business_unit,
        affected_process="Testprozess",
        submitter=owner,
        business_owner=owner,
        expected_benefit="Inkonsistente Lifecycle-Zustände verhindern.",
        status=status,
    )


def _assessment_data():
    return {
        "assessment_date": timezone.localdate(),
        "business_value": UseCase.Level.MEDIUM,
        "strategic_fit": UseCase.Level.MEDIUM,
        "technical_feasibility": UseCase.Level.MEDIUM,
        "data_readiness": UseCase.Level.MEDIUM,
        "risk_complexity": UseCase.Level.MEDIUM,
        "evidence_quality": DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
        "evidence_recency": DecisionAssessment.ConfidenceFactor.SOLID,
        "evidence_coverage": DecisionAssessment.ConfidenceFactor.SOLID,
        "independent_review": DecisionAssessment.ConfidenceFactor.SOLID,
        "assumptions_resolved": DecisionAssessment.ConfidenceFactor.SOLID,
        "evidence_url": "https://example.invalid/evidence/workflow-guard",
        "rationale": "Regressionstest.",
        "governance_precheck_completed": True,
        "recommendation": UseCase.DecisionStatus.APPROVED,
    }


@pytest.mark.django_db
def test_assessment_service_rejects_idea_status(owner, coordinator, business_unit):
    use_case = _use_case(owner=owner, business_unit=business_unit)

    with pytest.raises(ValidationError, match="Status Review"):
        create_decision_assessment(
            use_case=use_case,
            actor=coordinator,
            data=_assessment_data(),
        )

    assert use_case.decision_assessments.exists() is False


@pytest.mark.django_db
def test_assessment_direct_url_redirects_outside_review(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = _use_case(owner=owner, business_unit=business_unit)
    client.force_login(coordinator)

    response = client.get(reverse("use_cases:assessment_create", args=[use_case.pk]))

    assert response.status_code == 302
    assert response.url == use_case.get_absolute_url()
    assert use_case.decision_assessments.exists() is False


@pytest.mark.django_db
def test_end_review_rejects_review_source_status(owner, coordinator, business_unit):
    use_case = _use_case(
        owner=owner,
        business_unit=business_unit,
        status=UseCase.Status.REVIEW,
    )

    with pytest.raises(ValidationError, match="ist aus dem Status Prüfung nicht zulässig"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data={
                "review_date": timezone.localdate(),
                "decision": Review.Decision.END,
                "new_status": UseCase.Status.ENDED,
                "rationale": "Manipulierter Abschluss aus Review.",
                "go_live_exception_confirmed": False,
                "open_actions": "",
                "action_owner": None,
                "action_due_date": None,
                "next_review_date": None,
                "ending_reason": "Test",
                "data_and_access_handling": "Testzugänge schließen.",
            },
        )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.REVIEW
    assert use_case.reviews.filter(decision=Review.Decision.END).exists() is False


@pytest.mark.django_db
def test_direct_ended_transition_rejects_review_source_status(
    owner,
    coordinator,
    business_unit,
):
    use_case = _use_case(
        owner=owner,
        business_unit=business_unit,
        status=UseCase.Status.REVIEW,
    )
    use_case.ending_reason = "Test"
    use_case.data_and_access_handling = "Testzugänge schließen."
    use_case.save(update_fields=["ending_reason", "data_and_access_handling", "updated_at"])

    with pytest.raises(ValidationError, match=r"reviews\.services\.create_review"):
        apply_status_transition(
            use_case=use_case,
            target_status=UseCase.Status.ENDED,
            actor=coordinator,
        )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.REVIEW
