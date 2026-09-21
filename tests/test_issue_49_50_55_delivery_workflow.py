from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from ki_radar.delivery.actions import build_actionable_findings
from ki_radar.delivery.services import create_delivery_package, review_delivery_section
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase


def _create_package(owner, coordinator, business_unit):
    use_case = UseCase.objects.create(
        title="Assistierter Angebotsvergleich",
        summary="Angebote strukturiert vergleichen und Rückfragen reduzieren.",
        problem_statement="Uneinheitliche Angebote verlängern die Lieferantenauswahl.",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        target_users="Einkauf und Fachbereich",
        submitter=owner,
        business_owner=owner,
        technical_owner=coordinator,
        source_systems="ERP, Shared Inbox und Dateiablage",
        data_sources="Angebote, Kriterienkatalog und Lieferantenstammdaten",
        interface_description="Dateiablage und lesender ERP-Export",
        intended_users="Strategischer Einkauf",
        intended_purpose="Angebotsdaten extrahieren und vergleichbar darstellen.",
        expected_benefit="Durchlaufzeit von fünf auf drei Tage reduzieren.",
        metric_name="Durchlaufzeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Tage",
        metric_baseline=Decimal("5"),
        metric_target=Decimal("3"),
        metric_measurement_method="Median über zehn Beschaffungsvorgänge.",
        metric_measurement_period="Vier Wochen Pilotbetrieb.",
        human_oversight="Einkauf prüft Vergleich und trifft die Entscheidung.",
        support_responsibility="IT Application Management",
        decision_status=UseCase.DecisionStatus.CLARIFICATION,
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
        rationale="Prozessmessung, Datenstichprobe und technische Vorprüfung liegen vor.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Pilot und Delivery sind fachlich freigegeben.",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.save(update_fields=["decision_status", "updated_at"])
    return create_delivery_package(use_case=use_case, actor=coordinator)


@pytest.mark.django_db
def test_multiple_section_findings_explain_field_rule_and_cause(
    owner,
    coordinator,
    business_unit,
):
    package = _create_package(owner, coordinator, business_unit)
    package.out_of_scope = ""
    package.mvp_scope = ""
    package.save(update_fields=["out_of_scope", "mvp_scope", "updated_at"])

    findings = build_actionable_findings(package, coordinator)
    scope_findings = [
        finding
        for finding in findings
        if finding.section_key == "scope_and_users"
        and finding.code in {"OUT_OF_SCOPE_MISSING", "MVP_SCOPE_MISSING"}
    ]

    assert {finding.field_label for finding in scope_findings} == {
        "Nicht im Scope",
        "Must / MVP-Scope",
    }
    assert len(scope_findings) == 2
    expected_rule = "Pflichtangabe muss vollständig ausgefüllt sein."
    assert all(finding.rule == expected_rule for finding in scope_findings)
    assert all(finding.cause == finding.message for finding in scope_findings)
    assert all("highlight=" in finding.url for finding in scope_findings)


@pytest.mark.django_db
def test_detail_groups_all_findings_and_keeps_one_primary_action(
    client,
    owner,
    coordinator,
    business_unit,
):
    package = _create_package(owner, coordinator, business_unit)
    package.out_of_scope = ""
    package.mvp_scope = ""
    package.save(update_fields=["out_of_scope", "mvp_scope", "updated_at"])
    client.force_login(coordinator)

    response = client.get(package.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert content.count('data-testid="primary-readiness-action"') == 1
    assert content.count('data-testid="all-readiness-findings"') == 1
    assert 'data-section-key="scope_and_users"' in content
    assert "Nicht im Scope" in content
    assert "MVP-Scope" in content
    assert "Betroffenes Feld" in content
    assert "Readiness-Regel" in content
    assert "Konkrete Ursache" in content


@pytest.mark.django_db
def test_section_states_and_role_confirmations_are_visually_distinct(
    client,
    owner,
    coordinator,
    business_unit,
):
    package = _create_package(owner, coordinator, business_unit)
    review_delivery_section(
        package=package,
        section_key="problem_and_target",
        action="confirm_business",
        actor=owner,
        note="Problem und Ziel fachlich bestätigt.",
    )
    client.force_login(coordinator)

    response = client.get(package.get_absolute_url())
    content = response.content.decode()

    confirmed_section = (
        'class="app-card delivery-section-card delivery-section-confirmed" '
        'id="section-problem_and_target"'
    )
    blocked_section = (
        'class="app-card delivery-section-card delivery-section-blocked" '
        'id="section-scope_and_users"'
    )
    assert response.status_code == 200
    assert confirmed_section in content
    assert blocked_section in content
    assert "Fachliche Prüfung: bestätigt" in content
    assert "Technische Prüfung: nicht erforderlich" in content
    assert "Fachliche Prüfung: offen" in content


@pytest.mark.django_db
def test_package_update_renders_only_requested_editable_section(
    client,
    owner,
    coordinator,
    business_unit,
):
    package = _create_package(owner, coordinator, business_unit)
    client.force_login(coordinator)

    response = client.get(
        reverse("delivery:package_update", kwargs={"pk": package.pk}),
        {"section": "scope_and_users"},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["active_section"] == "scope_and_users"
    assert 'data-active-section="scope_and_users"' in content
    assert 'name="mvp_scope"' in content
    assert 'name="functional_requirements"' not in content
    assert content.count('data-section-key="') == 7
    assert content.count('class="btn btn-primary"') == 1


@pytest.mark.django_db
def test_focused_section_save_preserves_other_sections_and_artifacts(
    client,
    owner,
    coordinator,
    business_unit,
):
    package = _create_package(owner, coordinator, business_unit)
    original_requirements = package.functional_requirements
    original_landscape = package.architecture_artifacts.system_landscape
    client.force_login(coordinator)

    response = client.post(
        reverse("delivery:package_update", kwargs={"pk": package.pk}),
        {
            "section": "scope_and_users",
            "return_to": package.get_absolute_url(),
            "highlight": "mvp_scope",
            "in_scope": package.in_scope,
            "out_of_scope": "Automatische Bestellung bleibt außerhalb des MVP.",
            "users_and_scenarios": package.users_and_scenarios,
            "mvp_scope": "Angebote importieren, prüfen und vergleichbar darstellen.",
        },
    )

    assert response.status_code == 302
    assert response.url == package.get_absolute_url()
    package.refresh_from_db()
    package.architecture_artifacts.refresh_from_db()
    assert package.out_of_scope == "Automatische Bestellung bleibt außerhalb des MVP."
    assert package.functional_requirements == original_requirements
    assert package.architecture_artifacts.system_landscape == original_landscape
