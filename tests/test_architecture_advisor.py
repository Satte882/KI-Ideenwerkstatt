from __future__ import annotations

import json
from pathlib import Path

import pytest

from ki_radar.architecture.architecture_advisor import (
    MODE_ASSESSMENT_OPEN,
    MODE_BOUNDED_AGENT,
    MODE_CONTROLLED_LLM,
    MODE_LLM_WORKFLOW,
    MODE_NO_LLM_REQUIRED,
    REASON_BOUNDARY,
    REASON_CONTRADICTORY,
    REASON_INSUFFICIENT,
    REASON_SIMPLER,
    RULESET_VERSION,
    classify_architecture,
    explain_architecture,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "architecture_advisor_matrix_v1.json"


def _classify_entry(entry):
    return classify_architecture(**entry["answers"])


def test_product_classifier_matches_all_81_committed_contract_cases():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture["ruleset_version"] == RULESET_VERSION
    assert len(fixture["entries"]) == 81

    for entry in fixture["entries"]:
        result = _classify_entry(entry)
        assert result.mode == entry["mode"]
        assert result.reason_codes == tuple(entry["reason_codes"])
        assert result.ruleset_version == RULESET_VERSION


def test_canonical_mode_labels_are_stable():
    cases = (
        (("yes", "no", "no", "no"), MODE_NO_LLM_REQUIRED, "No LLM required"),
        (("no", "yes", "no", "no"), MODE_CONTROLLED_LLM, "Controlled LLM"),
        (("no", "yes", "yes", "no"), MODE_LLM_WORKFLOW, "LLM Workflow"),
        (("no", "yes", "no", "yes"), MODE_BOUNDED_AGENT, "Bounded Agent"),
    )

    for answers, expected_mode, expected_label in cases:
        result = classify_architecture(
            simpler_solution_sufficient=answers[0],
            semantic_reasoning_required=answers[1],
            multiple_known_ai_steps_required=answers[2],
            dynamic_orchestration_required=answers[3],
        )
        assert result.mode == expected_mode
        assert result.mode_label == expected_label


def test_golden_explainability_texts_for_classified_modes():
    no_llm = explain_architecture(MODE_NO_LLM_REQUIRED, (REASON_SIMPLER,))
    assert no_llm.why_pattern == (
        "Eine zuverlässige einfachere Lösung durch Prozessgestaltung, Standardsoftware oder "
        "explizite Regeln reicht aus; ein probabilistisches LLM ist dafür nicht erforderlich."
    )
    assert no_llm.why_no_agent == ""

    controlled = classify_architecture(
        simpler_solution_sufficient="no",
        semantic_reasoning_required="yes",
        multiple_known_ai_steps_required="no",
        dynamic_orchestration_required="no",
    )
    assert controlled.why_pattern == (
        "Semantische Verarbeitung ist erforderlich, ein klar begrenzter LLM-Schritt reicht "
        "jedoch aus."
    )
    assert controlled.why_no_agent == (
        "Dynamische Orchestrierung ist nicht erforderlich; ein begrenzter LLM-Schritt genügt."
    )

    workflow = classify_architecture(
        simpler_solution_sufficient="no",
        semantic_reasoning_required="yes",
        multiple_known_ai_steps_required="yes",
        dynamic_orchestration_required="no",
    )
    assert workflow.why_pattern == (
        "Mehrere getrennte KI-Schritte sind erforderlich, ihre Reihenfolge steht aber "
        "vollständig im Voraus fest."
    )
    assert workflow.why_no_agent == (
        "Die benötigten KI-Schritte und ihre Reihenfolge sind vorab bekannt; dynamische "
        "Orchestrierung ist nicht erforderlich."
    )

    agent = classify_architecture(
        simpler_solution_sufficient="no",
        semantic_reasoning_required="yes",
        multiple_known_ai_steps_required="no",
        dynamic_orchestration_required="yes",
    )
    assert agent.why_pattern == (
        "Der nächste freigegebene Schritt oder das benötigte Tool muss abhängig vom "
        "Zwischenzustand dynamisch gewählt werden."
    )
    assert agent.why_no_agent == ""


def test_golden_explainability_texts_for_open_assessment():
    explanation = explain_architecture(
        MODE_ASSESSMENT_OPEN,
        (REASON_CONTRADICTORY, REASON_INSUFFICIENT, REASON_BOUNDARY),
    )

    assert explanation.why_pattern == (
        "Die vorliegenden Antworten erlauben keine eindeutige Zuordnung zu einer minimal "
        "hinreichenden Architekturklasse."
    )
    assert explanation.why_no_agent == ""
    assert explanation.open_points == (
        "Die Antworten enthalten fachlich widersprüchliche Anforderungen und müssen geklärt "
        "werden.",
        "Mindestens eine unklare Antwort kann den Architecture Mode verändern.",
        "Die Aufgabe liegt außerhalb der V1-LLM-Taxonomie: Eine einfachere Lösung reicht "
        "nicht aus, semantisches LLM-Reasoning ist aber ebenfalls nicht erforderlich.",
    )


def test_no_llm_required_never_occurs_when_semantic_reasoning_is_yes():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    for entry in fixture["entries"]:
        if entry["answers"]["semantic_reasoning_required"] == "yes":
            assert _classify_entry(entry).mode != MODE_NO_LLM_REQUIRED


def test_invalid_answer_fails_closed():
    with pytest.raises(ValueError, match="Unsupported architecture answer"):
        classify_architecture(
            simpler_solution_sufficient="maybe",
            semantic_reasoning_required="no",
            multiple_known_ai_steps_required="no",
            dynamic_orchestration_required="no",
        )


def test_invalid_stored_explanation_contract_fails_closed():
    with pytest.raises(ValueError, match="Unsupported Architecture Mode"):
        explain_architecture("unknown", (REASON_SIMPLER,))

    with pytest.raises(ValueError, match="Unsupported architecture reason codes"):
        explain_architecture(MODE_ASSESSMENT_OPEN, ("unknown_reason",))
