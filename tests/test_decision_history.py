from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.accounts.permissions import GROUP_COORDINATOR
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase


def make_coordinator(username, business_unit):
    user = User.objects.create_user(
        username=username,
        password="VerySecureTestPassword!123",
        business_unit=business_unit,
    )
    group, _ = Group.objects.get_or_create(name=GROUP_COORDINATOR)
    user.groups.add(group)
    return user


def make_use_case(owner, coordinator, business_unit):
    return UseCase.objects.create(
        title="Auditierbarer Angebotsvergleich",
        summary="Angebote nachvollziehbar vergleichen.",
        problem_statement="Die bisherige Auswahl ist nicht ausreichend nachvollziehbar.",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        business_owner=owner,
        coordinator=coordinator,
        technical_owner=coordinator,
        expected_benefit="Entscheidungen schneller und prüfbar treffen.",
        decision_status=UseCase.DecisionStatus.READY,
    )


def make_assessment(use_case, assessor, *, version, rationale, recommendation):
    return DecisionAssessment.objects.create(
        use_case=use_case,
        version=version,
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
        evidence_url=f"https://example.com/evidence-v{version}",
        rationale=rationale,
        governance_precheck_completed=True,
        recommendation=recommendation,
    )


@pytest.fixture
def decision_history_case(owner, coordinator, business_unit):
    assessor = make_coordinator("history-assessor", business_unit)
    first_decider = make_coordinator("history-first-decider", business_unit)
    preferred_reviewer = make_coordinator("history-preferred-reviewer", business_unit)
    actual_reviewer = make_coordinator("history-actual-reviewer", business_unit)
    use_case = make_use_case(owner, coordinator, business_unit)
    return use_case, assessor, first_decider, preferred_reviewer, actual_reviewer


@pytest.mark.django_db
def test_detail_shows_complete_confirmed_approval_chain(client, owner, decision_history_case):
    use_case, assessor, first_decider, preferred_reviewer, actual_reviewer = decision_history_case
    assessment = make_assessment(
        use_case,
        assessor,
        version=3,
        rationale="Bewertung v3 mit belastbarer Evidenz.",
        recommendation=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
    )
    now = timezone.now()
    approval = ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
        rationale="Erstentscheidung mit klarer Betriebsauflage.",
        decided_by=first_decider,
        governance_confirmed=True,
        conditions="Monitoring vor Pilotstart aktivieren.",
        condition_owner=owner,
        condition_due_date=timezone.localdate() + timedelta(days=14),
        second_approval_assignee=preferred_reviewer,
        second_approval_requested_at=now - timedelta(hours=2),
        second_approved_by=actual_reviewer,
        finalized_at=now,
    )
    client.force_login(owner)

    response = client.get(reverse("use_cases:detail", args=[use_case.pk]))
    body = response.content.decode()

    assert response.status_code == 200
    assert 'data-testid="approval-history"' in body
    assert "1. Bewertung v3" in body
    assert "Bewertung v3 mit belastbarer Evidenz" in body
    assert "2. Erstentscheidung" in body
    assert "Erstentscheidung mit klarer Betriebsauflage" in body
    assert "3. Auflagen und Prüfauftrag" in body
    assert "Monitoring vor Pilotstart aktivieren" in body
    assert "4. Unabhängig bestätigt" in body
    assert first_decider.get_display_name() in body
    assert preferred_reviewer.get_display_name() in body
    assert actual_reviewer.get_display_name() in body
    assert body.index("1. Bewertung v3") < body.index("2. Erstentscheidung")
    assert body.index("2. Erstentscheidung") < body.index("3. Auflagen und Prüfauftrag")
    assert body.index("3. Auflagen und Prüfauftrag") < body.index("4. Unabhängig bestätigt")
    assert f'data-approval-id="{approval.pk}"' in body


@pytest.mark.django_db
def test_detail_shows_reasoned_return_without_overwriting_first_decision(
    client, owner, decision_history_case
):
    use_case, assessor, first_decider, preferred_reviewer, actual_reviewer = decision_history_case
    assessment = make_assessment(
        use_case,
        assessor,
        version=1,
        rationale="Bewertung für Rückgabefall.",
        recommendation=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
    )
    approval = ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
        rationale="Historische Erstentscheidung bleibt erhalten.",
        decided_by=first_decider,
        governance_confirmed=True,
        conditions="Abnahmekriterium konkretisieren.",
        condition_owner=owner,
        condition_due_date=timezone.localdate() + timedelta(days=7),
        second_approval_assignee=preferred_reviewer,
        second_approval_requested_at=timezone.now() - timedelta(hours=1),
        second_approval_returned_by=actual_reviewer,
        second_approval_returned_at=timezone.now(),
        second_approval_return_reason="Das Abnahmekriterium ist noch nicht prüfbar.",
    )
    before = (approval.rationale, approval.decided_by_id, approval.decision_status)
    client.force_login(owner)

    response = client.get(use_case.get_absolute_url())
    body = response.content.decode()
    approval.refresh_from_db()

    assert response.status_code == 200
    assert "4. Begründet zurückgegeben" in body
    assert "Das Abnahmekriterium ist noch nicht prüfbar" in body
    assert "Die Erstentscheidung bleibt als historisches Artefakt erhalten" in body
    assert "Historische Erstentscheidung bleibt erhalten" in body
    assert (approval.rationale, approval.decided_by_id, approval.decision_status) == before


@pytest.mark.django_db
def test_detail_keeps_multiple_decisions_linked_to_their_assessment_versions(
    client, owner, decision_history_case
):
    use_case, assessor, first_decider, preferred_reviewer, actual_reviewer = decision_history_case
    old_assessment = make_assessment(
        use_case,
        assessor,
        version=1,
        rationale="Alte Bewertungsversion eins.",
        recommendation=UseCase.DecisionStatus.DEFERRED,
    )
    old_decision = ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=old_assessment,
        decision_status=UseCase.DecisionStatus.DEFERRED,
        rationale="Historisch zunächst zurückgestellt.",
        decided_by=first_decider,
        governance_confirmed=True,
        finalized_at=timezone.now() - timedelta(days=20),
    )
    ApprovalDecision.objects.filter(pk=old_decision.pk).update(
        created_at=timezone.now() - timedelta(days=20)
    )
    new_assessment = make_assessment(
        use_case,
        assessor,
        version=2,
        rationale="Neue Bewertungsversion zwei.",
        recommendation=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
    )
    new_decision = ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=new_assessment,
        decision_status=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
        rationale="Später mit Auflage freigegeben.",
        decided_by=first_decider,
        governance_confirmed=True,
        conditions="Monitoring aktivieren.",
        condition_owner=owner,
        condition_due_date=timezone.localdate() + timedelta(days=7),
        second_approval_assignee=preferred_reviewer,
        second_approval_requested_at=timezone.now() - timedelta(hours=2),
        second_approved_by=actual_reviewer,
        finalized_at=timezone.now(),
    )
    client.force_login(owner)

    response = client.get(use_case.get_absolute_url())
    body = response.content.decode()

    assert response.status_code == 200
    assert "Historisch zunächst zurückgestellt" in body
    assert "Alte Bewertungsversion eins" in body
    assert "Später mit Auflage freigegeben" in body
    assert "Neue Bewertungsversion zwei" in body
    assert body.index(f'data-approval-id="{new_decision.pk}"') < body.index(
        f'data-approval-id="{old_decision.pk}"'
    )
    assert body.index("Neue Bewertungsversion zwei") < body.index("Alte Bewertungsversion eins")
