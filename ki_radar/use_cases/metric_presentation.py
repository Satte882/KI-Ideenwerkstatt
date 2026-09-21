from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

METRIC_NUMBER = "number"
METRIC_PERCENT = "percent"
METRIC_DURATION = "duration"
METRIC_CURRENCY = "currency"
METRIC_COUNT = "count"
METRIC_RATING = "rating"
MISSING_VALUE = "\N{EN DASH}"

KNOWN_METRIC_TYPES = frozenset(
    {
        METRIC_NUMBER,
        METRIC_PERCENT,
        METRIC_DURATION,
        METRIC_CURRENCY,
        METRIC_COUNT,
        METRIC_RATING,
    }
)


class MetricSource(Protocol):
    metric_type: str | None
    metric_unit: str
    metric_baseline: Decimal | None
    metric_target: Decimal | None
    metric_actual: Decimal | None


@dataclass(frozen=True, slots=True)
class MetricPresentation:
    formatted_value: str
    unit: str
    display: str
    metric_type: str | None
    is_missing: bool
    uses_fallback: bool


@dataclass(frozen=True, slots=True)
class MetricSetPresentation:
    baseline: MetricPresentation
    target: MetricPresentation
    actual: MetricPresentation


def _decimal_parts(value: Decimal) -> tuple[str, str]:
    text = format(value, "f")
    integer, separator, fraction = text.partition(".")
    return integer, fraction if separator else ""


def _group_integer(value: str) -> str:
    sign = ""
    digits = value
    if digits.startswith("-"):
        sign, digits = "-", digits[1:]
    groups = []
    while digits:
        groups.append(digits[-3:])
        digits = digits[:-3]
    return sign + ".".join(reversed(groups or ["0"]))


def _localize_decimal(
    value: Decimal,
    *,
    min_places: int = 0,
    max_places: int | None = None,
) -> str:
    displayed = value
    if max_places is not None:
        quantum = Decimal(1).scaleb(-max_places)
        displayed = value.quantize(quantum, rounding=ROUND_HALF_UP)

    integer, fraction = _decimal_parts(displayed)
    fraction = fraction.rstrip("0")
    if len(fraction) < min_places:
        fraction = fraction.ljust(min_places, "0")
    return f"{integer},{fraction}" if fraction else integer


def format_generic_decimal(value: Decimal) -> str:
    """Localize a Decimal without changing its numerical value."""

    return _localize_decimal(value)


def format_measurement_decimal(value: Decimal) -> str:
    """Format duration and percentage values with one or two decimal places."""

    return _localize_decimal(value, min_places=1, max_places=2)


def format_currency_decimal(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    integer, fraction = _decimal_parts(rounded)
    return f"{_group_integer(integer)},{fraction.ljust(2, '0')}"


def format_count_decimal(value: Decimal) -> str:
    """Remove representational zeroes but never quantize or round counts."""

    return format_generic_decimal(value)


def format_metric_value(value: Decimal | None, metric_type: str | None) -> str:
    if value is None:
        return MISSING_VALUE
    if metric_type == METRIC_CURRENCY:
        return format_currency_decimal(value)
    if metric_type == METRIC_COUNT:
        return format_count_decimal(value)
    if metric_type in {METRIC_PERCENT, METRIC_DURATION}:
        return format_measurement_decimal(value)
    return format_generic_decimal(value)


def _display_unit(metric_type: str | None, unit: str) -> str:
    normalized = unit.strip()
    if normalized:
        return normalized
    if metric_type == METRIC_PERCENT:
        return "%"
    if metric_type == METRIC_CURRENCY:
        return "€"
    return ""


def build_metric_presentation(
    *,
    metric_type: str | None,
    value: Decimal | None,
    unit: str = "",
) -> MetricPresentation:
    formatted_value = format_metric_value(value, metric_type)
    display_unit = _display_unit(metric_type, unit)
    is_missing = value is None
    return MetricPresentation(
        formatted_value=formatted_value,
        unit=display_unit,
        display=(
            formatted_value
            if is_missing or not display_unit
            else f"{formatted_value} {display_unit}"
        ),
        metric_type=metric_type,
        is_missing=is_missing,
        uses_fallback=metric_type not in KNOWN_METRIC_TYPES,
    )


def build_metric_set_presentation(source: MetricSource) -> MetricSetPresentation:
    kwargs = {
        "metric_type": source.metric_type,
        "unit": source.metric_unit,
    }
    return MetricSetPresentation(
        baseline=build_metric_presentation(value=source.metric_baseline, **kwargs),
        target=build_metric_presentation(value=source.metric_target, **kwargs),
        actual=build_metric_presentation(value=source.metric_actual, **kwargs),
    )
