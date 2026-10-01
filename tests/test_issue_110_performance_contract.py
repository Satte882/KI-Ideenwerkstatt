from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings

from ki_radar.accelerator.investigation_prompts import (
    PLANNER_PROMPT_VERSION,
    PLANNER_SCHEMA_VERSION,
    SYNTHESIS_PROMPT_VERSION,
    SYNTHESIS_SCHEMA_VERSION,
    VERIFIER_PROMPT_VERSION,
    VERIFIER_SCHEMA_VERSION,
)
from ki_radar.accelerator.investigation_runtime import (
    BUDGET_VERSION,
    ENDPOINT_CAPABILITY,
    ISSUE4_INVESTIGATION_PROVIDER_POLICY,
    LOOP_VERSION,
    MODEL_CALL_LIMITS,
    TRANSPORT_VERSION,
)

CONTRACT = Path(settings.BASE_DIR) / "tests/fixtures/issue106_performance_contract_v1.json"
AP4_MANIFEST = Path(settings.BASE_DIR) / "tests/fixtures/ap4_case_manifest_v1.json"
CONTRACT_RUNTIME_GATE = (
    "median_active_runtime_reduction_percent_at_least_10_and_seconds_at_least_30"
)
BATCHING_RUNTIME_GATE = (
    "median_active_runtime_reduction_percent_at_least_15_and_seconds_at_least_45"
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_issue110_contract_freezes_current_investigation_execution_contract():
    contract = _load(CONTRACT)["execution_contract"]

    assert contract["planner_prompt"] == PLANNER_PROMPT_VERSION
    assert contract["planner_schema"] == PLANNER_SCHEMA_VERSION
    assert contract["synthesis_prompt"] == SYNTHESIS_PROMPT_VERSION
    assert contract["synthesis_schema"] == SYNTHESIS_SCHEMA_VERSION
    assert contract["verifier_prompt"] == VERIFIER_PROMPT_VERSION
    assert contract["verifier_schema"] == VERIFIER_SCHEMA_VERSION
    assert contract["loop"] == LOOP_VERSION
    assert contract["budget"] == BUDGET_VERSION
    assert contract["transport"] == TRANSPORT_VERSION
    assert contract["model"] == ENDPOINT_CAPABILITY["model"]
    assert contract["provider_order"] == ISSUE4_INVESTIGATION_PROVIDER_POLICY["order"]
    assert contract["allow_fallbacks"] == ISSUE4_INVESTIGATION_PROVIDER_POLICY["allow_fallbacks"]
    assert contract["role_limits"] == MODEL_CALL_LIMITS


def test_issue110_golden_set_reuses_only_frozen_ap4_cases_and_source_packs():
    contract = _load(CONTRACT)
    ap4 = _load(AP4_MANIFEST)
    frozen = {item["case_id"]: item for item in ap4["cases"]}
    selected = contract["golden_cases"]

    assert [item["case_id"] for item in selected] == [
        "AP4-01",
        "AP4-02",
        "AP4-04",
        "AP4-05",
        "AP4-06",
    ]
    assert len(selected) == 5
    assert contract["source_case_manifest"] == "tests/fixtures/ap4_case_manifest_v1.json"

    for item in selected:
        frozen_case = frozen[item["case_id"]]
        source_root = Path(settings.BASE_DIR) / frozen_case["source_pack"]
        assert source_root.is_dir()
        actual_files = sorted(path.name for path in source_root.iterdir() if path.is_file())
        assert actual_files == sorted(frozen_case["files"])
        assert item["expected_key_findings"]
        assert item["required_counterevidence"]
        assert item["hard_failures"]
        assert set(item["allowed_terminal_states"]) <= {"ready", "waiting_human", "failed"}


def test_issue110_quality_authority_cannot_self_score_or_average_critical_errors():
    authority = _load(CONTRACT)["evaluation_authority"]

    assert authority["deterministic_checks_required_on_all_runs"] is True
    assert authority["human_review"]["required"] is True
    assert authority["llm_judge"] == "support_only"
    assert authority["optimized_verifier_self_assessment_is_sufficient"] is False
    assert authority["critical_errors_are_non_compensable"] is True


def test_issue110_budget_is_finite_and_failures_cannot_be_success_sampled_away():
    budget = _load(CONTRACT)["experiment_budget"]

    assert budget["baseline_repetitions_per_case"] == 5
    assert budget["baseline_real_provider_run_cap"] == 25
    assert budget["baseline_provider_cost_cap_usd"] > 0
    assert budget["experiment_real_provider_run_cap_per_gate"] == 25
    assert budget["experiment_provider_cost_cap_usd_per_gate"] > 0
    assert budget["experiment_engineering_hours_cap_before_regate"] == 40
    expected_cap = (
        budget["baseline_provider_cost_cap_usd"]
        + budget["experiment_provider_cost_cap_usd_per_gate"]
        + budget["final_provider_cost_cap_usd"]
    )
    assert budget["project_provider_cost_cap_usd_without_parent_amendment"] == expected_cap
    assert budget["failed_slow_and_aborted_runs_stay_in_dataset"] is True
    assert budget["replacement_runs_require_reason_and_link"] is True
    assert budget["ambiguous_result_after_budget"] == "not_sufficiently_proven"


def test_issue110_deeper_architecture_changes_have_stricter_adoption_gates():
    gates = _load(CONTRACT)["adoption_gates"]

    assert "benefit_must_exceed_aa_noise_floor" in gates["common"]
    reversible = gates["reversible_no_contract_change"]
    assert reversible["provider_cost_increase_percent_max"] == 5
    assert CONTRACT_RUNTIME_GATE in gates["contract_or_model_change"]["any_required_benefit"]
    batching = gates["batching_or_concurrency_change"]
    assert BATCHING_RUNTIME_GATE in batching["any_required_benefit"]
    assert "no_increase_in_unnecessary_evidence_actions" in batching["extra_requirements"]


def test_issue110_primary_scope_excludes_human_wait_and_keeps_bounded_regression():
    scope = _load(CONTRACT)["measurement_scope"]

    assert scope["primary"] == "investigation_to_correct_terminal_state"
    assert scope["human_wait_time_excluded_from_runtime"] is True
    assert scope["secondary_regression"] == "bounded_discovery_to_delivery"
    expected_policy = "baseline_only_when_code_path_and_execution_contract_match"
    assert scope["ap4_historical_runs_policy"] == expected_policy
