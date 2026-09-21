from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.architecture.forms import (
    ProcessAnalysisForm,
    SolutionOptionForm,
    ValueStreamForm,
    ValueStreamStageForm,
    is_eligible_value_stream_owner,
)
from ki_radar.architecture.models import EvidenceBasis, TimeToValue
from ki_radar.use_cases.forms import UseCaseForm

from .scenario_blueprint import blueprint_checksum, load_blueprint_json

CONTRACT_PATH = Path(__file__).with_name("scenario_blueprints") / "contract.v1.json"


class BlueprintValidationError(ValueError):
    def __init__(self, errors: list[str] | tuple[str, ...]):
        self.errors = tuple(errors)
        super().__init__("Blueprint ungültig: " + " | ".join(self.errors))


@dataclass(frozen=True)
class ResolvedBlueprint:
    payload: dict[str, Any]
    checksum: str
    business_unit: BusinessUnit
    actors: dict[str, User]


def load_blueprint_contract() -> dict[str, Any]:
    return load_blueprint_json(CONTRACT_PATH)


def _as_dict(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{path}: Objekt erwartet.")
    return {}


def _as_list(value: Any, path: str, errors: list[str]) -> list[Any]:
    if isinstance(value, list):
        return value
    errors.append(f"{path}: Liste erwartet.")
    return []


def _fields(
    value: dict[str, Any],
    section: str,
    contract: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    allowed = set(contract["allowed_fields"][section])
    required = set(contract["required_fields"][section])
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if unknown:
        errors.append(f"{path}: Unbekannte Felder: {', '.join(unknown)}.")
    if missing:
        errors.append(f"{path}: Pflichtfelder fehlen: {', '.join(missing)}.")


def _section(
    value: Any,
    section: str,
    contract: dict[str, Any],
    path: str,
    errors: list[str],
) -> dict[str, Any]:
    result = _as_dict(value, path, errors)
    _fields(result, section, contract, path, errors)
    return result


def _nonempty(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: Nichtleere Zeichenkette erwartet.")


def _allowed(value: Any, path: str, allowed: list[str], errors: list[str]) -> None:
    if value not in allowed:
        errors.append(f"{path}: Ungültiger Wert {value!r}.")


def _key(
    value: Any,
    path: str,
    pattern: re.Pattern[str],
    max_length: int,
    errors: list[str],
) -> None:
    valid = isinstance(value, str) and len(value) <= max_length
    if not valid or pattern.fullmatch(value) is None:
        errors.append(f"{path}: Ungültiger stabiler Schlüssel.")


def _form_errors(label: str, form) -> list[str]:
    result = []
    for field, messages in form.errors.get_json_data().items():
        for message in messages:
            result.append(f"{label}.{field}: {message['message']}")
    return result


def _validate_references(
    payload: dict[str, Any],
    contract: dict[str, Any],
    errors: list[str],
) -> None:
    references = _section(payload.get("references"), "references", contract, "references", errors)
    unit = _section(
        references.get("business_unit"),
        "references.business_unit",
        contract,
        "references.business_unit",
        errors,
    )
    _nonempty(unit.get("name"), "references.business_unit.name", errors)
    actors = _section(
        references.get("actors"),
        "references.actors",
        contract,
        "references.actors",
        errors,
    )
    for role, value in actors.items():
        actor = _section(
            value,
            "user_reference",
            contract,
            f"references.actors.{role}",
            errors,
        )
        _nonempty(
            actor.get("username"),
            f"references.actors.{role}.username",
            errors,
        )


def _validate_value_stream(
    payload: dict[str, Any],
    contract: dict[str, Any],
    pattern: re.Pattern[str],
    max_length: int,
    errors: list[str],
) -> set[str]:
    stream = _section(
        payload.get("value_stream"),
        "value_stream",
        contract,
        "value_stream",
        errors,
    )
    _key(stream.get("key"), "value_stream.key", pattern, max_length, errors)
    _allowed(
        stream.get("status"),
        "value_stream.status",
        contract["allowed_states"]["value_stream.status"],
        errors,
    )
    focus = _section(
        stream.get("focus"),
        "value_stream.focus",
        contract,
        "value_stream.focus",
        errors,
    )
    _allowed(
        focus.get("status"),
        "value_stream.focus.status",
        contract["allowed_states"]["value_stream.focus.status"],
        errors,
    )
    _allowed(
        focus.get("business_domain"),
        "value_stream.focus.business_domain",
        contract["allowed_enums"]["business_domain"],
        errors,
    )
    stages = _as_list(stream.get("stages"), "value_stream.stages", errors)
    limits = contract["cardinality"]
    if not limits["stages_min"] <= len(stages) <= limits["stages_max"]:
        errors.append("value_stream.stages: Unzulässige Anzahl von Phasen.")
    keys: set[str] = set()
    sequences: set[int] = set()
    for index, value in enumerate(stages):
        path = f"value_stream.stages[{index}]"
        stage = _section(value, "value_stream.stage", contract, path, errors)
        stage_key = stage.get("key")
        _key(stage_key, f"{path}.key", pattern, max_length, errors)
        if isinstance(stage_key, str):
            if stage_key in keys:
                errors.append(f"{path}.key: Schlüssel mehrfach vorhanden.")
            keys.add(stage_key)
        sequence = stage.get("sequence")
        valid_sequence = isinstance(sequence, int) and not isinstance(sequence, bool)
        if not valid_sequence or sequence < 1:
            errors.append(f"{path}.sequence: Positive Ganzzahl erwartet.")
        elif sequence in sequences:
            errors.append(f"{path}.sequence: Reihenfolge mehrfach vorhanden.")
        else:
            sequences.add(sequence)
    return keys


def _validate_process_and_options(
    payload: dict[str, Any],
    contract: dict[str, Any],
    pattern: re.Pattern[str],
    max_length: int,
    stage_keys: set[str],
    errors: list[str],
) -> tuple[dict[str, Any], set[str]]:
    process = _section(
        payload.get("process_analysis"),
        "process_analysis",
        contract,
        "process_analysis",
        errors,
    )
    _key(process.get("key"), "process_analysis.key", pattern, max_length, errors)
    _allowed(
        process.get("status"),
        "process_analysis.status",
        contract["allowed_states"]["process_analysis.status"],
        errors,
    )
    if process.get("stage_key") not in stage_keys:
        errors.append("process_analysis.stage_key: Unbekannte Phase.")

    options = _as_list(payload.get("solution_options"), "solution_options", errors)
    limits = contract["cardinality"]
    if not limits["solution_options_min"] <= len(options) <= limits["solution_options_max"]:
        errors.append("solution_options: Unzulässige Anzahl von Lösungsoptionen.")
    option_keys: set[str] = set()
    for index, value in enumerate(options):
        path = f"solution_options[{index}]"
        option = _section(value, "solution_option", contract, path, errors)
        option_key = option.get("key")
        _key(option_key, f"{path}.key", pattern, max_length, errors)
        if isinstance(option_key, str):
            if option_key in option_keys:
                errors.append(f"{path}.key: Schlüssel mehrfach vorhanden.")
            option_keys.add(option_key)
        for field, state_key in (
            ("recommendation", "solution_options[].recommendation"),
            ("evaluation_status", "solution_options[].evaluation_status"),
        ):
            _allowed(
                option.get(field),
                f"{path}.{field}",
                contract["allowed_states"][state_key],
                errors,
            )
        for field, enum_key in (
            ("option_type", "solution_option.option_type"),
            ("feasibility", "solution_option.feasibility"),
            ("integration_effort", "solution_option.integration_effort"),
        ):
            _allowed(
                option.get(field),
                f"{path}.{field}",
                contract["allowed_enums"][enum_key],
                errors,
            )
    return process, option_keys


def _validate_use_case(
    payload: dict[str, Any],
    contract: dict[str, Any],
    pattern: re.Pattern[str],
    max_length: int,
    errors: list[str],
) -> None:
    use_case = _section(payload.get("use_case"), "use_case", contract, "use_case", errors)
    _key(use_case.get("key"), "use_case.key", pattern, max_length, errors)
    for field, state_key in (
        ("status", "use_case.status"),
        ("decision_status", "use_case.decision_status"),
    ):
        _allowed(
            use_case.get(field),
            f"use_case.{field}",
            contract["allowed_states"][state_key],
            errors,
        )
    for field, enum_key in (
        ("priority", "use_case.priority"),
        ("solution_type", "use_case.solution_type"),
        ("hosting_type", "use_case.hosting_type"),
        ("business_value", "level"),
        ("technical_feasibility", "level"),
        ("data_readiness", "level"),
        ("risk_complexity", "level"),
    ):
        _allowed(
            use_case.get(field),
            f"use_case.{field}",
            contract["allowed_enums"][enum_key],
            errors,
        )
    metric = _section(
        use_case.get("metric"),
        "use_case.metric",
        contract,
        "use_case.metric",
        errors,
    )
    for field, enum_key in (
        ("type", "use_case.metric.type"),
        ("direction", "use_case.metric.direction"),
    ):
        _allowed(
            metric.get(field),
            f"use_case.metric.{field}",
            contract["allowed_enums"][enum_key],
            errors,
        )
    classification = _section(
        use_case.get("classification"),
        "use_case.classification",
        contract,
        "use_case.classification",
        errors,
    )
    _allowed(
        classification.get("business_domain"),
        "use_case.classification.business_domain",
        contract["allowed_enums"]["business_domain"],
        errors,
    )


def _validate_structure(payload: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = set(contract["required_top_level"])
    unknown = sorted(set(payload) - expected)
    missing = sorted(expected - set(payload))
    if unknown:
        errors.append(f"root: Unbekannte Felder: {', '.join(unknown)}.")
    if missing:
        errors.append(f"root: Pflichtfelder fehlen: {', '.join(missing)}.")
    if payload.get("schema_version") != contract["schema_version"]:
        errors.append(f"schema_version: Nur Version {contract['schema_version']} wird unterstützt.")
    pattern = re.compile(contract["keys"]["pattern"])
    max_length = int(contract["keys"]["max_length"])
    _key(payload.get("scenario_key"), "scenario_key", pattern, max_length, errors)
    _nonempty(payload.get("scenario_name"), "scenario_name", errors)
    _validate_references(payload, contract, errors)
    stage_keys = _validate_value_stream(payload, contract, pattern, max_length, errors)
    process, option_keys = _validate_process_and_options(
        payload,
        contract,
        pattern,
        max_length,
        stage_keys,
        errors,
    )
    _validate_use_case(payload, contract, pattern, max_length, errors)
    origin = _section(payload.get("origin"), "origin", contract, "origin", errors)
    if origin.get("stage_key") not in stage_keys:
        errors.append("origin.stage_key: Unbekannte Phase.")
    if origin.get("process_analysis_key") != process.get("key"):
        errors.append("origin.process_analysis_key: Unbekannte Prozessanalyse.")
    if origin.get("solution_option_key") not in option_keys:
        errors.append("origin.solution_option_key: Unbekannte Lösungsoption.")
    return errors


def _resolve_references(
    payload: dict[str, Any], errors: list[str]
) -> tuple[BusinessUnit | None, dict[str, User]]:
    references = payload["references"]
    unit_name = references["business_unit"]["name"]
    units = BusinessUnit.objects.filter(name=unit_name)
    unit = units.first() if units.count() == 1 else None
    if unit is None:
        errors.append(
            "references.business_unit.name: Organisationseinheit fehlt oder ist nicht eindeutig."
        )
    elif not unit.is_active:
        errors.append("references.business_unit.name: Organisationseinheit ist inaktiv.")

    actors: dict[str, User] = {}
    for role, actor_ref in references["actors"].items():
        users = User.objects.filter(username=actor_ref["username"])
        user = users.first() if users.count() == 1 else None
        if user is None:
            errors.append(
                f"references.actors.{role}.username: Benutzer fehlt oder ist nicht eindeutig."
            )
        elif not user.is_active or user.is_anonymized:
            errors.append(
                f"references.actors.{role}.username: Benutzer ist inaktiv oder anonymisiert."
            )
        else:
            actors[role] = user
    owner = actors.get("value_stream_owner")
    if owner is not None and not is_eligible_value_stream_owner(owner):
        errors.append(
            "references.actors.value_stream_owner: Benutzer ist nicht als "
            "Value-Stream-Owner berechtigt."
        )
    return unit, actors


def _pick(source: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: source[field] for field in fields}


def _validate_forms(
    payload: dict[str, Any], unit: BusinessUnit, actors: dict[str, User]
) -> list[str]:
    errors: list[str] = []
    stream = payload["value_stream"]
    focus = stream["focus"]
    stream_data = _pick(
        stream,
        (
            "name",
            "status",
            "description",
            "trigger",
            "outcome",
            "scope_in",
            "scope_out",
            "strategic_objective",
            "stakeholders",
            "constraints",
        ),
    )
    stream_data.update(
        {
            "business_unit": unit.pk,
            "owner": actors["value_stream_owner"].pk,
            "business_domain": focus["business_domain"],
            "capability": focus["capability"],
            "strategic_impact": "",
            "economic_potential": "",
            "pain_intensity": "",
            "data_accessibility": "",
            "change_effort": "",
            "focus_status": focus["status"],
            "focus_rationale": "",
        }
    )
    form = ValueStreamForm(data=stream_data)
    if not form.is_valid():
        errors.extend(_form_errors("value_stream", form))

    stage_fields = (
        "sequence",
        "name",
        "description",
        "actors",
        "systems",
        "documents",
        "pain_points",
        "baseline_metrics",
    )
    for index, stage in enumerate(stream["stages"]):
        form = ValueStreamStageForm(data=_pick(stage, stage_fields))
        if not form.is_valid():
            errors.extend(_form_errors(f"value_stream.stages[{index}]", form))

    process = payload["process_analysis"]
    process_fields = (
        "name",
        "status",
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
        "exceptions",
        "baseline_metrics",
        "target_state_principles",
    )
    form = ProcessAnalysisForm(data=_pick(process, process_fields))
    if not form.is_valid():
        errors.extend(_form_errors("process_analysis", form))

    option_fields = (
        "name",
        "option_type",
        "evaluation_status",
        "description",
        "expected_value",
        "bottleneck_coverage",
        "feasibility",
        "data_requirements",
        "application_impact",
        "integration_effort",
        "integration_impact",
        "technology_constraints",
        "risks",
        "architecture_fit",
    )
    for index, option in enumerate(payload["solution_options"]):
        option_data = _pick(option, option_fields)
        option_data.update(
            {
                "evidence_basis": EvidenceBasis.HYPOTHESIS,
                "time_to_value": TimeToValue.NOT_ASSESSED,
            }
        )
        form = SolutionOptionForm(data=option_data)
        if not form.is_valid():
            errors.extend(_form_errors(f"solution_options[{index}]", form))

    use_case = payload["use_case"]
    metric = use_case["metric"]
    classification = use_case["classification"]
    use_case_fields = (
        "title",
        "summary",
        "problem_statement",
        "affected_process",
        "target_users",
        "priority",
        "solution_type",
        "hosting_type",
        "provider",
        "product_name",
        "model_name",
        "source_systems",
        "data_sources",
        "interface_description",
        "intended_users",
        "intended_purpose",
        "expected_benefit",
        "benefit_category",
        "one_time_cost",
        "recurring_cost",
        "business_value",
        "technical_feasibility",
        "data_readiness",
        "risk_complexity",
        "human_oversight",
        "support_responsibility",
    )
    use_case_data = _pick(use_case, use_case_fields)
    use_case_data.update(
        {
            "business_unit": unit.pk,
            "business_domain": classification["business_domain"],
            "business_capability": classification["capability"],
            "process_area": classification["process_area"],
            "business_owner": actors["business_owner"].pk,
            "coordinator": actors["coordinator"].pk,
            "technical_owner": actors["technical_owner"].pk,
            "metric_name": metric["name"],
            "metric_type": metric["type"],
            "metric_direction": metric["direction"],
            "metric_unit": metric["unit"],
            "metric_baseline": metric["baseline"],
            "metric_target": metric["target"],
            "metric_measurement_method": metric["measurement_method"],
        }
    )
    form = UseCaseForm(data=use_case_data)
    if not form.is_valid():
        errors.extend(_form_errors("use_case", form))
    return errors


def validate_blueprint(payload: dict[str, Any]) -> ResolvedBlueprint:
    contract = load_blueprint_contract()
    errors = _validate_structure(payload, contract)
    if errors:
        raise BlueprintValidationError(errors)
    unit, actors = _resolve_references(payload, errors)
    required_roles = contract["references"]["users"]["required_roles"]
    if unit is not None and len(actors) == len(required_roles):
        errors.extend(_validate_forms(payload, unit, actors))
    if errors or unit is None:
        raise BlueprintValidationError(errors)
    return ResolvedBlueprint(
        payload=payload,
        checksum=blueprint_checksum(payload),
        business_unit=unit,
        actors=actors,
    )
