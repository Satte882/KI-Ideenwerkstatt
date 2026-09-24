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
            status="supported",
            evidence_refs=(ref,),
            metadata={"non_ai": False},
        ),
        PolicyCheck(
            claim_id="opt-non-ai",
            area="solution_options",
            claim_kind="option",
            critical=True,
            status="supported",
            evidence_refs=(ref,),
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
            status="supported",
            evidence_refs=(ref,),
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
        "checked_critical_claims": frozenset(c.claim_id for c in checks if c.critical),
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
    }
    values.update(overrides)
    return PolicyState(**values)


def replace_check(checks, claim_id, **changes):
    return tuple(replace(item, **changes) if item.claim_id == claim_id else item for item in checks)


def test_01_critical_gap_with_unused_allowed_action_continues():
    checks = replace_check(base_checks(), "problem", status="open", evidence_refs=())
    result = evaluate_policy(
        ready_state(checks=checks, verifier=None, allowed_action_available=True)
    )
    assert result.outcome == PolicyOutcome.CONTINUE
    assert "critical_unresolved:problem" in result.blockers


def test_02_all_conditions_and_valid_verifier_are_ready_even_if_optional_depth_exists():
    result = evaluate_policy(ready_state(allowed_action_available=True))
    assert result.outcome == PolicyOutcome.READY_FOR_DECISION
    assert result.reason_code is None


def test_03_model_confidence_cannot_replace_evidence_or_counterevidence_search():
    checks = replace_check(
        base_checks(),
        "problem",
        evidence_refs=(),
        metadata={"model_confidence": 0.999},
    )
    result = evaluate_policy(
        ready_state(
            checks=checks,
            verifier=None,
            counterevidence_search_executed=False,
            counterevidence_hits_processed=False,
        )
    )
    assert result.outcome != PolicyOutcome.READY_FOR_DECISION
    assert "supported_without_evidence:problem" in result.blockers
    assert "counterevidence_search_missing" in result.blockers


def test_04_conflict_continues_with_discriminating_action_else_missing_evidence():
    checks = replace_check(base_checks(), "hyp-a", status="conflicting")
    continuing = evaluate_policy(
        ready_state(checks=checks, verifier=None, allowed_action_available=True)
    )
    assert continuing.outcome == PolicyOutcome.CONTINUE

    stopped = evaluate_policy(
        ready_state(
            checks=checks,
            verifier=None,
            allowed_action_available=False,
            external_critical_gap=True,
        )
    )
    assert stopped.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert stopped.reason_code == ReasonCode.MISSING_EVIDENCE


def test_05_external_critical_unknown_requires_human_optional_unknown_can_still_be_ready():
    checks = replace_check(base_checks(), "risk", status="open", evidence_refs=())
    critical = evaluate_policy(
        ready_state(checks=checks, verifier=None, external_critical_gap=True)
    )
    assert critical.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert critical.reason_code == ReasonCode.MISSING_EVIDENCE

    optional = PolicyCheck(
        claim_id="optional",
        area="constraints_risks",
        claim_kind="context",
        critical=False,
        status="open",
        optional_unknown_justified=True,
        optional_unknown_verified=True,
    )
    checks = (*base_checks(), optional)
    result = evaluate_policy(ready_state(checks=checks))
    assert result.outcome == PolicyOutcome.READY_FOR_DECISION


def test_open_solution_option_is_a_candidate_not_an_unresolved_unknown():
    open_option = PolicyCheck(
        claim_id="status-quo",
        area="solution_options",
        claim_kind="option",
        critical=False,
        status="open",
        metadata={"non_ai": True, "status_quo": True},
    )
    checks = (*base_checks(), open_option)
    result = evaluate_policy(ready_state(checks=checks))

    assert result.outcome == PolicyOutcome.READY_FOR_DECISION
    assert "optional_unknown_unjustified:status-quo" not in result.blockers


def test_open_non_option_still_requires_explicit_optional_unknown_justification():
    open_context = PolicyCheck(
        claim_id="optional-context",
        area="constraints_risks",
        claim_kind="context",
        critical=False,
        status="open",
    )
    checks = (*base_checks(), open_context)
    result = evaluate_policy(ready_state(checks=checks))

    assert result.outcome != PolicyOutcome.READY_FOR_DECISION
    assert "optional_unknown_unjustified:optional-context" in result.blockers


def test_06_value_tradeoff_requires_human_instead_of_autonomous_weighting():
    result = evaluate_policy(ready_state(verifier=None, value_tradeoff=True))
    assert result.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert result.reason_code == ReasonCode.VALUE_TRADEOFF


@pytest.mark.parametrize(
    ("mutation", "expected_blocker"),
    [
        ({"verifier": None}, "verifier_missing"),
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
        (
            {
                "verifier": valid_verifier(
                    base_checks(),
                    bound_hashes={
                        "contract": "old",
                        "manifest": "manifest",
                        "register": "register",
                        "brief": "brief",
                    },
                )
            },
            "verifier_stale",
        ),
    ],
)
def test_07_verification_reference_and_revision_failures_never_ready(mutation, expected_blocker):
    result = evaluate_policy(ready_state(**mutation))
    assert result.outcome != PolicyOutcome.READY_FOR_DECISION
    assert expected_blocker in result.blockers


def test_08_budget_exhaustion_before_verification_is_not_success():
    result = evaluate_policy(ready_state(verifier=None, budget_exhausted=True))
    assert result.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert result.reason_code == ReasonCode.BUDGET_EXHAUSTED


def test_09_no_progress_and_legitimate_negative_progress_semantics():
    no_progress = evaluate_policy(
        ready_state(
            verifier=None,
            no_progress_streak=2,
            allowed_action_available=False,
            replan_available=False,
        )
    )
    assert no_progress.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert no_progress.reason_code == ReasonCode.NO_PROGRESS

    refuted = replace_check(
        base_checks(),
        "hyp-b",
        status="refuted",
        counterevidence_refs=(evidence_ref(),),
    )
    legitimate = evaluate_policy(
        ready_state(
            checks=refuted,
            verifier=None,
            no_progress_streak=0,
            allowed_action_available=True,
        )
    )
    assert legitimate.outcome == PolicyOutcome.CONTINUE

    negative_search_only = evaluate_policy(
        ready_state(
            verifier=None,
            counterevidence_search_executed=True,
            counterevidence_hits_processed=False,
        )
    )
    assert negative_search_only.outcome != PolicyOutcome.READY_FOR_DECISION


@pytest.mark.parametrize(
    "changed_field",
    ["manifest_hash", "register_hash", "brief_hash", "contract_hash"],
)
def test_10_relevant_revision_change_invalidates_old_verifier(changed_field):
    result = evaluate_policy(ready_state(**{changed_field: f"new-{changed_field}"}))
    assert result.outcome != PolicyOutcome.READY_FOR_DECISION
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
def test_11_claim_downgrade_question_narrowing_and_refuted_premise_block_ready(state, blocker):
    result = evaluate_policy(state)
    assert result.outcome != PolicyOutcome.READY_FOR_DECISION
    assert blocker in result.blockers


def test_12_abort_permission_and_restart_persisted_state_fail_closed():
    aborted = evaluate_policy(ready_state(verifier=None, aborted=True))
    assert aborted.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert "run_aborted" in aborted.blockers

    revoked = evaluate_policy(ready_state(verifier=None, permission_or_scope_block=True))
    assert revoked.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert revoked.reason_code == ReasonCode.PERMISSION_OR_SCOPE

    before = ready_state(verifier=None, allowed_action_available=True)
    after = replace(before)
    assert evaluate_policy(after) == evaluate_policy(before)
