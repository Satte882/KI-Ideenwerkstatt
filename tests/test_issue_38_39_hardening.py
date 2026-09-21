from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from ki_radar.delivery.models import DeliveryRoleSourceDecision
from ki_radar.delivery.permissions import can_resolve_role_source
from ki_radar.delivery.services import (
    create_delivery_package,
    resolve_technical_owner_source_change,
)
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase


def _approved_use_case(*, owner, technical_owner, coordinator, business_unit):
    use_case = UseCase.objects.create(
        title="Audit-Härtung",
        problem_statement="Uneindeutige Rollenquelle",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        business_owner=owner,
        technical_owner=technical_owner,
        coordinator=coordinator,
        expected_benefit="Nachvollziehbarkeit",
        metric_name="Durchlaufzeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Minuten",
        metric_baseline=Decimal("11"),
        metric_target=Decimal("8.25"),
        metric_measurement_method="Median",
        human_oversight="Fachliche Prüfung",
        support_responsibility="IT",
    )
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
        evidence_url="https://example.com/evidence",
        rationale="Geprüft",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Freigegeben",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.save(update_fields=["decision_status", "updated_at"])
    return use_case


@pytest.mark.django_db
def test_all_involved_authorized_roles_can_resolve_role_source(
    owner,
    other_owner,
    coordinator,
    technical_admin,
    business_unit,
    django_user_model,
):
    new_owner = django_user_model.objects.create_user(username="new-tech", password="x")
    use_case = _approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    use_case.technical_owner = new_owner
    use_case.save(update_fields=["technical_owner", "updated_at"])

    assert can_resolve_role_source(owner, package)
    assert can_resolve_role_source(other_owner, package)
    assert can_resolve_role_source(new_owner, package)
    assert can_resolve_role_source(coordinator, package)
    assert can_resolve_role_source(technical_admin, package)


@pytest.mark.django_db
def test_role_source_audit_rejects_bulk_mutation_and_parent_deletion(
    owner,
    other_owner,
    coordinator,
    business_unit,
    django_user_model,
):
    new_owner = django_user_model.objects.create_user(username="replacement-tech", password="x")
    use_case = _approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    use_case.technical_owner = new_owner
    use_case.save(update_fields=["technical_owner", "updated_at"])
    decision = resolve_technical_owner_source_change(
        package=package,
        action=DeliveryRoleSourceDecision.Decision.ADOPT_SOURCE,
        rationale="Die neue technische Verantwortung gilt für diese Version.",
        actor=owner,
    )

    with pytest.raises(ValidationError, match="unveränderlich"):
        DeliveryRoleSourceDecision.objects.filter(pk=decision.pk).update(rationale="Manipuliert")
    with pytest.raises(ValidationError, match="unveränderlich"):
        DeliveryRoleSourceDecision.objects.filter(pk=decision.pk).delete()
    with pytest.raises(ProtectedError):
        package.delete()
