from __future__ import annotations

from copy import deepcopy
from typing import Any

from .solution_generation_contract import GENERATED_OPTION_FIELDS, OPTION_LANES
from .solution_generation_sources import SolutionGenerationSourceContext
from .solution_generation_validation import (
    SolutionGenerationContractError,
    validate_solution_generation_payload,
)
from .solution_quality_versions import REPAIR_PROMPT_VERSION, REPAIR_SCHEMA_VERSION


class SolutionGenerationEffectivePayloadError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


MACHINE_REPAIR_FIELDS = frozenset(
    ("quality_run_id", "input_hash", "prompt_version", "schema_version", "patches")
)
MACHINE_REPAIR_PATCH_FIELDS = frozenset(("option", "field", "statement"))


def normalize_solution_generation_edits(
    preview_payload: dict[str, Any],
) -> dict[str, dict[str, str]]:
    edits = preview_payload.get("edits", {})
    if not isinstance(edits, dict):
        raise SolutionGenerationEffectivePayloadError(
            "Die gespeicherten Bearbeitungen sind ungültig. Bitte neu generieren.",
            code="invalid_preview",
        )

    unknown_lanes = set(edits) - set(OPTION_LANES)
    if unknown_lanes:
        raise SolutionGenerationEffectivePayloadError(
            "Die gespeicherten Bearbeitungen enthalten eine unbekannte Lösungsrichtung.",
            code="invalid_preview",
        )

    normalized: dict[str, dict[str, str]] = {}
    for lane, lane_edits in edits.items():
        if not isinstance(lane_edits, dict):
            raise SolutionGenerationEffectivePayloadError(
                "Die gespeicherten Bearbeitungen sind ungültig. Bitte neu generieren.",
                code="invalid_preview",
            )
        unknown_fields = set(lane_edits) - set(GENERATED_OPTION_FIELDS)
        if unknown_fields:
            raise SolutionGenerationEffectivePayloadError(
                "Die gespeicherten Bearbeitungen enthalten ein nicht freigegebenes Feld.",
                code="invalid_preview",
            )

        normalized_lane: dict[str, str] = {}
        for field_name, value in lane_edits.items():
            if not isinstance(value, str) or not value.strip():
                raise SolutionGenerationEffectivePayloadError(
                    "Bearbeitete Entwurfsfelder dürfen nicht leer sein.",
                    code="invalid_preview",
                )
            normalized_lane[field_name] = value.strip()
        if normalized_lane:
            normalized[lane] = normalized_lane
    return normalized


def normalize_solution_generation_machine_repair(
    preview_payload: dict[str, Any],
) -> dict[str, Any] | None:
    raw_repair = preview_payload.get("machine_repair")
    if raw_repair is None:
        return None
    if not isinstance(raw_repair, dict) or set(raw_repair) != MACHINE_REPAIR_FIELDS:
        raise SolutionGenerationEffectivePayloadError(
            "Der gespeicherte Machine Repair ist strukturell ungültig.",
            code="invalid_preview_repair",
        )

    quality_run_id = raw_repair.get("quality_run_id")
    input_hash = raw_repair.get("input_hash")
    prompt_version = raw_repair.get("prompt_version")
    schema_version = raw_repair.get("schema_version")
    if not isinstance(quality_run_id, str) or not quality_run_id.strip():
        raise SolutionGenerationEffectivePayloadError(
            "Der gespeicherte Machine Repair hat keine gültige Run-ID.",
            code="invalid_preview_repair",
        )
    if not isinstance(input_hash, str) or not input_hash.strip():
        raise SolutionGenerationEffectivePayloadError(
            "Der gespeicherte Machine Repair hat keinen gültigen Input-Hash.",
            code="invalid_preview_repair",
        )
    if prompt_version != REPAIR_PROMPT_VERSION or schema_version != REPAIR_SCHEMA_VERSION:
        raise SolutionGenerationEffectivePayloadError(
            "Der gespeicherte Machine Repair verwendet einen unbekannten Vertrag.",
            code="invalid_preview_repair",
        )

    raw_patches = raw_repair.get("patches")
    if not isinstance(raw_patches, list) or not raw_patches:
        raise SolutionGenerationEffectivePayloadError(
            "Der gespeicherte Machine Repair enthält keine gültigen Patches.",
            code="invalid_preview_repair",
        )

    normalized_patches: list[dict[str, Any]] = []
    seen_targets: set[tuple[str, str]] = set()
    for patch in raw_patches:
        if not isinstance(patch, dict) or set(patch) != MACHINE_REPAIR_PATCH_FIELDS:
            raise SolutionGenerationEffectivePayloadError(
                "Ein gespeicherter Machine-Repair-Patch ist strukturell ungültig.",
                code="invalid_preview_repair",
            )
        option = patch.get("option")
        field = patch.get("field")
        statement = patch.get("statement")
        if option not in OPTION_LANES or field not in GENERATED_OPTION_FIELDS:
            raise SolutionGenerationEffectivePayloadError(
                "Ein Machine-Repair-Patch zielt auf ein nicht freigegebenes Feld.",
                code="invalid_preview_repair",
            )
        if not isinstance(statement, dict):
            raise SolutionGenerationEffectivePayloadError(
                "Ein Machine-Repair-Patch enthält kein vollständiges Statement.",
                code="invalid_preview_repair",
            )
        target = (option, field)
        if target in seen_targets:
            raise SolutionGenerationEffectivePayloadError(
                "Der gespeicherte Machine Repair enthält ein doppeltes Ziel.",
                code="invalid_preview_repair",
            )
        seen_targets.add(target)
        normalized_patches.append(
            {
                "option": option,
                "field": field,
                "statement": deepcopy(statement),
            }
        )

    return {
        "quality_run_id": quality_run_id.strip(),
        "input_hash": input_hash.strip(),
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "patches": normalized_patches,
    }


def build_validated_effective_solution_payload(
    preview_payload: dict[str, Any],
    source_context: SolutionGenerationSourceContext,
) -> dict[str, Any]:
    """Build the single canonical, deterministically valid Block-7 preview payload.

    The persisted generator output remains immutable. A validated machine repair
    replaces only explicitly targeted complete statements. Human edits remain a
    separate text-only overlay and are applied last so later Human Review can
    intentionally supersede repaired text without losing repair provenance.
    Every stage is revalidated with the authoritative Block-7 validator.
    """

    raw_payload = {
        "schema_version": preview_payload.get("schema_version"),
        "prompt_version": preview_payload.get("prompt_version"),
        "options": preview_payload.get("options"),
    }
    try:
        validated = validate_solution_generation_payload(raw_payload, source_context)
    except SolutionGenerationContractError as exc:
        raise SolutionGenerationEffectivePayloadError(
            "Die gespeicherte KI-Vorschau ist nicht mehr vertragskonform. Bitte neu generieren.",
            code="invalid_preview",
        ) from exc

    machine_repair = normalize_solution_generation_machine_repair(preview_payload)
    if machine_repair is not None:
        for patch in machine_repair["patches"]:
            validated["options"][patch["option"]][patch["field"]] = deepcopy(patch["statement"])
        try:
            validated = validate_solution_generation_payload(validated, source_context)
        except SolutionGenerationContractError as exc:
            raise SolutionGenerationEffectivePayloadError(
                "Der gespeicherte Machine Repair verletzt die Quellen- oder Inhaltsregeln.",
                code="invalid_preview_repair",
            ) from exc

    for lane, lane_edits in normalize_solution_generation_edits(preview_payload).items():
        for field_name, value in lane_edits.items():
            validated["options"][lane][field_name]["text"] = value

    try:
        return validate_solution_generation_payload(validated, source_context)
    except SolutionGenerationContractError as exc:
        raise SolutionGenerationEffectivePayloadError(
            "Eine Bearbeitung verletzt die Quellen- oder Inhaltsregeln. Bitte den Entwurf prüfen.",
            code="invalid_preview_edit",
        ) from exc
