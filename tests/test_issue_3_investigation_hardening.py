from __future__ import annotations

import json
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Barrier

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.utils import timezone

from ki_radar.accelerator.investigation_llm import (
    PlannerAction,
    _decode_structured_field,
    _planner_context,
    _reserve_model_call,
    _structured_provider_call,
    request_planner_action,
    request_synthesis_package,
    request_verifier_report,
)
from ki_radar.accelerator.investigation_loop import (
    TRANSIENT_PROVIDER_CODES,
    _synthesis_attempts_since_verification,
    advance_investigation,
    run_until_boundary,
)
from ki_radar.accelerator.investigation_models import (
    InvestigationModelCall,
    InvestigationRun,
    InvestigationSourceFolder,
    InvestigationToolResult,
    InvestigationVerifierReport,
)
from ki_radar.accelerator.investigation_policy import PolicyOutcome
from ki_radar.accelerator.investigation_prompts import (
    PLANNER_SCHEMA_VERSION,
    PLANNER_TOOL_NAMES,
    TOOL_PARAMETER_CONTRACTS,
    VERIFIER_SCHEMA_VERSION,
    planner_response_format,
    verifier_response_format,
)
from ki_radar.accelerator.investigation_runtime import (
    BUDGET_VERSION,
    ISSUE4_INVESTIGATION_PROVIDER_POLICY,
    InvestigationRunError,
    StartInvestigationRequest,
    apply_planner_state,
    budget_exhausted,
    content_hash,
    evaluate_run_policy,
    execute_tool_step,
    investigation_evidence_complete,
    materialize_brief_revision,
    normalize_claim_register,
    set_source_relevance,
    start_investigation,
)
from ki_radar.accelerator.investigation_tools import (
    SnapshotRequest,
    create_source_snapshot,
    list_sources,
    replay_tool_result,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable


def make_process(*, owner, business_unit, name="VS1/2 Hardening"):
    stream = ValueStream.objects.create(
        name=f"{name} Value Stream",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Prüfung startet",
        outcome="Entscheidung ist dokumentiert",
        scope_in="Prüfung bis Entscheidung",
        status=ValueStream.Status.ACTIVE,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Prüfung",
        description="Fall prüfen.",
        actors="Fachbereich",
        systems="Workflow",
        documents="Fallunterlagen",
        pain_points="Unterschiedliche Laufzeiten",
        baseline_metrics="Offen",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name=name,
        status=ProcessAnalysis.Status.DRAFT,
        scope_start="Fall liegt vor",
        scope_end="Entscheidung liegt vor",
        trigger="Fall wird eingereicht",
        outcome="Nachvollziehbare Entscheidung",
        current_flow="Prüfen und entscheiden.",
        roles="Fachbereich",
        systems="Workflow",
        data_objects="Fallunterlagen",
        business_rules="Keine",
        handoffs="Keine",
        bottlenecks="Unterschiedliche Laufzeiten",
        diagnostic_observations="Laufzeiten schwanken",
        cause_hypotheses="",
        confirmed_causes="",
        constraints="",
        exceptions="",
        baseline_metrics="Offen",
        analyzed_by=owner,
    )


def snapshot_for_root(*, owner, process, root: Path, run_limits=None):
    folder = InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name=f"Quellen {process.name}",
        root_path=str(root),
        registered_by=owner,
    )
    snapshot = create_source_snapshot(
        actor=owner,
        request=SnapshotRequest(
            process_analysis_id=process.pk,
            folder_id=folder.pk,
            decision_question="Welche Lösungsrichtung ist durch Evidenz gestützt?",
            run_limits=run_limits or {},
        ),
    )
    return folder, snapshot


def start_csv_run(*, owner, business_unit, tmp_path, run_limits=None, key="hardening"):
    process = make_process(owner=owner, business_unit=business_unit, name=f"Fall {key}")
    (tmp_path / "cases.csv").write_text(
        "group,value,available,unit\nA,10,yes,h\nA,20,yes,h\nB,30,no,h\nB,40,no,h\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(
        owner=owner,
        process=process,
        root=tmp_path,
        run_limits=run_limits,
    )
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, key),
    )
    source = list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources[0]
    return process, snapshot, handle, source


def planner_action(**overrides):
    values = {
        "action": "tool",
        "target_claim_id": "problem",
        "expected_discriminating_finding": "Begrenzten Befund prüfen.",
        "rationale": "Nächster kontrollierter Schritt.",
        "tool_name": "list_sources",
        "parameters": {},
        "claim_register": (),
        "brief_payload": {},
        "source_relevance": {},
        "progress_kind": "none",
        "progress_payload": {},
        "clarification_reason": "",
        "clarification_payload": {},
    }
    values.update(overrides)
    return PlannerAction(**values)


def source_ref(source, *, row=1, column="group"):
    return {
        "source_id": str(source.source_id),
        "locator": {"row": row, "column": column},
        "revision_hash": source.content_sha256,
    }


def ready_claims(source):
    ref = source_ref(source)
    return (
        {
            "claim_id": "problem",
            "area": "problem_context",
            "claim_kind": "fact",
            "critical": True,
            "status": "supported",
            "evidence_refs": [ref],
        },
        {
            "claim_id": "hyp-a",
            "area": "competing_hypotheses",
            "claim_kind": "hypothesis",
            "critical": True,
            "status": "supported",
            "evidence_refs": [ref],
        },
        {
            "claim_id": "hyp-b",
            "area": "competing_hypotheses",
            "claim_kind": "hypothesis",
            "critical": True,
            "status": "refuted",
            "counterevidence_refs": [ref],
        },
        {
            "claim_id": "opt-ai",
            "area": "solution_options",
            "claim_kind": "option",
            "critical": True,
            "status": "supported",
            "evidence_refs": [ref],
            "metadata": {"non_ai": False},
        },
        {
            "claim_id": "opt-non-ai",
            "area": "solution_options",
            "claim_kind": "option",
            "critical": True,
            "status": "supported",
            "evidence_refs": [ref],
            "metadata": {"non_ai": True, "status_quo": True},
        },
        {
            "claim_id": "risk",
            "area": "constraints_risks",
            "claim_kind": "risk",
            "critical": True,
            "status": "supported",
            "evidence_refs": [ref],
        },
        {
            "claim_id": "recommendation",
            "area": "recommendation_validation",
            "claim_kind": "recommendation",
            "critical": True,
            "status": "supported",
            "evidence_refs": [ref],
        },
        {
            "claim_id": "validation",
            "area": "recommendation_validation",
            "claim_kind": "validation",
            "critical": True,
            "status": "supported",
            "evidence_refs": [ref],
        },
    )


def critical_ids(claims):
    return [str(item["claim_id"]) for item in claims if item.get("critical")]


def create_critical_verifier_report(run):
    call = InvestigationModelCall.objects.create(
        run=run,
        role=InvestigationModelCall.Role.VERIFIER,
        status=InvestigationModelCall.Status.SUCCESS,
        executor_generation=run.executor_generation,
        requested_model="test-model",
        returned_model="test-model",
        model_revision="test-revision",
        prompt_version="test-verifier",
        prompt_hash="a" * 64,
        instruction_template="test",
        schema_version="test-schema",
        accepted_payload={"findings": [{"severity": "critical"}]},
        accepted_payload_hash="b" * 64,
        finished_at=timezone.now(),
    )
    revision = run.verifier_reports.count() + 1
    claims = list(run.claim_register)
    return InvestigationVerifierReport.objects.create(
        run=run,
        revision=revision,
        model_call=call,
        success=False,
        findings=[
            {
                "severity": "critical",
                "code": "test-critical",
                "claim_id": "problem",
                "message": "Kritischer Befund bleibt offen.",
            }
        ],
        critical_findings=1,
        source_references_valid=True,
        checked_critical_claims=critical_ids(claims),
        bound_hashes={
            "contract": run.contract_hash,
            "manifest": run.manifest_hash,
            "register": run.register_hash,
            "brief": run.brief_hash,
        },
        created_for_executor_generation=run.executor_generation,
    )


@pytest.mark.django_db
def test_verifier_replays_analysis_without_side_effect_and_mismatch_blocks_success(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    _process, _snapshot, handle, source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="replay",
    )
    step = execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(source.source_id),
            "group_by": "available",
            "aggregation": "mean",
            "value_column": "value",
            "filters": [],
            "unit_column": "unit",
        },
        target_claim_id="hyp-availability",
    )
    result_id = step.result_ref["tool_result_id"]
    before_count = InvestigationToolResult.objects.count()
    replay = replay_tool_result(actor=owner, result_id=result_id)
    assert replay.matches is True
    assert replay.stored_hash == replay.replay_hash
    assert InvestigationToolResult.objects.count() == before_count

    mismatch = replace(
        replay,
        matches=False,
        replay_hash="0" * 64,
        mismatch_fields=("result_payload",),
    )
    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.replay_tool_result",
        lambda **_kwargs: mismatch,
    )
    seen_contexts = []

    def fake_openrouter(**kwargs):
        context = json.loads(kwargs["messages"][1]["content"])
        seen_contexts.append(context)
        payload = {
            "read_requests": [],
            "findings": [],
            "source_references_valid": True,
            "checked_critical_claims": [],
        }
        raw = json.dumps(payload)
        return OpenRouterResult(
            content=raw,
            model="test-model",
            usage={"prompt_tokens": 20, "completion_tokens": 10},
            output_chars=len(raw),
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter",
        fake_openrouter,
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    report = request_verifier_report(
        actor=owner,
        run=run,
        executor_token=handle.executor_token,
    )

    assert report.success is False
    assert report.critical_findings == 1
    assert report.findings[0]["code"] == "deterministic_analysis_replay_mismatch"
    assert seen_contexts[0]["analysis_replays"][0]["matches"] is False
    assert report.model_call.context_refs["source_snapshot_id"] == str(run.source_snapshot_id)
    assert report.bound_hashes["manifest"] == run.manifest_hash
    assert run.execution_snapshot["verifier"]["prompt_version"]


@pytest.mark.django_db
def test_replay_detects_real_persisted_result_payload_tamper(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="replay-tamper",
    )
    step = execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(source.source_id),
            "group_by": "available",
            "aggregation": "mean",
            "value_column": "value",
            "filters": [],
            "unit_column": "unit",
        },
        target_claim_id="hyp-availability",
    )
    result_id = step.result_ref["tool_result_id"]

    with pytest.raises(ValidationError):
        InvestigationToolResult.objects.filter(pk=result_id).update(
            result_payload={"status": "tampered"}
        )

    stored = InvestigationToolResult.objects.get(pk=result_id)
    tampered_payload = dict(stored.result_payload)
    tampered_payload["differences"] = [
        {
            "from_group": "yes",
            "to_group": "no",
            "delta": "999",
        }
    ]
    field = InvestigationToolResult._meta.get_field("result_payload")
    db_value = field.get_db_prep_value(tampered_payload, connection)
    assert InvestigationToolResult._meta.db_table == "accelerator_investigationtoolresult"

    with connection.cursor() as cursor:
        cursor.execute(
            (
                'UPDATE "accelerator_investigationtoolresult" '
                'SET "result_payload" = %s WHERE "id" = %s'
            ),
            [db_value, result_id],
        )

    replay = replay_tool_result(actor=owner, result_id=result_id)

    assert replay.matches is False
    assert "result_payload" in replay.mismatch_fields
    assert replay.stored_hash != replay.replay_hash


@pytest.mark.django_db
def test_legitimate_negative_progress_survives_but_repeated_null_step_stops(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Negative Progress")
    (tmp_path / "notes.txt").write_text(
        "Hypothese A widerlegt\nHypothese B widerlegt\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "negative-progress"),
    )
    source = list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources[0]
    ref_a = {
        "source_id": str(source.source_id),
        "locator": {"line": 1},
        "revision_hash": source.content_sha256,
    }
    ref_b = {
        "source_id": str(source.source_id),
        "locator": {"line": 2},
        "revision_hash": source.content_sha256,
    }
    claim_a = {
        "claim_id": "hyp-a",
        "area": "competing_hypotheses",
        "claim_kind": "hypothesis",
        "critical": True,
        "status": "refuted",
        "counterevidence_refs": [ref_a],
    }
    claim_b = {
        "claim_id": "hyp-b",
        "area": "competing_hypotheses",
        "claim_kind": "hypothesis",
        "critical": True,
        "status": "refuted",
        "counterevidence_refs": [ref_b],
    }
    actions = iter(
        [
            planner_action(
                target_claim_id="hyp-a",
                tool_name="search_sources",
                parameters={"query": "Hypothese A", "cursor": 0, "limit": 20},
                claim_register=(claim_a,),
                progress_kind="refutation",
                progress_payload={"coverage_change": True},
            ),
            planner_action(
                target_claim_id="hyp-b",
                tool_name="search_sources",
                parameters={"query": "Hypothese B", "cursor": 0, "limit": 20},
                claim_register=(claim_a, claim_b),
                progress_kind="refutation",
                progress_payload={"coverage_change": True},
            ),
        ]
    )

    def negative_planner(**_kwargs):
        return next(actions)

    first = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=negative_planner,
    )
    second = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=negative_planner,
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert first.status == second.status == InvestigationRun.Status.RUNNING
    assert run.no_progress_streak == 0

    null_action = planner_action(
        target_claim_id="remaining-gap",
        tool_name="search_sources",
        parameters={"query": "ZZZ-null", "cursor": 0, "limit": 20},
        claim_register=(claim_a, claim_b),
    )

    def null_planner(**_kwargs):
        return null_action

    third = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=null_planner,
    )
    fourth = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=null_planner,
    )
    run.refresh_from_db()
    assert third.status == InvestigationRun.Status.RUNNING
    assert fourth.status == InvestigationRun.Status.WAITING_HUMAN
    assert run.clarification_reason == "no_progress"


@pytest.mark.django_db
def test_distinct_source_reads_and_csv_profile_on_same_claim_are_progress(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Source Coverage")
    (tmp_path / "01_note.md").write_text("Initiale Hypothese.\n", encoding="utf-8")
    (tmp_path / "02_counter.md").write_text("Gegenbeleg zur Hypothese.\n", encoding="utf-8")
    (tmp_path / "cases.csv").write_text("group,hours\nA,5\nB,29\n", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "source-coverage"),
    )
    sources = {
        source.filename: source
        for source in list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources
    }
    note = sources["01_note.md"]
    counter = sources["02_counter.md"]
    csv = sources["cases.csv"]
    claim = {
        "claim_id": "C1",
        "area": "competing_hypotheses",
        "claim_kind": "hypothesis",
        "critical": True,
        "status": "open",
        "evidence_refs": [
            {
                "source_id": str(note.source_id),
                "locator": {"line": 1},
                "revision_hash": note.content_sha256,
            }
        ],
    }
    actions = iter(
        [
            planner_action(
                target_claim_id="claim_register",
                tool_name="read_source",
                parameters={"source_id": str(note.source_id)},
            ),
            planner_action(
                target_claim_id="C1",
                tool_name="read_source",
                parameters={"source_id": str(counter.source_id)},
                claim_register=(claim,),
            ),
            planner_action(
                target_claim_id="C1",
                tool_name="profile_csv",
                parameters={"source_id": str(csv.source_id)},
                claim_register=(claim,),
            ),
        ]
    )

    def planner(**_kwargs):
        return next(actions)

    for expected_tool in ("read_source", "read_source", "profile_csv"):
        result = advance_investigation(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            planner=planner,
        )
        run = InvestigationRun.objects.get(pk=handle.run_id)
        assert result.status == InvestigationRun.Status.RUNNING
        assert run.no_progress_streak == 0
        assert run.steps.order_by("-sequence").first().tool_name == expected_tool
    assert run.usage["tool_calls"] == 3
    assert run.data_check_executed is True


@pytest.mark.django_db
def test_repeated_read_with_changed_claim_id_does_not_reset_progress(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Repeated Read")
    (tmp_path / "note.md").write_text("Ein Befund.\n", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "repeated-read"),
    )
    source = list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources[0]
    targets = iter(("C1", "C2", "C3"))

    def planner(**_kwargs):
        return planner_action(
            target_claim_id=next(targets),
            tool_name="read_source",
            parameters={"source_id": str(source.source_id)},
        )

    statuses = [
        advance_investigation(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            planner=planner,
        ).status
        for _ in range(3)
    ]
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert statuses == [
        InvestigationRun.Status.RUNNING,
        InvestigationRun.Status.RUNNING,
        InvestigationRun.Status.WAITING_HUMAN,
    ]
    assert run.clarification_reason == "no_progress"
    assert run.usage["tool_calls"] == 2


@pytest.mark.django_db
def test_distinct_data_check_is_allowed_after_two_unproductive_steps(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="distinct-replan",
    )
    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="list_sources",
        parameters={},
        target_claim_id="C1",
    )
    apply_planner_state(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
    )
    action = planner_action(
        target_claim_id="C1",
        tool_name="profile_csv",
        parameters={"source_id": str(source.source_id)},
    )

    def planner(**_kwargs):
        return action

    result = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=planner,
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert result.status == InvestigationRun.Status.RUNNING
    assert run.usage["tool_calls"] == 2
    assert run.data_check_executed is True
    assert run.no_progress_streak == 0


@pytest.mark.django_db
def test_evidence_linked_claim_counts_even_with_planner_progress_none(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="claim-progress",
    )
    apply_planner_state(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
    )
    claim = {
        "claim_id": "C1",
        "area": "competing_hypotheses",
        "claim_kind": "hypothesis",
        "critical": True,
        "status": "open",
        "evidence_refs": [source_ref(source)],
    }
    run = apply_planner_state(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        claim_register=(claim,),
        progress_kind="none",
    )
    assert run.no_progress_streak == 0
    assert run.last_progress_at is not None


@pytest.mark.django_db
def test_provider_timeout_retries_once_then_fails_closed(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Timeout")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "timeout"),
    )

    def timeout_provider(**_kwargs):
        raise OpenRouterUnavailable("Timeout", code="timeout")

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter",
        timeout_provider,
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
    assert first.policy.outcome == PolicyOutcome.CONTINUE
    assert second.status == InvestigationRun.Status.WAITING_HUMAN
    assert run.clarification_reason == "technical_failure"
    assert run.usage["provider_attempts"] == 2
    assert run.status != InvestigationRun.Status.READY


@pytest.mark.django_db
def test_empty_provider_response_retries_once_then_fails_closed(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(
        owner=owner,
        business_unit=business_unit,
        name="Empty response",
    )
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "empty-response"),
    )
    diagnostics = {
        "response_type": "dict",
        "choices_count": 1,
        "finish_reason": "stop",
        "content_type": "str",
        "content_length": 0,
        "has_reasoning": False,
        "usage_prompt_tokens": 100,
        "usage_completion_tokens": 200,
        "usage_total_tokens": 300,
    }

    def empty_provider(**_kwargs):
        raise OpenRouterUnavailable(
            "OpenRouter hat keine Analyse zurückgegeben.",
            code="empty_response",
            diagnostics=diagnostics,
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter",
        empty_provider,
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
    calls = list(run.model_calls.order_by("created_at"))

    assert first.status == InvestigationRun.Status.RUNNING
    assert first.policy.outcome == PolicyOutcome.CONTINUE
    assert second.status == InvestigationRun.Status.WAITING_HUMAN
    assert run.loop_version == "vs1-agent-loop-v9"
    assert run.execution_snapshot["loop_version"] == "vs1-agent-loop-v9"
    assert run.clarification_reason == "technical_failure"
    assert run.clarification_payload["error_code"] == "empty_response"
    assert run.clarification_payload["attempts"] == 2
    assert [(call.status, call.error_code) for call in calls] == [
        (InvestigationModelCall.Status.FAILED, "empty_response"),
        (InvestigationModelCall.Status.FAILED, "empty_response"),
    ]
    assert all(call.effective_parameters["response_diagnostics"] == diagnostics for call in calls)


@pytest.mark.django_db
def test_provider_response_shape_diagnostics_are_persisted_for_retry(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Response shape")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "response-shape"),
    )
    diagnostics = {
        "response_type": "dict",
        "has_error": False,
        "choices_type": "NoneType",
        "choices_count": 0,
    }

    def malformed_provider(**_kwargs):
        raise OpenRouterUnavailable(
            "Unerwartete OpenRouter-Antwort.",
            code="provider_response_malformed",
            diagnostics=diagnostics,
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter",
        malformed_provider,
    )
    result = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
    )
    call = InvestigationRun.objects.get(pk=handle.run_id).model_calls.get()

    assert result.status == InvestigationRun.Status.RUNNING
    assert call.status == InvestigationModelCall.Status.FAILED
    assert call.error_code == "provider_response_malformed"
    assert call.effective_parameters["response_diagnostics"] == diagnostics


@pytest.mark.django_db
def test_invalid_provider_response_retries_once_then_fails_closed(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Invalid response")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "invalid-response"),
    )
    provider_calls = 0

    def invalid_provider(**_kwargs):
        nonlocal provider_calls
        provider_calls += 1
        return OpenRouterResult(
            content="{invalid-json",
            model="test-model",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
            output_chars=13,
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter",
        invalid_provider,
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
    assert first.policy.outcome == PolicyOutcome.CONTINUE
    assert second.status == InvestigationRun.Status.WAITING_HUMAN
    assert provider_calls == 2
    assert run.clarification_reason == "technical_failure"
    assert run.clarification_payload["error_code"] == "invalid_response"
    assert run.clarification_payload["attempts"] == 2
    assert run.usage == {
        "tool_calls": 0,
        "model_calls": 2,
        "input_tokens": 0,
        "output_tokens": 0,
        "verifier_calls": 0,
        "verifier_reads": 0,
        "provider_attempts": 2,
    }
    assert list(run.model_calls.values_list("status", "error_code")) == [
        (InvestigationModelCall.Status.FAILED, "invalid_response"),
        (InvestigationModelCall.Status.FAILED, "invalid_response"),
    ]


@pytest.mark.django_db
def test_successful_planner_call_resets_transient_response_retry(
    owner, business_unit, tmp_path, monkeypatch
):
    process = make_process(owner=owner, business_unit=business_unit, name="Retry after success")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "retry-after-success"),
    )
    provider_calls = 0

    def provider(**_kwargs):
        nonlocal provider_calls
        provider_calls += 1
        if provider_calls != 2:
            content = "{invalid-json"
        else:
            content = json.dumps(
                {
                    "action": "tool",
                    "target_claim_id": "manifest",
                    "expected_discriminating_finding": "Quellen erfassen.",
                    "rationale": "Vorhandene Quellen prüfen.",
                    "tool_name": "list_sources",
                    "parameters": "{}",
                    "claim_register": "null",
                    "brief_payload": "null",
                    "source_relevance": "{}",
                    "progress_kind": "none",
                    "progress_payload": "{}",
                    "clarification_reason": "",
                    "clarification_payload": "{}",
                }
            )
        return OpenRouterResult(
            content=content,
            model="test-model",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
            output_chars=len(content),
        )

    monkeypatch.setattr("ki_radar.accelerator.investigation_llm.request_openrouter", provider)
    results = [
        advance_investigation(
            actor=owner, run_id=handle.run_id, executor_token=handle.executor_token
        )
        for _ in range(3)
    ]
    run = InvestigationRun.objects.get(pk=handle.run_id)

    assert [result.status for result in results] == [InvestigationRun.Status.RUNNING] * 3
    assert [result.policy.outcome for result in results[::2]] == [PolicyOutcome.CONTINUE] * 2
    assert list(run.model_calls.order_by("created_at").values_list("status", flat=True)) == [
        InvestigationModelCall.Status.FAILED,
        InvestigationModelCall.Status.SUCCESS,
        InvestigationModelCall.Status.FAILED,
    ]
    assert run.steps.count() == 1


@pytest.mark.django_db
def test_post_provider_structured_field_decode_failure_is_capped_by_retry_policy(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Opaque field failure")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "opaque-field-failure"),
    )
    provider_calls = 0

    def invalid_opaque_field_provider(**_kwargs):
        nonlocal provider_calls
        provider_calls += 1
        payload = {
            "action": "tool",
            "target_claim_id": "problem",
            "expected_discriminating_finding": "Quelle lesen.",
            "rationale": "Beleg prüfen.",
            "tool_name": "list_sources",
            "parameters": "",
            "claim_register": "[]",
            "brief_payload": "{}",
            "source_relevance": "{}",
            "progress_kind": "none",
            "progress_payload": "{}",
            "clarification_reason": "",
            "clarification_payload": "{}",
        }
        raw = json.dumps(payload)
        return OpenRouterResult(
            content=raw,
            model="test-model",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
            output_chars=len(raw),
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter",
        invalid_opaque_field_provider,
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
    calls = list(run.model_calls.order_by("created_at"))

    assert first.status == InvestigationRun.Status.RUNNING
    assert second.status == InvestigationRun.Status.WAITING_HUMAN
    assert provider_calls == 2
    assert run.clarification_reason == "technical_failure"
    assert run.clarification_payload["error_code"] == "invalid_response"
    assert run.clarification_payload["attempts"] == 2
    assert [(call.status, call.error_code) for call in calls] == [
        (InvestigationModelCall.Status.FAILED, "invalid_response"),
        (InvestigationModelCall.Status.FAILED, "invalid_response"),
    ]
    assert all(call.returned_model == "test-model" for call in calls)
    assert all(call.prompt_tokens == 50 for call in calls)
    assert all(call.completion_tokens == 25 for call in calls)
    assert all(
        "structured_contract_error" in call.effective_parameters["response_diagnostics"]
        for call in calls
    )
    assert run.usage["input_tokens"] == 100
    assert run.usage["output_tokens"] == 50
    assert run.steps.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("invalid_parameters", "error_fragment"),
    [
        ({"group_column": "available", "value_column": "value"}, "group_column"),
        ({"group_by": "missing", "aggregation": "mean", "value_column": "value"}, "missing"),
    ],
)
def test_invalid_model_tool_parameters_get_one_informed_retry_before_execution(
    owner, business_unit, tmp_path, monkeypatch, invalid_parameters, error_fragment
):
    _process, _snapshot, handle, source = start_csv_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="tool-contract-retry"
    )
    provider_calls = 0

    def provider(**kwargs):
        nonlocal provider_calls
        provider_calls += 1
        context = json.loads(kwargs["messages"][1]["content"])
        contract = context["tool_parameter_contracts"]["compare_groups"]
        assert contract["required"] == ["source_id", "group_by", "aggregation"]
        if provider_calls == 1:
            assert context["last_planner_error"] == {}
            parameters = {"source_id": str(source.source_id), **invalid_parameters}
        else:
            assert error_fragment in context["last_planner_error"]["detail"]
            parameters = {
                "source_id": str(source.source_id),
                "group_by": "available",
                "aggregation": "mean",
                "value_column": "value",
                "unit_column": "unit",
            }
        payload = {
            "action": "tool",
            "target_claim_id": "hypothesis",
            "expected_discriminating_finding": "Gruppen vergleichen.",
            "rationale": "Quantitative Evidenz prüfen.",
            "tool_name": "compare_groups",
            "parameters": json.dumps(parameters),
            "claim_register": "[]",
            "brief_payload": "{}",
            "source_relevance": "{}",
            "progress_kind": "none",
            "progress_payload": "{}",
            "clarification_reason": "",
            "clarification_payload": "{}",
        }
        raw = json.dumps(payload)
        return OpenRouterResult(
            content=raw,
            model="test-model",
            usage={"prompt_tokens": 100, "completion_tokens": 200},
            output_chars=len(raw),
        )

    monkeypatch.setattr("ki_radar.accelerator.investigation_llm.request_openrouter", provider)
    first = advance_investigation(
        actor=owner, run_id=handle.run_id, executor_token=handle.executor_token
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    failed_call = run.model_calls.get()
    assert first.status == InvestigationRun.Status.RUNNING
    assert run.steps.count() == 0
    assert failed_call.status == InvestigationModelCall.Status.FAILED
    assert failed_call.error_code == "invalid_response"
    assert (
        failed_call.effective_parameters["response_diagnostics"]["structured_contract_error_code"]
        == "invalid_tool_parameters"
    )

    second = advance_investigation(
        actor=owner, run_id=handle.run_id, executor_token=handle.executor_token
    )
    run.refresh_from_db()
    assert second.status == InvestigationRun.Status.RUNNING
    assert provider_calls == 2
    assert run.model_calls.filter(status=InvestigationModelCall.Status.SUCCESS).count() == 1
    assert list(run.steps.values_list("tool_name", "status")) == [("compare_groups", "success")]
    assert run.data_check_executed is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("first_claims", "first_brief"),
    [
        ("[]", "{}"),
        ('[{"claim_id":"replacement"}]', "null"),
        ("null", "{}"),
    ],
)
def test_unchanged_planner_state_cannot_erase_claims_or_brief(
    owner, business_unit, tmp_path, monkeypatch, first_claims, first_brief
):
    _process, _snapshot, handle, source = start_csv_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="state-preservation"
    )
    claim = {
        "claim_id": "observed",
        "area": "problem_context",
        "claim_kind": "observation",
        "status": "supported",
        "evidence_refs": [source_ref(source)],
    }
    apply_planner_state(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        claim_register=(claim,),
        brief_payload={"draft": "Evidenzgestützter Arbeitsstand"},
    )
    provider_calls = 0

    def provider(**_kwargs):
        nonlocal provider_calls
        provider_calls += 1
        payload = {
            "action": "tool",
            "target_claim_id": "observed",
            "expected_discriminating_finding": "Quellen prüfen.",
            "rationale": "Evidenzarbeit fortsetzen.",
            "tool_name": "list_sources",
            "parameters": "{}",
            "claim_register": first_claims if provider_calls == 1 else "null",
            "brief_payload": first_brief if provider_calls == 1 else "null",
            "source_relevance": "{}",
            "progress_kind": "none",
            "progress_payload": "{}",
            "clarification_reason": "",
            "clarification_payload": "{}",
        }
        raw = json.dumps(payload)
        return OpenRouterResult(
            content=raw,
            model="test-model",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
            output_chars=len(raw),
        )

    monkeypatch.setattr("ki_radar.accelerator.investigation_llm.request_openrouter", provider)
    first = advance_investigation(
        actor=owner, run_id=handle.run_id, executor_token=handle.executor_token
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert first.status == InvestigationRun.Status.RUNNING
    assert run.model_calls.get().status == InvestigationModelCall.Status.SUCCESS
    assert run.claim_register[0]["claim_id"] == "observed"
    assert run.brief_payload == {"draft": "Evidenzgestützter Arbeitsstand"}
    assert list(run.steps.values_list("tool_name", "status")) == [("list_sources", "success")]


@pytest.mark.django_db
@pytest.mark.parametrize("read_first", [False, True])
def test_counterevidence_search_reuses_previously_read_hit(
    owner, business_unit, tmp_path, read_first
):
    process = make_process(owner=owner, business_unit=business_unit, name="Counterevidence order")
    (tmp_path / "evidence.md").write_text(
        "# Beobachtung\nGegenbeleg: alternative Ursache im Prozess.\n", encoding="utf-8"
    )
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, f"counter-order-{read_first}"),
    )
    source = list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources[0]
    if read_first:
        execute_tool_step(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            tool_name="read_source",
            parameters={"source_id": str(source.source_id)},
        )

    action = planner_action(tool_name="search_sources", parameters={"query": "Gegenbeleg"})
    result = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=lambda **_kwargs: action,
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert result.status == InvestigationRun.Status.RUNNING
    assert run.counterevidence_search_executed is True
    assert run.steps.get(tool_name="search_sources").result_payload["hits"]
    assert run.counterevidence_hits_processed is read_first


@pytest.mark.django_db
def test_covered_sources_and_targeted_search_force_synthesis_without_more_tools(
    owner, business_unit, tmp_path
):
    process = make_process(owner=owner, business_unit=business_unit, name="Evidence transition")
    (tmp_path / "case.md").write_text("Freigaben dauern lange.\n", encoding="utf-8")
    (tmp_path / "counter.md").write_text(
        "Fehlende Freigeber verlängern die Freigabe.\n", encoding="utf-8"
    )
    (tmp_path / "cases.csv").write_text("available,hours\nyes,4\nno,28\n", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "evidence-transition"),
    )
    sources = {
        item.filename: item
        for item in list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources
    }
    for filename in ("case.md", "counter.md"):
        execute_tool_step(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            tool_name="read_source",
            parameters={"source_id": str(sources[filename].source_id)},
        )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert investigation_evidence_complete(run) is False

    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="profile_csv",
        parameters={"source_id": str(sources["cases.csv"].source_id)},
    )
    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(sources["cases.csv"].source_id),
            "group_by": "available",
            "aggregation": "mean",
            "value_column": "hours",
        },
    )
    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(sources["cases.csv"].source_id),
            "group_by": "available",
            "aggregation": "count",
        },
    )
    search = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=lambda **_kwargs: planner_action(
            tool_name="search_sources",
            parameters={"query": "Freigeber"},
        ),
    )
    run.refresh_from_db()
    assert search.status == InvestigationRun.Status.RUNNING
    assert run.counterevidence_search_executed is True
    assert run.counterevidence_hits_processed is True
    assert investigation_evidence_complete(run) is True
    context = _planner_context(owner, run)
    assert context["phase"] == "synthesis"
    assert [item["tool_name"] for item in context["recent_steps"]] == [
        "search_sources",
        "compare_groups",
        "compare_groups",
        "profile_csv",
        "read_source",
        "read_source",
    ]

    with pytest.raises(InvestigationRunError) as exc_info:
        advance_investigation(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            planner=lambda **_kwargs: planner_action(
                tool_name="read_source",
                parameters={"source_id": str(sources["case.md"].source_id)},
            ),
        )
    run.refresh_from_db()
    assert exc_info.value.code == "invalid_planner_action"
    assert run.steps.count() == 6


@pytest.mark.django_db
def test_text_only_sources_can_enter_synthesis_without_csv_check(
    owner, business_unit, tmp_path, monkeypatch
):
    process = make_process(owner=owner, business_unit=business_unit, name="Text-only evidence")
    (tmp_path / "notes.md").write_text("Eine Gegenhypothese ist dokumentiert.\n", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "text-only-evidence"),
    )
    source = list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources[0]
    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="read_source",
        parameters={"source_id": str(source.source_id)},
    )
    advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=lambda **_kwargs: planner_action(
            tool_name="search_sources", parameters={"query": "Gegenhypothese"}
        ),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.data_check_executed is False
    assert investigation_evidence_complete(run) is True
    assert "data_check_missing" not in evaluate_run_policy(run).blockers

    def empty_synthesis(**kwargs):
        assert kwargs["response_format"] == {"type": "json_object"}
        raw = json.dumps(
            {
                "action": "synthesize",
                "target_claim_id": "",
                "expected_discriminating_finding": "",
                "rationale": "Zusammenfassen.",
                "tool_name": "",
                "parameters": "{}",
                "claim_register": "null",
                "brief_payload": "null",
                "source_relevance": "{}",
                "progress_kind": "none",
                "progress_payload": "{}",
                "clarification_reason": "",
                "clarification_payload": "{}",
            }
        )
        return OpenRouterResult(
            content=raw,
            model="test-model",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
            output_chars=len(raw),
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter", empty_synthesis
    )
    result = advance_investigation(
        actor=owner, run_id=handle.run_id, executor_token=handle.executor_token
    )
    run.refresh_from_db()
    assert result.status == InvestigationRun.Status.RUNNING
    assert run.model_calls.get().error_code == "invalid_response"
    assert run.claim_register == []
    assert run.brief_payload == {}

    def partial_synthesis(**_kwargs):
        raw = json.dumps(
            {
                "action": "synthesize",
                "target_claim_id": "problem",
                "expected_discriminating_finding": "",
                "rationale": "Unvollständiger Entwurf.",
                "tool_name": "",
                "parameters": "{}",
                "claim_register": json.dumps(
                    [
                        {
                            "claim_id": "problem",
                            "area": "problem_context",
                            "claim_kind": "observation",
                            "status": "open",
                        }
                    ]
                ),
                "brief_payload": json.dumps({"draft": "Unvollständig"}),
                "source_relevance": json.dumps(
                    {
                        str(source.source_id): {
                            "relevant": True,
                            "reason": "Quelle beschreibt die Gegenhypothese.",
                            "reference": {
                                "source_id": str(source.source_id),
                                "locator": {"line": 1},
                                "revision_hash": source.content_sha256,
                            },
                        }
                    }
                ),
                "progress_kind": "none",
                "progress_payload": "{}",
                "clarification_reason": "",
                "clarification_payload": "{}",
            }
        )
        return OpenRouterResult(
            content=raw,
            model="test-model",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
            output_chars=len(raw),
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter", partial_synthesis
    )
    first = advance_investigation(
        actor=owner, run_id=handle.run_id, executor_token=handle.executor_token
    )
    second = advance_investigation(
        actor=owner, run_id=handle.run_id, executor_token=handle.executor_token
    )
    run.refresh_from_db()
    assert first.status == InvestigationRun.Status.RUNNING
    assert second.status == InvestigationRun.Status.WAITING_HUMAN
    assert run.clarification_reason == "technical_failure"
    assert run.clarification_payload["error_code"] == "synthesis_incomplete"
    assert run.usage["model_calls"] == 3
    assert run.usage["verifier_calls"] == 0


@pytest.mark.django_db
def test_synthesizer_can_request_decision_critical_missing_evidence(
    owner, business_unit, tmp_path, monkeypatch
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="synthesis-gap"
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    def provider(**kwargs):
        assert kwargs["response_format"] == {"type": "json_object"}
        raw = json.dumps(
            {
                "claim_register": [],
                "brief_payload": {},
                "source_relevance": {},
                "clarification_reason": "missing_evidence",
                "clarification_payload": {
                    "question": "Wie viele Fälle waren insgesamt freigabeberechtigt?",
                    "decision_impact": "Ohne Nenner ist die Quote nicht belastbar.",
                },
            }
        )
        return OpenRouterResult(
            content=raw,
            model="test-model",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
            output_chars=len(raw),
        )

    monkeypatch.setattr("ki_radar.accelerator.investigation_llm.request_openrouter", provider)
    action = request_synthesis_package(actor=owner, run=run, executor_token=handle.executor_token)

    assert action.action == "clarify"
    assert action.clarification_reason == "missing_evidence"
    assert "freigabeberechtigt" in action.clarification_payload["question"]
    assert run.model_calls.get().role == InvestigationModelCall.Role.SYNTHESIZER
    assert _synthesis_attempts_since_verification(run) == 0
    run.refresh_from_db()
    assert run.claim_register == []
    assert run.brief_payload == {}


def test_empty_relevance_list_is_losslessly_normalized_but_nonempty_list_fails():
    assert (
        _decode_structured_field(
            {"source_relevance": "[]"},
            "source_relevance",
            expected_type=Mapping,
            default={},
        )
        == {}
    )
    with pytest.raises(InvestigationRunError, match="list") as exc_info:
        _decode_structured_field(
            {"source_relevance": '[{"relevant": true}]'},
            "source_relevance",
            expected_type=Mapping,
            default={},
        )
    assert exc_info.value.code == "invalid_response"


@pytest.mark.parametrize("empty_value", [None, "null"])
@pytest.mark.parametrize(
    "field", ["parameters", "source_relevance", "progress_payload", "clarification_payload"]
)
def test_empty_planner_object_fields_accept_json_null(field, empty_value):
    assert (
        _decode_structured_field({field: empty_value}, field, expected_type=Mapping, default={})
        == {}
    )


@pytest.mark.parametrize("field", ["claim_register", "brief_payload"])
@pytest.mark.parametrize("empty_value", [None, "null"])
def test_null_planner_state_still_means_unchanged(field, empty_value):
    assert (
        _decode_structured_field(
            {field: empty_value}, field, expected_type=(list, type(None)), default=None
        )
        is None
    )


@pytest.mark.django_db
def test_null_inactive_planner_fields_do_not_block_tool_or_erase_state(
    owner, business_unit, tmp_path, monkeypatch
):
    process = make_process(owner=owner, business_unit=business_unit, name="Null transport fields")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "null transport fields"),
    )
    claim = {
        "claim_id": "observation",
        "area": "problem_context",
        "claim_kind": "observation",
        "status": "open",
    }
    apply_planner_state(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        claim_register=(claim,),
        brief_payload={"draft": "Bestehender Arbeitsstand"},
    )

    def provider(**_kwargs):
        payload = {
            "action": "tool",
            "target_claim_id": "observation",
            "expected_discriminating_finding": "Quellenmanifest lesen.",
            "rationale": "Vorhandene Evidenz prüfen.",
            "tool_name": "list_sources",
            "parameters": "null",
            "claim_register": "null",
            "brief_payload": None,
            "source_relevance": None,
            "progress_kind": "none",
            "progress_payload": "null",
            "clarification_reason": "",
            "clarification_payload": "null",
        }
        raw = json.dumps(payload)
        return OpenRouterResult(
            content=raw,
            model="test-model",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
            output_chars=len(raw),
        )

    monkeypatch.setattr("ki_radar.accelerator.investigation_llm.request_openrouter", provider)
    result = advance_investigation(
        actor=owner, run_id=handle.run_id, executor_token=handle.executor_token
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    assert result.status == InvestigationRun.Status.RUNNING
    assert run.model_calls.get().status == InvestigationModelCall.Status.SUCCESS
    assert list(run.steps.values_list("tool_name", "status")) == [("list_sources", "success")]
    assert run.claim_register[0]["claim_id"] == "observation"
    assert run.brief_payload == {"draft": "Bestehender Arbeitsstand"}


@pytest.mark.django_db
def test_investigation_actions_ignore_unsolicited_claim_register(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Invalid claim")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "invalid-claim-contract"),
    )
    provider_calls = 0

    def invalid_claim_provider(**_kwargs):
        nonlocal provider_calls
        provider_calls += 1
        payload = {
            "action": "tool",
            "target_claim_id": "claim_register",
            "expected_discriminating_finding": "CSV profilieren.",
            "rationale": "Quantitativen Befund vorbereiten.",
            "tool_name": "list_sources",
            "parameters": "{}",
            "claim_register": json.dumps(
                [
                    {
                        "claim": (
                            "Fehlendes Wissen über Freigaberegeln ist Hauptursache der Verzögerung."
                        ),
                        "status": "hypothesis_unverified",
                    }
                ]
            ),
            "brief_payload": "{}",
            "source_relevance": "{}",
            "progress_kind": "none",
            "progress_payload": "{}",
            "clarification_reason": "",
            "clarification_payload": "{}",
        }
        raw = json.dumps(payload)
        return OpenRouterResult(
            content=raw,
            model="test-model",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
            output_chars=len(raw),
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter",
        invalid_claim_provider,
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
    calls = list(run.model_calls.order_by("created_at"))

    assert first.status == InvestigationRun.Status.RUNNING
    assert second.status == InvestigationRun.Status.WAITING_HUMAN
    assert provider_calls == 2
    assert run.claim_register == []
    assert run.steps.count() == 1
    assert run.clarification_reason == "no_progress"
    assert [(call.status, call.error_code) for call in calls] == [
        (InvestigationModelCall.Status.SUCCESS, ""),
        (InvestigationModelCall.Status.SUCCESS, ""),
    ]
    assert all(call.accepted_payload for call in calls)


@pytest.mark.django_db
def test_claim_register_requires_nonempty_claim_kind(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="claim-kind-required",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    with pytest.raises(InvestigationRunError) as exc_info:
        normalize_claim_register(
            run,
            [
                {
                    "claim_id": "hyp-a",
                    "area": "competing_hypotheses",
                    "status": "open",
                }
            ],
        )

    assert exc_info.value.code == "invalid_claim"


@pytest.mark.django_db
def test_budget_exhaustion_before_work_never_becomes_ready(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Budget")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(
        owner=owner,
        process=process,
        root=tmp_path,
        run_limits={"max_tool_calls": 0},
    )
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "budget"),
    )
    result = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    assert result.status == InvestigationRun.Status.WAITING_HUMAN
    assert run.clarification_reason == "budget_exhausted"
    assert run.status != InvestigationRun.Status.READY
    assert run.model_calls.count() == 0


@pytest.mark.django_db
def test_default_budget_version_covers_benchmark_and_repair_envelope(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="budget-v3",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    limits = run.budget_limits

    assert BUDGET_VERSION == "vs1-budget-v5"
    assert run.execution_snapshot["budget_version"] == "vs1-budget-v5"
    assert limits["max_model_calls"] == 14
    assert limits["max_verifier_calls"] == 4
    assert limits["verifier_reserved_model_calls"] == 4
    assert limits["max_repair_cycles"] == 1

    # Four verifier calls cover two possible two-call verifier rounds:
    # initial verification and the one allowed post-repair verification.
    assert limits["max_verifier_calls"] == 2 * (1 + limits["max_repair_cycles"])

    # The run has its own generous envelope. Four viable verifier responses
    # stay protected without imposing a per-call completion ceiling.
    assert limits["max_output_tokens"] == 131_072
    assert limits["verifier_reserved_output_tokens"] == limits["max_verifier_calls"] * 8_192


@pytest.mark.django_db
def test_verifier_reserve_tracks_only_remaining_verifier_calls(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="dynamic-verifier-reserve",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    usage = dict(run.usage)
    usage["model_calls"] = 10
    usage["verifier_calls"] = 0
    run.usage = usage
    run.save(update_fields=["usage", "updated_at"])

    assert budget_exhausted(run, reserve_verifier=True) is True

    usage["verifier_calls"] = 1
    run.usage = usage
    run.save(update_fields=["usage", "updated_at"])
    run.refresh_from_db()

    assert budget_exhausted(run, reserve_verifier=True) is False

    usage = dict(run.usage)
    usage["model_calls"] = 11
    run.usage = usage
    run.save(update_fields=["usage", "updated_at"])
    run.refresh_from_db()

    assert budget_exhausted(run, reserve_verifier=True) is True


@pytest.mark.django_db
def test_reserved_verifier_budget_becomes_clean_waiting_boundary(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Reserved budget")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(
        owner=owner,
        process=process,
        root=tmp_path,
        run_limits={
            "max_model_calls": 2,
            "max_verifier_calls": 2,
            "verifier_reserved_model_calls": 2,
        },
    )
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "reserved-budget-boundary"),
    )

    result = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    assert result.status == InvestigationRun.Status.WAITING_HUMAN
    assert run.status == InvestigationRun.Status.WAITING_HUMAN
    assert run.clarification_reason == "budget_exhausted"
    assert run.usage["model_calls"] == 0
    assert run.usage["provider_attempts"] == 0


@pytest.mark.django_db
def test_verifier_gets_exactly_one_repair_cycle_then_human_clarification(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="repair",
    )
    claims = ready_claims(source)
    brief = {"recommendation": "Option A", "validation": "Messung fortsetzen"}
    apply_planner_state(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        claim_register=claims,
        brief_payload=brief,
        progress_kind="evidence",
        progress_payload={"coverage_change": True},
    )
    set_source_relevance(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        relevance={
            str(source.source_id): {
                "relevant": True,
                "reason": "CSV trägt die entscheidungsrelevanten Messwerte.",
                "reference": source_ref(source),
            }
        },
    )
    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="profile_csv",
        parameters={"source_id": str(source.source_id)},
        target_claim_id="problem",
    )
    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="search_sources",
        parameters={"query": "counter-never-present", "cursor": 0, "limit": 20},
        target_claim_id="hyp-b",
    )

    def verify_planner(**kwargs):
        run = kwargs["run"]
        brief = dict(run.brief_payload)
        if run.repair_cycles:
            brief["validation"] = "Kritischen Verifier-Befund erneut prüfen"
        return planner_action(
            action="synthesize",
            target_claim_id="verification",
            tool_name="",
            parameters={},
            claim_register=tuple(run.claim_register),
            brief_payload=brief,
        )

    def failing_verifier(**kwargs):
        return create_critical_verifier_report(kwargs["run"])

    first = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=verify_planner,
        verifier=failing_verifier,
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert first.status == InvestigationRun.Status.RUNNING
    assert run.repair_cycles == 1

    second = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=verify_planner,
        verifier=failing_verifier,
    )
    run.refresh_from_db()
    assert second.status == InvestigationRun.Status.WAITING_HUMAN
    assert run.clarification_reason == "verification_failed"
    assert run.verifier_reports.count() == 2
    assert run.repair_cycles == 2


@pytest.mark.django_db(transaction=True)
def test_parallel_materialization_creates_exactly_one_revision(
    owner,
    business_unit,
    tmp_path,
):
    if connection.vendor != "postgresql":
        pytest.skip("Parallel row-lock semantics are validated on PostgreSQL.")

    process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="parallel-materialize",
    )
    payload = {"recommendation": "Option A"}
    InvestigationRun.objects.filter(pk=handle.run_id).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
        brief_payload=payload,
        brief_hash=content_hash(payload),
    )
    barrier = Barrier(2)

    def attempt(actor_id):
        close_old_connections()
        from ki_radar.accounts.models import User

        actor = User.objects.get(pk=actor_id)
        barrier.wait()
        try:
            revision = materialize_brief_revision(
                actor=actor,
                run_id=handle.run_id,
                operation_key="parallel-op",
                expected_process_version=process.version,
            )
            return str(revision.pk)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        revision_ids = list(pool.map(attempt, [owner.pk, owner.pk]))

    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert len(set(revision_ids)) == 1
    assert run.brief_revisions.filter(operation_key="parallel-op").count() == 1


@pytest.mark.django_db
def test_server_rejects_unsafe_tool_and_budget_expansion(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Unsafe Tool")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "unsafe-tool"),
    )

    def unsafe_planner(**_kwargs):
        return planner_action(tool_name="shell", parameters={"command": "echo nope"})

    with pytest.raises(InvestigationRunError) as exc_info:
        advance_investigation(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            planner=unsafe_planner,
        )
    assert exc_info.value.code == "tool_not_allowed"
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.status == InvestigationRun.Status.FAILED
    assert run.finished_at is not None
    assert run.clarification_reason == "technical_failure"
    assert run.clarification_payload["error_code"] == "tool_not_allowed"
    assert run.steps.count() == 0
    assert run.usage["tool_calls"] == 0

    process_2 = make_process(owner=owner, business_unit=business_unit, name="Budget Expansion")
    expanded_root = tmp_path / "expanded"
    expanded_root.mkdir()
    (expanded_root / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder_2, snapshot_2 = snapshot_for_root(
        owner=owner,
        process=process_2,
        root=expanded_root,
        run_limits={"max_tool_calls": 13},
    )
    with pytest.raises(InvestigationRunError) as budget_exc:
        start_investigation(
            actor=owner,
            request=StartInvestigationRequest(snapshot_2.snapshot_id, "expanded-budget"),
        )
    assert budget_exc.value.code == "budget_expansion_forbidden"


def test_planner_schema_allows_only_executable_tools():
    response_format = planner_response_format()
    schema = response_format["json_schema"]["schema"]

    assert PLANNER_SCHEMA_VERSION == "vs1-planner-schema-v12"
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert schema["properties"]["tool_name"]["enum"] == ["", *PLANNER_TOOL_NAMES]
    assert set(schema["properties"]["tool_name"]["enum"]) - {""} == {
        "list_sources",
        "search_sources",
        "read_source",
        "profile_csv",
        "compare_groups",
    }
    assert set(TOOL_PARAMETER_CONTRACTS) == set(PLANNER_TOOL_NAMES)


def _assert_portable_strict_schema(schema):
    forbidden = {"oneOf", "allOf", "if", "then", "else"}

    def visit(node):
        assert not (set(node) & forbidden)
        if node.get("type") == "object":
            properties = node.get("properties", {})
            assert node.get("additionalProperties") is False
            assert set(node.get("required", [])) == set(properties)
            for property_schema in properties.values():
                visit(property_schema)
        if "items" in node:
            visit(node["items"])

    visit(schema)


def test_planner_schema_uses_portable_closed_strict_subset():
    schema = planner_response_format()["json_schema"]["schema"]

    _assert_portable_strict_schema(schema)
    for name in (
        "parameters",
        "clarification_payload",
    ):
        assert schema["properties"][name]["type"] == "string"

    assert "{}" in schema["properties"]["parameters"]["description"]
    assert "claim_register" not in schema["properties"]
    assert "brief_payload" not in schema["properties"]
    assert "source_relevance" not in schema["properties"]


def test_verifier_schema_uses_strict_structured_outputs():
    response_format = verifier_response_format()

    assert VERIFIER_SCHEMA_VERSION == "vs1-verifier-schema-v4"
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    _assert_portable_strict_schema(response_format["json_schema"]["schema"])


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("planner_overrides", "expected_code"),
    [
        ({"action": "invent"}, "invalid_planner_action"),
        ({"progress_kind": "guess"}, "invalid_progress_kind"),
        (
            {"action": "clarify", "clarification_reason": "ask_anything"},
            "invalid_reason_code",
        ),
        (
            {
                "tool_name": "read_source",
                "parameters": {"source_ids": ["6a62ed0a-dc71-4817-80a1-e2571126900d"]},
            },
            "invalid_tool_parameters",
        ),
    ],
)
def test_invalid_planner_contract_is_persisted_as_terminal_technical_failure(
    owner,
    business_unit,
    tmp_path,
    planner_overrides,
    expected_code,
):
    process = make_process(
        owner=owner,
        business_unit=business_unit,
        name=f"Invalid contract {expected_code}",
    )
    source_root = tmp_path / expected_code
    source_root.mkdir()
    (source_root / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(
        owner=owner,
        process=process,
        root=source_root,
    )
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, expected_code),
    )

    with pytest.raises(InvestigationRunError) as exc_info:
        advance_investigation(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            planner=lambda **_kwargs: planner_action(**planner_overrides),
        )

    assert exc_info.value.code == expected_code
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.status == InvestigationRun.Status.FAILED
    assert run.finished_at is not None
    assert run.clarification_reason == "technical_failure"
    assert run.clarification_payload["error_code"] == expected_code
    assert run.steps.count() == 0


@pytest.mark.django_db
def test_direct_invalid_tool_parameters_terminalize_run_without_consuming_tool_budget(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Invalid tool input")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "invalid-tool-input"),
    )

    with pytest.raises(InvestigationRunError) as exc_info:
        execute_tool_step(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            tool_name="read_source",
            parameters={"source_id": ""},
        )

    assert exc_info.value.code == "invalid_tool_parameters"
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.status == InvestigationRun.Status.FAILED
    assert run.finished_at is not None
    assert run.clarification_reason == "technical_failure"
    assert run.clarification_payload["error_code"] == "invalid_tool_parameters"
    assert run.steps.count() == 0
    assert run.usage["tool_calls"] == 0


@pytest.mark.django_db
def test_mocked_model_transport_drives_adaptive_trace_through_verified_ready(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    _process, _snapshot, handle, source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="model-trace",
    )
    claims = ready_claims(source)
    brief = {
        "recommendation": "Verfügbarkeit als Lösungsrichtung weiter validieren.",
        "limits": "Kontrollierter Test, keine Kausalitätsfreigabe.",
        "validation": "Kleinsten nächsten Messschritt durchführen.",
    }
    ref = source_ref(source)
    planner_calls = 0
    saw_compare_result = False
    saw_counter_result = False

    def fake_openrouter(**kwargs):
        nonlocal planner_calls, saw_compare_result, saw_counter_result
        assert kwargs["provider"] == ISSUE4_INVESTIGATION_PROVIDER_POLICY
        system = kwargs["messages"][0]["content"]
        context = json.loads(kwargs["messages"][1]["content"])

        if "frischer unabhängiger Verifier" in system:
            assert context["analysis_replays"]
            assert all(item["matches"] for item in context["analysis_replays"])
            payload = {
                "read_requests": [],
                "findings": [],
                "source_references_valid": True,
                "checked_critical_claims": critical_ids(claims),
            }
        else:
            planner_calls += 1
            recent = context["recent_steps"]
            if planner_calls == 1:
                assert not recent
                payload = {
                    "action": "tool",
                    "target_claim_id": "manifest",
                    "expected_discriminating_finding": "Freigegebene Quelle identifizieren.",
                    "rationale": "Zuerst den begrenzten Quellenraum erfassen.",
                    "tool_name": "list_sources",
                    "parameters": {},
                    "claim_register": [],
                    "brief_payload": {},
                    "source_relevance": {},
                    "progress_kind": "none",
                    "progress_payload": {},
                    "clarification_reason": "",
                    "clarification_payload": {},
                }
            elif planner_calls == 2:
                assert recent[0]["tool_name"] == "list_sources"
                payload = {
                    "action": "tool",
                    "target_claim_id": "data-shape",
                    "expected_discriminating_finding": "Messspalten und Datenqualität prüfen.",
                    "rationale": "Die gefundene CSV vor dem Vergleich profilieren.",
                    "tool_name": "profile_csv",
                    "parameters": {"source_id": str(source.source_id)},
                    "claim_register": [],
                    "brief_payload": {},
                    "source_relevance": {},
                    "progress_kind": "none",
                    "progress_payload": {},
                    "clarification_reason": "",
                    "clarification_payload": {},
                }
            elif planner_calls == 3:
                assert recent[0]["tool_name"] == "profile_csv"
                payload = {
                    "action": "tool",
                    "target_claim_id": "hyp-availability",
                    "expected_discriminating_finding": "Gruppenunterschied quantifizieren.",
                    "rationale": "Profil erlaubt den unterscheidenden Vergleich.",
                    "tool_name": "compare_groups",
                    "parameters": {
                        "source_id": str(source.source_id),
                        "group_by": "available",
                        "aggregation": "mean",
                        "value_column": "value",
                        "filters": [],
                        "unit_column": "unit",
                    },
                    "claim_register": [],
                    "brief_payload": {},
                    "source_relevance": {},
                    "progress_kind": "none",
                    "progress_payload": {},
                    "clarification_reason": "",
                    "clarification_payload": {},
                }
            elif planner_calls == 4:
                assert recent[0]["tool_name"] == "compare_groups"
                assert recent[0]["result_payload"]["differences"]
                saw_compare_result = True
                payload = {
                    "action": "tool",
                    "target_claim_id": "counter-hyp-availability",
                    "expected_discriminating_finding": "Gegenbeleg im Quellenraum suchen.",
                    "rationale": "Nach positivem Unterschied gezielt Gegenbelege prüfen.",
                    "tool_name": "search_sources",
                    "parameters": {
                        "query": "counter-never-present",
                        "cursor": 0,
                        "limit": 20,
                    },
                    "claim_register": [],
                    "brief_payload": {},
                    "source_relevance": {},
                    "progress_kind": "none",
                    "progress_payload": {},
                    "clarification_reason": "",
                    "clarification_payload": {},
                }
            else:
                assert recent[0]["tool_name"] == "search_sources"
                assert recent[0]["result_payload"]["total_matches"] == 0
                assert context["phase"] == "synthesis"
                assert kwargs["response_format"] == {"type": "json_object"}
                saw_counter_result = True
                payload = {
                    "action": "synthesize",
                    "target_claim_id": "verification",
                    "expected_discriminating_finding": "READY-Vertrag unabhängig prüfen.",
                    "rationale": "Pflichtprüfungen sind strukturell belegt.",
                    "tool_name": "",
                    "parameters": {},
                    "claim_register": list(claims),
                    "brief_payload": brief,
                    "source_relevance": {
                        str(source.source_id): {
                            "relevant": True,
                            "reason": "CSV enthält die untersuchten Messwerte.",
                            "reference": ref,
                        }
                    },
                    "progress_kind": "evidence",
                    "progress_payload": {"coverage_change": True},
                    "clarification_reason": "",
                    "clarification_payload": {},
                }

        raw = json.dumps(payload)
        return OpenRouterResult(
            content=raw,
            model="test-model",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
            output_chars=len(raw),
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter",
        fake_openrouter,
    )
    result = run_until_boundary(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    assert result.status == InvestigationRun.Status.READY
    assert saw_compare_result is True
    assert saw_counter_result is True
    assert planner_calls == 5
    assert run.verifier_reports.count() == 1
    assert run.verifier_reports.get().success is True
    assert run.status == InvestigationRun.Status.READY
    assert run.usage["tool_calls"] == 4
    assert run.usage["model_calls"] == 6
    calls = list(run.model_calls.order_by("created_at"))
    assert all(call.effective_parameters["max_tokens"] > 4096 for call in calls)
    assert all(call.effective_parameters["timeout_seconds"] > 60 for call in calls)
    assert all(call.effective_parameters["reasoning_effort"] == "medium" for call in calls)


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["planner", "verifier"])
@pytest.mark.parametrize("partial", [False, True])
def test_truncated_structured_response_is_accounted_and_never_retried(
    owner, business_unit, tmp_path, monkeypatch, role, partial
):
    process = make_process(owner=owner, business_unit=business_unit, name=f"Truncated {role}")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, f"truncated-{role}-{partial}"),
    )
    provider_calls = 0

    def truncated_provider(**_kwargs):
        nonlocal provider_calls
        provider_calls += 1
        if not partial:
            raise OpenRouterUnavailable(
                "Completion limit",
                code="output_truncated",
                diagnostics={
                    "finish_reason": "length",
                    "usage_prompt_tokens": 20,
                    "usage_completion_tokens": 8192,
                    "returned_model": "test-model",
                },
            )
        return OpenRouterResult(
            content='{"action":"verify"}',
            model="test-model",
            usage={"prompt_tokens": 20, "completion_tokens": 8192},
            output_chars=19,
            finish_reason="length",
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter", truncated_provider
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    if role == "planner":
        result = advance_investigation(
            actor=owner, run_id=run.pk, executor_token=handle.executor_token
        )
        assert result.status == InvestigationRun.Status.WAITING_HUMAN
        run.refresh_from_db()
        assert run.clarification_payload["error_code"] == "output_truncated"
        assert run.clarification_payload["attempts"] == 1
    else:
        with pytest.raises(InvestigationRunError, match="Completion") as exc_info:
            request_verifier_report(actor=owner, run=run, executor_token=handle.executor_token)
        assert exc_info.value.code == "output_truncated"
    call = run.model_calls.get()
    assert provider_calls == 1
    assert "output_truncated" not in TRANSIENT_PROVIDER_CODES
    assert call.status == InvestigationModelCall.Status.FAILED
    assert call.error_code == "output_truncated"
    assert call.accepted_payload == {}
    assert call.prompt_tokens == 20
    assert call.completion_tokens == 8192
    assert call.effective_parameters["response_diagnostics"]["finish_reason"] == "length"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "capacity_kind", "expected_code"),
    [
        ("planner", "completion", "completion_budget_exhausted"),
        ("verifier", "completion", "completion_budget_exhausted"),
        ("planner", "timeout", "runtime_capacity_exhausted"),
        ("verifier", "timeout", "runtime_capacity_exhausted"),
    ],
)
def test_completion_and_timeout_floors_prevent_provider_attempt(
    owner, business_unit, tmp_path, role, capacity_kind, expected_code
):
    process = make_process(owner=owner, business_unit=business_unit, name=f"Floor {role}")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, f"floor-{role}-{expected_code}"),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    if capacity_kind == "completion":
        protected = 32_768 if role == "planner" else 0
        usage = dict(run.usage)
        usage["output_tokens"] = run.budget_limits["max_output_tokens"] - protected - 8_191
        run.usage = usage
        run.save(update_fields=["usage", "updated_at"])
    else:
        protected = 1_200 if role == "planner" else 0
        floor = 60 if role == "planner" else 75
        elapsed = run.budget_limits["max_runtime_seconds"] - protected - floor + 1
        InvestigationRun.objects.filter(pk=run.pk).update(
            started_at=timezone.now() - timedelta(seconds=elapsed)
        )
    with pytest.raises(InvestigationRunError) as exc_info:
        _reserve_model_call(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            role=role,
            instruction="Structured investigation",
            prompt_version="floor-test",
            schema_version="floor-test",
            context={},
        )
    assert exc_info.value.code == expected_code
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.model_calls.count() == 0
    assert run.usage["provider_attempts"] == 0


@pytest.mark.django_db
def test_later_planner_gets_time_without_consuming_verifier_reserve(owner, business_unit, tmp_path):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="runtime-share"
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    usage = dict(run.usage)
    usage["model_calls"] = 5
    usage["provider_attempts"] = 5
    run.usage = usage
    run.save(update_fields=["usage", "updated_at"])
    InvestigationRun.objects.filter(pk=run.pk).update(
        started_at=timezone.now() - timedelta(seconds=690)
    )

    call = _reserve_model_call(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        role=InvestigationModelCall.Role.PLANNER,
        instruction="Structured investigation",
        prompt_version="runtime-share-test",
        schema_version="runtime-share-test",
        context={},
    )
    assert run.budget_limits["max_runtime_seconds"] == 4_200
    assert run.budget_limits["verifier_reserved_seconds"] == 1_200
    # The planner shares the remaining runtime with the calls that stay possible
    # after the derived reserves: four verifier calls (1_200 s) and the synthesis
    # share (1 + max_repair_cycles = two of fourteen calls, so 600 s).
    assert 567 <= call.effective_parameters["timeout_seconds"] <= 571


@pytest.mark.django_db
def test_two_synthesis_calls_remain_after_investigation_budget(owner, business_unit, tmp_path):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="synthesis-reserve"
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    usage = dict(run.usage)
    usage["model_calls"] = 8
    run.usage = usage

    assert budget_exhausted(run, reserve_verifier=True, reserve_synthesis=True)
    assert not budget_exhausted(run, reserve_verifier=True)

    usage["model_calls"] = 9
    run.usage = usage
    assert not budget_exhausted(run, reserve_verifier=True)


@pytest.mark.django_db
def test_verifier_receives_its_reserved_time_share(owner, business_unit, tmp_path):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="verifier-time-share"
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    InvestigationRun.objects.filter(pk=run.pk).update(
        started_at=timezone.now() - timedelta(seconds=3_000)
    )

    call = _reserve_model_call(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        role=InvestigationModelCall.Role.VERIFIER,
        instruction="Verify the structured investigation",
        prompt_version="verifier-time-test",
        schema_version="verifier-time-test",
        context={},
    )
    assert 300 <= call.effective_parameters["timeout_seconds"] <= 302


@pytest.mark.django_db
def test_structured_planner_request_sends_productive_reasoning_parameters(
    owner, business_unit, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(settings, "OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash", raising=False)
    monkeypatch.setattr(settings, "OPENROUTER_REASONING_EXCLUDE", True, raising=False)
    process = make_process(owner=owner, business_unit=business_unit, name="Reasoning transport")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "reasoning-transport"),
    )
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return json.dumps(
                {
                    "model": "deepseek/deepseek-v4.1-flash",
                    "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 2},
                }
            ).encode()

    def fake_urlopen(request, **_kwargs):
        captured["body"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr("ki_radar.core.openrouter.urllib.request.urlopen", fake_urlopen)
    _structured_provider_call(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        role=InvestigationModelCall.Role.PLANNER,
        instruction="Produce a structured decision",
        prompt_version="reasoning-test",
        schema_version="reasoning-test",
        context={},
        response_format=planner_response_format(),
    )
    assert captured["body"]["reasoning"] == {"effort": "medium", "exclude": True}
    assert captured["body"]["max_tokens"] > 4096


@pytest.mark.django_db
def test_frozen_endpoint_capability_cannot_change_after_run_start(owner, business_unit, tmp_path):
    process = make_process(owner=owner, business_unit=business_unit, name="Frozen capability")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "frozen-capability"),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    frozen = dict(run.execution_snapshot)
    transport = dict(frozen["model_transport"])
    capability = dict(transport["endpoint_capability"])
    capability["completion_tokens"] -= 1
    transport["endpoint_capability"] = capability
    frozen["model_transport"] = transport
    InvestigationRun.objects.filter(pk=run.pk).update(execution_snapshot=frozen)

    with pytest.raises(InvestigationRunError) as exc_info:
        _reserve_model_call(
            actor=owner,
            run_id=run.pk,
            executor_token=handle.executor_token,
            role=InvestigationModelCall.Role.PLANNER,
            instruction="Produce a structured decision",
            prompt_version="frozen-test",
            schema_version="frozen-test",
            context={},
        )
    assert exc_info.value.code == "execution_version_unavailable"
    assert run.model_calls.count() == 0


@pytest.mark.django_db
def test_frozen_tool_parameter_contract_cannot_change_after_run_start(
    owner, business_unit, tmp_path
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="frozen-tool-contract"
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.execution_snapshot["tools"]["schema_version"] == "vs1-tool-schema-v2"
    assert run.execution_snapshot["tools"]["parameter_contracts"] == TOOL_PARAMETER_CONTRACTS
    frozen = json.loads(json.dumps(run.execution_snapshot))
    frozen["tools"]["parameter_contracts"]["compare_groups"]["required"] = ["source_id"]
    InvestigationRun.objects.filter(pk=run.pk).update(execution_snapshot=frozen)

    with pytest.raises(InvestigationRunError) as exc_info:
        _reserve_model_call(
            actor=owner,
            run_id=run.pk,
            executor_token=handle.executor_token,
            role=InvestigationModelCall.Role.PLANNER,
            instruction="Structured investigation",
            prompt_version="frozen-tool-test",
            schema_version="frozen-tool-test",
            context={},
        )
    assert exc_info.value.code == "execution_version_unavailable"
    assert run.model_calls.count() == 0

    old_snapshot = json.loads(json.dumps(run.execution_snapshot))
    del old_snapshot["tools"]["parameter_contracts"]
    InvestigationRun.objects.filter(pk=run.pk).update(execution_snapshot=old_snapshot)
    run.refresh_from_db()
    with pytest.raises(InvestigationRunError) as old_exc:
        request_planner_action(actor=owner, run=run, executor_token=handle.executor_token)
    assert old_exc.value.code == "execution_version_unavailable"
    assert run.model_calls.count() == 0
