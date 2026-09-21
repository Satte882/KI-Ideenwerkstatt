import pytest

from ki_radar.delivery import evidence_mapping_contract as contract
from ki_radar.delivery.architecture_artifacts import DeliveryArchitectureArtifacts
from ki_radar.delivery.models import DELIVERY_SECTION_DEFINITIONS, DeliveryPackage

EXPECTED_V1_TARGET_FIELDS = {
    "problem_context",
    "target_outcome",
    "in_scope",
    "out_of_scope",
    "users_and_scenarios",
    "solution_outline",
    "system_context",
    "data_context",
    "integrations",
    "human_oversight",
    "operations_and_support",
    "measurement_plan",
    "acceptance_criteria",
    "risks",
    "handover_notes",
    "system_landscape",
    "data_flows",
}
ALLOWED_SOURCE_KINDS = {
    "use_case",
    "value_stream",
    "solution_selection_snapshot",
    "approval_decision",
}
ARTIFACT_TARGET_FIELDS = {"system_landscape", "data_flows"}


def test_block8_v1_mapping_contract_has_exact_target_whitelist():
    assert contract.MAPPING_CONTRACT_VERSION == "block8.v1"
    assert set(contract.V1_DELIVERY_FIELD_MAPPINGS) == EXPECTED_V1_TARGET_FIELDS
    assert not (EXPECTED_V1_TARGET_FIELDS & contract.FORBIDDEN_AUTOMATED_DELIVERY_FIELDS)


def test_each_mapping_is_explicit_and_points_to_a_real_delivery_field():
    sections = {key for key, _label in DELIVERY_SECTION_DEFINITIONS}
    package_fields = {field.name for field in DeliveryPackage._meta.get_fields()}
    artifact_fields = {field.name for field in DeliveryArchitectureArtifacts._meta.get_fields()}

    for target_field, spec in contract.V1_DELIVERY_FIELD_MAPPINGS.items():
        assert spec.target_field == target_field
        assert spec.section_key in sections
        assert spec.sources
        assert spec.gap_policy is contract.GapPolicy.VISIBLE_GAP
        assert spec.conflict_policy is contract.ConflictPolicy.THREE_STATE_NO_OVERWRITE
        if target_field in ARTIFACT_TARGET_FIELDS:
            assert target_field in artifact_fields
        else:
            assert target_field in package_fields


def test_source_rules_are_static_versioned_and_domain_only():
    configured_source_kinds = set()
    for spec in contract.V1_DELIVERY_FIELD_MAPPINGS.values():
        for source in spec.sources:
            assert source.kind in ALLOWED_SOURCE_KINDS
            assert source.fields
            assert source.version_rule in contract.SourceVersionRule
            assert source.priority >= 1
            assert set(source.required_fields) <= set(source.fields)
            configured_source_kinds.add(source.kind)

    forbidden_source_kinds = {
        "capture_session",
        "analysis_run",
        "field_adoption_candidate",
        "solution_generation_run",
        "provider_response",
    }
    assert not (configured_source_kinds & forbidden_source_kinds)


def test_priority_mappings_define_order_and_compositions_are_explicit():
    for spec in contract.V1_DELIVERY_FIELD_MAPPINGS.values():
        if spec.multi_source_policy is contract.MultiSourcePolicy.PRIORITY:
            priorities = [source.priority for source in spec.sources]
            assert priorities == sorted(priorities)
            assert len(priorities) == len(set(priorities))

        if spec.multi_source_policy is contract.MultiSourcePolicy.COMPOSE:
            assert spec.transform is contract.TransformKind.COMPOSE_STRUCTURED


def test_llm_rest_text_is_allowlisted_to_two_non_authoritative_fields():
    llm_fields = set()
    for field_name, spec in contract.V1_DELIVERY_FIELD_MAPPINGS.items():
        if spec.llm_rest_task is not None:
            llm_fields.add(field_name)

    assert llm_fields == {"system_landscape", "acceptance_criteria"}
    for field_name in llm_fields:
        spec = contract.mapping_spec(field_name)
        assert spec.llm_rest_task is contract.LLMRestTask.LANGUAGE_COMPACTION

    forbidden_llm_fields = contract.FORBIDDEN_AUTOMATED_DELIVERY_FIELDS | {
        "risks",
        "integrations",
        "handover_notes",
        "human_oversight",
        "operations_and_support",
    }
    assert not (llm_fields & forbidden_llm_fields)


def test_handover_notes_only_reads_existing_final_approval():
    spec = contract.mapping_spec("handover_notes")

    assert len(spec.sources) == 1
    source = spec.sources[0]
    assert source.kind == "approval_decision"
    assert source.version_rule is contract.SourceVersionRule.FINAL_APPROVAL_SNAPSHOT
    assert source.constraint == "read_existing_final_positive_approval_only"
    assert "finalized_at" in source.required_fields


def test_selected_solution_data_requires_immutable_decision_snapshot():
    snapshot_sources = []
    for spec in contract.V1_DELIVERY_FIELD_MAPPINGS.values():
        for source in spec.sources:
            if source.kind == "solution_selection_snapshot":
                snapshot_sources.append(source)

    assert snapshot_sources
    for source in snapshot_sources:
        assert source.version_rule is contract.SourceVersionRule.IMMUTABLE_DECISION_SNAPSHOT
        assert source.constraint == "selected_solution_only"


def test_legacy_placeholders_are_catalogued_but_not_mapping_targets():
    normalized = " ".join(contract.LEGACY_PLACEHOLDER_FRAGMENTS)

    assert "konkretisieren" in normalized
    assert "betriebsverantwortung festlegen" in normalized
    assert contract.LEGACY_PLACEHOLDER_FRAGMENTS


def test_unknown_delivery_field_fails_closed():
    with pytest.raises(ValueError, match="nicht freigegeben"):
        contract.mapping_spec("initial_backlog")
