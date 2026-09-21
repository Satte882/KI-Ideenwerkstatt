# fmt: off
import hashlib
import json
from pathlib import Path

FIXTURE_PATH = Path(__file__).resolve().parents[1].joinpath(
    "ki_radar",
    "accelerator",
    "block9_benchmark.v1.json",
)
EXPECTED_CANONICAL_SHA256 = "e3c894f6ee2a87cc7755380fc6dc43f7352796bfaa31cddd56491997f38f7dab"
REFERENCE_BLUEPRINT = "ki_radar/core/scenario_blueprints/real_demo.v1.json"
REFERENCE_SHA256 = "a910863c3f677eb95b593e8031f48e54f811c5bb55295b4e601ae6f13a0b70d5"
EXPECTED_ORDER = (
    "manual-A-1",
    "accelerator-A-1",
    "accelerator-A-2",
    "manual-A-2",
    "manual-A-3",
    "accelerator-A-3",
)
EXPECTED_ACCELERATOR_SEEDS = (
    "business_unit",
    "business_owner",
    "submitter",
    "status",
    "decision_status",
)
EXPECTED_NO_INVENTION = (
    "provider",
    "model_name",
    "support_responsibility",
)


def _load_fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _canonical_sha256(payload):
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_block9_benchmark_fixture_is_frozen():
    fixture = _load_fixture()

    assert fixture["schema_version"] == "1.0"
    assert fixture["benchmark_version"] == "block9-v1"
    assert fixture["frozen"] is True
    assert _canonical_sha256(fixture) == EXPECTED_CANONICAL_SHA256


def test_block9_benchmark_uses_real_demo_as_reference_without_mutating_it():
    reference = _load_fixture()["reference"]

    assert reference["blueprint_path"] == REFERENCE_BLUEPRINT
    assert reference["blueprint_canonical_sha256"] == REFERENCE_SHA256


def test_block9_benchmark_freezes_interactive_run_order_and_count():
    operator = _load_fixture()["operator_contract"]
    order = operator["interactive_order"]

    assert operator["warm_up_runs"] == 1
    assert operator["scored_runs_per_interactive_path"] == 3
    assert tuple(order) == EXPECTED_ORDER
    assert sum(item.startswith("manual-") for item in order) == 3
    assert sum(item.startswith("accelerator-") for item in order) == 3


def test_block9_benchmark_has_fixed_primary_end_state_and_gate_boundary():
    end_state = _load_fixture()["shared_end_state"]

    assert end_state["object"] == "UseCase draft"
    assert end_state["required_status"] == "idea"
    assert end_state["required_decision_status"] == "clarification"
    assert "metric_target" in end_state["scored_fields"]
    assert "human_oversight" in end_state["scored_fields"]
    assert "approval/final decision" in end_state["excluded_gate_fields"]
    assert "pilot start" in end_state["excluded_gate_fields"]
    assert "go-live" in end_state["excluded_gate_fields"]


def test_block9_benchmark_keeps_path_specific_start_states_explicit():
    paths = _load_fixture()["paths"]

    assert paths["manual"]["kind"] == "interactive"
    assert paths["accelerator"]["kind"] == "interactive"
    assert paths["blueprint"]["kind"] == "technical_control"
    assert paths["delivery"]["kind"] == "secondary"
    assert paths["delivery"]["excluded_from_30_minute_primary"] is True
    seeds = paths["accelerator"]["seed_fields_excluded_from_scoring"]
    assert tuple(seeds) == EXPECTED_ACCELERATOR_SEEDS


def test_block9_robustness_case_contains_all_required_challenges():
    quality = _load_fixture()["cases"]["B"]["quality_expectations"]

    assert quality["missing_required_facts"] == 1
    assert quality["source_conflicts"] == 1
    assert quality["scope_traps"] == 1
    assert quality["missing_fact_keys"] == ["support_responsibility"]
    assert quality["conflict_keys"] == ["metric_target"]
    assert tuple(quality["must_not_invent"]) == EXPECTED_NO_INVENTION
    pair = quality["number_unit_pairs"][0]
    assert pair == {"field": "metric_baseline", "value": "11", "unit": "Minuten"}


def test_block9_measurement_contract_preserves_raw_runs():
    measurement = _load_fixture()["measurement_contract"]

    assert measurement["time_components"] == [
        "active_input_seconds",
        "navigation_seconds",
        "review_seconds",
        "correction_seconds",
        "system_wait_seconds",
        "end_to_end_seconds",
    ]
    assert "aborts" in measurement["quality_counts"]
    assert "total_tokens" in measurement["llm_metrics"]
    assert "deterministic_fields" in measurement["delivery_metrics"]
    assert "Never discard" in measurement["raw_run_rule"]
# fmt: on
