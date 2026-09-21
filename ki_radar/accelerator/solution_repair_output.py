from __future__ import annotations

from copy import deepcopy
from typing import Any

from .solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    OPTION_LANES,
    UNCERTAINTY_LEVELS,
)
from .solution_generation_sources import SolutionGenerationSourceContext
from .solution_generation_validation import (
    SolutionGenerationContractError,
    validate_solution_generation_payload,
)
from .solution_quality_versions import REPAIR_PROMPT_VERSION, REPAIR_SCHEMA_VERSION
from .solution_repair_contract import SolutionRepairPlan, SolutionRepairTarget

ROOT_FIELDS = frozenset(("schema_version", "prompt_version", "patches"))
PATCH_FIELDS = frozenset(("option", "field", "statement"))
STATEMENT_FIELDS = frozenset(("text", "source_ids", "assumptions", "open_evidence", "uncertainty"))
UNCERTAINTY_FIELDS = frozenset(("level", "reason"))


class SolutionRepairPayloadError(ValueError):
    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def _statement_schema(allowed_source_ids: tuple[str, ...]) -> dict[str, object]:
    required = ["text", "source_ids", "assumptions", "open_evidence", "uncertainty"]
    properties: dict[str, object] = {
        "text": {"type": "string", "minLength": 1},
        "source_ids": {
            "type": "array",
            "items": {"type": "string", "enum": list(allowed_source_ids)},
        },
        "assumptions": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "open_evidence": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "uncertainty": {
            "type": "object",
            "additionalProperties": False,
            "required": ["level", "reason"],
            "properties": {
                "level": {"type": "string", "enum": list(UNCERTAINTY_LEVELS)},
                "reason": {"type": "string", "minLength": 1},
            },
        },
    }
    provenance_branches: list[dict[str, object]] = []
    for field_name in ("source_ids", "assumptions", "open_evidence"):
        branch_properties = deepcopy(properties)
        branch_field = branch_properties[field_name]
        if not isinstance(branch_field, dict):
            raise TypeError(f"Statement-Schema für {field_name} muss ein Objekt sein.")
        branch_field["minItems"] = 1
        provenance_branches.append(
            {
                "type": "object",
                "additionalProperties": False,
                "required": required,
                "properties": branch_properties,
            }
        )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
        "anyOf": provenance_branches,
    }


def build_solution_repair_json_schema(
    *,
    allowed_source_ids,
    target_count: int,
) -> dict[str, object]:
    source_ids = tuple(sorted(set(allowed_source_ids)))
    if target_count < 1:
        raise ValueError("Der Repair benötigt mindestens ein explizites Ziel.")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "prompt_version", "patches"],
        "properties": {
            "schema_version": {"type": "string", "const": REPAIR_SCHEMA_VERSION},
            "prompt_version": {"type": "string", "const": REPAIR_PROMPT_VERSION},
            "patches": {
                "type": "array",
                "minItems": target_count,
                "maxItems": target_count,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["option", "field", "statement"],
                    "properties": {
                        "option": {"type": "string", "enum": list(OPTION_LANES)},
                        "field": {
                            "type": "string",
                            "enum": list(GENERATED_OPTION_FIELDS),
                        },
                        "statement": _statement_schema(source_ids),
                    },
                },
            },
        },
    }


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


def _nonempty_text(value: Any, path: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: Nicht-leerer Text erwartet.")
        return ""
    return value.strip()


def _target_sort_key(target: SolutionRepairTarget) -> tuple[int, int]:
    return OPTION_LANES.index(target.option), GENERATED_OPTION_FIELDS.index(target.field)


def validate_solution_repair_payload(
    payload: dict[str, Any],
    *,
    plan: SolutionRepairPlan,
    effective_payload: dict[str, Any],
    source_context: SolutionGenerationSourceContext,
) -> dict[str, Any]:
    errors: list[str] = []
    root = _as_dict(payload, "$", errors)
    _exact_fields(root, ROOT_FIELDS, "$", errors)

    schema_version = _nonempty_text(root.get("schema_version"), "$.schema_version", errors)
    prompt_version = _nonempty_text(root.get("prompt_version"), "$.prompt_version", errors)
    if schema_version and schema_version != REPAIR_SCHEMA_VERSION:
        errors.append("$.schema_version: Nicht unterstützte Repair-Schema-Version.")
    if prompt_version and prompt_version != REPAIR_PROMPT_VERSION:
        errors.append("$.prompt_version: Nicht unterstützte Repair-Prompt-Version.")

    raw_patches = _as_list(root.get("patches"), "$.patches", errors)
    expected_targets = set(plan.targets)
    seen_targets: set[SolutionRepairTarget] = set()
    raw_by_target: dict[SolutionRepairTarget, dict[str, Any]] = {}

    for index, value in enumerate(raw_patches):
        path = f"$.patches[{index}]"
        patch = _as_dict(value, path, errors)
        _exact_fields(patch, PATCH_FIELDS, path, errors)
        option = _nonempty_text(patch.get("option"), f"{path}.option", errors)
        field = _nonempty_text(patch.get("field"), f"{path}.field", errors)
        if option and option not in OPTION_LANES:
            errors.append(f"{path}.option: Unbekannte Lösungsrichtung '{option}'.")
        if field and field not in GENERATED_OPTION_FIELDS:
            errors.append(f"{path}.field: Nicht freigegebenes Feld '{field}'.")
        if option not in OPTION_LANES or field not in GENERATED_OPTION_FIELDS:
            continue

        target = SolutionRepairTarget(option=option, field=field)
        if target in seen_targets:
            errors.append(f"{path}: Doppeltes Repair-Ziel {option}.{field}.")
            continue
        seen_targets.add(target)
        if target not in expected_targets:
            errors.append(f"{path}: Nicht freigegebenes Repair-Ziel {option}.{field}.")
            continue

        statement = patch.get("statement")
        if not isinstance(statement, dict):
            errors.append(f"{path}.statement: JSON-Objekt erwartet.")
            continue
        raw_by_target[target] = statement

    missing_targets = sorted(expected_targets - seen_targets, key=_target_sort_key)
    for target in missing_targets:
        errors.append(f"$.patches: Repair-Ziel {target.option}.{target.field} fehlt.")

    if len(raw_patches) != len(plan.targets):
        errors.append("$.patches: Genau ein Patch pro freigegebenem Repair-Ziel ist erforderlich.")

    if errors:
        raise SolutionRepairPayloadError(errors)

    candidate = deepcopy(effective_payload)
    for target in plan.targets:
        candidate["options"][target.option][target.field] = deepcopy(raw_by_target[target])

    try:
        validated_candidate = validate_solution_generation_payload(candidate, source_context)
    except SolutionGenerationContractError as exc:
        raise SolutionRepairPayloadError(exc.errors) from exc

    normalized_patches = [
        {
            "option": target.option,
            "field": target.field,
            "statement": deepcopy(validated_candidate["options"][target.option][target.field]),
        }
        for target in plan.targets
    ]
    return {
        "schema_version": schema_version,
        "prompt_version": prompt_version,
        "patches": normalized_patches,
    }
