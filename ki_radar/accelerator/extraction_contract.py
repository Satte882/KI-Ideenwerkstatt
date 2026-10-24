from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .catalogs import CaptureCatalog, allowed_blueprint_target_paths

EXTRACTION_SCHEMA_VERSION = "1.0"
EXTRACTION_PROMPT_VERSION = "1.0"
MAX_EXTRACTION_SUGGESTIONS = 100


def extraction_prompt_version(catalog: CaptureCatalog) -> str:
    return "2.0" if catalog.version == "2.0" else EXTRACTION_PROMPT_VERSION


def current_extraction_prompt_version(catalog: CaptureCatalog) -> str:
    if catalog.capture_type == "use_case":
        return "1.1"
    return extraction_prompt_version(catalog)


ALLOWED_FIELD_TYPES = frozenset(
    {
        "text",
        "text_list",
        "integer",
        "decimal",
        "enum",
        "boolean",
        "date",
        "uuid",
        "reference",
    }
)
ALLOWED_UNCERTAINTY_LEVELS = frozenset({"low", "medium", "high"})
GROUP_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

EXTRACTION_ENUM_PATHS = {
    "value_stream.focus.business_domain": "business_domain",
    "solution_options[].option_type": "solution_option.option_type",
    "solution_options[].feasibility": "solution_option.feasibility",
    "solution_options[].integration_effort": "solution_option.integration_effort",
    "use_case.priority": "use_case.priority",
    "use_case.solution_type": "use_case.solution_type",
    "use_case.hosting_type": "use_case.hosting_type",
    "use_case.metric.type": "use_case.metric.type",
    "use_case.metric.direction": "use_case.metric.direction",
    "use_case.business_value": "level",
    "use_case.technical_feasibility": "level",
    "use_case.data_readiness": "level",
    "use_case.risk_complexity": "level",
    "use_case.classification.business_domain": "business_domain",
}
_DECIMAL_PATHS = {
    "use_case.metric.baseline",
    "use_case.metric.target",
    "use_case.one_time_cost",
    "use_case.recurring_cost",
}
_INTEGER_PATHS = {"value_stream.stages[].sequence"}


def extraction_field_type(path: str) -> str:
    if path in EXTRACTION_ENUM_PATHS:
        return "enum"
    if path in _DECIMAL_PATHS:
        return "decimal"
    if path in _INTEGER_PATHS:
        return "integer"
    return "text"


_ROOT_FIELDS = frozenset(
    {
        "schema_version",
        "prompt_version",
        "suggestions",
        "open_questions",
        "contradictions",
    }
)
_SUGGESTION_FIELDS = frozenset(
    {
        "target_object_type",
        "target_field",
        "target_group_key",
        "field_type",
        "suggested_value",
        "source_question",
        "source_excerpt",
        "uncertainty",
        "uncertainty_reason",
    }
)
_FINDING_FIELDS = frozenset({"message", "source_questions"})


class ExtractionContractError(ValueError):
    """Raised when provider output violates the versioned extraction contract."""

    def __init__(self, errors: list[str] | tuple[str, ...]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class ExtractionSuggestion:
    target_object_type: str
    target_field: str
    target_group_key: str | None
    field_type: str
    suggested_value: Any
    source_question: str
    source_excerpt: str
    uncertainty: str
    uncertainty_reason: str


@dataclass(frozen=True)
class ExtractionFinding:
    message: str
    source_questions: tuple[str, ...]


@dataclass(frozen=True)
class ExtractionDocument:
    schema_version: str
    prompt_version: str
    suggestions: tuple[ExtractionSuggestion, ...]
    open_questions: tuple[ExtractionFinding, ...]
    contradictions: tuple[ExtractionFinding, ...]


def allowed_extraction_target_paths(catalog: CaptureCatalog) -> frozenset[str]:
    blueprint_paths = allowed_blueprint_target_paths()
    return frozenset(
        path
        for question in catalog.questions
        for path in question.target_paths
        if path in blueprint_paths
    )


def target_object_type_for_path(path: str) -> str:
    prefixes = (
        ("value_stream.stages[].", "value_stream_stage"),
        ("solution_options[].", "solution_option"),
        ("value_stream.", "value_stream"),
        ("process_analysis.", "process_analysis"),
        ("use_case.", "use_case"),
    )
    for prefix, object_type in prefixes:
        if path.startswith(prefix):
            return object_type
    raise ValueError(f"Unbekannter Accelerator-Zielpfad: {path}")


def extraction_target_constraints(catalog: CaptureCatalog) -> dict[str, dict[str, Any]]:
    from ki_radar.core.scenario_blueprint_validation import load_blueprint_contract

    enums = load_blueprint_contract()["allowed_enums"]
    return {
        path: {
            "field_type": extraction_field_type(path),
            **(
                {"allowed_values": enums[EXTRACTION_ENUM_PATHS[path]]}
                if path in EXTRACTION_ENUM_PATHS
                else {}
            ),
        }
        for path in sorted(allowed_extraction_target_paths(catalog))
    }


def build_extraction_json_schema(
    catalog: CaptureCatalog, *, prompt_version: str | None = None
) -> dict[str, Any]:
    """Build the provider schema without changing stored prompt/replay contracts."""

    target_paths = sorted(allowed_extraction_target_paths(catalog))
    target_constraints = extraction_target_constraints(catalog)
    question_keys = sorted(catalog.question_map)
    target_object_types = sorted({target_object_type_for_path(path) for path in target_paths})
    finding_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["message", "source_questions"],
        "properties": {
            "message": {
                "type": "string",
                "minLength": 1,
                "description": "Konkrete offene Frage oder festgestellter Widerspruch.",
            },
            "source_questions": {
                "type": "array",
                "items": {"type": "string", "enum": question_keys},
                "description": "Betroffene Fragen aus dem eingefrorenen Katalog.",
            },
        },
    }
    suggestion_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "target_object_type",
            "target_field",
            "target_group_key",
            "field_type",
            "suggested_value",
            "source_question",
            "source_excerpt",
            "uncertainty",
            "uncertainty_reason",
        ],
        "properties": {
            "target_object_type": {
                "type": "string",
                "enum": target_object_types,
                "description": "Aus dem Zielpfad abgeleiteter Objekt-Typ.",
            },
            "target_field": {
                "type": "string",
                "enum": target_paths,
                "description": "Zulässiger Zielpfad aus dem eingefrorenen Katalog.",
            },
            "target_group_key": {
                "anyOf": [
                    {
                        "type": "string",
                        "minLength": 1,
                        "pattern": GROUP_KEY_PATTERN.pattern,
                    },
                    {"type": "null"},
                ],
                "description": "Lokaler Gruppenschlüssel für wiederholbare Ziele, sonst null.",
            },
            "field_type": {
                "type": "string",
                "enum": sorted(ALLOWED_FIELD_TYPES),
            },
            "suggested_value": {
                "anyOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "integer"},
                    {"type": "boolean"},
                    {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1},
                    },
                ],
                "description": (
                    "Nur belegte konkrete Werte vorschlagen. Unbekannte Angaben nicht als "
                    "'unbekannt', 'offen' oder andere Fülltexte in Zielfelder schreiben, "
                    "sondern als open_questions führen. Keine Baseline, Zielwerte, Kosten "
                    "oder Bewertungen ergänzen, wenn diese nicht belegt sind. "
                    "Enumwerte ausschließlich als aufgeführte interne Codes ausgeben, "
                    "keine übersetzten Bezeichnungen. Dezimalwerte bleiben Strings. "
                    "Verbindliche Zielfeldtypen und zulässige Codes:\n"
                    + json.dumps(target_constraints, ensure_ascii=False, separators=(",", ":"))
                ),
            },
            "source_question": {
                "type": "string",
                "enum": question_keys,
            },
            "source_excerpt": {
                "type": "string",
                "minLength": 1,
                "description": "Wörtlicher Ausschnitt aus der Nutzerantwort.",
            },
            "uncertainty": {
                "type": "string",
                "enum": sorted(ALLOWED_UNCERTAINTY_LEVELS),
            },
            "uncertainty_reason": {"type": "string", "minLength": 1},
        },
    }
    if not any("[]" in path for path in target_paths):
        # Match the existing parser contract for captures with only singleton targets.
        suggestion_schema["properties"]["target_group_key"] = {
            "type": "null",
            "description": "Ohne wiederholbare Ziele muss der Gruppenschlüssel null sein.",
        }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "description": (
            "Vorhandene konkrete Angaben vollständig extrahieren; nicht jedes Zielfeld "
            "befüllen. Fehlende Fakten bleiben offene Fragen. Leere Vorschläge sind nur "
            "sinnvoll, wenn keine konkreten Angaben belegt sind."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "prompt_version",
            "suggestions",
            "open_questions",
            "contradictions",
        ],
        "properties": {
            "schema_version": {
                "type": "string",
                "const": EXTRACTION_SCHEMA_VERSION,
            },
            "prompt_version": {
                "type": "string",
                "const": prompt_version or extraction_prompt_version(catalog),
            },
            "suggestions": {
                "type": "array",
                "maxItems": MAX_EXTRACTION_SUGGESTIONS,
                "items": suggestion_schema,
            },
            "open_questions": {"type": "array", "items": finding_schema},
            "contradictions": {"type": "array", "items": finding_schema},
        },
    }


def _exact_fields(
    value: dict[str, Any],
    allowed: frozenset[str],
    path: str,
    errors: list[str],
) -> None:
    unknown = sorted(set(value) - allowed)
    missing = sorted(allowed - set(value))
    if unknown:
        errors.append(f"{path}: Unbekannte Felder: {', '.join(unknown)}.")
    if missing:
        errors.append(f"{path}: Pflichtfelder fehlen: {', '.join(missing)}.")


def _as_dict(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{path}: JSON-Objekt erwartet.")
    return {}


def _as_list(value: Any, path: str, errors: list[str]) -> list[Any]:
    if isinstance(value, list):
        return value
    errors.append(f"{path}: JSON-Liste erwartet.")
    return []


def _nonempty_text(value: Any, path: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: Nichtleerer Text erwartet.")
        return ""
    return value.strip()


def _validate_suggested_value(field_type: str, value: Any, path: str, errors: list[str]) -> None:
    if field_type in {"text", "decimal", "enum", "date", "uuid", "reference"}:
        _nonempty_text(value, path, errors)
        return
    if field_type == "text_list":
        values = _as_list(value, path, errors)
        if not values:
            errors.append(f"{path}: Nichtleere Textliste erwartet.")
        for index, item in enumerate(values):
            _nonempty_text(item, f"{path}[{index}]", errors)
        return
    if field_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{path}: Ganze Zahl erwartet.")
        return
    if field_type == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{path}: Boolean erwartet.")
        return
    if field_type:
        errors.append(f"{path}: Unbekannter Feldtyp {field_type!r}.")


def _parse_finding_list(
    raw: Any,
    *,
    path: str,
    question_keys: frozenset[str],
    errors: list[str],
) -> tuple[ExtractionFinding, ...]:
    findings: list[ExtractionFinding] = []
    for index, item in enumerate(_as_list(raw, path, errors)):
        item_path = f"{path}[{index}]"
        before = len(errors)
        finding = _as_dict(item, item_path, errors)
        _exact_fields(finding, _FINDING_FIELDS, item_path, errors)
        message = _nonempty_text(finding.get("message"), f"{item_path}.message", errors)
        sources = _as_list(finding.get("source_questions"), f"{item_path}.source_questions", errors)
        normalized_sources: list[str] = []
        for source_index, source in enumerate(sources):
            source_path = f"{item_path}.source_questions[{source_index}]"
            source_key = _nonempty_text(source, source_path, errors)
            if source_key and source_key not in question_keys:
                errors.append(f"{source_path}: Unbekannte Quellfrage {source_key!r}.")
            elif source_key:
                normalized_sources.append(source_key)
        if len(errors) == before:
            findings.append(
                ExtractionFinding(
                    message=message,
                    source_questions=tuple(normalized_sources),
                )
            )
    return tuple(findings)


def parse_extraction_document(
    payload: Any,
    *,
    catalog: CaptureCatalog,
    expected_schema_version: str = EXTRACTION_SCHEMA_VERSION,
    expected_prompt_version: str | None = None,
) -> ExtractionDocument:
    expected_prompt_version = expected_prompt_version or extraction_prompt_version(catalog)
    errors: list[str] = []
    root = _as_dict(payload, "root", errors)
    _exact_fields(root, _ROOT_FIELDS, "root", errors)

    schema_version = _nonempty_text(root.get("schema_version"), "schema_version", errors)
    prompt_version = _nonempty_text(root.get("prompt_version"), "prompt_version", errors)
    if schema_version and schema_version != expected_schema_version:
        errors.append(
            f"schema_version: Erwartet wird Version {expected_schema_version}, "
            f"erhalten wurde {schema_version}."
        )
    if prompt_version and prompt_version != expected_prompt_version:
        errors.append(
            f"prompt_version: Erwartet wird Version {expected_prompt_version}, "
            f"erhalten wurde {prompt_version}."
        )

    question_map = catalog.question_map
    question_keys = frozenset(question_map)
    allowed_paths = allowed_extraction_target_paths(catalog)
    suggestions: list[ExtractionSuggestion] = []
    raw_suggestions = _as_list(root.get("suggestions"), "suggestions", errors)
    if len(raw_suggestions) > MAX_EXTRACTION_SUGGESTIONS:
        errors.append(
            f"suggestions: Höchstens {MAX_EXTRACTION_SUGGESTIONS} Vorschläge pro Analyse erlaubt."
        )
    for index, item in enumerate(raw_suggestions):
        path = f"suggestions[{index}]"
        before = len(errors)
        suggestion = _as_dict(item, path, errors)
        _exact_fields(suggestion, _SUGGESTION_FIELDS, path, errors)

        target_field = _nonempty_text(
            suggestion.get("target_field"), f"{path}.target_field", errors
        )
        target_object_type = _nonempty_text(
            suggestion.get("target_object_type"),
            f"{path}.target_object_type",
            errors,
        )
        source_question = _nonempty_text(
            suggestion.get("source_question"),
            f"{path}.source_question",
            errors,
        )
        question = question_map.get(source_question)
        if source_question and question is None:
            errors.append(f"{path}.source_question: Unbekannte Quellfrage {source_question!r}.")
        if target_field and target_field not in allowed_paths:
            errors.append(f"{path}.target_field: Unzulässiger Zielpfad {target_field!r}.")
        if question is not None and target_field not in question.target_paths:
            errors.append(
                f"{path}.target_field: Zielpfad {target_field!r} ist für "
                f"Quellfrage {source_question!r} nicht zulässig."
            )
        if target_field in allowed_paths:
            expected_object_type = target_object_type_for_path(target_field)
            if target_object_type != expected_object_type:
                errors.append(
                    f"{path}.target_object_type: Für {target_field!r} wird "
                    f"{expected_object_type!r} erwartet."
                )

        raw_group_key = suggestion.get("target_group_key")
        group_key: str | None = None
        repeated_target = target_field.startswith(("value_stream.stages[].", "solution_options[]."))
        if repeated_target:
            group_key = _nonempty_text(raw_group_key, f"{path}.target_group_key", errors)
            if group_key and GROUP_KEY_PATTERN.fullmatch(group_key) is None:
                errors.append(f"{path}.target_group_key: Ungültiger lokaler Gruppenschlüssel.")
        elif raw_group_key is not None:
            errors.append(f"{path}.target_group_key: Für diesen Zielpfad muss der Wert null sein.")

        field_type = _nonempty_text(suggestion.get("field_type"), f"{path}.field_type", errors)
        if field_type and field_type not in ALLOWED_FIELD_TYPES:
            errors.append(f"{path}.field_type: Unbekannter Feldtyp {field_type!r}.")
        else:
            _validate_suggested_value(
                field_type,
                suggestion.get("suggested_value"),
                f"{path}.suggested_value",
                errors,
            )

        source_excerpt = _nonempty_text(
            suggestion.get("source_excerpt"), f"{path}.source_excerpt", errors
        )
        uncertainty = _nonempty_text(suggestion.get("uncertainty"), f"{path}.uncertainty", errors)
        if uncertainty and uncertainty not in ALLOWED_UNCERTAINTY_LEVELS:
            errors.append(f"{path}.uncertainty: Unbekannte Unsicherheitsstufe {uncertainty!r}.")
        uncertainty_reason = _nonempty_text(
            suggestion.get("uncertainty_reason"),
            f"{path}.uncertainty_reason",
            errors,
        )

        if len(errors) == before:
            suggestions.append(
                ExtractionSuggestion(
                    target_object_type=target_object_type,
                    target_field=target_field,
                    target_group_key=group_key,
                    field_type=field_type,
                    suggested_value=suggestion["suggested_value"],
                    source_question=source_question,
                    source_excerpt=source_excerpt,
                    uncertainty=uncertainty,
                    uncertainty_reason=uncertainty_reason,
                )
            )

    open_questions = _parse_finding_list(
        root.get("open_questions"),
        path="open_questions",
        question_keys=question_keys,
        errors=errors,
    )
    contradictions = _parse_finding_list(
        root.get("contradictions"),
        path="contradictions",
        question_keys=question_keys,
        errors=errors,
    )

    if errors:
        raise ExtractionContractError(errors)
    return ExtractionDocument(
        schema_version=schema_version,
        prompt_version=prompt_version,
        suggestions=tuple(suggestions),
        open_questions=open_questions,
        contradictions=contradictions,
    )
