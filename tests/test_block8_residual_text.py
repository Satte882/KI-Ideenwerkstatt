from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from ki_radar.accelerator.models import AcceleratorLLMQuota
from ki_radar.architecture.models import (
    ProcessAnalysis,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable
from ki_radar.delivery.mapping_refresh import BLOCK8_MAPPING_MANIFEST_KEY
from ki_radar.delivery.residual_text import ResidualTextError, refine_delivery_residual_text
from ki_radar.delivery.services import create_delivery_package
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase


def make_mapped_package(owner, coordinator, business_unit):
    value_stream = ValueStream.objects.create(
        name="Beschaffungsbedarf bis Bestellung",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf erkannt",
        outcome="Bestellung ausgelöst",
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
    UseCaseOrigin.objects.create(
        use_case=use_case,
        stage=stage,
        process_analysis=process,
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
    ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Delivery ist freigegeben.",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    package = create_delivery_package(
        use_case=use_case,
        actor=coordinator,
        use_evidence_mapper=True,
    )
    return package, process


def provider_result(content="Zielwert im Pilot erreicht; Durchlaufzeit 5 auf 3 Tage."):
    return OpenRouterResult(
        content=content,
        model="test/model",
        usage={
            "prompt_tokens": 120,
            "completion_tokens": 20,
            "total_tokens": 140,
            "cost": 0.0012,
        },
        output_chars=len(content),
        finish_reason="stop",
    )


def test_residual_text_reuses_cache_without_second_provider_or_quota(
    owner,
    coordinator,
    business_unit,
):
    package, process = make_mapped_package(owner, coordinator, business_unit)

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

    assert first.cached is False
    assert second.cached is True
    assert provider.call_count == 1
    package.refresh_from_db()
    assert package.acceptance_criteria == first.value
    review = package.section_reviews.get(section_key="problem_and_target")
    residual = review.source_manifest[BLOCK8_MAPPING_MANIFEST_KEY]["residual_texts"]
    cache = residual["acceptance_criteria"]
    assert cache["model"] == "test/model"
    assert cache["usage"] == {
        "prompt_tokens": 120,
        "completion_tokens": 20,
        "total_tokens": 140,
        "cost": 0.0012,
    }
    quotas = AcceleratorLLMQuota.objects.filter(quota_date=timezone.localdate())
    assert quotas.count() == 3
    assert set(quotas.values_list("calls", flat=True)) == {1}
    assert quotas.get(scope=AcceleratorLLMQuota.Scope.CONTEXT).process_analysis == process


@pytest.mark.parametrize(
    "error_code",
    ["rate_limit", "timeout", "not_configured", "invalid_response"],
)
def test_provider_failure_preserves_deterministic_delivery(
    error_code,
    owner,
    coordinator,
    business_unit,
):
    package, _process = make_mapped_package(owner, coordinator, business_unit)
    before_value = package.acceptance_criteria
    review = package.section_reviews.get(section_key="problem_and_target")
    before_manifest = deepcopy(review.source_manifest)

    with (
        patch(
            "ki_radar.delivery.residual_text.request_openrouter",
            side_effect=OpenRouterUnavailable("Providerfehler", code=error_code),
        ),
        pytest.raises(ResidualTextError) as exc_info,
    ):
        refine_delivery_residual_text(
            package=package,
            target_field="acceptance_criteria",
            actor=coordinator,
        )

    assert exc_info.value.code == error_code
    package.refresh_from_db()
    review.refresh_from_db()
    assert package.acceptance_criteria == before_value
    assert review.source_manifest == before_manifest


def test_unsupported_field_never_calls_provider(owner, coordinator, business_unit):
    package, _process = make_mapped_package(owner, coordinator, business_unit)

    with (
        patch("ki_radar.delivery.residual_text.request_openrouter") as provider,
        pytest.raises(ResidualTextError) as exc_info,
    ):
        refine_delivery_residual_text(
            package=package,
            target_field="problem_context",
            actor=coordinator,
        )

    assert exc_info.value.code == "unsupported_field"
    provider.assert_not_called()
    assert AcceleratorLLMQuota.objects.count() == 0


def test_manual_divergence_is_not_sent_to_provider(owner, coordinator, business_unit):
    package, _process = make_mapped_package(owner, coordinator, business_unit)
    package.acceptance_criteria = "Manuell geändertes Akzeptanzkriterium."
    package.save(update_fields=["acceptance_criteria", "updated_at"])

    with (
        patch("ki_radar.delivery.residual_text.request_openrouter") as provider,
        pytest.raises(ResidualTextError) as exc_info,
    ):
        refine_delivery_residual_text(
            package=package,
            target_field="acceptance_criteria",
            actor=coordinator,
        )

    assert exc_info.value.code == "manual_divergence"
    provider.assert_not_called()


def test_residual_action_is_explicit_post_and_not_general_generation(
    client,
    owner,
    coordinator,
    business_unit,
):
    package, _process = make_mapped_package(owner, coordinator, business_unit)
    client.force_login(coordinator)

    response = client.get(package.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert 'data-testid="block8-residual-action"' in content
    assert "Sprachlich verdichten" in content
    assert f"/delivery/{package.pk}/mapping/acceptance_criteria/refine/" in content
