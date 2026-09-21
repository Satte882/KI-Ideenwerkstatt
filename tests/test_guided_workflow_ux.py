from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from ki_radar.core.navigation import safe_internal_url, with_return_to
from ki_radar.delivery.actions import primary_delivery_action
from ki_radar.delivery.forms import DeliveryPackageForm
from ki_radar.delivery.services import create_delivery_package
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.reporting.templatetags.worklist_tags import worklist_rows
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase
from ki_radar.use_cases.workflow import build_use_case_journey


def make_use_case(owner, business_unit, **overrides):
    data = {
        "title": "Automatische Rechnungsprüfung",
        "summary": "Eingangsrechnungen strukturiert vorprüfen.",
        "problem_statement": "Rechnungen werden manuell gegen Bestellung und Wareneingang geprüft.",
        "business_unit": business_unit,
        "affected_process": "Eingangsrechnungsprüfung",
        "target_users": "Einkauf und Buchhaltung",
        "submitter": owner,
        "business_owner": owner,
        "technical_owner": owner,
        "source_systems": "ERP und Dateiablage",
        "data_sources": "Rechnungen, Bestellungen und Wareneingänge",
        "interface_description": "Dateiimport und ERP-Export",
        "intended_users": "Sachbearbeitung",
        "intended_purpose": "Abweichungen vor der Freigabe erkennen.",
        "expected_benefit": "Prüfzeit und Rückfragen reduzieren.",
        "metric_name": "Prüfzeit",
        "metric_type": UseCase.MetricType.DURATION,
        "metric_direction": UseCase.MetricDirection.LOWER,
        "metric_unit": "Minuten",
        "metric_baseline": Decimal("20"),
        "metric_target": Decimal("10"),
        "metric_measurement_method": "Median über zwanzig Rechnungen.",
        "metric_measurement_period": "Vier Wochen Pilot.",
        "human_oversight": "Sachbearbeitung bestätigt jede Abweichung.",
        "support_responsibility": "IT Application Management",
        "decision_status": UseCase.DecisionStatus.CLARIFICATION,
        "next_review_date": timezone.localdate() + timedelta(days=14),
    }
    data.update(overrides)
    return UseCase.objects.create(**data)


def approve_use_case(use_case, coordinator):
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
        rationale="Fachliche und technische Vorprüfung liegen vor.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    decision = ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Delivery ist freigegeben.",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.save(update_fields=["decision_status", "updated_at"])
    GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=coordinator,
        basis_version="Governance-Leitlinie 1.0",
        result=GovernanceAssessment.Result.NO_FLAGS,
        rationale="Keine vertiefte Governance-Prüfung erforderlich.",
    )
    return decision


def make_package(owner, coordinator, business_unit, **use_case_overrides):
    use_case = make_use_case(owner, business_unit, **use_case_overrides)
    approve_use_case(use_case, coordinator)
    return use_case, create_delivery_package(use_case=use_case, actor=coordinator)


@pytest.mark.django_db
def test_missing_technical_owner_is_the_primary_delivery_action(
    owner,
    coordinator,
    business_unit,
):
    use_case, package = make_package(
        owner,
        coordinator,
        business_unit,
        technical_owner=None,
    )

    action = primary_delivery_action(package, owner)

    assert action is not None
    assert action.code == "TECHNICAL_OWNER_MISSING"
    assert action.priority_class == 1
    assert action.title == "Technical Owner benennen"
    assert reverse("use_cases:edit", kwargs={"pk": use_case.pk}) in action.url
    assert "highlight=technical_owner" in action.url
    assert "return_to=" in action.url


@pytest.mark.django_db
def test_role_collapse_assignment_explains_the_actual_control_rule(
    client,
    owner,
    coordinator,
    business_unit,
):
    _use_case, package = make_package(
        owner,
        coordinator,
        business_unit,
        technical_owner=owner,
        priority=UseCase.Priority.CRITICAL,
    )
    client.force_login(owner)

    response = client.get(package.get_absolute_url())
    body = response.content.decode()

    assert response.status_code == 200
    assert "Zusammengeführte Verantwortung" in body
    assert "Bestätigt dieselbe Person beide Rollen" in body
    assert "unabhängige Kontrolle erforderlich" in body


@pytest.mark.django_db
def test_same_person_receives_business_and_technical_edit_sections(
    owner,
    coordinator,
    business_unit,
):
    _use_case, package = make_package(
        owner,
        coordinator,
        business_unit,
        technical_owner=owner,
    )

    form = DeliveryPackageForm(instance=package, actor=owner)

    assert all(group["editable"] for group in form.section_groups)


@pytest.mark.django_db
def test_worklist_sorts_priority_before_due_date_and_then_due_date(
    owner,
    coordinator,
    business_unit,
):
    future_use_case, _future_package = make_package(
        owner,
        coordinator,
        business_unit,
        title="P1 künftig",
        technical_owner=None,
        next_review_date=timezone.localdate() + timedelta(days=10),
    )
    overdue_use_case, _overdue_package = make_package(
        owner,
        coordinator,
        business_unit,
        title="P1 überfällig",
        technical_owner=None,
        next_review_date=timezone.localdate() - timedelta(days=2),
    )
    lower_priority_use_case, _lower_package = make_package(
        owner,
        coordinator,
        business_unit,
        title="P3 überfällig",
        technical_owner=owner,
        next_review_date=timezone.localdate() - timedelta(days=5),
    )

    items = [lower_priority_use_case, future_use_case, overdue_use_case]
    for item in items:
        item.journey = build_use_case_journey(item, coordinator)
        item.decision_due = item.next_review_date

    request = RequestFactory().get("/worklist/")
    request.user = coordinator
    rows = worklist_rows({"request": request}, items)

    assert [row["use_case"] for row in rows] == [
        overdue_use_case,
        future_use_case,
        lower_priority_use_case,
    ]
    assert [row["priority_class"] for row in rows] == [1, 1, 3]


@pytest.mark.django_db
def test_direct_intake_remains_a_supported_short_path(owner, business_unit):
    use_case = make_use_case(owner, business_unit)

    journey = build_use_case_journey(use_case, owner)

    assert journey.path_label == "Direkter Intake"
    assert journey.steps[0].key == "value_stream"
    assert journey.steps[0].state == "optional"
    assert journey.steps[1].key == "focus"
    assert journey.steps[1].state == "optional"


@pytest.mark.django_db
def test_delivery_detail_exposes_direct_primary_action_and_not_applicable_guidance(
    client,
    owner,
    coordinator,
    business_unit,
):
    _use_case, package = make_package(
        owner,
        coordinator,
        business_unit,
        technical_owner=None,
    )
    client.force_login(owner)

    response = client.get(package.get_absolute_url())
    body = response.content.decode()

    assert response.status_code == 200
    assert 'data-testid="primary-readiness-action"' in body
    assert "Technical Owner benennen" in body
    assert "Technical Owner zuordnen" in body
    assert "bei Blockierung oder „Nicht relevant“ verpflichtend" in body
    assert "data-requires-review-note" in body


@pytest.mark.django_db
def test_delivery_form_collapses_sections_owned_by_another_role(
    client,
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    _use_case, package = make_package(
        owner,
        coordinator,
        business_unit,
        technical_owner=other_owner,
    )
    client.force_login(owner)

    response = client.get(reverse("delivery:package_update", kwargs={"pk": package.pk}))
    body = response.content.decode()

    assert response.status_code == 200
    assert 'id="id_problem_context"' in body
    assert 'id="id_system_landscape"' not in body
    assert "Technical Owner (Technik, Daten und KI)" in body
    assert "Nur lesen" in body


@pytest.mark.django_db
def test_worklist_ui_uses_stable_route_with_new_visible_labels(client, coordinator):
    client.force_login(coordinator)

    response = client.get(reverse("reporting:dashboard"))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Arbeitsvorrat" in body
    assert "Meine Aufgaben" in body
    assert "Anstehende Entscheidungen" in body
    assert "Entscheidungswarteschlange" not in body


def test_return_navigation_rejects_external_targets_and_preserves_internal_fragments():
    request = RequestFactory().get("/source/", HTTP_HOST="testserver")

    assert safe_internal_url(request, "https://evil.example/path", "/fallback/") == "/fallback/"
    assert safe_internal_url(request, "/delivery/123/", "/fallback/") == "/delivery/123/"

    target = with_return_to(
        "/use-cases/1/edit/?highlight=technical_owner#field-technical_owner", "/delivery/123/"
    )
    assert "highlight=technical_owner" in target
    assert "return_to=%2Fdelivery%2F123%2F" in target
    assert target.endswith("#field-technical_owner")
