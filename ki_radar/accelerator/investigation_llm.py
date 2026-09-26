from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from ki_radar.core.openrouter import OpenRouterUnavailable, request_openrouter

from .investigation_evidence import (
    cost_to_microunits,
    mark_provider_attempt_uncertain,
    max_reservable_output_tokens,
    reserve_provider_attempt,
    settle_provider_attempt,
)
from .investigation_models import (
    InvestigationEvidenceCampaign,
    InvestigationModelCall,
    InvestigationRun,
    InvestigationSource,
    InvestigationStep,
    InvestigationVerifierReport,
)
from .investigation_policy import POLICY_VERSION, is_evidence_claim
from .investigation_prompts import (
    PLANNER_INSTRUCTION,
    PLANNER_PROMPT_VERSION,
    PLANNER_SCHEMA_VERSION,
    SYNTHESIS_INSTRUCTION,
    SYNTHESIS_PROMPT_VERSION,
    SYNTHESIS_SCHEMA_VERSION,
    TOOL_PARAMETER_CONTRACTS,
    VERIFIER_INSTRUCTION,
    VERIFIER_PROMPT_VERSION,
    VERIFIER_SCHEMA_VERSION,
    planner_response_format,
    synthesis_response_format,
    verifier_response_format,
)
from .investigation_runtime import (
    ALLOWED_TOOLS,
    BUDGET_VERSION,
    ENDPOINT_CAPABILITY,
    FIXED_ROUTE_VERSION,
    ISSUE4_INVESTIGATION_PROVIDER_POLICY,
    LOOP_VERSION,
    MIN_PLANNER_COMPLETION_TOKENS,
    MIN_PLANNER_TIMEOUT_SECONDS,
    MIN_VERIFIER_COMPLETION_TOKENS,
    MIN_VERIFIER_TIMEOUT_SECONDS,
    TOOL_SCHEMA_VERSION,
    InvestigationRunError,
    _remaining_synthesis_reserve,
    _remaining_verifier_reserve,
    assert_active,
    assert_actor_can_edit_run,
    assert_executor,
    budget_exhausted,
    canonical_json,
    content_hash,
    elapsed_seconds,
    evaluate_run_policy,
    execute_tool_step,
    locked_run,
    normalize_claim_register,
    normalize_tool_parameters,
    reference_valid,
)
from .investigation_tools import (
    TOOL_VERSION,
    InvestigationToolError,
    list_sources,
    replay_tool_result,
)


@dataclass(frozen=True)
class PlannerAction:
    action: str
    target_claim_id: str
    expected_discriminating_finding: str
    rationale: str
    tool_name: str
    parameters: Mapping[str, Any]
    claim_register: tuple[Mapping[str, Any], ...] | None
    brief_payload: Mapping[str, Any] | None
    source_relevance: Mapping[str, Mapping[str, Any]]
    progress_kind: str
    progress_payload: Mapping[str, Any]
    clarification_reason: str
    clarification_payload: Mapping[str, Any]


def _decode_structured_field(
    payload: Mapping[str, Any],
    field: str,
    *,
    expected_type: type | tuple[type, ...],
    default: Any,
) -> Any:
    """Decode an opaque strict-schema field while retaining the domain payload shape."""
    value = payload.get(field, default)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise InvestigationRunError(
                f"Das strukturierte Feld '{field}' enthält kein gültiges JSON.",
                code="invalid_response",
            ) from exc
    # Strict schemas require every transport field, including fields unused by
    # this action. Providers may encode their empty value as JSON null (inside
    # the string or as a native value). Keep null's "unchanged" meaning for
    # claim_register/brief_payload; only empty object fields use their default.
    if value is None and isinstance(default, Mapping):
        value = default
    # An empty relevance list carries no decisions and is safely equivalent to
    # an empty mapping. Nonempty lists still fail the contract.
    if field == "source_relevance" and value == []:
        value = {}
    if not isinstance(value, expected_type):
        raise InvestigationRunError(
            f"Das strukturierte Feld '{field}' hat den falschen Typ ({type(value).__name__}).",
            code="invalid_response",
        )
    return value


def _validate_investigation_action(run: InvestigationRun, payload: Mapping[str, Any]) -> None:
    required_fields = {
        "action",
        "target_claim_id",
        "expected_discriminating_finding",
        "rationale",
        "tool_name",
        "parameters",
        "clarification_reason",
        "clarification_payload",
    }
    unknown = sorted(set(payload) - required_fields)
    missing = sorted(required_fields - set(payload))
    if unknown or missing:
        details = []
        if missing:
            details.append("fehlend: " + ", ".join(missing))
        if unknown:
            details.append("unbekannt: " + ", ".join(unknown))
        raise InvestigationRunError(
            "Planner-Antwort verletzt den Top-Level-Vertrag (" + "; ".join(details) + ").",
            code="invalid_response",
        )
    if not isinstance(payload.get("parameters"), Mapping):
        raise InvestigationRunError(
            "Planner-Feld 'parameters' muss ein JSON-Objekt sein.",
            code="invalid_response",
        )
    if not isinstance(payload.get("clarification_payload"), Mapping):
        raise InvestigationRunError(
            "Planner-Feld 'clarification_payload' muss ein JSON-Objekt sein.",
            code="invalid_response",
        )
    if payload.get("action") not in {"tool", "synthesize", "clarify"}:
        raise InvestigationRunError("Ungültige Untersuchungsaktion.", code="invalid_planner_action")
    if payload.get("action") == "synthesize" and (
        str(payload.get("tool_name") or "")
        or payload["parameters"]
    ):
        raise InvestigationRunError(
            "Synthese darf kein Werkzeug oder Parameter enthalten.",
            code="invalid_planner_action",
        )
    if payload.get("action") == "tool":
        tool_name = str(payload.get("tool_name") or "")
        if tool_name not in ALLOWED_TOOLS:
            raise InvestigationRunError("Nicht erlaubtes Werkzeug.", code="tool_not_allowed")
        normalized = normalize_tool_parameters(
            tool_name,
            payload["parameters"],
            allowed_source_ids=frozenset(
                str(source_id)
                for source_id in run.source_snapshot.sources.values_list("pk", flat=True)
            ),
        )
        if tool_name in {"read_source", "profile_csv", "compare_groups"}:
            source = run.source_snapshot.sources.get(pk=normalized["source_id"])
            if (
                tool_name in {"profile_csv", "compare_groups"}
                and source.source_type != InvestigationSource.SourceType.CSV
            ):
                raise InvestigationRunError(
                    "CSV-Quelle erforderlich.", code="invalid_tool_parameters"
                )
            if source.source_type == InvestigationSource.SourceType.CSV:
                columns = set(normalized.get("columns") or [])
                if tool_name == "compare_groups":
                    columns.add(normalized["group_by"])
                    columns.update(item["column"] for item in normalized["filters"])
                    columns.update(
                        value
                        for value in (normalized["value_column"], normalized["unit_column"])
                        if value is not None
                    )
                if missing := sorted(columns - set(source.columns)):
                    raise InvestigationRunError(
                        f"Unbekannte CSV-Spalten: {', '.join(missing)}.",
                        code="invalid_tool_parameters",
                    )


def _validate_synthesis_package(run: InvestigationRun, payload: Mapping[str, Any]) -> None:
    reason = payload.get("clarification_reason", "")
    if reason not in {"", "missing_evidence"}:
        raise InvestigationRunError("Ungültiger Klärungsgrund.", code="invalid_reason_code")

    investigation_request = _decode_structured_field(
        payload, "investigation_request", expected_type=Mapping, default={}
    )
    if investigation_request:
        if reason:
            raise InvestigationRunError(
                (
                    "Interne Untersuchung und menschliche Klärung dürfen nicht "
                    "gleichzeitig angefordert werden."
                ),
                code="invalid_response",
            )
        if not str(investigation_request.get("goal") or "").strip():
            raise InvestigationRunError(
                "Interne Untersuchung benötigt ein konkretes Untersuchungsziel.",
                code="invalid_response",
            )
        return

    if reason == "missing_evidence":
        clarification = _decode_structured_field(
            payload, "clarification_payload", expected_type=Mapping, default={}
        )
        if not str(clarification.get("question") or "").strip():
            raise InvestigationRunError(
                "Klärung benötigt eine konkrete Frage.", code="invalid_response"
            )
        return

    claims = _decode_structured_field(payload, "claim_register", expected_type=list, default=[])
    brief = _decode_structured_field(payload, "brief_payload", expected_type=Mapping, default={})
    relevance = _decode_structured_field(
        payload, "source_relevance", expected_type=Mapping, default={}
    )
    if not claims or not brief or not relevance:
        raise InvestigationRunError(
            "Die Synthese benötigt ein vollständiges Package.", code="invalid_response"
        )

    source_ids = {str(pk) for pk in run.source_snapshot.sources.values_list("pk", flat=True)}
    if set(relevance) != source_ids:
        raise InvestigationRunError(
            "Die Synthese muss jede Manifestquelle relevant/irrelevant klassifizieren.",
            code="source_relevance_incomplete",
        )
    observed_source_ids = {
        str(step.parameters.get("source_id") or "")
        for step in run.steps.filter(
            status=InvestigationStep.Status.SUCCESS,
            tool_name__in={"read_source", "profile_csv", "compare_groups"},
        )
    }
    for source_id, item in relevance.items():
        if not isinstance(item, Mapping) or not isinstance(item.get("relevant"), bool):
            raise InvestigationRunError(
                "Quellenklassifikation benötigt relevant=true|false.",
                code="invalid_source_relevance",
            )
        reference = item.get("reference")
        if reference is not None and (
            not isinstance(reference, Mapping) or not reference_valid(run, reference)
        ):
            raise InvestigationRunError(
                "Optionale Relevanzreferenz ist ungültig.",
                code="invalid_source_relevance",
            )
        if bool(item.get("relevant")) and source_id not in observed_source_ids:
            raise InvestigationRunError(
                "Als relevant markierte Quelle wurde nicht gelesen oder analysiert.",
                code="source_relevance_unobserved",
            )

    previous_ids = {item["claim_id"] for item in run.claim_register}
    proposed_ids = {str(item.get("claim_id")) for item in claims if isinstance(item, Mapping)}
    replacement_targets = {
        str(metadata.get("replaces_claim_id") or "").strip()
        for item in claims
        if isinstance(item, Mapping)
        and isinstance((metadata := item.get("metadata")), Mapping)
        and str(metadata.get("replaces_claim_id") or "").strip()
    }
    if missing := sorted(previous_ids - proposed_ids - replacement_targets):
        raise InvestigationRunError(
            "Bestehende Claims dürfen nicht ohne expliziten Ersatz verschwinden: "
            + ", ".join(missing),
            code="invalid_claim",
        )
    normalize_claim_register(run, claims)
    if missing_sections := sorted(set(run.brief_payload) - set(brief)):
        raise InvestigationRunError(
            "Bestehende Brief-Abschnitte dürfen nicht verschwinden: " + ", ".join(missing_sections),
            code="invalid_brief",
        )


def _requested_model() -> str:
    return str(getattr(settings, "OPENROUTER_MODEL", os.getenv("OPENROUTER_MODEL", "")) or "")


def _instruction_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _assert_frozen_execution_contract(run: InvestigationRun) -> None:
    frozen = run.execution_snapshot
    if (
        run.loop_version != LOOP_VERSION
        or run.policy_version != POLICY_VERSION
        or run.budget_version != BUDGET_VERSION
        or frozen.get("loop_version") != LOOP_VERSION
        or frozen.get("policy_version") != POLICY_VERSION
        or frozen.get("budget_version") != BUDGET_VERSION
    ):
        raise InvestigationRunError(
            "Die fixierte Ausführungsversion ist nicht mehr verfügbar.",
            code="execution_version_unavailable",
        )

    if run.execution_mode == "fixed" and frozen.get("fixed_route_version") != FIXED_ROUTE_VERSION:
        raise InvestigationRunError(
            "Die fixierte Kontrollstrecke ist nicht mehr verfügbar.",
            code="execution_version_unavailable",
        )

    tools = frozen.get("tools") or {}
    if (
        tools.get("implementation_version") != TOOL_VERSION
        or set(tools.get("allowlist") or []) != set(ALLOWED_TOOLS)
        or tools.get("schema_version") != TOOL_SCHEMA_VERSION
        or tools.get("parameter_contracts") != TOOL_PARAMETER_CONTRACTS
    ):
        raise InvestigationRunError(
            "Der fixierte Werkzeugvertrag hat sich geändert.",
            code="execution_version_unavailable",
        )

    planner = frozen.get("planner") or {}
    synthesizer = frozen.get("synthesizer") or {}
    verifier = frozen.get("verifier") or {}
    if (
        planner.get("prompt_version") != PLANNER_PROMPT_VERSION
        or planner.get("instruction_hash") != _instruction_hash(PLANNER_INSTRUCTION)
        or planner.get("schema_version") != PLANNER_SCHEMA_VERSION
        or synthesizer.get("prompt_version") != SYNTHESIS_PROMPT_VERSION
        or synthesizer.get("instruction_hash") != _instruction_hash(SYNTHESIS_INSTRUCTION)
        or synthesizer.get("schema_version") != SYNTHESIS_SCHEMA_VERSION
        or verifier.get("prompt_version") != VERIFIER_PROMPT_VERSION
        or verifier.get("instruction_hash") != _instruction_hash(VERIFIER_INSTRUCTION)
        or verifier.get("schema_version") != VERIFIER_SCHEMA_VERSION
    ):
        raise InvestigationRunError(
            "Ein fixierter Prompt-/Schema-Vertrag hat sich geändert.",
            code="execution_version_unavailable",
        )

    transport = frozen.get("model_transport") or {}
    if (
        transport.get("requested_model", "") != _requested_model()
        or transport.get("provider_policy") != ISSUE4_INVESTIGATION_PROVIDER_POLICY
        or transport.get("endpoint_capability") != ENDPOINT_CAPABILITY
        or (
            transport.get("requested_model")
            and transport.get("requested_model") != ENDPOINT_CAPABILITY["model"]
        )
    ):
        raise InvestigationRunError(
            "Der für den Run fixierte Modell-/Providervertrag ist nicht mehr aktiv.",
            code="execution_version_unavailable",
        )


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _usage_tokens(result, messages: list[dict[str, str]]) -> tuple[int, int, int]:
    prompt = result.usage.get("prompt_tokens")
    completion = result.usage.get("completion_tokens")
    try:
        prompt_tokens = (
            int(prompt)
            if prompt is not None
            else _estimate_tokens("".join(message["content"] for message in messages))
        )
    except (TypeError, ValueError):
        prompt_tokens = _estimate_tokens("".join(message["content"] for message in messages))
    try:
        completion_tokens = (
            int(completion) if completion is not None else _estimate_tokens(result.content)
        )
    except (TypeError, ValueError):
        completion_tokens = _estimate_tokens(result.content)
    return prompt_tokens, completion_tokens, prompt_tokens + completion_tokens


def _pending_synthesis_investigation(run: InvestigationRun) -> dict[str, str]:
    """Return an unresolved tool-addressable gap raised by the latest synthesis."""
    latest = (
        run.model_calls.filter(
            role=InvestigationModelCall.Role.SYNTHESIZER,
            status=InvestigationModelCall.Status.SUCCESS,
        )
        .order_by("-created_at")
        .first()
    )
    if latest is None:
        return {}
    raw = latest.accepted_payload.get("investigation_request")
    if not isinstance(raw, Mapping):
        return {}
    goal = str(raw.get("goal") or "").strip()
    if not goal:
        return {}
    if run.steps.filter(
        status=InvestigationStep.Status.SUCCESS,
        created_at__gt=latest.created_at,
    ).exists():
        return {}
    if run.input_revisions.filter(created_at__gt=latest.created_at).exists():
        return {}
    return {
        "goal": goal,
        "reason": str(raw.get("reason") or "").strip(),
    }


def _planner_context(actor, run: InvestigationRun) -> dict[str, Any]:
    sources = list_sources(actor=actor, snapshot_id=run.source_snapshot_id)
    pending_investigation = _pending_synthesis_investigation(run)
    latest_verifier = run.verifier_reports.order_by("-revision").first()
    previous_call = run.model_calls.order_by("-created_at").first()
    last_planner_error: dict[str, str] = {}
    if (
        previous_call is not None
        and previous_call.role
        in {InvestigationModelCall.Role.PLANNER, InvestigationModelCall.Role.SYNTHESIZER}
        and previous_call.status == InvestigationModelCall.Status.FAILED
        and previous_call.error_code == "invalid_response"
    ):
        diagnostics = previous_call.effective_parameters.get("response_diagnostics") or {}
        last_planner_error = {
            "code": previous_call.error_code,
            "detail": str(diagnostics.get("structured_contract_error") or "")[:250],
        }
    return {
        "phase": "investigation",
        "synthesis_investigation_request": pending_investigation,
        "decision_question": run.decision_question,
        "process_context": run.source_snapshot.process_context,
        "sources": [
            {
                "source_id": str(item.source_id),
                "filename": item.filename,
                "source_type": item.source_type,
                "row_count": item.row_count,
                "columns": list(item.columns),
                "content_sha256": item.content_sha256,
            }
            for item in sources.sources
        ],
        "tool_parameter_contracts": (run.execution_snapshot.get("tools") or {}).get(
            "parameter_contracts", {}
        ),
        "last_planner_error": last_planner_error,
        "claim_register": run.claim_register,
        "source_relevance": run.source_relevance,
        "brief_payload": run.brief_payload,
        "recent_steps": [
            {
                "sequence": step.sequence,
                "tool_name": step.tool_name,
                "parameters": step.parameters,
                "result_payload": step.result_payload,
                "progress_kind": step.progress_kind,
                "progress_payload": step.progress_payload,
            }
            for step in run.steps.order_by("-sequence")
        ],
        "input_revisions": [
            {
                "revision": item.revision,
                "payload": item.payload,
                "payload_hash": item.payload_hash,
            }
            for item in run.input_revisions.order_by("revision")
        ],
        "usage": run.usage,
        "budget_limits": run.budget_limits,
        "policy_blockers": list(evaluate_run_policy(run).blockers),
        "latest_verifier": (
            {
                "success": latest_verifier.success,
                "findings": latest_verifier.findings,
                "source_references_valid": latest_verifier.source_references_valid,
                "checked_critical_claims": latest_verifier.checked_critical_claims,
                "bound_hashes": latest_verifier.bound_hashes,
            }
            if latest_verifier is not None
            else {}
        ),
    }


def _investigation_context(actor, run: InvestigationRun) -> dict[str, Any]:
    context = _planner_context(actor, run)
    for field in ("claim_register", "brief_payload", "source_relevance"):
        context.pop(field)
    context["recent_steps"] = context["recent_steps"][:5]
    context["evidence_coverage"] = {
        "data_check_executed": run.data_check_executed,
        "counterevidence_search_executed": run.counterevidence_search_executed,
        "counterevidence_hits_processed": run.counterevidence_hits_processed,
    }
    return context


def _deterministic_analysis_replays(actor, run: InvestigationRun) -> list[dict[str, Any]]:
    replays: list[dict[str, Any]] = []
    for step in run.steps.filter(
        status=InvestigationStep.Status.SUCCESS,
        tool_name__in=["profile_csv", "compare_groups"],
    ).order_by("sequence"):
        result_id = step.result_ref.get("tool_result_id")
        if not result_id:
            replays.append(
                {
                    "step_sequence": step.sequence,
                    "tool_name": step.tool_name,
                    "result_id": "",
                    "matches": False,
                    "stored_hash": "",
                    "replay_hash": "",
                    "mismatch_fields": ["missing_result_ref"],
                }
            )
            continue
        try:
            replay = replay_tool_result(actor=actor, result_id=result_id)
            replays.append(
                {
                    "step_sequence": step.sequence,
                    "tool_name": replay.tool_name,
                    "result_id": str(replay.result_id),
                    "source_id": str(replay.source_id),
                    "source_hash": replay.source_hash,
                    "matches": replay.matches,
                    "stored_hash": replay.stored_hash,
                    "replay_hash": replay.replay_hash,
                    "mismatch_fields": list(replay.mismatch_fields),
                }
            )
        except InvestigationToolError as exc:
            replays.append(
                {
                    "step_sequence": step.sequence,
                    "tool_name": step.tool_name,
                    "result_id": str(result_id),
                    "matches": False,
                    "stored_hash": "",
                    "replay_hash": "",
                    "mismatch_fields": [exc.code],
                }
            )
    return replays


def _apply_replay_findings(
    payload: Mapping[str, Any],
    analysis_replays: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = dict(payload)
    findings = [dict(item) for item in normalized.get("findings", []) if isinstance(item, Mapping)]
    for replay in analysis_replays:
        if replay.get("matches"):
            continue
        findings.append(
            {
                "severity": "critical",
                "code": "deterministic_analysis_replay_mismatch",
                "claim_id": "",
                "message": (
                    "Eine gespeicherte deterministische Analyse konnte aus ihren "
                    "eingefrorenen Eingaben nicht identisch reproduziert werden."
                ),
                "result_id": replay.get("result_id", ""),
                "tool_name": replay.get("tool_name", ""),
                "mismatch_fields": replay.get("mismatch_fields", []),
            }
        )
    normalized["findings"] = findings
    return normalized


def _verifier_context(
    run: InvestigationRun,
    *,
    analysis_replays: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "decision_question": run.decision_question,
        "process_context": run.source_snapshot.process_context,
        "claim_register": run.claim_register,
        "source_relevance": run.source_relevance,
        "brief_payload": run.brief_payload,
        "analysis_replays": list(analysis_replays or []),
        "tool_trace": [
            {
                "sequence": step.sequence,
                "tool_name": step.tool_name,
                "parameters": step.parameters,
                "result_ref": step.result_ref,
                "result_hash": step.result_hash,
            }
            for step in run.steps.filter(status=InvestigationStep.Status.SUCCESS).order_by(
                "sequence"
            )
        ],
        "bound_hashes": {
            "contract": run.contract_hash,
            "manifest": run.manifest_hash,
            "register": run.register_hash,
            "brief": run.brief_hash,
        },
    }


@transaction.atomic
def _reserve_model_call(
    *,
    actor,
    run_id,
    executor_token,
    role: str,
    instruction: str,
    prompt_version: str,
    schema_version: str,
    context: Mapping[str, Any],
    response_format: dict[str, Any] | None = None,
) -> InvestigationModelCall:
    run = locked_run(actor=actor, run_id=run_id)
    assert_active(run)
    assert_executor(run, executor_token)
    if run.status != InvestigationRun.Status.RUNNING:
        raise InvestigationRunError(
            "Der Run wartet auf menschliche Klärung.",
            code="human_input_required",
        )
    _assert_frozen_execution_contract(run)

    prompt_payload = {"instruction": instruction, "context": dict(context)}
    prompt_token_reservation = _estimate_tokens(canonical_json(prompt_payload))
    # UTF-8 bytes (including the response schema) conservatively bound context
    # tokens without changing the existing usage reservation and safety limits.
    response_schema = response_format or (
        planner_response_format()
        if role == InvestigationModelCall.Role.PLANNER
        else synthesis_response_format()
        if role == InvestigationModelCall.Role.SYNTHESIZER
        else verifier_response_format()
    )
    context_token_bound = (
        len(
            (instruction + canonical_json(context) + canonical_json(response_schema)).encode(
                "utf-8"
            )
        )
        + 32
    )
    context_room = ENDPOINT_CAPABILITY["context_tokens"] - context_token_bound

    usage = dict(run.usage)
    remaining_input = run.budget_limits["max_input_tokens"] - int(usage.get("input_tokens", 0))
    remaining_output = run.budget_limits["max_output_tokens"] - int(usage.get("output_tokens", 0))
    if prompt_token_reservation > remaining_input or remaining_output <= 0:
        raise InvestigationRunError(
            "Das verbleibende Tokenbudget reicht für keinen weiteren Modellaufruf.",
            code="budget_exhausted",
        )
    completion_floor = (
        MIN_PLANNER_COMPLETION_TOKENS
        if role != InvestigationModelCall.Role.VERIFIER
        else MIN_VERIFIER_COMPLETION_TOKENS
    )
    timeout_floor = (
        MIN_PLANNER_TIMEOUT_SECONDS
        if role != InvestigationModelCall.Role.VERIFIER
        else MIN_VERIFIER_TIMEOUT_SECONDS
    )
    verifier_reserve = _remaining_verifier_reserve(run)
    if role == InvestigationModelCall.Role.PLANNER:
        synthesis_reserve = _remaining_synthesis_reserve(run)
        verifier_reserve = {
            **verifier_reserve,
            **{key: verifier_reserve[key] + synthesis_reserve[key] for key in verifier_reserve},
        }
    if role == InvestigationModelCall.Role.VERIFIER:
        # Allocate one equal share of the reserved verifier time to this call;
        # protect the remaining shares for reads, rechecks and repair.
        remaining_verifier_calls = max(
            1, run.budget_limits["max_verifier_calls"] - usage["verifier_calls"]
        )
        current_input_share = (
            verifier_reserve["input_tokens"] + remaining_verifier_calls - 1
        ) // remaining_verifier_calls
        current_time_share = (
            verifier_reserve["seconds"] + remaining_verifier_calls - 1
        ) // remaining_verifier_calls
        verifier_reserve = {
            **verifier_reserve,
            "input_tokens": max(0, verifier_reserve["input_tokens"] - current_input_share),
            "output_tokens": max(0, verifier_reserve["output_tokens"] - completion_floor),
            "seconds": max(0, verifier_reserve["seconds"] - current_time_share),
        }
    if prompt_token_reservation > remaining_input - verifier_reserve["input_tokens"]:
        raise InvestigationRunError(
            "Das Run-Inputbudget reicht nicht für den Call samt Verifier-Reserve.",
            code="input_budget_exhausted",
        )
    remaining_output -= verifier_reserve["output_tokens"]
    remaining_seconds = (
        run.budget_limits["max_runtime_seconds"]
        - elapsed_seconds(run)
        - verifier_reserve["seconds"]
    )
    if remaining_seconds < timeout_floor:
        raise InvestigationRunError(
            "Die Run-Zeit reicht nicht für einen sinnvollen Modellaufruf samt Verifier-Reserve.",
            code="runtime_capacity_exhausted",
        )
    if role != InvestigationModelCall.Role.VERIFIER:
        remaining_planner_calls = max(
            1,
            run.budget_limits["max_model_calls"]
            - usage["model_calls"]
            - verifier_reserve["model_calls"],
        )
        call_timeout = max(timeout_floor, remaining_seconds // remaining_planner_calls)
    else:
        call_timeout = remaining_seconds
    call_max_tokens = min(ENDPOINT_CAPABILITY["completion_tokens"], context_room, remaining_output)
    campaign = None
    if run.evidence_campaign_id is not None:
        campaign = InvestigationEvidenceCampaign.objects.select_for_update().get(
            pk=run.evidence_campaign_id
        )
        call_max_tokens = max_reservable_output_tokens(
            campaign,
            input_tokens=prompt_token_reservation,
            upper_bound=call_max_tokens,
            protected_input_tokens=verifier_reserve["input_tokens"],
            protected_output_tokens=verifier_reserve["output_tokens"],
        )
    if call_max_tokens < completion_floor:
        code = (
            "context_capacity_exhausted"
            if context_room < completion_floor
            else "evidence_budget_exhausted"
            if campaign is not None
            and max_reservable_output_tokens(
                campaign,
                input_tokens=prompt_token_reservation,
                upper_bound=completion_floor,
                protected_input_tokens=verifier_reserve["input_tokens"],
                protected_output_tokens=verifier_reserve["output_tokens"],
            )
            < completion_floor
            else "completion_budget_exhausted"
        )
        raise InvestigationRunError(
            "Der Completion-Spielraum liegt unter dem Mindestwert für strukturiertes Arbeiten.",
            code=code,
        )

    if usage["model_calls"] >= run.budget_limits["max_model_calls"]:
        raise InvestigationRunError("Modellbudget ist erschöpft.", code="budget_exhausted")

    if role == InvestigationModelCall.Role.VERIFIER:
        if usage["verifier_calls"] >= run.budget_limits["max_verifier_calls"]:
            raise InvestigationRunError("Verifier-Budget ist erschöpft.", code="budget_exhausted")
        usage["verifier_calls"] += 1
    elif budget_exhausted(
        run,
        reserve_verifier=True,
        reserve_synthesis=role == InvestigationModelCall.Role.PLANNER,
    ):
        raise InvestigationRunError(
            "Die für den Verifier reservierten Modellbudgets würden verletzt.",
            code="budget_exhausted",
        )

    usage["model_calls"] += 1
    usage["provider_attempts"] += 1
    run.usage = usage
    run.save(update_fields=["usage", "updated_at"])

    call = InvestigationModelCall.objects.create(
        run=run,
        role=role,
        executor_generation=run.executor_generation,
        requested_provider="openrouter",
        requested_model=_requested_model(),
        effective_parameters={
            "temperature": 0.1,
            "reasoning_effort": "medium",
            "max_tokens": call_max_tokens,
            "timeout_seconds": call_timeout,
            "provider_policy": dict(ISSUE4_INVESTIGATION_PROVIDER_POLICY),
        },
        prompt_version=prompt_version,
        prompt_hash=content_hash(prompt_payload),
        instruction_template=instruction,
        schema_version=schema_version,
        context_refs={
            "source_snapshot_id": str(run.source_snapshot_id),
            "manifest_hash": run.manifest_hash,
            "register_hash": run.register_hash,
            "brief_hash": run.brief_hash,
        },
    )
    if run.evidence_campaign_id is not None:
        reserve_provider_attempt(
            run_id=run.pk,
            model_call_id=call.pk,
            max_input_tokens=prompt_token_reservation,
            max_output_tokens=call_max_tokens,
        )
    return call


def _mark_model_failure(
    call_id,
    code: str,
    *,
    response_diagnostics: Mapping[str, Any] | None = None,
) -> None:
    with transaction.atomic():
        call = InvestigationModelCall.objects.select_for_update().get(pk=call_id)
        if call.status == InvestigationModelCall.Status.RUNNING:
            call.status = InvestigationModelCall.Status.FAILED
            call.error_code = str(code or "provider_error")[:50]
            call.finished_at = timezone.now()
            if response_diagnostics:
                parameters = dict(call.effective_parameters)
                parameters["response_diagnostics"] = dict(response_diagnostics)
                call.effective_parameters = parameters
            call.save(
                update_fields=[
                    "status",
                    "error_code",
                    "effective_parameters",
                    "finished_at",
                    "updated_at",
                ]
            )


def _record_truncated_usage(run_id, call_id, reservation, diagnostics: Mapping[str, Any]) -> None:
    """Settle complete provider usage; retain the reservation if any field is uncertain."""
    try:
        prompt = int(diagnostics["usage_prompt_tokens"])
        completion = int(diagnostics["usage_completion_tokens"])
        if prompt < 0 or completion < 0:
            raise ValueError("negative usage")
    except (KeyError, TypeError, ValueError):
        prompt = completion = None
    cost = cost_to_microunits(diagnostics.get("usage_cost"))
    cost_required = reservation is not None and "max_cost_microunits" in reservation.campaign.limits
    complete = (
        prompt is not None and completion is not None and (not cost_required or cost is not None)
    )
    if reservation is not None:
        if complete:
            settle_provider_attempt(
                reservation_id=reservation.pk,
                actual_input_tokens=prompt,
                actual_output_tokens=completion,
                actual_cost_microunits=cost,
            )
        else:
            mark_provider_attempt_uncertain(
                reservation_id=reservation.pk,
                reason="output_truncated_usage_incomplete",
            )
    if complete:
        with transaction.atomic():
            run = InvestigationRun.objects.select_for_update().get(pk=run_id)
            call = InvestigationModelCall.objects.select_for_update().get(pk=call_id)
            usage = dict(run.usage)
            usage["input_tokens"] += prompt
            usage["output_tokens"] += completion
            run.usage = usage
            run.save(update_fields=["usage", "updated_at"])
            call.prompt_tokens = prompt
            call.completion_tokens = completion
            call.total_tokens = prompt + completion
            call.returned_model = str(diagnostics.get("returned_model") or "")
            call.save(
                update_fields=[
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "returned_model",
                    "updated_at",
                ]
            )


def _structured_provider_call(
    *,
    actor,
    run_id,
    executor_token,
    role: str,
    instruction: str,
    prompt_version: str,
    schema_version: str,
    context: Mapping[str, Any],
    response_format: dict[str, Any],
    payload_validator: Callable[[Mapping[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], InvestigationModelCall]:
    call = _reserve_model_call(
        actor=actor,
        run_id=run_id,
        executor_token=executor_token,
        role=role,
        instruction=instruction,
        prompt_version=prompt_version,
        schema_version=schema_version,
        context=context,
        response_format=response_format,
    )
    messages = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": canonical_json(context)},
    ]

    reservation = getattr(call, "evidence_reservation", None)
    try:
        result = request_openrouter(
            messages=messages,
            max_tokens=int(call.effective_parameters["max_tokens"]),
            timeout_seconds=int(call.effective_parameters["timeout_seconds"]),
            temperature=0.1,
            response_format=response_format,
            provider=dict(ISSUE4_INVESTIGATION_PROVIDER_POLICY),
            reasoning_effort="medium",
        )
        if result.finish_reason == "length":
            raise OpenRouterUnavailable(
                "OpenRouter hat das Completion-Limit vor einem vollständigen Ergebnis erreicht.",
                code="output_truncated",
                diagnostics={
                    "finish_reason": result.finish_reason,
                    "content_length": len(result.content),
                    "returned_model": result.model,
                    "usage_prompt_tokens": result.usage.get("prompt_tokens"),
                    "usage_completion_tokens": result.usage.get("completion_tokens"),
                    "usage_total_tokens": result.usage.get("total_tokens"),
                    "usage_cost": result.usage.get("cost"),
                },
            )
        payload = json.loads(result.content)
        if not isinstance(payload, dict):
            raise ValueError("structured response must be an object")
    except OpenRouterUnavailable as exc:
        if exc.code == "output_truncated":
            _record_truncated_usage(run_id, call.pk, reservation, exc.diagnostics)
        elif reservation is not None:
            mark_provider_attempt_uncertain(
                reservation_id=reservation.pk,
                reason=exc.code,
            )
        _mark_model_failure(
            call.pk,
            exc.code,
            response_diagnostics=exc.diagnostics,
        )
        raise InvestigationRunError(str(exc), code=exc.code) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        if reservation is not None:
            mark_provider_attempt_uncertain(
                reservation_id=reservation.pk,
                reason="invalid_response",
            )
        _mark_model_failure(call.pk, "invalid_response")
        raise InvestigationRunError(
            "Das Modell lieferte kein gültiges strukturiertes Ergebnis.",
            code="invalid_response",
        ) from exc

    validation_error: InvestigationRunError | None = None
    validation_source_code = ""
    if payload_validator is not None:
        try:
            payload_validator(payload)
        except InvestigationRunError as exc:
            validation_source_code = exc.code
            validation_error = InvestigationRunError(
                str(exc),
                code="invalid_response",
            )

    prompt_tokens, completion_tokens, total_tokens = _usage_tokens(result, messages)
    if reservation is not None:
        raw_prompt = result.usage.get("prompt_tokens")
        raw_completion = result.usage.get("completion_tokens")
        actual_cost = cost_to_microunits(result.usage.get("cost"))
        cost_required = "max_cost_microunits" in reservation.campaign.limits
        if raw_prompt is None or raw_completion is None or (cost_required and actual_cost is None):
            mark_provider_attempt_uncertain(
                reservation_id=reservation.pk,
                reason="provider_usage_metadata_incomplete",
            )
        else:
            settle_provider_attempt(
                reservation_id=reservation.pk,
                actual_input_tokens=int(raw_prompt),
                actual_output_tokens=int(raw_completion),
                actual_cost_microunits=actual_cost,
            )

    with transaction.atomic():
        run = InvestigationRun.objects.select_for_update().get(pk=run_id)
        current = InvestigationModelCall.objects.select_for_update().get(pk=call.pk)
        usage = dict(run.usage)
        usage["input_tokens"] += prompt_tokens
        usage["output_tokens"] += completion_tokens
        run.usage = usage
        run.save(update_fields=["usage", "updated_at"])

        stale = (
            run.executor_generation != call.executor_generation
            or str(run.executor_token) != str(executor_token)
            or run.status != InvestigationRun.Status.RUNNING
        )
        current.returned_model = result.model
        current.model_revision = "unknown"
        current.prompt_tokens = prompt_tokens
        current.completion_tokens = completion_tokens
        current.total_tokens = total_tokens
        current.finished_at = timezone.now()

        if stale:
            current.status = InvestigationModelCall.Status.DISCARDED
            current.error_code = "stale_executor"
            update_fields = [
                "status",
                "error_code",
                "returned_model",
                "model_revision",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "finished_at",
                "updated_at",
            ]
        elif validation_error is not None:
            current.status = InvestigationModelCall.Status.FAILED
            current.error_code = validation_error.code
            parameters = dict(current.effective_parameters)
            parameters["response_diagnostics"] = {
                "structured_contract_error": str(validation_error),
                "structured_contract_error_code": validation_source_code,
            }
            current.effective_parameters = parameters
            update_fields = [
                "status",
                "error_code",
                "effective_parameters",
                "returned_model",
                "model_revision",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "finished_at",
                "updated_at",
            ]
        else:
            current.status = InvestigationModelCall.Status.SUCCESS
            current.accepted_payload = payload
            current.accepted_payload_hash = content_hash(payload)
            update_fields = [
                "status",
                "returned_model",
                "model_revision",
                "accepted_payload",
                "accepted_payload_hash",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "finished_at",
                "updated_at",
            ]
        current.save(update_fields=update_fields)

    if stale:
        raise InvestigationRunError(
            "Verspätetes Modellergebnis wurde verworfen.",
            code="stale_executor",
        )
    if validation_error is not None:
        raise validation_error
    return payload, current


def request_planner_action(
    *,
    actor,
    run: InvestigationRun,
    executor_token,
) -> PlannerAction:
    assert_actor_can_edit_run(actor, run)
    payload, _call = _structured_provider_call(
        actor=actor,
        run_id=run.pk,
        executor_token=executor_token,
        role=InvestigationModelCall.Role.PLANNER,
        instruction=PLANNER_INSTRUCTION,
        prompt_version=PLANNER_PROMPT_VERSION,
        schema_version=PLANNER_SCHEMA_VERSION,
        context=_investigation_context(actor, run),
        response_format=planner_response_format(),
        payload_validator=lambda response: _validate_investigation_action(run, response),
    )
    if payload.get("action") == "synthesize":
        return request_synthesis_package(actor=actor, run=run, executor_token=executor_token)
    parameters = _decode_structured_field(payload, "parameters", expected_type=Mapping, default={})
    clarification_payload = _decode_structured_field(
        payload, "clarification_payload", expected_type=Mapping, default={}
    )
    return PlannerAction(
        action=str(payload.get("action") or ""),
        target_claim_id=str(payload.get("target_claim_id") or ""),
        expected_discriminating_finding=str(payload.get("expected_discriminating_finding") or ""),
        rationale=str(payload.get("rationale") or ""),
        tool_name=str(payload.get("tool_name") or ""),
        parameters=dict(parameters),
        claim_register=None,
        brief_payload=None,
        source_relevance={},
        progress_kind="none",
        progress_payload={},
        clarification_reason=str(payload.get("clarification_reason") or ""),
        clarification_payload=dict(clarification_payload),
    )


def request_synthesis_package(*, actor, run: InvestigationRun, executor_token) -> PlannerAction:
    assert_actor_can_edit_run(actor, run)
    payload, _call = _structured_provider_call(
        actor=actor,
        run_id=run.pk,
        executor_token=executor_token,
        role=InvestigationModelCall.Role.SYNTHESIZER,
        instruction=SYNTHESIS_INSTRUCTION,
        prompt_version=SYNTHESIS_PROMPT_VERSION,
        schema_version=SYNTHESIS_SCHEMA_VERSION,
        context=_planner_context(actor, run),
        response_format=synthesis_response_format(),
        payload_validator=lambda response: _validate_synthesis_package(run, response),
    )
    investigation_request = _decode_structured_field(
        payload, "investigation_request", expected_type=Mapping, default={}
    )
    if investigation_request:
        return PlannerAction(
            action="investigate",
            target_claim_id="",
            expected_discriminating_finding=str(investigation_request.get("goal") or ""),
            rationale=str(investigation_request.get("reason") or ""),
            tool_name="",
            parameters={},
            claim_register=None,
            brief_payload=None,
            source_relevance={},
            progress_kind="none",
            progress_payload={},
            clarification_reason="",
            clarification_payload=dict(investigation_request),
        )
    if payload.get("clarification_reason") == "missing_evidence":
        clarification = _decode_structured_field(
            payload, "clarification_payload", expected_type=Mapping, default={}
        )
        return PlannerAction(
            action="clarify",
            target_claim_id="",
            expected_discriminating_finding="",
            rationale="",
            tool_name="",
            parameters={},
            claim_register=None,
            brief_payload=None,
            source_relevance={},
            progress_kind="none",
            progress_payload={},
            clarification_reason="missing_evidence",
            clarification_payload=dict(clarification),
        )
    claims = _decode_structured_field(payload, "claim_register", expected_type=list, default=[])
    brief = _decode_structured_field(payload, "brief_payload", expected_type=Mapping, default={})
    relevance = _decode_structured_field(
        payload, "source_relevance", expected_type=Mapping, default={}
    )
    return PlannerAction(
        action="synthesize",
        target_claim_id="",
        expected_discriminating_finding="",
        rationale="",
        tool_name="",
        parameters={},
        claim_register=tuple(claims),
        brief_payload=dict(brief),
        source_relevance={str(key): dict(value) for key, value in relevance.items()},
        progress_kind="none",
        progress_payload={},
        clarification_reason="",
        clarification_payload={},
    )


def _critical_claim_ids(run: InvestigationRun) -> set[str]:
    return {
        str(item["claim_id"])
        for item in run.claim_register
        if bool(item.get("critical"))
        and is_evidence_claim(str(item.get("area") or ""), str(item.get("claim_kind") or ""))
    }


def _record_verifier_report(
    *,
    run_id,
    call: InvestigationModelCall,
    payload: Mapping[str, Any],
) -> InvestigationVerifierReport:
    with transaction.atomic():
        run = InvestigationRun.objects.select_for_update().get(pk=run_id)
        findings = [dict(item) for item in payload.get("findings", []) if isinstance(item, Mapping)]
        critical_findings = sum(1 for item in findings if item.get("severity") == "critical")
        checked = [str(item) for item in payload.get("checked_critical_claims", []) if str(item)]
        refs_valid = bool(payload.get("source_references_valid")) and all(
            bool(item.get("references_valid", False))
            for item in run.claim_register
            if item.get("status") in {"supported", "refuted"}
            and is_evidence_claim(
                str(item.get("area") or ""),
                str(item.get("claim_kind") or ""),
            )
        )
        success = (
            critical_findings == 0
            and refs_valid
            and _critical_claim_ids(run).issubset(set(checked))
        )
        revision = (run.verifier_reports.aggregate(value=Max("revision"))["value"] or 0) + 1
        return InvestigationVerifierReport.objects.create(
            run=run,
            revision=revision,
            model_call=call,
            success=success,
            findings=findings,
            critical_findings=critical_findings,
            source_references_valid=refs_valid,
            checked_critical_claims=checked,
            bound_hashes={
                "contract": run.contract_hash,
                "manifest": run.manifest_hash,
                "register": run.register_hash,
                "brief": run.brief_hash,
            },
            created_for_executor_generation=run.executor_generation,
        )


def request_verifier_report(
    *,
    actor,
    run: InvestigationRun,
    executor_token,
) -> InvestigationVerifierReport:
    """Run an independent review with iterative, unique evidence reads.

    A request for more evidence is not itself a critical finding. The verifier
    may continue reading while global run/campaign budgets permit. Repeating the
    exact same read request is treated as a noncritical review caveat rather
    than manufacturing a verification failure.
    """
    assert_actor_can_edit_run(actor, run)
    analysis_replays = _deterministic_analysis_replays(actor, run)
    verifier_reads: list[dict[str, Any]] = []
    seen_read_requests: set[str] = set()
    context = _verifier_context(run, analysis_replays=analysis_replays)

    while True:
        payload, call = _structured_provider_call(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
            role=InvestigationModelCall.Role.VERIFIER,
            instruction=VERIFIER_INSTRUCTION,
            prompt_version=VERIFIER_PROMPT_VERSION,
            schema_version=VERIFIER_SCHEMA_VERSION,
            context=context,
            response_format=verifier_response_format(),
        )
        read_requests = [
            dict(item) for item in payload.get("read_requests", []) if isinstance(item, Mapping)
        ]
        if not read_requests:
            return _record_verifier_report(
                run_id=run.pk,
                call=call,
                payload=_apply_replay_findings(payload, analysis_replays),
            )

        new_requests: list[dict[str, Any]] = []
        for item in read_requests:
            read_key = content_hash(
                {
                    "source_id": str(item.get("source_id") or ""),
                    "cursor": int(item.get("cursor", 0)),
                    "limit": int(item.get("limit", 100)),
                    "columns": list(item.get("columns") or []),
                }
            )
            if read_key in seen_read_requests:
                continue
            seen_read_requests.add(read_key)
            new_requests.append(item)

        if not new_requests:
            final_payload = dict(payload)
            findings = [
                dict(item)
                for item in final_payload.get("findings", [])
                if isinstance(item, Mapping)
            ]
            findings.append(
                {
                    "severity": "noncritical",
                    "code": "verification_repeated_read_request",
                    "claim_id": "",
                    "message": (
                        "Der Verifier forderte ausschließlich bereits gelesene "
                        "Fundstellen erneut an; die Wiederholung blockiert READY nicht."
                    ),
                }
            )
            final_payload["findings"] = findings
            final_payload["read_requests"] = []
            return _record_verifier_report(
                run_id=run.pk,
                call=call,
                payload=_apply_replay_findings(final_payload, analysis_replays),
            )

        for item in new_requests:
            step = execute_tool_step(
                actor=actor,
                run_id=run.pk,
                executor_token=executor_token,
                tool_name="read_source",
                parameters={
                    "source_id": item.get("source_id"),
                    "cursor": item.get("cursor", 0),
                    "limit": item.get("limit", 100),
                    "columns": item.get("columns") or [],
                },
                target_claim_id=f"verifier:{item.get('claim_id') or ''}",
                expected_discriminating_finding="Verifier-Fundstelle prüfen",
                verifier_read=True,
            )
            verifier_reads.append(
                {
                    "claim_id": str(item.get("claim_id") or ""),
                    "source_id": str(item.get("source_id") or ""),
                    "result": step.result_payload,
                    "result_hash": step.result_hash,
                }
            )

        run.refresh_from_db()
        context = _verifier_context(run, analysis_replays=analysis_replays)
        context["verifier_reads"] = list(verifier_reads)
