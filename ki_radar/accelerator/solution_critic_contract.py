from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any

from .solution_generation_contract import GENERATED_OPTION_FIELDS, OPTION_LANES
from .solution_generation_sources import ALLOWED_SOURCE_IDS, SolutionGenerationSourceContext
from .solution_quality_versions import CRITIC_PROMPT_VERSION, CRITIC_SCHEMA_VERSION

CRITIC_CRITERIA = (
    "distinctiveness",
    "bottleneck_fit",
    "grounding_consistency",
    "evidence_discipline",
    "complexity_proportionality",
)

ROOT_FIELDS = frozenset(("schema_version", "prompt_version", "findings"))
FINDING_REQUIRED_FIELDS = frozenset(
    ("criterion", "option", "finding", "source_ids", "repairable", "related_targets")
)
FINDING_ALLOWED_FIELDS = FINDING_REQUIRED_FIELDS | {"field"}
TARGET_FIELDS = frozenset(("option", "field"))


class SolutionCriticContractError(ValueError):
    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def unconfirmed_solution_fit_findings(options, source_context, findings):
    """Supplement the semantic critic using its existing bound-repair contract."""
    if source_context.validation_state != "not_validated" or any(
        fact.field == "confirmed_causes" and fact.value.strip() for fact in source_context.facts
    ):
        return []
    source_ids = [fact.source_id for fact in source_context.facts if fact.field == "bottlenecks"]
    if not source_ids:
        return []
    covered = set()
    for finding in findings:
        if not isinstance(finding, dict) or not finding.get("repairable"):
            continue
        covered.add((finding.get("option"), finding.get("field")))
        covered.update(
            (target.get("option"), target.get("field"))
            for target in finding.get("related_targets", [])
            if isinstance(target, dict)
        )
    claim = re.compile(r"\b(?:adressiert|reduziert|beseitigt|löst|deckt)\b|\bsetzt\b.+\ban\b", re.I)
    qualified = re.compile(
        r"\b(?:kann|könn\w*|würde\w*|wäre\w*|falls|sofern|möglich\w*|bedingt\w*|"
        r"unbestätigt\w*|unbewiesen\w*|Hypothes\w*|berichtet\w*|subjektiv\w*|soll\w*)\b|"
        r"nicht (?:belegt|nachgewiesen|bestätigt|bewiesen)",
        re.I,
    )
    result = []
    for lane in OPTION_LANES:
        field = "bottleneck_coverage"
        if (lane, field) in covered:
            continue
        text = options[lane][field]["text"]
        if any(
            claim.search(sentence) and not qualified.search(sentence)
            for sentence in re.split(r"[.;\n]", text)
        ):
            result.append(
                {
                    "criterion": "evidence_discipline",
                    "option": lane,
                    "field": field,
                    "finding": "Serverseitige Claim-Prüfung: Bei unvalidierter Diagnose ohne "
                    "bestätigte Ursache muss jeder Satz zum Engpass-Fit ausdrücklich bedingt "
                    "formuliert sein. Ein späterer Evidenzvorbehalt bestätigt den Fit nicht.",
                    "source_ids": source_ids,
                    "repairable": True,
                    "related_targets": [],
                }
            )
    for lane in OPTION_LANES:
        field = "technology_constraints"
        statement = options[lane].get(field, {})
        if (lane, field) in covered:
            continue
        if any(
            re.search(r"\bEngp(?:ass|äss)\w*\b", sentence, re.I)
            and not qualified.search(sentence)
            and not re.search(r"\bkein\w*\b", sentence, re.I)
            for sentence in re.split(r"[.;\n]", statement.get("text", ""))
        ):
            result.append(
                {
                    "criterion": "evidence_discipline",
                    "option": lane,
                    "field": field,
                    "finding": "Serverseitige Claim-Prüfung: Eine berichtete technische "
                    "Einschränkung ist ohne Wirkungsbeleg kein nachgewiesener Engpass. "
                    "Bericht erhalten, kausale Blockierungswirkung ausdrücklich offen lassen, "
                    "auch in uncertainty.reason und offenen Evidenzfragen.",
                    "source_ids": source_ids,
                    "repairable": True,
                    "related_targets": [],
                }
            )
    systems = next((fact for fact in source_context.facts if fact.field == "systems"), None)
    if systems and not re.search(r"integrat|anbind|schnittstell", systems.value, re.I):
        necessity = re.compile(r"erforderlich|notwendig|nötig|\bmuss\b|\bmüsst\w*", re.I)
        conditional = re.compile(
            r"^\s*ob\b|"
            r"\b(?:falls|sofern|wenn|gegebenenfalls|eventuell|möglicherweise|kann|könnte\w*|offen)\b|"
            r"\b(?:kein\w*|nicht)\b[^.;]{0,80}\b(?:erforderlich|notwendig|nötig)\b",
            re.I,
        )
        for lane in OPTION_LANES:
            field = "integration_impact"
            statement = options[lane].get(field, {})
            if (lane, field) in covered or statement.get("source_ids") != [systems.source_id]:
                continue
            if any(
                necessity.search(sentence) and not conditional.search(sentence)
                for sentence in re.split(r"[.;\n]", statement["text"])
            ):
                result.append(
                    {
                        "criterion": "evidence_discipline",
                        "option": lane,
                        "field": field,
                        "finding": "Serverseitige Claim-Prüfung: Ausschließlich referenzierte "
                        "Systemnamen belegen keine notwendige Integration. Ob eine Anbindung "
                        "erforderlich wäre, bleibt ohne konkrete Anforderung offen; "
                        "bedingt formulieren.",
                        "source_ids": [systems.source_id],
                        "repairable": True,
                        "related_targets": [],
                    }
                )
    return result


def _exact_fields(
    value: dict[str, Any],
    *,
    required: frozenset[str],
    allowed: frozenset[str],
    path: str,
    errors: list[str],
) -> None:
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
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


def _enum_text(
    value: Any,
    *,
    allowed: tuple[str, ...],
    path: str,
    errors: list[str],
) -> str:
    text = _nonempty_text(value, path, errors)
    if text and text not in allowed:
        errors.append(f"{path}: Nicht unterstützter Wert '{text}'.")
        return ""
    return text


def _source_ids(
    value: Any,
    *,
    actual_source_ids: frozenset[str],
    path: str,
    errors: list[str],
) -> list[str]:
    items = _as_list(value, path, errors)
    normalized: list[str] = []
    for index, item in enumerate(items):
        source_id = _nonempty_text(item, f"{path}[{index}]", errors)
        if not source_id:
            continue
        if source_id not in actual_source_ids:
            errors.append(
                f"{path}[{index}]: Source-ID '{source_id}' ist nicht im Snapshot enthalten."
            )
            continue
        if source_id in normalized:
            errors.append(f"{path}[{index}]: Doppelte Source-ID '{source_id}'.")
            continue
        normalized.append(source_id)
    return sorted(normalized)


def _target_sort_key(target: dict[str, str]) -> tuple[int, int]:
    return OPTION_LANES.index(target["option"]), GENERATED_OPTION_FIELDS.index(target["field"])


def _target(
    value: Any,
    *,
    path: str,
    errors: list[str],
) -> dict[str, str] | None:
    target = _as_dict(value, path, errors)
    _exact_fields(
        target,
        required=TARGET_FIELDS,
        allowed=TARGET_FIELDS,
        path=path,
        errors=errors,
    )
    option = _enum_text(
        target.get("option"),
        allowed=OPTION_LANES,
        path=f"{path}.option",
        errors=errors,
    )
    field = _enum_text(
        target.get("field"),
        allowed=GENERATED_OPTION_FIELDS,
        path=f"{path}.field",
        errors=errors,
    )
    if not option or not field:
        return None
    return {"option": option, "field": field}


def _finding_id(finding: dict[str, Any]) -> str:
    serialized = json.dumps(
        finding,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"finding_{hashlib.sha256(serialized).hexdigest()[:24]}"


def _validate_finding(
    value: Any,
    *,
    index: int,
    actual_source_ids: frozenset[str],
    errors: list[str],
) -> dict[str, Any] | None:
    path = f"findings[{index}]"
    finding = _as_dict(value, path, errors)
    _exact_fields(
        finding,
        required=FINDING_REQUIRED_FIELDS,
        allowed=FINDING_ALLOWED_FIELDS,
        path=path,
        errors=errors,
    )

    criterion = _enum_text(
        finding.get("criterion"),
        allowed=CRITIC_CRITERIA,
        path=f"{path}.criterion",
        errors=errors,
    )
    option = _enum_text(
        finding.get("option"),
        allowed=OPTION_LANES,
        path=f"{path}.option",
        errors=errors,
    )
    primary_field = ""
    if "field" in finding and finding["field"] is not None:
        primary_field = _enum_text(
            finding.get("field"),
            allowed=GENERATED_OPTION_FIELDS,
            path=f"{path}.field",
            errors=errors,
        )
    finding_text = _nonempty_text(finding.get("finding"), f"{path}.finding", errors)
    source_ids = _source_ids(
        finding.get("source_ids"),
        actual_source_ids=actual_source_ids,
        path=f"{path}.source_ids",
        errors=errors,
    )

    repairable = finding.get("repairable")
    if not isinstance(repairable, bool):
        errors.append(f"{path}.repairable: Boolean erwartet.")
        repairable = False

    related_items = _as_list(finding.get("related_targets"), f"{path}.related_targets", errors)
    related_targets: list[dict[str, str]] = []
    seen_targets: set[tuple[str, str]] = set()
    if option and primary_field:
        seen_targets.add((option, primary_field))
    for target_index, item in enumerate(related_items):
        normalized = _target(item, path=f"{path}.related_targets[{target_index}]", errors=errors)
        if normalized is None:
            continue
        key = (normalized["option"], normalized["field"])
        if key in seen_targets:
            continue
        seen_targets.add(key)
        related_targets.append(normalized)
    related_targets.sort(key=_target_sort_key)

    if repairable and not seen_targets:
        errors.append(
            f"{path}.repairable: Reparierbare Findings benötigen mindestens ein konkretes Feldziel."
        )

    if not criterion or not option or not finding_text:
        return None

    normalized_finding: dict[str, Any] = {
        "criterion": criterion,
        "option": option,
        "finding": finding_text,
        "source_ids": source_ids,
        "repairable": repairable,
        "related_targets": related_targets,
    }
    if primary_field:
        normalized_finding["field"] = primary_field
    normalized_finding["finding_id"] = _finding_id(normalized_finding)
    return normalized_finding


def validate_solution_critic_payload(
    payload: Any,
    source_context: SolutionGenerationSourceContext,
) -> dict[str, Any]:
    errors: list[str] = []
    root = _as_dict(payload, "root", errors)
    _exact_fields(
        root,
        required=ROOT_FIELDS,
        allowed=ROOT_FIELDS,
        path="root",
        errors=errors,
    )

    schema_version = _nonempty_text(root.get("schema_version"), "root.schema_version", errors)
    if schema_version and schema_version != CRITIC_SCHEMA_VERSION:
        errors.append(
            f"root.schema_version: Erwartet {CRITIC_SCHEMA_VERSION}, erhalten {schema_version}."
        )
    prompt_version = _nonempty_text(root.get("prompt_version"), "root.prompt_version", errors)
    if prompt_version and prompt_version != CRITIC_PROMPT_VERSION:
        errors.append(
            f"root.prompt_version: Erwartet {CRITIC_PROMPT_VERSION}, erhalten {prompt_version}."
        )

    actual_source_ids = frozenset(fact.source_id for fact in source_context.facts)
    findings = _as_list(root.get("findings"), "root.findings", errors)
    normalized_findings: list[dict[str, Any]] = []
    finding_ids: set[str] = set()
    for index, value in enumerate(findings):
        normalized = _validate_finding(
            value,
            index=index,
            actual_source_ids=actual_source_ids,
            errors=errors,
        )
        if normalized is None:
            continue
        finding_id = normalized["finding_id"]
        if finding_id in finding_ids:
            errors.append(f"findings[{index}]: Identisches Finding ist bereits vorhanden.")
            continue
        finding_ids.add(finding_id)
        normalized_findings.append(normalized)

    if errors:
        raise SolutionCriticContractError(errors)

    return {
        "schema_version": CRITIC_SCHEMA_VERSION,
        "prompt_version": CRITIC_PROMPT_VERSION,
        "findings": normalized_findings,
    }


def _target_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["option", "field"],
        "properties": {
            "option": {"type": "string", "enum": list(OPTION_LANES)},
            "field": {"type": "string", "enum": list(GENERATED_OPTION_FIELDS)},
        },
    }


def build_solution_critic_json_schema(
    *, allowed_source_ids: Iterable[str] = ALLOWED_SOURCE_IDS
) -> dict[str, object]:
    source_ids = sorted(set(allowed_source_ids))
    finding_properties: dict[str, object] = {
        "criterion": {"type": "string", "enum": list(CRITIC_CRITERIA)},
        "option": {"type": "string", "enum": list(OPTION_LANES)},
        "field": {
            "type": ["string", "null"],
            "enum": [*GENERATED_OPTION_FIELDS, None],
        },
        "finding": {"type": "string", "minLength": 1},
        "source_ids": {
            "type": "array",
            "items": {"type": "string", "enum": source_ids},
        },
        "repairable": {"type": "boolean"},
        "related_targets": {
            "type": "array",
            "items": _target_schema(),
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "prompt_version", "findings"],
        "properties": {
            "schema_version": {"type": "string", "const": CRITIC_SCHEMA_VERSION},
            "prompt_version": {"type": "string", "const": CRITIC_PROMPT_VERSION},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": sorted(FINDING_ALLOWED_FIELDS),
                    "properties": finding_properties,
                },
            },
        },
    }
