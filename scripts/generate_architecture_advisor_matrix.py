from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

RULESET_VERSION = "architecture-advisor-v1"

ANSWER_VALUES = ("yes", "no", "unclear")
BINARY_ANSWER_VALUES = ("yes", "no")

MODE_NO_LLM_REQUIRED = "no_llm_required"
MODE_CONTROLLED_LLM = "controlled_llm"
MODE_LLM_WORKFLOW = "llm_workflow"
MODE_BOUNDED_AGENT = "bounded_agent"
MODE_ASSESSMENT_OPEN = "assessment_open"

REASON_CONTRADICTORY = "contradictory_answers"
REASON_INSUFFICIENT = "insufficient_information"
REASON_BOUNDARY = "architecture_boundary_unclear"
REASON_SIMPLER = "simpler_solution_sufficient"
REASON_CONTROLLED = "controlled_llm_sufficient"
REASON_WORKFLOW = "fixed_llm_workflow_sufficient"
REASON_AGENT = "dynamic_orchestration_required"

REASON_CODE_ORDER = (
    REASON_CONTRADICTORY,
    REASON_INSUFFICIENT,
    REASON_BOUNDARY,
    REASON_SIMPLER,
    REASON_CONTROLLED,
    REASON_WORKFLOW,
    REASON_AGENT,
)

QUESTION_KEYS = (
    "simpler_solution_sufficient",
    "semantic_reasoning_required",
    "multiple_known_ai_steps_required",
    "dynamic_orchestration_required",
)


def _ordered_reason_codes(reason_codes: set[str]) -> list[str]:
    return [code for code in REASON_CODE_ORDER if code in reason_codes]


def classify_complete_answers(answers: tuple[str, str, str, str]) -> tuple[str, list[str]]:
    """Classify one fully known yes/no combination for the V1 contract."""

    simpler, semantic, multiple_steps, dynamic = answers
    if any(value not in BINARY_ANSWER_VALUES for value in answers):
        raise ValueError("Complete answers must contain only yes/no values.")

    reasons: set[str] = set()

    if simpler == "yes" and "yes" in (semantic, multiple_steps, dynamic):
        reasons.add(REASON_CONTRADICTORY)

    if multiple_steps == "yes" and dynamic == "yes":
        reasons.add(REASON_CONTRADICTORY)

    if simpler == "no" and semantic == "no":
        reasons.add(REASON_BOUNDARY)

    if reasons:
        return MODE_ASSESSMENT_OPEN, _ordered_reason_codes(reasons)

    if simpler == "yes":
        return MODE_NO_LLM_REQUIRED, [REASON_SIMPLER]

    if multiple_steps == "no" and dynamic == "no":
        return MODE_CONTROLLED_LLM, [REASON_CONTROLLED]

    if multiple_steps == "yes" and dynamic == "no":
        return MODE_LLM_WORKFLOW, [REASON_WORKFLOW]

    if multiple_steps == "no" and dynamic == "yes":
        return MODE_BOUNDED_AGENT, [REASON_AGENT]

    raise AssertionError(f"Uncovered complete answer combination: {answers!r}")


def _binary_completions(answers: tuple[str, str, str, str]) -> list[tuple[str, str, str, str]]:
    unknown_indexes = [index for index, value in enumerate(answers) if value == "unclear"]
    completions: list[tuple[str, str, str, str]] = []

    for replacements in itertools.product(BINARY_ANSWER_VALUES, repeat=len(unknown_indexes)):
        completed = list(answers)
        for index, replacement in zip(unknown_indexes, replacements, strict=True):
            completed[index] = replacement
        completions.append(tuple(completed))

    return completions


def classify_contract_answers(answers: tuple[str, str, str, str]) -> tuple[str, list[str]]:
    """Apply symmetric unknown handling for the reviewable V1 contract.

    An unclear answer is mode-irrelevant only when every binary completion yields
    the same Architecture Mode. For an invariant open mode, only reason codes
    shared by every completion are retained. If the diagnostic reason itself
    depends on the unknown answer, insufficient_information is returned.
    """

    if any(value not in ANSWER_VALUES for value in answers):
        raise ValueError(f"Unsupported answer value in {answers!r}.")

    if "unclear" not in answers:
        return classify_complete_answers(answers)

    outcomes = [
        classify_complete_answers(completion) for completion in _binary_completions(answers)
    ]
    modes = {mode for mode, _ in outcomes}

    if len(modes) != 1:
        return MODE_ASSESSMENT_OPEN, [REASON_INSUFFICIENT]

    mode = next(iter(modes))
    if mode != MODE_ASSESSMENT_OPEN:
        reason_sets = {tuple(reason_codes) for _, reason_codes in outcomes}
        if len(reason_sets) == 1:
            return outcomes[0]
        return MODE_ASSESSMENT_OPEN, [REASON_INSUFFICIENT]

    common_reasons = set(outcomes[0][1])
    for _, reason_codes in outcomes[1:]:
        common_reasons.intersection_update(reason_codes)

    invariant_open_reasons = common_reasons.intersection({REASON_CONTRADICTORY, REASON_BOUNDARY})
    if invariant_open_reasons:
        return MODE_ASSESSMENT_OPEN, _ordered_reason_codes(invariant_open_reasons)

    return MODE_ASSESSMENT_OPEN, [REASON_INSUFFICIENT]


def generate_matrix() -> dict:
    entries = []

    for answers in itertools.product(ANSWER_VALUES, repeat=4):
        mode, reason_codes = classify_contract_answers(answers)
        entries.append(
            {
                "answers": dict(zip(QUESTION_KEYS, answers, strict=True)),
                "mode": mode,
                "reason_codes": reason_codes,
            }
        )

    return {
        "ruleset_version": RULESET_VERSION,
        "answer_values": list(ANSWER_VALUES),
        "reason_code_order": list(REASON_CODE_ORDER),
        "entries": entries,
    }


def serialize_matrix() -> str:
    return json.dumps(generate_matrix(), ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the Architecture Advisor V1 decision-matrix fixture."
    )
    parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout.")
    args = parser.parse_args()
    rendered = serialize_matrix()

    if args.output is None:
        print(rendered, end="")
        return

    args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
