from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.services import hand_over_package
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.reviews.forms import ReviewForm
from ki_radar.reviews.models import Review
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase


@pytest.fixture
def use_case(owner, business_unit):
    return UseCase.objects.create(
        title="Idee",
        problem_statement="Problem",
        business_unit=business_unit,
        affected_process="Prozess",
        business_owner=owner,
        expected_benefit="Nutzen",
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


def prepare_failed_pilot(use_case, coordinator):
    today = timezone.localdate()
    use_case.status = UseCase.Status.PILOT
    use_case.pilot_start = today
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.data_sources = "ERP und Dokumentenablage"
    use_case.planned_pilot_end = today
    use_case.technical_owner = coordinator
    use_case.one_time_cost = Decimal("5000")
    use_case.recurring_cost = Decimal("300")
    use_case.support_responsibility = "IT-Service"
    use_case.human_oversight = "Fachliche Freigabe bleibt manuell"
    use_case.metric_name = "Bearbeitungszeit"
    use_case.metric_type = UseCase.MetricType.DURATION
    use_case.metric_direction = UseCase.MetricDirection.LOWER
    use_case.metric_unit = "Minuten"
    use_case.metric_baseline = Decimal("30")
    use_case.metric_target = Decimal("10")
    use_case.metric_actual = Decimal("12")
    use_case.metric_measurement_method = "Zeitmessung bei 20 Fällen"
    use_case.metric_measurement_period = "Pilotwochen 1 bis 4"
    use_case.metric_measured_at = today
    use_case.metric_evidence_url = "https://example.invalid/evidence"
    use_case.save()
    decision = create_final_approval(use_case, coordinator)
    DeliveryPackage.objects.create(
        use_case=use_case,
        version=1,
        status=DeliveryPackage.Status.HANDED_OVER,
        generated_from_decision=decision,
        created_by=coordinator,
        handed_over_by=coordinator,
        handed_over_at=timezone.now(),
    )
    return today


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
        "scale_evidence_url": "https://example.invalid/evidence/operations",
        "ml_score_data": Decimal("6.0"),
        "ml_score_model": Decimal("6.0"),
        "ml_score_infrastructure": Decimal("6.0"),
        "ml_score_monitoring": Decimal("6.0"),
        "ml_score_minimum": Decimal("5.0"),
        "ml_score_version": "mlts-2026-08-23",
        "ml_score_date": timezone.localdate(),
        "ml_score_evidence_url": "https://example.invalid/evidence/ml-test-score",
        "ml_score_open_core_checks": "",
        "ml_score_failed_mandatory_checks": "",
    }


@pytest.mark.django_db
def test_only_coordinator_can_open_review_form(client, owner, coordinator, use_case):
    client.force_login(owner)
    assert client.get(reverse("reviews:create", args=[use_case.pk])).status_code == 403
    client.force_login(coordinator)
    assert client.get(reverse("reviews:create", args=[use_case.pk])).status_code == 200


@pytest.mark.django_db
def test_review_form_uses_german_decision_labels(use_case):
    form = ReviewForm(use_case=use_case)

    assert form.fields["review_date"].label == "Review-Datum"
    assert form.fields["decision"].label == "Entscheidung"
    assert form.fields["new_status"].label == "Neuer Status"
    assert form.fields["rationale"].label == "Entscheidungsbegründung"


@pytest.mark.django_db
def test_review_form_renders_date_inputs_in_browser_format(use_case):
    localized_today = timezone.localdate().strftime("%d.%m.%Y")
    form = ReviewForm(use_case=use_case)

    assert f'value="{timezone.localdate().isoformat()}"' in form.as_p()
    assert localized_today not in form.as_p()


@pytest.mark.django_db
def test_review_form_preselects_next_decision(use_case):
    form = ReviewForm(use_case=use_case)

    assert form.fields["decision"].initial == Review.Decision.START_REVIEW
    assert form.fields["new_status"].initial == UseCase.Status.REVIEW


@pytest.mark.django_db
def test_review_form_preselects_operation_continuation(use_case):
    use_case.status = UseCase.Status.OPERATION
    use_case.save()

    form = ReviewForm(use_case=use_case)

    assert form.fields["decision"].initial == Review.Decision.CONTINUE
    assert form.fields["new_status"].initial == UseCase.Status.OPERATION


@pytest.mark.django_db
def test_bound_review_form_keeps_submitted_decision(use_case):
    form = ReviewForm(
        {
            "review_date": timezone.localdate(),
            "decision": Review.Decision.REWORK,
            "new_status": UseCase.Status.IDEA,
            "rationale": "Nochmals überarbeiten.",
            "open_actions": "",
            "action_owner": "",
            "action_due_date": "",
            "next_review_date": "",
        },
        use_case=use_case,
    )

    assert form.fields["decision"].initial is None
    assert form.is_valid()


@pytest.mark.django_db
def test_continue_review_keeps_status(client, coordinator, use_case):
    use_case.status = UseCase.Status.REVIEW
    use_case.save(update_fields=["status", "updated_at"])
    client.force_login(coordinator)
    response = client.post(
        reverse("reviews:create", args=[use_case.pk]),
        {
            "review_date": timezone.localdate(),
            "decision": Review.Decision.CONTINUE,
            "new_status": UseCase.Status.REVIEW,
            "rationale": "Weiter prüfen",
            "open_actions": "",
            "action_owner": "",
            "action_due_date": "",
            "next_review_date": timezone.localdate(),
        },
    )
    assert response.status_code == 302
    assert Review.objects.count() == 1


@pytest.mark.django_db
def test_review_can_supply_required_review_date_for_pilot_transition(coordinator, use_case):
    today = timezone.localdate()
    use_case.status = UseCase.Status.REVIEW
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.data_sources = "Freigegebene Wissensbasis"
    use_case.planned_pilot_end = today
    use_case.metric_name = "Bearbeitungszeit"
    use_case.metric_type = UseCase.MetricType.DURATION
    use_case.metric_direction = UseCase.MetricDirection.LOWER
    use_case.metric_unit = "Minuten"
    use_case.metric_baseline = Decimal("30")
    use_case.metric_target = Decimal("10")
    use_case.metric_measurement_method = "Zeitmessung bei 20 Fällen"
    use_case.save()
    GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=today,
        reviewer=coordinator,
        basis_version="2026-01",
        result=GovernanceAssessment.Result.NO_FLAGS,
        rationale="Keine besonderen Hinweise",
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

    review = create_review(
        use_case=use_case,
        actor=coordinator,
        data={
            "review_date": today,
            "pilot_start": today,
            "decision": Review.Decision.START_PILOT,
            "new_status": UseCase.Status.PILOT,
            "rationale": "Pilot ist fachlich vorbereitet",
            "open_actions": "",
            "action_owner": None,
            "action_due_date": None,
            "next_review_date": today,
        },
    )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.PILOT
    assert use_case.pilot_start == today
    assert use_case.next_review_date == today
    assert use_case.history.first().history_user == coordinator
    assert review.history.first().history_user == coordinator


@pytest.mark.django_db
def test_failed_pilot_cannot_go_live_without_confirmed_exception(coordinator, use_case):
    today = prepare_failed_pilot(use_case, coordinator)

    with pytest.raises(ValidationError, match="ausdrücklich bestätigte Ausnahme"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data={
                "review_date": today,
                "decision": Review.Decision.GO_LIVE,
                "new_status": UseCase.Status.OPERATION,
                "rationale": "Nutzen reicht trotz Zielabweichung für einen begrenzten Betrieb.",
                "go_live_exception_confirmed": False,
                "open_actions": "",
                "action_owner": None,
                "action_due_date": None,
                "next_review_date": today,
                **_scale_evidence(),
            },
        )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.PILOT
    assert Review.objects.count() == 0


@pytest.mark.django_db
def test_confirmed_go_live_exception_is_persisted(coordinator, use_case):
    today = prepare_failed_pilot(use_case, coordinator)

    review = create_review(
        use_case=use_case,
        actor=coordinator,
        data={
            "review_date": today,
            "decision": Review.Decision.GO_LIVE,
            "new_status": UseCase.Status.OPERATION,
            "rationale": "Nutzen reicht trotz Zielabweichung für einen begrenzten Betrieb.",
            "go_live_exception_confirmed": True,
            "open_actions": "Zielwert nach drei Monaten erneut prüfen.",
            "action_owner": coordinator,
            "action_due_date": today,
            "next_review_date": today,
            **_scale_evidence(),
        },
    )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.OPERATION
    assert review.go_live_exception_confirmed is True
    assert review.history.first().go_live_exception_confirmed is True
