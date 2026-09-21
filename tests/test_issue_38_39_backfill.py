from decimal import Decimal
from importlib import import_module

import pytest
from django.apps import apps as django_apps
from django.utils import timezone

from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.delivery.services import create_delivery_package
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase


def _approved_use_case(*, owner, technical_owner, coordinator, business_unit):
    use_case = UseCase.objects.create(
        title="Backfill-Test",
        problem_statement="Uneindeutige Quellenbasis",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        business_owner=owner,
        technical_owner=technical_owner,
        coordinator=coordinator,
        expected_benefit="Nachvollziehbarkeit",
        metric_name="Durchlaufzeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Minuten",
        metric_baseline=Decimal("11"),
        metric_target=Decimal("8.25"),
        metric_measurement_method="Median",
        human_oversight="Fachliche Prüfung",
        support_responsibility="IT",
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
        rationale="Geprüft",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Freigegeben",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.save(update_fields=["decision_status", "updated_at"])
    return use_case


@pytest.mark.django_db
def test_source_snapshot_backfill_covers_existing_process_and_use_case_origin(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    stream = ValueStream.objects.create(
        name="Lieferantenauswahl",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf liegt vor",
        outcome="Lieferant ausgewählt",
        scope_in="Angebotsvergleich",
        created_by=coordinator,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Angebote vergleichen",
        description="Angebote werden fachlich verglichen",
        actors="Einkauf",
        systems="ERP",
        documents="Angebote",
        pain_points="Hoher manueller Aufwand",
        baseline_metrics="11 Minuten",
    )
    process = ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        source_snapshot={},
        scope_start="Angebote liegen vor",
        scope_end="Entscheidung dokumentiert",
        trigger="Bedarf liegt vor",
        outcome="Vergleich abgeschlossen",
        current_flow="Manueller Vergleich",
        roles="Einkauf",
        systems="ERP",
        data_objects="Angebote",
        bottlenecks="Uneinheitliche Formate",
        baseline_metrics="11 Minuten",
        analyzed_by=coordinator,
    )
    option = SolutionOption.objects.create(
        process_analysis=process,
        name="Regelbasierter Vergleich",
        option_type=SolutionOption.OptionType.RULE_AUTOMATION,
        description="Regeln strukturieren den Vergleich.",
        expected_value="Weniger manueller Aufwand",
        data_requirements="Angebotsdaten",
        created_by=coordinator,
    )
    use_case = _approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    origin = UseCaseOrigin.objects.create(
        use_case=use_case,
        stage=stage,
        process_analysis=process,
        solution_option=option,
        source_snapshot={},
    )

    migration = import_module("ki_radar.architecture.migrations.0009_backfill_source_provenance")
    migration.backfill_source_snapshots(django_apps, None)

    process.refresh_from_db()
    origin.refresh_from_db()
    assert process.source_snapshot["name"]["value"] == stage.name
    assert process.source_snapshot["name"]["captured_via"] == "migration_backfill"
    assert origin.source_snapshot["title"]["value"] == option.name
    assert origin.source_snapshot["data_sources"]["value"] == option.data_requirements


@pytest.mark.django_db
def test_historical_package_owner_backfill_uses_owner_at_package_creation(
    owner,
    other_owner,
    coordinator,
    business_unit,
    django_user_model,
):
    replacement = django_user_model.objects.create_user(username="later-tech", password="x")
    use_case = _approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    use_case.technical_owner = replacement
    use_case.save(update_fields=["technical_owner", "updated_at"])

    migration = import_module("ki_radar.delivery.migrations.0006_harden_role_source_audit")
    migration.reconstruct_package_owners(django_apps, None)

    package.refresh_from_db()
    review = package.section_reviews.get(section_key="architecture_and_data")
    source = review.source_manifest["role_sources"]["technical_owner"]
    assert package.technical_owner == other_owner
    assert source["id"] == str(other_owner.pk)
    assert source["adoption"] == "historical_backfill"
