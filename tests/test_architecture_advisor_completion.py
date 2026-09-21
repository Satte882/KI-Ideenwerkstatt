from __future__ import annotations

import json
from pathlib import Path

from ki_radar.architecture.architecture_advisor import RULESET_VERSION as PRODUCT_RULESET_VERSION
from ki_radar.architecture.architecture_assessment import ANSWER_FIELD_NAMES
from ki_radar.architecture.architecture_assessment_models import SolutionArchitectureAssessment
from scripts.generate_architecture_advisor_matrix import (
    RULESET_VERSION as CONTRACT_RULESET_VERSION,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "architecture_advisor_matrix_v1.json"
EXPECTED_ANSWER_FIELDS = (
    "simpler_solution_sufficient",
    "semantic_reasoning_required",
    "multiple_known_ai_steps_required",
    "dynamic_orchestration_required",
)
EXPECTED_MODES = {
    "no_llm_required",
    "controlled_llm",
    "llm_workflow",
    "bounded_agent",
    "assessment_open",
}


def test_ruleset_version_is_aligned_across_contract_product_fixture_and_persistence():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    persisted_default = SolutionArchitectureAssessment._meta.get_field(
        "ruleset_version"
    ).get_default()

    assert PRODUCT_RULESET_VERSION == "architecture-advisor-v1"
    assert CONTRACT_RULESET_VERSION == PRODUCT_RULESET_VERSION
    assert fixture["ruleset_version"] == PRODUCT_RULESET_VERSION
    assert persisted_default == PRODUCT_RULESET_VERSION


def test_v1_surface_remains_exactly_four_three_state_answers_and_five_modes():
    assert ANSWER_FIELD_NAMES == EXPECTED_ANSWER_FIELDS
    assert {value for value, _label in SolutionArchitectureAssessment.Answer.choices} == {
        "yes",
        "no",
        "unclear",
    }
    assert {
        value for value, _label in SolutionArchitectureAssessment.ArchitectureMode.choices
    } == EXPECTED_MODES
