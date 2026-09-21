from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_architecture_advisor_matrix import (
    MODE_ASSESSMENT_OPEN,
    MODE_BOUNDED_AGENT,
    MODE_CONTROLLED_LLM,
    MODE_LLM_WORKFLOW,
    MODE_NO_LLM_REQUIRED,
    REASON_BOUNDARY,
    REASON_CONTRADICTORY,
    REASON_INSUFFICIENT,
    RULESET_VERSION,
    classify_contract_answers,
    generate_matrix,
    serialize_matrix,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "architecture_advisor_matrix_v1.json"


def test_generated_matrix_matches_committed_fixture_byte_for_byte():
    assert FIXTURE_PATH.read_text(encoding="utf-8") == serialize_matrix()


def test_matrix_contains_all_81_unique_answer_combinations():
    matrix = generate_matrix()

    assert matrix["ruleset_version"] == RULESET_VERSION
    assert len(matrix["entries"]) == 81

    combinations = {tuple(entry["answers"].values()) for entry in matrix["entries"]}
    assert len(combinations) == 81


def test_canonical_complete_modes_are_fixed():
    assert classify_contract_answers(("yes", "no", "no", "no"))[0] == MODE_NO_LLM_REQUIRED
    assert classify_contract_answers(("no", "yes", "no", "no"))[0] == MODE_CONTROLLED_LLM
    assert classify_contract_answers(("no", "yes", "yes", "no"))[0] == MODE_LLM_WORKFLOW
    assert classify_contract_answers(("no", "yes", "no", "yes"))[0] == MODE_BOUNDED_AGENT


def test_no_llm_required_is_never_emitted_when_semantic_reasoning_is_yes():
    matrix = generate_matrix()

    for entry in matrix["entries"]:
        if entry["answers"]["semantic_reasoning_required"] == "yes":
            assert entry["mode"] != MODE_NO_LLM_REQUIRED


def test_each_question_has_an_explicit_outcome_irrelevant_unclear_case():
    cases = (
        (("unclear", "no", "yes", "yes"), REASON_CONTRADICTORY),
        (("yes", "unclear", "yes", "no"), REASON_CONTRADICTORY),
        (("no", "no", "unclear", "no"), REASON_BOUNDARY),
        (("no", "no", "no", "unclear"), REASON_BOUNDARY),
    )

    for answers, expected_reason in cases:
        mode, reason_codes = classify_contract_answers(answers)
        assert mode == MODE_ASSESSMENT_OPEN
        assert reason_codes == [expected_reason]


def test_unclear_is_insufficient_when_binary_completions_change_the_outcome():
    mode, reason_codes = classify_contract_answers(("unclear", "no", "no", "no"))

    assert mode == MODE_ASSESSMENT_OPEN
    assert reason_codes == [REASON_INSUFFICIENT]


def test_reason_code_order_is_stable_for_multiple_applicable_reasons():
    mode, reason_codes = classify_contract_answers(("no", "no", "yes", "yes"))

    assert mode == MODE_ASSESSMENT_OPEN
    assert reason_codes == [REASON_CONTRADICTORY, REASON_BOUNDARY]


def test_fixture_is_valid_json_and_reviewable():
    loaded = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert loaded == generate_matrix()
