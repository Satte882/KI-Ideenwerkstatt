from __future__ import annotations

import re
from typing import Any

from ki_radar.architecture.models import EvidenceBasis, TimeToValue
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel

DISCOVERY_SCHEMA_VERSION = "ap1-discovery-v1"
DISCOVERY_PROMPT_VERSION = "ap1-discovery-v1"
DISCOVERY_VERIFIER_SCHEMA_VERSION = "ap1-discovery-verifier-v1"
DISCOVERY_VERIFIER_PROMPT_VERSION = "ap1-discovery-verifier-v1"

_STAGE_FIELDS = frozenset(
    {
        "key",
        "sequence",
        "name",
        "description",
        "roles",
        "systems",
        "documents",
        "pain_points",
        "baseline_metrics",
        "impact",
        "pain_intensity",
        "improvement_potential",
        "data_accessibility",
        "change_effort",
        "time_to_value",
        "evidence_basis",
        "evidence_refs",
    }
)
_VALUE_STREAM_FIELDS = frozenset(
    {
        "name",
        "description",
        "trigger",
        "outcome",
        "scope_in",
        "scope_out",
        "strategic_objective",
        "stakeholders",
        "constraints",
        "evidence_refs",
    }
)
_FOCUS_FIELDS = frozenset(
    {
        "recommended_stage_key",
        "business_domain",
        "capability",
        "strategic_impact",
        "economic_potential",
        "pain_intensity",
        "data_accessibility",
        "change_effort",
        "rationale",
        "tradeoffs",
        "uncertainties",
        "evidence_refs",
    }
)
_PROCESS_FIELDS = frozenset(
    {
        "name",
        "scope_start",
        "scope_end",
        "trigger",
        "outcome",
        "current_flow",
        "roles",
        "systems",
        "data_objects",
        "business_rules",
        "handoffs",
        "bottlenecks",
        "observations",
        "cause_hypotheses",
        "constraints",
        "exceptions",
        "baseline_metrics",
        "evidence_refs",
    }
)
_ROOT_FIELDS = frozenset(
    {
        "schema_version",
        "value_stream",
        "stages",
        "focus",
        "process_analysis",
        "facts",
        "hypotheses",
        "unknowns",
        "clarifications",
        "contradictions",
    }
)
_NUMBER_RE = re.compile(r"(?<![A-Za-zÄÖÜäöüß])\d+(?:[.,]\d+)?(?:\s*%)?")


class DiscoveryContractError(ValueError):
    def __init__(self, errors: list[str] | tuple[str, ...]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def _text_schema(*, min_length: int = 0) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string"}
    if min_length:
        schema["minLength"] = min_length
    return schema


def _ref_list_schema(*, min_items: int = 0) -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": min_items,
        "uniqueItems": True,
        "items": {"type": "string", "minLength": 1},
    }


def _object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def build_discovery_json_schema() -> dict[str, Any]:
    value_stream = _object_schema(
        {
            "name": _text_schema(min_length=1),
            "description": _text_schema(),
            "trigger": _text_schema(min_length=1),
            "outcome": _text_schema(min_length=1),
            "scope_in": _text_schema(min_length=1),
            "scope_out": _text_schema(),
            "strategic_objective": _text_schema(),
            "stakeholders": _text_schema(),
            "constraints": _text_schema(),
            "evidence_refs": _ref_list_schema(min_items=1),
        }
    )
    stage = _object_schema(
        {
            "key": _text_schema(min_length=1),
            "sequence": {"type": "integer", "minimum": 1, "maximum": 30},
            "name": _text_schema(min_length=1),
            "description": _text_schema(),
            "roles": _text_schema(),
            "systems": _text_schema(),
            "documents": _text_schema(),
            "pain_points": _text_schema(),
            "baseline_metrics": _text_schema(),
            "impact": {
                "type": "string",
                "enum": [choice for choice, _label in ScreeningLevel.choices],
            },
            "pain_intensity": {
                "type": "string",
                "enum": [choice for choice, _label in ScreeningLevel.choices],
            },
            "improvement_potential": {
                "type": "string",
                "enum": [choice for choice, _label in ScreeningLevel.choices],
            },
            "data_accessibility": {
                "type": "string",
                "enum": [choice for choice, _label in ScreeningLevel.choices],
            },
            "change_effort": {
                "type": "string",
                "enum": [choice for choice, _label in ScreeningLevel.choices],
            },
            "time_to_value": {
                "type": "string",
                "enum": [
                    TimeToValue.UNKNOWN,
                    TimeToValue.SHORT,
                    TimeToValue.MEDIUM,
                    TimeToValue.LONG,
                ],
            },
            "evidence_basis": {
                "type": "string",
                "enum": [choice for choice, _label in EvidenceBasis.choices],
            },
            "evidence_refs": _ref_list_schema(),
        }
    )
    levels = [choice for choice, _label in ScreeningLevel.choices]
    domains = [choice for choice, _label in BusinessDomain.choices]
    focus = _object_schema(
        {
            "recommended_stage_key": _text_schema(min_length=1),
            "business_domain": {"type": "string", "enum": domains},
            "capability": _text_schema(min_length=1),
            "strategic_impact": {"type": "string", "enum": levels},
            "economic_potential": {"type": "string", "enum": levels},
            "pain_intensity": {"type": "string", "enum": levels},
            "data_accessibility": {"type": "string", "enum": levels},
            "change_effort": {"type": "string", "enum": levels},
            "rationale": _text_schema(min_length=1),
            "tradeoffs": {"type": "array", "items": _text_schema(min_length=1)},
            "uncertainties": {"type": "array", "items": _text_schema(min_length=1)},
            "evidence_refs": _ref_list_schema(min_items=1),
        }
    )
    process = _object_schema(
        {
            "name": _text_schema(min_length=1),
            "scope_start": _text_schema(min_length=1),
            "scope_end": _text_schema(min_length=1),
            "trigger": _text_schema(min_length=1),
            "outcome": _text_schema(min_length=1),
            "current_flow": _text_schema(min_length=1),
            "roles": _text_schema(),
            "systems": _text_schema(),
            "data_objects": _text_schema(),
            "business_rules": _text_schema(),
            "handoffs": _text_schema(),
            "bottlenecks": _text_schema(min_length=1),
            "observations": _text_schema(),
            "cause_hypotheses": _text_schema(),
            "constraints": _text_schema(),
            "exceptions": _text_schema(),
            "baseline_metrics": _text_schema(),
            "evidence_refs": _ref_list_schema(min_items=1),
        }
    )
    grounded_item = _object_schema(
        {
            "statement": _text_schema(min_length=1),
            "evidence_refs": _ref_list_schema(min_items=1),
        }
    )
    hypothesis_item = _object_schema(
        {
            "statement": _text_schema(min_length=1),
            "evidence_refs": _ref_list_schema(),
        }
    )
    unknown_item = _object_schema(
        {
            "statement": _text_schema(min_length=1),
            "impact": _text_schema(min_length=1),
        }
    )
    clarification_item = _object_schema(
        {
            "question": _text_schema(min_length=1),
            "impact": _text_schema(min_length=1),
            "blocking": {"type": "boolean"},
        }
    )
    contradiction_item = _object_schema(
        {
            "statement": _text_schema(min_length=1),
            "evidence_refs": _ref_list_schema(min_items=2),
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **_object_schema(
            {
                "schema_version": {"type": "string", "const": DISCOVERY_SCHEMA_VERSION},
                "value_stream": value_stream,
                "stages": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 12,
                    "items": stage,
                },
                "focus": focus,
                "process_analysis": process,
                "facts": {"type": "array", "items": grounded_item},
                "hypotheses": {"type": "array", "items": hypothesis_item},
                "unknowns": {"type": "array", "items": unknown_item},
                "clarifications": {"type": "array", "items": clarification_item},
                "contradictions": {"type": "array", "items": contradiction_item},
            }
        ),
    }


def build_discovery_verifier_schema() -> dict[str, Any]:
    finding = _object_schema(
        {
            "code": _text_schema(min_length=1),
            "message": _text_schema(min_length=1),
        }
    )
    checks = _object_schema(
        {
            "source_grounding": {"type": "boolean"},
            "scope_quality": {"type": "boolean"},
            "stage_sequence": {"type": "boolean"},
            "focus_fit": {"type": "boolean"},
            "hypothesis_separation": {"type": "boolean"},
            "unknowns_visible": {"type": "boolean"},
            "contradictions_preserved": {"type": "boolean"},
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **_object_schema(
            {
                "schema_version": {
                    "type": "string",
                    "const": DISCOVERY_VERIFIER_SCHEMA_VERSION,
                },
                "status": {
                    "type": "string",
                    "enum": ["approved", "repair", "waiting_human"],
                },
                "checks": checks,
                "critical_findings": {"type": "array", "items": finding},
                "repair_instructions": _text_schema(),
                "human_question": _text_schema(),
            }
        ),
    }


def _exact_fields(value: Any, expected: frozenset[str], path: str, errors: list[str]) -> dict:
    if not isinstance(value, dict):
        errors.append(f"{path}: JSON-Objekt erwartet.")
        return {}
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown:
        errors.append(f"{path}: Unbekannte Felder: {', '.join(unknown)}.")
    if missing:
        errors.append(f"{path}: Pflichtfelder fehlen: {', '.join(missing)}.")
    return value


def _validate_refs(value: Any, allowed_refs: set[str], path: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{path}: Quellenreferenzen müssen eine Liste sein.")
        return
    for ref in value:
        if not isinstance(ref, str) or ref not in allowed_refs:
            errors.append(f"{path}: Unbekannte Quellenreferenz {ref!r}.")


def _validate_numbers(payload: dict[str, Any], evidence_text: str, errors: list[str]) -> None:
    candidates: list[tuple[str, str]] = []
    process = payload.get("process_analysis")
    if isinstance(process, dict):
        candidates.append(
            (
                "process_analysis.baseline_metrics",
                str(process.get("baseline_metrics") or ""),
            )
        )
    stages = payload.get("stages")
    if isinstance(stages, list):
        for index, stage in enumerate(stages):
            if isinstance(stage, dict):
                candidates.append(
                    (f"stages[{index}].baseline_metrics", str(stage.get("baseline_metrics") or ""))
                )
    facts = payload.get("facts")
    if isinstance(facts, list):
        for index, fact in enumerate(facts):
            if isinstance(fact, dict):
                candidates.append((f"facts[{index}].statement", str(fact.get("statement") or "")))

    evidence_compact = evidence_text.casefold().replace(",", ".")
    for path, value in candidates:
        for raw in _NUMBER_RE.findall(value):
            normalized = raw.casefold().replace(",", ".").replace(" ", "")
            if normalized and normalized not in evidence_compact.replace(" ", ""):
                errors.append(f"{path}: Zahl {raw!r} ist im autorisierten Input nicht belegt.")


def validate_discovery_payload(
    payload: Any,
    *,
    allowed_refs: set[str],
    evidence_text: str,
) -> dict[str, Any]:
    errors: list[str] = []
    root = _exact_fields(payload, _ROOT_FIELDS, "root", errors)
    if root.get("schema_version") != DISCOVERY_SCHEMA_VERSION:
        errors.append("schema_version: Falsche Discovery-Schema-Version.")

    value_stream = _exact_fields(
        root.get("value_stream"),
        _VALUE_STREAM_FIELDS,
        "value_stream",
        errors,
    )
    focus = _exact_fields(root.get("focus"), _FOCUS_FIELDS, "focus", errors)
    process = _exact_fields(
        root.get("process_analysis"),
        _PROCESS_FIELDS,
        "process_analysis",
        errors,
    )

    for path, value in (
        ("value_stream.name", value_stream.get("name")),
        ("value_stream.trigger", value_stream.get("trigger")),
        ("value_stream.outcome", value_stream.get("outcome")),
        ("value_stream.scope_in", value_stream.get("scope_in")),
        ("focus.capability", focus.get("capability")),
        ("focus.rationale", focus.get("rationale")),
        ("process_analysis.name", process.get("name")),
        ("process_analysis.scope_start", process.get("scope_start")),
        ("process_analysis.scope_end", process.get("scope_end")),
        ("process_analysis.trigger", process.get("trigger")),
        ("process_analysis.outcome", process.get("outcome")),
        ("process_analysis.current_flow", process.get("current_flow")),
        ("process_analysis.bottlenecks", process.get("bottlenecks")),
    ):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}: Nichtleerer Text erforderlich.")

    _validate_refs(
        value_stream.get("evidence_refs"),
        allowed_refs,
        "value_stream.evidence_refs",
        errors,
    )
    _validate_refs(focus.get("evidence_refs"), allowed_refs, "focus.evidence_refs", errors)
    _validate_refs(
        process.get("evidence_refs"),
        allowed_refs,
        "process_analysis.evidence_refs",
        errors,
    )

    stages = root.get("stages")
    stage_keys: list[str] = []
    if not isinstance(stages, list) or not stages:
        errors.append("stages: Mindestens eine Phase erforderlich.")
        stages = []
    for index, raw_stage in enumerate(stages):
        stage = _exact_fields(raw_stage, _STAGE_FIELDS, f"stages[{index}]", errors)
        key = str(stage.get("key") or "").strip()
        name = str(stage.get("name") or "").strip()
        if not key:
            errors.append(f"stages[{index}].key: Nichtleerer Schlüssel erforderlich.")
        if not name:
            errors.append(f"stages[{index}].name: Nichtleerer Name erforderlich.")
        stage_keys.append(key)
        if stage.get("sequence") != index + 1:
            errors.append(f"stages[{index}].sequence: Phasen müssen lückenlos ab 1 sortiert sein.")
        allowed_stage_levels = set(ScreeningLevel.values)
        for criterion in (
            "impact",
            "pain_intensity",
            "improvement_potential",
            "data_accessibility",
            "change_effort",
        ):
            if stage.get(criterion) not in allowed_stage_levels:
                errors.append(f"stages[{index}].{criterion}: Ungültige Screening-Stufe.")
        if stage.get("time_to_value") not in {
            TimeToValue.UNKNOWN,
            TimeToValue.SHORT,
            TimeToValue.MEDIUM,
            TimeToValue.LONG,
        }:
            errors.append(f"stages[{index}].time_to_value: Ungültige Einordnung.")
        if stage.get("evidence_basis") not in set(EvidenceBasis.values):
            errors.append(f"stages[{index}].evidence_basis: Ungültige Evidenzbasis.")
        _validate_refs(
            stage.get("evidence_refs"),
            allowed_refs,
            f"stages[{index}].evidence_refs",
            errors,
        )
    if len(stage_keys) != len(set(stage_keys)):
        errors.append("stages: Phasenschlüssel müssen eindeutig sein.")
    if focus.get("recommended_stage_key") not in stage_keys:
        errors.append("focus.recommended_stage_key: Fokus verweist auf keine erzeugte Phase.")

    domains = {choice for choice, _label in BusinessDomain.choices}
    levels = {choice for choice, _label in ScreeningLevel.choices}
    if focus.get("business_domain") not in domains:
        errors.append("focus.business_domain: Ungültige Fachdomäne.")
    for field in (
        "strategic_impact",
        "economic_potential",
        "pain_intensity",
        "data_accessibility",
        "change_effort",
    ):
        if focus.get(field) not in levels:
            errors.append(f"focus.{field}: Ungültige Screening-Stufe.")

    for list_name in ("facts", "hypotheses", "contradictions"):
        values = root.get(list_name)
        if not isinstance(values, list):
            errors.append(f"{list_name}: Liste erwartet.")
            continue
        for index, item in enumerate(values):
            if not isinstance(item, dict):
                errors.append(f"{list_name}[{index}]: Objekt erwartet.")
                continue
            _validate_refs(
                item.get("evidence_refs"),
                allowed_refs,
                f"{list_name}[{index}].evidence_refs",
                errors,
            )
            if list_name == "contradictions":
                refs = item.get("evidence_refs")
                if isinstance(refs, list) and len(set(refs)) < 2:
                    errors.append(
                        f"{list_name}[{index}].evidence_refs: "
                        "Widerspruch braucht mindestens zwei Quellen."
                    )

    for list_name in ("unknowns", "clarifications"):
        if not isinstance(root.get(list_name), list):
            errors.append(f"{list_name}: Liste erwartet.")

    _validate_numbers(root, evidence_text, errors)
    if errors:
        raise DiscoveryContractError(errors)
    return root


def validate_verifier_payload(payload: Any) -> dict[str, Any]:
    expected = frozenset(
        {
            "schema_version",
            "status",
            "checks",
            "critical_findings",
            "repair_instructions",
            "human_question",
        }
    )
    errors: list[str] = []
    root = _exact_fields(payload, expected, "verifier", errors)
    if root.get("schema_version") != DISCOVERY_VERIFIER_SCHEMA_VERSION:
        errors.append("verifier.schema_version: Falsche Schema-Version.")
    if root.get("status") not in {"approved", "repair", "waiting_human"}:
        errors.append("verifier.status: Ungültiger Status.")
    expected_checks = frozenset(
        {
            "source_grounding",
            "scope_quality",
            "stage_sequence",
            "focus_fit",
            "hypothesis_separation",
            "unknowns_visible",
            "contradictions_preserved",
        }
    )
    checks = _exact_fields(root.get("checks"), expected_checks, "verifier.checks", errors)
    for key in expected_checks:
        if not isinstance(checks.get(key), bool):
            errors.append(f"verifier.checks.{key}: Boolean erwartet.")

    findings = root.get("critical_findings")
    if not isinstance(findings, list):
        errors.append("verifier.critical_findings: Liste erwartet.")
    if root.get("status") == "approved":
        if findings:
            errors.append("verifier: approved darf keine kritischen Findings enthalten.")
        if any(value is not True for value in checks.values()):
            errors.append("verifier: approved verlangt alle Checks=true.")
    if root.get("status") == "repair" and not str(root.get("repair_instructions") or "").strip():
        errors.append("verifier.repair_instructions: Repair benötigt konkrete Anweisung.")
    if root.get("status") == "waiting_human" and not str(root.get("human_question") or "").strip():
        errors.append("verifier.human_question: WAITING_HUMAN benötigt eine präzise Frage.")
    if errors:
        raise DiscoveryContractError(errors)
    return root
