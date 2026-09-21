from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ki_radar.accelerator.solution_critic_contract import CRITIC_CRITERIA
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from ki_radar.accelerator.solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
    QUALITY_CONTRACT_VERSION,
    REPAIR_PROMPT_VERSION,
    REPAIR_SCHEMA_VERSION,
)
from ki_radar.architecture.architecture_advisor import (
    ANSWER_VALUES,
    MODE_LABELS,
    REASON_CODE_ORDER,
    RULESET_VERSION,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "architecture_real_demo_v1.json"
SCHEMA_PATH = Path(__file__).parent / "fixtures" / "architecture_real_demo_v1.schema.json"
CHECKSUM_PATH = Path(__file__).parent / "fixtures" / "architecture_real_demo_v1.sha256"

EXPECTED_FIXTURE_VERSION = "architecture-real-demo-v1"
EXPECTED_SCHEMA_VERSION = "architecture-real-demo-fixture-schema-v1"
EXPECTED_SCHEMA_ID = "urn:ki-usecase-radar:architecture-real-demo-fixture:v1"
EXPECTED_FIXTURE_SHA256 = "be3cc95f6e815370613ccfe088e7783bcfe88db229e2ffa218fea3a14c06348b"

EXPECTED_ADVISOR_CASE_IDS = {
    "advisor_canonical_no_llm",
    "advisor_canonical_controlled_llm",
    "advisor_canonical_llm_workflow",
    "advisor_canonical_bounded_agent",
    "advisor_canonical_assessment_open",
    "advisor_adversarial_simpler_and_semantic",
    "advisor_adversarial_fixed_steps_and_dynamic",
    "advisor_adversarial_taxonomy_boundary",
    "advisor_adversarial_dynamic_claim_fixed_flow",
    "advisor_adversarial_all_unclear",
    "advisor_adversarial_high_complexity_fixed_workflow",
    "advisor_adversarial_dynamic_countercontrol",
}

EXPECTED_QUALITY_CASE_IDS = {
    "quality_distinctiveness_near_identical",
    "quality_missing_bottleneck_reference",
    "quality_unsubstantiated_qualitative_claim",
    "quality_explicit_assumption_positive_control",
    "quality_unnecessary_architecture_complexity",
    "quality_structured_finding_reference",
    "quality_initial_critic_provider_failure",
    "quality_repair_provider_failure",
    "quality_invalid_repair_contract",
    "quality_human_edit_collision",
    "quality_exactly_one_repair",
    "quality_no_second_repair_after_final",
    "quality_remaining_final_finding_human_review",
    "quality_full_path_call_cap",
}


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_architecture_real_demo_fixture_checksum_and_contract_versions():
    raw = FIXTURE_PATH.read_bytes().replace(b"\r\n", b"\n")
    payload = json.loads(raw)
    checksum_line = CHECKSUM_PATH.read_text(encoding="utf-8").strip()

    actual_checksum = hashlib.sha256(raw, usedforsecurity=False).hexdigest()
    assert actual_checksum == EXPECTED_FIXTURE_SHA256
    assert checksum_line == f"{EXPECTED_FIXTURE_SHA256}  architecture_real_demo_v1.json"

    assert payload["fixture_version"] == EXPECTED_FIXTURE_VERSION
    assert payload["schema_version"] == EXPECTED_SCHEMA_VERSION
    assert payload["data_classification"] == "synthetic_anonymized"
    assert payload["contract_versions"] == {
        "architecture_advisor_ruleset": RULESET_VERSION,
        "generation_schema": GENERATION_SCHEMA_VERSION,
        "generation_prompt": GENERATION_PROMPT_VERSION,
        "quality_contract": QUALITY_CONTRACT_VERSION,
        "critic_schema": CRITIC_SCHEMA_VERSION,
        "critic_prompt": CRITIC_PROMPT_VERSION,
        "repair_schema": REPAIR_SCHEMA_VERSION,
        "repair_prompt": REPAIR_PROMPT_VERSION,
    }


def test_architecture_real_demo_schema_tracks_product_enums_and_versions():
    schema = _load_json(SCHEMA_PATH)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == EXPECTED_SCHEMA_ID
    assert schema["properties"]["schema_version"]["const"] == EXPECTED_SCHEMA_VERSION
    assert schema["properties"]["fixture_version"]["const"] == EXPECTED_FIXTURE_VERSION
    assert schema["properties"]["data_classification"]["const"] == "synthetic_anonymized"
    assert schema["additionalProperties"] is False

    answer_properties = schema["$defs"]["advisor_answers"]["properties"]
    assert set(answer_properties) == {
        "simpler_solution_sufficient",
        "semantic_reasoning_required",
        "multiple_known_ai_steps_required",
        "dynamic_orchestration_required",
    }
    assert all(prop["enum"] == list(ANSWER_VALUES) for prop in answer_properties.values())

    advisor_expected = schema["$defs"]["advisor_expected"]["properties"]
    assert advisor_expected["mode"]["enum"] == list(MODE_LABELS)
    assert advisor_expected["reason_codes"]["items"]["enum"] == list(REASON_CODE_ORDER)

    quality_expected = schema["$defs"]["quality_expected"]["properties"]
    assert quality_expected["criterion"]["enum"] == [None, *CRITIC_CRITERIA]
    quality_target = schema["$defs"]["quality_target"]["properties"]
    assert quality_target["option"]["enum"] == list(OPTION_LANES)
    assert quality_target["field"]["enum"] == list(GENERATED_OPTION_FIELDS)


def test_architecture_real_demo_fixture_has_exact_named_case_sets():
    payload = _load_json(FIXTURE_PATH)
    advisor_cases = payload["advisor_cases"]
    quality_cases = payload["quality_cases"]

    advisor_ids = [case["case_id"] for case in advisor_cases]
    quality_ids = [case["case_id"] for case in quality_cases]
    assert len(advisor_ids) == len(set(advisor_ids)) == 12
    assert len(quality_ids) == len(set(quality_ids)) == 14
    assert set(advisor_ids) == EXPECTED_ADVISOR_CASE_IDS
    assert set(quality_ids) == EXPECTED_QUALITY_CASE_IDS

    category_counts = {
        category: sum(case["category"] == category for case in advisor_cases)
        for category in ("canonical", "adversarial")
    }
    assert category_counts == {"canonical": 5, "adversarial": 7}

    for case in advisor_cases:
        assert set(case) == {
            "case_id",
            "category",
            "name",
            "narrative",
            "complexity_context",
            "answers",
            "expected",
        }
        assert case["name"].strip()
        assert case["narrative"].strip()
        assert set(case["answers"]) == {
            "simpler_solution_sufficient",
            "semantic_reasoning_required",
            "multiple_known_ai_steps_required",
            "dynamic_orchestration_required",
        }
        assert set(case["answers"].values()).issubset(ANSWER_VALUES)
        assert case["expected"]["mode"] in MODE_LABELS
        assert set(case["expected"]["reason_codes"]).issubset(REASON_CODE_ORDER)

    for case in quality_cases:
        assert set(case) == {"case_id", "kind", "description", "expected"}
        assert case["description"].strip()
        expected = case["expected"]
        assert expected["criterion"] is None or expected["criterion"] in CRITIC_CRITERIA
        assert 0 <= expected["repair_runs_max"] <= 1
        assert 0 <= expected["provider_calls_max"] <= 4
        target = expected["target"]
        if target is not None:
            assert target["option"] in OPTION_LANES
            assert target["field"] in GENERATED_OPTION_FIELDS
            assert target["source_ids"]


def test_architecture_real_demo_fixture_is_explicitly_synthetic_and_cross_referenced():
    payload = _load_json(FIXTURE_PATH)
    real_demo = payload["real_demo"]

    assert payload["data_classification"] == "synthetic_anonymized"
    assert real_demo["synthetic"] is True
    assert real_demo["contains_personal_data"] is False
    assert real_demo["scenario_key"] == "architecture-real-demo-procurement-v1"

    advisor_ids = {case["case_id"] for case in payload["advisor_cases"]}
    option_keys = set()
    for option in real_demo["solution_options"]:
        assert option["advisor_case_id"] in advisor_ids
        option_keys.add(option["option_key"])
        assert option["name"].strip()
        assert option["description"].strip()

    assert len(option_keys) == len(real_demo["solution_options"]) == 3
    assert real_demo["value_stream"]["name"] == "Synthetischer Beschaffungsprozess"
    assert real_demo["process_analysis"]["name"] == "Synthetischer Angebotsvergleich"


def test_positive_quality_control_is_non_finding_and_failure_cases_preserve_preview():
    payload = _load_json(FIXTURE_PATH)
    cases = {case["case_id"]: case for case in payload["quality_cases"]}

    positive = cases["quality_explicit_assumption_positive_control"]["expected"]
    assert positive["finding_expected"] is False
    assert positive["criterion"] is None
    assert positive["target"] is None
    assert positive["repair_runs_max"] == 0

    for case_id in (
        "quality_initial_critic_provider_failure",
        "quality_repair_provider_failure",
        "quality_invalid_repair_contract",
    ):
        assert cases[case_id]["expected"]["preview_policy"] == "preserve_original"

    call_cap = cases["quality_full_path_call_cap"]["expected"]
    assert call_cap["provider_calls_max"] == 4
    assert call_cap["repair_runs_max"] == 1
