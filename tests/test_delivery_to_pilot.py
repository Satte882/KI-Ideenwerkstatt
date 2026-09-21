from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.core.demo_architecture_data import INVOICE_USE_CASE_KEY
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.services import (
    create_delivery_package,
    hand_over_package,
    mark_package_ready,
    review_delivery_section,
)
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.reviews.models import Review
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase
from ki_radar.use_cases.outcome_workspace import build_outcome_workspace_journey
from ki_radar.use_cases.permissions import can_start_pilot
from ki_radar.use_cases.workflow import build_use_case_journey


def _complete_delivery_readiness(package):
    use_case = package.use_case
    if use_case.technical_owner_id is None:
        use_case.technical_owner = package.created_by
        use_case.save(update_fields=["technical_owner", "updated_at"])

    package.out_of_scope = "Automatische Bestellung und Vertragsabschluss sind nicht enthalten."
    package.integrations = "Dateiimport aus der Ablage und lesender ERP-Export."
    package.functional_requirements = (
        "Angebote extrahieren, validieren und vergleichbar darstellen."
    )
    package.non_functional_requirements = "Antwortzeit unter 15 Sekunden; barrierearme Bedienung."
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
    package.mvp_scope = "Angebote einer Warengruppe bis zur menschlichen Auswahl vergleichen."
    package.acceptance_criteria = (
        "Mindestens 90 Prozent Pflichtfelder korrekt; Einkauf entscheidet final."
    )
    package.test_scenarios = (
        "Happy Path, fehlende Preise, unbekannte Einheit und manueller Eingriff."
    )
    package.measurement_plan = "Median der Durchlaufzeit über zehn Vorgänge während vier Wochen."
    package.dependencies = "Freigegebener ERP-Export und Zugriff auf die Shared Inbox."
    package.risks = "Ungewöhnliche Tabellen können eine manuelle Korrektur erfordern."
    package.assumptions = "Angebote enthalten mindestens Lieferant und Gesamtpreis."
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
    artifacts.data_flows = "Dateiablage zu Extraktion zu Validierung zu Vergleichs-UI."
    artifacts.data_quality_and_access = (
        "Einkauf hat Leserechte; Pflichtfelder werden validiert; Daten intern."
    )
    artifacts.integration_contracts = "Dateiimport und versionierter ERP-CSV-Export."
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


def _make_pilot_candidate(owner, coordinator, business_unit, *, technical_owner=None):
    use_case = UseCase.objects.create(
        title="Assistierter Angebotsvergleich",
        summary="Angebote strukturiert vergleichen und Rückfragen reduzieren.",
        problem_statement="Uneinheitliche Angebote verlängern die Lieferantenauswahl.",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        target_users="Einkauf und Fachbereich",
        submitter=owner,
        business_owner=owner,
        coordinator=coordinator,
        technical_owner=technical_owner,
        status=UseCase.Status.REVIEW,
        source_systems="ERP, Shared Inbox und Dateiablage",
        data_sources="Angebote, Kriterienkatalog und Lieferantenstammdaten",
        interface_description="Dateiablage; ERP zunächst per Export",
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
        next_review_date=timezone.localdate() + timedelta(days=14),
        planned_pilot_end=timezone.localdate() + timedelta(days=30),
        human_oversight="Einkauf prüft Vergleich und trifft die Entscheidung.",
        support_responsibility="IT Application Management",
        decision_status=UseCase.DecisionStatus.APPROVED,
    )
    GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=coordinator,
        basis_version="2026-01",
        result=GovernanceAssessment.Result.NO_FLAGS,
        rationale="Keine Hinweise",
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
    return use_case


def _create_package(use_case, coordinator, *, handover=False):
    if use_case.technical_owner_id is None:
        use_case.technical_owner = coordinator
        use_case.save(update_fields=["technical_owner", "updated_at"])
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    _complete_delivery_readiness(package)
    mark_package_ready(package)
    if handover:
        hand_over_package(package, coordinator)
        package.refresh_from_db()
    return package


def _review_data(use_case, pilot_start):
    return {
        "review_date": timezone.localdate(),
        "pilot_start": pilot_start,
        "decision": Review.Decision.START_PILOT,
        "new_status": UseCase.Status.PILOT,
        "rationale": "Delivery ist übergeben; der Pilot wird fachlich gestartet.",
        "go_live_exception_confirmed": False,
        "open_actions": "",
        "action_owner": None,
        "action_due_date": None,
        "next_review_date": use_case.next_review_date,
    }


def _pilot_start_url(use_case):
    return reverse("reviews:create", kwargs={"use_case_id": use_case.pk}) + "?action=pilot_start"


def _pilot_start_payload(use_case, package, *, rationale):
    return {
        "review_date": timezone.localdate().isoformat(),
        "pilot_start": timezone.localdate(package.handed_over_at).isoformat(),
        "rationale": rationale,
        "open_actions": "",
        "action_owner": "",
        "action_due_date": "",
        "next_review_date": use_case.next_review_date.isoformat(),
    }


@pytest.fixture
def handed_over_candidate(owner, coordinator, business_unit):
    use_case = _make_pilot_candidate(owner, coordinator, business_unit)
    package = _create_package(use_case, coordinator, handover=True)
    return use_case, package


@pytest.mark.django_db
def test_golden_path_uses_one_use_case_from_value_stream_to_pilot(settings):
    settings.DEBUG = True
    call_command("seed_demo_data", demo_user_password="Delivery-Pilot-Demo-2026!")
    coordinator = User.objects.get(username="demo_ki_koordinator")
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    package = use_case.delivery_packages.get(version=1)

    before = build_use_case_journey(use_case, coordinator)
    steps = {step.key: step for step in before.steps}
    assert [step.key for step in before.steps[:9]] == [
        "value_stream",
        "focus",
        "process",
        "solution",
        "use_case",
        "assessment",
        "governance",
        "approval",
        "delivery",
    ]
    assert all(
        steps[key].state == "complete"
        for key in [
            "value_stream",
            "focus",
            "process",
            "solution",
            "use_case",
            "assessment",
            "governance",
            "approval",
        ]
    )
    assert package.status == DeliveryPackage.Status.READY

    hand_over_package(package, coordinator)
    package.refresh_from_db()
    after_handover = build_use_case_journey(use_case, coordinator)
    assert after_handover.next_action is not None
    assert after_handover.next_action.key == "pilot_start"
    assert after_handover.next_action.action_label == "Pilot starten"

    pilot_start = timezone.localdate(package.handed_over_at)
    review = create_review(
        use_case=use_case,
        actor=coordinator,
        data=_review_data(use_case, pilot_start),
    )
    use_case.refresh_from_db()

    assert use_case.status == UseCase.Status.PILOT
    assert use_case.pilot_start == pilot_start
    assert review.decision == Review.Decision.START_PILOT
    assert review.previous_status == UseCase.Status.REVIEW
    assert review.new_status == UseCase.Status.PILOT
    assert package.status == DeliveryPackage.Status.HANDED_OVER
    outcome = build_outcome_workspace_journey(use_case, coordinator)
    outcome_steps = {step.key: step for step in outcome.steps}
    assert outcome_steps["pilot"].state == "current"
    assert outcome_steps["measurement"].state == "upcoming"
    assert outcome_steps["outcome_decision"].state == "upcoming"
    assert sum(step.state == "current" for step in outcome_steps.values()) == 1


@pytest.mark.django_db
def test_pilot_start_requires_a_delivery_package(owner, coordinator, business_unit):
    use_case = _make_pilot_candidate(owner, coordinator, business_unit)

    with pytest.raises(ValidationError, match="verbindliche Übergabe"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data=_review_data(use_case, timezone.localdate()),
        )


@pytest.mark.django_db
def test_pilot_start_requires_handed_over_package(owner, coordinator, business_unit):
    use_case = _make_pilot_candidate(owner, coordinator, business_unit)
    _create_package(use_case, coordinator, handover=False)

    with pytest.raises(ValidationError, match="verbindliche Übergabe"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data=_review_data(use_case, timezone.localdate()),
        )


@pytest.mark.django_db
def test_current_package_must_be_handed_over(owner, coordinator, business_unit):
    use_case = _make_pilot_candidate(owner, coordinator, business_unit)
    first = _create_package(use_case, coordinator, handover=True)
    second = create_delivery_package(use_case=use_case, actor=coordinator)

    assert first.status == DeliveryPackage.Status.HANDED_OVER
    assert second.version == 2
    with pytest.raises(ValidationError, match="verbindliche Übergabe"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data=_review_data(use_case, timezone.localdate()),
        )


@pytest.mark.django_db
def test_pilot_start_requires_review_status(handed_over_candidate, coordinator):
    use_case, _package = handed_over_candidate
    use_case.status = UseCase.Status.IDEA
    use_case.save(update_fields=["status", "updated_at"])

    with pytest.raises(ValidationError, match="ist aus dem Status Idee nicht zulässig"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data=_review_data(use_case, timezone.localdate()),
        )


@pytest.mark.django_db
def test_pilot_start_date_is_required_and_failure_is_atomic(
    handed_over_candidate,
    coordinator,
):
    use_case, _package = handed_over_candidate
    original_review_date = use_case.next_review_date

    with pytest.raises(ValidationError, match="Pilotbeginn ist erforderlich"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data={**_review_data(use_case, None), "next_review_date": timezone.localdate()},
        )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.REVIEW
    assert use_case.pilot_start is None
    assert use_case.next_review_date == original_review_date
    assert use_case.reviews.count() == 0


@pytest.mark.django_db
def test_pilot_start_date_cannot_be_in_future(handed_over_candidate, coordinator):
    use_case, _package = handed_over_candidate

    with pytest.raises(ValidationError, match="nicht in der Zukunft"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data=_review_data(use_case, timezone.localdate() + timedelta(days=1)),
        )


@pytest.mark.django_db
def test_pilot_start_date_cannot_precede_handover(handed_over_candidate, coordinator):
    use_case, package = handed_over_candidate
    handover_date = timezone.localdate(package.handed_over_at)

    with pytest.raises(ValidationError, match="nicht vor der verbindlichen Übergabe"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data=_review_data(use_case, handover_date - timedelta(days=1)),
        )


@pytest.mark.django_db
def test_planned_pilot_end_is_readiness_for_actual_start(handed_over_candidate, coordinator):
    use_case, package = handed_over_candidate
    pilot_start = timezone.localdate(package.handed_over_at)
    use_case.planned_pilot_end = pilot_start - timedelta(days=1)
    use_case.save(update_fields=["planned_pilot_end", "updated_at"])

    review = create_review(
        use_case=use_case,
        actor=coordinator,
        data=_review_data(use_case, pilot_start),
    )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.PILOT
    assert review.decision == Review.Decision.START_PILOT


@pytest.mark.django_db
def test_only_coordinator_or_assigned_business_owner_can_start(
    handed_over_candidate,
    owner,
    other_owner,
    coordinator,
    technical_admin,
    reader,
):
    use_case, _package = handed_over_candidate
    use_case.technical_owner = reader
    use_case.save(update_fields=["technical_owner", "updated_at"])
    assert can_start_pilot(coordinator, use_case) is True
    assert can_start_pilot(owner, use_case) is True
    assert can_start_pilot(other_owner, use_case) is False
    assert can_start_pilot(reader, use_case) is False
    assert can_start_pilot(technical_admin, use_case) is True

    for actor in [other_owner, reader]:
        assert can_start_pilot(actor, use_case) is False


@pytest.mark.django_db
def test_manipulated_owner_post_is_forced_to_pilot_start(
    client,
    handed_over_candidate,
    owner,
):
    use_case, package = handed_over_candidate
    client.force_login(owner)
    response = client.post(
        _pilot_start_url(use_case),
        {
            "review_date": timezone.localdate().isoformat(),
            "pilot_start": timezone.localdate(package.handed_over_at).isoformat(),
            "decision": Review.Decision.GO_LIVE,
            "new_status": UseCase.Status.OPERATION,
            "rationale": "Manipulierter POST darf den festen Pilotübergang nicht verändern.",
            "open_actions": "",
            "action_owner": "",
            "action_due_date": "",
            "next_review_date": use_case.next_review_date.isoformat(),
        },
    )

    use_case.refresh_from_db()
    review = use_case.reviews.get()
    assert response.status_code == 302
    assert use_case.status == UseCase.Status.PILOT
    assert review.decision == Review.Decision.START_PILOT
    assert review.new_status == UseCase.Status.PILOT


@pytest.mark.django_db
def test_assigned_business_owner_can_open_and_submit_pilot_start(
    client,
    handed_over_candidate,
    owner,
):
    use_case, package = handed_over_candidate
    pilot_start = timezone.localdate(package.handed_over_at)
    rationale = "Delivery ist übergeben; der Business Owner startet den Pilot."
    url = _pilot_start_url(use_case)
    client.force_login(owner)

    assert client.get(url).status_code == 200
    response = client.post(
        url,
        _pilot_start_payload(use_case, package, rationale=rationale),
    )

    use_case.refresh_from_db()
    review = use_case.reviews.get()
    assert response.status_code == 302
    assert use_case.status == UseCase.Status.PILOT
    assert use_case.pilot_start == pilot_start
    assert review.reviewer == owner
    assert review.previous_status == UseCase.Status.REVIEW
    assert review.new_status == UseCase.Status.PILOT
    assert review.decision == Review.Decision.START_PILOT
    assert review.rationale == rationale


@pytest.mark.django_db
def test_coordinator_can_open_and_submit_pilot_start(
    client,
    handed_over_candidate,
    coordinator,
):
    use_case, package = handed_over_candidate
    url = _pilot_start_url(use_case)
    client.force_login(coordinator)

    assert client.get(url).status_code == 200
    response = client.post(
        url,
        _pilot_start_payload(
            use_case,
            package,
            rationale="Der KI-Koordinator startet den vorbereiteten Pilot.",
        ),
    )

    use_case.refresh_from_db()
    assert response.status_code == 302
    assert use_case.status == UseCase.Status.PILOT
    assert use_case.reviews.get().reviewer == coordinator


@pytest.mark.django_db
def test_unassigned_business_owner_cannot_open_or_submit_pilot_start(
    client,
    handed_over_candidate,
    other_owner,
):
    use_case, package = handed_over_candidate
    url = _pilot_start_url(use_case)
    client.force_login(other_owner)

    assert client.get(url).status_code == 403
    assert (
        client.post(
            url,
            _pilot_start_payload(use_case, package, rationale="Nicht zugeordnet."),
        ).status_code
        == 403
    )
    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.REVIEW
    assert use_case.reviews.count() == 0


@pytest.mark.django_db
def test_assigned_user_without_business_owner_group_cannot_open_or_submit_pilot_start(
    client,
    handed_over_candidate,
    reader,
):
    use_case, package = handed_over_candidate
    use_case.business_owner = reader
    use_case.save(update_fields=["business_owner", "updated_at"])
    url = _pilot_start_url(use_case)
    client.force_login(reader)

    assert client.get(url).status_code == 403
    assert (
        client.post(
            url,
            _pilot_start_payload(use_case, package, rationale="Gruppe fehlt."),
        ).status_code
        == 403
    )
    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.REVIEW
    assert use_case.reviews.count() == 0


@pytest.mark.django_db
def test_business_owner_cannot_open_general_lifecycle_review(
    client,
    handed_over_candidate,
    owner,
):
    use_case, _package = handed_over_candidate
    client.force_login(owner)

    response = client.get(reverse("reviews:create", kwargs={"use_case_id": use_case.pk}))

    assert response.status_code == 403


@pytest.mark.django_db
def test_pilot_start_post_rejects_unauthorized_roles(
    client,
    handed_over_candidate,
    other_owner,
    technical_admin,
):
    use_case, package = handed_over_candidate
    url = _pilot_start_url(use_case)
    payload = {
        "review_date": timezone.localdate().isoformat(),
        "pilot_start": timezone.localdate(package.handed_over_at).isoformat(),
        "rationale": "Nicht berechtigt.",
        "next_review_date": use_case.next_review_date.isoformat(),
    }

    client.force_login(other_owner)
    assert client.post(url, payload).status_code == 403

    client.force_login(technical_admin)
    assert client.post(url, payload).status_code == 302


@pytest.mark.django_db
def test_pilot_start_form_defaults_to_today_and_limits_future_dates(
    client,
    handed_over_candidate,
    owner,
):
    use_case, _package = handed_over_candidate
    client.force_login(owner)
    url = _pilot_start_url(use_case)

    response = client.get(url)

    assert response.status_code == 200
    form = response.context["form"]
    assert form.fields["pilot_start"].initial == timezone.localdate()
    assert form.fields["pilot_start"].required is True
    assert form.fields["pilot_start"].widget.attrs["max"] == timezone.localdate().isoformat()
    assert response.context["pilot_start_only"] is True
    assert "Pilot starten" in response.content.decode()
