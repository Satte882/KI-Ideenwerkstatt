from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.core.golden_path_demo import SUPPLIER_GOLDEN_PATH_USE_CASE_KEY
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.services import hand_over_package
from ki_radar.reviews.models import Review
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.outcome_workspace import build_outcome_workspace_journey
from ki_radar.use_cases.services import approval_check
from ki_radar.use_cases.workflow import build_use_case_journey


@pytest.fixture
def supplier_golden_path(settings, db):
    settings.DEBUG = True
    call_command("seed_demo_data", demo_user_password="Golden-Path-Demo-2026!")
    coordinator = User.objects.get(username="demo_ki_koordinator")
    owner = User.objects.get(username="demo_business_owner")
    use_case = UseCase.objects.get(demo_key=SUPPLIER_GOLDEN_PATH_USE_CASE_KEY)
    package = use_case.delivery_packages.get(version=1)
    return use_case, package, coordinator, owner


def _start_pilot(use_case, package, coordinator):
    hand_over_package(package, coordinator)
    package.refresh_from_db()
    pilot_start = timezone.localdate(package.handed_over_at)
    review = create_review(
        use_case=use_case,
        actor=coordinator,
        data={
            "review_date": timezone.localdate(),
            "pilot_start": pilot_start,
            "decision": Review.Decision.START_PILOT,
            "new_status": UseCase.Status.PILOT,
            "rationale": "Delivery ist übergeben; der Pilot wird fachlich gestartet.",
            "go_live_exception_confirmed": False,
            "open_actions": "",
            "action_owner": None,
            "action_due_date": None,
            "next_review_date": timezone.localdate(),
        },
    )
    use_case.refresh_from_db()
    return review


def _record_measurement(use_case, *, actual=Decimal("2.8")):
    use_case.metric_actual = actual
    use_case.metric_measurement_period = "Pilot vom 01.07. bis 21.07.2026"
    use_case.metric_measured_at = timezone.localdate()
    use_case.metric_evidence_url = "https://example.invalid/evidence/supplier-pilot-result"
    use_case.save(
        update_fields=[
            "metric_actual",
            "metric_measurement_period",
            "metric_measured_at",
            "metric_evidence_url",
            "updated_at",
        ]
    )


def _complete_pilot_period(use_case):
    use_case.planned_pilot_end = timezone.localdate()
    use_case.save(update_fields=["planned_pilot_end", "updated_at"])


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


def _go_live_data(use_case, *, exception=False, rationale="Pilotziel erreicht; produktiv setzen."):
    return {
        "review_date": timezone.localdate(),
        "decision": Review.Decision.GO_LIVE,
        "new_status": UseCase.Status.OPERATION,
        "rationale": rationale,
        "go_live_exception_confirmed": exception,
        "open_actions": (
            "Pilotabweichung im Betrieb nachmessen und nach drei Monaten erneut bewerten."
            if exception
            else ""
        ),
        "action_owner": use_case.coordinator if exception else None,
        "action_due_date": (
            timezone.localdate() + timezone.timedelta(days=90) if exception else None
        ),
        "next_review_date": timezone.localdate() + timezone.timedelta(days=90),
        **_scale_evidence(),
    }


def _end_data(**overrides):
    data = {
        "review_date": timezone.localdate(),
        "decision": Review.Decision.END,
        "new_status": UseCase.Status.ENDED,
        "rationale": "Der Referenzbetrieb ist abgeschlossen.",
        "go_live_exception_confirmed": False,
        "open_actions": "",
        "action_owner": None,
        "action_due_date": None,
        "next_review_date": None,
        "ending_reason": "Der befristete Referenzbetrieb wurde planmäßig beendet.",
        "data_and_access_handling": (
            "Testangebote gelöscht, Demo-Zugänge deaktiviert und Evidenz revisionssicher archiviert."
        ),
        "replacement_solution": "Manueller Angebotsvergleich bleibt als Rückfalloption dokumentiert.",
        "final_assessment": "Ziel erreicht; Vorgehen ist für weitere Warengruppen geeignet.",
        "lessons_learned": "Frühe Datenstandardisierung reduziert Rückfragen besonders stark.",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_supplier_demo_runs_from_value_stream_to_closure(supplier_golden_path):
    use_case, package, coordinator, _owner = supplier_golden_path

    selection_journey = build_use_case_journey(use_case, coordinator)
    steps = {step.key: step for step in selection_journey.steps}
    assert package.status == DeliveryPackage.Status.READY
    assert all(
        steps[key].state == "complete"
        for key in [
            "value_stream",
            "focus",
            "process",
            "solution",
            "use_case",
            "assessment",
            "approval",
        ]
    )

    _start_pilot(use_case, package, coordinator)
    _record_measurement(use_case)
    _complete_pilot_period(use_case)
    go_live = create_review(
        use_case=use_case,
        actor=coordinator,
        data=_go_live_data(use_case),
    )
    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.OPERATION
    assert go_live.previous_status == UseCase.Status.PILOT
    assert go_live.new_status == UseCase.Status.OPERATION
    assert go_live.decision == Review.Decision.GO_LIVE

    create_review(
        use_case=use_case,
        actor=coordinator,
        data={
            "review_date": timezone.localdate(),
            "decision": Review.Decision.CONTINUE,
            "new_status": UseCase.Status.OPERATION,
            "rationale": "Betrieb stabil; Abschluss des Referenzzeitraums vorbereiten.",
            "go_live_exception_confirmed": False,
            "open_actions": "Abschlussnachweise zusammenstellen.",
            "action_owner": coordinator,
            "action_due_date": timezone.localdate(),
            "next_review_date": timezone.localdate(),
        },
    )
    closure = create_review(
        use_case=use_case,
        actor=coordinator,
        data=_end_data(),
    )
    use_case.refresh_from_db()

    assert use_case.status == UseCase.Status.ENDED
    assert use_case.actual_end_date == timezone.localdate()
    assert use_case.ending_reason
    assert use_case.data_and_access_handling
    assert closure.previous_status == UseCase.Status.OPERATION
    assert closure.new_status == UseCase.Status.ENDED
    assert closure.reviewer == coordinator
    assert closure.history.first().history_user == coordinator

    outcome = build_outcome_workspace_journey(use_case, coordinator)
    outcome_steps = {step.key: step for step in outcome.steps}
    assert outcome_steps["pilot"].state == "complete"
    assert outcome_steps["measurement"].state == "complete"
    assert outcome_steps["outcome_decision"].state == "complete"
    assert outcome_steps["operation"].state == "complete"
    assert outcome_steps["closure"].state == "complete"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field_name", "missing_value", "label"),
    [
        ("metric_actual", None, "Ist-Wert"),
        ("metric_measured_at", None, "Messdatum"),
    ],
)
def test_go_live_requires_enforcement_measurement(
    supplier_golden_path,
    field_name,
    missing_value,
    label,
):
    use_case, package, coordinator, _owner = supplier_golden_path
    _start_pilot(use_case, package, coordinator)
    _record_measurement(use_case)
    _complete_pilot_period(use_case)
    setattr(use_case, field_name, missing_value)
    use_case.save(update_fields=[field_name, "updated_at"])

    with pytest.raises(ValidationError, match=label):
        create_review(use_case=use_case, actor=coordinator, data=_go_live_data(use_case))

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.PILOT
    assert use_case.reviews.filter(decision=Review.Decision.GO_LIVE).exists() is False


@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ["metric_measurement_period", "metric_evidence_url"])
def test_go_live_measurement_documentation_is_readiness(supplier_golden_path, field_name):
    use_case, package, coordinator, _owner = supplier_golden_path
    _start_pilot(use_case, package, coordinator)
    _record_measurement(use_case)
    _complete_pilot_period(use_case)
    setattr(use_case, field_name, "")
    use_case.save(update_fields=[field_name, "updated_at"])

    review = create_review(use_case=use_case, actor=coordinator, data=_go_live_data(use_case))

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.OPERATION
    assert review.decision == Review.Decision.GO_LIVE


@pytest.mark.django_db
def test_failed_target_exception_uses_semantic_coordinator_role(
    supplier_golden_path,
    technical_admin,
):
    use_case, package, coordinator, owner = supplier_golden_path
    _start_pilot(use_case, package, coordinator)
    _record_measurement(use_case, actual=Decimal("4"))
    _complete_pilot_period(use_case)
    data = _go_live_data(
        use_case,
        exception=True,
        rationale="Trotz Abweichung ist ein begrenzter Betrieb wirtschaftlich vertretbar.",
    )

    with pytest.raises(PermissionDenied, match="Koordinator-Berechtigung"):
        create_review(use_case=use_case, actor=owner, data=data)

    review = create_review(use_case=use_case, actor=technical_admin, data=data)
    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.OPERATION
    assert review.go_live_exception_confirmed is True
    assert review.reviewer == technical_admin
    assert review.rationale


@pytest.mark.django_db
def test_failed_target_exception_requires_concrete_rationale(supplier_golden_path):
    use_case, package, coordinator, _owner = supplier_golden_path
    _start_pilot(use_case, package, coordinator)
    _record_measurement(use_case, actual=Decimal("4"))
    _complete_pilot_period(use_case)

    with pytest.raises(ValidationError, match="kurze Entscheidungsbegründung"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data=_go_live_data(use_case, exception=True, rationale="  "),
        )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.PILOT


@pytest.mark.django_db
def test_service_rejects_manipulated_go_live_status_pair(supplier_golden_path):
    use_case, package, coordinator, _owner = supplier_golden_path
    _start_pilot(use_case, package, coordinator)
    _record_measurement(use_case)
    _complete_pilot_period(use_case)
    data = _go_live_data(use_case)
    data["new_status"] = UseCase.Status.PILOT

    with pytest.raises(ValidationError, match="erfordert den Zielstatus Betrieb"):
        create_review(use_case=use_case, actor=coordinator, data=data)

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.PILOT
    assert use_case.reviews.filter(decision=Review.Decision.GO_LIVE).exists() is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name",
    [
        "ending_reason",
        "data_and_access_handling",
    ],
)
def test_closure_documentation_is_readiness(
    supplier_golden_path,
    field_name,
):
    use_case, package, coordinator, _owner = supplier_golden_path
    _start_pilot(use_case, package, coordinator)
    _record_measurement(use_case)
    _complete_pilot_period(use_case)
    create_review(use_case=use_case, actor=coordinator, data=_go_live_data(use_case))
    use_case.refresh_from_db()

    review = create_review(
        use_case=use_case,
        actor=coordinator,
        data=_end_data(**{field_name: ""}),
    )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.ENDED
    assert getattr(use_case, field_name) == ""
    assert review.decision == Review.Decision.END


@pytest.mark.django_db
def test_service_rejects_manipulated_end_status_pair(supplier_golden_path):
    use_case, package, coordinator, _owner = supplier_golden_path
    _start_pilot(use_case, package, coordinator)
    _record_measurement(use_case)
    _complete_pilot_period(use_case)
    create_review(use_case=use_case, actor=coordinator, data=_go_live_data(use_case))
    use_case.refresh_from_db()
    data = _end_data(new_status=UseCase.Status.OPERATION)

    with pytest.raises(ValidationError, match="erfordert den Zielstatus Beendet"):
        create_review(use_case=use_case, actor=coordinator, data=data)

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.OPERATION


@pytest.mark.django_db
def test_exception_post_accepts_semantic_technical_admin_coordinator(
    client,
    supplier_golden_path,
    technical_admin,
):
    use_case, package, coordinator, _owner = supplier_golden_path
    _start_pilot(use_case, package, coordinator)
    _record_measurement(use_case, actual=Decimal("4"))
    _complete_pilot_period(use_case)
    client.force_login(technical_admin)

    response = client.post(
        reverse("reviews:create", args=[use_case.pk]),
        {
            "review_date": timezone.localdate().isoformat(),
            "decision": Review.Decision.GO_LIVE,
            "new_status": UseCase.Status.OPERATION,
            "rationale": "Manipulierte Ausnahmebestätigung.",
            "go_live_exception_confirmed": "on",
            "open_actions": "",
            "action_owner": "",
            "action_due_date": "",
            "next_review_date": timezone.localdate().isoformat(),
            **_scale_evidence(),
        },
    )

    use_case.refresh_from_db()
    assert response.status_code == 302
    assert use_case.status == UseCase.Status.OPERATION


@pytest.mark.django_db
def test_existing_operation_case_is_not_retroactively_invalidated(settings):
    settings.DEBUG = True
    call_command("seed_demo_data", demo_user_password="Golden-Path-Demo-2026!")

    existing = UseCase.objects.get(title="[DEMO] Interner Wissensassistent")

    assert existing.status == UseCase.Status.OPERATION


@pytest.mark.django_db
def test_final_approval_shows_metric_definition_as_readiness(supplier_golden_path):
    use_case, _package, coordinator, _owner = supplier_golden_path
    use_case.metric_baseline = None
    use_case.save(update_fields=["metric_baseline", "updated_at"])

    check = approval_check(
        use_case=use_case,
        target_status=UseCase.DecisionStatus.APPROVED,
        actor=coordinator,
        governance_confirmed=True,
    )

    assert "Baseline-Wert" not in check.blockers
    assert "Readiness offen: Baseline-Wert" in check.warnings


@pytest.mark.django_db
def test_metric_guidance_matches_the_actual_gates(client, supplier_golden_path):
    use_case, _package, coordinator, _owner = supplier_golden_path
    client.force_login(coordinator)

    response = client.get(reverse("use_cases:edit", args=[use_case.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Voraussetzung für die finale Freigabe" in content
    assert "Ist-Wert, Messzeitraum, Messdatum und Nachweis" in content
    assert "erst für Pilotstart und Go-live verbindlich" not in content
