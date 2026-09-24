from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

POLICY_VERSION = "vs1-stop-policy-v2"

REQUIRED_AREAS = frozenset(
    {
        "problem_context",
        "competing_hypotheses",
        "solution_options",
        "constraints_risks",
        "recommendation_validation",
    }
)


class PolicyOutcome(StrEnum):
    CONTINUE = "CONTINUE"
    READY_FOR_DECISION = "READY_FOR_DECISION"
    HUMAN_CLARIFICATION = "HUMAN_CLARIFICATION"


class ReasonCode(StrEnum):
    MISSING_EVIDENCE = "missing_evidence"
    FIXED_ROUTE_BOUNDARY = "fixed_route_boundary"
    PERMISSION_OR_SCOPE = "permission_or_scope"
    VALUE_TRADEOFF = "value_tradeoff"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NO_PROGRESS = "no_progress"
    VERIFICATION_FAILED = "verification_failed"
    TECHNICAL_FAILURE = "technical_failure"


@dataclass(frozen=True)
class PolicyCheck:
    claim_id: str
    area: str
    claim_kind: str
    critical: bool
    status: str
    evidence_refs: tuple[Mapping[str, object], ...] = ()
    counterevidence_refs: tuple[Mapping[str, object], ...] = ()
    remaining_assumption: str = ""
    references_valid: bool = True
    change_guard_valid: bool = True
    used_as_premise: bool = False
    optional_unknown_justified: bool = False
    optional_unknown_verified: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class VerifierState:
    success: bool
    critical_findings: int
    bound_hashes: Mapping[str, str]
    source_references_valid: bool = True
    checked_critical_claims: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PolicyState:
    checks: tuple[PolicyCheck, ...]
    data_check_executed: bool
    counterevidence_search_executed: bool
    counterevidence_hits_processed: bool
    source_relevance_complete: bool
    contract_hash: str
    manifest_hash: str
    register_hash: str
    brief_hash: str
    brief_blockers: tuple[str, ...] = ()
    verifier: VerifierState | None = None
    allowed_action_available: bool = False
    external_critical_gap: bool = False
    permission_or_scope_block: bool = False
    value_tradeoff: bool = False
    budget_exhausted: bool = False
    technical_failure: bool = False
    retry_available: bool = False
    no_progress_streak: int = 0
    replan_available: bool = False
    repair_available: bool = False
    question_narrowed: bool = False
    aborted: bool = False


@dataclass(frozen=True)
class PolicyDecision:
    outcome: PolicyOutcome
    reason_code: ReasonCode | None
    blockers: tuple[str, ...]


def _current_hashes(state: PolicyState) -> dict[str, str]:
    return {
        "contract": state.contract_hash,
        "manifest": state.manifest_hash,
        "register": state.register_hash,
        "brief": state.brief_hash,
    }


def _semantic_contract_blockers(checks: tuple[PolicyCheck, ...]) -> list[str]:
    blockers: list[str] = []
    handled_areas = {
        check.area
        for check in checks
        if check.status in {"supported", "refuted", "conflicting"}
        or (
            check.area == "solution_options"
            and check.claim_kind == "option"
            and check.status == "open"
            and not check.used_as_premise
        )
        or (not check.critical and check.optional_unknown_justified)
    }
    for area in sorted(REQUIRED_AREAS - handled_areas):
        blockers.append(f"required_area_open:{area}")

    hypotheses = [
        check
        for check in checks
        if check.area == "competing_hypotheses" and check.claim_kind == "hypothesis"
    ]
    if len(hypotheses) < 2:
        blockers.append("at_least_two_competing_hypotheses_required")

    options = [
        check
        for check in checks
        if check.area == "solution_options" and check.claim_kind == "option"
    ]
    if len(options) < 2:
        blockers.append("at_least_two_solution_options_required")
    if options and not any(bool(check.metadata.get("non_ai")) for check in options):
        blockers.append("non_ai_option_required")
    if options and not any(bool(check.metadata.get("status_quo")) for check in options):
        blockers.append("status_quo_consideration_required")

    recommendation = any(
        check.area == "recommendation_validation" and check.claim_kind == "recommendation"
        for check in checks
    )
    validation = any(
        check.area == "recommendation_validation" and check.claim_kind == "validation"
        for check in checks
    )
    if not recommendation:
        blockers.append("recommendation_required")
    if not validation:
        blockers.append("validation_step_required")
    return blockers


def readiness_blockers(state: PolicyState) -> tuple[str, ...]:
    blockers = _semantic_contract_blockers(state.checks)
    blockers.extend(state.brief_blockers)

    critical_ids: set[str] = set()
    for check in state.checks:
        if check.critical:
            critical_ids.add(check.claim_id)
            if check.status in {"open", "conflicting"}:
                blockers.append(f"critical_unresolved:{check.claim_id}")
        elif (
            check.status == "open"
            and not (
                check.area == "solution_options"
                and check.claim_kind == "option"
                and not check.used_as_premise
            )
            and not (check.optional_unknown_justified and check.optional_unknown_verified)
        ):
            blockers.append(f"optional_unknown_unjustified:{check.claim_id}")

        if check.status == "supported" and not check.evidence_refs:
            blockers.append(f"supported_without_evidence:{check.claim_id}")
        if check.status == "refuted" and not (check.counterevidence_refs or check.evidence_refs):
            blockers.append(f"refuted_without_evidence:{check.claim_id}")
        if not check.references_valid:
            blockers.append(f"invalid_reference:{check.claim_id}")
        if not check.change_guard_valid:
            blockers.append(f"invalid_claim_revision:{check.claim_id}")
        if check.status == "refuted" and check.used_as_premise:
            blockers.append(f"refuted_premise_used:{check.claim_id}")

    if state.question_narrowed:
        blockers.append("decision_question_changed")
    if not state.data_check_executed:
        blockers.append("data_check_missing")
    if not state.counterevidence_search_executed:
        blockers.append("counterevidence_search_missing")
    if not state.counterevidence_hits_processed:
        blockers.append("counterevidence_hits_unprocessed")
    if not state.source_relevance_complete:
        blockers.append("source_relevance_incomplete")

    verifier = state.verifier
    if verifier is None:
        blockers.append("verifier_missing")
    else:
        if not verifier.success or verifier.critical_findings:
            blockers.append("verifier_critical")
        if not verifier.source_references_valid:
            blockers.append("verifier_source_reference_invalid")
        if dict(verifier.bound_hashes) != _current_hashes(state):
            blockers.append("verifier_stale")
        if not critical_ids.issubset(verifier.checked_critical_claims):
            blockers.append("verifier_critical_scope_incomplete")

    return tuple(sorted(set(blockers)))


def evaluate_policy(state: PolicyState) -> PolicyDecision:
    blockers = readiness_blockers(state)
    if not blockers:
        return PolicyDecision(PolicyOutcome.READY_FOR_DECISION, None, ())

    if state.aborted:
        return PolicyDecision(
            PolicyOutcome.HUMAN_CLARIFICATION,
            ReasonCode.TECHNICAL_FAILURE,
            (*blockers, "run_aborted"),
        )
    if state.permission_or_scope_block:
        return PolicyDecision(
            PolicyOutcome.HUMAN_CLARIFICATION,
            ReasonCode.PERMISSION_OR_SCOPE,
            blockers,
        )
    if state.value_tradeoff:
        return PolicyDecision(
            PolicyOutcome.HUMAN_CLARIFICATION,
            ReasonCode.VALUE_TRADEOFF,
            blockers,
        )
    if state.budget_exhausted:
        return PolicyDecision(
            PolicyOutcome.HUMAN_CLARIFICATION,
            ReasonCode.BUDGET_EXHAUSTED,
            blockers,
        )
    if state.technical_failure and not state.retry_available:
        return PolicyDecision(
            PolicyOutcome.HUMAN_CLARIFICATION,
            ReasonCode.TECHNICAL_FAILURE,
            blockers,
        )

    verifier_failed = any(
        blocker == "verifier_critical" or blocker == "verifier_source_reference_invalid"
        for blocker in blockers
    )
    if verifier_failed and not state.repair_available:
        return PolicyDecision(
            PolicyOutcome.HUMAN_CLARIFICATION,
            ReasonCode.VERIFICATION_FAILED,
            blockers,
        )

    if (
        state.no_progress_streak >= 2
        and not state.replan_available
        and not state.allowed_action_available
    ):
        return PolicyDecision(
            PolicyOutcome.HUMAN_CLARIFICATION,
            ReasonCode.NO_PROGRESS,
            blockers,
        )

    if (
        state.allowed_action_available
        or state.replan_available
        or (state.technical_failure and state.retry_available)
    ):
        return PolicyDecision(PolicyOutcome.CONTINUE, None, blockers)

    if state.external_critical_gap:
        return PolicyDecision(
            PolicyOutcome.HUMAN_CLARIFICATION,
            ReasonCode.MISSING_EVIDENCE,
            blockers,
        )
    if "verifier_missing" in blockers or "verifier_stale" in blockers:
        return PolicyDecision(
            PolicyOutcome.HUMAN_CLARIFICATION,
            ReasonCode.VERIFICATION_FAILED,
            blockers,
        )
    return PolicyDecision(
        PolicyOutcome.HUMAN_CLARIFICATION,
        ReasonCode.MISSING_EVIDENCE,
        blockers,
    )
