from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
    UNCERTAINTY_LEVELS,
)
from .solution_generation_sources import SolutionGenerationSourceContext

ROOT_FIELDS = frozenset(("schema_version", "prompt_version", "options"))
STATEMENT_FIELD_NAMES = (
    "text",
    "source_ids",
    "assumptions",
    "open_evidence",
    "uncertainty",
)
STATEMENT_FIELDS = frozenset(STATEMENT_FIELD_NAMES)
UNCERTAINTY_FIELDS = frozenset(("level", "reason"))
DISTINCTIVE_FIELDS = (
    "description",
    "expected_value",
    "bottleneck_coverage",
    "integration_impact",
    "risks",
    "architecture_fit",
)
NUMBER_PATTERN = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?(?:\s*%)?")


class SolutionGenerationContractError(ValueError):
    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


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
        errors.append(f"{path}: Nicht-leerer Text erwartet.")
        return ""
    return value.strip()


def _string_list(value: Any, path: str, errors: list[str]) -> list[str]:
    items = _as_list(value, path, errors)
    result: list[str] = []
    for index, item in enumerate(items):
        cleaned = _nonempty_text(item, f"{path}[{index}]", errors)
        if cleaned:
            result.append(cleaned)
    return result


def _numeric_tokens(value: str) -> set[tuple[Decimal, bool]]:
    tokens: set[tuple[Decimal, bool]] = set()
    for raw in NUMBER_PATTERN.findall(value):
        compact = raw.replace(" ", "")
        is_percent = compact.endswith("%")
        numeric = compact[:-1] if is_percent else compact
        try:
            token = Decimal(numeric.replace(",", "."))
        except InvalidOperation:
            continue
        tokens.add((token, is_percent))
    return tokens


def _numeric_token_sort_key(item: tuple[Decimal, bool]) -> tuple[Decimal, bool]:
    return item[0], item[1]


def _render_numeric_token(item: tuple[Decimal, bool]) -> str:
    value, is_percent = item
    suffix = "%" if is_percent else ""
    return f"{value}{suffix}"


def _validate_numeric_claims(
    *,
    text: str,
    source_ids: list[str],
    source_values: dict[str, str],
    path: str,
    errors: list[str],
) -> None:
    generated_tokens = _numeric_tokens(text)
    if not generated_tokens:
        return

    supported_tokens: set[tuple[Decimal, bool]] = set()
    for source_id in source_ids:
        source_value = source_values.get(source_id, "")
        supported_tokens.update(_numeric_tokens(source_value))

    unsupported = generated_tokens - supported_tokens
    if not unsupported:
        return

    ordered = sorted(unsupported, key=_numeric_token_sort_key)
    rendered = ", ".join(_render_numeric_token(item) for item in ordered)
    errors.append(f"{path}: Nicht belegte quantitative Angabe: {rendered}.")


def _validate_statement(
    *,
    value: Any,
    path: str,
    available_sources: dict[str, str],
    errors: list[str],
) -> dict[str, Any]:
    statement = _as_dict(value, path, errors)
    _exact_fields(statement, STATEMENT_FIELDS, path, errors)

    text = _nonempty_text(statement.get("text"), f"{path}.text", errors)
    source_ids = _string_list(
        statement.get("source_ids"),
        f"{path}.source_ids",
        errors,
    )
    assumptions = _string_list(
        statement.get("assumptions"),
        f"{path}.assumptions",
        errors,
    )
    open_evidence = _string_list(
        statement.get("open_evidence"),
        f"{path}.open_evidence",
        errors,
    )

    if len(source_ids) != len(set(source_ids)):
        errors.append(f"{path}.source_ids: Doppelte Source-ID ist nicht zulässig.")
    for source_id in source_ids:
        if source_id not in available_sources:
            errors.append(f"{path}.source_ids: Unbekannte Source-ID {source_id}.")

    uncertainty_path = f"{path}.uncertainty"
    uncertainty = _as_dict(
        statement.get("uncertainty"),
        uncertainty_path,
        errors,
    )
    _exact_fields(
        uncertainty,
        UNCERTAINTY_FIELDS,
        uncertainty_path,
        errors,
    )
    level = _nonempty_text(
        uncertainty.get("level"),
        f"{uncertainty_path}.level",
        errors,
    )
    reason = _nonempty_text(
        uncertainty.get("reason"),
        f"{uncertainty_path}.reason",
        errors,
    )
    if level and level not in UNCERTAINTY_LEVELS:
        errors.append(
            f"{uncertainty_path}.level: Unzulässige Unsicherheitsstufe {level}.",
        )

    has_provenance = bool(source_ids or assumptions or open_evidence)
    if not has_provenance:
        message = f"{path}: Mindestens Quelle, Annahme oder offene Evidenz muss angegeben sein."
        errors.append(message)

    if text:
        _validate_numeric_claims(
            text=text,
            source_ids=source_ids,
            source_values=available_sources,
            path=f"{path}.text",
            errors=errors,
        )

    return {
        "text": text,
        "source_ids": source_ids,
        "assumptions": assumptions,
        "open_evidence": open_evidence,
        "uncertainty": {"level": level, "reason": reason},
    }


def _normalized_signature(option: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        " ".join(option[field_name]["text"].lower().split()) for field_name in DISTINCTIVE_FIELDS
    )


def validate_solution_generation_payload(
    payload: dict[str, Any],
    source_context: SolutionGenerationSourceContext,
) -> dict[str, Any]:
    errors: list[str] = []
    root = _as_dict(payload, "$", errors)
    _exact_fields(root, ROOT_FIELDS, "$", errors)

    schema_version = _nonempty_text(
        root.get("schema_version"),
        "$.schema_version",
        errors,
    )
    prompt_version = _nonempty_text(
        root.get("prompt_version"),
        "$.prompt_version",
        errors,
    )
    if schema_version and schema_version != GENERATION_SCHEMA_VERSION:
        errors.append("$.schema_version: Nicht unterstützte Schema-Version.")
    if prompt_version and prompt_version != GENERATION_PROMPT_VERSION:
        errors.append("$.prompt_version: Nicht unterstützte Prompt-Version.")

    options = _as_dict(root.get("options"), "$.options", errors)
    _exact_fields(options, frozenset(OPTION_LANES), "$.options", errors)
    available_sources = {fact.source_id: fact.value for fact in source_context.facts}
    normalized_options: dict[str, dict[str, Any]] = {}

    for lane in OPTION_LANES:
        option_path = f"$.options.{lane}"
        raw_option = _as_dict(options.get(lane), option_path, errors)
        _exact_fields(
            raw_option,
            frozenset(GENERATED_OPTION_FIELDS),
            option_path,
            errors,
        )

        normalized_option: dict[str, Any] = {}
        for field_name in GENERATED_OPTION_FIELDS:
            normalized_option[field_name] = _validate_statement(
                value=raw_option.get(field_name),
                path=f"{option_path}.{field_name}",
                available_sources=available_sources,
                errors=errors,
            )
        normalized_options[lane] = normalized_option

    names = [
        " ".join(normalized_options[lane]["name"]["text"].lower().split()) for lane in OPTION_LANES
    ]
    if all(names) and len(set(names)) != len(names):
        errors.append(
            "$.options: Die drei Lösungsentwürfe benötigen unterschiedliche Namen.",
        )

    signatures = [_normalized_signature(normalized_options[lane]) for lane in OPTION_LANES]
    signatures_complete = all(all(signature) for signature in signatures)
    signatures_unique = len(set(signatures)) == len(signatures)
    if signatures_complete and not signatures_unique:
        errors.append(
            "$.options: Mindestens zwei Lösungsentwürfe sind inhaltlich identisch.",
        )

    if errors:
        raise SolutionGenerationContractError(errors)

    return {
        "schema_version": schema_version,
        "prompt_version": prompt_version,
        "options": normalized_options,
    }
