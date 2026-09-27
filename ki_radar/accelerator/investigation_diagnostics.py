from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

from django.utils import timezone

from .investigation_models import InvestigationModelCall, InvestigationRun
from .investigation_runtime import evaluate_run_policy


def _duration_seconds(started_at, finished_at) -> float | None:
    if started_at is None or finished_at is None:
        return None
    return round(max(0.0, (finished_at - started_at).total_seconds()), 3)


def _planner_action(call: InvestigationModelCall) -> str:
    payload = call.accepted_payload if isinstance(call.accepted_payload, Mapping) else {}
    return str(payload.get("action") or "")


def _synthesis_trigger(
    calls: list[InvestigationModelCall],
    index: int,
    call: InvestigationModelCall,
) -> str:
    stored = str((call.context_refs or {}).get("synthesis_mode") or "")
    if stored:
        return stored
    previous = calls[index - 1] if index else None
    if previous is None:
        return "initial"
    if (
        previous.role == InvestigationModelCall.Role.PLANNER
        and _planner_action(previous) == "synthesize"
    ):
        return "planner_synthesize"
    if (
        previous.role == InvestigationModelCall.Role.SYNTHESIZER
        and previous.status == InvestigationModelCall.Status.FAILED
    ):
        return "contract_retry"
    if previous.role == InvestigationModelCall.Role.VERIFIER:
        return "verifier_repair"
    return "runtime_synthesis"


def build_investigation_diagnostic(
    run: InvestigationRun,
    *,
    now=None,
) -> dict[str, Any]:
    now = now or timezone.now()
    calls = list(run.model_calls.order_by("created_at"))
    steps = list(run.steps.order_by("sequence"))
    model_seconds = 0.0
    role_totals: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"calls": 0, "seconds": 0.0, "prompt_tokens": 0, "completion_tokens": 0}
    )
    call_rows: list[dict[str, Any]] = []

    for index, call in enumerate(calls):
        duration = _duration_seconds(call.started_at, call.finished_at)
        if duration is not None:
            model_seconds += duration
        totals = role_totals[call.role]
        totals["calls"] = int(totals["calls"]) + 1
        totals["seconds"] = round(float(totals["seconds"]) + float(duration or 0.0), 3)
        totals["prompt_tokens"] = int(totals["prompt_tokens"]) + int(call.prompt_tokens or 0)
        totals["completion_tokens"] = int(totals["completion_tokens"]) + int(
            call.completion_tokens or 0
        )

        context_refs = dict(call.context_refs or {})
        next_refs = (
            dict(calls[index + 1].context_refs or {})
            if index + 1 < len(calls)
            else {
                "register_hash": run.register_hash,
                "brief_hash": run.brief_hash,
            }
        )
        payload = call.accepted_payload if isinstance(call.accepted_payload, Mapping) else {}
        response_metadata = dict((call.effective_parameters or {}).get("response_metadata") or {})
        row = {
            "sequence": index + 1,
            "role": call.role,
            "status": call.status,
            "duration_seconds": duration,
            "prompt_tokens": call.prompt_tokens,
            "completion_tokens": call.completion_tokens,
            "total_tokens": call.total_tokens,
            "max_tokens": (call.effective_parameters or {}).get("max_tokens"),
            "timeout_seconds": (call.effective_parameters or {}).get("timeout_seconds"),
            "reasoning_effort": (call.effective_parameters or {}).get("reasoning_effort"),
            "reasoning_tokens": response_metadata.get("reasoning_tokens"),
            "output_chars": response_metadata.get("output_chars"),
            "finish_reason": str(response_metadata.get("finish_reason") or ""),
            "context_profile": str(context_refs.get("context_profile") or ""),
            "context_chars": context_refs.get("context_chars"),
            "error_code": call.error_code,
            "action": (
                _planner_action(call) if call.role == InvestigationModelCall.Role.PLANNER else ""
            ),
            "rationale": str(payload.get("rationale") or ""),
            "synthesis_trigger": (
                _synthesis_trigger(calls, index, call)
                if call.role == InvestigationModelCall.Role.SYNTHESIZER
                else ""
            ),
            "pre_register_hash": str(context_refs.get("register_hash") or ""),
            "pre_brief_hash": str(context_refs.get("brief_hash") or ""),
            "post_register_hash": (
                str(next_refs.get("register_hash") or "")
                if call.role == InvestigationModelCall.Role.SYNTHESIZER
                else ""
            ),
            "post_brief_hash": (
                str(next_refs.get("brief_hash") or "")
                if call.role == InvestigationModelCall.Role.SYNTHESIZER
                else ""
            ),
            "policy_blockers": list(context_refs.get("policy_blockers") or []),
            "pre_verifier_blockers": list(context_refs.get("pre_verifier_blockers") or []),
        }
        if call.role == InvestigationModelCall.Role.SYNTHESIZER:
            row["register_changed"] = (
                bool(row["pre_register_hash"])
                and bool(row["post_register_hash"])
                and row["pre_register_hash"] != row["post_register_hash"]
            )
            row["brief_changed"] = (
                bool(row["pre_brief_hash"])
                and bool(row["post_brief_hash"])
                and row["pre_brief_hash"] != row["post_brief_hash"]
            )
        call_rows.append(row)

    step_rows: list[dict[str, Any]] = []
    read_keys: list[tuple[str, int, int, tuple[str, ...]]] = []
    for step in steps:
        duration = _duration_seconds(step.started_at, step.finished_at)
        parameters = dict(step.parameters or {})
        step_rows.append(
            {
                "sequence": step.sequence,
                "tool_name": step.tool_name,
                "status": step.status,
                "duration_seconds": duration,
                "parameters": parameters,
                "result_hash": step.result_hash,
                "progress_kind": step.progress_kind,
            }
        )
        if step.tool_name == "read_source" and step.status == "success":
            read_keys.append(
                (
                    str(parameters.get("source_id") or ""),
                    int(parameters.get("cursor", 0)),
                    int(parameters.get("limit", 100)),
                    tuple(str(item) for item in parameters.get("columns") or []),
                )
            )

    exact_duplicate_reads = [
        {
            "source_id": source_id,
            "cursor": cursor,
            "limit": limit,
            "columns": list(columns),
            "count": count,
        }
        for (source_id, cursor, limit, columns), count in Counter(read_keys).items()
        if count > 1
    ]

    end = run.finished_at or now
    run_seconds = max(0.0, (end - run.started_at).total_seconds())
    synthesis_rows = [
        row for row in call_rows if row["role"] == InvestigationModelCall.Role.SYNTHESIZER
    ]
    return {
        "run_id": str(run.pk),
        "status": run.status,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "run_seconds": round(run_seconds, 3),
        "model_seconds": round(model_seconds, 3),
        "non_model_seconds": round(max(0.0, run_seconds - model_seconds), 3),
        "model_share_percent": (
            round((model_seconds / run_seconds) * 100, 1) if run_seconds else 0.0
        ),
        "model_calls": call_rows,
        "role_totals": dict(role_totals),
        "tool_steps": step_rows,
        "synthesis_count": len(synthesis_rows),
        "synthesis_seconds": round(
            sum(float(item["duration_seconds"] or 0.0) for item in synthesis_rows), 3
        ),
        "exact_duplicate_reads": exact_duplicate_reads,
        "final_register_hash": run.register_hash,
        "final_brief_hash": run.brief_hash,
        "final_policy_blockers": list(evaluate_run_policy(run).blockers),
    }


def render_investigation_diagnostic_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        f"# Investigation-Diagnose {report['run_id']}",
        "",
        f"- Status: **{report['status']}**",
        f"- Gesamtdauer: **{report['run_seconds']:.1f}s**",
        f"- Modellzeit: **{report['model_seconds']:.1f}s** ({report['model_share_percent']:.1f}%)",
        f"- Übrige Runtime: **{report['non_model_seconds']:.1f}s**",
        f"- Synthesen: **{report['synthesis_count']}** / {report['synthesis_seconds']:.1f}s",
        "",
        "## Modellaufrufe",
        "",
        (
            "| # | Rolle | Status | Dauer | Tokens in/out/reasoning | Sichtbar | "
            "Call-Limit | Aktion / Auslöser |"
        ),
        "|---:|---|---|---:|---:|---:|---|---|",
    ]
    for call in report["model_calls"]:
        action = call["synthesis_trigger"] or call["action"] or "-"
        tokens = (
            f"{call['prompt_tokens'] or 0}/{call['completion_tokens'] or 0}/"
            f"{call['reasoning_tokens'] if call['reasoning_tokens'] is not None else '-'}"
        )
        visible = str(call["output_chars"]) if call["output_chars"] is not None else "-"
        duration = (
            f"{call['duration_seconds']:.1f}s" if call["duration_seconds"] is not None else "-"
        )
        status = str(call["status"])
        if call["error_code"]:
            status = f"{status} ({call['error_code']})"
        call_limit = (
            f"{call['timeout_seconds'] or '-'}s / {call['max_tokens'] or '-'} / "
            f"{call['reasoning_effort'] or '-'}"
        )
        lines.append(
            f"| {call['sequence']} | {call['role']} | {status} | "
            f"{duration} | {tokens} | {visible} | {call_limit} | {action} |"
        )
        if call["role"] == InvestigationModelCall.Role.SYNTHESIZER:
            blockers = call["pre_verifier_blockers"]
            if blockers:
                lines.append(f"|  |  |  |  |  |  |  | Pre-Verifier: {', '.join(blockers)} |")
            if call["context_profile"]:
                lines.append(
                    f"|  |  |  |  |  |  |  | Kontext: {call['context_profile']} "
                    f"({call['context_chars'] or '-'} Zeichen) |"
                )

    lines.extend(
        [
            "",
            "## Werkzeugschritte",
            "",
            "| # | Werkzeug | Dauer | Parameter |",
            "|---:|---|---:|---|",
        ]
    )
    for step in report["tool_steps"]:
        duration = (
            f"{step['duration_seconds']:.1f}s" if step["duration_seconds"] is not None else "-"
        )
        lines.append(
            f"| {step['sequence']} | {step['tool_name']} | {duration} | `{step['parameters']}` |"
        )

    lines.extend(["", "## Exakte doppelte Reads", ""])
    duplicates = report["exact_duplicate_reads"]
    if not duplicates:
        lines.append("Keine identischen read_source-Aufrufe mit gleichem Cursor/Limit gefunden.")
    else:
        for item in duplicates:
            lines.append(
                "- "
                f"{item['source_id']} cursor={item['cursor']} limit={item['limit']} "
                f"columns={item['columns']} → {item['count']}x"
            )
    return "\n".join(lines) + "\n"
