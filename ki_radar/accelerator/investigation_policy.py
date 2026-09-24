from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

POLICY_VERSION = "vs1-stop-policy-v3"

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
    external_critical_gap: bool = False
    permission_or_scope_block: bool = False
    value_tradeoff: bool = False
    budget_exhausted: bool = False
    technical_failure: bool = False
    retry_available: bool = False
    no_progress_streak: int = 0
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


def is_evidence_claim(area: str, claim_kind: str) -> bool:
    """Return whether a claim belongs to evidence readiness.

    Solution options are candidate proposals and validation steps are future brief
    content. Neither category is an evidence claim and neither may block the
    pre-verifier contract.
    """
    return not (
        (area == "solution_options" and claim_kind == "option")
        or (area == "recommendation_validation" and claim_kind == "validation")
    )


def pre_verifier_blockers(state: PolicyState) -> tuple[str, ...]:
    """Deterministic package contract that must pass before verification."""
    blockers = list(state.brief_blockers)
    evidence_checks = tuple(
        check for check in state.checks if is_evidence_claim(check.area, check.claim_kind)
    )
    if not evidence_checks:
        blockers.append("claim_register_missing")

    for check in evidence_checks:
        if check.critical and check.status in {"open", "conflicting"}:
            blockers.append(f"critical_unresolved:{check.claim_id}")
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

    return tuple(sorted(set(blockers)))


def verifier_blockers(state: PolicyState) -> tuple[str, ...]:
    """Verification state after the deterministic package contract passes."""
    blockers: list[str] = []
    critical_ids = {
        check.claim_id
        for check in state.checks
        if check.critical and is_evidence_claim(check.area, check.claim_kind)
    }
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


def readiness_blockers(state: PolicyState) -> tuple[str, ...]:
    return tuple(sorted(set((*pre_verifier_blockers(state), *verifier_blockers(state)))))


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
    if state.external_critical_gap:
        return PolicyDecision(
            PolicyOutcome.HUMAN_CLARIFICATION,
            ReasonCode.MISSING_EVIDENCE,
            blockers,
        )
    verifier_failed = any(
        blocker in {
            "verifier_critical",
            "verifier_source_reference_invalid",
            "verifier_critical_scope_incomplete",
        }
        for blocker in blockers
    )
    if verifier_failed and not state.repair_available:
        return PolicyDecision(
            PolicyOutcome.HUMAN_CLARIFICATION,
            ReasonCode.VERIFICATION_FAILED,
            blockers,
        )

    # Missing/stale verification and deterministic package blockers are runtime
    # work, not a reason to delegate internal work to a human.
    return PolicyDecision(PolicyOutcome.CONTINUE, None, blockers)
