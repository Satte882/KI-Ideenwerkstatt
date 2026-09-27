from __future__ import annotations

import json
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from ki_radar.accelerator.investigation_diagnostics import build_investigation_diagnostic
from ki_radar.accelerator.investigation_llm import _reserve_model_call
from ki_radar.accelerator.investigation_loop import (
    _provider_failures_for_role,
    advance_investigation,
)
from ki_radar.accelerator.investigation_models import InvestigationModelCall, InvestigationRun
from ki_radar.accelerator.investigation_runtime import MODEL_CALL_LIMITS
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable
from tests.test_issue_3_investigation_hardening import start_csv_run


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
