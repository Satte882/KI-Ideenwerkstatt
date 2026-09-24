from __future__ import annotations

from dataclasses import replace

import pytest

from ki_radar.accelerator.investigation_policy import (
    PolicyCheck,
    PolicyOutcome,
    PolicyState,
    ReasonCode,
    VerifierState,
    evaluate_policy,
    is_evidence_claim,
    pre_verifier_blockers,
)


def evidence_ref(source_id: str = "source-1") -> dict[str, object]:
    return {"source_id": source_id, "locator": {"line": 1}, "revision_hash": "a" * 64}


def base_checks() -> tuple[PolicyCheck, ...]:
    ref = evidence_ref()
    return (
        PolicyCheck(
            claim_id="problem",
            area="problem_context",
            claim_kind="fact",
            critical=True,
            status="supported",
            evidence_refs=(ref,),
        ),
        PolicyCheck(
            claim_id="hyp-a",
            area="competing_hypotheses",
            claim_kind="hypothesis",
            critical=True,
            status="supported",
            evidence_refs=(ref,),
        ),
        PolicyCheck(
            claim_id="hyp-b",
            area="competing_hypotheses",
            claim_kind="hypothesis",
            critical=True,
            status="refuted",
            counterevidence_refs=(ref,),
        ),
        PolicyCheck(
            claim_id="opt-ai",
            area="solution_options",
            claim_kind="option",
            critical=True,
            status="open",
            metadata={"non_ai": False},
        ),
        PolicyCheck(
            claim_id="opt-non-ai",
            area="solution_options",
            claim_kind="option",
            critical=True,
            status="open",
            metadata={"non_ai": True, "status_quo": True},
        ),
        PolicyCheck(
            claim_id="risk",
            area="constraints_risks",
            claim_kind="risk",
            critical=True,
            status="supported",
            evidence_refs=(ref,),
        ),
        PolicyCheck(
            claim_id="recommendation",
            area="recommendation_validation",
            claim_kind="recommendation",
            critical=True,
            status="supported",
            evidence_refs=(ref,),
        ),
        PolicyCheck(
            claim_id="validation",
            area="recommendation_validation",
            claim_kind="validation",
            critical=True,
            status="open",
        ),
    )


def valid_verifier(checks: tuple[PolicyCheck, ...], **overrides) -> VerifierState:
    values = {
        "success": True,
        "critical_findings": 0,
        "bound_hashes": {
            "contract": "contract",
            "manifest": "manifest",
            "register": "register",
            "brief": "brief",
        },
        "source_references_valid": True,
        "checked_critical_claims": frozenset(
            c.claim_id for c in checks if c.critical and is_evidence_claim(c.area, c.claim_kind)
        ),
    }
    values.update(overrides)
    return VerifierState(**values)


def ready_state(**overrides) -> PolicyState:
    checks = overrides.pop("checks", base_checks())
    values = {
        "checks": checks,
        "data_check_executed": True,
        "counterevidence_search_executed": True,
        "counterevidence_hits_processed": True,
        "source_relevance_complete": True,
        "contract_hash": "contract",
        "manifest_hash": "manifest",
        "register_hash": "register",
        "brief_hash": "brief",
        "verifier": valid_verifier(checks),
        "repair_available": True,
    }
    values.update(overrides)
    return PolicyState(**values)


def replace_check(checks, claim_id, **changes):
    return tuple(replace(item, **changes) if item.claim_id == claim_id else item for item in checks)


def test_critical_evidence_gap_is_runtime_work_until_external_gap_is_proven():
    checks = replace_check(base_checks(), "problem", status="open", evidence_refs=())
    result = evaluate_policy(ready_state(checks=checks, verifier=None))

    assert result.outcome == PolicyOutcome.CONTINUE
    assert "critical_unresolved:problem" in result.blockers

    external = evaluate_policy(
        ready_state(checks=checks, verifier=None, external_critical_gap=True)
    )
    assert external.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert external.reason_code == ReasonCode.MISSING_EVIDENCE


def test_all_prechecks_and_valid_verifier_are_ready():
    result = evaluate_policy(ready_state())
    assert result.outcome == PolicyOutcome.READY_FOR_DECISION
    assert result.reason_code is None


def test_hallucination_guards_survive_lean_reset():
    checks = replace_check(base_checks(), "problem", evidence_refs=())
    checks = replace_check(checks, "hyp-b", counterevidence_refs=(), evidence_refs=())
    result = evaluate_policy(ready_state(checks=checks, verifier=None))

    assert result.outcome == PolicyOutcome.CONTINUE
    assert "supported_without_evidence:problem" in result.blockers
    assert "refuted_without_evidence:hyp-b" in result.blockers


def test_noncritical_open_evidence_unknown_is_disclosed_not_globally_gated():
    optional = PolicyCheck(
        claim_id="optional-context",
        area="constraints_risks",
        claim_kind="context",
        critical=False,
        status="open",
    )
    checks = (*base_checks(), optional)
    result = evaluate_policy(ready_state(checks=checks))

    assert result.outcome == PolicyOutcome.READY_FOR_DECISION
    assert all("optional_unknown" not in blocker for blocker in result.blockers)


def test_solution_options_and_validation_plan_are_not_evidence_readiness_claims():
    checks = base_checks()
    assert is_evidence_claim("solution_options", "option") is False
    assert is_evidence_claim("recommendation_validation", "validation") is False

    result = evaluate_policy(ready_state(checks=checks))
    pre = pre_verifier_blockers(ready_state(checks=checks, verifier=None))

    assert result.outcome == PolicyOutcome.READY_FOR_DECISION
    assert "critical_unresolved:opt-ai" not in pre
    assert "critical_unresolved:opt-non-ai" not in pre
    assert "critical_unresolved:validation" not in pre


def test_value_tradeoff_requires_human_instead_of_autonomous_weighting():
    result = evaluate_policy(ready_state(verifier=None, value_tradeoff=True))
    assert result.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert result.reason_code == ReasonCode.VALUE_TRADEOFF


def test_verifier_missing_is_runtime_transition_not_human_blocker():
    result = evaluate_policy(ready_state(verifier=None))

    assert result.outcome == PolicyOutcome.CONTINUE
    assert result.reason_code is None
    assert "verifier_missing" in result.blockers


@pytest.mark.parametrize(
    ("mutation", "expected_blocker"),
    [
        (
            {"verifier": valid_verifier(base_checks(), success=False, critical_findings=1)},
            "verifier_critical",
        ),
        (
            {"checks": replace_check(base_checks(), "problem", references_valid=False)},
            "invalid_reference:problem",
        ),
        (
            {"verifier": valid_verifier(base_checks(), source_references_valid=False)},
            "verifier_source_reference_invalid",
        ),
    ],
)
def test_verification_and_reference_failures_never_ready(mutation, expected_blocker):
    result = evaluate_policy(ready_state(**mutation))
    assert result.outcome != PolicyOutcome.READY_FOR_DECISION
    assert expected_blocker in result.blockers


def test_stale_verifier_is_automatically_reverifiable_runtime_state():
    result = evaluate_policy(
        ready_state(
            verifier=valid_verifier(
                base_checks(),
                bound_hashes={
                    "contract": "old",
                    "manifest": "manifest",
                    "register": "register",
                    "brief": "brief",
                },
            )
        )
    )
    assert result.outcome == PolicyOutcome.CONTINUE
    assert "verifier_stale" in result.blockers


def test_budget_exhaustion_before_verification_is_not_success():
    result = evaluate_policy(ready_state(verifier=None, budget_exhausted=True))
    assert result.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert result.reason_code == ReasonCode.BUDGET_EXHAUSTED


def test_no_progress_counter_is_not_a_readiness_or_human_boundary():
    result = evaluate_policy(ready_state(verifier=None, no_progress_streak=2))
    assert result.outcome == PolicyOutcome.CONTINUE
    assert result.reason_code is None


@pytest.mark.parametrize(
    "changed_field",
    ["manifest_hash", "register_hash", "brief_hash", "contract_hash"],
)
def test_relevant_revision_change_invalidates_old_verifier(changed_field):
    result = evaluate_policy(ready_state(**{changed_field: f"new-{changed_field}"}))
    assert result.outcome == PolicyOutcome.CONTINUE
    assert "verifier_stale" in result.blockers


@pytest.mark.parametrize(
    ("state", "blocker"),
    [
        (
            ready_state(checks=replace_check(base_checks(), "problem", change_guard_valid=False)),
            "invalid_claim_revision:problem",
        ),
        (ready_state(question_narrowed=True), "decision_question_changed"),
        (
            ready_state(checks=replace_check(base_checks(), "hyp-b", used_as_premise=True)),
            "refuted_premise_used:hyp-b",
        ),
    ],
)
def test_claim_guard_question_scope_and_refuted_premise_block_ready(state, blocker):
    result = evaluate_policy(state)
    assert result.outcome != PolicyOutcome.READY_FOR_DECISION
    assert blocker in result.blockers


def test_abort_permission_and_restart_persisted_state_fail_closed():
    aborted = evaluate_policy(ready_state(verifier=None, aborted=True))
    assert aborted.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert "run_aborted" in aborted.blockers

    revoked = evaluate_policy(ready_state(verifier=None, permission_or_scope_block=True))
    assert revoked.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert revoked.reason_code == ReasonCode.PERMISSION_OR_SCOPE

    before = ready_state(verifier=None)
    after = replace(before)
    assert evaluate_policy(after) == evaluate_policy(before)
