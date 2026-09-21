from decimal import Decimal
from pathlib import Path

import pytest

from ki_radar.core.scenario_blueprint import (
    BlueprintCanonicalizationError,
    blueprint_checksum,
    canonical_json_text,
    load_blueprint_json,
)


def test_canonical_checksum_ignores_object_order_and_decimal_format(
    tmp_path: Path,
):
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text(
        '{"b":11.0,"a":{"x":1,"y":true}}',
        encoding="utf-8",
    )
    second_path.write_text(
        '{\n  "a": {"y": true, "x": 1},\n  "b": 11.00\n}',
        encoding="utf-8",
    )

    first = load_blueprint_json(first_path)
    second = load_blueprint_json(second_path)

    assert canonical_json_text(first) == '{"a":{"x":1,"y":true},"b":11}'
    assert blueprint_checksum(first) == blueprint_checksum(second)


def test_canonical_checksum_preserves_array_order():
    assert blueprint_checksum({"items": [1, 2]}) != blueprint_checksum(
        {"items": [2, 1]},
    )


@pytest.mark.parametrize(
    "value",
    [
        {"value": 1.5},
        {"value": Decimal("NaN")},
        {1: "not-a-string-key"},
        {"value": object()},
    ],
)
def test_canonicalization_rejects_unsupported_values(value):
    with pytest.raises(BlueprintCanonicalizationError):
        canonical_json_text(value)


def test_load_blueprint_requires_top_level_object(tmp_path: Path):
    path = tmp_path / "blueprint.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(
        BlueprintCanonicalizationError,
        match="oberster Ebene ein JSON-Objekt",
    ):
        load_blueprint_json(path)


def test_load_blueprint_reports_invalid_json(tmp_path: Path):
    path = tmp_path / "blueprint.json"
    path.write_text('{"broken":', encoding="utf-8")

    with pytest.raises(BlueprintCanonicalizationError, match="ungültiges JSON"):
        load_blueprint_json(path)
