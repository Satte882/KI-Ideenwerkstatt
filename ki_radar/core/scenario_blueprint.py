from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any


class BlueprintCanonicalizationError(ValueError):
    """Raised when a value cannot be represented by the canonical JSON format."""


def load_blueprint_json(path: Path) -> dict[str, Any]:
    """Load a blueprint while preserving decimal numbers exactly."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BlueprintCanonicalizationError(
            f"Blueprint-Datei konnte nicht gelesen werden: {path}",
        ) from exc
    try:
        payload = json.loads(raw, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise BlueprintCanonicalizationError(
            f"Blueprint enthält ungültiges JSON: Zeile {exc.lineno}, Spalte {exc.colno}.",
        ) from exc
    if not isinstance(payload, dict):
        raise BlueprintCanonicalizationError(
            "Ein Blueprint muss auf oberster Ebene ein JSON-Objekt sein.",
        )
    return payload


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise BlueprintCanonicalizationError(
            "NaN und unendliche Zahlen sind in Blueprints nicht zulässig.",
        )
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def canonical_json_text(value: Any) -> str:
    """Serialize supported JSON values deterministically."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
    if isinstance(value, float):
        raise BlueprintCanonicalizationError(
            "Binäre Gleitkommawerte sind nicht zulässig; JSON mit Decimal laden.",
        )
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(canonical_json_text(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise BlueprintCanonicalizationError(
                "JSON-Objektschlüssel müssen Zeichenketten sein.",
            )
        items = (
            f"{json.dumps(key, ensure_ascii=False)}:{canonical_json_text(value[key])}"
            for key in sorted(value)
        )
        return "{" + ",".join(items) + "}"
    raise BlueprintCanonicalizationError(
        f"Nicht unterstützter Blueprint-Wert: {type(value).__name__}.",
    )


def canonical_json_bytes(value: Any) -> bytes:
    return canonical_json_text(value).encode("utf-8")


def blueprint_checksum(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
