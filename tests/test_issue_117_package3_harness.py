from __future__ import annotations

from copy import deepcopy

import pytest

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


def _slot(test_type: str):
    return next(
        item for item in package3._contract()["slots"] if item["test_type"] == test_type
    )


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
    assert audit["original_mapping"]["assignments"] == original_payload["structured_mappings"][0][
        "assignments"
    ]
    assert audit["mutated_mapping"] == result.brief_payload["structured_mappings"][0]


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
