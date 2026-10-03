"""Current v21 product contract; historical v19/v20 evidence remains frozen."""

import json
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from ki_radar.accelerator import investigation_llm
from ki_radar.accelerator.investigation_llm import _investigation_context, request_planner_action
from ki_radar.accelerator.investigation_models import InvestigationRun
from ki_radar.accelerator.investigation_runtime import (
    InvestigationRunError,
    StartInvestigationRequest,
    execute_tool_step,
    recover_investigation,
    start_investigation,
)
from ki_radar.accelerator.issue118_fixtures import HISTORICAL_COMMIT, fixture_evidence
from tests.test_issue_3_investigation_runtime import make_process, snapshot_for_root


@pytest.fixture(autouse=True)
def forbid_real_provider(monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("Rollback checks must never call a real provider")

    monkeypatch.setattr(investigation_llm, "request_openrouter", forbidden)


@pytest.mark.django_db
@pytest.mark.parametrize("case_id", ["AP4-02", "AP4-04"])
def test_current_v21_planner_uses_only_five_recent_steps(
    owner, business_unit, case_id, monkeypatch
):
    root = Path(settings.BASE_DIR) / "tests/fixtures/ap4_source_packs" / case_id
    process = make_process(owner=owner, business_unit=business_unit)
    _, snapshot = snapshot_for_root(owner=owner, process=process, root=root)
    handle = start_investigation(
        actor=owner, request=StartInvestigationRequest(snapshot.snapshot_id, "rollback")
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.loop_version == run.execution_snapshot["loop_version"] == "vs1-agent-loop-v21"
    source = run.source_snapshot.sources.order_by("filename").first()
    early = execute_tool_step(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        tool_name="read_source",
        parameters={"source_id": str(source.pk), "cursor": 0, "limit": 100, "columns": []},
    )
    for query in ("Freigabe", "Ausnahme", "Prüfung", "Beleg", "Regel", "Prozess"):
        execute_tool_step(
            actor=owner,
            run_id=run.pk,
            executor_token=handle.executor_token,
            tool_name="search_sources",
            parameters={"query": query},
        )
    run.refresh_from_db()
    context = _investigation_context(owner, run)
    assert len(context["recent_steps"]) == 5
    assert early.sequence not in [step["sequence"] for step in context["recent_steps"]]
    assert "source_read_coverage" not in context
    assert not {"claim_register", "brief_payload", "source_relevance"} & context.keys()
    assert run.steps.count() == 7  # Historical steps remain persisted.
    recovered = recover_investigation(actor=owner, run_id=run.pk)
    run.refresh_from_db()

    def capture(**kwargs):
        assert kwargs["context"] == _investigation_context(owner, run)
        assert "source_read_coverage" not in kwargs["context"]
        return {"action": "clarify", "clarification_reason": "missing_evidence"}, None

    monkeypatch.setattr(investigation_llm, "_structured_provider_call", capture)
    assert (
        request_planner_action(actor=owner, run=run, executor_token=recovered.executor_token).action
        == "clarify"
    )
    assert run.model_calls.count() == 0


@pytest.mark.django_db
def test_historical_v20_contract_fails_closed_without_relabeling(owner, business_unit, tmp_path):
    (tmp_path / "notes.txt").write_text("Evidence", encoding="utf-8")
    process = make_process(owner=owner, business_unit=business_unit)
    _, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner, request=StartInvestigationRequest(snapshot.snapshot_id, "historical-v20")
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    frozen = {**run.execution_snapshot, "loop_version": "vs1-agent-loop-v20"}
    InvestigationRun.objects.filter(pk=run.pk).update(
        loop_version="vs1-agent-loop-v20", execution_snapshot=frozen
    )
    recovered = recover_investigation(actor=owner, run_id=run.pk)
    run.refresh_from_db()
    with pytest.raises(InvestigationRunError) as error:
        request_planner_action(actor=owner, run=run, executor_token=recovered.executor_token)
    assert error.value.code == "execution_version_unavailable"
    run.refresh_from_db()
    assert run.loop_version == "vs1-agent-loop-v20"
    assert run.execution_snapshot == frozen
    assert run.status == InvestigationRun.Status.RUNNING
    assert run.model_calls.count() == run.steps.count() == 0


def test_archived_c1_proof_remains_valid_only_for_historical_commit():
    root = Path(settings.BASE_DIR)
    proof = root / "artifacts/issue106/exp118/c1-state-fixtures.json"
    payload = fixture_evidence(proof, root, HISTORICAL_COMMIT)
    assert payload["passed_cases"] == ["AP4-02", "AP4-04"]
    with pytest.raises(CommandError, match="commit/test selection mismatch"):
        fixture_evidence(proof, root, "a" * 40)
    plan = json.loads((root / "artifacts/issue106/exp118/plan.json").read_text(encoding="utf-8"))
    assert plan["variant_commit"] == HISTORICAL_COMMIT


def test_historical_fixture_execution_is_unavailable_on_current_runtime(tmp_path):
    with pytest.raises(CommandError, match="frozen v20 runtime"):
        call_command(
            "check_issue118_fixtures",
            expected_variant_commit=HISTORICAL_COMMIT,
            output=str(tmp_path / "proof.json"),
        )
    assert not (tmp_path / "proof.json").exists()


def test_export_cannot_overwrite_frozen_archive():
    with pytest.raises(CommandError, match="read-only"):
        call_command("export_issue118_experiment", plan="unused")
