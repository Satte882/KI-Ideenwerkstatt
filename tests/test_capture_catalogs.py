import pytest

from ki_radar.accelerator.catalogs import (
    ANSWER_SCHEMA_VERSION,
    CATALOGS,
    CaptureAnswerValidationError,
    UnsupportedCaptureCatalog,
    allowed_blueprint_target_paths,
    catalog_contract_errors,
    catalog_progress,
    get_capture_catalog,
    validate_answer_document,
)


def test_catalogs_are_versioned_and_contract_compatible():
    assert set(CATALOGS) == {("value_stream", "1.0"), ("use_case", "1.0")}

    for catalog in CATALOGS.values():
        assert catalog.version == "1.0"
        assert catalog.schema_version == ANSWER_SCHEMA_VERSION
        assert catalog.sections
        assert catalog.questions
        assert catalog_contract_errors(catalog) == ()


def test_catalog_question_ids_are_stable_and_unique():
    for catalog in CATALOGS.values():
        keys = [question.key for question in catalog.questions]
        assert len(keys) == len(set(keys))
        assert all(key.replace("_", "").isalnum() for key in keys)


def test_scope_in_and_scope_out_are_separate_questions():
    catalog = get_capture_catalog("value_stream")
    question_map = catalog.question_map

    assert question_map["vs_scope_in"].target_paths == ("value_stream.scope_in",)
    assert question_map["vs_scope_out"].target_paths == ("value_stream.scope_out",)
    assert question_map["vs_scope_in"].key != question_map["vs_scope_out"].key


def test_catalogs_do_not_capture_workflow_or_system_states():
    forbidden = {
        "value_stream.key",
        "value_stream.status",
        "value_stream.focus.status",
        "process_analysis.key",
        "process_analysis.stage_key",
        "process_analysis.status",
        "solution_options[].key",
        "solution_options[].recommendation",
        "solution_options[].evaluation_status",
        "use_case.key",
        "use_case.status",
        "use_case.decision_status",
    }

    configured = {
        target
        for catalog in CATALOGS.values()
        for question in catalog.questions
        for target in question.target_paths
    }
    assert configured.isdisjoint(forbidden)
    assert configured <= allowed_blueprint_target_paths()


def test_explicit_supported_version_is_frozen_and_unknown_version_is_rejected():
    catalog = get_capture_catalog("value_stream", "1.0")
    assert catalog is get_capture_catalog("value_stream")

    with pytest.raises(UnsupportedCaptureCatalog, match="nicht mehr unterstützt"):
        get_capture_catalog("value_stream", "0.9")


def test_answer_document_rejects_unknown_questions_and_non_text_values():
    catalog = get_capture_catalog("use_case")

    with pytest.raises(CaptureAnswerValidationError) as error:
        validate_answer_document(
            catalog,
            {
                "uc_problem_context": 123,
                "not_in_catalog": "Wert",
            },
        )

    assert "Antwort für uc_problem_context muss Text sein." in error.value.errors
    assert "Unbekannte Frage-ID: not_in_catalog" in error.value.errors


def test_answer_document_normalizes_text_and_checks_completion():
    catalog = get_capture_catalog("use_case")
    answers = {
        question.key: f"  Antwort für {question.key}  "
        for question in catalog.questions
        if question.required
    }

    normalized = validate_answer_document(catalog, answers, require_complete=True)

    assert all(value.startswith("Antwort") for value in normalized.values())
    assert catalog_progress(catalog, normalized) == (
        len(catalog.required_question_keys),
        len(catalog.required_question_keys),
    )


def test_answer_document_lists_all_missing_required_answers():
    catalog = get_capture_catalog("value_stream")

    with pytest.raises(CaptureAnswerValidationError) as error:
        validate_answer_document(catalog, {}, require_complete=True)

    assert len(error.value.errors) == len(catalog.required_question_keys)
    assert all(message.startswith("Pflichtantwort fehlt:") for message in error.value.errors)


def test_answer_document_enforces_question_length_limit():
    catalog = get_capture_catalog("use_case")
    question = catalog.question_map["uc_problem_context"]

    with pytest.raises(CaptureAnswerValidationError, match="überschreitet"):
        validate_answer_document(catalog, {question.key: "x" * (question.max_length + 1)})


def test_open_questions_are_optional_and_have_no_blueprint_target():
    for capture_type, question_key in (
        ("value_stream", "vs_open_questions"),
        ("use_case", "uc_open_questions"),
    ):
        question = get_capture_catalog(capture_type).question_map[question_key]
        assert question.required is False
        assert question.target_paths == ()
