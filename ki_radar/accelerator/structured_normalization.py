from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from ki_radar.use_cases.models import UseCase

from .structured_contract import StructuredContractError, structured_field_spec


class NormalizationStatus(StrEnum):
    VALID = "valid"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"


@dataclass(frozen=True)
class NormalizedValue:
    status: NormalizationStatus
    value: Any = None
    unit: str = ""
    error_code: str = ""

    @property
    def adoptable(self) -> bool:
        return self.status == NormalizationStatus.VALID


UNIT_ALIASES = {
    "%": "%",
    "prozent": "%",
    "min": "min",
    "minute": "min",
    "minuten": "min",
    "h": "h",
    "std": "h",
    "stunde": "h",
    "stunden": "h",
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",
    "anzahl": "count",
    "fall": "count",
    "fälle": "count",
    "faelle": "count",
    "stück": "count",
    "stueck": "count",
}

ENUM_ALIASES = {
    "use_case.metric.type": {
        UseCase.MetricType.NUMBER: {"number", "zahl", "wert"},
        UseCase.MetricType.PERCENT: {"percent", "prozent", "%"},
        UseCase.MetricType.DURATION: {"duration", "dauer", "zeit"},
        UseCase.MetricType.CURRENCY: {
            "currency",
            "geldbetrag",
            "geld",
            "eur",
            "euro",
        },
        UseCase.MetricType.COUNT: {
            "count",
            "anzahl",
            "fälle",
            "faelle",
            "stück",
            "stueck",
        },
        UseCase.MetricType.RATING: {
            "rating",
            "bewertung",
            "skala",
            "bewertungsskala",
        },
    },
    "use_case.metric.direction": {
        UseCase.MetricDirection.LOWER: {
            "lower",
            "niedriger",
            "niedriger ist besser",
            "senken",
            "reduzieren",
        },
        UseCase.MetricDirection.HIGHER: {
            "higher",
            "höher",
            "hoeher",
            "höher ist besser",
            "hoeher ist besser",
            "steigern",
            "erhöhen",
            "erhoehen",
        },
    },
}

_SPACE_PATTERN = re.compile(r"[\s\u00a0\u202f]+")
_RANGE_PATTERN = re.compile(r"\d\s*(?:-|\u2013|\u2014|bis)\s*\d", re.IGNORECASE)
_UNIT_PATTERN = re.compile(r"^(?P<number>.+?)(?:\s*)(?P<unit>%|€|[A-Za-zÄÖÜäöüß]+)$")
_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")
_GERMAN_GROUPED_DECIMAL = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})+,\d+$")
_CANONICAL_DECIMAL = re.compile(r"^[+-]?\d+[.,]\d+$")


def _normalize_text(value: Any) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip()


def _normalize_alias(value: str) -> str:
    return _SPACE_PATTERN.sub(" ", _normalize_text(value).casefold())


def _extract_number_and_unit(value: Any) -> tuple[str, str] | NormalizedValue:
    text = _normalize_text(value)
    if not text:
        return NormalizedValue(NormalizationStatus.INVALID, error_code="empty_value")
    if _RANGE_PATTERN.search(text):
        return NormalizedValue(NormalizationStatus.AMBIGUOUS, error_code="numeric_range")

    match = _UNIT_PATTERN.fullmatch(text)
    if match is None:
        if re.search(r"[A-Za-zÄÖÜäöüß€%]", text):
            return NormalizedValue(NormalizationStatus.INVALID, error_code="unknown_unit")
        return text, ""

    unit_alias = _normalize_alias(match.group("unit"))
    unit = UNIT_ALIASES.get(unit_alias)
    if unit is None:
        return NormalizedValue(NormalizationStatus.INVALID, error_code="unknown_unit")
    return match.group("number").strip(), unit


def normalize_decimal(value: Any) -> NormalizedValue:
    extracted = _extract_number_and_unit(value)
    if isinstance(extracted, NormalizedValue):
        return extracted
    number_text, unit = extracted
    compact = _SPACE_PATTERN.sub("", number_text)

    if "," in compact and "." in compact:
        if not _GERMAN_GROUPED_DECIMAL.fullmatch(compact):
            return NormalizedValue(
                NormalizationStatus.AMBIGUOUS,
                unit=unit,
                error_code="mixed_separators",
            )
        canonical = compact.replace(".", "").replace(",", ".")
    elif _INTEGER_PATTERN.fullmatch(compact):
        canonical = compact
    elif _CANONICAL_DECIMAL.fullmatch(compact):
        separator = "," if "," in compact else "."
        whole, fraction = compact.rsplit(separator, 1)
        if len(fraction) == 3 and len(whole.lstrip("+-")) <= 3:
            return NormalizedValue(
                NormalizationStatus.AMBIGUOUS,
                unit=unit,
                error_code="three_digit_separator",
            )
        canonical = f"{whole}.{fraction}"
    else:
        return NormalizedValue(
            NormalizationStatus.INVALID,
            unit=unit,
            error_code="invalid_decimal",
        )

    try:
        normalized = Decimal(canonical)
    except InvalidOperation:
        return NormalizedValue(
            NormalizationStatus.INVALID,
            unit=unit,
            error_code="invalid_decimal",
        )
    return NormalizedValue(NormalizationStatus.VALID, value=normalized, unit=unit)


def normalize_integer(value: Any) -> NormalizedValue:
    text = _SPACE_PATTERN.sub("", _normalize_text(value))
    if not _INTEGER_PATTERN.fullmatch(text):
        return NormalizedValue(NormalizationStatus.INVALID, error_code="invalid_integer")
    return NormalizedValue(NormalizationStatus.VALID, value=int(text))


def normalize_enum(*, target_path: str, value: Any) -> NormalizedValue:
    aliases = ENUM_ALIASES.get(target_path)
    if aliases is None:
        return NormalizedValue(NormalizationStatus.INVALID, error_code="unsupported_enum")

    text = _normalize_alias(value)
    if not text:
        return NormalizedValue(NormalizationStatus.INVALID, error_code="empty_value")
    parts = [part.strip() for part in re.split(r"\s+(?:oder|or)\s+|[/|]", text) if part.strip()]
    matches = {
        canonical for part in parts for canonical, accepted in aliases.items() if part in accepted
    }
    if len(matches) > 1:
        return NormalizedValue(NormalizationStatus.AMBIGUOUS, error_code="ambiguous_enum")
    if not matches:
        return NormalizedValue(NormalizationStatus.INVALID, error_code="unknown_enum")
    return NormalizedValue(NormalizationStatus.VALID, value=matches.pop())


def normalize_structured_value(
    *,
    target_path: str,
    provider_field_type: str,
    value: Any,
) -> NormalizedValue:
    spec = structured_field_spec(
        target_path=target_path,
        provider_field_type=provider_field_type,
    )
    if spec.field_type.value == "decimal":
        return normalize_decimal(value)
    if spec.field_type.value == "integer":
        return normalize_integer(value)
    if spec.field_type.value == "enum":
        return normalize_enum(target_path=target_path, value=value)
    if spec.field_type.value == "text":
        text = _normalize_text(value)
        if not text:
            return NormalizedValue(NormalizationStatus.INVALID, error_code="empty_value")
        return NormalizedValue(NormalizationStatus.VALID, value=text)
    raise StructuredContractError("Der strukturierte Feldtyp wird nicht unterstützt.")
