from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from ki_radar.architecture.architecture_advisor import RULESET_VERSION
from ki_radar.architecture.architecture_assessment_models import (
    SolutionArchitectureAssessment,
)
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
)


@pytest.fixture
def solution_option(db, business_unit, owner):
    value_stream = ValueStream.objects.create(
        name="Architecture Advisor Test",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf entsteht",
        outcome="Bedarf ist bearbeitet",
        scope_in="Testumfang",
        created_by=owner,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Testphase",
    )
    process = ProcessAnalysis.objects.create(
        stage=stage,
        name="Testprozess",
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
    return SolutionOption.objects.create(
        process_analysis=process,
        name="Semantische Assistenz",
        option_type=SolutionOption.OptionType.GENERATIVE_AI,
        description="Unterstützt die semantische Prüfung.",
        expected_value="Reduziert manuellen Aufwand.",
        created_by=owner,
    )


def _create_assessment(solution_option, owner, **overrides):
    values = {
        "solution_option": solution_option,
        "simpler_solution_sufficient": SolutionArchitectureAssessment.Answer.NO,
        "semantic_reasoning_required": SolutionArchitectureAssessment.Answer.YES,
        "multiple_known_ai_steps_required": SolutionArchitectureAssessment.Answer.NO,
        "dynamic_orchestration_required": SolutionArchitectureAssessment.Answer.NO,
        "architecture_mode": SolutionArchitectureAssessment.ArchitectureMode.CONTROLLED_LLM,
        "reason_codes": ["controlled_llm_sufficient"],
        "assessed_by": owner,
    }
    values.update(overrides)
    return SolutionArchitectureAssessment.objects.create(**values)


@pytest.mark.django_db
def test_assessment_is_one_to_one_with_solution_option(solution_option, owner):
    assessment = _create_assessment(solution_option, owner)

    assert solution_option.architecture_assessment == assessment
    assert assessment.ruleset_version == RULESET_VERSION
    assert assessment.version == 1

    with pytest.raises(IntegrityError), transaction.atomic():
        _create_assessment(solution_option, owner)


@pytest.mark.django_db
def test_stored_ruleset_and_mode_are_not_automatically_reclassified(solution_option, owner):
    assessment = _create_assessment(
        solution_option,
        owner,
        simpler_solution_sufficient=SolutionArchitectureAssessment.Answer.YES,
        semantic_reasoning_required=SolutionArchitectureAssessment.Answer.YES,
        architecture_mode=SolutionArchitectureAssessment.ArchitectureMode.NO_LLM_REQUIRED,
        reason_codes=["legacy_reason"],
        ruleset_version="architecture-advisor-legacy-v0",
    )

    assessment.version = 2
    assessment.save(update_fields=["version", "updated_at"])
    assessment.refresh_from_db()

    assert (
        assessment.architecture_mode
        == SolutionArchitectureAssessment.ArchitectureMode.NO_LLM_REQUIRED
    )
    assert assessment.reason_codes == ["legacy_reason"]
    assert assessment.ruleset_version == "architecture-advisor-legacy-v0"
    assert assessment.version == 2


@pytest.mark.django_db
def test_derived_fields_and_version_are_not_form_editable(solution_option, owner):
    assessment = _create_assessment(solution_option, owner)

    assert assessment._meta.get_field("architecture_mode").editable is False
    assert assessment._meta.get_field("reason_codes").editable is False
    assert assessment._meta.get_field("ruleset_version").editable is False
    assert assessment._meta.get_field("version").editable is False
