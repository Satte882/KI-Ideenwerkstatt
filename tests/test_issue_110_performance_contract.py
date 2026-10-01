from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

from django.conf import settings

from ki_radar.accelerator import investigation_llm
from ki_radar.accelerator.ap4_evidence import source_pack_hash
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
PROMPTS = Path(settings.BASE_DIR) / "ki_radar/accelerator/investigation_prompts.py"
CONTRACT_RUNTIME_GATE = (
    "median_active_runtime_reduction_percent_at_least_10_and_seconds_at_least_30"
)
BATCHING_RUNTIME_GATE = (
    "median_active_runtime_reduction_percent_at_least_15_and_seconds_at_least_45"
)
REASONING_PATTERN = re.compile(
    r'"low"\s+if role == InvestigationModelCall\.Role\.SYNTHESIZER\s+'
    r'and synthesis_mode == "pre_verifier_repair"\s+else "medium"',
    re.DOTALL,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    prefix = f"blob {len(data)}\0".encode()
    return hashlib.sha1(prefix + data, usedforsecurity=False).hexdigest()


def test_issue110_contract_freezes_current_investigation_execution_contract():
    contract = _load(CONTRACT)["execution_contract"]
    provider_policy = ISSUE4_INVESTIGATION_PROVIDER_POLICY

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
    assert contract["provider_order"] == provider_policy["order"]
    assert contract["allow_fallbacks"] == provider_policy["allow_fallbacks"]
    assert contract["role_limits"] == MODEL_CALL_LIMITS
    prompt_blob = contract["source_blobs"]["investigation_prompts_py"]
    assert prompt_blob == _git_blob_sha(PROMPTS)


def test_issue110_contract_freezes_reasoning_effort_used_by_model_calls():
    contract = _load(CONTRACT)["execution_contract"]
    source = inspect.getsource(investigation_llm._reserve_model_call)

    assert contract["reasoning_effort"]["default"] == "medium"
    assert contract["reasoning_effort"]["pre_verifier_repair"] == "low"
    assert REASONING_PATTERN.search(source)


def test_issue110_golden_set_is_source_bound_and_content_frozen():
    contract = _load(CONTRACT)
    ap4 = _load(AP4_MANIFEST)
    frozen = {item["case_id"]: item for item in ap4["cases"]}
    selected = contract["golden_cases"]
    case_ids = [item["case_id"] for item in selected]

    assert case_ids == ["AP4-01", "AP4-02", "AP4-04", "AP4-05", "AP4-06"]
    expected_manifest = "tests/fixtures/ap4_case_manifest_v1.json"
    assert contract["source_case_manifest"] == expected_manifest

    for item in selected:
        frozen_case = frozen[item["case_id"]]
        source_root = Path(settings.BASE_DIR) / frozen_case["source_pack"]
        current_hash = source_pack_hash(source_root, frozen_case["files"])

        assert current_hash in item["source_pack_hashes"]
        assert item["hard_failures"]
        allowed = set(item["allowed_terminal_states"])
        assert allowed <= {"ready", "waiting_human", "failed"}

        for group in ("expected_key_findings", "required_counterevidence"):
            assert item[group]
            for criterion in item[group]:
                assert criterion["criterion"]
                assert criterion["source_refs"]
                for source_ref in criterion["source_refs"]:
                    assert source_ref["file"] in frozen_case["files"]
                    path = source_root / source_ref["file"]
                    source = path.read_text(encoding="utf-8")
                    assert source_ref["locator"] in source


def test_issue110_quality_authority_requires_assessment_of_every_run():
    authority = _load(CONTRACT)["evaluation_authority"]
    human = authority["human_review"]

    assert authority["deterministic_checks_required_on_all_runs"] is True
    assert len(authority["deterministic_checks"]) >= 6
    assert authority["per_run_assessment_statuses"] == ["pass", "fail", "unassessed"]
    assert authority["all_runs_require_authoritative_assessment_for_adoption"] is True
    assert authority["unassessed_semantic_criterion_blocks_adoption"] is True
    assert human["selection_rule"] == "all_runs_for_non_deterministic_criteria"
    assert human["human_is_final_authority"] is True
    assert authority["llm_judge"] == "support_only"
    assert authority["optimized_verifier_self_assessment_is_sufficient"] is False
    assert authority["critical_errors_are_non_compensable"] is True


def test_issue110_verifier_change_requires_versioned_independent_control_suite():
    control = _load(CONTRACT)["verifier_control_contract"]
    experiment_types = set(control["required_before_experiment_types"])
    expected = {item["control"]: item["expected"] for item in control["minimum_controls"]}

    assert control["versioned_fixture_required"] is True
    assert experiment_types == {"verifier_contract_change", "verifier_model_routing"}
    assert expected["known_good_package"] == "accept"
    assert expected["hallucinated_fact_mutation"] == "reject_or_critical_finding"
    assert expected["missing_counterevidence_mutation"] == "reject_or_critical_finding"
    assert expected["human_authority_bypass_mutation"] == "reject_or_critical_finding"
    assert expected["broken_provenance_mutation"] == "reject_or_critical_finding"
    assert control["optimized_verifier_cannot_label_its_own_controls"] is True
    assert control["human_calibration_required"] is True


def test_issue110_comparison_contract_prevents_post_hoc_subsets_and_defines_noise():
    comparison = _load(CONTRACT)["comparison_contract"]
    experiment = comparison["experiment_interleaving"]
    final = comparison["final_interleaving"]

    assert comparison["affected_cases_must_be_declared_before_variant_runs"] is True
    assert comparison["all_five_golden_cases_must_be_reported"] is True
    assert comparison["ap4_06_results_stratified_by_terminal_state"] is True
    assert comparison["case_noise_floor_seconds"] == "2_x_median_absolute_deviation_seconds"
    assert comparison["too_noisy_result"] == "not_sufficiently_proven"
    expected_denominator = "all_attempted_runs_in_the_same_comparison_arm"
    assert comparison["event_rate_denominator"] == expected_denominator
    assert experiment["candidate_repetitions_per_case"] == 4
    assert experiment["baseline_control_repetitions_per_case"] == 1
    assert final["candidate_repetitions_per_case"] == 3
    assert final["baseline_control_repetitions_per_case"] == 2


def test_issue110_budget_is_finite_and_failures_cannot_be_success_sampled_away():
    budget = _load(CONTRACT)["experiment_budget"]

    assert budget["baseline_repetitions_per_case"] == 5
    assert budget["baseline_real_provider_run_cap"] == 25
    assert budget["baseline_human_review_minutes_cap"] == 480
    assert budget["experiment_real_provider_run_cap_per_gate"] == 25
    assert budget["experiment_human_review_minutes_cap_per_gate"] == 480
    assert budget["experiment_engineering_hours_cap_before_regate"] == 40
    assert budget["final_investigation_run_cap"] == 25
    assert budget["secondary_regression_run_cap"] == 2
    assert budget["final_total_provider_run_cap_including_secondary_regression"] == 27
    expected_cost = (
        budget["baseline_provider_cost_cap_usd"]
        + budget["experiment_provider_cost_cap_usd_per_gate"]
        + budget["final_provider_cost_cap_usd"]
    )
    assert budget["project_provider_cost_cap_usd_without_parent_amendment"] == expected_cost
    assert budget["failed_slow_and_aborted_runs_stay_in_dataset"] is True
    assert budget["replacement_runs_require_reason_and_link"] is True
    assert budget["replacement_runs_do_not_expand_caps"] is True
    assert budget["hard_fail_requires_stop_and_regate_after_human_confirmation"] is True
    assert budget["ambiguous_result_after_budget"] == "not_sufficiently_proven"


def test_issue110_adoption_gates_apply_quality_cost_and_tail_guards_to_all_changes():
    gates = _load(CONTRACT)["adoption_gates"]
    common = gates["common"]

    assert common["observed_quality_hard_failures_max"] == 0
    assert common["all_runs_authoritatively_assessed"] is True
    assert common["unassessed_blocks_adoption"] is True
    assert common["benefit_must_exceed_aa_noise_floor"] is True
    cost_key = "cost_per_accepted_result_increase_percent_max_without_parent_approval"
    assert common[cost_key] == 5
    assert common["timeout_retry_repair_rate_increase_percentage_points_max"] == 5

    contract_benefits = gates["contract_or_model_change"]["any_required_benefit"]
    assert CONTRACT_RUNTIME_GATE in contract_benefits
    batching = gates["batching_or_concurrency_change"]
    assert BATCHING_RUNTIME_GATE in batching["any_required_benefit"]
    assert "no_increase_in_unnecessary_evidence_actions" in batching["extra_requirements"]


def test_issue110_primary_scope_excludes_human_wait_and_bounds_e2e_regression():
    contract = _load(CONTRACT)
    scope = contract["measurement_scope"]
    budget = contract["experiment_budget"]

    assert scope["primary"] == "investigation_to_correct_terminal_state"
    assert scope["human_wait_time_excluded_from_runtime"] is True
    assert scope["secondary_regression"] == "bounded_discovery_to_delivery"
    expected_policy = "baseline_only_when_code_path_and_execution_contract_match"
    assert scope["ap4_historical_runs_policy"] == expected_policy
    assert budget["secondary_regression_case_ids"] == ["AP4-01", "AP4-04"]
    assert budget["secondary_regression_run_cap"] == 2
