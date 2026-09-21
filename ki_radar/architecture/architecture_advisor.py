from __future__ import annotations

import itertools
from dataclasses import dataclass

RULESET_VERSION = "architecture-advisor-v1"

ANSWER_YES = "yes"
ANSWER_NO = "no"
ANSWER_UNCLEAR = "unclear"
ANSWER_VALUES = (ANSWER_YES, ANSWER_NO, ANSWER_UNCLEAR)
BINARY_ANSWER_VALUES = (ANSWER_YES, ANSWER_NO)

MODE_NO_LLM_REQUIRED = "no_llm_required"
MODE_CONTROLLED_LLM = "controlled_llm"
MODE_LLM_WORKFLOW = "llm_workflow"
MODE_BOUNDED_AGENT = "bounded_agent"
MODE_ASSESSMENT_OPEN = "assessment_open"

MODE_LABELS = {
    MODE_NO_LLM_REQUIRED: "No LLM required",
    MODE_CONTROLLED_LLM: "Controlled LLM",
    MODE_LLM_WORKFLOW: "LLM Workflow",
    MODE_BOUNDED_AGENT: "Bounded Agent",
    MODE_ASSESSMENT_OPEN: "Assessment open",
}

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

WHY_PATTERN_BY_REASON = {
    REASON_SIMPLER: (
        "Eine zuverlässige einfachere Lösung durch Prozessgestaltung, Standardsoftware oder "
        "explizite Regeln reicht aus; ein probabilistisches LLM ist dafür nicht erforderlich."
    ),
    REASON_CONTROLLED: (
        "Semantische Verarbeitung ist erforderlich, ein klar begrenzter LLM-Schritt reicht "
        "jedoch aus."
    ),
    REASON_WORKFLOW: (
        "Mehrere getrennte KI-Schritte sind erforderlich, ihre Reihenfolge steht aber "
        "vollständig im Voraus fest."
    ),
    REASON_AGENT: (
        "Der nächste freigegebene Schritt oder das benötigte Tool muss abhängig vom "
        "Zwischenzustand dynamisch gewählt werden."
    ),
}

WHY_OPEN = (
    "Die vorliegenden Antworten erlauben keine eindeutige Zuordnung zu einer minimal "
    "hinreichenden Architekturklasse."
)

WHY_NO_AGENT_BY_MODE = {
    MODE_CONTROLLED_LLM: (
        "Dynamische Orchestrierung ist nicht erforderlich; ein begrenzter LLM-Schritt genügt."
    ),
    MODE_LLM_WORKFLOW: (
        "Die benötigten KI-Schritte und ihre Reihenfolge sind vorab bekannt; dynamische "
        "Orchestrierung ist nicht erforderlich."
    ),
}

OPEN_POINT_BY_REASON = {
    REASON_CONTRADICTORY: (
        "Die Antworten enthalten fachlich widersprüchliche Anforderungen und müssen geklärt werden."
    ),
    REASON_INSUFFICIENT: "Mindestens eine unklare Antwort kann den Architecture Mode verändern.",
    REASON_BOUNDARY: (
        "Die Aufgabe liegt außerhalb der V1-LLM-Taxonomie: Eine einfachere Lösung reicht "
        "nicht aus, semantisches LLM-Reasoning ist aber ebenfalls nicht erforderlich."
    ),
}


@dataclass(frozen=True, slots=True)
class ArchitectureExplanation:
    mode: str
    mode_label: str
    reason_codes: tuple[str, ...]
    why_pattern: str
    why_no_agent: str
    open_points: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArchitectureAssessmentResult:
    mode: str
    mode_label: str
    reason_codes: tuple[str, ...]
    why_pattern: str
    why_no_agent: str
    open_points: tuple[str, ...]
    ruleset_version: str = RULESET_VERSION


def _ordered_reason_codes(reason_codes: set[str]) -> tuple[str, ...]:
    return tuple(code for code in REASON_CODE_ORDER if code in reason_codes)


def _classify_complete(answers: tuple[str, str, str, str]) -> tuple[str, tuple[str, ...]]:
    simpler, semantic, multiple_steps, dynamic = answers
    if any(value not in BINARY_ANSWER_VALUES for value in answers):
        raise ValueError("Complete answers must contain only yes/no values.")

    reasons: set[str] = set()

    if simpler == ANSWER_YES and ANSWER_YES in (semantic, multiple_steps, dynamic):
        reasons.add(REASON_CONTRADICTORY)
    if multiple_steps == ANSWER_YES and dynamic == ANSWER_YES:
        reasons.add(REASON_CONTRADICTORY)
    if simpler == ANSWER_NO and semantic == ANSWER_NO:
        reasons.add(REASON_BOUNDARY)

    if reasons:
        return MODE_ASSESSMENT_OPEN, _ordered_reason_codes(reasons)
    if simpler == ANSWER_YES:
        return MODE_NO_LLM_REQUIRED, (REASON_SIMPLER,)
    if multiple_steps == ANSWER_NO and dynamic == ANSWER_NO:
        return MODE_CONTROLLED_LLM, (REASON_CONTROLLED,)
    if multiple_steps == ANSWER_YES and dynamic == ANSWER_NO:
        return MODE_LLM_WORKFLOW, (REASON_WORKFLOW,)
    if multiple_steps == ANSWER_NO and dynamic == ANSWER_YES:
        return MODE_BOUNDED_AGENT, (REASON_AGENT,)

    raise AssertionError(f"Uncovered complete answer combination: {answers!r}")


def _binary_completions(answers: tuple[str, str, str, str]) -> list[tuple[str, str, str, str]]:
    unknown_indexes = [index for index, value in enumerate(answers) if value == ANSWER_UNCLEAR]
    completions: list[tuple[str, str, str, str]] = []

    for replacements in itertools.product(BINARY_ANSWER_VALUES, repeat=len(unknown_indexes)):
        completed = list(answers)
        for index, replacement in zip(unknown_indexes, replacements, strict=True):
            completed[index] = replacement
        completions.append(tuple(completed))

    return completions


def _classify_answers(answers: tuple[str, str, str, str]) -> tuple[str, tuple[str, ...]]:
    if any(value not in ANSWER_VALUES for value in answers):
        raise ValueError(f"Unsupported architecture answer in {answers!r}.")

    if ANSWER_UNCLEAR not in answers:
        return _classify_complete(answers)

    outcomes = [_classify_complete(completion) for completion in _binary_completions(answers)]
    modes = {mode for mode, _ in outcomes}

    if len(modes) != 1:
        return MODE_ASSESSMENT_OPEN, (REASON_INSUFFICIENT,)

    mode = next(iter(modes))
    if mode != MODE_ASSESSMENT_OPEN:
        reason_sets = {reason_codes for _, reason_codes in outcomes}
        if len(reason_sets) == 1:
            return outcomes[0]
        return MODE_ASSESSMENT_OPEN, (REASON_INSUFFICIENT,)

    common_reasons = set(outcomes[0][1])
    for _, reason_codes in outcomes[1:]:
        common_reasons.intersection_update(reason_codes)

    invariant_open_reasons = common_reasons.intersection({REASON_CONTRADICTORY, REASON_BOUNDARY})
    if invariant_open_reasons:
        return MODE_ASSESSMENT_OPEN, _ordered_reason_codes(invariant_open_reasons)

    return MODE_ASSESSMENT_OPEN, (REASON_INSUFFICIENT,)


def explain_architecture(
    mode: str,
    reason_codes: tuple[str, ...] | list[str],
) -> ArchitectureExplanation:
    if mode not in MODE_LABELS:
        raise ValueError(f"Unsupported Architecture Mode: {mode!r}.")

    normalized_reasons = tuple(reason_codes)
    unknown_reasons = set(normalized_reasons).difference(REASON_CODE_ORDER)
    if unknown_reasons:
        raise ValueError(f"Unsupported architecture reason codes: {sorted(unknown_reasons)!r}.")

    if mode == MODE_ASSESSMENT_OPEN:
        why_pattern = WHY_OPEN
        open_points = tuple(
            OPEN_POINT_BY_REASON[reason]
            for reason in normalized_reasons
            if reason in OPEN_POINT_BY_REASON
        )
    else:
        if len(normalized_reasons) != 1 or normalized_reasons[0] not in WHY_PATTERN_BY_REASON:
            raise ValueError(
                "A classified Architecture Mode requires exactly one positive reason code."
            )
        why_pattern = WHY_PATTERN_BY_REASON[normalized_reasons[0]]
        open_points = ()

    return ArchitectureExplanation(
        mode=mode,
        mode_label=MODE_LABELS[mode],
        reason_codes=normalized_reasons,
        why_pattern=why_pattern,
        why_no_agent=WHY_NO_AGENT_BY_MODE.get(mode, ""),
        open_points=open_points,
    )


def classify_architecture(
    *,
    simpler_solution_sufficient: str,
    semantic_reasoning_required: str,
    multiple_known_ai_steps_required: str,
    dynamic_orchestration_required: str,
) -> ArchitectureAssessmentResult:
    answers = (
        simpler_solution_sufficient,
        semantic_reasoning_required,
        multiple_known_ai_steps_required,
        dynamic_orchestration_required,
    )
    mode, reason_codes = _classify_answers(answers)
    explanation = explain_architecture(mode, reason_codes)

    return ArchitectureAssessmentResult(
        mode=explanation.mode,
        mode_label=explanation.mode_label,
        reason_codes=explanation.reason_codes,
        why_pattern=explanation.why_pattern,
        why_no_agent=explanation.why_no_agent,
        open_points=explanation.open_points,
    )
