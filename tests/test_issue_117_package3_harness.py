from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from django.core.management.base import CommandError
from django.utils import timezone

from ki_radar.accelerator import investigation_llm as llm
from ki_radar.accelerator.investigation_llm import PlannerAction
from ki_radar.accelerator.investigation_models import InvestigationModelCall, InvestigationRun
from ki_radar.accelerator.investigation_runtime import (
    InvestigationRunError,
    StartInvestigationRequest,
    apply_planner_state,
    content_hash,
    start_investigation,
    structured_mapping_blockers,
)
from ki_radar.accelerator.management.commands import run_issue117_package3 as package3
from tests.test_issue_117_structured_mapping import make_process, snapshot_for_root


@pytest.fixture(autouse=True)
def forbid_provider_calls(monkeypatch):
    def forbidden(**_kwargs):
        pytest.fail("Package 3 harness tests must never call a real provider")

    monkeypatch.setattr(llm, "_structured_provider_call", forbidden)


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
        # Validate against Django's real model fields without executing a DB query.
        InvestigationModelCall.objects.filter(**kwargs)

        def matches(item, key, value):
            field, _, json_key = key.partition("__")
            actual = getattr(item, field)
            if json_key:
                actual = (actual or {}).get(json_key)
            return actual == value

        return _Records(
            item for item in self if all(matches(item, key, value) for key, value in kwargs.items())
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
                InvestigationModelCall(
                    role="synthesizer",
                    status="success",
                    context_refs={
                        "brief_hash": audit["mutated_brief_hash"],
                        "synthesis_mode": "pre_verifier_repair",
                    },
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


@pytest.mark.parametrize(
    "defect", ["absent", "wrong_hash", "failed", "wrong_trigger", "missing_mode"]
)
def test_missing_assignment_requires_real_repair_bound_to_injected_brief(defect):
    run, slot, audit = _completed_control("controlled_missing_assignment_repair")
    if defect == "absent":
        run.model_calls.clear()
    elif defect == "wrong_hash":
        run.model_calls[0].context_refs["brief_hash"] = "c" * 64
    elif defect == "failed":
        run.model_calls[0].status = "failed"
    elif defect == "wrong_trigger":
        run.model_calls[0].context_refs["synthesis_mode"] = "initial"
    else:
        run.model_calls[0].context_refs.pop("synthesis_mode")
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


def _pending_negative_response(run, audit):
    payload = {
        "findings": [{"severity": "critical", "code": "wrong_routing", "message": "R02 is wrong"}],
        "read_requests": [{"source_id": "source", "cursor": 0, "limit": 5}],
    }
    call = InvestigationModelCall(
        role="verifier",
        status="success",
        context_refs={"brief_hash": audit["mutated_brief_hash"]},
        accepted_payload=payload,
        accepted_payload_hash=content_hash(payload),
    )
    run.model_calls.append(call)
    run.verifier_reports.pop(0)
    return call


def test_semantic_negative_accepts_validated_critical_response_with_pending_read():
    run, slot, audit = _completed_control("semantic_verifier_negative")
    call = _pending_negative_response(run, audit)
    command = package3.Command()
    assert command._negative_verifier_calls(run, audit["mutated_brief_hash"]) == [call]
    command._assert_mechanical_expectation(run, slot, audit)


@pytest.mark.parametrize("defect", ["failed", "planner", "wrong_hash", "tampered", "noncritical"])
def test_semantic_negative_rejects_unbound_or_unvalidated_model_response(defect):
    run, slot, audit = _completed_control("semantic_verifier_negative")
    call = _pending_negative_response(run, audit)
    if defect == "failed":
        call.status = "failed"
    elif defect == "planner":
        call.role = "planner"
    elif defect == "wrong_hash":
        call.context_refs["brief_hash"] = "c" * 64
    elif defect == "tampered":
        call.accepted_payload_hash = "c" * 64
    else:
        call.accepted_payload["findings"][0]["severity"] = "noncritical"
        call.accepted_payload_hash = content_hash(call.accepted_payload)
    with pytest.raises(CommandError, match="critical finding"):
        package3.Command()._assert_mechanical_expectation(run, slot, audit)


@pytest.mark.parametrize("defect", ["missing_report", "stale_report", "wrong_r02"])
def test_pending_negative_response_never_substitutes_for_final_ready_verification(defect):
    run, slot, audit = _completed_control("semantic_verifier_negative")
    _pending_negative_response(run, audit)
    if defect == "missing_report":
        run.verifier_reports.clear()
    elif defect == "stale_report":
        run.verifier_reports[0].bound_hashes["brief"] = audit["mutated_brief_hash"]
    else:
        run.brief_payload["structured_mappings"][0]["assignments"][1]["value"] = "standard"
    with pytest.raises(CommandError):
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
    run.model_calls[0].context_refs["brief_hash"] = ""
    run.verifier_reports[0].bound_hashes = {"brief": ""}
    with pytest.raises(CommandError, match="injected brief hash"):
        package3.Command()._assert_mechanical_expectation(run, slot, audit)


def test_real_provider_command_requires_explicit_confirmation(monkeypatch):
    def forbidden_contract_read():
        pytest.fail("Provider preflight must not run before explicit confirmation")

    monkeypatch.setattr(package3, "_contract", forbidden_contract_read)
    with pytest.raises(CommandError, match="confirm-real-provider"):
        package3.Command().handle(confirm_real_provider=False)


@pytest.mark.parametrize("synthesis_mode", ["pre_verifier_repair", "initial", None])
def test_summary_exports_repair_and_final_verifier_bindings(synthesis_mode):
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
    if synthesis_mode is None:
        call.context_refs.pop("synthesis_mode")
    else:
        call.context_refs["synthesis_mode"] = synthesis_mode
    call.pk = call.id
    call.prompt_version = "test-prompt"
    call.schema_version = "test-schema"
    call.accepted_payload_hash = "payload"
    call.error_code = ""

    summary = package3.Command()._summary(run, slot, mutation_audit=audit)

    assert summary["final_brief_hash"] == run.brief_hash
    assert summary["model_calls"][0]["synthesis_trigger"] == (synthesis_mode or "")
    assert summary["model_calls"][0]["context_refs"]["brief_hash"] == audit["mutated_brief_hash"]
    assert summary["verifier_reports"][-1]["bound_hashes"]["brief"] == summary["final_brief_hash"]


@pytest.mark.parametrize(
    "test_type", ["controlled_missing_assignment_repair", "semantic_verifier_negative"]
)
def test_planner_internal_synthesis_is_mutated_once_before_later_repair(monkeypatch, test_type):
    slot = _slot(test_type)
    action = _action(slot)
    audit = _audit(slot)
    run = _FakeRun()
    run.pk = "test-run"
    monkeypatch.setattr(llm, "assert_actor_can_edit_run", lambda *_args: None)
    monkeypatch.setattr(llm, "_investigation_context", lambda *_args: {})
    monkeypatch.setattr(
        llm, "_structured_provider_call", lambda **_kwargs: ({"action": "synthesize"}, None)
    )
    monkeypatch.setattr(llm, "request_synthesis_package", lambda **_kwargs: action)
    monkeypatch.setattr(package3, "request_synthesis_package", lambda **_kwargs: action)
    command = package3.Command()
    planner = command._controlled_synthesizer(slot, audit, requester=llm.request_planner_action)
    synthesizer = command._controlled_synthesizer(slot, audit)

    first = planner(actor=None, run=run, executor_token=None)
    first_audit = deepcopy(audit)
    assert first.brief_payload != action.brief_payload
    assert audit["applied"] is True
    assert synthesizer(actor=None, run=run, executor_token=None) is action
    assert planner(actor=None, run=run, executor_token=None) is action
    assert audit == first_audit


def _control_snapshot(owner, business_unit, tmp_path, slot):
    process = make_process(owner=owner, business_unit=business_unit)
    rows = [f"{key},{slot['expected_assignments'][key]}" for key in slot["case_keys"]]
    (tmp_path / "cases.csv").write_text("case_id,decision\n" + "\n".join(rows), encoding="utf-8")
    result = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    snapshot = process.investigation_source_snapshots.get(pk=result.snapshot_id)
    return process, snapshot


def _mapping_values(payload):
    return {
        item["case_key"]: item["value"] for item in payload["structured_mappings"][0]["assignments"]
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "test_type", ["controlled_missing_assignment_repair", "semantic_verifier_negative"]
)
def test_control_is_persisted_before_repair_or_verifier(
    owner, business_unit, tmp_path, monkeypatch, test_type
):
    slot = _slot(test_type)
    _process, snapshot = _control_snapshot(owner, business_unit, tmp_path, slot)
    source = snapshot.sources.get(filename="cases.csv")
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.pk,
            idempotency_key="control-sequence",
            structured_mapping_obligations=(
                {
                    "obligation_id": "test-obligation",
                    "source_id": str(source.pk),
                    "case_key_column": "case_id",
                    "case_keys": slot["case_keys"],
                    "mapping_dimension": "routing",
                    "exhaustive": True,
                },
            ),
        ),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    action = _action(slot)
    for assignment in action.brief_payload["structured_mappings"][0]["assignments"]:
        assignment["references"][0].update(
            source_id=str(source.pk), revision_hash=source.content_sha256
        )
    original_context = llm._investigation_context
    monkeypatch.setattr(llm, "_investigation_context", lambda *_args: {})
    monkeypatch.setattr(
        llm, "_structured_provider_call", lambda **_kwargs: ({"action": "synthesize"}, None)
    )

    def initial_synthesis(**_kwargs):
        InvestigationModelCall.objects.create(
            run=run,
            role="synthesizer",
            status="success",
            executor_generation=run.executor_generation,
            prompt_version="test",
            schema_version="test",
            finished_at=timezone.now(),
            context_refs={"synthesis_mode": "initial", "brief_hash": run.brief_hash},
        )
        return action

    monkeypatch.setattr(llm, "request_synthesis_package", initial_synthesis)
    audit = _audit(slot)
    command = package3.Command()
    controlled = command._controlled_synthesizer(slot, audit, requester=llm.request_planner_action)
    initial = controlled(actor=owner, run=run, executor_token=handle.executor_token)
    monkeypatch.setattr(llm, "_investigation_context", original_context)
    apply_planner_state(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        brief_payload=initial.brief_payload,
    )
    run.refresh_from_db()
    assert run.brief_hash == audit["mutated_brief_hash"]
    assert run.verifier_reports.count() == 0
    if test_type == "controlled_missing_assignment_repair":
        assert any("coverage_incomplete" in item for item in structured_mapping_blockers(run))
        context = llm._synthesis_context(owner, run)
        assert context["synthesis_mode"] == "pre_verifier_repair"
        assert _mapping_values(context["brief_payload"]) == _mapping_values(run.brief_payload)

        def repair_request(*, actor, run, executor_token):
            call = llm._reserve_model_call(
                actor=actor,
                run_id=run.pk,
                executor_token=executor_token,
                role="synthesizer",
                instruction="test",
                prompt_version="test",
                schema_version="test",
                context=context,
            )
            assert call.context_refs["brief_hash"] == audit["mutated_brief_hash"]
            assert call.context_refs["synthesis_mode"] == "pre_verifier_repair"
            return action

        monkeypatch.setattr(package3, "request_synthesis_package", repair_request)
        repaired = command._controlled_synthesizer(slot, audit)(
            actor=owner, run=run, executor_token=handle.executor_token
        )
        assert repaired is action
        apply_planner_state(
            actor=owner,
            run_id=run.pk,
            executor_token=handle.executor_token,
            brief_payload=repaired.brief_payload,
        )
        run.refresh_from_db()
        assert structured_mapping_blockers(run) == ()
    else:
        assert structured_mapping_blockers(run) == ()
    context = llm._verifier_context(run)
    assert _mapping_values(context["brief_payload"]) == _mapping_values(run.brief_payload)
    assert context["bound_hashes"]["brief"] == run.brief_hash


@pytest.mark.parametrize("defect", ["wrong_id", "wrong_slot", "missing", "ready", "second"])
def test_replacement_rejects_anything_except_documented_failed_run(defect):
    slot = deepcopy(_slot("controlled_missing_assignment_repair"))
    original = SimpleNamespace(
        pk=package3.REPLACEABLE_RUN_ID, status="failed", evidence_metadata={}
    )
    existing = [original]
    requested = package3.REPLACEABLE_RUN_ID
    if defect == "wrong_id":
        requested = "another-run"
    elif defect == "wrong_slot":
        slot["slot_id"] = "p3-d-ap4-04-semantic-negative"
    elif defect == "missing":
        existing = []
    elif defect == "ready":
        original.status = "ready"
    else:
        existing.append(
            SimpleNamespace(
                pk="replacement", status="failed", evidence_metadata={"replaces_run_id": requested}
            )
        )
    with pytest.raises(CommandError):
        package3.Command()._replacement_target(slot, existing, requested)


@pytest.mark.django_db
def test_explicit_replacement_preserves_original_and_rejects_second(
    owner, business_unit, tmp_path, monkeypatch
):
    slot = _slot("controlled_missing_assignment_repair")
    process, snapshot = _control_snapshot(owner, business_unit, tmp_path, slot)
    original = InvestigationRun.objects.create(
        id=package3.REPLACEABLE_RUN_ID,
        process_analysis=process,
        source_snapshot=snapshot,
        requested_by=owner,
        idempotency_key="documented-failure",
        process_version=process.version,
        decision_question="Control",
        contract_hash="a" * 64,
        manifest_hash=snapshot.manifest_hash,
        status="failed",
        finished_at=timezone.now(),
        evidence_metadata={"experiment_id": package3.EXPERIMENT_ID, "slot_id": slot["slot_id"]},
    )
    before = InvestigationRun.objects.filter(pk=original.pk).values().get()
    for key, value in {
        "ISSUE106_PRICE_INPUT_PER_MILLION": "0.1",
        "ISSUE106_PRICE_OUTPUT_PER_MILLION": "0.4",
        "ISSUE106_PRICING_CURRENCY": "USD",
        "ISSUE106_PRICING_VERSION": "test-only",
    }.items():
        monkeypatch.setenv(key, value)
    command = package3.Command()
    kwargs = dict(
        process=process,
        snapshot=snapshot,
        slot=slot,
        contract=package3._contract(),
        tested_commit="b" * 40,
    )
    with pytest.raises(CommandError, match="no automatic replacement"):
        command._start_slot(**kwargs, replace_run=None)
    handle, campaign = command._start_slot(**kwargs, replace_run=package3.REPLACEABLE_RUN_ID)
    replacement = InvestigationRun.objects.get(pk=handle.run_id)
    assert replacement.evidence_metadata["replaces_run_id"] == str(original.pk)
    assert (
        replacement.evidence_metadata["replacement_reason"]
        == "package3_control_initial_synthesis_bypass"
    )
    assert campaign.campaign_key.endswith("-replacement-1")
    assert replacement.idempotency_key.endswith("-replacement-1")
    assert InvestigationRun.objects.filter(pk=original.pk).values().get() == before
    with pytest.raises(CommandError, match="replacement already exists"):
        command._start_slot(**kwargs, replace_run=package3.REPLACEABLE_RUN_ID)
    assert (
        InvestigationRun.objects.filter(
            evidence_metadata__experiment_id=package3.EXPERIMENT_ID
        ).count()
        == 2
    )
    assert replacement.provider_reservations.count() == 0
