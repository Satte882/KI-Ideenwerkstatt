from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from ki_radar.delivery.actions import primary_delivery_action
from ki_radar.delivery.models import DeliveryRoleSourceDecision
from ki_radar.delivery.services import (
    create_delivery_package,
    resolve_technical_owner_source_change,
)
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase


def make_approved_use_case(
    *, owner, technical_owner, coordinator, business_unit, title="Issue 321"
):
    use_case = UseCase.objects.create(
        title=title,
        summary="Angebote strukturiert vergleichen.",
        problem_statement="Uneinheitliche Angebote erzeugen Rückfragen.",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        target_users="Einkauf",
        submitter=owner,
        business_owner=owner,
        technical_owner=technical_owner,
        source_systems="ERP, Shared Inbox, Dateiablage",
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
        human_oversight="Einkauf prüft und entscheidet.",
        support_responsibility="Application Management",
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
        evidence_url="https://example.com/evidence",
        rationale="Repräsentative Messung und technische Vorprüfung liegen vor.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Freigabe für Delivery.",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    return use_case


def make_package(*, owner, technical_owner, coordinator, business_unit, title="Issue 321"):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=technical_owner,
        coordinator=coordinator,
        business_unit=business_unit,
        title=title,
    )
    return use_case, create_delivery_package(use_case=use_case, actor=coordinator)


@pytest.mark.django_db
def test_owner_loop_state_a_still_routes_to_use_case_correction(
    owner, other_owner, coordinator, business_unit
):
    use_case, package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package.technical_owner = None
    package.save(update_fields=["technical_owner", "updated_at"])
    use_case.technical_owner = None
    use_case.save(update_fields=["technical_owner", "updated_at"])

    action = primary_delivery_action(package, coordinator)

    assert action is not None
    assert action.code == "TECHNICAL_OWNER_MISSING"
    assert action.action_label == "Technical Owner zuordnen"
    assert reverse("use_cases:edit", kwargs={"pk": use_case.pk}) in action.url
    assert "highlight=technical_owner" in action.url


@pytest.mark.django_db
def test_owner_loop_state_b_routes_missing_package_owner_to_source_decision(
    owner, other_owner, coordinator, business_unit
):
    use_case, package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package.technical_owner = None
    package.save(update_fields=["technical_owner", "updated_at"])
    use_case.technical_owner = owner
    use_case.save(update_fields=["technical_owner", "updated_at"])

    action = primary_delivery_action(package, coordinator)

    assert action is not None
    assert action.code == "TECHNICAL_OWNER_MISSING"
    assert action.title == "Änderung des Technical Owners entscheiden"
    assert action.action_label == "Abweichung auflösen"
    assert action.url == f"{package.get_absolute_url()}#technical-owner-source-change"


@pytest.mark.django_db
def test_owner_loop_state_c_keeps_existing_source_decision_route(
    owner, other_owner, coordinator, business_unit
):
    use_case, package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    use_case.technical_owner = owner
    use_case.save(update_fields=["technical_owner", "updated_at"])

    action = primary_delivery_action(package, coordinator)

    assert action is not None
    assert action.code == "TECHNICAL_OWNER_SOURCE_CHANGE_UNRESOLVED"
    assert action.action_label == "Abweichung auflösen"
    assert action.url == f"{package.get_absolute_url()}#technical-owner-source-change"


@pytest.mark.django_db
def test_owner_loop_handed_over_snapshot_routes_to_visible_source_decision(
    owner, other_owner, coordinator, business_unit
):
    use_case, package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package.technical_owner = None
    package.status = package.Status.HANDED_OVER
    package.save(update_fields=["technical_owner", "status", "updated_at"])
    use_case.technical_owner = owner
    use_case.save(update_fields=["technical_owner", "updated_at"])

    action = primary_delivery_action(package, coordinator)

    assert action is not None
    assert action.code == "TECHNICAL_OWNER_MISSING"
    assert action.title == "Änderung des Technical Owners entscheiden"
    assert action.action_label == "Abweichung auflösen"
    assert action.url == f"{package.get_absolute_url()}#technical-owner-source-change"


@pytest.mark.django_db
def test_source_decision_rejects_inapplicable_keep_and_adopt_actions(
    owner, other_owner, coordinator, business_unit
):
    keep_use_case, keep_package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
        title="KEEP invalid",
    )
    keep_package.technical_owner = None
    keep_package.save(update_fields=["technical_owner", "updated_at"])
    keep_use_case.technical_owner = owner
    keep_use_case.save(update_fields=["technical_owner", "updated_at"])

    with pytest.raises(ValidationError, match="kann nicht beibehalten werden"):
        resolve_technical_owner_source_change(
            package=keep_package,
            action=DeliveryRoleSourceDecision.Decision.KEEP_PACKAGE,
            rationale="Manipulierter KEEP-Versuch.",
            actor=coordinator,
        )

    adopt_use_case, adopt_package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
        title="ADOPT invalid",
    )
    adopt_use_case.technical_owner = None
    adopt_use_case.save(update_fields=["technical_owner", "updated_at"])

    with pytest.raises(ValidationError, match="kann nicht übernommen werden"):
        resolve_technical_owner_source_change(
            package=adopt_package,
            action=DeliveryRoleSourceDecision.Decision.ADOPT_SOURCE,
            rationale="Manipulierter ADOPT-Versuch.",
            actor=coordinator,
        )


@pytest.mark.django_db
def test_source_decision_keeps_legitimate_keep_and_adopt_paths(
    owner, other_owner, coordinator, business_unit
):
    keep_use_case, keep_package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
        title="KEEP valid",
    )
    keep_use_case.technical_owner = owner
    keep_use_case.save(update_fields=["technical_owner", "updated_at"])
    keep_decision = resolve_technical_owner_source_change(
        package=keep_package,
        action=DeliveryRoleSourceDecision.Decision.KEEP_PACKAGE,
        rationale="Bestehende Package-Verantwortung bleibt gültig.",
        actor=coordinator,
    )
    keep_package.refresh_from_db()
    assert keep_package.technical_owner == other_owner
    assert keep_decision.decision == DeliveryRoleSourceDecision.Decision.KEEP_PACKAGE

    adopt_use_case, adopt_package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
        title="ADOPT valid",
    )
    adopt_use_case.technical_owner = owner
    adopt_use_case.save(update_fields=["technical_owner", "updated_at"])
    adopt_decision = resolve_technical_owner_source_change(
        package=adopt_package,
        action=DeliveryRoleSourceDecision.Decision.ADOPT_SOURCE,
        rationale="Neue Use-Case-Verantwortung wird übernommen.",
        actor=coordinator,
    )
    adopt_package.refresh_from_db()
    assert adopt_package.technical_owner == owner
    assert adopt_decision.decision == DeliveryRoleSourceDecision.Decision.ADOPT_SOURCE


@pytest.mark.django_db
def test_source_decision_ui_hides_invalid_keep_and_rejects_tampered_post(
    client, owner, other_owner, coordinator, business_unit
):
    use_case, package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package.technical_owner = None
    package.save(update_fields=["technical_owner", "updated_at"])
    use_case.technical_owner = owner
    use_case.save(update_fields=["technical_owner", "updated_at"])
    client.force_login(coordinator)

    detail = client.get(package.get_absolute_url())
    body = detail.content.decode()
    assert detail.status_code == 200
    assert 'value="adopt_source"' in body
    assert 'value="keep_package"' not in body
    assert "Package-Zuordnung kann nicht beibehalten werden" in body

    response = client.post(
        reverse("delivery:package_resolve_technical_owner_source", kwargs={"pk": package.pk}),
        {
            "action": DeliveryRoleSourceDecision.Decision.KEEP_PACKAGE,
            "rationale": "Manipulierter direkter POST.",
        },
    )
    assert response.status_code == 302
    assert package.role_source_decisions.count() == 0


@pytest.mark.django_db
def test_delivery_edit_highlight_renders_current_finding_context_only(
    client, owner, other_owner, coordinator, business_unit
):
    _use_case, package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    client.force_login(coordinator)
    url = reverse("delivery:package_update", kwargs={"pk": package.pk})

    response = client.get(url, {"highlight": "out_of_scope"})
    body = response.content.decode()
    assert response.status_code == 200
    assert 'data-finding-code="OUT_OF_SCOPE_MISSING"' in body
    assert "Ursache:" in body
    assert "Readiness-Regel:" in body
    assert "Pflichtangabe muss vollständig ausgefüllt sein." in body
    assert "Zuständig:" in body
    assert "Nächster Schritt:" in body

    package.out_of_scope = "Nicht Bestandteil des MVP sind Vertragsverhandlungen."
    package.save(update_fields=["out_of_scope", "updated_at"])
    refreshed = client.get(url, {"highlight": "out_of_scope"}).content.decode()
    assert 'data-finding-code="OUT_OF_SCOPE_MISSING"' not in refreshed
    assert 'data-testid="delivery-highlight-finding"' not in refreshed


@pytest.mark.django_db
def test_use_case_owner_highlight_explains_missing_then_source_decision_state(
    client, owner, other_owner, coordinator, business_unit
):
    use_case, _package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    client.force_login(coordinator)
    url = reverse("use_cases:edit", kwargs={"pk": use_case.pk})

    use_case.technical_owner = None
    use_case.save(update_fields=["technical_owner", "updated_at"])
    missing = client.get(url, {"highlight": "technical_owner"}).content.decode()
    assert "Technical Owner im Use Case korrigieren" in missing
    assert "leer oder die zugeordnete Person ist nicht verwendbar" in missing

    owner.first_name = "Bente"
    owner.last_name = "Owner"
    owner.save(update_fields=["first_name", "last_name"])
    use_case.technical_owner = owner
    use_case.save(update_fields=["technical_owner", "updated_at"])
    active = client.get(url, {"highlight": "technical_owner"}).content.decode()
    assert "Technical Owner im Use Case ist bereits verwendbar" in active
    assert "Bente Owner" in active
    assert "wird im Delivery Package entschieden, nicht in diesem Feld" in active


@pytest.mark.django_db
def test_delivery_status_labels_and_person_display_are_unambiguous(
    client, owner, other_owner, coordinator, business_unit
):
    owner.first_name = "Bente"
    owner.last_name = "Owner"
    owner.save(update_fields=["first_name", "last_name"])
    other_owner.first_name = "Tina"
    other_owner.last_name = "Technik"
    other_owner.save(update_fields=["first_name", "last_name"])
    use_case, package = make_package(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    client.force_login(coordinator)

    detail = client.get(package.get_absolute_url()).content.decode()
    assert "Delivery Readiness: Blockiert" in detail
    assert "Fachliche Prüfung:" in detail
    assert "Technische Prüfung:" in detail
    assert "offene Readiness-Punkte.</strong> Die vollständige Liste" not in detail
    assert "Tina Technik" in detail

    edit = client.get(reverse("use_cases:edit", kwargs={"pk": use_case.pk})).content.decode()
    assert ">Tina Technik<" in edit
