from __future__ import annotations

import json
from pathlib import Path

from ki_radar.accelerator.models import SolutionQualityRun
from ki_radar.accelerator.solution_critic_contract import CRITIC_CRITERIA
from ki_radar.accelerator.solution_generation_contract import GENERATED_OPTION_FIELDS, OPTION_LANES

ROOT = Path(__file__).parents[1]
FIXTURE_PATH = ROOT / "tests/fixtures/architecture_real_demo_v1.json"
ASSESSMENT_REPORT_PATH = ROOT / "docs/accelerator/ARCHITECTURE_REAL_DEMO_ASSESSMENT_OPEN_REPORT.md"
DRIFT_CONTRACT_PATH = ROOT / "docs/accelerator/ARCHITECTURE_REAL_DEMO_DRIFT_CONTRACT.md"

EXPECTED_CRITIC_CRITERIA = (
    "distinctiveness",
    "bottleneck_fit",
    "grounding_consistency",
    "evidence_discipline",
    "complexity_proportionality",
)
EXPECTED_QUALITY_STEP_ORDER = ("initial_critic", "repair", "final_critic")

EVIDENCE_PATHS = (
    "tests/fixtures/architecture_advisor_matrix_v1.json",
    "tests/fixtures/architecture_real_demo_v1.json",
    "tests/fixtures/architecture_real_demo_v1.schema.json",
    "tests/fixtures/architecture_real_demo_v1.sha256",
    "tests/test_architecture_advisor_contract.py",
    "tests/test_architecture_real_demo_fixture_contract.py",
    "tests/test_architecture_real_demo_advisor_regression.py",
    "tests/test_architecture_real_demo_quality_acceptance.py",
    "tests/test_architecture_real_demo_ap5_invariance.py",
    "tests/test_architecture_real_demo_ap6_e2e.py",
    "docs/accelerator/ARCHITECTURE_REAL_DEMO_ASSESSMENT_OPEN_REPORT.md",
    "docs/accelerator/ARCHITECTURE_REAL_DEMO_QUALITY_MATRIX.md",
)


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _quality_cases() -> dict[str, dict[str, object]]:
    payload = _load_fixture()
    return {case["case_id"]: case for case in payload["quality_cases"]}


def test_ap7_structured_quality_and_state_machine_drift_contract_is_fixed():
    assert tuple(CRITIC_CRITERIA) == EXPECTED_CRITIC_CRITERIA
    assert tuple(SolutionQualityRun.StepType.values) == EXPECTED_QUALITY_STEP_ORDER

    one_shot_constraint = next(
        constraint
        for constraint in SolutionQualityRun._meta.constraints
        if constraint.name == "uniq_solution_quality_step"
    )
    assert tuple(one_shot_constraint.fields) == ("solution_generation_run", "step_type")

    cases = _quality_cases()
    exactly_one = cases["quality_exactly_one_repair"]["expected"]
    no_second = cases["quality_no_second_repair_after_final"]["expected"]
    human_review = cases["quality_remaining_final_finding_human_review"]["expected"]
    full_path = cases["quality_full_path_call_cap"]["expected"]

    assert exactly_one["repair_runs_max"] == 1
    assert exactly_one["preview_policy"] == "machine_repair_once"
    assert no_second["repair_runs_max"] == 1
    assert no_second["provider_calls_max"] == 0
    assert no_second["human_review_required"] is True
    assert human_review["repair_runs_max"] == 1
    assert human_review["human_review_required"] is True
    assert full_path["repair_runs_max"] == 1
    assert full_path["provider_calls_max"] == 4
    assert full_path["human_review_required"] is True


def test_ap7_quality_targets_remain_structured_and_bound_to_product_fields():
    for case in _quality_cases().values():
        target = case["expected"]["target"]
        if target is None:
            continue
        assert target["option"] in OPTION_LANES
        assert target["field"] in GENERATED_OPTION_FIELDS
        assert target["source_ids"]


def test_ap7_consolidated_drift_evidence_paths_remain_present():
    missing = [path for path in EVIDENCE_PATHS if not (ROOT / path).is_file()]
    assert missing == []


def test_ap7_assessment_open_report_provenance_remains_explicit():
    report = ASSESSMENT_REPORT_PATH.read_text(encoding="utf-8")

    assert "Fixture: `tests/fixtures/architecture_real_demo_v1.json`" in report
    assert "Ruleset: `architecture-advisor-v1`" in report
    assert "- Getestete Advisor-Fälle: **12**" in report
    assert "- `Assessment open`: **6**" in report
    assert "- `contradictory_answers`: **3**" in report
    assert "- `insufficient_information`: **2**" in report
    assert "- `architecture_boundary_unclear`: **1**" in report


def test_ap7_methodological_limits_are_explicit_without_hashing_free_text():
    document = DRIFT_CONTRACT_PATH.read_text(encoding="utf-8")
    normalized_document = " ".join(document.replace("**", "").split())
    required_statements = (
        "expert-informed",
        "nicht empirisch kalibriert",
        "keine objektive Architekturwahrheit",
        "`Assessment open` ist ein beabsichtigter Sicherheitsausgang",
        "kein Framework-Benchmark",
        "kein Multi-Agent-System",
        "kein Domain-, Governance-, Selection- oder Lifecycle-Gate",
        "Freie LLM-Texte werden nicht als Ganzes gehasht",
    )

    for statement in required_statements:
        assert statement in normalized_document
