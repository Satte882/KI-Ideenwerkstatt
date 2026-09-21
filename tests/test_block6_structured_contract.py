import pytest

from ki_radar.accelerator.structured_contract import (
    ACTIVE_ENUM_TARGETS,
    CASCADE_INVALIDATING_STATES,
    StructuredCandidateKind,
    StructuredContractError,
    StructuredFieldType,
    dependency_is_invalidating,
    process_dependency_key,
    structured_field_spec,
    validate_local_key,
)


def test_metric_enum_targets_are_explicit_and_limited():
    assert {
        "use_case.metric.type",
        "use_case.metric.direction",
    } == ACTIVE_ENUM_TARGETS
    assert (
        structured_field_spec(
            target_path="use_case.metric.type",
            provider_field_type="enum",
        ).candidate_kind
        == StructuredCandidateKind.METRIC_SET
    )


@pytest.mark.parametrize("provider_type", ["boolean", "date", "uuid", "reference"])
def test_provider_type_does_not_authorize_unknown_target(provider_type):
    with pytest.raises(StructuredContractError):
        structured_field_spec(
            target_path=f"use_case.hypothetical_{provider_type}",
            provider_field_type=provider_type,
        )


def test_known_target_rejects_mismatching_provider_type():
    with pytest.raises(StructuredContractError):
        structured_field_spec(
            target_path="use_case.metric.baseline",
            provider_field_type="text",
        )


def test_stage_fields_require_grouping_and_correct_types():
    sequence = structured_field_spec(
        target_path="value_stream.stages[].sequence",
        provider_field_type="integer",
    )
    assert sequence.repeated is True
    assert sequence.required_for_object is True
    assert sequence.field_type == StructuredFieldType.INTEGER


def test_process_analysis_uses_only_validated_local_stage_key():
    assert process_dependency_key(referenced_stage_key="stage-01") == "stage-01"
    with pytest.raises(StructuredContractError):
        validate_local_key("Stage 01")


def test_dependency_invalidating_states_are_explicit():
    assert dependency_is_invalidating("rejected") is True
    assert dependency_is_invalidating("conflict") is True
    assert dependency_is_invalidating("valid") is False
    assert "invalid" in CASCADE_INVALIDATING_STATES
