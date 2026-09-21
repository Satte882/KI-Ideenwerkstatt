from types import SimpleNamespace

import pytest

from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.extraction_validation import (
    ExtractionValidationError,
    validate_extraction_document,
)


def _prepared(question_key: str, answer: str):
    return SimpleNamespace(
        catalog=get_capture_catalog("use_case", "1.0"),
        answers={question_key: answer},
    )


def _payload(
    *,
    target_field: str,
    source_question: str,
    source_excerpt: str,
    suggested_value,
    field_type: str = "text",
) -> dict:
    return {
        "schema_version": "1.0",
        "prompt_version": "1.0",
        "suggestions": [
            {
                "target_object_type": "use_case",
                "target_field": target_field,
                "target_group_key": None,
                "field_type": field_type,
                "suggested_value": suggested_value,
                "source_question": source_question,
                "source_excerpt": source_excerpt,
                "uncertainty": "low",
                "uncertainty_reason": "Explizit in der Antwort genannt.",
            }
        ],
        "open_questions": [],
        "contradictions": [],
    }


@pytest.mark.parametrize(
    (
        "target_field",
        "source_question",
        "source_excerpt",
        "suggested_value",
        "expected_type",
        "expected_value",
    ),
    [
        (
            "use_case.classification.business_domain",
            "uc_problem_context",
            "Fachdomäne: procurement / Einkauf und Beschaffung",
            "procurement / Einkauf und Beschaffung",
            "enum",
            "procurement",
        ),
        (
            "use_case.metric.type",
            "uc_metric",
            "Metriktyp: duration / Dauer",
            "duration / Dauer",
            "enum",
            "duration",
        ),
        (
            "use_case.metric.direction",
            "uc_metric",
            "Optimierungsrichtung: lower / Niedriger ist besser",
            "lower / Niedriger ist besser",
            "enum",
            "lower",
        ),
        (
            "use_case.metric.baseline",
            "uc_metric",
            "Baseline: 11.0",
            "11.0",
            "decimal",
            {"value": "11.0", "unit": ""},
        ),
        (
            "use_case.metric.target",
            "uc_metric",
            "Zielwert: 8.25",
            "8.25",
            "decimal",
            {"value": "8.25", "unit": ""},
        ),
        (
            "use_case.solution_type",
            "uc_solution_context",
            "Lösungstyp: assistant / Assistenzsystem",
            "assistant / Assistenzsystem",
            "enum",
            "assistant",
        ),
        (
            "use_case.hosting_type",
            "uc_solution_context",
            "Hosting: unknown / Noch offen",
            "unknown / Noch offen",
            "enum",
            "unknown",
        ),
    ],
)
def test_diagnosed_text_labels_are_normalized_from_authoritative_target_type(
    target_field,
    source_question,
    source_excerpt,
    suggested_value,
    expected_type,
    expected_value,
):
    prepared = _prepared(source_question, source_excerpt)
    payload = _payload(
        target_field=target_field,
        source_question=source_question,
        source_excerpt=source_excerpt,
        suggested_value=suggested_value,
    )

    _document, suggestions = validate_extraction_document(payload, prepared=prepared)

    assert suggestions == (
        {
            "target_object_type": "use_case",
            "target_field": target_field,
            "target_group_key": "",
            "field_type": expected_type,
            "suggested_value": expected_value,
            "source_question": source_question,
            "source_excerpt": source_excerpt,
            "uncertainty": "low",
            "uncertainty_reason": "Explizit in der Antwort genannt.",
        },
    )


def test_enum_normalization_stays_fail_closed_for_label_only_value():
    source_excerpt = "Metriktyp: Dauer"
    prepared = _prepared("uc_metric", source_excerpt)
    payload = _payload(
        target_field="use_case.metric.type",
        source_question="uc_metric",
        source_excerpt=source_excerpt,
        suggested_value="Dauer",
    )

    with pytest.raises(ExtractionValidationError, match="Ungültiger Enumwert"):
        validate_extraction_document(payload, prepared=prepared)


def test_authoritative_text_target_rejects_non_text_raw_value():
    source_excerpt = "Titel: Benchmark"
    prepared = _prepared("uc_problem_context", source_excerpt)
    payload = _payload(
        target_field="use_case.title",
        source_question="uc_problem_context",
        source_excerpt=source_excerpt,
        suggested_value=True,
        field_type="boolean",
    )

    with pytest.raises(ExtractionValidationError, match="wird 'text' erwartet"):
        validate_extraction_document(payload, prepared=prepared)


@pytest.mark.parametrize(
    ("target_field", "source_question", "source_excerpt", "suggested_value", "expected_value"),
    [
        (
            "use_case.target_users",
            "uc_problem_context",
            "Zielgruppen: Strategischer Einkauf und anfordernder Fachbereich",
            ["Strategischer Einkauf und anfordernder Fachbereich"],
            "Strategischer Einkauf und anfordernder Fachbereich",
        ),
        (
            "use_case.source_systems",
            "uc_systems_data",
            "Quellsysteme: Shared Inbox, Dateiablage und ERP",
            ["Shared Inbox", "Dateiablage", "ERP"],
            "Shared Inbox, Dateiablage, ERP",
        ),
    ],
)
def test_text_list_is_deterministically_normalized_for_authoritative_text_target(
    target_field,
    source_question,
    source_excerpt,
    suggested_value,
    expected_value,
):
    prepared = _prepared(source_question, source_excerpt)
    payload = _payload(
        target_field=target_field,
        source_question=source_question,
        source_excerpt=source_excerpt,
        suggested_value=suggested_value,
        field_type="text_list",
    )

    _document, suggestions = validate_extraction_document(payload, prepared=prepared)

    assert suggestions[0]["field_type"] == "text"
    assert suggestions[0]["suggested_value"] == expected_value


@pytest.mark.parametrize("suggested_value", [[], ["ERP", ""], ["ERP", 1]])
def test_text_list_normalization_stays_fail_closed_for_invalid_items(suggested_value):
    source_excerpt = "Quellsysteme: ERP"
    prepared = _prepared("uc_systems_data", source_excerpt)
    payload = _payload(
        target_field="use_case.source_systems",
        source_question="uc_systems_data",
        source_excerpt=source_excerpt,
        suggested_value=suggested_value,
        field_type="text_list",
    )

    with pytest.raises(ExtractionValidationError, match=r"Textliste erwartet|Text erwartet"):
        validate_extraction_document(payload, prepared=prepared)
