from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from django.core.exceptions import PermissionDenied
from django.db import close_old_connections, connection
from django.db.models import F
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator.investigation_llm import PlannerAction, request_planner_action
from ki_radar.accelerator.investigation_loop import advance_investigation
from ki_radar.accelerator.investigation_models import (
    InvestigationRun,
    InvestigationSourceFolder,
    InvestigationStep,
)
from ki_radar.accelerator.investigation_runtime import (
    InvestigationRunError,
    StartInvestigationRequest,
    abort_investigation,
    continue_with_human_input,
    execute_tool_step,
    mark_counterevidence_processed,
    materialize_brief_revision,
    recover_investigation,
    set_source_relevance,
    start_investigation,
)
from ki_radar.accelerator.investigation_tools import (
    SnapshotRequest,
    create_source_snapshot,
    list_sources,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage
from ki_radar.core.openrouter import OpenRouterResult


def make_process(*, owner, business_unit, name="VS1/2 Fall"):
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
            decision_question="Welche Lösungsrichtung ist durch die Evidenz gestützt?",
            run_limits=run_limits or {},
        ),
    )
    return folder, snapshot


def empty_action(**overrides):
    values = {
        "action": "tool",
        "target_claim_id": "problem",
        "expected_discriminating_finding": "Beleg prüfen",
        "rationale": "Nächster begrenzter Prüfschritt.",
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


@pytest.mark.django_db
def test_start_is_idempotent_and_active_run_blocks_second_start(
    owner,
    coordinator,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)

    first = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "same-key"),
    )
    retry = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "same-key"),
    )
    assert retry.reused is True
    assert retry.run_id == first.run_id

    with pytest.raises(InvestigationRunError) as exc_info:
        start_investigation(
            actor=coordinator,
            request=StartInvestigationRequest(snapshot.snapshot_id, "other-key"),
        )
    assert exc_info.value.code == "active_run_exists"
    assert exc_info.value.existing_run_id == first.run_id


@pytest.mark.django_db(transaction=True)
def test_parallel_starts_create_exactly_one_active_run(
    owner,
    coordinator,
    business_unit,
    tmp_path,
):
    if connection.vendor != "postgresql":
        pytest.skip("Parallel row-lock semantics are validated on PostgreSQL.")

    process = make_process(owner=owner, business_unit=business_unit, name="Parallel")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    barrier = Barrier(2)

    def attempt(actor_id, key):
        close_old_connections()
        from ki_radar.accounts.models import User

        actor = User.objects.get(pk=actor_id)
        barrier.wait()
        try:
            handle = start_investigation(
                actor=actor,
                request=StartInvestigationRequest(snapshot.snapshot_id, key),
            )
            return ("created", str(handle.run_id))
        except InvestigationRunError as exc:
            return (exc.code, str(exc.existing_run_id or ""))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda item: attempt(*item),
                [(owner.pk, "p1"), (coordinator.pk, "p2")],
            )
        )

    assert sum(result[0] == "created" for result in results) == 1
    assert sum(result[0] == "active_run_exists" for result in results) == 1
    assert (
        InvestigationRun.objects.filter(
            process_analysis=process,
            status__in=InvestigationRun.ACTIVE_STATUSES,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_waiting_human_blocks_new_start_and_abort_allows_successor(
    owner,
    coordinator,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "wait-key"),
    )

    def clarify(**_kwargs):
        return empty_action(
            action="clarify",
            clarification_reason="missing_evidence",
            clarification_payload={
                "claim_id": "external-volume",
                "attempts": ["source room searched"],
                "impact": "Kritische Bezugsgröße fehlt.",
                "required_input": "Bezugsgröße oder explizite Scope-Freigabe.",
            },
        )

    result = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=clarify,
    )
    assert result.status == InvestigationRun.Status.WAITING_HUMAN

    with pytest.raises(InvestigationRunError) as exc_info:
        start_investigation(
            actor=coordinator,
            request=StartInvestigationRequest(snapshot.snapshot_id, "blocked"),
        )
    assert exc_info.value.code == "active_run_exists"

    abort_investigation(actor=owner, run_id=handle.run_id)
    successor = start_investigation(
        actor=coordinator,
        request=StartInvestigationRequest(snapshot.snapshot_id, "successor"),
    )
    assert successor.run_id != handle.run_id


@pytest.mark.django_db
def test_human_input_continues_same_run_and_invalidates_executor_and_verifier_basis(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "human"),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    old_hash = run.register_hash
    InvestigationRun.objects.filter(pk=run.pk).update(
        status=InvestigationRun.Status.WAITING_HUMAN,
        clarification_reason="missing_evidence",
    )

    resumed = continue_with_human_input(
        actor=owner,
        run_id=run.pk,
        payload={"external_volume": "unknown"},
    )
    run.refresh_from_db()
    assert resumed.run_id == handle.run_id
    assert resumed.executor_token != handle.executor_token
    assert run.register_hash != old_hash
    assert run.input_revisions.count() == 1


@pytest.mark.django_db
def test_recovery_preserves_budget_and_late_old_executor_result_is_discarded(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "recovery"),
    )
    holder = {}

    def delayed_result(_actor, run, _tool_name, _params):
        holder["new"] = recover_investigation(actor=owner, run_id=run.pk)
        return {"ok": True}

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_runtime.run_tool",
        delayed_result,
    )
    with pytest.raises(InvestigationRunError) as exc_info:
        execute_tool_step(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            tool_name="list_sources",
            parameters={},
        )
    assert exc_info.value.code == "stale_executor"

    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.usage["tool_calls"] == 1
    assert InvestigationStep.objects.get(run=run).status == InvestigationStep.Status.DISCARDED

    with pytest.raises(InvestigationRunError) as old_exc:
        execute_tool_step(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            tool_name="list_sources",
            parameters={},
        )
    assert old_exc.value.code == "stale_executor"
    assert holder["new"].executor_generation == handle.executor_generation + 1


@pytest.mark.django_db
def test_process_version_conflict_and_permission_revocation_fail_closed(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "version"),
    )

    ProcessAnalysis.objects.filter(pk=process.pk).update(version=F("version") + 1)
    with pytest.raises(InvestigationRunError) as exc_info:
        execute_tool_step(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            tool_name="list_sources",
            parameters={},
        )
    assert exc_info.value.code == "process_version_conflict"

    ProcessAnalysis.objects.filter(pk=process.pk).update(version=process.version)
    folder.is_active = False
    folder.save(update_fields=["is_active", "updated_at"])
    with pytest.raises(PermissionDenied):
        execute_tool_step(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            tool_name="list_sources",
            parameters={},
        )


@pytest.mark.django_db
def test_identical_successful_tool_step_is_reused_without_budget_charge(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "dedupe"),
    )
    first = execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="list_sources",
        parameters={},
        target_claim_id="manifest",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    usage_after_first = dict(run.usage)

    second = execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="list_sources",
        parameters={},
        target_claim_id="manifest",
    )
    run.refresh_from_db()
    assert second.pk == first.pk
    assert run.usage == usage_after_first


@pytest.mark.django_db
def test_repeated_no_progress_tool_loop_fails_without_human_delegation(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "no-progress"),
    )

    def same_step(**_kwargs):
        return empty_action(target_claim_id="same-target")

    first = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=same_step,
    )
    assert first.status == InvestigationRun.Status.RUNNING

    second = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=same_step,
    )
    third = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=same_step,
    )
    fourth = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=same_step,
    )
    fifth = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=same_step,
    )
    assert second.status == third.status == fourth.status == InvestigationRun.Status.RUNNING
    assert fifth.status == InvestigationRun.Status.FAILED
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.clarification_reason == "technical_failure"
    assert run.clarification_payload["error_code"] == "no_progress_loop"
    assert run.clarification_payload["repeat_count"] == 4
    assert run.usage["tool_calls"] == 1


@pytest.mark.django_db
def test_counterevidence_hits_must_be_read_before_processed(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text(
        "Hypothese A\nGegenbeleg: fehlende Info erklärt Fall nicht\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "counter"),
    )
    source = list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources[0]

    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="search_sources",
        parameters={"query": "Gegenbeleg", "limit": 20, "cursor": 0},
        target_claim_id="hyp-a",
    )
    with pytest.raises(InvestigationRunError) as exc_info:
        mark_counterevidence_processed(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
        )
    assert exc_info.value.code == "counterevidence_unread"

    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="read_source",
        parameters={
            "source_id": str(source.source_id),
            "cursor": 0,
            "limit": 10,
            "columns": [],
        },
        target_claim_id="hyp-a-read",
    )
    mark_counterevidence_processed(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.counterevidence_hits_processed is True


@pytest.mark.django_db
def test_source_relevance_requires_full_classification_and_real_access_for_relevant_sources(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Relevanter Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "relevance"),
    )
    source = list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources[0]

    with pytest.raises(InvestigationRunError) as missing:
        set_source_relevance(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            relevance={},
        )
    assert missing.value.code == "source_relevance_incomplete"

    with pytest.raises(InvestigationRunError) as unread:
        set_source_relevance(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            relevance={str(source.source_id): {"relevant": True}},
        )
    assert unread.value.code == "source_relevance_unobserved"

    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="read_source",
        parameters={"source_id": str(source.source_id)},
        target_claim_id="source-coverage",
    )
    run = set_source_relevance(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        relevance={str(source.source_id): {"relevant": True}},
    )
    assert run.source_relevance_complete is True
    assert run.source_relevance == {str(source.source_id): {"relevant": True}}


@pytest.mark.django_db
def test_materialization_is_idempotent_and_version_protected(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "materialize"),
    )
    InvestigationRun.objects.filter(pk=handle.run_id).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
        brief_payload={"recommendation": "Option A prüfen"},
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    first = materialize_brief_revision(
        actor=owner,
        run_id=run.pk,
        operation_key="brief-op",
        expected_process_version=process.version,
    )
    second = materialize_brief_revision(
        actor=owner,
        run_id=run.pk,
        operation_key="brief-op",
        expected_process_version=process.version,
    )
    assert first.pk == second.pk
    assert run.brief_revisions.count() == 1

    ProcessAnalysis.objects.filter(pk=process.pk).update(version=F("version") + 1)
    with pytest.raises(InvestigationRunError) as exc_info:
        materialize_brief_revision(
            actor=owner,
            run_id=run.pk,
            operation_key="new-op",
            expected_process_version=process.version,
        )
    assert exc_info.value.code == "process_version_conflict"


@pytest.mark.django_db
def test_resume_does_not_silently_switch_model_alias(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")

    with override_settings(OPENROUTER_MODEL="fixed-model"):
        _folder, snapshot = snapshot_for_root(
            owner=owner,
            process=process,
            root=tmp_path,
        )
        handle = start_investigation(
            actor=owner,
            request=StartInvestigationRequest(snapshot.snapshot_id, "fixed-model"),
        )

    run = InvestigationRun.objects.get(pk=handle.run_id)
    with (
        override_settings(OPENROUTER_MODEL="changed-model"),
        pytest.raises(InvestigationRunError) as exc_info,
    ):
        request_planner_action(
            actor=owner,
            run=run,
            executor_token=handle.executor_token,
        )
    assert exc_info.value.code == "execution_version_unavailable"
    assert run.model_calls.count() == 0


@pytest.mark.django_db
def test_planner_decodes_closed_schema_json_fields_without_changing_action_semantics(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "closed-schema"),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    payload = {
        "action": "tool",
        "target_claim_id": "manifest",
        "expected_discriminating_finding": "Quelle erfassen.",
        "rationale": "Der Quellenraum wird zuerst gelesen.",
        "tool_name": "list_sources",
        "parameters": "{}",
        "claim_register": "[]",
        "brief_payload": "{}",
        "source_relevance": "{}",
        "progress_kind": "none",
        "progress_payload": '{"coverage_change": false}',
        "clarification_reason": "",
        "clarification_payload": "{}",
    }

    def fake_provider(**kwargs):
        schema = kwargs["response_format"]["json_schema"]["schema"]
        assert schema["additionalProperties"] is False
        assert schema["properties"]["parameters"]["type"] == "string"
        content = json.dumps(payload)
        return OpenRouterResult(
            content=content,
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            output_chars=len(content),
        )

    monkeypatch.setattr("ki_radar.accelerator.investigation_llm.request_openrouter", fake_provider)

    action = request_planner_action(
        actor=owner,
        run=run,
        executor_token=handle.executor_token,
    )

    assert action.parameters == {}
    assert action.claim_register is None
    assert action.brief_payload is None
    assert action.source_relevance == {}
    assert action.progress_payload == {}
