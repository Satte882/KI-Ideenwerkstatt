from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from django.core.management.base import CommandError

from ki_radar.accelerator.investigation_llm import PlannerAction
from ki_radar.accelerator.investigation_runtime import InvestigationRunError
from ki_radar.accelerator.management.commands import run_issue117_package3 as package3


class _FakeCalls:
    def filter(self, **_kwargs):
        return self

    def order_by(self, *_args):
        return self

    def first(self):
        return None


class _FakeRun:
    model_calls = _FakeCalls()
    execution_snapshot = {"decision_brief_required": False}


def _slot(test_type: str):
    return next(item for item in package3._contract()["slots"] if item["test_type"] == test_type)


def _action(slot):
    assignments = [
        {
            "case_key": case_key,
            "value": slot["expected_assignments"][case_key],
            "references": [{"source_id": "source", "locator": {"row": index + 1}}],
        }
        for index, case_key in enumerate(slot["case_keys"])
    ]
    return PlannerAction(
        action="synthesize",
        target_claim_id="",
        expected_discriminating_finding="",
        rationale="",
        tool_name="",
        parameters={},
        claim_register=(),
        brief_payload={
            "structured_mappings": [
                {
                    "obligation_id": "test-obligation",
                    "assignments": assignments,
                }
            ]
        },
        source_relevance={},
        progress_kind="none",
        progress_payload={},
        clarification_reason="",
        clarification_payload={},
    )


def _audit(slot):
    return {
        "declared": deepcopy(slot["mutation"]),
        "applied": False,
        "original_mapping": None,
        "mutated_mapping": None,
        "mutated_brief_hash": None,
        "model_call_id": None,
    }


def test_package3_contract_freezes_small_non_statistical_matrix():
    contract = package3._contract()
    slots = contract["slots"]
    budget = contract["provider_budget"]

    assert [item["test_type"] for item in slots] == [
        "positive",
        "positive",
        "controlled_missing_assignment_repair",
        "semantic_verifier_negative",
    ]
    assert len({item["slot_id"] for item in slots}) == 4
    assert budget == {
        "max_investigation_runs": 5,
        "planned_runs": 4,
        "max_provider_calls_total": 40,
        "max_cost_usd": 5,
        "currency": "USD",
    }


def test_missing_assignment_control_mutates_only_persisted_control_action(monkeypatch):
    slot = _slot("controlled_missing_assignment_repair")
    source_action = _action(slot)
    original_payload = deepcopy(source_action.brief_payload)
    audit = _audit(slot)
    monkeypatch.setattr(package3, "request_synthesis_package", lambda **_kwargs: source_action)

    result = package3.Command()._controlled_synthesizer(slot, audit)(
        actor=None,
        run=_FakeRun(),
        executor_token=None,
    )

    target = slot["mutation"]["case_key"]
    assignments = result.brief_payload["structured_mappings"][0]["assignments"]
    assert {item["case_key"] for item in assignments} == set(slot["case_keys"]) - {target}
    assert source_action.brief_payload == original_payload
    assert audit["applied"] is True
    assert (
        audit["original_mapping"]["assignments"]
        == original_payload["structured_mappings"][0]["assignments"]
    )
    assert audit["mutated_mapping"] == result.brief_payload["structured_mappings"][0]
    assert isinstance(audit["mutated_brief_hash"], str)
    assert len(audit["mutated_brief_hash"]) == 64


def test_semantic_negative_control_changes_exactly_one_predeclared_value(monkeypatch):
    slot = _slot("semantic_verifier_negative")
    source_action = _action(slot)
    original_payload = deepcopy(source_action.brief_payload)
    audit = _audit(slot)
    monkeypatch.setattr(package3, "request_synthesis_package", lambda **_kwargs: source_action)

    result = package3.Command()._controlled_synthesizer(slot, audit)(
        actor=None,
        run=_FakeRun(),
        executor_token=None,
    )

    target = slot["mutation"]["case_key"]
    before = {
        item["case_key"]: item["value"]
        for item in original_payload["structured_mappings"][0]["assignments"]
    }
    after = {
        item["case_key"]: item["value"]
        for item in result.brief_payload["structured_mappings"][0]["assignments"]
    }
    changed = {key for key in before if before[key] != after[key]}

    assert changed == {target}
    assert before[target] == slot["expected_assignments"][target]
    assert after[target] == slot["mutation"]["value"]
    assert source_action.brief_payload == original_payload
    assert audit["applied"] is True
    assert isinstance(audit["mutated_brief_hash"], str)
    assert len(audit["mutated_brief_hash"]) == 64


def test_semantic_negative_control_fails_closed_if_model_is_already_wrong(monkeypatch):
    slot = _slot("semantic_verifier_negative")
    source_action = _action(slot)
    target = slot["mutation"]["case_key"]
    source_action.brief_payload["structured_mappings"][0]["assignments"][1]["value"] = "wrong"
    assert (
        source_action.brief_payload["structured_mappings"][0]["assignments"][1]["case_key"]
        == target
    )
    audit = _audit(slot)
    monkeypatch.setattr(package3, "request_synthesis_package", lambda **_kwargs: source_action)

    with pytest.raises(InvestigationRunError) as exc_info:
        package3.Command()._controlled_synthesizer(slot, audit)(
            actor=None,
            run=_FakeRun(),
            executor_token=None,
        )

    assert exc_info.value.code == "package3_control_precondition"
    assert audit["applied"] is False


class _Records(list):
    def filter(self, **kwargs):
        return _Records(
            item
            for item in self
            if all(getattr(item, key) == value for key, value in kwargs.items())
        )

    def order_by(self, *fields):
        return _Records(sorted(self, key=lambda item: tuple(getattr(item, key) for key in fields)))


def _completed_control(test_type):
    slot = _slot(test_type)
    audit = _audit(slot)
    audit.update(
        applied=True,
        mutated_brief_hash="a" * 64,
        original_mapping=deepcopy(_action(slot).brief_payload["structured_mappings"][0]),
    )
    run = SimpleNamespace(
        status=package3.InvestigationRun.Status.READY,
        brief_hash="b" * 64,
        brief_payload=deepcopy(_action(slot).brief_payload),
        model_calls=_Records(
            [
                SimpleNamespace(
                    role="synthesizer",
                    synthesis_trigger="pre_verifier_repair",
                    status="success",
                    started_at=1,
                    id=1,
                    context_refs={"brief_hash": audit["mutated_brief_hash"]},
                )
            ]
        ),
        verifier_reports=_Records(
            [
                SimpleNamespace(
                    revision=1,
                    success=False,
                    critical_findings=1,
                    bound_hashes={"brief": audit["mutated_brief_hash"]},
                ),
                SimpleNamespace(
                    revision=2,
                    success=True,
                    critical_findings=0,
                    bound_hashes={"brief": "b" * 64},
                ),
            ]
        ),
    )
    return run, slot, audit


@pytest.mark.parametrize(
    "test_type", ["controlled_missing_assignment_repair", "semantic_verifier_negative"]
)
def test_completed_control_requires_bound_evidence(test_type):
    run, slot, audit = _completed_control(test_type)
    package3.Command()._assert_mechanical_expectation(run, slot, audit)


@pytest.mark.parametrize(
    "test_type", ["controlled_missing_assignment_repair", "semantic_verifier_negative"]
)
@pytest.mark.parametrize(
    "defect", ["absent", "wrong_hash", "empty_hash", "failed", "critical", "superseded"]
)
def test_ready_control_rejects_missing_or_stale_final_verifier(test_type, defect):
    run, slot, audit = _completed_control(test_type)
    final_report = run.verifier_reports[-1]
    if defect == "absent":
        run.verifier_reports.pop()
    elif defect == "wrong_hash":
        final_report.bound_hashes = {"brief": "c" * 64}
    elif defect == "empty_hash":
        run.brief_hash = ""
        final_report.bound_hashes = {"brief": ""}
    elif defect == "failed":
        final_report.success = False
    elif defect == "critical":
        final_report.critical_findings = 1
    else:
        run.verifier_reports.append(
            SimpleNamespace(
                revision=3,
                success=False,
                critical_findings=1,
                bound_hashes={"brief": run.brief_hash},
            )
        )
    with pytest.raises(CommandError, match="verifier"):
        package3.Command()._assert_mechanical_expectation(run, slot, audit)


@pytest.mark.parametrize("defect", ["absent", "wrong_hash", "failed", "wrong_trigger"])
def test_missing_assignment_requires_real_repair_bound_to_injected_brief(defect):
    run, slot, audit = _completed_control("controlled_missing_assignment_repair")
    if defect == "absent":
        run.model_calls.clear()
    elif defect == "wrong_hash":
        run.model_calls[0].context_refs = {"brief_hash": "c" * 64}
    elif defect == "failed":
        run.model_calls[0].status = "failed"
    else:
        run.model_calls[0].synthesis_trigger = "initial"
    with pytest.raises(CommandError, match="repair"):
        package3.Command()._assert_mechanical_expectation(run, slot, audit)


@pytest.mark.parametrize(
    "test_type", ["controlled_missing_assignment_repair", "semantic_verifier_negative"]
)
@pytest.mark.parametrize("defect", ["missing", "duplicate", "unexpected", "empty_target"])
def test_ready_control_requires_exact_complete_mapping(test_type, defect):
    run, slot, audit = _completed_control(test_type)
    assignments = run.brief_payload["structured_mappings"][0]["assignments"]
    target = next(item for item in assignments if item["case_key"] == slot["mutation"]["case_key"])
    if defect == "missing":
        assignments.remove(next(item for item in assignments if item is not target))
    elif defect == "duplicate":
        assignments.append(deepcopy(target))
    elif defect == "unexpected":
        assignments[0]["case_key"] = "unexpected"
    else:
        target["value"] = "  "
    with pytest.raises(CommandError):
        package3.Command()._assert_mechanical_expectation(run, slot, audit)


def test_missing_assignment_repair_preserves_retained_values():
    run, slot, audit = _completed_control("controlled_missing_assignment_repair")
    assignments = run.brief_payload["structured_mappings"][0]["assignments"]
    retained = next(
        item for item in assignments if item["case_key"] != slot["mutation"]["case_key"]
    )
    retained["value"] = "changed without evidence"
    with pytest.raises(CommandError, match="retained assignment"):
        package3.Command()._assert_mechanical_expectation(run, slot, audit)


def test_semantic_negative_requires_critical_finding_bound_to_mutation():
    run, slot, audit = _completed_control("semantic_verifier_negative")
    run.verifier_reports[0].bound_hashes = {"brief": "c" * 64}
    with pytest.raises(CommandError, match="critical finding"):
        package3.Command()._assert_mechanical_expectation(run, slot, audit)


@pytest.mark.parametrize("value", ["injected", "another incorrect value"])
def test_semantic_negative_ready_requires_frozen_expected_target_value(value):
    run, slot, audit = _completed_control("semantic_verifier_negative")
    target = next(
        item
        for item in run.brief_payload["structured_mappings"][0]["assignments"]
        if item["case_key"] == slot["mutation"]["case_key"]
    )
    target["value"] = slot["mutation"]["value"] if value == "injected" else value
    with pytest.raises(CommandError, match="semantic value"):
        package3.Command()._assert_mechanical_expectation(run, slot, audit)


def test_semantic_negative_failure_is_evidence_without_claiming_ready():
    run, slot, audit = _completed_control("semantic_verifier_negative")
    run.status = package3.InvestigationRun.Status.FAILED
    run.verifier_reports.pop()
    package3.Command()._assert_mechanical_expectation(run, slot, audit)


@pytest.mark.parametrize(
    "test_type", ["controlled_missing_assignment_repair", "semantic_verifier_negative"]
)
def test_control_requires_persisted_mutation_hash(test_type):
    run, slot, audit = _completed_control(test_type)
    audit["mutated_brief_hash"] = ""
    run.model_calls[0].context_refs = {"brief_hash": ""}
    run.verifier_reports[0].bound_hashes = {"brief": ""}
    with pytest.raises(CommandError, match="injected brief hash"):
        package3.Command()._assert_mechanical_expectation(run, slot, audit)


def test_real_provider_command_requires_explicit_confirmation(monkeypatch):
    def forbidden_contract_read():
        pytest.fail("Provider preflight must not run before explicit confirmation")

    monkeypatch.setattr(package3, "_contract", forbidden_contract_read)
    with pytest.raises(CommandError, match="confirm-real-provider"):
        package3.Command().handle(confirm_real_provider=False)


def test_summary_exports_repair_and_final_verifier_bindings():
    run, slot, audit = _completed_control("controlled_missing_assignment_repair")
    run.refresh_from_db = lambda: None
    run.pk = "test-run"
    run.evidence_metadata = {"tested_commit": "d" * 40}
    run.contract_hash = "contract"
    run.manifest_hash = "manifest"
    run.execution_snapshot = {"structured_mapping_obligations": []}
    run.usage = {}
    for report in run.verifier_reports:
        report.findings = []
        report.model_call_id = report.revision
    call = run.model_calls[0]
    call.pk = call.id
    call.prompt_version = "test-prompt"
    call.schema_version = "test-schema"
    call.accepted_payload_hash = "payload"
    call.error_code = ""

    summary = package3.Command()._summary(run, slot, mutation_audit=audit)

    assert summary["final_brief_hash"] == run.brief_hash
    assert summary["model_calls"][0]["context_refs"]["brief_hash"] == audit["mutated_brief_hash"]
    assert summary["verifier_reports"][-1]["bound_hashes"]["brief"] == summary["final_brief_hash"]
