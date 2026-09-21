from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from ki_radar.delivery.lean_services import hand_over_package, mark_package_ready
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.reviews.models import Review
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase
from ki_radar.use_cases.services import (
    apply_status_transition,
    create_decision_assessment,
    submit_approval_decision,
)
from ki_radar.use_cases.transition_policy import validate_review_command


def _use_case(owner, business_unit, *, status=UseCase.Status.REVIEW):
    return UseCase.objects.create(
        title="Lean Workflow",
        problem_statement="Ein klar beschriebenes Businessproblem.",
        business_unit=business_unit,
        affected_process="Kernprozess",
        submitter=owner,
        business_owner=owner,
        expected_benefit="Durchlaufzeit reduzieren",
        status=status,
    )


def _assessment_data(*, recommendation=UseCase.DecisionStatus.APPROVED):
    return {
        "assessment_date": timezone.localdate(),
        "business_value": UseCase.Level.MEDIUM,
        "strategic_fit": UseCase.Level.MEDIUM,
        "technical_feasibility": UseCase.Level.MEDIUM,
        "data_readiness": UseCase.Level.MEDIUM,
        "risk_complexity": UseCase.Level.MEDIUM,
        "evidence_quality": DecisionAssessment.EvidenceQuality.EXPERT_OPINION,
        "evidence_recency": DecisionAssessment.ConfidenceFactor.LIMITED,
        "evidence_coverage": DecisionAssessment.ConfidenceFactor.LIMITED,
        "independent_review": DecisionAssessment.ConfidenceFactor.LIMITED,
        "assumptions_resolved": DecisionAssessment.ConfidenceFactor.LIMITED,
        "evidence_url": "",
        "rationale": "Für die Entscheidung ausreichend, Nachweis kann ergänzt werden.",
        "governance_precheck_completed": False,
        "recommendation": recommendation,
    }


def _assessment(use_case, coordinator, *, recommendation=UseCase.DecisionStatus.APPROVED):
    return DecisionAssessment.objects.create(
        use_case=use_case,
        version=1,
        assessed_by=coordinator,
        **_assessment_data(recommendation=recommendation),
    )


def _approval(use_case, coordinator):
    assessment = _assessment(use_case, coordinator)
    decision = ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Pilot freigegeben.",
        decided_by=coordinator,
        finalized_at=timezone.now(),
    )
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.save(update_fields=["decision_status", "updated_at"])
    return decision


def _empty_delivery_package(use_case, coordinator, decision):
    text_fields = {
        "problem_context": "",
        "target_outcome": "",
        "in_scope": "",
        "out_of_scope": "",
        "users_and_scenarios": "",
        "solution_outline": "",
        "system_context": "",
        "data_context": "",
        "integrations": "",
        "functional_requirements": "",
        "non_functional_requirements": "",
        "security_privacy_requirements": "",
        "human_oversight": "",
        "logging_and_audit": "",
        "operations_and_support": "",
        "mvp_scope": "",
        "acceptance_criteria": "",
        "test_scenarios": "",
        "measurement_plan": "",
        "dependencies": "",
        "risks": "",
        "assumptions": "",
        "architecture_decisions": "",
        "initial_backlog": "",
        "external_delivery_url": "",
        "handover_notes": "",
    }
    return DeliveryPackage.objects.create(
        use_case=use_case,
        technical_owner=coordinator,
        version=1,
        readiness_schema_version=2,
        generated_from_decision=decision,
        created_by=coordinator,
        **text_fields,
    )


@pytest.mark.django_db
def test_direct_status_write_is_fenced(owner, coordinator, business_unit):
    use_case = _use_case(owner, business_unit)

    with pytest.raises(ValidationError, match=r"reviews\.services\.create_review"):
        apply_status_transition(
            use_case=use_case,
            target_status=UseCase.Status.PILOT,
            actor=coordinator,
            pilot_start=timezone.localdate(),
        )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.REVIEW


@pytest.mark.django_db
def test_start_review_requires_idea_source(owner, coordinator, business_unit):
    use_case = _use_case(owner, business_unit, status=UseCase.Status.REVIEW)

    with pytest.raises(ValidationError, match="start_review"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data={
                "review_date": timezone.localdate(),
                "decision": Review.Decision.START_REVIEW,
                "new_status": UseCase.Status.REVIEW,
                "rationale": "",
            },
        )

    assert use_case.reviews.exists() is False


@pytest.mark.django_db
def test_end_is_atomic_and_not_blocked_by_closure_documentation(
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit, status=UseCase.Status.PILOT)
    use_case.pilot_start = timezone.localdate() - timedelta(days=7)
    use_case.save(update_fields=["pilot_start", "updated_at"])

    review = create_review(
        use_case=use_case,
        actor=owner,
        data={
            "review_date": timezone.localdate(),
            "decision": Review.Decision.END,
            "new_status": UseCase.Status.ENDED,
            "rationale": "",
            "ending_reason": "",
            "data_and_access_handling": "",
        },
    )

    use_case.refresh_from_db()
    assert review.previous_status == UseCase.Status.PILOT
    assert review.new_status == UseCase.Status.ENDED
    assert use_case.status == UseCase.Status.ENDED
    assert use_case.actual_end_date == timezone.localdate()
    assert use_case.ending_reason == ""
    assert use_case.data_and_access_handling == ""


@pytest.mark.django_db
def test_negative_decision_needs_no_governance_and_not_pursued_is_terminal(
    owner,
    coordinator,
    business_unit,
):
    use_case = _use_case(owner, business_unit)
    _assessment(use_case, coordinator, recommendation=UseCase.DecisionStatus.NOT_PURSUED)

    submit_approval_decision(
        use_case=use_case,
        actor=coordinator,
        data={
            "decision_status": UseCase.DecisionStatus.NOT_PURSUED,
            "rationale": "Kein ausreichender Businessnutzen.",
            "governance_confirmed": False,
            "conditions": "",
            "condition_owner": None,
            "condition_due_date": None,
            "second_approval_assignee": None,
        },
    )

    use_case.refresh_from_db()
    assert use_case.decision_status == UseCase.DecisionStatus.NOT_PURSUED
    assert use_case.governance_assessments.exists() is False
    with pytest.raises(ValidationError, match="terminal"):
        create_decision_assessment(
            use_case=use_case,
            actor=coordinator,
            data=_assessment_data(),
        )


@pytest.mark.django_db
def test_deferred_can_be_reactivated_by_new_assessment(
    owner,
    coordinator,
    business_unit,
):
    use_case = _use_case(owner, business_unit)
    _assessment(use_case, coordinator, recommendation=UseCase.DecisionStatus.DEFERRED)
    submit_approval_decision(
        use_case=use_case,
        actor=coordinator,
        data={
            "decision_status": UseCase.DecisionStatus.DEFERRED,
            "rationale": "Später erneut bewerten.",
            "governance_confirmed": False,
            "conditions": "",
            "condition_owner": None,
            "condition_due_date": None,
            "second_approval_assignee": None,
        },
    )
    use_case.refresh_from_db()
    assert use_case.decision_status == UseCase.DecisionStatus.DEFERRED

    assessment = create_decision_assessment(
        use_case=use_case,
        actor=coordinator,
        data=_assessment_data(),
    )

    use_case.refresh_from_db()
    assert assessment.version == 2
    assert use_case.decision_status == UseCase.DecisionStatus.READY


@pytest.mark.django_db
def test_go_live_rejects_measurement_from_before_pilot(
    owner,
    coordinator,
    business_unit,
):
    today = timezone.localdate()
    use_case = _use_case(owner, business_unit, status=UseCase.Status.PILOT)
    use_case.pilot_start = today
    use_case.metric_name = "Durchlaufzeit"
    use_case.metric_direction = UseCase.MetricDirection.LOWER
    use_case.metric_target = 8
    use_case.metric_actual = 7
    use_case.metric_measured_at = today - timedelta(days=1)
    use_case.technical_owner = coordinator
    use_case.support_responsibility = "IT-Service"
    use_case.save()

    with pytest.raises(ValidationError, match="Messdatum"):
        validate_review_command(
            use_case=use_case,
            decision=Review.Decision.GO_LIVE,
            target_status=UseCase.Status.OPERATION,
            actor=coordinator,
            scale_evidence={"scale_rollback_tested": True},
        )


@pytest.mark.django_db
def test_delivery_documentation_findings_are_readiness_not_hard_gate(
    owner,
    coordinator,
    business_unit,
):
    use_case = _use_case(owner, business_unit)
    decision = _approval(use_case, coordinator)
    package = _empty_delivery_package(use_case, coordinator, decision)

    mark_package_ready(package)
    package.refresh_from_db()
    assert package.status == DeliveryPackage.Status.READY

    hand_over_package(package, coordinator)
    package.refresh_from_db()
    assert package.status == DeliveryPackage.Status.HANDED_OVER
    assert package.handed_over_at is not None
