# fmt: off
import hashlib
import json
from pathlib import Path

import pytest

from ki_radar.accelerator.benchmark_measurement import build_raw_record
from ki_radar.accelerator.field_registry import ADOPTION_TARGETS
from ki_radar.accelerator.models import CaptureSession
from ki_radar.core.taxonomy import BusinessDomain
from ki_radar.use_cases.intake import WIZARD_STEPS
from ki_radar.use_cases.intake_views import _build_use_case
from ki_radar.use_cases.models import UseCase

FIXTURE_PATH = Path(__file__).resolve().parents[1].joinpath(
    "ki_radar",
    "accelerator",
    "block9_benchmark.v2.json",
)
EXPECTED_SHA256 = "d4f7431ac68bb94b05885ae25f323e4147cf68fb20977ecd18c2acdeef74e6d1"
EXPECTED_ORDER = (
    "manual-A-1",
    "accelerator-A-1",
    "accelerator-A-2",
    "manual-A-2",
    "manual-A-3",
    "accelerator-A-3",
)
EXPECTED_POST_INTAKE = {
    "interface_description",
    "benefit_category",
    "human_oversight",
}

pytestmark = pytest.mark.django_db


def _fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _canonical_sha256(payload):
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _manual_intake_fields():
    fields = set()
    for step in range(1, 6):
        fields.update(WIZARD_STEPS[step]["form"].base_fields)
    return fields


def test_block9_v2_is_new_frozen_version_without_mutating_v1():
    fixture = _fixture()

    assert fixture["benchmark_version"] == "block9-v2"
    assert fixture["supersedes"] == "block9-v1"
    assert fixture["frozen"] is True
    assert _canonical_sha256(fixture) == EXPECTED_SHA256
    assert tuple(fixture["operator_contract"]["interactive_order"]) == EXPECTED_ORDER
    assert fixture["operator_contract"]["quality_run"] == "accelerator-B-1"


def test_block9_v2_matches_real_manual_intake_field_coverage():
    fixture = _fixture()
    scored = set(fixture["shared_end_state"]["scored_fields"])
    intake_fields = _manual_intake_fields()
    missing_from_intake = scored - intake_fields

    assert missing_from_intake == EXPECTED_POST_INTAKE
    assert set(fixture["paths"]["manual"]["post_intake_edit_fields"]) == EXPECTED_POST_INTAKE
    assert {"business_domain", "business_capability", "hosting_type"} <= intake_fields
    assert fixture["common_path_facts"]["business_domain"] == BusinessDomain.PROCUREMENT


def test_block9_v2_records_real_manual_builder_semantics(business_unit, owner):
    fixture = _fixture()
    facts = fixture["cases"]["A"]["facts"]
    common = fixture["common_path_facts"]
    stored = {
        "title": facts["title"],
        "summary": facts["summary"],
        "problem_statement": facts["problem_statement"],
        "business_unit": business_unit.pk,
        "business_owner": owner.pk,
        "business_domain": common["business_domain"],
        "business_capability": common["business_capability"],
        "affected_process": facts["affected_process"],
        "target_users": facts["target_users"],
        "source_systems": facts["source_systems"],
        "intended_users": facts["intended_users"],
        "intended_purpose": facts["intended_purpose"],
        "privacy_review_required": False,
        "security_review_required": False,
        "legal_review_required": False,
        "expected_benefit": facts["expected_benefit"],
        "metric_name": facts["metric_name"],
        "metric_type": facts["metric_type"],
        "metric_direction": facts["metric_direction"],
        "metric_unit": facts["metric_unit"],
        "metric_baseline": facts["metric_baseline"],
        "metric_target": facts["metric_target"],
        "metric_measurement_method": facts["metric_measurement_method"],
        "data_sources": facts["data_sources"],
        "solution_type": facts["solution_type"],
        "hosting_type": common["hosting_type"],
    }

    candidate = _build_use_case(stored=stored, user=owner, business_owner=owner)

    assert candidate.decision_status == UseCase.DecisionStatus.READY
    assert candidate.summary == facts["summary"]
    assert candidate.source_systems == facts["source_systems"]
    assert candidate.data_sources == facts["data_sources"]


def test_block9_v2_accelerator_plain_text_adoption_matches_registry():
    fixture = _fixture()
    spec = ADOPTION_TARGETS[CaptureSession.CaptureType.USE_CASE]

    assert set(
        fixture["paths"]["accelerator"]["known_plain_text_adoption_fields"]
    ) == set(spec.fields)
    assert "solution_type" not in spec.fields
    assert fixture["paths"]["accelerator"]["normal_edit_fallback_scored_fields"] == [
        "solution_type"
    ]


def test_block9_v2_robustness_case_has_only_declared_gap_and_conflict():
    fixture = _fixture()
    case = fixture["cases"]["B"]
    quality = case["quality_expectations"]

    assert quality["missing_required_facts"] == 1
    assert quality["missing_fact_keys"] == ["support_responsibility"]
    assert case["facts"]["support_responsibility"] is None
    assert quality["conflict_keys"] == ["metric_target"]
    assert case["facts"]["metric_target"] is None
    assert case["facts"]["metric_target_conflicting"] == ["8.25", "8.5"]


def test_block9_measurement_can_record_v2_without_relabeling_v1_defaults():
    v2_record = build_raw_record(
        benchmark_version="block9-v2",
        run_id="manual-A-1",
        path="manual",
        case_key="A",
        status="completed",
        times={},
        quality={},
    )
    v1_record = build_raw_record(
        run_id="blueprint-A-control-1",
        path="blueprint",
        case_key="A",
        status="completed",
        times={},
        quality={},
    )

    assert v2_record["benchmark_version"] == "block9-v2"
    assert v1_record["benchmark_version"] == "block9-v1"
# fmt: on
