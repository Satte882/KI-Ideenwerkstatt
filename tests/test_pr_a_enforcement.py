from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.accounts.permissions import GROUP_COORDINATOR
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.use_cases.models import DecisionAssessment, UseCase
from ki_radar.use_cases.services import (
    apply_status_transition,
    confirm_conditional_decision,
    create_decision_assessment,
    submit_approval_decision,
)


def make_coordinator(username, business_unit):
    user = User.objects.create_user(
        username=username,
        password="VerySecureTestPassword!123",
        business_unit=business_unit,
    )
    group, _ = Group.objects.get_or_create(name=GROUP_COORDINATOR)
    user.groups.add(group)
    return user


def make_ready_use_case(owner, business_unit):
    use_case = UseCase.objects.create(
        title="Angebote strukturiert vergleichen",
        summary="Lieferantenangebote werden heute manuell vereinheitlicht.",
        problem_statement=(
            "Uneinheitliche Lieferantenangebote verlängern die Prüfung und erschweren eine "
            "nachvollziehbare Auswahl."
        ),
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        target_users="Strategischer Einkauf",
        submitter=owner,
        business_owner=owner,
        intended_users="Einkäuferinnen und Einkäufer",
        intended_purpose="Angebote anhand freigegebener Kriterien gegenüberstellen",
        expected_benefit="Durchlaufzeit und manuelle Nacharbeit reduzieren",
        metric_name="Durchlaufzeit je Auswahl",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Tage",
        metric_baseline=Decimal("5"),
        metric_target=Decimal("3"),
        metric_measurement_method="Messung über zehn abgeschlossene Auswahlvorgänge",
        data_sources="Angebotsdokumente und freigegebene Bewertungskriterien",
        status=UseCase.Status.REVIEW,
        decision_status=UseCase.DecisionStatus.READY,
    )
    GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        basis_version="test-screening-v1",
        result=GovernanceAssessment.Result.NO_FLAGS,
    )
    return use_case


def assessment_data(**overrides):
    data = {
        "assessment_date": timezone.localdate(),
        "business_value": UseCase.Level.HIGH,
        "strategic_fit": UseCase.Level.MEDIUM,
        "technical_feasibility": UseCase.Level.HIGH,
        "data_readiness": UseCase.Level.MEDIUM,
        "risk_complexity": UseCase.Level.MEDIUM,
        "evidence_quality": DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
        "evidence_recency": DecisionAssessment.ConfidenceFactor.SOLID,
        "evidence_coverage": DecisionAssessment.ConfidenceFactor.SOLID,
        "independent_review": DecisionAssessment.ConfidenceFactor.SOLID,
        "assumptions_resolved": DecisionAssessment.ConfidenceFactor.SOLID,
        "evidence_url": "https://example.com/assessment-evidence",
        "rationale": "Prozessmessung und Datenprüfung stützen die Bewertung.",
        "governance_precheck_completed": True,
        "recommendation": UseCase.DecisionStatus.APPROVED,
    }
    data.update(overrides)
    return data


def approval_data(**overrides):
    data = {
        "decision_status": UseCase.DecisionStatus.APPROVED,
        "rationale": "Die dokumentierten Voraussetzungen rechtfertigen die Freigabe.",
        "governance_confirmed": True,
        "conditions": "",
        "condition_owner": None,
        "condition_due_date": None,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_business_owner_cannot_approve_own_use_case(owner, coordinator, business_unit):
    use_case = make_ready_use_case(owner, business_unit)
    create_decision_assessment(
        use_case=use_case,
        actor=coordinator,
        data=assessment_data(),
    )
    coordinator_group, _ = Group.objects.get_or_create(name=GROUP_COORDINATOR)
    owner.groups.add(coordinator_group)

    with pytest.raises(ValidationError, match="Fachlich verantwortliche"):
        submit_approval_decision(
            use_case=use_case,
            actor=owner,
            data=approval_data(),
        )

    use_case.refresh_from_db()
    assert use_case.decision_status == UseCase.DecisionStatus.READY


@pytest.mark.django_db
def test_high_risk_is_readiness_for_positive_approval(owner, coordinator, business_unit):
    use_case = make_ready_use_case(owner, business_unit)
    approver = make_coordinator("risk-approver", business_unit)
    create_decision_assessment(
        use_case=use_case,
        actor=coordinator,
        data=assessment_data(risk_complexity=UseCase.Level.HIGH),
    )

    decision = submit_approval_decision(
        use_case=use_case,
        actor=approver,
        data=approval_data(),
    )

    assert decision.is_final


@pytest.mark.django_db
def test_positive_approval_uses_screening_without_duplicate_confirmation(
    owner, coordinator, business_unit
):
    use_case = make_ready_use_case(owner, business_unit)
    approver = make_coordinator("governance-approver", business_unit)
    create_decision_assessment(
        use_case=use_case,
        actor=coordinator,
        data=assessment_data(),
    )

    decision = submit_approval_decision(
        use_case=use_case,
        actor=approver,
        data=approval_data(governance_confirmed=False),
    )

    assert decision.is_final


@pytest.mark.django_db
def test_pilot_transition_requires_positive_approval(owner, coordinator, business_unit):
    use_case = make_ready_use_case(owner, business_unit)
    use_case.next_review_date = timezone.localdate()
    use_case.planned_pilot_end = timezone.localdate() + timedelta(days=30)
    use_case.save()

    with pytest.raises(ValidationError, match=r"reviews\.services\.create_review"):
        apply_status_transition(
            use_case=use_case,
            target_status=UseCase.Status.PILOT,
            actor=coordinator,
        )


@pytest.mark.django_db
def test_owner_cannot_be_second_conditional_approver(owner, coordinator, business_unit):
    use_case = make_ready_use_case(owner, business_unit)
    first_approver = make_coordinator("first-approver", business_unit)
    second_approver = make_coordinator("second-approver", business_unit)
    coordinator_group, _ = Group.objects.get_or_create(name=GROUP_COORDINATOR)
    owner.groups.add(coordinator_group)
    create_decision_assessment(
        use_case=use_case,
        actor=coordinator,
        data=assessment_data(recommendation=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS),
    )
    decision = submit_approval_decision(
        use_case=use_case,
        actor=first_approver,
        data=approval_data(
            decision_status=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
            conditions="Messkonzept vor Pilotstart bestätigen.",
            condition_owner=owner,
            condition_due_date=timezone.localdate() + timedelta(days=14),
            second_approval_assignee=second_approver,
        ),
    )

    with pytest.raises(PermissionDenied, match="Personentrennung"):
        confirm_conditional_decision(decision=decision, actor=owner)

    use_case.refresh_from_db()
    assert use_case.decision_status == UseCase.DecisionStatus.READY
