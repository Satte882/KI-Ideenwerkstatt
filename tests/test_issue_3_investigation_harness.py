from __future__ import annotations

import json
from pathlib import Path

import pytest

from ki_radar.accelerator.investigation_llm import PlannerAction
from ki_radar.accelerator.investigation_loop import advance_investigation
from ki_radar.accelerator.investigation_models import InvestigationRun, InvestigationSourceFolder
from ki_radar.accelerator.investigation_runtime import (
    StartInvestigationRequest,
    execute_tool_step,
    start_investigation,
)
from ki_radar.accelerator.investigation_tools import (
    SnapshotRequest,
    create_source_snapshot,
    list_sources,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage


def make_process(*, owner, business_unit, name):
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


def start_pack(*, owner, business_unit, pack):
    process = make_process(owner=owner, business_unit=business_unit, name=f"Pack {pack}")
    root = Path(__file__).parent / "fixtures" / "investigation_source_packs" / pack
    folder = InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name=f"Pack {pack}",
        root_path=str(root),
        registered_by=owner,
    )
    snapshot = create_source_snapshot(
        actor=owner,
        request=SnapshotRequest(
            process_analysis_id=process.pk,
            folder_id=folder.pk,
            decision_question="Welche Ursache und Lösungsrichtung ist durch die Evidenz gestützt?",
            run_limits={},
        ),
    )
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, f"pack-{pack}"),
    )
    sources = list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources
    cases = next(source for source in sources if source.filename == "cases.csv")
    return process, snapshot, handle, cases


@pytest.mark.django_db
def test_a_b_c_measurement_harness_distinguishes_evidence_gap_and_supported_signals(
    owner,
    business_unit,
):
    fixture = Path(__file__).parent / "fixtures" / "investigation_expected_v1.json"
    expected = json.loads(fixture.read_text(encoding="utf-8"))

    _process_a, _snapshot_a, handle_a, source_a = start_pack(
        owner=owner, business_unit=business_unit, pack="A"
    )
    result_a = execute_tool_step(
        actor=owner,
        run_id=handle_a.run_id,
        executor_token=handle_a.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(source_a.source_id),
            "group_by": expected["A"]["analysis"]["group_by"],
            "aggregation": expected["A"]["analysis"]["aggregation"],
            "value_column": expected["A"]["analysis"]["value_column"],
            "filters": [],
            "unit_column": expected["A"]["analysis"]["unit_column"],
        },
        target_claim_id="hyp-approver-availability",
    )
    assert (
        expected["A"]["analysis"]["expected_difference"] in result_a.result_payload["differences"]
    )

    _process_b, _snapshot_b, handle_b, source_b = start_pack(
        owner=owner, business_unit=business_unit, pack="B"
    )
    result_b = execute_tool_step(
        actor=owner,
        run_id=handle_b.run_id,
        executor_token=handle_b.executor_token,
        tool_name="profile_csv",
        parameters={"source_id": str(source_b.source_id)},
        target_claim_id="critical-denominator",
    )
    profile = expected["B"]["profile"]
    assert result_b.result_payload["columns"][profile["column"]]["missing"] == profile["missing"]
    assert result_b.result_payload["columns"][profile["column"]]["type"] == profile["type"]

    _process_c, _snapshot_c, handle_c, source_c = start_pack(
        owner=owner, business_unit=business_unit, pack="C"
    )
    result_c = execute_tool_step(
        actor=owner,
        run_id=handle_c.run_id,
        executor_token=handle_c.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(source_c.source_id),
            "group_by": expected["C"]["analysis"]["group_by"],
            "aggregation": expected["C"]["analysis"]["aggregation"],
            "value_column": expected["C"]["analysis"]["value_column"],
            "filters": [],
            "unit_column": expected["C"]["analysis"]["unit_column"],
        },
        target_claim_id="hyp-queue-retries",
    )
    groups_c = {item["group"]: item for item in result_c.result_payload["groups"]}
    for group, contract in expected["C"]["analysis"]["groups"].items():
        assert groups_c[group]["value"] == contract["value"]
        assert groups_c[group]["population"] == contract["population"]

    for run_id in (handle_a.run_id, handle_b.run_id, handle_c.run_id):
        run = InvestigationRun.objects.get(pk=run_id)
        assert run.usage["tool_calls"] == 1
        assert run.data_check_executed is True


@pytest.mark.django_db
def test_controlled_adaptive_trace_uses_result_before_choosing_next_tool(
    owner,
    business_unit,
):
    _process, snapshot, handle, source = start_pack(
        owner=owner,
        business_unit=business_unit,
        pack="A",
    )

    def adaptive_planner(**kwargs):
        run = kwargs["run"]
        steps = list(run.steps.order_by("sequence"))
        if not steps:
            return PlannerAction(
                action="tool",
                target_claim_id="data-shape",
                expected_discriminating_finding=(
                    "Prüfen, welche Spalten belastbar analysierbar sind."
                ),
                rationale="Erst Datenstruktur prüfen.",
                tool_name="profile_csv",
                parameters={"source_id": str(source.source_id)},
                claim_register=(),
                brief_payload={},
                source_relevance={},
                progress_kind="none",
                progress_payload={},
                clarification_reason="",
                clarification_payload={},
            )

        latest = steps[-1]
        if latest.tool_name == "profile_csv":
            columns = latest.result_payload["columns"]
            assert "approver_available" in columns
            assert "approval_hours" in columns
            return PlannerAction(
                action="tool",
                target_claim_id="hyp-availability",
                expected_discriminating_finding="Unterscheidet Verfügbarkeit die Laufzeit?",
                rationale="Die profilierten Spalten erlauben einen Gruppenvergleich.",
                tool_name="compare_groups",
                parameters={
                    "source_id": str(source.source_id),
                    "group_by": "approver_available",
                    "aggregation": "mean",
                    "value_column": "approval_hours",
                    "filters": [],
                    "unit_column": "unit",
                },
                claim_register=(),
                brief_payload={},
                source_relevance={},
                progress_kind="none",
                progress_payload={},
                clarification_reason="",
                clarification_payload={},
            )

        assert latest.tool_name == "compare_groups"
        assert latest.result_payload["differences"]
        return PlannerAction(
            action="tool",
            target_claim_id="counter-hyp-availability",
            expected_discriminating_finding=(
                "Gezielt Gegenbelege zur Verfügbarkeitshypothese suchen."
            ),
            rationale="Nach unterscheidender Analyse folgt Gegenbelegsuche.",
            tool_name="search_sources",
            parameters={"query": "Gegen", "cursor": 0, "limit": 20},
            claim_register=(),
            brief_payload={},
            source_relevance={},
            progress_kind="none",
            progress_payload={},
            clarification_reason="",
            clarification_payload={},
        )

    first = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=adaptive_planner,
    )
    second = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=adaptive_planner,
    )
    third = advance_investigation(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        planner=adaptive_planner,
    )

    assert first.status == second.status == third.status == InvestigationRun.Status.RUNNING
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert [step.tool_name for step in run.steps.order_by("sequence")] == [
        "profile_csv",
        "compare_groups",
        "search_sources",
    ]
    assert run.usage["tool_calls"] == 3
    assert run.source_snapshot_id == snapshot.snapshot_id
