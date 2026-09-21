from __future__ import annotations

import pytest
from django.urls import reverse

from ki_radar.architecture.architecture_assessment import (
    save_solution_architecture_assessment,
)
from ki_radar.architecture.architecture_assessment_models import (
    SolutionArchitectureAssessment,
)
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
    TimeToValue,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.solution_selection import comparison_blockers
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.governance.models import GovernanceAssessment, GovernanceReview
from ki_radar.reviews.models import Review
from ki_radar.use_cases.models import UseCase


@pytest.fixture
def comparison_setup(db, business_unit, owner):
    value_stream = ValueStream.objects.create(
        name="Advisor Vergleich",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf entsteht",
        outcome="Bedarf ist bearbeitet",
        scope_in="Testumfang",
        created_by=owner,
    )
    ValueStreamFocus.objects.create(
        value_stream=value_stream,
        business_domain=BusinessDomain.OTHER,
        capability="Dokumentenprüfung",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.MEDIUM,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Für den Advisor-Vergleich ausgewählt.",
        updated_by=owner,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Testphase",
    )
    process = ProcessAnalysis.objects.create(
        stage=stage,
        name="Vergleichsprozess",
        scope_start="Start",
        scope_end="Ende",
        trigger="Bedarf",
        outcome="Ergebnis",
        current_flow="Aktueller Ablauf",
        roles="Fachrolle",
        systems="Quellsystem",
        data_objects="Dokumente",
        bottlenecks="Manuelle Prüfung",
        baseline_metrics="10 Minuten",
        analyzed_by=owner,
    )

    def create_option(name, option_type):
        return SolutionOption.objects.create(
            process_analysis=process,
            name=name,
            option_type=option_type,
            evaluation_status=SolutionOption.EvaluationStatus.ASSESSED,
            description=f"Beschreibung {name}",
            expected_value=f"Nutzen {name}",
            bottleneck_coverage="Deckt den manuellen Engpass ab.",
            feasibility=SolutionOption.Effort.LOW,
            data_requirements="Dokumente",
            application_impact="Keine neue Kernanwendung",
            integration_effort=SolutionOption.Effort.LOW,
            integration_impact="Bestehende Schnittstelle",
            technology_constraints="Bestehender Stack",
            risks="Begrenztes Betriebsrisiko",
            architecture_fit="Passt in das Zielbild",
            time_to_value=TimeToValue.UNKNOWN,
            created_by=owner,
        )

    primary = create_option("Semantische Assistenz", SolutionOption.OptionType.GENERATIVE_AI)
    secondary = create_option("Regelautomatisierung", SolutionOption.OptionType.RULE_AUTOMATION)
    return process, primary, secondary


def _controlled_llm_answers():
    return {
        "simpler_solution_sufficient": "no",
        "semantic_reasoning_required": "yes",
        "multiple_known_ai_steps_required": "no",
        "dynamic_orchestration_required": "no",
    }


def _option_snapshot(option):
    return {
        "evaluation_status": option.evaluation_status,
        "description": option.description,
        "expected_value": option.expected_value,
        "bottleneck_coverage": option.bottleneck_coverage,
        "feasibility": option.feasibility,
        "data_requirements": option.data_requirements,
        "application_impact": option.application_impact,
        "integration_effort": option.integration_effort,
        "integration_impact": option.integration_impact,
        "technology_constraints": option.technology_constraints,
        "risks": option.risks,
        "architecture_fit": option.architecture_fit,
        "recommendation": option.recommendation,
        "comparison_complete": option.comparison_complete,
    }


def _side_effect_counts():
    return {
        "selection_decisions": SolutionSelectionDecision.objects.count(),
        "process_validations": ProcessValidation.objects.count(),
        "use_cases": UseCase.objects.count(),
        "use_case_origins": UseCaseOrigin.objects.count(),
        "governance_assessments": GovernanceAssessment.objects.count(),
        "governance_reviews": GovernanceReview.objects.count(),
        "delivery_packages": DeliveryPackage.objects.count(),
        "lifecycle_reviews": Review.objects.count(),
    }


@pytest.mark.django_db
def test_comparison_shows_compact_architecture_mode_without_replacing_existing_rows(
    client,
    owner,
    comparison_setup,
):
    process, primary, _secondary = comparison_setup
    save_solution_architecture_assessment(
        solution_option=primary,
        answers=_controlled_llm_answers(),
        actor=owner,
    )
    client.force_login(owner)

    response = client.get(
        reverse("architecture:solution_option_compare", kwargs={"pk": process.pk})
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert content.count("Architecture Mode") == 1
    assert "Controlled LLM" in content
    assert "Nicht eingeschätzt" in content
    assert "Machbarkeit" in content
    assert "Integrationsaufwand" in content
    assert "Passung zu Zielbild und Leitplanken" in content
    assert "Entscheidungsstatus" in content
    assert "Bevorzugte Option auswählen" in content


@pytest.mark.django_db
def test_saving_advisor_has_no_selection_gate_or_downstream_side_effects(
    owner,
    comparison_setup,
):
    process, primary, secondary = comparison_setup
    option_before = _option_snapshot(primary)
    process_before = (process.status, process.version)
    side_effects_before = _side_effect_counts()
    blockers_before = comparison_blockers([primary, secondary])

    assessment = save_solution_architecture_assessment(
        solution_option=primary,
        answers=_controlled_llm_answers(),
        actor=owner,
    )

    primary.refresh_from_db()
    process.refresh_from_db()
    assert (
        assessment.architecture_mode
        == SolutionArchitectureAssessment.ArchitectureMode.CONTROLLED_LLM
    )
    assert _option_snapshot(primary) == option_before
    assert (process.status, process.version) == process_before
    assert comparison_blockers([primary, secondary]) == blockers_before == []
    assert _side_effect_counts() == side_effects_before
