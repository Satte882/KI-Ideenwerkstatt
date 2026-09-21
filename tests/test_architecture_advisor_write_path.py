from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from ki_radar.architecture.architecture_advisor import (
    MODE_BOUNDED_AGENT,
    MODE_CONTROLLED_LLM,
    RULESET_VERSION,
)
from ki_radar.architecture.architecture_assessment import (
    ANSWER_FIELD_NAMES,
    save_solution_architecture_assessment,
)
from ki_radar.architecture.architecture_assessment_forms import (
    SolutionArchitectureAssessmentForm,
)
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
        name="Advisor Write Path",
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
        architecture_fit="Bestehender Architecture-Fit-Text",
        created_by=owner,
    )


def _controlled_answers():
    return {
        "simpler_solution_sufficient": "no",
        "semantic_reasoning_required": "yes",
        "multiple_known_ai_steps_required": "no",
        "dynamic_orchestration_required": "no",
    }


def test_form_exposes_exactly_the_four_human_answers():
    form = SolutionArchitectureAssessmentForm()

    assert tuple(form.fields) == ANSWER_FIELD_NAMES
    assert "architecture_mode" not in form.fields
    assert "reason_codes" not in form.fields
    assert "ruleset_version" not in form.fields
    assert "version" not in form.fields
    assert "assessed_by" not in form.fields


@pytest.mark.django_db
def test_owner_can_create_assessment_and_server_derives_output(solution_option, owner):
    assessment = save_solution_architecture_assessment(
        solution_option=solution_option,
        answers={
            **_controlled_answers(),
            "architecture_mode": MODE_BOUNDED_AGENT,
            "reason_codes": ["tampered"],
        },
        actor=owner,
    )

    assert assessment.architecture_mode == MODE_CONTROLLED_LLM
    assert assessment.reason_codes == ["controlled_llm_sufficient"]
    assert assessment.ruleset_version == RULESET_VERSION
    assert assessment.version == 1
    assert assessment.assessed_by == owner


@pytest.mark.django_db
def test_coordinator_reuses_existing_value_stream_permission(solution_option, coordinator):
    assessment = save_solution_architecture_assessment(
        solution_option=solution_option,
        answers=_controlled_answers(),
        actor=coordinator,
    )

    assert assessment.assessed_by == coordinator


@pytest.mark.django_db
@pytest.mark.parametrize("actor_fixture", ["reader", "other_owner"])
def test_unauthorized_users_cannot_write_assessment(
    solution_option,
    actor_fixture,
    request,
):
    actor = request.getfixturevalue(actor_fixture)

    with pytest.raises(ValidationError, match="Berechtigung"):
        save_solution_architecture_assessment(
            solution_option=solution_option,
            answers=_controlled_answers(),
            actor=actor,
        )

    assert not SolutionArchitectureAssessment.objects.filter(
        solution_option=solution_option
    ).exists()


@pytest.mark.django_db
def test_explicit_update_reclassifies_with_current_ruleset_and_increments_version(
    solution_option,
    owner,
):
    assessment = SolutionArchitectureAssessment.objects.create(
        solution_option=solution_option,
        **_controlled_answers(),
        architecture_mode=SolutionArchitectureAssessment.ArchitectureMode.NO_LLM_REQUIRED,
        reason_codes=["legacy_reason"],
        ruleset_version="architecture-advisor-legacy-v0",
        version=7,
        assessed_by=owner,
    )

    assert assessment.architecture_mode == "no_llm_required"
    assert assessment.ruleset_version == "architecture-advisor-legacy-v0"

    updated = save_solution_architecture_assessment(
        solution_option=solution_option,
        answers={
            "simpler_solution_sufficient": "no",
            "semantic_reasoning_required": "yes",
            "multiple_known_ai_steps_required": "no",
            "dynamic_orchestration_required": "yes",
        },
        actor=owner,
    )

    assert updated.pk == assessment.pk
    assert updated.architecture_mode == MODE_BOUNDED_AGENT
    assert updated.reason_codes == ["dynamic_orchestration_required"]
    assert updated.ruleset_version == RULESET_VERSION
    assert updated.version == 8


@pytest.mark.django_db
def test_write_path_does_not_change_solution_option_evaluation_or_selection_fields(
    solution_option,
    owner,
):
    before = {
        "feasibility": solution_option.feasibility,
        "integration_effort": solution_option.integration_effort,
        "evaluation_status": solution_option.evaluation_status,
        "recommendation": solution_option.recommendation,
        "architecture_fit": solution_option.architecture_fit,
        "comparison_complete": solution_option.comparison_complete,
    }

    save_solution_architecture_assessment(
        solution_option=solution_option,
        answers=_controlled_answers(),
        actor=owner,
    )
    solution_option.refresh_from_db()

    after = {
        "feasibility": solution_option.feasibility,
        "integration_effort": solution_option.integration_effort,
        "evaluation_status": solution_option.evaluation_status,
        "recommendation": solution_option.recommendation,
        "architecture_fit": solution_option.architecture_fit,
        "comparison_complete": solution_option.comparison_complete,
    }
    assert after == before
