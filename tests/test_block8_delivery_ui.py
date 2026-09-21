from decimal import Decimal

from django.utils import timezone

from ki_radar.delivery.services import create_delivery_package
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase


def make_approved_use_case(owner, coordinator, business_unit):
    use_case = UseCase.objects.create(
        title="Assistierter Angebotsvergleich",
        summary="Angebote strukturiert vergleichen.",
        problem_statement="Uneinheitliche Angebote verlängern die Auswahl.",
        expected_benefit="Durchlaufzeit messbar reduzieren.",
        affected_process="Lieferantenauswahl",
        target_users="Einkauf",
        intended_users="Strategischer Einkauf",
        intended_purpose="Angebotsdaten vergleichbar darstellen.",
        source_systems="ERP und Dateiablage",
        data_sources="Angebote und Lieferantenstammdaten",
        interface_description="ERP-Export",
        human_oversight="Einkauf trifft die finale Entscheidung.",
        support_responsibility="IT Application Management",
        metric_name="Durchlaufzeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Tage",
        metric_baseline=Decimal("5"),
        metric_target=Decimal("3"),
        metric_measurement_method="Median über zehn Vorgänge",
        metric_measurement_period="Pilot",
        success_criterion="Zielwert im Pilot erreicht",
        business_unit=business_unit,
        submitter=owner,
        business_owner=owner,
        coordinator=coordinator,
        technical_owner=coordinator,
        status=UseCase.Status.REVIEW,
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
        rationale="Quellen sind geprüft.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Delivery ist freigegeben.",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    return use_case


def test_delivery_detail_shows_mapping_status_and_source_version(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(owner, coordinator, business_unit)
    package = create_delivery_package(
        use_case=use_case,
        actor=coordinator,
        use_evidence_mapper=True,
    )
    client.force_login(coordinator)

    response = client.get(package.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert 'data-testid="block8-mapping-status"' in content
    assert "Evidence-to-Delivery Mapping" in content
    assert "Gemappt" in content
    assert "Use Case" in content
    assert "problem_statement" in content
    assert "Version" in content


def test_delivery_detail_explains_mapping_conflict_without_overwrite(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(owner, coordinator, business_unit)
    package = create_delivery_package(
        use_case=use_case,
        actor=coordinator,
        use_evidence_mapper=True,
    )
    package.problem_context = "Manuell präzisierter Delivery-Kontext."
    package.save(update_fields=["problem_context", "updated_at"])
    use_case.problem_statement = "Neue bestätigte Problembeschreibung."
    use_case.save(update_fields=["problem_statement", "updated_at"])
    client.force_login(coordinator)

    response = client.get(package.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert 'data-testid="block8-mapping-conflict"' in content
    assert "Konflikt" in content
    assert "keine automatische Überschreibung." in content
    assert "Uneinheitliche Angebote verlängern die Auswahl." in content
    assert "Manuell präzisierter Delivery-Kontext." in content
    assert "Neue bestätigte Problembeschreibung." in content
    package.refresh_from_db()
    assert package.problem_context == "Manuell präzisierter Delivery-Kontext."


def test_delivery_detail_marks_legacy_package_without_silent_migration(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(owner, coordinator, business_unit)
    package = create_delivery_package(
        use_case=use_case,
        actor=coordinator,
        use_evidence_mapper=False,
    )
    client.force_login(coordinator)

    response = client.get(package.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert 'data-testid="block8-mapping-legacy"' in content
    assert "Bestands-Package ohne Block-8-Nachweis." in content
    review = package.section_reviews.get(section_key="problem_and_target")
    assert "block8_mapping" not in review.source_manifest
