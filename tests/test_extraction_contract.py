import json

import pytest

from ki_radar.accelerator.catalogs import CURRENT_CATALOG_VERSIONS, get_capture_catalog
from ki_radar.accelerator.extraction_contract import (
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SCHEMA_VERSION,
    ExtractionContractError,
    allowed_extraction_target_paths,
    build_extraction_json_schema,
    parse_extraction_document,
    target_object_type_for_path,
)


def _payload(*, suggestion=None, open_questions=None, contradictions=None):
    return {
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "prompt_version": EXTRACTION_PROMPT_VERSION,
        "suggestions": [suggestion] if suggestion else [],
        "open_questions": open_questions or [],
        "contradictions": contradictions or [],
    }


def _suggestion(**overrides):
    value = {
        "target_object_type": "value_stream",
        "target_field": "value_stream.scope_in",
        "target_group_key": None,
        "field_type": "text",
        "suggested_value": "Angebote fachlich vergleichen",
        "source_question": "vs_scope_in",
        "source_excerpt": "Angebote fachlich vergleichen",
        "uncertainty": "low",
        "uncertainty_reason": "Die Aussage ist ausdrücklich als Scope-In formuliert.",
    }
    value.update(overrides)
    return value


def test_valid_document_uses_catalog_specific_target_whitelist():
    catalog = get_capture_catalog("value_stream", "1.0")

    document = parse_extraction_document(_payload(suggestion=_suggestion()), catalog=catalog)

    assert document.schema_version == "1.0"
    assert document.suggestions[0].target_field == "value_stream.scope_in"
    assert "use_case.title" not in allowed_extraction_target_paths(catalog)


def test_explicit_frozen_catalog_is_used_instead_of_active_version(monkeypatch):
    catalog = get_capture_catalog("value_stream", "1.0")
    monkeypatch.setitem(CURRENT_CATALOG_VERSIONS, "value_stream", "9.9")

    document = parse_extraction_document(_payload(suggestion=_suggestion()), catalog=catalog)

    assert document.suggestions[0].source_question == "vs_scope_in"


def test_target_path_must_belong_to_the_declared_source_question():
    catalog = get_capture_catalog("value_stream", "1.0")
    payload = _payload(
        suggestion=_suggestion(
            target_field="value_stream.scope_out",
            source_question="vs_scope_in",
        )
    )

    with pytest.raises(ExtractionContractError, match="ist für Quellfrage"):
        parse_extraction_document(payload, catalog=catalog)


def test_scope_in_and_scope_out_cannot_be_swapped():
    catalog = get_capture_catalog("value_stream", "1.0")
    payload = _payload(
        suggestion=_suggestion(
            target_field="value_stream.scope_in",
            source_question="vs_scope_out",
        )
    )

    with pytest.raises(ExtractionContractError, match="ist für Quellfrage"):
        parse_extraction_document(payload, catalog=catalog)


def test_repeated_target_requires_valid_local_group_key():
    catalog = get_capture_catalog("value_stream", "1.0")
    suggestion = _suggestion(
        target_object_type="value_stream_stage",
        target_field="value_stream.stages[].name",
        target_group_key=None,
        source_question="vs_stages",
    )

    with pytest.raises(ExtractionContractError, match="target_group_key"):
        parse_extraction_document(_payload(suggestion=suggestion), catalog=catalog)


def test_non_repeated_target_rejects_group_key():
    catalog = get_capture_catalog("value_stream", "1.0")

    with pytest.raises(ExtractionContractError, match="muss der Wert null sein"):
        parse_extraction_document(
            _payload(suggestion=_suggestion(target_group_key="gruppe-1")),
            catalog=catalog,
        )


def test_contract_rejects_unknown_fields_and_versions():
    catalog = get_capture_catalog("value_stream", "1.0")
    payload = _payload()
    payload["unexpected"] = True
    payload["schema_version"] = "2.0"

    with pytest.raises(ExtractionContractError) as error:
        parse_extraction_document(payload, catalog=catalog)

    assert any("Unbekannte Felder" in message for message in error.value.errors)
    assert any("Erwartet wird Version 1.0" in message for message in error.value.errors)


def test_findings_may_only_reference_questions_from_the_frozen_catalog():
    catalog = get_capture_catalog("use_case", "1.0")
    payload = _payload(
        open_questions=[
            {
                "message": "Messzeitraum fehlt.",
                "source_questions": ["not_in_catalog"],
            }
        ]
    )

    with pytest.raises(ExtractionContractError, match="Unbekannte Quellfrage"):
        parse_extraction_document(payload, catalog=catalog)


def test_target_object_type_is_derived_from_the_target_path():
    assert target_object_type_for_path("value_stream.stages[].name") == "value_stream_stage"
    assert target_object_type_for_path("solution_options[].name") == "solution_option"
    assert target_object_type_for_path("use_case.title") == "use_case"


def test_provider_schema_is_derived_from_frozen_catalog():
    catalog = get_capture_catalog("value_stream", "1.0")

    schema = build_extraction_json_schema(catalog)
    suggestion_schema = schema["properties"]["suggestions"]["items"]

    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == EXTRACTION_SCHEMA_VERSION
    assert schema["properties"]["prompt_version"]["const"] == EXTRACTION_PROMPT_VERSION
    assert set(suggestion_schema["properties"]["target_field"]["enum"]) == set(
        allowed_extraction_target_paths(catalog)
    )
    assert "use_case.title" not in suggestion_schema["properties"]["target_field"]["enum"]
    assert set(suggestion_schema["properties"]["source_question"]["enum"]) == set(
        catalog.question_map
    )
    assert suggestion_schema["additionalProperties"] is False


def test_direct_use_case_provider_cannot_generate_groups_rejected_by_parser():
    catalog = get_capture_catalog("use_case", "1.0")
    schema = build_extraction_json_schema(catalog)
    group_schema = schema["properties"]["suggestions"]["items"]["properties"]["target_group_key"]
    suggestion = _suggestion(
        target_object_type="use_case",
        target_field="use_case.title",
        source_question="uc_problem_context",
        target_group_key="wissensantworten",
    )

    assert group_schema["type"] == "null"
    assert "anyOf" not in group_schema
    with pytest.raises(ExtractionContractError, match="muss der Wert null sein"):
        parse_extraction_document(_payload(suggestion=suggestion), catalog=catalog)

    suggestion["target_group_key"] = None
    document = parse_extraction_document(_payload(suggestion=suggestion), catalog=catalog)
    assert document.suggestions[0].target_group_key is None
    assert document.schema_version == "1.0"
    assert document.prompt_version == "1.0"


@pytest.mark.parametrize("catalog_version", ["1.0", "2.0"])
def test_value_stream_provider_keeps_supported_repeated_groups(catalog_version):
    catalog = get_capture_catalog("value_stream", catalog_version)
    schema = build_extraction_json_schema(catalog)
    group_schema = schema["properties"]["suggestions"]["items"]["properties"]["target_group_key"]

    assert group_schema["anyOf"] == [
        {"type": "string", "minLength": 1, "pattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$"},
        {"type": "null"},
    ]


def test_provider_receives_the_same_enum_codes_and_types_that_validation_requires():
    from ki_radar.core.scenario_blueprint_validation import load_blueprint_contract

    catalog = get_capture_catalog("use_case", "1.0")
    schema = build_extraction_json_schema(catalog)
    description = schema["properties"]["suggestions"]["items"]["properties"]["suggested_value"][
        "description"
    ]
    constraints = json.loads(description.split("\n", 1)[1])
    enums = load_blueprint_contract()["allowed_enums"]

    assert set(constraints) == allowed_extraction_target_paths(catalog)
    for path in ("use_case.metric.type", "use_case.metric.direction", "use_case.solution_type"):
        assert constraints[path] == {"field_type": "enum", "allowed_values": enums[path]}
    assert constraints["use_case.metric.baseline"] == {"field_type": "decimal"}
    assert constraints["use_case.title"] == {"field_type": "text"}
