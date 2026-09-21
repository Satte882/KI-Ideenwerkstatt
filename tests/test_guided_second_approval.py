from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.accounts.permissions import GROUP_COORDINATOR
from ki_radar.core.management.commands.seed_demo_data import Command
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.use_cases.decision_forms import ApprovalDecisionForm
from ki_radar.use_cases.models import DecisionAssessment, UseCase
from ki_radar.use_cases.services import (
    confirm_conditional_decision,
    return_conditional_decision,
    submit_approval_decision,
)


def coordinator_user(username, business_unit):
    user = User.objects.create_user(
        username=username,
        password="VerySecureTestPassword!123",
        business_unit=business_unit,
    )
    group, _ = Group.objects.get_or_create(name=GROUP_COORDINATOR)
    user.groups.add(group)
    return user


def make_case(owner, first_decider, assessor, business_unit):
    use_case = UseCase.objects.create(
        title="Assistierter Angebotsvergleich",
        summary="Angebote strukturiert vergleichen.",
        problem_statement="Uneinheitliche Angebote verlängern die Auswahl.",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        target_users="Einkauf",
        submitter=owner,
        business_owner=owner,
        coordinator=first_decider,
        technical_owner=first_decider,
        source_systems="ERP und Dateiablage",
        data_sources="Angebote und Kriterienkatalog",
        interface_description="Dateiimport und ERP-Export",
        intended_users="Strategischer Einkauf",
        intended_purpose="Angebote extrahieren und vergleichbar darstellen.",
        expected_benefit="Durchlaufzeit reduzieren.",
        metric_name="Durchlaufzeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Tage",
        metric_baseline=Decimal("5"),
        metric_target=Decimal("3"),
        metric_measurement_method="Median über zehn Vorgänge.",
        metric_measurement_period="Vier Wochen.",
        human_oversight="Einkauf entscheidet final.",
        support_responsibility="Application Management",
        decision_status=UseCase.DecisionStatus.READY,
        next_review_date=timezone.localdate() + timedelta(days=14),
    )
    assessment = DecisionAssessment.objects.create(
        use_case=use_case,
        version=1,
        assessed_by=assessor,
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
        evidence_url="https://example.com/evidence",
        rationale="Repräsentative Messung und technische Vorprüfung liegen vor.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
    )
    GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=first_decider,
        basis_version="test-screening-v1",
        result=GovernanceAssessment.Result.NO_FLAGS,
    )
    return use_case, assessment


def decision_data(owner, assignee):
    return {
        "decision_status": UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
        "rationale": "Pilot ist mit einer klaren Betriebsauflage vertretbar.",
        "governance_confirmed": True,
        "conditions": "Monitoring vor dem Pilotstart aktivieren.",
        "condition_owner": owner,
        "condition_due_date": timezone.localdate() + timedelta(days=10),
        "second_approval_assignee": assignee,
    }


@pytest.fixture
def second_approval_case(owner, coordinator, technical_admin, business_unit):
    assessor = coordinator_user("assessment-coordinator", business_unit)
    reviewer = coordinator_user("independent-reviewer", business_unit)
    use_case, assessment = make_case(owner, coordinator, assessor, business_unit)
    return use_case, assessment, reviewer, technical_admin, assessor


@pytest.mark.django_db
def test_form_offers_only_independent_but_multiple_eligible_reviewers(
    owner, coordinator, second_approval_case
):
    use_case, _assessment, reviewer, technical_admin, assessor = second_approval_case
    form = ApprovalDecisionForm(
        initial={"decision_status": UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS},
        actor=coordinator,
        use_case=use_case,
    )
    ids = set(form.fields["second_approval_assignee"].queryset.values_list("pk", flat=True))

    assert reviewer.pk in ids
    assert technical_admin.pk in ids
    assert coordinator.pk not in ids
    assert assessor.pk not in ids
    assert owner.pk not in ids
    assert form.fields["second_approval_assignee"].required is True


@pytest.mark.django_db
def test_conditional_decision_records_preferred_assignment(
    owner, coordinator, second_approval_case
):
    use_case, _assessment, reviewer, _technical_admin, _assessor = second_approval_case

    decision = submit_approval_decision(
        use_case=use_case,
        actor=coordinator,
        data=decision_data(owner, reviewer),
    )

    assert decision.is_pending_second_approval is True
    assert decision.second_approval_assignee == reviewer
    assert decision.second_approval_requested_at is not None
    use_case.refresh_from_db()
    assert use_case.decision_status == UseCase.DecisionStatus.READY


@pytest.mark.django_db
def test_other_eligible_reviewer_can_take_over_non_exclusive_assignment(
    owner, coordinator, second_approval_case
):
    use_case, _assessment, reviewer, technical_admin, _assessor = second_approval_case
    decision = submit_approval_decision(
        use_case=use_case,
        actor=coordinator,
        data=decision_data(owner, reviewer),
    )

    confirm_conditional_decision(decision=decision, actor=technical_admin)

    decision.refresh_from_db()
    assert decision.second_approval_assignee == reviewer
    assert decision.second_approved_by == technical_admin
    assert decision.is_final is True


@pytest.mark.django_db
def test_first_decider_assessor_and_business_owner_cannot_execute_second_review(
    owner, coordinator, second_approval_case
):
    use_case, _assessment, reviewer, _technical_admin, assessor = second_approval_case
    decision = submit_approval_decision(
        use_case=use_case,
        actor=coordinator,
        data=decision_data(owner, reviewer),
    )

    for actor in [coordinator, assessor, owner]:
        with pytest.raises(PermissionDenied):
            confirm_conditional_decision(decision=decision, actor=actor)


@pytest.mark.django_db
def test_reasoned_return_preserves_first_decision_and_closes_task(
    owner, coordinator, second_approval_case
):
    use_case, _assessment, reviewer, _technical_admin, _assessor = second_approval_case
    decision = submit_approval_decision(
        use_case=use_case,
        actor=coordinator,
        data=decision_data(owner, reviewer),
    )

    return_conditional_decision(
        decision=decision,
        actor=reviewer,
        reason="Die Auflage enthält noch kein prüfbares Abnahmekriterium.",
    )

    decision.refresh_from_db()
    assert decision.second_approval_returned_by == reviewer
    assert decision.is_returned_from_second_approval is True
    assert decision.is_pending_second_approval is False
    assert decision.decided_by == coordinator
    assert decision.rationale.startswith("Pilot ist")


@pytest.mark.django_db
def test_guided_workspace_shows_context_and_actions_only_to_eligible_user(
    client, owner, coordinator, second_approval_case
):
    use_case, assessment, reviewer, _technical_admin, _assessor = second_approval_case
    decision = submit_approval_decision(
        use_case=use_case,
        actor=coordinator,
        data=decision_data(owner, reviewer),
    )
    url = reverse("use_cases:second_approval_review", args=[decision.pk])

    client.force_login(reviewer)
    eligible_response = client.get(url)
    eligible_body = eligible_response.content.decode()
    assert eligible_response.status_code == 200
    assert f"Aktuelle Bewertung v{assessment.version}" in eligible_body
    assert "Erstentscheidung" in eligible_body
    assert "Monitoring vor dem Pilotstart aktivieren" in eligible_body
    assert "Governance-Nachweise" in eligible_body
    assert 'name="action" value="confirm"' in eligible_body
    assert 'name="action" value="return"' in eligible_body

    client.force_login(owner)
    readonly_response = client.get(url)
    readonly_body = readonly_response.content.decode()
    assert readonly_response.status_code == 200
    assert "Nur Ansicht" in readonly_body
    assert 'name="action" value="confirm"' not in readonly_body
    assert 'name="action" value="return"' not in readonly_body


@pytest.mark.django_db
def test_use_case_detail_shows_assignment_and_guided_link(
    client, owner, coordinator, second_approval_case
):
    use_case, _assessment, reviewer, _technical_admin, _assessor = second_approval_case
    decision = submit_approval_decision(
        use_case=use_case,
        actor=coordinator,
        data=decision_data(owner, reviewer),
    )
    client.force_login(owner)

    response = client.get(use_case.get_absolute_url())
    body = response.content.decode()

    assert response.status_code == 200
    assert "Unabhängige Zweitprüfung ausstehend" in body
    assert reviewer.get_display_name() in body
    assert reverse("use_cases:second_approval_review", args=[decision.pk]) in body
    assert "Als zweite Person bestätigen" not in body


@pytest.mark.django_db
def test_demo_seed_contains_independent_second_reviewer(settings):
    settings.DEBUG = True
    Command().handle(demo_user_password="Demo-Test-2026!")

    reviewer = User.objects.get(username="demo_ki_pruefer")
    assert reviewer.is_active is True
    assert reviewer.groups.filter(name=GROUP_COORDINATOR).exists()
