from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURE_PATH = ROOT / "tests/fixtures/architecture_real_demo_v1.json"
CLOSURE_PATH = ROOT / "docs/accelerator/ARCHITECTURE_REAL_DEMO_REGRESSION_CLOSURE.md"

REQUIRED_EVIDENCE = (
    "test_architecture_real_demo_advisor_regression.py",
    "ARCHITECTURE_REAL_DEMO_ASSESSMENT_OPEN_REPORT.md",
    "test_architecture_real_demo_quality_acceptance.py",
    "test_architecture_real_demo_ap5_invariance.py",
    "test_architecture_real_demo_ap6_e2e.py",
    "ARCHITECTURE_REAL_DEMO_DRIFT_CONTRACT.md",
    "generation -> initial_critic -> repair -> final_critic",
    "#1451 \u2013 success",
)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_ap8_closure_lists_every_versioned_advisor_and_quality_case():
    fixture = _fixture()
    closure = CLOSURE_PATH.read_text(encoding="utf-8")

    advisor_ids = {case["case_id"] for case in fixture["advisor_cases"]}
    quality_ids = {case["case_id"] for case in fixture["quality_cases"]}

    assert len(advisor_ids) == 12
    assert len(quality_ids) == 14
    assert all(f"`{case_id}`" in closure for case_id in advisor_ids)
    assert all(f"`{case_id}`" in closure for case_id in quality_ids)


def test_ap8_closure_contains_required_cross_cutting_evidence():
    closure = CLOSURE_PATH.read_text(encoding="utf-8")

    for evidence in REQUIRED_EVIDENCE:
        assert evidence in closure

    assert "`Assessment open`: **6**" in closure
    assert "`contradictory_answers`: **3**" in closure
    assert "`insufficient_information`: **2**" in closure
    assert "`architecture_boundary_unclear`: **1**" in closure
    assert "= **4 Calls**" in closure


def test_ap8_closure_keeps_methodological_non_claims_explicit():
    closure = CLOSURE_PATH.read_text(encoding="utf-8")
    normalized = " ".join(closure.replace("**", "").split())

    required = (
        "expert-informed",
        "nicht empirisch an einer breiten Menge realer Unternehmensfälle kalibriert",
        "keine objektive Architekturwahrheit",
        "keinen Framework-Benchmark",
        "kein Multi-Agent-System",
        "kein Domain-, Governance-, Selection- oder Lifecycle-Gate",
        "keinen zweiten Repair-Versuch",
        "synthetisch/anonymisiert",
    )
    for statement in required:
        assert statement in normalized
