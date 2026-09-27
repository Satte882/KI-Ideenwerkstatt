from __future__ import annotations

import json
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from ki_radar.accelerator.investigation_diagnostics import build_investigation_diagnostic
from ki_radar.accelerator.investigation_llm import (
    _reserve_model_call,
    _structured_provider_call,
    _verifier_context,
    request_synthesis_package,
)
from ki_radar.accelerator.investigation_loop import (
    _provider_failures_for_role,
    advance_investigation,
)
from ki_radar.accelerator.investigation_models import InvestigationModelCall, InvestigationRun
from ki_radar.accelerator.investigation_runtime import (
    MODEL_CALL_LIMITS,
    apply_planner_state,
    decision_brief_blockers,
    execute_tool_step,
    mark_counterevidence_processed,
    set_source_relevance,
)
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable
from tests.test_issue_3_investigation_hardening import (
    critical_ids,
    planner_action,
    ready_claims,
    source_ref,
    start_csv_run,
)


@pytest.mark.django_db
def test_run_diagnostic_quantifies_model_time_tokens_and_synthesis_trigger(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue86-diagnostic",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    started = timezone.now() - timedelta(seconds=30)

    InvestigationModelCall.objects.create(
        run=run,
        role=InvestigationModelCall.Role.PLANNER,
        status=InvestigationModelCall.Status.SUCCESS,
        executor_generation=run.executor_generation,
        requested_model="test-model",
        returned_model="test-model",
        model_revision="test-revision",
        prompt_version="planner-test",
        prompt_hash="a" * 64,
        instruction_template="test",
        schema_version="test-schema",
        context_refs={
            "register_hash": "1" * 64,
            "brief_hash": "2" * 64,
        },
        accepted_payload={
            "action": "synthesize",
            "rationale": "Paket jetzt verdichten.",
        },
        accepted_payload_hash="b" * 64,
        prompt_tokens=100,
        completion_tokens=25,
        total_tokens=125,
        started_at=started,
        finished_at=started + timedelta(seconds=5),
    )
    InvestigationModelCall.objects.create(
        run=run,
        role=InvestigationModelCall.Role.SYNTHESIZER,
        status=InvestigationModelCall.Status.SUCCESS,
        executor_generation=run.executor_generation,
        requested_model="test-model",
        returned_model="test-model",
        model_revision="test-revision",
        prompt_version="synthesis-test",
        prompt_hash="c" * 64,
        instruction_template="test",
        schema_version="test-schema",
        effective_parameters={
            "reasoning_effort": "low",
            "max_tokens": 20_000,
            "timeout_seconds": 120,
        },
        context_refs={
            "register_hash": "1" * 64,
            "brief_hash": "2" * 64,
            "synthesis_mode": "pre_verifier_repair",
            "pre_verifier_blockers": ["decision_brief_recommendation_invalid"],
        },
        accepted_payload={
            "claim_register": [],
            "brief_payload": {},
            "source_relevance": {},
        },
        accepted_payload_hash="d" * 64,
        prompt_tokens=200,
        completion_tokens=50,
        total_tokens=250,
        started_at=started + timedelta(seconds=6),
        finished_at=started + timedelta(seconds=16),
    )
    run.started_at = started
    run.finished_at = started + timedelta(seconds=20)
    run.status = InvestigationRun.Status.FAILED
    run.save(update_fields=["started_at", "finished_at", "status", "updated_at"])

    report = build_investigation_diagnostic(run)

    assert report["run_seconds"] == 20.0
    assert report["model_seconds"] == 15.0
    assert report["non_model_seconds"] == 5.0
    assert report["synthesis_count"] == 1
    assert report["synthesis_seconds"] == 10.0
    assert report["role_totals"]["planner"]["prompt_tokens"] == 100
    synthesis = report["model_calls"][1]
    assert synthesis["synthesis_trigger"] == "pre_verifier_repair"
    assert synthesis["pre_verifier_blockers"] == ["decision_brief_recommendation_invalid"]
    assert synthesis["reasoning_effort"] == "low"


@pytest.mark.django_db
def test_diagnose_investigation_run_command_emits_read_only_markdown(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue86-command",
    )
    out = StringIO()

    call_command("diagnose_investigation_run", str(handle.run_id), stdout=out)

    content = out.getvalue()
    assert f"# Investigation-Diagnose {handle.run_id}" in content
    assert "## Modellaufrufe" in content
    assert "Call-Limit" in content
    assert "## Werkzeugschritte" in content
    assert "Exakte doppelte Reads" in content


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "timeout_seconds", "max_output_tokens"),
    [
        (InvestigationModelCall.Role.PLANNER, 90, 16_384),
        (InvestigationModelCall.Role.SYNTHESIZER, 270, 32_768),
        (InvestigationModelCall.Role.VERIFIER, 120, 16_384),
    ],
)
def test_role_specific_provider_wait_and_output_are_capped(
    owner,
    business_unit,
    tmp_path,
    role,
    timeout_seconds,
    max_output_tokens,
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key=f"issue86-role-cap-{role}",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    call = _reserve_model_call(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        role=role,
        instruction="Role cap test",
        prompt_version="role-cap-test",
        schema_version="role-cap-test",
        context={},
    )

    assert call.effective_parameters["timeout_seconds"] == timeout_seconds
    assert call.effective_parameters["max_tokens"] == max_output_tokens
    assert run.execution_snapshot["model_transport"]["role_limits"] == MODEL_CALL_LIMITS


@pytest.mark.django_db
def test_success_in_other_role_does_not_reset_synthesizer_failure_chain(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue86-role-retry-chain",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    for role, status, error_code in [
        (
            InvestigationModelCall.Role.SYNTHESIZER,
            InvestigationModelCall.Status.FAILED,
            "timeout",
        ),
        (
            InvestigationModelCall.Role.PLANNER,
            InvestigationModelCall.Status.SUCCESS,
            "",
        ),
        (
            InvestigationModelCall.Role.SYNTHESIZER,
            InvestigationModelCall.Status.FAILED,
            "timeout",
        ),
    ]:
        InvestigationModelCall.objects.create(
            run=run,
            role=role,
            status=status,
            error_code=error_code,
            executor_generation=run.executor_generation,
            requested_model="test-model",
            returned_model="test-model" if status == "success" else "",
            model_revision="test-revision",
            prompt_version="role-retry-test",
            prompt_hash="a" * 64,
            instruction_template="test",
            schema_version="test-schema",
            accepted_payload={"action": "tool"} if status == "success" else {},
            accepted_payload_hash="b" * 64 if status == "success" else "",
            finished_at=timezone.now(),
        )

    assert _provider_failures_for_role(run, InvestigationModelCall.Role.SYNTHESIZER) == 2
    assert _provider_failures_for_role(run, InvestigationModelCall.Role.PLANNER) == 0


@pytest.mark.django_db
def test_synthesizer_timeout_retries_same_role_once_without_planner_hop(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue86-synth-timeout-retry",
    )
    roles = []

    def fake_openrouter(**kwargs):
        system = kwargs["messages"][0]["content"]
        if "Erzeuge aus dem serverseitig gespeicherten Werkzeugverlauf" in system:
            roles.append("synthesizer")
            raise OpenRouterUnavailable("Timeout", code="timeout")

        roles.append("planner")
        payload = {
            "action": "synthesize",
            "rationale": "Die Quellenarbeit ist abgeschlossen.",
            "tool_name": "",
            "parameters": {},
            "claim_register": [],
            "brief_payload": {},
            "source_relevance": {},
            "progress_kind": "none",
            "progress_payload": {},
            "clarification_reason": "",
            "clarification_payload": {},
        }
        content = json.dumps(payload)
        return OpenRouterResult(
            content=content,
            model="test-model",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
            output_chars=len(content),
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter",
        fake_openrouter,
    )

    first = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
    )
    second = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    assert first.status == InvestigationRun.Status.RUNNING
    assert second.status == InvestigationRun.Status.FAILED
    assert roles == ["planner", "synthesizer", "synthesizer"]
    assert run.clarification_payload["error_code"] == "timeout"
    assert run.clarification_payload["attempts"] == 2
    assert run.clarification_payload["model_role"] == "synthesizer"
    synth_calls = run.model_calls.filter(role=InvestigationModelCall.Role.SYNTHESIZER)
    assert synth_calls.count() == 2
    assert all(call.effective_parameters["timeout_seconds"] == 270 for call in synth_calls)


@pytest.mark.django_db
def test_synthesizer_receives_compact_evidence_context(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue86-compact-synthesis-context",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    captured = {}

    def fake_openrouter(**kwargs):
        captured["context"] = json.loads(kwargs["messages"][1]["content"])
        payload = {
            "claim_register": [],
            "brief_payload": {},
            "source_relevance": {},
            "clarification_reason": "missing_evidence",
            "clarification_payload": {
                "question": "Welche externe Information entscheidet die Richtung?"
            },
            "investigation_request": {},
        }
        content = json.dumps(payload)
        return OpenRouterResult(
            content=content,
            model="test-model",
            usage={
                "prompt_tokens": 120,
                "completion_tokens": 40,
                "reasoning_tokens": 12,
            },
            output_chars=len(content),
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter",
        fake_openrouter,
    )

    action = request_synthesis_package(
        actor=owner,
        run=run,
        executor_token=handle.executor_token,
    )

    context = captured["context"]
    assert action.action == "clarify"
    assert context["context_profile"] == "synthesis_compact_v2"
    assert context["synthesis_mode"] == "initial"
    assert context["claim_register"] == []
    assert context["brief_payload"] == {}
    assert context["source_relevance"] == {}
    assert "evidence_steps" in context
    assert "recent_steps" not in context
    assert "tool_parameter_contracts" not in context
    assert "usage" not in context
    assert "budget_limits" not in context
    assert "policy_blockers" not in context
    assert "latest_verifier" not in context


@pytest.mark.django_db
def test_invalid_optional_calculation_is_pruned_before_brief_persistence(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue86-invalid-optional-calculation",
        decision_brief_required=True,
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    source_reference = {
        "source_id": str(source.source_id),
        "locator": {"row": 1, "column": "group"},
        "revision_hash": source.content_sha256,
    }
    brief = {
        "question_scope": {
            "question": run.decision_question,
            "scope": "Autorisierter Testfall.",
        },
        "problem": {
            "statement": "Die Quelle enthält den betrachteten Befund.",
            "references": [source_reference],
        },
        "calculations": [
            {
                "summary": "Nicht reproduzierbare Modellberechnung.",
                "reference": source_reference,
                "population": {"scope": "Testpopulation"},
                "limits": "Keine reproduzierbare Analyse vorhanden.",
            }
        ],
        "recommendation": {
            "summary": "Befund als Kandidat weiter prüfen.",
            "rationale": "Die Quelle stützt die Richtung.",
            "references": [source_reference],
        },
    }

    apply_planner_state(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        brief_payload=brief,
    )
    run.refresh_from_db()

    assert run.brief_payload["calculations"] == []
    assert not any(
        blocker.startswith("decision_brief_calculation_")
        for blocker in decision_brief_blockers(run)
    )


@pytest.mark.django_db
def test_successful_model_call_persists_reasoning_and_visible_output_diagnostics(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue86-provider-metadata",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    def fake_openrouter(**_kwargs):
        content = '{"ok":true}'
        return OpenRouterResult(
            content=content,
            model="test-model",
            usage={
                "prompt_tokens": 111,
                "completion_tokens": 222,
                "total_tokens": 333,
                "reasoning_tokens": 180,
            },
            output_chars=len(content),
            finish_reason="stop",
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter",
        fake_openrouter,
    )

    _payload, call = _structured_provider_call(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        role=InvestigationModelCall.Role.SYNTHESIZER,
        instruction="Provider metadata test",
        prompt_version="provider-metadata-test",
        schema_version="provider-metadata-test",
        context={
            "context_profile": "synthesis_compact_v1",
            "synthesis_mode": "initial",
        },
        response_format={"type": "json_object"},
    )

    call.refresh_from_db()
    metadata = call.effective_parameters["response_metadata"]
    assert metadata == {
        "output_chars": len('{"ok":true}'),
        "finish_reason": "stop",
        "reasoning_tokens": 180,
    }
    assert call.context_refs["context_profile"] == "synthesis_compact_v1"
    assert call.context_refs["context_chars"] > 0

    diagnostic = build_investigation_diagnostic(run)
    row = diagnostic["model_calls"][0]
    assert row["reasoning_tokens"] == 180
    assert row["output_chars"] == len('{"ok":true}')
    assert row["finish_reason"] == "stop"
    assert row["context_profile"] == "synthesis_compact_v1"


def _prepare_verification(*, owner, business_unit, tmp_path):
    _process, _snapshot, handle, source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue86-verifier-recovery",
        decision_brief_required=True,
    )
    for tool, parameters in [
        ("read_source", {"source_id": str(source.source_id)}),
        ("search_sources", {"query": "A"}),
    ]:
        execute_tool_step(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            tool_name=tool,
            parameters=parameters,
            target_claim_id="problem",
        )
    mark_counterevidence_processed(
        actor=owner, run_id=handle.run_id, executor_token=handle.executor_token
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    brief = {
        "question_scope": {"question": run.decision_question, "scope": "Testfall."},
        "problem": {"statement": "Gruppen unterscheiden sich.", "references": [source_ref(source)]},
        "recommendation": {
            "summary": "Option prüfen.",
            "rationale": "Evidenz trägt diese Richtung.",
            "references": [source_ref(source)],
        },
    }
    apply_planner_state(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        claim_register=ready_claims(source),
        brief_payload=brief,
    )
    set_source_relevance(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        relevance={str(source.source_id): {"relevant": True}},
    )
    run.refresh_from_db()
    return run, handle


@pytest.mark.django_db
@pytest.mark.parametrize("retry_error", ["", "timeout", "provider_unavailable"])
def test_verifier_transport_failure_retries_directly_and_never_regenerates_package(
    owner, business_unit, tmp_path, monkeypatch, retry_error
):
    run, handle = _prepare_verification(owner=owner, business_unit=business_unit, tmp_path=tmp_path)
    original = (run.register_hash, run.brief_hash, run.claim_register, run.brief_payload)
    contexts = []

    def provider(**kwargs):
        contexts.append(json.loads(kwargs["messages"][1]["content"]))
        assert kwargs["timeout_seconds"] == 120
        assert kwargs["max_tokens"] == 16_384
        if len(contexts) == 1 or retry_error:
            raise OpenRouterUnavailable("Transport failure", code=retry_error or "timeout")
        payload = {
            "read_requests": [],
            "findings": [],
            "source_references_valid": True,
            "checked_critical_claims": critical_ids(run.claim_register),
        }
        content = json.dumps(payload)
        return OpenRouterResult(
            content=content,
            model="test-model",
            usage={"prompt_tokens": 100, "completion_tokens": 30},
            output_chars=len(content),
        )

    monkeypatch.setattr("ki_radar.accelerator.investigation_llm.request_openrouter", provider)

    def initial(**_kwargs):
        return planner_action(
            action="synthesize",
            tool_name="",
            parameters={},
            claim_register=tuple(run.claim_register),
            brief_payload=run.brief_payload,
        )

    first = advance_investigation(
        actor=owner, run_id=run.pk, executor_token=handle.executor_token, planner=initial
    )
    assert first.status == InvestigationRun.Status.RUNNING
    assert run.verifier_reports.count() == 0

    def forbidden(**_kwargs):
        raise AssertionError("Verifier recovery must not invoke planner or synthesizer")

    second = advance_investigation(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        planner=forbidden,
        synthesizer=forbidden,
    )
    run.refresh_from_db()
    assert contexts[0] == contexts[1]
    assert original == (run.register_hash, run.brief_hash, run.claim_register, run.brief_payload)
    assert list(run.model_calls.values_list("role", flat=True)) == ["verifier", "verifier"]
    if retry_error:
        assert second.status == InvestigationRun.Status.FAILED
        assert run.clarification_reason == "technical_failure"
        assert run.clarification_payload["attempts"] == 2
        assert run.clarification_payload["model_role"] == "verifier"
        assert run.clarification_payload["error_code"] == retry_error
        assert run.finished_at is not None
        assert run.executor_token != handle.executor_token
        assert run.verifier_reports.count() == 0
    else:
        assert second.status == InvestigationRun.Status.READY
        assert run.verifier_reports.get().success


@pytest.mark.django_db
def test_unchanged_complete_synthesis_goes_to_verifier_without_refresh(
    owner, business_unit, tmp_path, monkeypatch
):
    run, handle = _prepare_verification(owner=owner, business_unit=business_unit, tmp_path=tmp_path)
    InvestigationModelCall.objects.create(
        run=run,
        role="synthesizer",
        status="success",
        executor_generation=run.executor_generation,
        finished_at=timezone.now(),
    )

    def forbidden(**_kwargs):
        raise AssertionError("No ground truth changed; refresh must not run")

    def provider(**kwargs):
        assert json.loads(kwargs["messages"][1]["content"]) == _verifier_context(run)
        payload = {
            "read_requests": [],
            "findings": [],
            "source_references_valid": True,
            "checked_critical_claims": critical_ids(run.claim_register),
        }
        content = json.dumps(payload)
        return OpenRouterResult(content=content, model="test", usage={}, output_chars=len(content))

    monkeypatch.setattr("ki_radar.accelerator.investigation_llm.request_openrouter", provider)
    result = advance_investigation(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        planner=forbidden,
        synthesizer=forbidden,
    )
    assert result.status == InvestigationRun.Status.READY
    assert list(run.model_calls.order_by("created_at").values_list("role", flat=True)) == [
        "synthesizer",
        "verifier",
    ]
