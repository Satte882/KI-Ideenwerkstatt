from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from config.settings.base import openrouter_api_url
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.use_cases.copilot import CopilotUnavailable, analyze_use_case
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase
from ki_radar.use_cases.services import (
    check_go_live,
    check_pilot_start,
    current_decision_check,
    validate_target_status,
)


@pytest.fixture
def decision_use_case(owner, coordinator, business_unit):
    use_case = UseCase.objects.create(
        title="Rechnungsprüfung",
        problem_statement="Rechnungen werden manuell geprüft.",
        business_unit=business_unit,
        affected_process="Eingangsrechnung",
        business_owner=owner,
        coordinator=coordinator,
        expected_benefit="Prüfzeit reduzieren",
        data_sources="ERP und Dokumentenablage",
        next_review_date=timezone.localdate() + timedelta(days=14),
        planned_pilot_end=timezone.localdate() + timedelta(days=30),
        decision_status=UseCase.DecisionStatus.APPROVED,
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
    GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=coordinator,
        basis_version="test-screening-v1",
        result=GovernanceAssessment.Result.NO_FLAGS,
    )
    return use_case


@pytest.mark.django_db
def test_idea_is_checked_for_review_before_pilot(decision_use_case):
    decision_use_case.status = UseCase.Status.IDEA

    check = current_decision_check(decision_use_case)

    assert check.target_status == UseCase.Status.REVIEW
    assert check.title == UseCase.Status.REVIEW.label
    assert "Primäre Erfolgsmetrik" not in check.blockers


@pytest.mark.django_db
def test_pilot_start_shows_structured_metric_as_readiness(decision_use_case):
    decision_use_case.status = UseCase.Status.REVIEW
    decision_use_case.save(update_fields=["status", "updated_at"])

    check = check_pilot_start(decision_use_case)

    assert check.state == "review"
    assert "Readiness offen: Primäre Erfolgsmetrik" in check.warnings
    validate_target_status(decision_use_case, UseCase.Status.PILOT)


@pytest.mark.django_db
def test_decision_blockers_use_user_facing_labels(decision_use_case):
    decision_use_case.status = UseCase.Status.REVIEW
    decision_use_case.planned_pilot_end = None
    decision_use_case.next_review_date = None
    decision_use_case.data_sources = ""
    decision_use_case.save()

    check = check_pilot_start(decision_use_case)

    assert "Readiness offen: Geplantes Pilotende" in check.warnings
    assert "Readiness offen: Nächster Entscheidungstermin" in check.warnings
    assert "Readiness offen: Datenquellen" in check.warnings
    assert "planned pilot end" not in check.warnings


@pytest.mark.django_db
def test_go_live_compares_target_and_actual(decision_use_case, coordinator):
    decision_use_case.status = UseCase.Status.PILOT
    decision_use_case.pilot_start = timezone.localdate()
    decision_use_case.technical_owner = coordinator
    decision_use_case.one_time_cost = Decimal("5000")
    decision_use_case.recurring_cost = Decimal("300")
    decision_use_case.support_responsibility = "IT-Service"
    decision_use_case.human_oversight = "Fachliche Freigabe bleibt manuell"
    decision_use_case.metric_name = "Prüfzeit je Rechnung"
    decision_use_case.metric_type = UseCase.MetricType.DURATION
    decision_use_case.metric_direction = UseCase.MetricDirection.LOWER
    decision_use_case.metric_unit = "Minuten"
    decision_use_case.metric_baseline = Decimal("11")
    decision_use_case.metric_target = Decimal("8.25")
    decision_use_case.metric_actual = Decimal("8.9")
    decision_use_case.metric_measurement_method = "100 Rechnungen"
    decision_use_case.metric_measurement_period = "Pilotwochen 5 bis 8"
    decision_use_case.metric_measured_at = timezone.localdate()
    decision_use_case.metric_evidence_url = "https://example.invalid/evidence"
    decision_use_case.planned_pilot_end = timezone.localdate()
    decision_use_case.save()

    check = check_go_live(decision_use_case)

    assert check.state == "review"
    assert decision_use_case.metric_result == UseCase.MetricResult.NOT_ACHIEVED
    assert "Pilotziel wurde nicht erreicht" in check.warnings[0]


@pytest.mark.django_db
def test_go_live_rechecks_complete_target_metric(decision_use_case, coordinator):
    decision_use_case.status = UseCase.Status.PILOT
    decision_use_case.technical_owner = coordinator
    decision_use_case.one_time_cost = Decimal("5000")
    decision_use_case.recurring_cost = Decimal("300")
    decision_use_case.support_responsibility = "IT-Service"
    decision_use_case.human_oversight = "Fachliche Freigabe bleibt manuell"
    decision_use_case.metric_actual = Decimal("8.9")
    decision_use_case.metric_measurement_period = "Pilotwochen 5 bis 8"
    decision_use_case.metric_measured_at = timezone.localdate()
    decision_use_case.metric_evidence_url = "https://example.invalid/evidence"
    decision_use_case.save()

    check = check_go_live(decision_use_case)

    assert check.state == "blocked"
    assert "Primäre Erfolgsmetrik" in check.blockers
    assert "Zielwert" in check.blockers


@pytest.mark.django_db
def test_metric_result_is_achieved_for_lower_target(decision_use_case):
    decision_use_case.metric_name = "Prüfzeit"
    decision_use_case.metric_direction = UseCase.MetricDirection.LOWER
    decision_use_case.metric_target = Decimal("8.25")
    decision_use_case.metric_actual = Decimal("8.0")

    assert decision_use_case.metric_result == UseCase.MetricResult.ACHIEVED


@pytest.mark.django_db
def test_copilot_is_optional_without_openrouter_key(settings, decision_use_case):
    settings.OPENROUTER_API_KEY = ""

    with pytest.raises(CopilotUnavailable, match="Kein OpenRouter API-Key"):
        analyze_use_case(decision_use_case)


@pytest.mark.django_db
def test_copilot_button_is_enabled_when_openrouter_key_is_configured(
    client,
    settings,
    coordinator,
    decision_use_case,
):
    settings.OPENROUTER_API_KEY = "test-key-not-rendered"
    client.force_login(coordinator)

    response = client.get(decision_use_case.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert "OpenRouter ist nicht konfiguriert" not in content
    assert "test-key-not-rendered" not in content
    assert '<button class="btn btn-outline-secondary btn-sm" >Analyse starten</button>' in content


def test_openrouter_url_can_be_derived_from_openai_compatible_base_url(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_URL", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")

    assert openrouter_api_url() == "https://openrouter.ai/api/v1/chat/completions"


@pytest.mark.django_db
def test_copilot_endpoint_rejects_non_coordinator(client, owner, decision_use_case):
    client.force_login(owner)

    response = client.post(reverse("use_cases:copilot", args=[decision_use_case.pk]))

    assert response.status_code == 403
