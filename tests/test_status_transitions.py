from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.services import hand_over_package
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.reviews.models import Review
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase
from ki_radar.use_cases.services import apply_status_transition


@pytest.fixture
def use_case(owner, business_unit):
    return UseCase.objects.create(
        title="Assistent",
        problem_statement="Wissen ist verteilt",
        business_unit=business_unit,
        affected_process="Auskunft",
        business_owner=owner,
        expected_benefit="Schnellere Antworten",
    )


def create_final_approval(use_case, coordinator):
    assessment = DecisionAssessment.objects.create(
        use_case=use_case,
        version=1,
        assessed_by=coordinator,
        business_value=UseCase.Level.HIGH,
        strategic_fit=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.HIGH,
        data_readiness=UseCase.Level.HIGH,
        risk_complexity=UseCase.Level.LOW,
        evidence_quality=DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
        evidence_recency=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_coverage=DecisionAssessment.ConfidenceFactor.SOLID,
        independent_review=DecisionAssessment.ConfidenceFactor.SOLID,
        assumptions_resolved=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_url="https://example.invalid/evidence",
        rationale="Testfreigabe ist fachlich und technisch belegt.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    return ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Pilot ist freigegeben.",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )


@pytest.mark.django_db
def test_transition_to_pilot_requires_fields_and_governance(use_case, coordinator):
    with pytest.raises(ValidationError):
        apply_status_transition(
            use_case=use_case,
            target_status=UseCase.Status.PILOT,
            actor=coordinator,
            pilot_start=timezone.localdate(),
        )


@pytest.mark.django_db
def test_transition_to_pilot_succeeds(use_case, coordinator):
    today = timezone.localdate()
    use_case.status = UseCase.Status.REVIEW
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.data_sources = "Wissensbasis"
    use_case.next_review_date = today
    use_case.planned_pilot_end = today
    use_case.metric_name = "Antwortzeit"
    use_case.metric_type = UseCase.MetricType.DURATION
    use_case.metric_direction = UseCase.MetricDirection.LOWER
    use_case.metric_unit = "Minuten"
    use_case.metric_baseline = Decimal("30")
    use_case.metric_target = Decimal("10")
    use_case.metric_measurement_method = "Zeitmessung bei 20 repräsentativen Anfragen"
    use_case.save()
    GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=today,
        reviewer=coordinator,
        basis_version="2026-01",
        result=GovernanceAssessment.Result.NO_FLAGS,
        rationale="Keine Hinweise",
    )
    decision = create_final_approval(use_case, coordinator)
    package = DeliveryPackage.objects.create(
        use_case=use_case,
        version=1,
        status=DeliveryPackage.Status.READY,
        generated_from_decision=decision,
        created_by=coordinator,
    )
    hand_over_package(package, coordinator)
    create_review(
        use_case=use_case,
        actor=coordinator,
        data={
            "review_date": today,
            "pilot_start": today,
            "decision": Review.Decision.START_PILOT,
            "new_status": UseCase.Status.PILOT,
            "rationale": "Pilot ist fachlich vorbereitet.",
            "open_actions": "",
            "action_owner": None,
            "action_due_date": None,
            "next_review_date": today,
        },
    )
    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.PILOT
    assert use_case.pilot_start == today
