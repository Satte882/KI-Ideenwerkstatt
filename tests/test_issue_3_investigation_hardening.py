from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from ki_radar.accelerator.investigation_llm import (
    PlannerAction,
    request_verifier_report,
)
from ki_radar.accelerator.investigation_loop import (
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
from ki_radar.accelerator.investigation_runtime import (
    InvestigationRunError,
    StartInvestigationRequest,
    apply_planner_state,
    content_hash,
    execute_tool_step,
    materialize_brief_revision,
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
        return planner_action(
            action="verify",
            target_claim_id="verification",
            tool_name="",
            parameters={},
            claim_register=tuple(run.claim_register),
            brief_payload=run.brief_payload,
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
                saw_counter_result = True
                payload = {
                    "action": "verify",
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
