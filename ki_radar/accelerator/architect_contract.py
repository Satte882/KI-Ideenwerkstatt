from __future__ import annotations

import re
from typing import Any

from ki_radar.architecture.models import EvidenceBasis, TimeToValue
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel

from . import strategic_discovery as strategic

DISCOVERY_SCHEMA_VERSION = "ap1-discovery-v1"
DISCOVERY_PROMPT_VERSION = "ap1-methodology-v13"
DISCOVERY_VERIFIER_SCHEMA_VERSION = "ap1-discovery-verifier-v1"
DISCOVERY_VERIFIER_PROMPT_VERSION = "ap1-ver-method-v13"
MAX_DISCOVERY_STAGES = 12
DISCOVERY_SCHEMA_VERSION_V2 = "ap1-discovery-v2"
DISCOVERY_PROMPT_VERSION_V2 = "ap1-methodology-v14"


def discovery_versions(catalog_version):
    if catalog_version == "1.0":
        return DISCOVERY_SCHEMA_VERSION, DISCOVERY_PROMPT_VERSION
    if catalog_version == "2.0":
        return DISCOVERY_SCHEMA_VERSION_V2, DISCOVERY_PROMPT_VERSION_V2
    if catalog_version == strategic.CATALOG:
        return strategic.SCHEMA, strategic.PROMPT
    raise ValueError("Nicht unterstützter Discovery-Katalog.")


def supported_discovery_analysis(analysis):
    if str(getattr(analysis, "model_name", "")).startswith("solo/offline"):
        return False
    try:
        versions = discovery_versions(analysis.catalog_version)
    except ValueError:
        return False
    return (analysis.extraction_schema_version, analysis.prompt_version) == versions


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


def blocking_discovery_questions(draft: Any) -> tuple[str, ...]:
    """Project decision gaps from the persisted draft, including historical analyses."""
    if not isinstance(draft, dict):
        return ()
    return tuple(
        str(item.get("question") or "Entscheidungsrelevante Klärung fehlt.").strip()
        for item in (draft.get("clarifications") or [])
        if isinstance(item, dict) and item.get("blocking") is True
    )


def enforce_discovery_readiness(draft: dict, verifier: dict) -> dict:
    """Technical review success cannot resolve a question whose answer is missing.

    Keep repair findings first: correcting unsupported assertions is still possible
    without inventing an answer. Apply the decision boundary after that repair.
    """
    questions = blocking_discovery_questions(draft)
    if draft.get("schema_version") == strategic.SCHEMA:
        question = strategic.missing_scope_question(draft.get("scope_basis"))
        if question:
            questions = (question, *questions)
    if not questions or verifier.get("status") != "approved":
        return verifier
    return {
        **verifier,
        "status": "waiting_human",
        "human_question": questions[0],
        "critical_findings": [
            {"code": "decision_blocking_clarification", "message": question}
            for question in questions
        ],
    }


def discovery_methodical_findings(draft: dict) -> tuple[str, ...]:
    """Conservative language/shape boundary, not a general causal truth classifier.

    Discovery has no human-confirmed cause field. Assertive causal explanations
    in summaries must be explicit source reports or qualified hypotheses.
    """
    if not isinstance(draft, dict):
        return ()
    findings = []
    causal = re.compile(
        r"\b(?:primär\w*|systembestimmend\w*)\s+Engpass\b|\bHauptursache\b|"
        r"\b(?:verursacht|verzögert|sichert|gewährleistet|garantiert)\b|"
        r"\b(?:führt|führen)\b[^.;\n]{0,120}\bzu\b|"
        r"\b(?:Verzögerung|Wartezeit|Engpass|Aufwand)\w*\s+durch\b",
        re.IGNORECASE,
    )
    qualified = re.compile(
        r"\b(?:Hypothes\w*|hypothetisch\w*|unbestätigt\w*|vermut\w*|könnte\w*|möglicherweise|"
        r"vorläufig\w*|berichtet\w*|laut|falls|wenn|kann|können|soll\w*|würde\w*)\b|"
        r"nicht (?:belegt|nachgewiesen|bestätigt)",
        re.IGNORECASE,
    )

    def walk(value, path):
        if isinstance(value, dict):
            for name, child in value.items():
                if name not in {"cause_hypotheses", "hypotheses", "clarifications", "unknowns"}:
                    walk(child, f"{path}.{name}" if path else name)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
        elif isinstance(value, str):
            for sentence in re.split(r"[.;\n]", value):
                if causal.search(sentence) and not qualified.search(sentence):
                    findings.append(
                        f"{path}: unqualifizierte Kausalbehauptung; als berichtete "
                        "Beobachtung formulieren oder ausdrücklich unbestätigte Hypothese nennen."
                    )

    walk(draft, "")
    stages = draft.get("stages")
    keys = (
        [str(s.get("key") or "") for s in stages if isinstance(s, dict)]
        if isinstance(stages, list)
        else []
    )
    process = draft.get("process_analysis")
    flow = str(process.get("current_flow") or "") if isinstance(process, dict) else ""
    if len(keys) > 1 and all(
        key and re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", flow) for key in keys
    ):
        findings.append(
            "process_analysis.current_flow: Process Scope wiederholt alle Value-Stream-Phasen; "
            "auf die Fokusphase und deren belegte Teilschritte begrenzen."
        )
    return tuple(dict.fromkeys(findings))


def enforce_discovery_methodology(draft: dict, verifier: dict) -> dict:
    findings = discovery_methodical_findings(draft)
    if not findings:
        return verifier
    return {
        **verifier,
        "status": "repair",
        "checks": {**verifier["checks"], "source_grounding": False},
        "critical_findings": list(verifier.get("critical_findings") or [])
        + [{"code": "methodical_contract", "message": finding} for finding in findings],
        "repair_instructions": "\n".join([verifier.get("repair_instructions", ""), *findings]),
        "human_question": "",
    }


def discovery_modality_findings(draft: dict, evidence_text: str) -> tuple[str, ...]:
    """Catch newly introduced absolute wording in reported facts, like numeric grounding."""
    if not isinstance(draft, dict):
        return ()
    findings = []
    facts = draft.get("facts")
    if not isinstance(facts, list):
        return ()
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        text = str(fact.get("statement") or "").casefold()
        for term in ("ausgeschlossen", "verboten", "garantiert", "niemals"):
            if term in text and term not in evidence_text.casefold():
                findings.append(
                    f"facts[{index}].statement: absolute Modalität {term!r} ist im Input "
                    "nicht belegt; die Stärke der berichteten Aussage erhalten."
                )
    return tuple(findings)


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


def build_discovery_json_schema(schema_version=DISCOVERY_SCHEMA_VERSION) -> dict[str, Any]:
    if schema_version == strategic.SCHEMA:
        schema = build_discovery_json_schema(DISCOVERY_SCHEMA_VERSION_V2)
        props = schema["properties"]
        props["schema_version"]["enum"] = [strategic.SCHEMA]
        props["scope_basis"] = _object_schema(
            {key: _text_schema() for key in strategic.SCOPE_FIELDS}
        )
        schema["required"].append("scope_basis")
        clarification = props["clarifications"]["items"]
        clarification["properties"]["kind"] = {
            "type": "string",
            "enum": ["scope_decision", "evidence_collection"],
        }
        clarification["required"].append("kind")
        for obj, fields in [
            (props["stages"]["items"], strategic.STAGE_RATINGS),
            (props["focus"], strategic.FOCUS_RATINGS),
        ]:
            for field in fields:
                obj["properties"][field] = {"type": "string", "enum": [""]}
        props["stages"]["items"]["properties"]["time_to_value"]["enum"] = ["unknown"]
        return schema
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
            "bottlenecks": _text_schema(
                min_length=1 if schema_version == DISCOVERY_SCHEMA_VERSION else 0
            ),
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
                "schema_version": {"type": "string", "enum": [schema_version]},
                "value_stream": value_stream,
                "stages": {
                    "type": "array",
                    "minItems": 1,
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


def build_discovery_verifier_schema(
    schema_version=DISCOVERY_VERIFIER_SCHEMA_VERSION,
) -> dict[str, Any]:
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
                    "enum": [schema_version],
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
    schema_version: str = DISCOVERY_SCHEMA_VERSION,
) -> dict[str, Any]:
    errors: list[str] = []
    is_strategic = schema_version == strategic.SCHEMA
    root = _exact_fields(
        payload, _ROOT_FIELDS | ({"scope_basis"} if is_strategic else set()), "root", errors
    )
    if (
        schema_version
        not in {DISCOVERY_SCHEMA_VERSION, DISCOVERY_SCHEMA_VERSION_V2, strategic.SCHEMA}
        or root.get("schema_version") != schema_version
    ):
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
    ):
        if not isinstance(value, str) or (
            not value.strip()
            and not (
                is_strategic
                and path in {"process_analysis.scope_start", "process_analysis.scope_end"}
            )
        ):
            errors.append(f"{path}: Nichtleerer Text erforderlich.")

    bottlenecks = process.get("bottlenecks")
    if not isinstance(bottlenecks, str) or (
        schema_version == DISCOVERY_SCHEMA_VERSION and not bottlenecks.strip()
    ):
        errors.append("process_analysis.bottlenecks: Nichtleerer Text erforderlich.")

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
    if len(stages) > MAX_DISCOVERY_STAGES:
        errors.append(f"stages: Höchstens {MAX_DISCOVERY_STAGES} Phasen erlaubt.")
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
        allowed_stage_levels = {""} if is_strategic else set(ScreeningLevel.values)
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
        if is_strategic and stage.get("time_to_value") != TimeToValue.UNKNOWN:
            errors.append(f"stages[{index}].time_to_value: Explorative Schätzung unzulässig.")
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
    errors.extend(discovery_methodical_findings(root))
    if focus.get("recommended_stage_key") not in stage_keys:
        errors.append("focus.recommended_stage_key: Fokus verweist auf keine erzeugte Phase.")

    domains = {choice for choice, _label in BusinessDomain.choices}
    levels = {""} if is_strategic else {choice for choice, _label in ScreeningLevel.choices}
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

    if is_strategic:
        _exact_fields(
            root.get("scope_basis"), frozenset(strategic.SCOPE_FIELDS), "scope_basis", errors
        )
        for item in root.get("clarifications") or []:
            if isinstance(item, dict):
                _exact_fields(
                    item,
                    frozenset({"question", "impact", "kind", "blocking"}),
                    "clarification",
                    errors,
                )
                if not isinstance(item.get("blocking"), bool):
                    errors.append("clarification.blocking: Boolean erforderlich.")
            if not isinstance(item, dict) or item.get("kind") not in {
                "scope_decision",
                "evidence_collection",
            }:
                errors.append("clarifications.kind: Typisierte Scope-/Evidenzfrage erforderlich.")
            elif item["kind"] == "evidence_collection" and item.get("blocking") is not False:
                errors.append(
                    "clarifications: Evidenzerhebung darf keine Scopeentscheidung ersetzen."
                )
    _validate_numbers(root, evidence_text, errors)
    errors.extend(discovery_modality_findings(root, evidence_text))
    if errors:
        raise DiscoveryContractError(errors)
    return root


def validate_verifier_payload(
    payload: Any, schema_version=DISCOVERY_VERIFIER_SCHEMA_VERSION
) -> dict[str, Any]:
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
    if root.get("schema_version") != schema_version:
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
