from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.delivery.actions import build_actionable_findings
from ki_radar.delivery.lean_services import (
    hand_over_package as lean_hand_over_package,
)
from ki_radar.delivery.lean_services import (
    mark_package_ready as lean_mark_package_ready,
)
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.permissions import can_edit_package
from ki_radar.delivery.readiness import delivery_status_snapshot, evaluate_delivery_readiness
from ki_radar.delivery.services import (
    create_delivery_package,
    current_handed_over_package,
    hand_over_package,
    mark_package_ready,
    render_delivery_markdown,
    review_delivery_section,
)
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase
from ki_radar.use_cases.outcome_workspace import build_outcome_workspace_journey
from ki_radar.use_cases.workflow import build_use_case_journey


def make_use_case(owner, business_unit, **overrides):
    data = {
        "title": "Assistierter Angebotsvergleich",
        "summary": "Angebote strukturiert vergleichen und Rückfragen reduzieren.",
        "problem_statement": "Uneinheitliche Angebote verlängern die Lieferantenauswahl.",
        "business_unit": business_unit,
        "affected_process": "Lieferantenauswahl",
        "target_users": "Einkauf und Fachbereich",
        "submitter": owner,
        "business_owner": owner,
        "technical_owner": owner,
        "source_systems": "ERP, Shared Inbox und Dateiablage",
        "data_sources": "Angebote, Kriterienkatalog und Lieferantenstammdaten",
        "interface_description": "Dateiablage; ERP zunächst per Export",
        "intended_users": "Strategischer Einkauf",
        "intended_purpose": "Angebotsdaten extrahieren und vergleichbar darstellen.",
        "expected_benefit": "Durchlaufzeit von fünf auf drei Tage reduzieren.",
        "metric_name": "Durchlaufzeit",
        "metric_type": UseCase.MetricType.DURATION,
        "metric_direction": UseCase.MetricDirection.LOWER,
        "metric_unit": "Tage",
        "metric_baseline": Decimal("5"),
        "metric_target": Decimal("3"),
        "metric_measurement_method": "Median über zehn Beschaffungsvorgänge.",
        "metric_measurement_period": "Vier Wochen Pilotbetrieb.",
        "human_oversight": "Einkauf prüft Vergleich und trifft die Entscheidung.",
        "support_responsibility": "IT Application Management",
        "decision_status": UseCase.DecisionStatus.CLARIFICATION,
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
        rationale="Prozessmessung, Datenstichprobe und technische Vorprüfung liegen vor.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    decision = ApprovalDecision.objects.create(
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
    GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=coordinator,
        basis_version="Governance-Leitlinie 1.0",
        result=GovernanceAssessment.Result.NO_FLAGS,
        rationale="Keine vertiefte Governance-Prüfung erforderlich.",
    )
    return decision


def complete_delivery_readiness(package):
    package.out_of_scope = "Automatische Bestellung und Vertragsabschluss sind nicht enthalten."
    package.integrations = "Dateiimport aus der Ablage und lesender ERP-Export."
    package.functional_requirements = (
        "Angebote extrahieren, validieren und vergleichbar darstellen."
    )
    package.non_functional_requirements = "Antwortzeit unter 15 Sekunden; WCAG-AA-Bedienung."
    package.security_privacy_requirements = (
        "Rollenbasierter Zugriff und verschlüsselte Übertragung."
    )
    package.human_oversight = (
        "Extraktion/Klassifikation: Es wird keine numerische Confidence ausgegeben; "
        "der Einkauf validiert jedes Ergebnis fachlich."
    )
    package.logging_and_audit = (
        "Audit-/Traceability-Metadaten — Zweck: Nachvollziehbarkeit; Aufbewahrung: 24 Monate.\n"
        "Prompt-/Input-Rohinhalte — Zweck: Verarbeitung der Anfrage; nicht persistiert.\n"
        "Dokumentinhalte — Zweck: Fachliche Prüfung; Löschung nach Abschluss.\n"
        "Personenbezogene Daten — Zweck: Vorgangsbearbeitung; Löschung nach Zweckfortfall.\n"
        "Technische Logs/Betriebsdaten — Zweck: Störungsanalyse; Aufbewahrung: 30 Tage."
    )
    package.operations_and_support = "IT Application Management übernimmt Betrieb und Support."
    package.mvp_scope = "PDF- und Word-Angebote einer Warengruppe bis zur menschlichen Auswahl."
    package.acceptance_criteria = (
        "Mindestens 90 Prozent Pflichtfelder korrekt; Einkauf entscheidet final."
    )
    package.test_scenarios = (
        "Happy Path, fehlende Preise, unbekannte Einheit und manueller Eingriff."
    )
    package.measurement_plan = "Median der Durchlaufzeit über zehn Vorgänge während vier Wochen."
    package.dependencies = "Freigegebener ERP-Export und Zugriff auf die Shared Inbox."
    package.risks = "Ungewöhnliche Tabellen können eine manuelle Korrektur erfordern."
    package.assumptions = "Die Angebotsvorlagen enthalten mindestens Lieferant und Gesamtpreis."
    package.architecture_decisions = "ERP bleibt führend; keine automatische Bestellung im MVP."
    package.initial_backlog = "1. Import 2. Extraktion 3. Vergleich 4. Freigabe 5. Monitoring"
    package.external_delivery_url = "https://example.com/delivery/ki-0001"
    package.save()

    artifacts = package.architecture_artifacts
    artifacts.system_landscape = (
        "Ist: ERP, Shared Inbox, Dateiablage. Ziel: Extraktionsservice und Vergleichs-UI."
    )
    artifacts.system_responsibilities = (
        "ERP ist System of Record; IT Application Management ist Technical Owner."
    )
    artifacts.data_flows = (
        "Dateiablage → Extraktion → Validierung → Vergleichs-UI; Ergebnis lesend im ERP."
    )
    artifacts.data_quality_and_access = (
        "Einkauf hat Leserechte; Pflichtfelder werden validiert; Daten intern."
    )
    artifacts.integration_contracts = (
        "Dateiimport und versionierter ERP-CSV-Export; Einkauf liefert Daten."
    )
    artifacts.integration_operations = (
        "Täglicher Import; Fehlerqueue; ein Retry; Alarm an Application Management."
    )
    artifacts.save()

    business_actor = package.use_case.business_owner
    technical_actor = package.use_case.technical_owner
    if technical_actor is None or technical_actor.pk == business_actor.pk:
        technical_actor = package.created_by

    for review in package.section_reviews.all():
        if "business" in review.required_confirmations:
            review_delivery_section(
                package=package,
                section_key=review.section_key,
                action="confirm_business",
                actor=business_actor,
                note="Fachlicher Inhalt für Delivery geprüft.",
            )
        if "technical" in review.required_confirmations:
            review_delivery_section(
                package=package,
                section_key=review.section_key,
                action="confirm_technical",
                actor=technical_actor,
                note="Technischer Inhalt für Delivery geprüft.",
            )


@pytest.mark.django_db
def test_inactive_technical_owner_is_one_canonical_server_blocker(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)
    approve_use_case(use_case, coordinator)
    use_case.status = UseCase.Status.REVIEW
    use_case.save(update_fields=["status", "updated_at"])
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    complete_delivery_readiness(package)
    type(owner).objects.filter(pk=owner.pk).update(is_active=False)
    package.refresh_from_db()

    finding_codes = [finding.code for finding in evaluate_delivery_readiness(package)]
    action_codes = [finding.code for finding in build_actionable_findings(package, coordinator)]

    assert finding_codes.count("TECHNICAL_OWNER_INACTIVE") == 1
    assert action_codes.count("TECHNICAL_OWNER_INACTIVE") == 1
    lean_mark_package_ready(package)
    package.refresh_from_db()
    assert package.status == DeliveryPackage.Status.READY

    DeliveryPackage.objects.filter(pk=package.pk).update(status=DeliveryPackage.Status.READY)
    package.refresh_from_db()
    ready_snapshot = delivery_status_snapshot(package)
    journey = build_use_case_journey(use_case, coordinator)
    outcome = build_outcome_workspace_journey(use_case, coordinator)
    delivery_step = next(step for step in journey.steps if step.key == "delivery")
    handover_step = next(step for step in outcome.steps if step.key == "handover")
    client.force_login(coordinator)
    detail_response = client.get(reverse("delivery:package_detail", kwargs={"pk": package.pk}))
    list_response = client.get(reverse("delivery:package_list"))
    workspace_response = client.get(
        reverse("reporting:outcome_workspace"),
        {"stage": "handover", "use_case": use_case.pk},
    )

    assert ready_snapshot.code == "readiness_blocked"
    assert ready_snapshot.label == "Readiness blockiert"
    assert delivery_step.state == "blocked"
    assert delivery_step.action_method == "get"
    assert handover_step.state == "blocked"
    assert "Readiness blockiert" in detail_response.content.decode()
    assert "Readiness blockiert" in list_response.content.decode()
    assert "Status: Readiness blockiert" in render_delivery_markdown(package)
    assert "An Delivery übergeben" not in detail_response.content.decode()
    assert workspace_response.context["active_stage_action"]["action_label"] == "Readiness prüfen"
    with pytest.raises(ValidationError, match="Technical Owner"):
        lean_hand_over_package(package, coordinator)

    DeliveryPackage.objects.filter(pk=package.pk).update(
        status=DeliveryPackage.Status.HANDED_OVER,
        handed_over_at=timezone.now(),
    )
    package.refresh_from_db()

    assert delivery_status_snapshot(package).handover_complete is False
    assert current_handed_over_package(use_case) is None
    assert render_delivery_markdown(package).count("TECHNICAL_OWNER_INACTIVE") == 1


@pytest.mark.django_db
def test_delivery_package_requires_final_positive_approval(
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)

    with pytest.raises(ValidationError):
        create_delivery_package(use_case=use_case, actor=coordinator)


@pytest.mark.django_db
def test_delivery_package_is_prefilled_and_versioned(
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)
    decision = approve_use_case(use_case, coordinator)

    first = create_delivery_package(use_case=use_case, actor=coordinator)
    second = create_delivery_package(use_case=use_case, actor=coordinator)

    assert first.version == 1
    assert second.version == 2
    assert first.generated_from_decision == decision
    assert use_case.problem_statement in first.problem_context
    assert first.measurement_plan.startswith("Durchlaufzeit: Baseline 5")
    assert "Pilot und Delivery" in first.handover_notes
    assert first.section_reviews.count() == 7


@pytest.mark.django_db
def test_delivery_package_uses_optional_architecture_origin(
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)
    approve_use_case(use_case, coordinator)
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Freigegebener Bedarf",
        outcome="Bezahlte Leistung",
        scope_in="Bedarf bis Zahlung",
        constraints="ERP bleibt führendes System.",
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Lieferantenauswahl",
        description="Angebote vergleichen und Entscheidung vorbereiten.",
        actors="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        documents="Angebote und Kriterienkatalog",
        pain_points="Manuelle Übertragung",
        baseline_metrics="Fünf Tage",
    )
    process = ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        scope_start="Angebote liegen vor",
        scope_end="Lieferant ist ausgewählt",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Entscheidung",
        current_flow="Angebote öffnen, Daten übertragen und bewerten.",
        roles="Einkauf und Fachbereich",
        systems="ERP, Shared Inbox, Dateiablage",
        data_objects="Angebote und Kriterien",
        bottlenecks="Manuelle Übertragung und Rückfragen",
        baseline_metrics="Fünf Tage",
        handoffs="Einkauf übergibt Shortlist an Fachbereich.",
        exceptions="Fehlende Preise und Einheiten.",
        analyzed_by=owner,
    )
    option = SolutionOption.objects.create(
        process_analysis=process,
        name="Assistierter Vergleich",
        option_type=SolutionOption.OptionType.ASSISTANT,
        recommendation=SolutionOption.Recommendation.PREFERRED,
        description="Extraktion und Vergleich mit menschlicher Freigabe.",
        expected_value="Durchlaufzeit reduzieren",
        data_requirements="Angebote und Kriterien",
        integration_impact="Dateiablage und ERP-Export",
        risks="Ungewöhnliche Tabellen",
        architecture_fit="Passt zur bestehenden Systemlandschaft.",
        created_by=owner,
    )
    UseCaseOrigin.objects.create(
        use_case=use_case,
        stage=stage,
        process_analysis=process,
        solution_option=option,
    )

    package = create_delivery_package(use_case=use_case, actor=coordinator)

    assert package.in_scope == stream.scope_in
    assert package.solution_outline == use_case.intended_purpose
    assert package.system_context == use_case.source_systems
    assert package.integrations == use_case.interface_description
    assert package.architecture_decisions == ""
    assert process.exceptions not in package.test_scenarios
    assert process.current_flow not in package.problem_context
    source_manifest = package.section_reviews.first().source_manifest
    assert source_manifest["field_sources"]["in_scope"]["label"] == "Value Stream"
    assert source_manifest["field_sources"]["solution_outline"]["label"] == "Use Case"


@pytest.mark.django_db
def test_ready_and_handover_make_version_immutable(
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)
    approve_use_case(use_case, coordinator)
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    complete_delivery_readiness(package)

    mark_package_ready(package)
    package.refresh_from_db()
    assert package.status == DeliveryPackage.Status.READY

    hand_over_package(package, coordinator)
    package.refresh_from_db()
    assert package.status == DeliveryPackage.Status.HANDED_OVER
    assert package.handed_over_by == coordinator
    assert package.handed_over_at is not None
    assert can_edit_package(owner, package) is False

    with pytest.raises(ValidationError):
        hand_over_package(package, coordinator)


@pytest.mark.django_db
def test_missing_required_content_blocks_ready_state(
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)
    approve_use_case(use_case, coordinator)
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.mvp_scope = ""
    package.save(update_fields=["mvp_scope", "updated_at"])

    with pytest.raises(ValidationError, match="MVP-Scope"):
        mark_package_ready(package)


@pytest.mark.django_db
def test_delivery_views_require_post_for_creation_and_export_markdown(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)
    approve_use_case(use_case, coordinator)
    client.force_login(coordinator)

    create_url = reverse("delivery:package_create", kwargs={"use_case_id": use_case.pk})
    assert client.get(create_url).status_code == 405

    created = client.post(create_url)
    package = DeliveryPackage.objects.get(use_case=use_case)
    assert created.status_code == 302
    assert created.url == package.get_absolute_url()

    export = client.get(reverse("delivery:package_export_markdown", kwargs={"pk": package.pk}))
    assert export.status_code == 200
    assert export["Content-Type"].startswith("text/markdown")
    assert "# Delivery Package" in export.content.decode()
    assert "## Akzeptanzkriterien" in export.content.decode()
    assert render_delivery_markdown(package) == export.content.decode()


@pytest.mark.django_db
def test_use_case_detail_renders_delivery_package_creation_as_post_form(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)
    approve_use_case(use_case, coordinator)
    create_url = reverse("delivery:package_create", kwargs={"use_case_id": use_case.pk})
    client.force_login(coordinator)

    response = client.get(use_case.get_absolute_url())
    rendered = response.content.decode()

    assert response.status_code == 200
    assert f'<form method="post" action="{create_url}">' in rendered
    assert 'name="csrfmiddlewaretoken"' in rendered
    assert "Delivery Package erzeugen" in rendered
    assert f'href="{create_url}"' not in rendered
    assert rendered.count('data-testid="primary-next-action-control"') == 1


@pytest.mark.django_db
def test_delivery_detail_marks_ready_package_via_post(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)
    approve_use_case(use_case, coordinator)
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    complete_delivery_readiness(package)
    ready_url = reverse("delivery:package_mark_ready", kwargs={"pk": package.pk})
    client.force_login(coordinator)

    detail = client.get(package.get_absolute_url())
    rendered = detail.content.decode()

    assert detail.status_code == 200
    assert f'<form method="post" action="{ready_url}">' in rendered
    assert 'name="csrfmiddlewaretoken"' in rendered
    assert "Als bereit markieren" in rendered
    assert f'href="{ready_url}"' not in rendered

    response = client.post(ready_url)
    package.refresh_from_db()

    assert response.status_code == 302
    assert response.url == package.get_absolute_url()
    assert package.status == DeliveryPackage.Status.READY


@pytest.mark.django_db
def test_delivery_detail_hands_over_ready_package_via_post(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)
    approve_use_case(use_case, coordinator)
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    complete_delivery_readiness(package)
    mark_package_ready(package)
    handover_url = reverse("delivery:package_handover", kwargs={"pk": package.pk})
    client.force_login(coordinator)

    detail = client.get(package.get_absolute_url())
    rendered = detail.content.decode()

    assert detail.status_code == 200
    assert f'<form method="post" action="{handover_url}">' in rendered
    assert 'name="csrfmiddlewaretoken"' in rendered
    assert "An Delivery übergeben" in rendered
    assert f'href="{handover_url}"' not in rendered

    response = client.post(handover_url)
    package.refresh_from_db()

    assert response.status_code == 302
    assert response.url == package.get_absolute_url()
    assert package.status == DeliveryPackage.Status.HANDED_OVER
    assert package.handed_over_by == coordinator


@pytest.mark.django_db
def test_delivery_overview_is_visible_and_creation_is_coordinator_only(
    client,
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)
    approve_use_case(use_case, coordinator)
    client.force_login(owner)

    overview = client.get(reverse("delivery:package_list"))
    forbidden = client.post(reverse("delivery:package_create", kwargs={"use_case_id": use_case.pk}))

    assert overview.status_code == 200
    assert use_case.short_id in overview.content.decode()
    assert "Delivery Packages" in overview.content.decode()
    assert forbidden.status_code == 403
