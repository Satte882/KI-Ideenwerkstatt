from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from ki_radar.core.llm_tasks import FIRST_WAVE_PROVIDER_POLICY
from ki_radar.core.openrouter import OpenRouterUnavailable, request_openrouter

from .investigation_models import (
    InvestigationModelCall,
    InvestigationRun,
    InvestigationStep,
    InvestigationVerifierReport,
)
from .investigation_policy import POLICY_VERSION
from .investigation_prompts import (
    PLANNER_INSTRUCTION,
    PLANNER_PROMPT_VERSION,
    PLANNER_SCHEMA_VERSION,
    VERIFIER_INSTRUCTION,
    VERIFIER_PROMPT_VERSION,
    VERIFIER_SCHEMA_VERSION,
    planner_response_format,
    verifier_response_format,
)
from .investigation_runtime import (
    ALLOWED_TOOLS,
    BUDGET_VERSION,
    LOOP_VERSION,
    InvestigationRunError,
    assert_active,
    assert_actor_can_edit_run,
    assert_executor,
    budget_exhausted,
    canonical_json,
    content_hash,
    evaluate_run_policy,
    execute_tool_step,
    locked_run,
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
    claim_register: tuple[Mapping[str, Any], ...]
    brief_payload: Mapping[str, Any]
    source_relevance: Mapping[str, Mapping[str, Any]]
    progress_kind: str
    progress_payload: Mapping[str, Any]
    clarification_reason: str
    clarification_payload: Mapping[str, Any]


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

    tools = frozen.get("tools") or {}
    if tools.get("implementation_version") != TOOL_VERSION or set(
        tools.get("allowlist") or []
    ) != set(ALLOWED_TOOLS):
        raise InvestigationRunError(
            "Der fixierte Werkzeugvertrag hat sich geändert.",
            code="execution_version_unavailable",
        )

    planner = frozen.get("planner") or {}
    verifier = frozen.get("verifier") or {}
    if (
        planner.get("prompt_version") != PLANNER_PROMPT_VERSION
        or planner.get("instruction_hash") != _instruction_hash(PLANNER_INSTRUCTION)
        or planner.get("schema_version") != PLANNER_SCHEMA_VERSION
        or verifier.get("prompt_version") != VERIFIER_PROMPT_VERSION
        or verifier.get("instruction_hash") != _instruction_hash(VERIFIER_INSTRUCTION)
        or verifier.get("schema_version") != VERIFIER_SCHEMA_VERSION
    ):
        raise InvestigationRunError(
            "Ein fixierter Prompt-/Schema-Vertrag hat sich geändert.",
            code="execution_version_unavailable",
        )

    transport = frozen.get("model_transport") or {}
    if transport.get("requested_model", "") != _requested_model():
        raise InvestigationRunError(
            "Der für den Run fixierte Modell-Alias ist nicht mehr aktiv.",
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


def _planner_context(actor, run: InvestigationRun) -> dict[str, Any]:
    sources = list_sources(actor=actor, snapshot_id=run.source_snapshot_id)
    return {
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
            for step in run.steps.order_by("-sequence")[:5]
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
    }


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
    findings = [
        dict(item)
        for item in normalized.get("findings", [])
        if isinstance(item, Mapping)
    ]
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

    usage = dict(run.usage)
    if usage["model_calls"] >= run.budget_limits["max_model_calls"]:
        raise InvestigationRunError("Modellbudget ist erschöpft.", code="budget_exhausted")

    if role == InvestigationModelCall.Role.VERIFIER:
        if usage["verifier_calls"] >= run.budget_limits["max_verifier_calls"]:
            raise InvestigationRunError("Verifier-Budget ist erschöpft.", code="budget_exhausted")
        usage["verifier_calls"] += 1
    elif budget_exhausted(run, reserve_verifier=True):
        raise InvestigationRunError(
            "Die für den Verifier reservierten Modellbudgets würden verletzt.",
            code="budget_exhausted",
        )

    usage["model_calls"] += 1
    usage["provider_attempts"] += 1
    run.usage = usage
    run.save(update_fields=["usage", "updated_at"])

    prompt_payload = {"instruction": instruction, "context": dict(context)}
    return InvestigationModelCall.objects.create(
        run=run,
        role=role,
        executor_generation=run.executor_generation,
        requested_provider="openrouter",
        requested_model=_requested_model(),
        effective_parameters={
            "temperature": 0.1,
            "reasoning_effort": "medium",
            "max_tokens": 4096,
            "provider_policy": dict(FIRST_WAVE_PROVIDER_POLICY),
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


def _mark_model_failure(call_id, code: str) -> None:
    with transaction.atomic():
        call = InvestigationModelCall.objects.select_for_update().get(pk=call_id)
        if call.status == InvestigationModelCall.Status.RUNNING:
            call.status = InvestigationModelCall.Status.FAILED
            call.error_code = str(code or "provider_error")[:50]
            call.finished_at = timezone.now()
            call.save(update_fields=["status", "error_code", "finished_at", "updated_at"])


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
    )
    messages = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": canonical_json(context)},
    ]

    try:
        result = request_openrouter(
            messages=messages,
            max_tokens=4096,
            timeout_seconds=60,
            temperature=0.1,
            response_format=response_format,
            provider=dict(FIRST_WAVE_PROVIDER_POLICY),
            reasoning_effort="medium",
        )
        payload = json.loads(result.content)
        if not isinstance(payload, dict):
            raise ValueError("structured response must be an object")
    except OpenRouterUnavailable as exc:
        _mark_model_failure(call.pk, exc.code)
        raise InvestigationRunError(str(exc), code=exc.code) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        _mark_model_failure(call.pk, "invalid_response")
        raise InvestigationRunError(
            "Das Modell lieferte kein gültiges strukturiertes Ergebnis.",
            code="invalid_response",
        ) from exc

    prompt_tokens, completion_tokens, total_tokens = _usage_tokens(result, messages)

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
            current.save(
                update_fields=[
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
            )
        else:
            current.status = InvestigationModelCall.Status.SUCCESS
            current.accepted_payload = payload
            current.accepted_payload_hash = content_hash(payload)
            current.save(
                update_fields=[
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
            )

    if stale:
        raise InvestigationRunError(
            "Verspätetes Modellergebnis wurde verworfen.",
            code="stale_executor",
        )
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
        context=_planner_context(actor, run),
        response_format=planner_response_format(),
    )
    return PlannerAction(
        action=str(payload.get("action") or ""),
        target_claim_id=str(payload.get("target_claim_id") or ""),
        expected_discriminating_finding=str(payload.get("expected_discriminating_finding") or ""),
        rationale=str(payload.get("rationale") or ""),
        tool_name=str(payload.get("tool_name") or ""),
        parameters=dict(payload.get("parameters") or {}),
        claim_register=tuple(payload.get("claim_register") or []),
        brief_payload=dict(payload.get("brief_payload") or {}),
        source_relevance={
            str(key): dict(value)
            for key, value in dict(payload.get("source_relevance") or {}).items()
            if isinstance(value, Mapping)
        },
        progress_kind=str(payload.get("progress_kind") or "none"),
        progress_payload=dict(payload.get("progress_payload") or {}),
        clarification_reason=str(payload.get("clarification_reason") or ""),
        clarification_payload=dict(payload.get("clarification_payload") or {}),
    )


def _critical_claim_ids(run: InvestigationRun) -> set[str]:
    return {str(item["claim_id"]) for item in run.claim_register if bool(item.get("critical"))}


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
    assert_actor_can_edit_run(actor, run)
    analysis_replays = _deterministic_analysis_replays(actor, run)
    first_payload, first_call = _structured_provider_call(
        actor=actor,
        run_id=run.pk,
        executor_token=executor_token,
        role=InvestigationModelCall.Role.VERIFIER,
        instruction=VERIFIER_INSTRUCTION,
        prompt_version=VERIFIER_PROMPT_VERSION,
        schema_version=VERIFIER_SCHEMA_VERSION,
        context=_verifier_context(run, analysis_replays=analysis_replays),
        response_format=verifier_response_format(),
    )

    read_requests = [
        dict(item) for item in first_payload.get("read_requests", []) if isinstance(item, Mapping)
    ]
    if not read_requests:
        return _record_verifier_report(
            run_id=run.pk,
            call=first_call,
            payload=_apply_replay_findings(first_payload, analysis_replays),
        )

    verifier_reads: list[dict[str, Any]] = []
    for item in read_requests:
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
    second_context = _verifier_context(run, analysis_replays=analysis_replays)
    second_context["verifier_reads"] = verifier_reads
    final_payload, final_call = _structured_provider_call(
        actor=actor,
        run_id=run.pk,
        executor_token=executor_token,
        role=InvestigationModelCall.Role.VERIFIER,
        instruction=VERIFIER_INSTRUCTION,
        prompt_version=VERIFIER_PROMPT_VERSION,
        schema_version=VERIFIER_SCHEMA_VERSION,
        context=second_context,
        response_format=verifier_response_format(),
    )

    if final_payload.get("read_requests"):
        findings = list(final_payload.get("findings") or [])
        findings.append(
            {
                "severity": "critical",
                "code": "verification_reads_incomplete",
                "claim_id": "",
                "message": (
                    "Der Verifier benötigt nach dem zweiten Aufruf weitere Fundstellenprüfung."
                ),
            }
        )
        final_payload = dict(final_payload)
        final_payload["findings"] = findings
        final_payload["source_references_valid"] = False

    return _record_verifier_report(
        run_id=run.pk,
        call=final_call,
        payload=_apply_replay_findings(final_payload, analysis_replays),
    )
