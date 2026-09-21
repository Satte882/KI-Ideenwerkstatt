from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from ki_radar.delivery.models import DeliveryPackage
from ki_radar.reviews.models import Review
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase
from ki_radar.use_cases.outcome_workspace import build_outcome_workspace_journey

OUTCOME_KEYS = {
    "handover",
    "pilot",
    "measurement",
    "outcome_decision",
    "operation",
    "closure",
}


def _use_case(owner, business_unit, *, status=UseCase.Status.PILOT):
    return UseCase.objects.create(
        title="Automatische Lieferantenauswahl",
        problem_statement="Lieferantenangebote werden manuell verglichen.",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        business_owner=owner,
        expected_benefit="Durchlaufzeit senken.",
        status=status,
        metric_name="Durchlaufzeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Tage",
        metric_baseline=Decimal("5"),
        metric_target=Decimal("3"),
    )


def _final_approval(use_case, coordinator):
    assessment = DecisionAssessment.objects.create(
        use_case=use_case,
        version=1,
        assessed_by=coordinator,
        business_value=UseCase.Level.HIGH,
        strategic_fit=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.HIGH,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.MEDIUM,
        evidence_quality=DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
        evidence_recency=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_coverage=DecisionAssessment.ConfidenceFactor.SOLID,
        independent_review=DecisionAssessment.ConfidenceFactor.SOLID,
        assumptions_resolved=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_url="https://example.invalid/evidence/approval",
        rationale="Die Freigabe ist durch repräsentative Evidenz belegt.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    return ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Delivery und Pilot sind freigegeben.",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )


def _handed_over_package(use_case, coordinator):
    return DeliveryPackage.objects.create(
        use_case=use_case,
        version=1,
        status=DeliveryPackage.Status.HANDED_OVER,
        generated_from_decision=_final_approval(use_case, coordinator),
        created_by=coordinator,
        handed_over_by=coordinator,
        handed_over_at=timezone.now(),
    )


def _start_pilot(use_case):
    use_case.pilot_start = timezone.localdate() - timedelta(days=30)
    use_case.save(update_fields=["pilot_start", "updated_at"])


def _complete_measurement(use_case, *, measured_at=None):
    use_case.metric_actual = Decimal("2.8")
    use_case.metric_measurement_period = "Mai bis Juni 2026"
    use_case.metric_measured_at = measured_at or timezone.localdate()
    use_case.metric_evidence_url = "https://example.invalid/evidence/pilot"
    use_case.save(
        update_fields=[
            "metric_actual",
            "metric_measurement_period",
            "metric_measured_at",
            "metric_evidence_url",
            "updated_at",
        ]
    )


def _review(
    use_case,
    coordinator,
    *,
    decision,
    previous_status,
    new_status,
    review_date=None,
):
    return Review.objects.create(
        use_case=use_case,
        review_date=review_date or timezone.localdate(),
        reviewer=coordinator,
        previous_status=previous_status,
        new_status=new_status,
        decision=decision,
        rationale="Verbindliche Lifecycle-Entscheidung für den Test.",
    )


def _outcome_states(journey):
    return {step.key: step.state for step in journey.steps if step.key in OUTCOME_KEYS}


@pytest.mark.django_db
def test_complete_pilot_measurement_exposes_only_result_decision_as_current(
    coordinator,
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit)
    _handed_over_package(use_case, coordinator)
    _start_pilot(use_case)
    _complete_measurement(use_case)

    states = _outcome_states(build_outcome_workspace_journey(use_case, coordinator))

    assert states == {
        "handover": "complete",
        "pilot": "complete",
        "measurement": "complete",
        "outcome_decision": "current",
        "operation": "upcoming",
        "closure": "upcoming",
    }
    assert list(states.values()).count("current") == 1


@pytest.mark.django_db
def test_operation_without_handover_or_reviews_is_blocked_as_data_inconsistency(
    coordinator,
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit, status=UseCase.Status.OPERATION)
    _complete_measurement(use_case)

    journey = build_outcome_workspace_journey(use_case, coordinator)
    states = _outcome_states(journey)
    reasons = {step.key: step.reason for step in journey.steps if step.key in OUTCOME_KEYS}

    assert states["handover"] == "blocked"
    assert states["pilot"] == "blocked"
    assert states["measurement"] == "blocked"
    assert states["outcome_decision"] == "blocked"
    assert states["operation"] == "blocked"
    assert not ({"complete", "current"} & set(states.values()))
    assert "Dateninkonsistenz" in reasons["handover"]
    assert "Go-live-Review fehlt" in reasons["operation"]


@pytest.mark.django_db
def test_valid_operation_has_complete_predecessors_and_one_current_phase(
    coordinator,
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit, status=UseCase.Status.OPERATION)
    _handed_over_package(use_case, coordinator)
    _start_pilot(use_case)
    _complete_measurement(use_case)
    _review(
        use_case,
        coordinator,
        decision=Review.Decision.GO_LIVE,
        previous_status=UseCase.Status.PILOT,
        new_status=UseCase.Status.OPERATION,
    )

    states = _outcome_states(build_outcome_workspace_journey(use_case, coordinator))

    assert states == {
        "handover": "complete",
        "pilot": "complete",
        "measurement": "complete",
        "outcome_decision": "complete",
        "operation": "current",
        "closure": "upcoming",
    }
    assert list(states.values()).count("current") == 1


@pytest.mark.django_db
def test_go_live_review_with_wrong_previous_status_does_not_validate_operation(
    coordinator,
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit, status=UseCase.Status.OPERATION)
    _handed_over_package(use_case, coordinator)
    _start_pilot(use_case)
    _complete_measurement(use_case)
    _review(
        use_case,
        coordinator,
        decision=Review.Decision.GO_LIVE,
        previous_status=UseCase.Status.REVIEW,
        new_status=UseCase.Status.OPERATION,
    )

    states = _outcome_states(build_outcome_workspace_journey(use_case, coordinator))

    assert states["outcome_decision"] == "blocked"
    assert states["operation"] == "blocked"
    assert "current" not in states.values()


@pytest.mark.django_db
def test_direct_end_from_pilot_marks_operation_optional(
    coordinator,
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit, status=UseCase.Status.ENDED)
    _handed_over_package(use_case, coordinator)
    _start_pilot(use_case)
    use_case.actual_end_date = timezone.localdate()
    use_case.save(update_fields=["actual_end_date", "updated_at"])
    _review(
        use_case,
        coordinator,
        decision=Review.Decision.END,
        previous_status=UseCase.Status.PILOT,
        new_status=UseCase.Status.ENDED,
    )

    journey = build_outcome_workspace_journey(use_case, coordinator)
    states = _outcome_states(journey)

    assert states == {
        "handover": "complete",
        "pilot": "complete",
        "measurement": "optional",
        "outcome_decision": "complete",
        "operation": "optional",
        "closure": "complete",
    }
    assert journey.completion_message


@pytest.mark.django_db
def test_end_review_outside_pilot_or_operation_does_not_validate_closure(
    coordinator,
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit, status=UseCase.Status.ENDED)
    _handed_over_package(use_case, coordinator)
    _start_pilot(use_case)
    _review(
        use_case,
        coordinator,
        decision=Review.Decision.END,
        previous_status=UseCase.Status.REVIEW,
        new_status=UseCase.Status.ENDED,
    )

    states = _outcome_states(build_outcome_workspace_journey(use_case, coordinator))

    assert states["outcome_decision"] == "blocked"
    assert states["operation"] == "blocked"
    assert states["closure"] == "blocked"
    assert "complete" not in {
        states["outcome_decision"],
        states["operation"],
        states["closure"],
    }


@pytest.mark.django_db
def test_measurement_before_current_pilot_does_not_complete_pilot(
    coordinator,
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit)
    _handed_over_package(use_case, coordinator)
    _start_pilot(use_case)
    _complete_measurement(
        use_case,
        measured_at=use_case.pilot_start - timedelta(days=1),
    )
    _review(
        use_case,
        coordinator,
        decision=Review.Decision.GO_LIVE,
        previous_status=UseCase.Status.PILOT,
        new_status=UseCase.Status.OPERATION,
        review_date=use_case.pilot_start - timedelta(days=60),
    )

    states = _outcome_states(build_outcome_workspace_journey(use_case, coordinator))

    assert states == {
        "handover": "complete",
        "pilot": "current",
        "measurement": "upcoming",
        "outcome_decision": "upcoming",
        "operation": "upcoming",
        "closure": "upcoming",
    }
    assert list(states.values()).count("current") == 1


@pytest.mark.django_db
def test_selected_view_is_marked_independently_from_lifecycle_state(
    client,
    coordinator,
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit)
    _handed_over_package(use_case, coordinator)
    _start_pilot(use_case)
    _complete_measurement(use_case)
    client.force_login(coordinator)

    response = client.get(
        reverse("reporting:outcome_workspace"),
        {"stage": "effect", "use_case": use_case.pk},
    )
    content = response.content.decode()

    assert content.count("cr-lifecycle-step--active") == 1
    assert "cr-lifecycle-step--complete cr-lifecycle-step--active" in content
    assert 'aria-current="page"' in content
    assert "cr-lifecycle-step--current" in content
