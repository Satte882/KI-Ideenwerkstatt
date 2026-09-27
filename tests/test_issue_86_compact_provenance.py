from __future__ import annotations

import json
from copy import deepcopy

import pytest

from ki_radar.accelerator.investigation_llm import (
    _compact_source_references,
    _expand_source_references,
    _source_reference_catalog,
    _verifier_context,
    request_synthesis_package,
)
from ki_radar.accelerator.investigation_models import InvestigationModelCall
from ki_radar.accelerator.investigation_runtime import (
    InvestigationRunError,
    apply_planner_state,
    canonical_json,
    content_hash,
)
from ki_radar.core.openrouter import OpenRouterResult
from tests.test_issue_86_investigation_convergence import _prepare_verification

CATALOG = {"S1": {"source_id": "source-a", "revision_hash": "a" * 64}}


@pytest.mark.parametrize("locator", [{"line": 7}, {"row": 5}, {"row": 5, "column": "amount"}])
def test_source_wire_roundtrip_preserves_every_locator_and_full_revision(locator):
    reference = {**CATALOG["S1"], "locator": locator}
    package = {
        "claims": [{"statement": "A fact.", "evidence_refs": [reference]}],
        "brief": {"references": [reference], "counterevidence_refs": [reference]},
        "analysis": {"tool_result_id": "analysis-id", "revision_hash": "b" * 64},
    }
    original = deepcopy(package)
    compact = _compact_source_references(package, CATALOG)
    assert compact["claims"][0]["evidence_refs"] == [{"source_ref": "S1", "locator": locator}]
    assert _expand_source_references(compact, CATALOG) == original
    assert package == original
    assert compact["analysis"] == package["analysis"]


@pytest.mark.parametrize(
    "reference",
    [
        {"source_ref": "S999", "locator": {"line": 7}},
        {"source_ref": "source-from-another-run", "locator": {"line": 7}},
        {"source_ref": ["S1"], "locator": {"line": 7}},
        {"source_ref": "S1"},
        {"source_ref": "S1", "locator": "line 7"},
        {"source_ref": "S1", "locator": {"line": 7}, "source_id": "other"},
        {"source_ref": "S1", "locator": {"line": 7}, "revision_hash": "b" * 64},
    ],
)
def test_unknown_or_ambiguous_wire_reference_fails_without_inferred_provenance(reference):
    with pytest.raises(InvestigationRunError) as exc:
        _expand_source_references({"references": [reference]}, CATALOG)
    assert exc.value.code == "invalid_source_reference"


def test_invalid_canonical_revision_is_never_replaced_by_current_catalog_revision():
    reference = {"source_id": "source-a", "revision_hash": "b" * 64, "locator": {"line": 7}}
    assert _compact_source_references(reference, CATALOG) == reference
    assert _expand_source_references(reference, CATALOG) == reference


def test_malformed_canonical_locator_remains_visible_without_a_transport_repair():
    reference = {**CATALOG["S1"], "locator": "line seven"}
    assert _compact_source_references(reference, CATALOG) == reference
    assert _expand_source_references(reference, CATALOG) == reference


def test_multiple_source_revisions_and_counterevidence_remain_distinct():
    catalog = {**CATALOG, "S2": {"source_id": "source-b", "revision_hash": "b" * 64}}
    package = {
        "evidence_refs": [{**catalog["S1"], "locator": {"line": 7}}],
        "counterevidence_refs": [{**catalog["S2"], "locator": {"line": 9}}],
    }
    compact = _compact_source_references(package, catalog)
    assert compact["evidence_refs"][0]["source_ref"] == "S1"
    assert compact["counterevidence_refs"][0]["source_ref"] == "S2"
    assert _expand_source_references(compact, catalog) == package


@pytest.mark.django_db
def test_real_synthesis_path_audits_wire_output_and_persists_identical_canonical_package(
    owner, business_unit, tmp_path, monkeypatch
):
    run, handle = _prepare_verification(owner=owner, business_unit=business_unit, tmp_path=tmp_path)
    original = (
        deepcopy(run.claim_register),
        deepcopy(run.brief_payload),
        run.register_hash,
        run.brief_hash,
    )
    canonical = {
        "claim_register": run.claim_register,
        "brief_payload": run.brief_payload,
        "source_relevance": run.source_relevance,
    }
    catalog = _source_reference_catalog(run)
    wire = _compact_source_references(canonical, catalog)

    def provider(**kwargs):
        context = json.loads(kwargs["messages"][1]["content"])
        assert context["source_reference_catalog"] == catalog
        assert context["context_profile"] == "synthesis_compact_v2"
        assert kwargs["reasoning_effort"] == "medium"
        content = json.dumps(wire)
        return OpenRouterResult(
            content=content,
            model="test-model",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            output_chars=len(content),
        )

    monkeypatch.setattr("ki_radar.accelerator.investigation_llm.request_openrouter", provider)
    action = request_synthesis_package(actor=owner, run=run, executor_token=handle.executor_token)
    assert list(action.claim_register) == canonical["claim_register"]
    assert action.brief_payload == canonical["brief_payload"]
    assert action.source_relevance == canonical["source_relevance"]
    call = run.model_calls.get()
    assert call.status == InvestigationModelCall.Status.SUCCESS
    assert call.accepted_payload == wire
    assert call.accepted_payload_hash == content_hash(wire)
    assert call.accepted_payload != canonical

    apply_planner_state(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        claim_register=action.claim_register,
        brief_payload=action.brief_payload,
    )
    run.refresh_from_db()
    assert (run.claim_register, run.brief_payload, run.register_hash, run.brief_hash) == original


@pytest.mark.django_db
def test_verifier_transport_preserves_all_claims_brief_trace_replays_and_binding_hashes(
    owner, business_unit, tmp_path
):
    run, _handle = _prepare_verification(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path
    )
    replay = [{"matches": False, "mismatch_fields": ["population"], "source_hash": "x" * 64}]
    wire = _verifier_context(run, analysis_replays=replay)
    catalog = wire["source_reference_catalog"]
    expanded = _expand_source_references(wire, catalog)
    assert expanded["claim_register"] == run.claim_register
    assert expanded["brief_payload"] == run.brief_payload
    assert expanded["source_relevance"] == run.source_relevance
    assert expanded["analysis_replays"] == replay
    assert expanded["tool_trace"] == wire["tool_trace"]
    assert len(wire["tool_trace"]) == run.steps.count()
    assert wire["bound_hashes"] == {
        "contract": run.contract_hash,
        "manifest": run.manifest_hash,
        "register": run.register_hash,
        "brief": run.brief_hash,
    }
    assert [c["claim_id"] for c in wire["claim_register"] if c["critical"]] == [
        c["claim_id"] for c in run.claim_register if c["critical"]
    ]
    # Repeated references save transport data, without dropping statements or locators.
    assert len(canonical_json(wire)) < len(canonical_json(expanded))


@pytest.mark.django_db
def test_invalid_wire_response_is_audited_as_contract_failure_and_cannot_change_package(
    owner, business_unit, tmp_path, monkeypatch
):
    run, handle = _prepare_verification(owner=owner, business_unit=business_unit, tmp_path=tmp_path)
    original = (run.register_hash, run.brief_hash)
    response = {
        "claim_register": run.claim_register,
        "brief_payload": {
            "problem": {"references": [{"source_ref": "S999", "locator": {"line": 7}}]}
        },
        "source_relevance": run.source_relevance,
    }

    def provider(**_kwargs):
        content = json.dumps(response)
        return OpenRouterResult(
            content=content,
            model="test-model",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            output_chars=len(content),
        )

    monkeypatch.setattr("ki_radar.accelerator.investigation_llm.request_openrouter", provider)
    with pytest.raises(InvestigationRunError) as exc:
        request_synthesis_package(actor=owner, run=run, executor_token=handle.executor_token)
    assert exc.value.code == "invalid_response"
    call = run.model_calls.get()
    assert call.status == InvestigationModelCall.Status.FAILED
    assert (
        call.effective_parameters["response_diagnostics"]["structured_contract_error_code"]
        == "invalid_source_reference"
    )
    run.refresh_from_db()
    assert (run.register_hash, run.brief_hash) == original
    assert run.verifier_reports.count() == 0
