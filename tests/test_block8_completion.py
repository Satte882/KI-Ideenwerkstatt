import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    SolutionSelectionDecision,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.solution_selection import build_comparison_snapshot
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable
from ki_radar.delivery.mapping_integration import (
    block8_mapping_source_differences,
    build_existing_package_refresh_plan,
    delivery_mapping_is_legacy,
)
from ki_radar.delivery.mapping_refresh import MappingStatus
from ki_radar.delivery.models import DeliveryPackage, DeliverySectionReview
from ki_radar.delivery.residual_text import ResidualTextError, refine_delivery_residual_text
from ki_radar.delivery.services import create_delivery_package, refresh_delivery_package_mapping
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase

REFERENCE_PATH = Path(__file__).parent / "fixtures" / "accelerator" / "block8_real_demo.v1.json"
HASH_PATH = Path(__file__).parent / "fixtures" / "accelerator" / "block8_real_demo.v1.sha256"


def make_real_demo(owner, coordinator, business_unit):
    value_stream = ValueStream.objects.create(
        name="Beschaffungsbedarf bis Bestellung",
        business_unit=business_unit,
        owner=owner,
        trigger="Beschaffungsbedarf liegt vor",
        outcome="Bestellung ist ausgelöst",
        scope_in="Bedarf bis Bestellung",
        scope_out="Rechnung und Zahlung",
        status=ValueStream.Status.ACTIVE,
        created_by=owner,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Angebote vergleichen",
        description="Angebote werden fachlich verglichen.",
    )
    process = ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        status=ProcessAnalysis.Status.VALIDATED,
        scope_start="Angebote liegen vor",
        scope_end="Lieferant ausgewählt",
        trigger="Angebote vollständig",
        outcome="Vergleich dokumentiert",
        current_flow="Angebote werden manuell nebeneinander geprüft.",
        roles="Strategischer Einkauf",
        systems="ERP und Dateiablage",
        data_objects="Angebote und Lieferantenstammdaten",
        bottlenecks="Uneinheitliche Angebotsstrukturen",
        baseline_metrics="Bearbeitungszeit 5 Tage",
        analyzed_by=coordinator,
    )
    option = SolutionOption.objects.create(
        process_analysis=process,
        name="KI-Assistenz Angebotsvergleich",
        option_type=SolutionOption.OptionType.ASSISTANT,
        evaluation_status=SolutionOption.EvaluationStatus.ASSESSED,
        description="KI unterstützt den strukturierten Angebotsvergleich.",
        expected_value="Vergleichsaufwand sinkt bei nachvollziehbarer Fachentscheidung.",
        bottleneck_coverage="Uneinheitliche Angebotsstrukturen werden normalisiert.",
        feasibility=SolutionOption.Effort.MEDIUM,
        data_requirements="Angebote und Lieferantenstammdaten",
        application_impact="Bestehende Einkaufsoberfläche um Assistenzansicht ergänzen.",
        integration_impact="ERP-Export wird eingelesen.",
        integration_effort=SolutionOption.Effort.MEDIUM,
        technology_constraints="Keine autonome Lieferantenauswahl.",
        risks="Fehlerhafte Extraktion muss fachlich überprüft werden.",
        architecture_fit="Assistenz bleibt im bestehenden Einkaufsprozess.",
        created_by=coordinator,
    )
    SolutionSelectionDecision.objects.create(
        process_analysis=process,
        selected_option=option,
        rationale="Beste Kombination aus Nutzen, Machbarkeit und kontrollierter Assistenz.",
        comparison_snapshot=build_comparison_snapshot([option]),
        decided_by=coordinator,
    )
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
        support_responsibility="",
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
    UseCaseOrigin.objects.create(
        use_case=use_case,
        stage=stage,
        process_analysis=process,
        solution_option=option,
        source_snapshot={},
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
    approval = ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Delivery ist freigegeben.",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    return use_case, approval


def provider_result():
    content = "Erfolg im Pilot: Durchlaufzeit von 5 auf 3 Tage reduzieren."
    return OpenRouterResult(
        content=content,
        model="test/model",
        usage={"prompt_tokens": 100, "completion_tokens": 18, "total_tokens": 118},
        output_chars=len(content),
        finish_reason="stop",
    )


def canonical_hash(payload):
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_real_demo_semantic_reference_drift_and_gate_invariance(
    owner,
    coordinator,
    business_unit,
):
    use_case, approval = make_real_demo(owner, coordinator, business_unit)
    package = create_delivery_package(
        use_case=use_case,
        actor=coordinator,
        use_evidence_mapper=True,
    )

    assert delivery_mapping_is_legacy(package) is False
    assert package.generated_from_decision == approval
    assert package.problem_context == "Uneinheitliche Angebote verlängern die Auswahl."
    assert package.target_outcome == "Durchlaufzeit messbar reduzieren."
    assert "Baseline: 5" in package.measurement_plan
    assert "Ziel: 3" in package.measurement_plan
    assert "Erfolgskriterium: Zielwert im Pilot erreicht" in package.acceptance_criteria
    assert "Bestehende Einkaufsoberfläche" in package.architecture_artifacts.system_landscape

    initial_plan = build_existing_package_refresh_plan(package)
    support = next(
        item for item in initial_plan.decisions if item.target_field == "operations_and_support"
    )
    assert support.status is MappingStatus.GAP

    use_case.support_responsibility = "IT Application Management"
    use_case.save(update_fields=["support_responsibility", "updated_at"])
    support_refresh = refresh_delivery_package_mapping(package)
    package.refresh_from_db()
    support = next(
        item for item in support_refresh.decisions if item.target_field == "operations_and_support"
    )
    assert support.status is MappingStatus.MAPPED
    assert package.operations_and_support == "IT Application Management"

    package.problem_context = "Manuell präzisierter Delivery-Kontext."
    package.save(update_fields=["problem_context", "updated_at"])
    use_case.problem_statement = "Neue bestätigte Problembeschreibung."
    use_case.save(update_fields=["problem_statement", "updated_at"])
    differences = block8_mapping_source_differences(package)
    problem_stale = next(item for item in differences if item["package_field"] == "problem_context")
    target_stale = next(item for item in differences if item["package_field"] == "target_outcome")
    conflict_plan = refresh_delivery_package_mapping(package)
    package.refresh_from_db()
    conflict = next(
        item for item in conflict_plan.decisions if item.target_field == "problem_context"
    )
    assert conflict.status is MappingStatus.CONFLICT
    assert package.problem_context == "Manuell präzisierter Delivery-Kontext."

    before_provider_failure = package.acceptance_criteria
    with (
        patch(
            "ki_radar.delivery.residual_text.request_openrouter",
            side_effect=OpenRouterUnavailable("Provider nicht verfügbar", code="timeout"),
        ),
        pytest.raises(ResidualTextError),
    ):
        refine_delivery_residual_text(
            package=package,
            target_field="acceptance_criteria",
            actor=coordinator,
        )
    package.refresh_from_db()
    provider_failure_preserves = package.acceptance_criteria == before_provider_failure

    with patch(
        "ki_radar.delivery.residual_text.request_openrouter",
        return_value=provider_result(),
    ) as provider:
        first = refine_delivery_residual_text(
            package=package,
            target_field="acceptance_criteria",
            actor=coordinator,
        )
        package.refresh_from_db()
        second = refine_delivery_residual_text(
            package=package,
            target_field="acceptance_criteria",
            actor=coordinator,
        )
    cache_reuses = not first.cached and second.cached and provider.call_count == 1

    package.refresh_from_db()
    reviews = list(package.section_reviews.all())
    gate_state = {
        "initial_status": DeliveryPackage.Status.DRAFT,
        "auto_ready": package.status == DeliveryPackage.Status.READY,
        "auto_confirmed": any(
            review.review_status == DeliverySectionReview.ReviewStatus.CONFIRMED
            for review in reviews
        ),
        "auto_handover": package.handed_over_at is not None,
    }

    before_handover_value = package.problem_context
    before_handover_manifest = deepcopy(
        package.section_reviews.get(section_key="problem_and_target").source_manifest
    )
    DeliveryPackage.objects.filter(pk=package.pk).update(
        status=DeliveryPackage.Status.HANDED_OVER,
        handed_over_at=timezone.now(),
    )
    package.refresh_from_db()
    with pytest.raises(ValidationError, match="unveränderlich"):
        refresh_delivery_package_mapping(package)
    package.refresh_from_db()
    tracking_review = package.section_reviews.get(section_key="problem_and_target")
    handover_blocked = (
        package.problem_context == before_handover_value
        and tracking_review.source_manifest == before_handover_manifest
    )

    actual = {
        "schema": "block8-real-demo-v1",
        "direct_mapping": {
            "problem_context": "Uneinheitliche Angebote verlängern die Auswahl.",
            "target_outcome": "Durchlaufzeit messbar reduzieren.",
        },
        "composition": {
            "measurement_plan_has_baseline_target": True,
            "acceptance_criteria_has_success_criterion": True,
            "system_landscape_has_selected_solution": True,
        },
        "gap": {"operations_and_support": "gap"},
        "first_evidence": {
            "operations_and_support": support.status.value,
            "value": package.operations_and_support,
        },
        "staleness": {
            "problem_context": problem_stale["changed"],
            "target_outcome": target_stale["changed"],
        },
        "conflict": {
            "field": conflict.target_field,
            "status": conflict.status.value,
            "overwrite": package.problem_context != "Manuell präzisierter Delivery-Kontext.",
        },
        "gates": gate_state,
        "llm": {
            "provider_failure_preserves_deterministic": provider_failure_preserves,
            "cache_reuses_result": cache_reuses,
        },
        "handover": {"refresh_blocked": handover_blocked},
    }
    expected = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    expected_hash = HASH_PATH.read_text(encoding="utf-8").strip()

    assert actual == expected
    assert canonical_hash(expected) == expected_hash
    assert canonical_hash(actual) == expected_hash
