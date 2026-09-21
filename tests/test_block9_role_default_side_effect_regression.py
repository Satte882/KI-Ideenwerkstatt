from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.role_default_ui import present_role_default
from ki_radar.accelerator.role_defaults import (
    EXISTING,
    ROLE_ONLY,
    resolve_delivery_review_roles,
    resolve_governance_review_role,
    resolve_second_approver,
)
from ki_radar.accounts.models import User
from ki_radar.accounts.permissions import GROUP_COORDINATOR
from ki_radar.architecture.models import ValueStream, ValueStreamStage
from ki_radar.delivery.models import (
    DeliveryPackage,
    DeliveryRoleSourceDecision,
    DeliverySectionReview,
)
from ki_radar.governance.models import GovernanceReview
from ki_radar.use_cases.decision_forms import ApprovalDecisionForm
from ki_radar.use_cases.forms import UseCaseForm
from ki_radar.use_cases.intake_views import SESSION_KEY
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase

pytestmark = pytest.mark.django_db


def _coordinator_user(*, username, business_unit):
    user = User.objects.create_user(
        username=username,
        password="VerySecureTestPassword!123",
        business_unit=business_unit,
    )
    group, _ = Group.objects.get_or_create(name=GROUP_COORDINATOR)
    user.groups.add(group)
    return user


def _use_case(*, business_unit, owner, coordinator=None, technical_owner=None):
    return UseCase.objects.create(
        title="Block-9-Nebenwirkungstest",
        problem_statement=(
            "Ein reproduzierbarer Testfall prüft, dass Rollenhinweise keine Gates auslösen."
        ),
        business_unit=business_unit,
        affected_process="Testprozess",
        business_owner=owner,
        coordinator=coordinator,
        technical_owner=technical_owner,
        expected_benefit="Weniger manuelle Bearbeitung",
        status=UseCase.Status.REVIEW,
        decision_status=UseCase.DecisionStatus.READY,
    )


def _assessment(*, use_case, assessor):
    return DecisionAssessment.objects.create(
        use_case=use_case,
        version=1,
        assessed_by=assessor,
        business_value=UseCase.Level.HIGH,
        strategic_fit=UseCase.Level.MEDIUM,
        technical_feasibility=UseCase.Level.HIGH,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.MEDIUM,
        evidence_quality=DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
        evidence_recency=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_coverage=DecisionAssessment.ConfidenceFactor.SOLID,
        independent_review=DecisionAssessment.ConfidenceFactor.SOLID,
        assumptions_resolved=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_url="https://example.com/block9-evidence",
        rationale="Die Evidenz ist für den Regressionstest ausreichend dokumentiert.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
    )


def _conditional_decision(*, use_case, assessment, decider, owner, assignee):
    return ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
        rationale="Freigabe nur nach expliziter unabhängiger Zweitprüfung.",
        decided_by=decider,
        governance_confirmed=True,
        conditions="Messkonzept vor Pilotstart bestätigen.",
        condition_owner=owner,
        condition_due_date=timezone.localdate() + timedelta(days=14),
        second_approval_assignee=assignee,
        second_approval_requested_at=timezone.now(),
    )


def test_use_case_role_provenance_does_not_write_history_or_lifecycle(
    business_unit,
    owner,
    coordinator,
    reader,
):
    use_case = _use_case(
        business_unit=business_unit,
        owner=owner,
        coordinator=coordinator,
        technical_owner=reader,
    )
    history_count = use_case.history.count()

    form = UseCaseForm(instance=use_case, current_user=coordinator)

    assert form.fields["business_owner"].role_default.state == EXISTING
    assert use_case.history.count() == history_count
    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.REVIEW
    assert use_case.decision_status == UseCase.DecisionStatus.READY
    assert use_case.pilot_start is None
    assert use_case.actual_end_date is None
    assert use_case.approval_decisions.count() == 0


def test_approval_suggestions_do_not_create_or_confirm_decision(
    business_unit,
    owner,
    coordinator,
):
    use_case = _use_case(business_unit=business_unit, owner=owner)
    assessor = _coordinator_user(username="block9-ap6-assessor", business_unit=business_unit)
    candidate = _coordinator_user(username="block9-ap6-second", business_unit=business_unit)
    _assessment(use_case=use_case, assessor=assessor)
    history_count = use_case.history.count()

    form = ApprovalDecisionForm(actor=coordinator, use_case=use_case)

    resolution = form.fields["second_approval_assignee"].role_default
    assert resolution.user_id == candidate.pk
    assert form.fields["second_approval_assignee"].initial is None
    assert use_case.approval_decisions.count() == 0
    assert use_case.history.count() == history_count
    use_case.refresh_from_db()
    assert use_case.decision_status == UseCase.DecisionStatus.READY


def test_existing_second_approval_assignment_is_not_confirmation(
    business_unit,
    owner,
    coordinator,
):
    use_case = _use_case(business_unit=business_unit, owner=owner)
    assessor = _coordinator_user(username="block9-ap6-assessor-2", business_unit=business_unit)
    assignee = _coordinator_user(username="block9-ap6-assignee", business_unit=business_unit)
    assessment = _assessment(use_case=use_case, assessor=assessor)
    decision = _conditional_decision(
        use_case=use_case,
        assessment=assessment,
        decider=coordinator,
        owner=owner,
        assignee=assignee,
    )

    resolution = resolve_second_approver(
        use_case=use_case,
        first_decider=coordinator,
        assigned=assignee,
    )
    present_role_default(resolution)

    assert resolution.state == EXISTING
    decision.refresh_from_db()
    use_case.refresh_from_db()
    assert decision.second_approved_by is None
    assert decision.finalized_at is None
    assert decision.second_approval_returned_at is None
    assert use_case.decision_status == UseCase.DecisionStatus.READY


def test_governance_role_resolution_does_not_complete_review(business_unit, owner):
    use_case = _use_case(business_unit=business_unit, owner=owner)
    review = GovernanceReview.objects.create(
        use_case=use_case,
        review_type=GovernanceReview.ReviewType.PRIVACY,
        status=GovernanceReview.Status.OPEN,
        reviewer=None,
        responsible_role="Datenschutz",
        rationale="Die formale Datenschutzprüfung ist noch offen.",
    )
    history_count = review.history.count()

    resolution = resolve_governance_review_role(review=review)
    present_role_default(resolution)

    assert resolution.state == ROLE_ONLY
    review.refresh_from_db()
    assert review.status == GovernanceReview.Status.OPEN
    assert review.result == ""
    assert review.reviewer is None
    assert review.history.count() == history_count


def test_delivery_role_resolution_does_not_confirm_handover_or_write_role_audit(
    business_unit,
    owner,
    reader,
):
    use_case = _use_case(
        business_unit=business_unit,
        owner=owner,
        technical_owner=reader,
    )
    package = DeliveryPackage(
        use_case=use_case,
        technical_owner=reader,
        version=1,
        status=DeliveryPackage.Status.DRAFT,
    )
    review = DeliverySectionReview(
        delivery_package=package,
        section_key=DeliverySectionReview.Section.SOLUTION_DIRECTION,
    )
    role_audit_count = DeliveryRoleSourceDecision.objects.count()

    resolutions = resolve_delivery_review_roles(package=package, review=review)
    for item in resolutions:
        present_role_default(item.resolution)

    assert [item.role for item in resolutions] == ["business", "technical"]
    assert review.business_confirmed_by is None
    assert review.business_confirmed_at is None
    assert review.technical_confirmed_by is None
    assert review.technical_confirmed_at is None
    assert package.status == DeliveryPackage.Status.DRAFT
    assert package.handed_over_by is None
    assert package.handed_over_at is None
    assert DeliveryRoleSourceDecision.objects.count() == role_audit_count


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_rendering_role_suggestions_does_not_send_assignment_or_review_email(
    client,
    business_unit,
    owner,
    coordinator,
):
    value_stream = ValueStream.objects.create(
        name="Beschaffung",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf entsteht",
        outcome="Bestellung ist ausgelöst",
        scope_in="Bedarf bis Bestellung",
    )
    stage = ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Lieferantenauswahl",
        description="Angebote vergleichen",
        actors="Einkauf",
        systems="ERP",
        documents="Angebote",
        pain_points="Vergleich ist manuell und langsam.",
        baseline_metrics="Fünf Tage",
    )
    use_case = _use_case(business_unit=business_unit, owner=owner)
    assessor = _coordinator_user(username="block9-ap6-assessor-3", business_unit=business_unit)
    _coordinator_user(username="block9-ap6-second-3", business_unit=business_unit)
    _assessment(use_case=use_case, assessor=assessor)

    mail.get_connection()
    mail.outbox.clear()
    session = client.session
    session[SESSION_KEY] = {"source_stage_id": str(stage.pk)}
    session.save()

    client.force_login(owner)
    intake_response = client.get(reverse("use_cases:create"))
    client.force_login(coordinator)
    approval_response = client.get(
        reverse("use_cases:approval_decision_create", args=[use_case.pk])
    )

    assert intake_response.status_code == 200
    assert approval_response.status_code == 200
    assert mail.outbox == []
    assert use_case.approval_decisions.count() == 0
