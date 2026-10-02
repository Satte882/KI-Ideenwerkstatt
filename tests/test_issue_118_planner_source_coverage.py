from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.core.exceptions import PermissionDenied

from ki_radar.accelerator import investigation_llm
from ki_radar.accelerator.investigation_llm import (
    _investigation_context,
    _source_read_coverage,
    _synthesis_context,
    request_planner_action,
)
from ki_radar.accelerator.investigation_models import InvestigationRun, InvestigationStep
from ki_radar.accelerator.investigation_runtime import (
    DEFAULT_BUDGET,
    InvestigationRunError,
    StartInvestigationRequest,
    content_hash,
    execute_tool_step,
    recover_investigation,
    start_investigation,
)
from tests.test_issue_3_investigation_runtime import make_process, snapshot_for_root

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def forbid_provider_calls(monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("#118 deterministic tests must never call a real provider")

    monkeypatch.setattr(investigation_llm, "request_openrouter", forbidden)


def start_run(owner, business_unit, root):
    process = make_process(owner=owner, business_unit=business_unit)
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=root)
    handle = start_investigation(
        actor=owner, request=StartInvestigationRequest(snapshot.snapshot_id, "coverage")
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    sources = {source.filename: source for source in run.source_snapshot.sources.all()}
    return run, handle, sources


@pytest.fixture
def coverage_run(owner, business_unit, tmp_path):
    (tmp_path / "a.txt").write_text("\n".join(f"Line {i}" for i in range(250)), encoding="utf-8")
    (tmp_path / "b.txt").write_text("Other source", encoding="utf-8")
    (tmp_path / "data.csv").write_text(
        "id,value\n" + "\n".join(f"{i},{i * 2}" for i in range(250)), encoding="utf-8"
    )
    return start_run(owner, business_unit, tmp_path)


def read(owner, run, handle, source, *, cursor=0, limit=100, columns=None, verifier_read=False):
    return execute_tool_step(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        tool_name="read_source",
        parameters={
            "source_id": str(source.pk),
            "cursor": cursor,
            "limit": limit,
            "columns": columns or [],
        },
        verifier_read=verifier_read,
    )


@pytest.mark.parametrize(
    ("case_id", "early_filename"),
    [
        pytest.param("AP4-02", "01_policy.md", id="AP4-02-R4-state-pattern"),
        pytest.param("AP4-04", "01_invoice_process.md", id="AP4-04-R5-state-pattern"),
    ],
)
def test_historical_early_read_survives_six_later_steps(
    owner, business_unit, case_id, early_filename, monkeypatch
):
    # Real frozen source packs; structural replay, not a claim about model behavior.
    root = Path(__file__).parent / "fixtures" / "ap4_source_packs" / case_id
    run, handle, sources = start_run(owner, business_unit, root)
    early = read(owner, run, handle, sources[early_filename])
    csv = next(source for source in sources.values() if source.source_type == "csv")
    read(owner, run, handle, csv)
    execute_tool_step(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        tool_name="profile_csv",
        parameters={"source_id": str(csv.pk)},
    )
    for query in ("Freigabe", "Ausnahme", "Prüfung", "Beleg"):
        execute_tool_step(
            actor=owner,
            run_id=run.pk,
            executor_token=handle.executor_token,
            tool_name="search_sources",
            parameters={"query": query},
        )
    run.refresh_from_db()
    assert run.steps.filter(status=InvestigationStep.Status.SUCCESS).count() == 7
    context = _investigation_context(owner, run)
    assert len(context["recent_steps"]) == 5
    assert early.sequence not in [step["sequence"] for step in context["recent_steps"]]
    entry = context["source_read_coverage"][0]
    assert entry["sequence"] == early.sequence
    assert entry["source_id"] == str(sources[early_filename].pk)
    assert entry["returned_count"] == len(early.result_payload["items"])
    assert entry["result_hash"] == early.result_hash

    # Verify that request_planner_action actually passes this projection to transport.
    def capture(**kwargs):
        assert kwargs["context"] == context
        return {"action": "clarify", "clarification_reason": "missing_evidence"}, None

    monkeypatch.setattr(investigation_llm, "_structured_provider_call", capture)
    assert (
        request_planner_action(actor=owner, run=run, executor_token=handle.executor_token).action
        == "clarify"
    )
    assert run.model_calls.count() == 0
    assert "source_read_coverage" not in _synthesis_context(owner, run)


def test_partial_read_records_actual_interval_not_full_source(owner, coverage_run):
    run, handle, sources = coverage_run
    read(owner, run, handle, sources["a.txt"], cursor=0, limit=100)
    entry = _source_read_coverage(run)[0]
    assert (entry["cursor"], entry["limit"], entry["returned_count"]) == (0, 100, 100)
    assert entry["end_cursor_exclusive"] == entry["next_cursor"] == 100
    assert "fully_read" not in entry
    assert entry["snapshot_id"] == str(run.source_snapshot_id)
    assert entry["revision_hash"] == sources["a.txt"].content_sha256


def test_pagination_and_distinct_column_reads_stay_separate(owner, coverage_run):
    run, handle, sources = coverage_run
    source = sources["data.csv"]
    for cursor in (0, 100, 200):
        read(owner, run, handle, source, cursor=cursor, columns=["id"])
    read(owner, run, handle, source, cursor=200, columns=["value"])
    read(owner, run, handle, source, cursor=200)
    entries = _source_read_coverage(run)
    assert [(item["cursor"], item["end_cursor_exclusive"]) for item in entries] == [
        (0, 100),
        (100, 200),
        (200, 250),
        (200, 250),
        (200, 250),
    ]
    assert [item["next_cursor"] for item in entries] == [100, 200, None, None, None]
    assert [item["columns"] for item in entries] == [["id"], ["id"], ["id"], ["value"], []]
    assert all(item["source_id"] == str(source.pk) for item in entries)
    assert all("fully_read" not in item for item in entries)


def test_terminal_suffix_and_empty_read_do_not_claim_prefix_coverage(owner, coverage_run):
    run, handle, sources = coverage_run
    read(owner, run, handle, sources["a.txt"], cursor=200)
    read(owner, run, handle, sources["a.txt"], cursor=300)
    suffix, empty = _source_read_coverage(run)
    assert (suffix["cursor"], suffix["end_cursor_exclusive"], suffix["next_cursor"]) == (
        200,
        250,
        None,
    )
    assert (empty["cursor"], empty["end_cursor_exclusive"], empty["returned_count"]) == (
        300,
        300,
        0,
    )


def test_byte_shortened_page_uses_stored_count(owner, coverage_run, monkeypatch):
    run, handle, sources = coverage_run
    monkeypatch.setattr("ki_radar.accelerator.investigation_tools.MAX_READ_BYTES", 80)
    step = read(owner, run, handle, sources["a.txt"], limit=100)
    entry = _source_read_coverage(run)[0]
    assert 0 < entry["returned_count"] < entry["limit"]
    assert entry["returned_count"] == len(step.result_payload["items"])
    assert entry["end_cursor_exclusive"] == entry["next_cursor"] == entry["returned_count"]


def test_coverage_never_transfers_between_sources(owner, coverage_run):
    run, handle, sources = coverage_run
    read(owner, run, handle, sources["a.txt"])
    context = _investigation_context(owner, run)
    assert {entry["source_id"] for entry in context["source_read_coverage"]} == {
        str(sources["a.txt"].pk)
    }
    assert str(sources["b.txt"].pk) in {item["source_id"] for item in context["sources"]}


@pytest.mark.parametrize("status", ["failed", "discarded", "running"])
def test_non_successful_read_never_counts_even_with_retained_result(owner, coverage_run, status):
    run, handle, sources = coverage_run
    step = read(owner, run, handle, sources["a.txt"])
    InvestigationStep.objects.filter(pk=step.pk).update(status=status)
    assert _source_read_coverage(run) == []


@pytest.mark.parametrize("field", ["snapshot_id", "source_id"])
def test_mismatched_stored_result_binding_is_not_projected(owner, coverage_run, field):
    run, handle, sources = coverage_run
    step = read(owner, run, handle, sources["a.txt"])
    payload = {**step.result_payload, field: str(sources["b.txt"].pk)}
    InvestigationStep.objects.filter(pk=step.pk).update(result_payload=payload)
    assert _source_read_coverage(run) == []


def test_snapshot_content_recovery_and_dedup_remain_deterministic(owner, coverage_run, tmp_path):
    run, handle, sources = coverage_run
    first = read(owner, run, handle, sources["a.txt"])
    before = _source_read_coverage(run)
    # External files can change; the source snapshot and persisted result cannot.
    (tmp_path / "a.txt").write_text("Changed external content", encoding="utf-8")
    recovered = recover_investigation(actor=owner, run_id=run.pk)
    run.refresh_from_db()
    reused = read(owner, run, recovered, sources["a.txt"])
    assert reused.pk == first.pk
    assert run.steps.count() == 1
    assert _source_read_coverage(InvestigationRun.objects.get(pk=run.pk)) == before
    assert content_hash(_source_read_coverage(run)) == content_hash(before)


def test_full_read_budget_preserves_earliest_read_without_payload_accumulation(owner, coverage_run):
    run, handle, sources = coverage_run
    for cursor in range(DEFAULT_BUDGET["max_tool_calls"]):
        read(owner, run, handle, sources["a.txt"], cursor=cursor, limit=1)
    for cursor in range(40, 40 + DEFAULT_BUDGET["max_verifier_reads"]):
        read(owner, run, handle, sources["a.txt"], cursor=cursor, limit=1, verifier_read=True)
    run.refresh_from_db()
    context = _investigation_context(owner, run)
    entries = context["source_read_coverage"]
    assert len(entries) == DEFAULT_BUDGET["max_tool_calls"] + DEFAULT_BUDGET["max_verifier_reads"]
    assert entries[0]["sequence"] == 1
    assert len(context["recent_steps"]) == 5
    assert len(json.dumps(entries)) < 50_000
    assert all("items" not in entry and "result_payload" not in entry for entry in entries)
    with pytest.raises(InvestigationRunError, match="budget"):
        read(owner, run, handle, sources["a.txt"], cursor=81, limit=1)


def test_old_loop_contract_is_rejected_before_provider_call(owner, coverage_run):
    run, handle, _sources = coverage_run
    assert run.loop_version == run.execution_snapshot["loop_version"] == "vs1-agent-loop-v20"
    frozen = {**run.execution_snapshot, "loop_version": "vs1-agent-loop-v19"}
    InvestigationRun.objects.filter(pk=run.pk).update(
        loop_version="vs1-agent-loop-v19", execution_snapshot=frozen
    )
    run.refresh_from_db()
    with pytest.raises(InvestigationRunError) as error:
        request_planner_action(actor=owner, run=run, executor_token=handle.executor_token)
    assert error.value.code == "execution_version_unavailable"
    assert run.model_calls.count() == 0


def test_projection_preserves_existing_source_authorization(reader, coverage_run):
    run, _handle, _sources = coverage_run
    with pytest.raises(PermissionDenied):
        _investigation_context(reader, run)
