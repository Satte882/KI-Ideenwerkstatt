from __future__ import annotations

import re
from dataclasses import asdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from ki_radar.core.scenario_blueprint_validation import load_blueprint_contract

from .adoption_policy import field_adoption_enabled
from .analysis_service import (
    CaptureAnalysisError,
    CaptureProviderPayload,
    PreparedCaptureAnalysis,
    log_capture_analysis,
    mark_capture_analysis_failed,
    prepare_capture_analysis,
    request_capture_provider,
)
from .candidate_snapshot import CandidateSnapshotError, create_adoption_candidates
from .extraction_contract import (
    ExtractionContractError,
    ExtractionDocument,
    ExtractionSuggestion,
    parse_extraction_document,
)
from .models import CaptureAnalysis, CaptureFieldSuggestion

_WHITESPACE = re.compile(r"\s+")
_DECIMAL = re.compile(
    r"^\s*([+-]?(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?))"
    r"\s*([%€A-Za-zÄÖÜäöüß/²³-]*)\s*$"
)
_GENERIC_VALUES = {
    "unbekannt",
    "nicht bekannt",
    "noch offen",
    "offen",
    "keine angabe",
    "n/a",
    "tbd",
    "konkretisieren",
}
_ALLOWED_UNITS = {
    "": "",
    "%": "%",
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",
    "s": "s",
    "sek": "s",
    "sekunde": "s",
    "sekunden": "s",
    "min": "min",
    "minute": "min",
    "minuten": "min",
    "h": "h",
    "std": "h",
    "stunde": "h",
    "stunden": "h",
    "tag": "d",
    "tage": "d",
    "d": "d",
    "stück": "count",
    "stueck": "count",
    "anzahl": "count",
    "count": "count",
}
_ENUM_PATHS = {
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
_TEXT_LIST_NORMALIZATION_TARGETS = frozenset(
    {
        "use_case.benefit_category",
        "use_case.data_sources",
        "use_case.intended_users",
        "use_case.source_systems",
        "use_case.target_users",
    }
)


class ExtractionValidationError(ValueError):
    def __init__(self, errors: list[str] | tuple[str, ...]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def _normalized_text(value: object) -> str:
    return _WHITESPACE.sub(" ", str(value or "").strip()).casefold()


def _expected_field_type(path: str) -> str:
    if path in _ENUM_PATHS:
        return "enum"
    if path in _DECIMAL_PATHS:
        return "decimal"
    if path in _INTEGER_PATHS:
        return "integer"
    return "text"


def _normalize_decimal(raw: object, path: str, errors: list[str]) -> dict[str, str] | None:
    if not isinstance(raw, str):
        errors.append(f"{path}: Dezimalzahl muss als Text mit optionaler Einheit vorliegen.")
        return None
    match = _DECIMAL.fullmatch(raw)
    if match is None:
        errors.append(f"{path}: Deutsche Dezimalzahl oder eindeutige Einheit erwartet.")
        return None
    number, raw_unit = match.groups()
    if "." in number and "," in number:
        normalized_number = number.replace(".", "").replace(",", ".")
    elif "," in number:
        normalized_number = number.replace(",", ".")
    elif number.count(".") > 1 or ("." in number and len(number.rsplit(".", 1)[1]) == 3):
        normalized_number = number.replace(".", "")
    else:
        normalized_number = number
    try:
        decimal = Decimal(normalized_number)
    except InvalidOperation:
        errors.append(f"{path}: Ungültige Dezimalzahl.")
        return None
    unit_key = raw_unit.casefold()
    if unit_key not in _ALLOWED_UNITS:
        errors.append(f"{path}: Unbekannte oder mehrdeutige Einheit {raw_unit!r}.")
        return None
    value = format(decimal, "f")
    return {"value": value, "unit": _ALLOWED_UNITS[unit_key]}


def _normalize_enum(
    raw: object,
    *,
    allowed: list[str],
    target_field: str,
    path: str,
    errors: list[str],
) -> str | None:
    if not isinstance(raw, str):
        errors.append(f"{path}: Enumwert muss als Text vorliegen.")
        return None
    value = raw.strip()
    if value in allowed:
        return value
    code, separator, label = value.partition(" / ")
    canonical = code.strip()
    if separator and canonical in allowed and label.strip():
        return canonical
    errors.append(f"{path}: Ungültiger Enumwert {raw!r} für {target_field}.")
    return None


def _value_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    if isinstance(value, dict):
        return " ".join(str(item) for item in value.values())
    return str(value)


def _is_degenerate(suggestion: ExtractionSuggestion, question) -> bool:
    value = _normalized_text(_value_text(suggestion.suggested_value))
    if not value or value in _GENERIC_VALUES:
        return True
    candidates = {
        _normalized_text(question.label),
        _normalized_text(question.help_text),
        _normalized_text(suggestion.target_field),
        _normalized_text(suggestion.target_field.rsplit(".", 1)[-1]),
    }
    return value in candidates


def _normalize_value(
    suggestion: ExtractionSuggestion,
    *,
    contract: dict[str, Any],
    path: str,
    errors: list[str],
) -> Any:
    expected = _expected_field_type(suggestion.target_field)
    if suggestion.field_type != expected:
        recoverable_text_underclassification = suggestion.field_type == "text" and expected in {
            "enum",
            "decimal",
            "integer",
        }
        recoverable_text_list = (
            suggestion.field_type == "text_list"
            and expected == "text"
            and suggestion.target_field in _TEXT_LIST_NORMALIZATION_TARGETS
        )
        if not recoverable_text_underclassification and not recoverable_text_list:
            errors.append(
                f"{path}.field_type: Für {suggestion.target_field!r} wird {expected!r} erwartet."
            )
            return None
    value = suggestion.suggested_value
    if expected == "text":
        if isinstance(value, str):
            return value.strip()
        if (
            suggestion.field_type == "text_list"
            and suggestion.target_field in _TEXT_LIST_NORMALIZATION_TARGETS
            and isinstance(value, list)
        ):
            items = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            if len(items) == len(value) and items:
                return ", ".join(items)
        errors.append(f"{path}.suggested_value: Text oder nicht-leere Textliste erwartet.")
        return None
    if expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            errors.append(f"{path}.suggested_value: Positive Ganzzahl erwartet.")
            return None
        return value
    if expected == "decimal":
        return _normalize_decimal(value, f"{path}.suggested_value", errors)
    if expected == "enum":
        allowed = contract["allowed_enums"][_ENUM_PATHS[suggestion.target_field]]
        return _normalize_enum(
            value,
            allowed=allowed,
            target_field=suggestion.target_field,
            path=f"{path}.suggested_value",
            errors=errors,
        )
    if expected == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{path}.suggested_value: Boolean erwartet.")
            return None
        return value
    if expected == "date":
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError:
            errors.append(f"{path}.suggested_value: ISO-Datum erwartet.")
            return None
    if expected == "uuid":
        try:
            return str(UUID(str(value)))
        except ValueError:
            errors.append(f"{path}.suggested_value: UUID erwartet.")
            return None
    return str(value).strip()


def validate_extraction_document(
    payload: Any,
    *,
    prepared: PreparedCaptureAnalysis,
) -> tuple[ExtractionDocument, tuple[dict[str, Any], ...]]:
    try:
        document = parse_extraction_document(payload, catalog=prepared.catalog)
    except ExtractionContractError as exc:
        raise ExtractionValidationError(exc.errors) from exc

    errors: list[str] = []
    normalized_suggestions: list[dict[str, Any]] = []
    seen_targets: set[tuple[str, str]] = set()
    contract = load_blueprint_contract()
    question_map = prepared.catalog.question_map
    for index, suggestion in enumerate(document.suggestions):
        path = f"suggestions[{index}]"
        question = question_map[suggestion.source_question]
        answer = prepared.answers.get(suggestion.source_question, "")
        normalized_excerpt = _normalized_text(suggestion.source_excerpt)
        if not normalized_excerpt or normalized_excerpt not in _normalized_text(answer):
            errors.append(
                f"{path}.source_excerpt: Ausschnitt ist in der Quellantwort nicht belegt."
            )
        if _is_degenerate(suggestion, question):
            errors.append(
                f"{path}.suggested_value: Vorschlag wiederholt nur Frage, Hilfetext, "
                "Zielfeld oder eine Leerformel."
            )
        if suggestion.target_group_key:
            excerpt_tokens = set(slugify(suggestion.source_excerpt).split("-"))
            group_tokens = {
                token for token in suggestion.target_group_key.split("-") if len(token) >= 3
            }
            if not group_tokens or not group_tokens.issubset(excerpt_tokens):
                errors.append(
                    f"{path}.target_group_key: Gruppe ist im Quellausschnitt nicht belegt."
                )
        target_key = (suggestion.target_field, suggestion.target_group_key or "")
        if target_key in seen_targets:
            errors.append(f"{path}: Zielpfad und Gruppe sind im Lauf mehrfach vorhanden.")
        seen_targets.add(target_key)
        normalized_value = _normalize_value(
            suggestion,
            contract=contract,
            path=path,
            errors=errors,
        )
        normalized_suggestions.append(
            {
                "target_object_type": suggestion.target_object_type,
                "target_field": suggestion.target_field,
                "target_group_key": suggestion.target_group_key or "",
                "field_type": _expected_field_type(suggestion.target_field),
                "suggested_value": normalized_value,
                "source_question": suggestion.source_question,
                "source_excerpt": suggestion.source_excerpt,
                "uncertainty": suggestion.uncertainty,
                "uncertainty_reason": suggestion.uncertainty_reason,
            }
        )
    if errors:
        raise ExtractionValidationError(errors)
    return document, tuple(normalized_suggestions)


def _usage_value(usage: dict[str, object], key: str) -> int | None:
    value = usage.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _usage_cost(usage: dict[str, object]) -> Decimal | None:
    value = usage.get("cost")
    if value in {None, ""}:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


@transaction.atomic
def store_validated_extraction(
    *,
    prepared: PreparedCaptureAnalysis,
    provider: CaptureProviderPayload,
    document: ExtractionDocument,
    suggestions: tuple[dict[str, Any], ...],
) -> CaptureAnalysis:
    analysis = CaptureAnalysis.objects.select_for_update().get(pk=prepared.analysis.pk)
    if analysis.status != CaptureAnalysis.Status.RUNNING:
        raise CaptureAnalysisError(
            "Der Analyselauf ist nicht mehr offen.",
            code="analysis_not_running",
        )
    CaptureFieldSuggestion.objects.bulk_create(
        [CaptureFieldSuggestion(analysis=analysis, **suggestion) for suggestion in suggestions]
    )
    finished_at = timezone.now()
    analysis.status = CaptureAnalysis.Status.SUCCESS
    analysis.finished_at = finished_at
    analysis.duration_ms = max(
        0,
        round((finished_at - analysis.started_at).total_seconds() * 1000),
    )
    analysis.model_name = provider.result.model
    analysis.output_chars = provider.result.output_chars
    analysis.prompt_tokens = _usage_value(provider.result.usage, "prompt_tokens")
    analysis.completion_tokens = _usage_value(provider.result.usage, "completion_tokens")
    analysis.total_tokens = _usage_value(provider.result.usage, "total_tokens")
    analysis.cost = _usage_cost(provider.result.usage)
    analysis.open_questions = [asdict(finding) for finding in document.open_questions]
    analysis.contradictions = [asdict(finding) for finding in document.contradictions]
    analysis.error_code = ""
    analysis.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "model_name",
            "output_chars",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost",
            "open_questions",
            "contradictions",
            "error_code",
            "updated_at",
        ]
    )
    if field_adoption_enabled() and analysis.session.target_object is not None:
        create_adoption_candidates(analysis_id=analysis.pk)
    log_capture_analysis(analysis)
    return analysis


def execute_capture_analysis(*, actor, session_id) -> CaptureAnalysis:
    prepared = prepare_capture_analysis(actor=actor, session_id=session_id)
    provider = request_capture_provider(prepared)
    try:
        document, suggestions = validate_extraction_document(
            provider.payload,
            prepared=prepared,
        )
    except ExtractionValidationError as exc:
        mark_capture_analysis_failed(
            analysis_id=prepared.analysis.pk,
            error_code="invalid_extraction",
            result=provider.result,
        )
        raise CaptureAnalysisError(
            "Die Providerantwort hat die Extraktionsprüfung nicht bestanden.",
            code="invalid_extraction",
        ) from exc
    try:
        return store_validated_extraction(
            prepared=prepared,
            provider=provider,
            document=document,
            suggestions=suggestions,
        )
    except CandidateSnapshotError as exc:
        mark_capture_analysis_failed(
            analysis_id=prepared.analysis.pk,
            error_code="candidate_snapshot_failed",
            result=provider.result,
        )
        raise CaptureAnalysisError(
            "Die validierten Vorschläge konnten nicht für die Feldprüfung vorbereitet werden.",
            code="candidate_snapshot_failed",
        ) from exc
