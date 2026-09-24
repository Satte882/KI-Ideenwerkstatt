from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from .investigation_llm import (
    PlannerAction,
    _pending_synthesis_investigation,
    request_planner_action,
    request_verifier_report,
)
from .investigation_models import (
    InvestigationRun,
    InvestigationStep,
    InvestigationVerifierReport,
)
from .investigation_policy import PolicyDecision, PolicyOutcome, ReasonCode
from .investigation_runtime import (
    ALLOWED_TOOLS,
    InvestigationRunError,
    apply_planner_state,
    assert_active,
    assert_actor_can_edit_run,
    assert_executor,
    budget_exhausted,
    evaluate_run_policy,
    execute_tool_step,
    investigation_evidence_complete,
    locked_run,
    mark_counterevidence_processed,
    normalize_tool_parameters,
    pre_verifier_blockers_for_run,
    set_source_relevance,
)

TRANSIENT_PROVIDER_CODES = frozenset(
    {
        "timeout",
        "provider_unavailable",
        "rate_limit",
        "invalid_response",
        "provider_response_malformed",
        "empty_response",
    }
)
PLANNER_PROGRESS_KINDS = frozenset(item.value for item in InvestigationStep.ProgressKind)
MAX_PRE_VERIFIER_PACKAGE_ATTEMPTS = 2  # initial package + one technical retry


@dataclass(frozen=True)
class AdvanceResult:
    run_id: uuid.UUID
    status: str
    policy: PolicyDecision
    step_id: uuid.UUID | None = None


@transaction.atomic
def _set_waiting_human(
    *,
    actor,
    run_id,
    executor_token,
    reason: str,
    payload: Mapping[str, Any],
) -> InvestigationRun:
    allowed = {item.value for item in ReasonCode}
    if reason not in allowed:
        raise InvestigationRunError("Reason Code ist ungültig.", code="invalid_reason_code")
    run = locked_run(actor=actor, run_id=run_id)
    assert_active(run)
    assert_executor(run, executor_token)
    run.status = InvestigationRun.Status.WAITING_HUMAN
    run.clarification_reason = reason
    run.clarification_payload = dict(payload)
    run.save(
        update_fields=[
            "status",
            "clarification_reason",
            "clarification_payload",
            "updated_at",
        ]
    )
    return run


@transaction.atomic
def _set_ready(*, actor, run_id, executor_token) -> InvestigationRun:
    run = locked_run(actor=actor, run_id=run_id)
    assert_active(run)
    assert_executor(run, executor_token)
    decision = evaluate_run_policy(run)
    if decision.outcome != PolicyOutcome.READY_FOR_DECISION:
        raise InvestigationRunError(
            "READY ist durch die Stopppolicy blockiert.",
            code="ready_blocked",
        )
    run.status = InvestigationRun.Status.READY
    run.finished_at = timezone.now()
    run.executor_generation += 1
    run.executor_token = uuid.uuid4()
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "executor_generation",
            "executor_token",
            "updated_at",
        ]
    )
    return run


@transaction.atomic
def _set_failed_planner_contract(
    *,
    actor,
    run_id,
    executor_token,
    error: InvestigationRunError,
) -> InvestigationRun:
    run = locked_run(actor=actor, run_id=run_id)
    assert_active(run)
    assert_executor(run, executor_token)
    run.status = InvestigationRun.Status.FAILED
    run.clarification_reason = ReasonCode.TECHNICAL_FAILURE.value
    run.clarification_payload = {
        "error_code": error.code,
        "impact": "Die Untersuchung wurde wegen eines ungültigen Planner-Vertrags beendet.",
        "required_action": (
            "Planner-/Schema-Vertrag technisch prüfen; keinen fachlichen Schluss ableiten."
        ),
    }
    run.finished_at = timezone.now()
    run.executor_generation += 1
    run.executor_token = uuid.uuid4()
    run.save(
        update_fields=[
            "status",
            "clarification_reason",
            "clarification_payload",
            "finished_at",
            "executor_generation",
            "executor_token",
            "updated_at",
        ]
    )
    return run


@transaction.atomic
def _set_failed_runtime(
    *,
    actor,
    run_id,
    executor_token,
    reason: str,
    error_code: str,
    impact: str,
    required_action: str,
    details: Mapping[str, Any] | None = None,
) -> InvestigationRun:
    run = locked_run(actor=actor, run_id=run_id)
    assert_active(run)
    assert_executor(run, executor_token)
    run.status = InvestigationRun.Status.FAILED
    run.clarification_reason = reason
    run.clarification_payload = {
        "error_code": error_code,
        "impact": impact,
        "required_action": required_action,
        **dict(details or {}),
    }
    run.finished_at = timezone.now()
    run.executor_generation += 1
    run.executor_token = uuid.uuid4()
    run.save(
        update_fields=[
            "status",
            "clarification_reason",
            "clarification_payload",
            "finished_at",
            "executor_generation",
            "executor_token",
            "updated_at",
        ]
    )
    return run


def _planner_contract_error(
    run: InvestigationRun,
    action: PlannerAction,
) -> InvestigationRunError | None:
    pending_investigation = _pending_synthesis_investigation(run)
    allowed_actions = (
        {"tool", "investigate", "clarify"}
        if pending_investigation
        else {"synthesize", "investigate", "clarify"}
        if investigation_evidence_complete(run)
        else {"tool", "clarify"}
    )
    if action.action not in allowed_actions:
        return InvestigationRunError(
            "Planner-Aktion ist ungültig.",
            code="invalid_planner_action",
        )
    if action.action == "synthesize" and (action.tool_name or action.parameters):
        return InvestigationRunError(
            "Eine Synthese darf kein Werkzeug anfordern.",
            code="invalid_planner_action",
        )
    if action.action == "tool" and action.tool_name not in ALLOWED_TOOLS:
        return InvestigationRunError(
            "Planner forderte ein nicht erlaubtes Werkzeug an.",
            code="tool_not_allowed",
        )
    if action.action == "tool":
        try:
            normalize_tool_parameters(
                action.tool_name,
                action.parameters,
                allowed_source_ids=frozenset(
                    str(source_id)
                    for source_id in run.source_snapshot.sources.values_list("pk", flat=True)
                ),
            )
        except InvestigationRunError as exc:
            return exc
    if action.progress_kind not in PLANNER_PROGRESS_KINDS:
        return InvestigationRunError(
            "Planner lieferte eine ungültige Fortschrittsart.",
            code="invalid_progress_kind",
        )
    if action.action == "clarify" and action.clarification_reason not in {
        item.value for item in ReasonCode
    }:
        return InvestigationRunError(
            "Planner lieferte einen ungültigen Klärungsgrund.",
            code="invalid_reason_code",
        )
    return None


def _provider_failures(run: InvestigationRun) -> int:
    """Count consecutive failed calls; a successful response restores retry capacity."""
    failures = 0
    for status in run.model_calls.order_by("-created_at").values_list("status", flat=True):
        if status == "success":
            break
        if status == "failed":
            failures += 1
    return failures


def _pre_verifier_package_attempts_since_verification(run: InvestigationRun) -> int:
    calls = run.model_calls.filter(role="synthesizer", status="success")
    latest_report = run.verifier_reports.order_by("-created_at").first()
    if latest_report is not None:
        calls = calls.filter(created_at__gt=latest_report.created_at)
    latest_input = run.input_revisions.order_by("-created_at").first()
    if latest_input is not None:
        calls = calls.filter(created_at__gt=latest_input.created_at)
    return sum(
        call.get("clarification_reason") != "missing_evidence"
        and not bool(call.get("investigation_request"))
        for call in calls.values_list("accepted_payload", flat=True)
    )


def _handle_provider_failure(
    *,
    actor,
    run: InvestigationRun,
    executor_token,
    error: InvestigationRunError,
) -> AdvanceResult:
    run.refresh_from_db()
    failures = _provider_failures(run)
    if error.code in TRANSIENT_PROVIDER_CODES and failures <= 1:
        decision = evaluate_run_policy(
            run,
            technical_failure=True,
            retry_available=True,
        )
        return AdvanceResult(run.pk, run.status, decision)

    failed = _set_failed_runtime(
        actor=actor,
        run_id=run.pk,
        executor_token=executor_token,
        reason=ReasonCode.TECHNICAL_FAILURE.value,
        error_code=error.code,
        impact="Die Untersuchung ist wegen eines technischen Providerfehlers beendet.",
        required_action="Provider-/Transportfehler technisch prüfen.",
        details={"attempts": failures},
    )
    return AdvanceResult(failed.pk, failed.status, evaluate_run_policy(failed))


def _handle_budget_exhaustion(
    *,
    actor,
    run: InvestigationRun,
    executor_token,
    error_code: str = "budget_exhausted",
) -> AdvanceResult:
    waiting = _set_waiting_human(
        actor=actor,
        run_id=run.pk,
        executor_token=executor_token,
        reason=ReasonCode.BUDGET_EXHAUSTED.value,
        payload={
            "error_code": error_code,
            "impact": "Die Untersuchung ist vor erfolgreicher Verifikation unvollständig.",
            "required_action": "Budget-/Betriebsentscheidung durch einen Menschen.",
        },
    )
    return AdvanceResult(waiting.pk, waiting.status, evaluate_run_policy(waiting))


def _replan_is_distinct(run: InvestigationRun, action: PlannerAction) -> bool:
    if action.action != "tool":
        return action.action in {"clarify", "investigate"}
    try:
        params = normalize_tool_parameters(action.tool_name, action.parameters)
    except InvestigationRunError:
        return False
    # A different tool or request may investigate the same claim. Conversely,
    # changing only the claim ID must not make a repeated request distinct.
    return not any(
        step.parameters == params
        for step in run.steps.filter(
            status=InvestigationStep.Status.SUCCESS,
            tool_name=action.tool_name,
        )
    )


def _try_mark_counterevidence_processed(
    *,
    actor,
    run: InvestigationRun,
    executor_token,
) -> None:
    if not run.counterevidence_search_executed or run.counterevidence_hits_processed:
        return
    try:
        mark_counterevidence_processed(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
        )
    except InvestigationRunError as exc:
        if exc.code != "counterevidence_unread":
            raise


def advance_investigation(
    *,
    actor,
    run_id,
    executor_token,
    planner: Callable[..., PlannerAction] = request_planner_action,
    verifier: Callable[..., InvestigationVerifierReport] = request_verifier_report,
) -> AdvanceResult:
    run = InvestigationRun.objects.select_related(
        "process_analysis__stage__value_stream",
        "source_snapshot__folder",
    ).get(pk=run_id)
    assert_actor_can_edit_run(actor, run)
    assert_active(run)
    assert_executor(run, executor_token)

    if run.status == InvestigationRun.Status.WAITING_HUMAN:
        return AdvanceResult(run.pk, run.status, evaluate_run_policy(run))

    decision = evaluate_run_policy(run)
    if decision.outcome == PolicyOutcome.READY_FOR_DECISION:
        ready = _set_ready(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
        )
        return AdvanceResult(ready.pk, ready.status, decision)

    if budget_exhausted(run):
        return _handle_budget_exhaustion(
            actor=actor,
            run=run,
            executor_token=executor_token,
        )

    try:
        action = planner(actor=actor, run=run, executor_token=executor_token)
    except InvestigationRunError as exc:
        if exc.code in {
            "budget_exhausted",
            "completion_budget_exhausted",
            "input_budget_exhausted",
            "context_capacity_exhausted",
            "runtime_capacity_exhausted",
            "evidence_budget_exhausted",
        }:
            run.refresh_from_db()
            return _handle_budget_exhaustion(
                actor=actor,
                run=run,
                executor_token=executor_token,
                error_code=exc.code,
            )
        if exc.code in TRANSIENT_PROVIDER_CODES | {
            "invalid_response",
            "provider_error",
            "provider_schema_unsupported",
            "output_truncated",
        }:
            return _handle_provider_failure(
                actor=actor,
                run=run,
                executor_token=executor_token,
                error=exc,
            )
        raise

    contract_error = _planner_contract_error(run, action)
    if contract_error is not None:
        _set_failed_planner_contract(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
            error=contract_error,
        )
        raise contract_error

    if action.action == "synthesize":
        apply_planner_state(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
            claim_register=action.claim_register,
            brief_payload=action.brief_payload,
        )
        run.refresh_from_db()

    if action.action == "synthesize" and action.source_relevance:
        set_source_relevance(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
            relevance=action.source_relevance,
        )
        run.refresh_from_db()

    if action.action == "investigate":
        return AdvanceResult(
            run.pk,
            run.status,
            evaluate_run_policy(run),
        )

    if (
        action.action != "synthesize"
        and run.no_progress_streak >= 1
        and not _replan_is_distinct(run, action)
    ):
        waiting = _set_waiting_human(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
            reason=ReasonCode.NO_PROGRESS.value,
            payload={
                "impact": (
                    "Der letzte Werkzeugschritt brachte keine neue Evidenzabdeckung; "
                    "die nächste Aktion würde ihn ohne Erkenntnisgewinn wiederholen."
                ),
                "required_action": "Neue Evidenz, Scope-/Zugriffsentscheidung oder Abbruch.",
                "recent_steps": [
                    {
                        "sequence": step.sequence,
                        "tool": step.tool_name,
                        "target_claim_id": step.target_claim_id,
                    }
                    for step in run.steps.order_by("-sequence")[:2]
                ],
            },
        )
        return AdvanceResult(waiting.pk, waiting.status, evaluate_run_policy(waiting))

    if action.action == "tool":
        step = execute_tool_step(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
            tool_name=action.tool_name,
            parameters=action.parameters,
            target_claim_id=action.target_claim_id,
            expected_discriminating_finding=action.expected_discriminating_finding,
        )
        run.refresh_from_db()
        # A search hit may already have been read before the search. The
        # server-side locator check decides whether every hit is covered.
        if action.tool_name in {"read_source", "search_sources"}:
            _try_mark_counterevidence_processed(
                actor=actor,
                run=run,
                executor_token=executor_token,
            )
            run.refresh_from_db()
        return AdvanceResult(
            run.pk,
            run.status,
            evaluate_run_policy(run),
            step.pk,
        )

    if action.action == "synthesize":
        pre_blockers = pre_verifier_blockers_for_run(run)
        if pre_blockers:
            attempts = _pre_verifier_package_attempts_since_verification(run)
            if attempts >= MAX_PRE_VERIFIER_PACKAGE_ATTEMPTS:
                failed = _set_failed_runtime(
                    actor=actor,
                    run_id=run.pk,
                    executor_token=executor_token,
                    reason=ReasonCode.TECHNICAL_FAILURE.value,
                    error_code="pre_verifier_contract_failed",
                    impact=(
                        "Die Synthese erfüllt den deterministischen Package-Vertrag "
                        "auch nach einem technischen Retry nicht."
                    ),
                    required_action="Synthese-/Pre-Verifier-Vertrag technisch prüfen.",
                    details={
                        "attempts": attempts,
                        "blockers": list(pre_blockers),
                    },
                )
                return AdvanceResult(
                    failed.pk,
                    failed.status,
                    evaluate_run_policy(failed),
                )
            return AdvanceResult(
                run.pk,
                run.status,
                evaluate_run_policy(run),
            )

        # The verifier is runtime-owned. A complete technical package triggers it
        # automatically; the synthesizer never requests verification.
        try:
            report = verifier(
                actor=actor,
                run=run,
                executor_token=executor_token,
            )
        except InvestigationRunError as exc:
            if exc.code in {
                "budget_exhausted",
                "completion_budget_exhausted",
                "input_budget_exhausted",
                "context_capacity_exhausted",
                "runtime_capacity_exhausted",
                "evidence_budget_exhausted",
            }:
                run.refresh_from_db()
                return _handle_budget_exhaustion(
                    actor=actor,
                    run=run,
                    executor_token=executor_token,
                    error_code=exc.code,
                )
            if exc.code in TRANSIENT_PROVIDER_CODES | {
                "invalid_response",
                "provider_error",
                "provider_schema_unsupported",
                "output_truncated",
            }:
                return _handle_provider_failure(
                    actor=actor,
                    run=run,
                    executor_token=executor_token,
                    error=exc,
                )
            raise

        run.refresh_from_db()
        decision = evaluate_run_policy(run)
        if decision.outcome == PolicyOutcome.READY_FOR_DECISION:
            ready = _set_ready(
                actor=actor,
                run_id=run.pk,
                executor_token=executor_token,
            )
            return AdvanceResult(ready.pk, ready.status, decision)

        if not report.success:
            if run.repair_cycles < run.budget_limits["max_repair_cycles"]:
                with transaction.atomic():
                    locked = locked_run(actor=actor, run_id=run.pk)
                    assert_executor(locked, executor_token)
                    locked.repair_cycles += 1
                    locked.save(update_fields=["repair_cycles", "updated_at"])
                repaired_run = InvestigationRun.objects.get(pk=run.pk)
                return AdvanceResult(
                    repaired_run.pk,
                    InvestigationRun.Status.RUNNING,
                    evaluate_run_policy(repaired_run),
                )

            failed = _set_failed_runtime(
                actor=actor,
                run_id=run.pk,
                executor_token=executor_token,
                reason=ReasonCode.VERIFICATION_FAILED.value,
                error_code="verification_failed",
                impact=(
                    "Das Decision Package bleibt nach dem einzigen Repair-Zyklus "
                    "nicht ausreichend verifiziert."
                ),
                required_action="Verifier-/Package-Vertrag technisch prüfen.",
                details={"findings": report.findings},
            )
            return AdvanceResult(failed.pk, failed.status, evaluate_run_policy(failed))

        failed = _set_failed_runtime(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
            reason=ReasonCode.TECHNICAL_FAILURE.value,
            error_code="post_verifier_contract_failed",
            impact="Der Verifier meldet Erfolg, aber READY bleibt deterministisch blockiert.",
            required_action="Runtime-/Policy-Invarianten technisch prüfen.",
            details={"blockers": list(decision.blockers)},
        )
        return AdvanceResult(failed.pk, failed.status, evaluate_run_policy(failed))

    if action.action == "clarify":
        reason = action.clarification_reason or ReasonCode.MISSING_EVIDENCE.value
        waiting = _set_waiting_human(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
            reason=reason,
            payload=action.clarification_payload,
        )
        return AdvanceResult(waiting.pk, waiting.status, evaluate_run_policy(waiting))

    raise AssertionError("validated planner action was not handled")


def run_until_boundary(
    *,
    actor,
    run_id,
    executor_token,
    planner: Callable[..., PlannerAction] = request_planner_action,
    verifier: Callable[..., InvestigationVerifierReport] = request_verifier_report,
    max_iterations: int = 24,
) -> AdvanceResult:
    if max_iterations < 1 or max_iterations > 64:
        raise InvestigationRunError(
            "Iterationsgrenze ist ungültig.",
            code="invalid_iteration_limit",
        )

    last: AdvanceResult | None = None
    for _index in range(max_iterations):
        last = advance_investigation(
            actor=actor,
            run_id=run_id,
            executor_token=executor_token,
            planner=planner,
            verifier=verifier,
        )
        if last.status != InvestigationRun.Status.RUNNING:
            return last

    run = InvestigationRun.objects.get(pk=run_id)
    waiting = _set_waiting_human(
        actor=actor,
        run_id=run.pk,
        executor_token=executor_token,
        reason=ReasonCode.TECHNICAL_FAILURE.value,
        payload={
            "error_code": "iteration_guard",
            "impact": "Die technische Iterationsgrenze wurde ohne terminalen Zustand erreicht.",
            "required_action": "Run prüfen und gezielt fortsetzen oder abbrechen.",
        },
    )
    return AdvanceResult(waiting.pk, waiting.status, evaluate_run_policy(waiting))
