from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from ki_radar.architecture.architecture_advisor import (
    MODE_ASSESSMENT_OPEN,
    MODE_BOUNDED_AGENT,
    MODE_LABELS,
    MODE_LLM_WORKFLOW,
    REASON_CODE_ORDER,
    RULESET_VERSION,
    classify_architecture,
)

ROOT = Path(__file__).parents[1]
FIXTURE_PATH = ROOT / "tests/fixtures/architecture_real_demo_v1.json"
REPORT_PATH = ROOT / "docs/accelerator/ARCHITECTURE_REAL_DEMO_ASSESSMENT_OPEN_REPORT.md"


def _load_advisor_cases() -> list[dict[str, object]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return payload["advisor_cases"]


ADVISOR_CASES = _load_advisor_cases()


def _classify_case(case: dict[str, object]):
    answers = case["answers"]
    return classify_architecture(
        simpler_solution_sufficient=answers["simpler_solution_sufficient"],
        semantic_reasoning_required=answers["semantic_reasoning_required"],
        multiple_known_ai_steps_required=answers["multiple_known_ai_steps_required"],
        dynamic_orchestration_required=answers["dynamic_orchestration_required"],
    )


def _build_assessment_report(cases: list[dict[str, object]]) -> str:
    evaluated = [(case, _classify_case(case)) for case in cases]
    open_results = [item for item in evaluated if item[1].mode == MODE_ASSESSMENT_OPEN]
    classified_count = len(evaluated) - len(open_results)
    mode_counts = Counter(result.mode for _, result in evaluated)
    reason_counts = Counter(code for _, result in open_results for code in result.reason_codes)

    lines = [
        "# Architecture Real-DEMO - Assessment-open-Bericht",
        "",
        "Issue: #213  ",
        "Fixture: `tests/fixtures/architecture_real_demo_v1.json`  ",
        f"Ruleset: `{RULESET_VERSION}`",
        "",
        "## Ergebnis des fixierten Referenzsets",
        "",
        f"- Getestete Advisor-Fälle: **{len(evaluated)}**",
        f"- Klassifizierte Fälle: **{classified_count}**",
        f"- `Assessment open`: **{len(open_results)}**",
        "",
        "### Mode-Verteilung",
        "",
    ]
    for mode, label in MODE_LABELS.items():
        lines.append(f"- `{mode}` ({label}): **{mode_counts[mode]}**")

    lines.extend(["", "### Reason Codes der offenen Fälle", ""])
    for reason_code in REASON_CODE_ORDER:
        if reason_counts[reason_code]:
            lines.append(f"- `{reason_code}`: **{reason_counts[reason_code]}**")

    lines.extend(["", "### Offene Fälle", ""])
    for case, result in open_results:
        reason_text = ", ".join(f"`{code}`" for code in result.reason_codes)
        lines.append(f"- `{case['case_id']}` - {case['name']}: {reason_text}")

    case_by_id = {case["case_id"]: (case, result) for case, result in evaluated}
    complex_case, complex_result = case_by_id["advisor_adversarial_high_complexity_fixed_workflow"]
    dynamic_case, dynamic_result = case_by_id["advisor_adversarial_dynamic_countercontrol"]

    lines.extend(
        [
            "",
            "## Kontrollnachweise",
            "",
            "- Hohe inhaltliche Komplexität allein erzeugt keinen Agenten-Ausgang: "
            f"`{complex_case['case_id']}` ist als `{complex_case['complexity_context']}` "
            f"markiert und ergibt `{complex_result.mode}`.",
            "- Die dynamische Gegenkontrolle zeigt die eigentliche Agentenbedingung: "
            f"`{dynamic_case['case_id']}` ist als `{dynamic_case['complexity_context']}` "
            f"markiert und ergibt `{dynamic_result.mode}`.",
            "- Widersprüchliche Anforderungen werden als `Assessment open` ausgewiesen; "
            "sie werden nicht durch eine spätere positive Regel verdeckt.",
            "",
            "## Methodische Einordnung",
            "",
            "Die V1-Logik ist **expert-informed** und bewusst als kleine, nachvollziehbare "
            "Entscheidungslogik ausgelegt. Sie ist **noch nicht empirisch an einer breiten "
            "Menge realer Unternehmensfälle kalibriert**.",
            "",
            "Für dieses Referenzset gibt es **keine Mindest-Klassifikationsquote und kein "
            "Erfolgsziel**. `Assessment open` ist ein beabsichtigter transparenter Ausgang, "
            "wenn Informationen fehlen, Anforderungen widersprüchlich sind oder der Fall "
            "außerhalb der V1-Taxonomie liegt.",
            "",
            "Die dokumentierten Häufigkeiten beschreiben ausschließlich das fixierte "
            "#213-Referenzset. Sie sind keine empirische Aussage über die Verteilung von "
            "Architekturklassen in realen Unternehmen.",
            "",
        ]
    )
    return "\n".join(lines)


@pytest.mark.parametrize("case", ADVISOR_CASES, ids=lambda case: case["case_id"])
def test_reference_case_matches_productive_advisor_contract(case):
    result = _classify_case(case)
    expected = case["expected"]

    assert result.ruleset_version == RULESET_VERSION
    assert result.mode == expected["mode"]
    assert result.reason_codes == tuple(expected["reason_codes"])
    assert bool(result.why_no_agent) is expected["why_no_agent_required"]
    assert bool(result.open_points) is expected["open_points_expected"]
    assert result.why_pattern.strip()


@pytest.mark.parametrize(
    "case",
    [case for case in ADVISOR_CASES if case["category"] == "adversarial"],
    ids=lambda case: case["case_id"],
)
def test_adversarial_case_never_depends_on_fixture_narrative_for_classification(case):
    result = _classify_case(case)

    assert case["narrative"].strip()
    assert result.mode == case["expected"]["mode"]
    assert result.reason_codes == tuple(case["expected"]["reason_codes"])


def test_complexity_alone_never_creates_bounded_agent():
    cases = {case["case_id"]: case for case in ADVISOR_CASES}
    complex_fixed = cases["advisor_adversarial_high_complexity_fixed_workflow"]
    dynamic_countercontrol = cases["advisor_adversarial_dynamic_countercontrol"]

    complex_result = _classify_case(complex_fixed)
    dynamic_result = _classify_case(dynamic_countercontrol)

    assert complex_fixed["complexity_context"] == "high"
    assert complex_result.mode == MODE_LLM_WORKFLOW
    assert complex_result.mode != MODE_BOUNDED_AGENT

    assert dynamic_countercontrol["complexity_context"] == "low"
    assert dynamic_result.mode == MODE_BOUNDED_AGENT


def test_assessment_open_frequency_and_reason_distribution_are_explicit():
    results = [_classify_case(case) for case in ADVISOR_CASES]
    open_results = [result for result in results if result.mode == MODE_ASSESSMENT_OPEN]
    reason_counts = Counter(code for result in open_results for code in result.reason_codes)

    assert len(ADVISOR_CASES) == 12
    assert len(results) - len(open_results) == 6
    assert len(open_results) == 6
    assert reason_counts == {
        "contradictory_answers": 3,
        "insufficient_information": 2,
        "architecture_boundary_unclear": 1,
    }


def test_committed_assessment_open_report_is_reproducible_from_fixture_and_advisor():
    expected_report = _build_assessment_report(ADVISOR_CASES)
    committed_report = REPORT_PATH.read_text(encoding="utf-8")

    assert committed_report == expected_report
