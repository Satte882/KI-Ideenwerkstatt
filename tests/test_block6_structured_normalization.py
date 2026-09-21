from decimal import Decimal

import pytest

from ki_radar.accelerator.structured_contract import StructuredContractError
from ki_radar.accelerator.structured_normalization import (
    NormalizationStatus,
    normalize_decimal,
    normalize_enum,
    normalize_integer,
    normalize_structured_value,
)
from ki_radar.use_cases.models import UseCase


@pytest.mark.parametrize(
    ("raw", "expected", "unit"),
    [
        ("1.234,56", Decimal("1234.56"), ""),
        ("1\u202f234,56 EUR", Decimal("1234.56"), "EUR"),
        ("12,5 %", Decimal("12.5"), "%"),
        ("8,25 min", Decimal("8.25"), "min"),
        ("12.5", Decimal("12.5"), ""),
    ],
)
def test_decimal_normalization_is_deterministic(raw, expected, unit):
    result = normalize_decimal(raw)
    assert result.status == NormalizationStatus.VALID
    assert result.value == expected
    assert result.unit == unit


@pytest.mark.parametrize("raw", ["1,234", "1.234", "1,234.56", "10-12"])
def test_ambiguous_numbers_are_not_adoptable(raw):
    result = normalize_decimal(raw)
    assert result.status == NormalizationStatus.AMBIGUOUS
    assert result.adoptable is False


@pytest.mark.parametrize("raw", ["12 Mio.", "8 fortnights", "abc"])
def test_unknown_numbers_or_units_are_invalid(raw):
    result = normalize_decimal(raw)
    assert result.status == NormalizationStatus.INVALID


def test_integer_normalization_rejects_decimal_sequence():
    assert normalize_integer("3").value == 3
    assert normalize_integer("3,0").status == NormalizationStatus.INVALID


def test_enum_aliases_return_canonical_model_values():
    metric_type = normalize_enum(target_path="use_case.metric.type", value="Prozent")
    direction = normalize_enum(
        target_path="use_case.metric.direction",
        value="niedriger ist besser",
    )
    assert metric_type.value == UseCase.MetricType.PERCENT
    assert direction.value == UseCase.MetricDirection.LOWER


def test_enum_ambiguity_is_explicit():
    result = normalize_enum(
        target_path="use_case.metric.direction",
        value="höher oder niedriger",
    )
    assert result.status == NormalizationStatus.AMBIGUOUS
    assert result.adoptable is False


@pytest.mark.parametrize("field_type", ["boolean", "date", "reference"])
def test_unsupported_provider_type_remains_fail_closed(field_type):
    with pytest.raises(StructuredContractError):
        normalize_structured_value(
            target_path=f"use_case.hypothetical_{field_type}",
            provider_field_type=field_type,
            value="yes",
        )
