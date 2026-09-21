from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from ki_radar.delivery.models import DeliveryPackage
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.governance.services import create_screening_review_artifacts
from ki_radar.reviews.forms import ReviewForm
from ki_radar.reviews.models import EarlyGoLiveException, Review
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase
from ki_radar.use_cases.services import (
    apply_status_transition,
    check_go_live,
)


def _early_go_live_candidate(owner, coordinator, business_unit):
    today = timezone.localdate()
    use_case = UseCase.objects.create(
        title="Früh entscheidbarer Pilot",
        summary="Der Pilot liefert früher als geplant belastbare Evidenz.",
        problem_statement="Der bestehende Prozess verursacht vermeidbare Bearbeitungszeit.",
        business_unit=business_unit,
        affected_process="Angebotsprüfung",
        target_users="Einkauf",
        submitter=owner,
        business_owner=owner,
        coordinator=coordinator,
        technical_owner=coordinator,
        status=UseCase.Status.PILOT,
        decision_status=UseCase.DecisionStatus.APPROVED,
        data_sources="ERP und Dokumentenablage",
        expected_benefit="Bearbeitungszeit reduzieren.",
        next_review_date=today + timedelta(days=90),
        pilot_start=today - timedelta(days=14),
        planned_pilot_end=today + timedelta(days=30),
        metric_name="Bearbeitungszeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Minuten",
        metric_baseline=Decimal("30"),
        metric_target=Decimal("10"),
        metric_actual=Decimal("8"),
        metric_measurement_method="Zeitmessung bei 20 Fällen",
        metric_measurement_period="Pilotwochen 1 bis 2",
        metric_measured_at=today,
        metric_evidence_url="https://example.com/pilot-evidence",
        one_time_cost=Decimal("5000"),
        recurring_cost=Decimal("300"),
        support_responsibility="IT-Service",
        human_oversight="Fachliche Entscheidung bleibt manuell.",
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
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    decision = ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Pilot und Delivery sind freigegeben.",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    DeliveryPackage.objects.create(
        use_case=use_case,
        version=1,
        status=DeliveryPackage.Status.HANDED_OVER,
        generated_from_decision=decision,
        created_by=coordinator,
        handed_over_by=coordinator,
        handed_over_at=timezone.now(),
    )
    return use_case


def _scale_evidence():
    return {
        "scale_tailoring_level": "C",
        "scale_pilot_validation_confirmed": True,
        "scale_production_version": "release-2026.08.23",
        "scale_rollback_tested": True,
        "scale_technical_monitoring_ready": True,
        "scale_ai_quality_monitoring_ready": True,
        "scale_incident_process_ready": True,
        "scale_extended_controls_completed": True,
        "scale_evidence_url": "https://example.com/evidence/operations",
        "ml_score_data": Decimal("6.0"),
        "ml_score_model": Decimal("6.0"),
        "ml_score_infrastructure": Decimal("6.0"),
        "ml_score_monitoring": Decimal("6.0"),
        "ml_score_minimum": Decimal("5.0"),
        "ml_score_version": "mlts-2026-08-23",
        "ml_score_date": timezone.localdate(),
        "ml_score_evidence_url": "https://example.com/evidence/ml-test-score",
        "ml_score_open_core_checks": "",
        "ml_score_failed_mandatory_checks": "",
    }


def _go_live_data(use_case, coordinator, **overrides):
    data = {
        "review_date": timezone.localdate(),
        "decision": Review.Decision.GO_LIVE,
        "new_status": UseCase.Status.OPERATION,
        "rationale": "Die vorhandene Evidenz trägt eine kontrollierte vorzeitige Entscheidung.",
        "go_live_exception_confirmed": False,
        "early_go_live_exception_confirmed": True,
        "early_go_live_original_pilot_end": use_case.planned_pilot_end,
        "early_go_live_evidence_basis": "Vierzehn Tage Messung mit repräsentativen Fällen.",
        "early_go_live_unobserved_risks": "Saisonale Lastspitzen wurden noch nicht beobachtet.",
        "early_go_live_mitigation_measures": (
            "Begrenzter Nutzerkreis, tägliches Monitoring und Rückfalloption."
        ),
        "open_actions": "Messung bis zum ursprünglichen Pilotende fortführen.",
        "action_owner": coordinator,
        "action_due_date": use_case.planned_pilot_end,
        "next_review_date": use_case.next_review_date,
        **_scale_evidence(),
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_future_pilot_end_is_go_live_readiness(owner, coordinator, business_unit):
    use_case = _early_go_live_candidate(owner, coordinator, business_unit)

    check = check_go_live(use_case)

    assert check.state == "review"
    assert check.blockers == []
    assert any("Pilotende" in warning for warning in check.warnings)


@pytest.mark.django_db
def test_direct_transition_is_fenced_by_canonical_review_command(
    owner,
    coordinator,
    business_unit,
):
    use_case = _early_go_live_candidate(owner, coordinator, business_unit)

    with pytest.raises(ValidationError, match=r"reviews\.services\.create_review"):
        apply_status_transition(
            use_case=use_case,
            target_status=UseCase.Status.OPERATION,
            actor=coordinator,
            scale_evidence=_scale_evidence(),
        )


@pytest.mark.django_db
def test_early_go_live_needs_no_separate_exception(owner, coordinator, business_unit):
    use_case = _early_go_live_candidate(owner, coordinator, business_unit)

    review = create_review(
        use_case=use_case,
        actor=coordinator,
        data=_go_live_data(
            use_case,
            coordinator,
            early_go_live_exception_confirmed=False,
        ),
    )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.OPERATION
    assert review.decision == Review.Decision.GO_LIVE
    assert EarlyGoLiveException.objects.count() == 0


@pytest.mark.django_db
def test_coordinator_exception_is_persisted_as_separate_audit_artifact(
    owner,
    coordinator,
    business_unit,
):
    use_case = _early_go_live_candidate(owner, coordinator, business_unit)
    original_pilot_end = use_case.planned_pilot_end

    review = create_review(
        use_case=use_case,
        actor=coordinator,
        data=_go_live_data(use_case, coordinator),
    )

    use_case.refresh_from_db()
    artifact = review.early_go_live_exception
    assert use_case.status == UseCase.Status.OPERATION
    assert use_case.planned_pilot_end == original_pilot_end
    assert review.go_live_exception_confirmed is False
    assert artifact.original_planned_pilot_end == original_pilot_end
    assert artifact.decision_date == review.review_date
    assert artifact.reason == review.rationale
    assert artifact.evidence_basis.startswith("Vierzehn Tage")
    assert "Saisonale" in artifact.unobserved_risks
    assert "Monitoring" in artifact.mitigation_measures
    assert artifact.confirmed_by == coordinator
    assert artifact.confirmed_by_label == coordinator.get_display_name()
    assert artifact.confirmed_role == "KI-Koordinator"
    assert artifact.created_at is not None


@pytest.mark.django_db
def test_early_exception_cannot_override_mandatory_go_live_blockers(
    owner,
    coordinator,
    business_unit,
):
    use_case = _early_go_live_candidate(owner, coordinator, business_unit)
    screening = GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=coordinator,
        basis_version="Issue 43",
        privacy_review_required=True,
        result=GovernanceAssessment.Result.PRIVACY,
        privacy_review_rationale="Datenschutzprüfung ist vor Go-live erforderlich.",
    )
    create_screening_review_artifacts(assessment=screening, actor=coordinator)

    with pytest.raises(ValidationError, match="Datenschutzprüfung"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data=_go_live_data(use_case, coordinator),
        )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.PILOT
    assert Review.objects.count() == 0
    assert EarlyGoLiveException.objects.count() == 0


@pytest.mark.django_db
def test_early_exception_does_not_replace_failed_target_exception(
    owner,
    coordinator,
    business_unit,
):
    use_case = _early_go_live_candidate(owner, coordinator, business_unit)
    use_case.metric_actual = Decimal("12")
    use_case.save(update_fields=["metric_actual", "updated_at"])

    with pytest.raises(ValidationError, match="verfehltem Pilotziel"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data=_go_live_data(use_case, coordinator),
        )


@pytest.mark.django_db
def test_go_live_form_exposes_separate_early_exception_fields(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = _early_go_live_candidate(owner, coordinator, business_unit)
    client.force_login(coordinator)
    base_url = reverse("reviews:create", kwargs={"use_case_id": use_case.pk})

    for url in [base_url, base_url + "?action=go_live"]:
        response = client.get(url)

        assert response.status_code == 200
        form = response.context["form"]
        assert isinstance(form, ReviewForm)
        assert "early_go_live_exception_confirmed" in form.fields
        assert "early_go_live_original_pilot_end" in form.fields
        assert form.fields["early_go_live_original_pilot_end"].disabled is True
        assert "early_go_live_evidence_basis" in form.fields
        assert "early_go_live_unobserved_risks" in form.fields
        assert "early_go_live_mitigation_measures" in form.fields
        assert "Vorzeitige Produktivsetzung ausdrücklich bestätigen" in response.content.decode()
