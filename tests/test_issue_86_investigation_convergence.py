from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from ki_radar.accelerator.investigation_diagnostics import build_investigation_diagnostic
from ki_radar.accelerator.investigation_models import InvestigationModelCall, InvestigationRun
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
    assert synthesis["pre_verifier_blockers"] == [
        "decision_brief_recommendation_invalid"
    ]
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
    assert "## Werkzeugschritte" in content
    assert "Exakte doppelte Reads" in content
