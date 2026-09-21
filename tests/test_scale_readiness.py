from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.core.golden_path_demo import SUPPLIER_GOLDEN_PATH_USE_CASE_KEY
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.services import hand_over_package
from ki_radar.reviews.models import Review
from ki_radar.reviews.services import create_review
from ki_radar.use_cases import services as use_case_services
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.scale_readiness import evaluate_scale_readiness


@pytest.fixture
def scale_candidate(settings, db):
    settings.DEBUG = True
    call_command("seed_demo_data", demo_user_password="Issue-333-Scale-Readiness-2026!")
    coordinator = User.objects.get(username="demo_ki_koordinator")
    use_case = UseCase.objects.get(demo_key=SUPPLIER_GOLDEN_PATH_USE_CASE_KEY)
    package = use_case.delivery_packages.get(version=1)
    assert package.status == DeliveryPackage.Status.READY

    hand_over_package(package, coordinator)
    package.refresh_from_db()
    pilot_start = timezone.localdate(package.handed_over_at)
    create_review(
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
    use_case.metric_actual = Decimal("2.8")
    use_case.metric_measurement_period = "Pilot vom 01.07. bis 21.07.2026"
    use_case.metric_measured_at = timezone.localdate()
    use_case.metric_evidence_url = "https://example.com/evidence/pilot"
    use_case.planned_pilot_end = timezone.localdate()
    use_case.save(
        update_fields=[
            "metric_actual",
            "metric_measurement_period",
            "metric_measured_at",
            "metric_evidence_url",
            "planned_pilot_end",
            "updated_at",
        ]
    )
    return use_case, package, coordinator


def _scale_evidence(**overrides):
    data = {
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
    data.update(overrides)
    return data


def _go_live_data(coordinator, **scale_overrides):
    return {
        "review_date": timezone.localdate(),
        "decision": Review.Decision.GO_LIVE,
        "new_status": UseCase.Status.OPERATION,
        "rationale": "Pilotwirkung und Produktionsfähigkeit sind ausreichend belegt.",
        "go_live_exception_confirmed": False,
        "open_actions": "",
        "action_owner": None,
        "action_due_date": None,
        "next_review_date": timezone.localdate() + timezone.timedelta(days=90),
        **_scale_evidence(**scale_overrides),
    }


@pytest.mark.django_db
def test_scale_readiness_go_live_reuses_review_and_persists_snapshot(scale_candidate):
    use_case, package, coordinator = scale_candidate

    result = evaluate_scale_readiness(use_case, _scale_evidence())
    assert result.state == "ready"
    assert result.final_ml_score == Decimal("6.0")
    assert [dimension.key for dimension in result.dimensions] == [
        "pilot",
        "data",
        "quality",
        "deployment",
        "monitoring",
        "responsibility",
    ]

    review = create_review(
        use_case=use_case,
        actor=coordinator,
        data=_go_live_data(coordinator),
    )
    use_case.refresh_from_db()

    assert use_case.status == UseCase.Status.OPERATION
    assert review.decision == Review.Decision.GO_LIVE
    assert review.scale_readiness_schema_version == 1
    assert review.scale_readiness_snapshot["state"] == "ready"
    assert [item["key"] for item in review.scale_readiness_snapshot["dimensions"]] == [
        "pilot",
        "data",
        "quality",
        "deployment",
        "monitoring",
        "responsibility",
    ]
    assert review.scale_readiness_snapshot["ml_test_score"]["final"] == "6.0"
    assert review.scale_readiness_snapshot["delivery"]["package_version"] == package.version
    assert review.scale_readiness_snapshot["delivery"]["production_version"] == "release-2026.08.23"
    assert "metric_actual" not in review.scale_readiness_snapshot["pilot"]


@pytest.mark.django_db
def test_missing_rollback_is_non_overridable_scale_blocker(scale_candidate):
    use_case, _package, coordinator = scale_candidate

    with pytest.raises(ValidationError, match="Rollback"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data=_go_live_data(coordinator, scale_rollback_tested=False),
        )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.PILOT
    assert use_case.reviews.filter(decision=Review.Decision.GO_LIVE).exists() is False


@pytest.mark.django_db
def test_failed_mandatory_ml_check_blocks_even_with_high_scores(scale_candidate):
    use_case, _package, coordinator = scale_candidate

    with pytest.raises(ValidationError, match="zwingende ML-Prüfung"):
        create_review(
            use_case=use_case,
            actor=coordinator,
            data=_go_live_data(
                coordinator,
                ml_score_data=Decimal("7.0"),
                ml_score_model=Decimal("7.0"),
                ml_score_infrastructure=Decimal("7.0"),
                ml_score_monitoring=Decimal("7.0"),
                ml_score_failed_mandatory_checks="Security regression check failed",
            ),
        )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.PILOT


@pytest.mark.django_db
def test_conditional_go_action_owner_and_due_date_are_readiness(scale_candidate):
    use_case, _package, coordinator = scale_candidate
    data = _go_live_data(
        coordinator,
        ml_score_open_core_checks="Automatisierung eines nichtkritischen Monitoring-Checks offen.",
    )

    review = create_review(use_case=use_case, actor=coordinator, data=data)
    use_case.refresh_from_db()

    assert use_case.status == UseCase.Status.OPERATION
    assert review.scale_readiness_snapshot["state"] == "conditional"
    assert review.open_actions == ""
    assert review.action_owner is None
    assert review.action_due_date is None


@pytest.mark.django_db
def test_direct_operation_transition_cannot_bypass_scale_gate(scale_candidate):
    use_case, _package, coordinator = scale_candidate

    with pytest.raises(ValidationError, match=r"reviews\.services\.create_review"):
        use_case_services.apply_status_transition(
            use_case=use_case,
            target_status=UseCase.Status.OPERATION,
            actor=coordinator,
        )

    use_case.refresh_from_db()
    assert use_case.status == UseCase.Status.PILOT


@pytest.mark.django_db
def test_go_live_form_exposes_compact_scale_gate(client, scale_candidate):
    use_case, _package, coordinator = scale_candidate
    client.force_login(coordinator)

    response = client.get(
        reverse("reviews:create", kwargs={"use_case_id": use_case.pk}) + "?action=go_live"
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Scale Readiness &amp; Entscheidung" in content
    assert "Pilot-Evidenz / Wirkung" in content
    assert "Daten &amp; Wissen" in content
    assert "AI-/Systemqualität" in content
    assert "Deployment &amp; technische Robustheit" in content
    assert "Monitoring &amp; Betrieb" in content
    assert "Verantwortung, Governance &amp; Restrisiko" in content
    assert 'name="scale_tailoring_level"' in content
    assert 'name="ml_score_data"' in content
    assert 'name="scale_rollback_tested"' in content
    assert "kein zusätzlicher Gesamtscore" in content
    assert "NO-GO · Nicht bereit" in content
    assert "Pilot → Wirkung → Scale" in content
    assert "scale-readiness-preview.js" in content
    assert 'name="ending_reason"' not in content
    assert 'name="lessons_learned"' not in content


@pytest.mark.django_db
def test_scale_readiness_preview_updates_to_go_and_conditional_go(client, scale_candidate):
    use_case, _package, coordinator = scale_candidate
    client.force_login(coordinator)
    url = reverse("reviews:scale_readiness_preview", kwargs={"use_case_id": use_case.pk})

    go_response = client.post(url, _scale_evidence())
    go_content = go_response.content.decode()

    assert go_response.status_code == 200
    assert "GO · Bereit" in go_content
    assert "GO dokumentieren" in go_content
    assert "Pilot-Evidenz / Wirkung" in go_content
    assert "Verantwortung, Governance &amp; Restrisiko" in go_content

    conditional_response = client.post(
        url,
        _scale_evidence(
            ml_score_open_core_checks="Nichtkritische Monitoring-Automatisierung offen."
        ),
    )
    conditional_content = conditional_response.content.decode()

    assert conditional_response.status_code == 200
    assert "CONDITIONAL GO · Bereit mit Auflagen" in conditional_content
    assert "Maßnahme, Owner und Frist" in conditional_content


@pytest.mark.django_db
def test_saved_scale_decision_remains_visible_in_outcome_workspace(client, scale_candidate):
    use_case, _package, coordinator = scale_candidate
    client.force_login(coordinator)
    create_review(use_case=use_case, actor=coordinator, data=_go_live_data(coordinator))

    response = client.get(
        reverse("reporting:outcome_workspace"),
        {"stage": "decision", "use_case": use_case.pk},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Gespeicherte Entscheidung" in content
    assert "GO · Bereit" in content
    assert "release-2026.08.23" in content
    assert "Scale-Readiness-Snapshot" in content


@pytest.mark.django_db
def test_legacy_operation_case_without_scale_snapshot_remains_valid(settings):
    settings.DEBUG = True
    call_command("seed_demo_data", demo_user_password="Issue-333-Legacy-2026!")
    existing = UseCase.objects.get(title="[DEMO] Interner Wissensassistent")

    assert existing.status == UseCase.Status.OPERATION
    assert existing.reviews.exclude(scale_readiness_snapshot={}).exists() is False
