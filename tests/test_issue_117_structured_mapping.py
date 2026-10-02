from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.utils import timezone

from ki_radar.accelerator.investigation_llm import (
    SYNTHESIS_INSTRUCTION,
    VERIFIER_INSTRUCTION,
    _assert_frozen_execution_contract,
    _synthesis_context,
    _verifier_context,
)
from ki_radar.accelerator.investigation_models import (
    InvestigationModelCall,
    InvestigationRun,
    InvestigationSourceFolder,
    InvestigationVerifierReport,
)
from ki_radar.accelerator.investigation_policy import PolicyOutcome
from ki_radar.accelerator.investigation_runtime import (
    InvestigationRunError,
    StartInvestigationRequest,
    apply_planner_state,
    content_hash,
    decision_brief_blockers,
    evaluate_run_policy,
    execute_tool_step,
    recover_investigation,
    start_investigation,
    structured_mapping_blockers,
)
from ki_radar.accelerator.investigation_tools import (
    SnapshotRequest,
    create_source_snapshot,
    list_sources,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage


def make_process(*, owner, business_unit, name="Issue 117"):
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
        pain_points="Manuelle Zuordnung",
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
        bottlenecks="Manuelle Zuordnung",
        diagnostic_observations="Explizite Zuordnung erforderlich",
        cause_hypotheses="",
        confirmed_causes="",
        constraints="",
        exceptions="",
        baseline_metrics="Offen",
        analyzed_by=owner,
    )


def snapshot_for_root(*, owner, process, root: Path):
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
            decision_question="Ordne die explizit vorgegebenen Fälle nachvollziehbar zu.",
            run_limits={},
        ),
    )
    return snapshot


def write_default_sources(root: Path) -> None:
    (root / "cases.csv").write_text(
        "case_id,decision,amount\n"
        "E01,standard,10\n"
        "E02,manual_review,20\n"
        "E03,standard,30\n"
        "E04,manual_review,40\n",
        encoding="utf-8",
    )
    (root / "secondary.csv").write_text(
        "case_id,decision,amount\n"
        "E01,secondary,11\n"
        "X02,secondary,22\n",
        encoding="utf-8",
    )


def source_by_filename(owner, snapshot, filename):
    return next(
        source
        for source in list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources
        if source.filename == filename
    )


def obligation(source, *, obligation_id="routing", case_keys=("E01", "E02")):
    return {
        "obligation_id": obligation_id,
        "source_id": str(source.source_id),
        "case_key_column": "case_id",
        "case_keys": list(case_keys),
        "mapping_dimension": "routing decision",
        "exhaustive": True,
    }


def source_ref(source, *, row, column="case_id"):
    return {
        "source_id": str(source.source_id),
        "locator": {"row": row, "column": column},
        "revision_hash": source.content_sha256,
    }


def assignment(source, case_key, value, row):
    return {
        "case_key": case_key,
        "value": value,
        "references": [source_ref(source, row=row)],
    }


def mapping_payload(obligation_id, assignments):
    return {
        "structured_mappings": [
            {
                "obligation_id": obligation_id,
                "assignments": list(assignments),
            }
        ]
    }


def start_default_mapping_run(
    *,
    owner,
    business_unit,
    tmp_path,
    key="issue117",
    case_keys=("E01", "E02"),
    extra_obligations=(),
):
    process = make_process(owner=owner, business_unit=business_unit, name=f"Issue 117 {key}")
    write_default_sources(tmp_path)
    snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    primary = source_by_filename(owner, snapshot, "cases.csv")
    obligations = (obligation(primary, case_keys=case_keys), *extra_obligations)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot.snapshot_id,
            key,
            structured_mapping_obligations=tuple(obligations),
        ),
    )
    return snapshot, handle, primary


def persist_brief(*, owner, handle, payload):
    apply_planner_state(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        brief_payload=payload,
    )
    return InvestigationRun.objects.get(pk=handle.run_id)


def make_verifier_report(run):
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
        accepted_payload={
            "read_requests": [],
            "findings": [],
            "source_references_valid": True,
            "checked_critical_claims": [],
        },
        accepted_payload_hash="b" * 64,
        finished_at=timezone.now(),
    )
    return InvestigationVerifierReport.objects.create(
        run=run,
        revision=run.verifier_reports.count() + 1,
        model_call=call,
        success=True,
        findings=[],
        critical_findings=0,
        source_references_valid=True,
        checked_critical_claims=[],
        bound_hashes={
            "contract": run.contract_hash,
            "manifest": run.manifest_hash,
            "register": run.register_hash,
            "brief": run.brief_hash,
        },
        created_for_executor_generation=run.executor_generation,
    )


@pytest.mark.django_db
def test_complete_explicit_mapping_has_no_coverage_blocker(owner, business_unit, tmp_path):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="complete"
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [
                assignment(source, "E01", "standard", 1),
                assignment(source, "E02", "manual_review", 2),
            ],
        ),
    )
    assert structured_mapping_blockers(run) == ()


@pytest.mark.django_db
def test_missing_required_key_blocks_ready(owner, business_unit, tmp_path):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="missing"
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload("routing", [assignment(source, "E01", "standard", 1)]),
    )
    assert "structured_mapping_coverage_incomplete:routing" in structured_mapping_blockers(run)
    decision = evaluate_run_policy(run)
    assert decision.outcome != PolicyOutcome.READY_FOR_DECISION
    assert "structured_mapping_coverage_incomplete:routing" in decision.blockers


@pytest.mark.django_db
def test_duplicate_case_key_blocks(owner, business_unit, tmp_path):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="duplicate"
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [
                assignment(source, "E01", "standard", 1),
                assignment(source, "E01", "standard", 1),
                assignment(source, "E02", "manual_review", 2),
            ],
        ),
    )
    assert (
        "structured_mapping_duplicate_case_key:routing:E01"
        in structured_mapping_blockers(run)
    )


@pytest.mark.django_db
def test_unexpected_case_key_and_same_count_wrong_keys_block(owner, business_unit, tmp_path):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="wrong-keys"
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [
                assignment(source, "E01", "standard", 1),
                assignment(source, "E03", "standard", 3),
            ],
        ),
    )
    blockers = structured_mapping_blockers(run)
    assert "structured_mapping_unexpected_case_key:routing:E03" in blockers
    assert "structured_mapping_coverage_incomplete:routing" in blockers


@pytest.mark.django_db
def test_wrong_obligation_id_blocks_expected_obligation(owner, business_unit, tmp_path):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="wrong-obligation"
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "other-routing",
            [
                assignment(source, "E01", "standard", 1),
                assignment(source, "E02", "manual_review", 2),
            ],
        ),
    )
    blockers = structured_mapping_blockers(run)
    assert "structured_mapping_unexpected_obligation:other-routing" in blockers
    assert "structured_mapping_coverage_incomplete:routing" in blockers


@pytest.mark.django_db
def test_invalid_or_wrong_source_reference_blocks(owner, business_unit, tmp_path):
    process = make_process(owner=owner, business_unit=business_unit, name="Issue 117 wrong source")
    write_default_sources(tmp_path)
    snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    primary = source_by_filename(owner, snapshot, "cases.csv")
    secondary = source_by_filename(owner, snapshot, "secondary.csv")
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot.snapshot_id,
            "wrong-source",
            structured_mapping_obligations=(obligation(primary, case_keys=("E01",)),),
        ),
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [assignment(secondary, "E01", "standard", 1)],
        ),
    )
    assert (
        "structured_mapping_reference_invalid:routing:E01"
        in structured_mapping_blockers(run)
    )


@pytest.mark.django_db
def test_rows_outside_explicit_scope_do_not_create_blocker(owner, business_unit, tmp_path):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="bounded-scope",
        case_keys=("E01", "E02"),
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [
                assignment(source, "E01", "standard", 1),
                assignment(source, "E02", "manual_review", 2),
            ],
        ),
    )
    assert structured_mapping_blockers(run) == ()
    assert "E03" not in json.dumps(run.execution_snapshot["structured_mapping_obligations"])


@pytest.mark.django_db
def test_csv_without_obligation_and_text_case_remain_unchanged(owner, business_unit, tmp_path):
    process = make_process(owner=owner, business_unit=business_unit, name="Issue 117 default")
    (tmp_path / "cases.csv").write_text("case_id,value\nE01,1\nE02,2\n", encoding="utf-8")
    (tmp_path / "note.md").write_text("# Kontext\nKeine Mapping-Pflicht.", encoding="utf-8")
    snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(snapshot.snapshot_id, "no-obligation"),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.execution_snapshot["structured_mapping_obligations"] == []
    assert structured_mapping_blockers(run) == ()


@pytest.mark.django_db
def test_pagination_and_column_projection_do_not_change_expected_scope(
    owner, business_unit, tmp_path
):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="projection"
    )
    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="read_source",
        parameters={
            "source_id": str(source.source_id),
            "cursor": 0,
            "limit": 1,
            "columns": ["case_id"],
        },
        target_claim_id="",
        expected_discriminating_finding="",
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [
                assignment(source, "E01", "standard", 1),
                assignment(source, "E02", "manual_review", 2),
            ],
        ),
    )
    assert structured_mapping_blockers(run) == ()


@pytest.mark.django_db
def test_same_case_key_in_two_sources_is_bound_per_obligation(owner, business_unit, tmp_path):
    process = make_process(owner=owner, business_unit=business_unit, name="Issue 117 two sources")
    write_default_sources(tmp_path)
    snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    primary = source_by_filename(owner, snapshot, "cases.csv")
    secondary = source_by_filename(owner, snapshot, "secondary.csv")
    obligations = (
        obligation(primary, obligation_id="primary", case_keys=("E01",)),
        obligation(secondary, obligation_id="secondary", case_keys=("E01",)),
    )
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot.snapshot_id,
            "two-sources",
            structured_mapping_obligations=obligations,
        ),
    )
    payload = {
        "structured_mappings": [
            {
                "obligation_id": "primary",
                "assignments": [assignment(primary, "E01", "standard", 1)],
            },
            {
                "obligation_id": "secondary",
                "assignments": [assignment(secondary, "E01", "secondary", 1)],
            },
        ]
    }
    run = persist_brief(owner=owner, handle=handle, payload=payload)
    assert structured_mapping_blockers(run) == ()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mutator",
    [
        lambda item: {**item, "source_id": "00000000-0000-0000-0000-000000000000"},
        lambda item: {**item, "case_key_column": "missing"},
        lambda item: {**item, "case_keys": []},
        lambda item: {**item, "case_keys": ["E01", "E01"]},
        lambda item: {**item, "case_keys": ["E99"]},
        lambda item: {**item, "exhaustive": False},
    ],
)
def test_invalid_activation_contract_fails_closed(
    owner, business_unit, tmp_path, mutator
):
    process = make_process(owner=owner, business_unit=business_unit, name="Issue 117 invalid")
    write_default_sources(tmp_path)
    snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    primary = source_by_filename(owner, snapshot, "cases.csv")
    invalid = mutator(obligation(primary))
    with pytest.raises(InvestigationRunError) as exc_info:
        start_investigation(
            actor=owner,
            request=StartInvestigationRequest(
                snapshot.snapshot_id,
                f"invalid-{content_hash(invalid)[:8]}",
                structured_mapping_obligations=(invalid,),
            ),
        )
    assert exc_info.value.code == "invalid_structured_mapping_obligation"


@pytest.mark.django_db
def test_text_source_cannot_activate_mapping_obligation(owner, business_unit, tmp_path):
    process = make_process(owner=owner, business_unit=business_unit, name="Issue 117 text")
    (tmp_path / "note.md").write_text("# Fall\nE01", encoding="utf-8")
    snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    source = source_by_filename(owner, snapshot, "note.md")
    with pytest.raises(InvestigationRunError) as exc_info:
        start_investigation(
            actor=owner,
            request=StartInvestigationRequest(
                snapshot.snapshot_id,
                "text-obligation",
                structured_mapping_obligations=(obligation(source, case_keys=("E01",)),),
            ),
        )
    assert exc_info.value.code == "invalid_structured_mapping_obligation"


@pytest.mark.django_db
def test_mapping_removal_inside_existing_brief_section_is_rechecked(
    owner, business_unit, tmp_path
):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="repair-loss"
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [
                assignment(source, "E01", "standard", 1),
                assignment(source, "E02", "manual_review", 2),
            ],
        ),
    )
    assert structured_mapping_blockers(run) == ()

    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload("routing", [assignment(source, "E01", "standard", 1)]),
    )
    assert "structured_mapping_coverage_incomplete:routing" in structured_mapping_blockers(run)


@pytest.mark.django_db
def test_pre_verifier_repair_context_keeps_existing_mapping_and_obligation(
    owner, business_unit, tmp_path
):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="repair-context"
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload("routing", [assignment(source, "E01", "standard", 1)]),
    )
    InvestigationModelCall.objects.create(
        run=run,
        role=InvestigationModelCall.Role.SYNTHESIZER,
        status=InvestigationModelCall.Status.SUCCESS,
        executor_generation=run.executor_generation,
        requested_model="test-model",
        returned_model="test-model",
        model_revision="test-revision",
        prompt_version="test-synth",
        prompt_hash="c" * 64,
        instruction_template="test",
        schema_version="test-schema",
        accepted_payload={"claim_register": [], "brief_payload": run.brief_payload},
        accepted_payload_hash="d" * 64,
        finished_at=timezone.now(),
    )
    context = _synthesis_context(owner, run)
    assert context["synthesis_mode"] == "pre_verifier_repair"
    assert context["structured_mapping_obligations"][0]["obligation_id"] == "routing"
    assert context["brief_payload"]["structured_mappings"][0]["assignments"][0]["case_key"] == "E01"
    assert "structured_mapping_coverage_incomplete:routing" in context["pre_verifier_blockers"]


@pytest.mark.django_db
def test_repair_can_complete_missing_assignment(owner, business_unit, tmp_path):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="repair-complete"
    )
    persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload("routing", [assignment(source, "E01", "standard", 1)]),
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [
                assignment(source, "E01", "standard", 1),
                assignment(source, "E02", "manual_review", 2),
            ],
        ),
    )
    assert structured_mapping_blockers(run) == ()


@pytest.mark.django_db
def test_budget_exhaustion_with_missing_mapping_never_becomes_ready(
    owner, business_unit, tmp_path
):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="budget"
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload("routing", [assignment(source, "E01", "standard", 1)]),
    )
    usage = dict(run.usage)
    usage["model_calls"] = run.budget_limits["max_model_calls"]
    run.usage = usage
    run.save(update_fields=["usage", "updated_at"])
    decision = evaluate_run_policy(run)
    assert decision.outcome != PolicyOutcome.READY_FOR_DECISION
    assert "structured_mapping_coverage_incomplete:routing" in decision.blockers


@pytest.mark.django_db
def test_mapping_change_invalidates_existing_verifier(owner, business_unit, tmp_path):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="stale-mapping"
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [
                assignment(source, "E01", "standard", 1),
                assignment(source, "E02", "manual_review", 2),
            ],
        ),
    )
    make_verifier_report(run)
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [
                assignment(source, "E01", "changed-but-complete", 1),
                assignment(source, "E02", "manual_review", 2),
            ],
        ),
    )
    decision = evaluate_run_policy(run)
    assert "verifier_stale" in decision.blockers


@pytest.mark.django_db
def test_obligation_contract_change_invalidates_existing_verifier(
    owner, business_unit, tmp_path
):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="stale-obligation"
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [
                assignment(source, "E01", "standard", 1),
                assignment(source, "E02", "manual_review", 2),
            ],
        ),
    )
    make_verifier_report(run)
    frozen = dict(run.execution_snapshot)
    changed = [dict(item) for item in frozen["structured_mapping_obligations"]]
    changed[0]["case_keys"] = ["E01", "E02", "E03"]
    frozen["structured_mapping_obligations"] = changed
    run.execution_snapshot = frozen
    run.contract_hash = content_hash({"changed_obligation": changed})
    decision = evaluate_run_policy(run)
    assert "verifier_stale" in decision.blockers
    assert "structured_mapping_coverage_incomplete:routing" in decision.blockers


@pytest.mark.django_db
def test_semantically_wrong_but_complete_value_is_not_python_blocked(
    owner, business_unit, tmp_path
):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="semantic-separation"
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(
            "routing",
            [
                assignment(source, "E01", "manual_review", 1),
                assignment(source, "E02", "standard", 2),
            ],
        ),
    )
    assert structured_mapping_blockers(run) == ()
    verifier_context = _verifier_context(run)
    assert verifier_context["structured_mapping_obligations"][0]["mapping_dimension"] == (
        "routing decision"
    )


@pytest.mark.django_db
def test_same_idempotency_key_same_obligation_reuses_but_changed_contract_fails(
    owner, business_unit, tmp_path
):
    process = make_process(owner=owner, business_unit=business_unit, name="Issue 117 idempotency")
    write_default_sources(tmp_path)
    snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    source = source_by_filename(owner, snapshot, "cases.csv")
    first_obligation = obligation(source, case_keys=("E02", "E01"))
    first = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot.snapshot_id,
            "idempotent-mapping",
            structured_mapping_obligations=(first_obligation,),
        ),
    )
    same = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot.snapshot_id,
            "idempotent-mapping",
            structured_mapping_obligations=(obligation(source, case_keys=("E01", "E02")),),
        ),
    )
    assert same.reused is True
    assert same.run_id == first.run_id

    changed = {
        **obligation(source, case_keys=("E01", "E02")),
        "mapping_dimension": "different dimension",
    }
    with pytest.raises(InvestigationRunError) as exc_info:
        start_investigation(
            actor=owner,
            request=StartInvestigationRequest(
                snapshot.snapshot_id,
                "idempotent-mapping",
                structured_mapping_obligations=(changed,),
            ),
        )
    assert exc_info.value.code == "idempotency_contract_conflict"
    assert exc_info.value.existing_run_id == first.run_id


@pytest.mark.django_db
def test_v19_run_fails_closed_and_v21_run_recovers(owner, business_unit, tmp_path):
    _snapshot, handle, _source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="versions"
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    recovered = recover_investigation(actor=owner, run_id=run.pk)
    assert recovered.run_id == run.pk
    run.refresh_from_db()
    _assert_frozen_execution_contract(run)

    run.loop_version = "vs1-agent-loop-v19"
    frozen = dict(run.execution_snapshot)
    frozen["loop_version"] = "vs1-agent-loop-v19"
    run.execution_snapshot = frozen
    with pytest.raises(InvestigationRunError) as exc_info:
        _assert_frozen_execution_contract(run)
    assert exc_info.value.code == "execution_version_unavailable"


@pytest.mark.django_db
def test_reused_tool_result_cannot_bypass_mapping_guard(owner, business_unit, tmp_path):
    _snapshot, handle, source = start_default_mapping_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path, key="tool-result"
    )
    execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(source.source_id),
            "group_by": "decision",
            "aggregation": "count",
            "filters": [],
            "value_column": None,
            "unit_column": None,
        },
        target_claim_id="",
        expected_discriminating_finding="",
    )
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload("routing", [assignment(source, "E01", "standard", 1)]),
    )
    assert run.source_snapshot.tool_results.exists()
    assert "structured_mapping_coverage_incomplete:routing" in structured_mapping_blockers(run)


def test_prompt_contracts_preserve_server_verifier_separation():
    assert "structured_mapping_obligations" in SYNTHESIS_INSTRUCTION
    assert "bereits valide Assignments erhalten" in SYNTHESIS_INSTRUCTION
    assert "structured_mapping_obligations" in VERIFIER_INSTRUCTION
    assert "Sollmenge selbst kommt ausschließlich aus dem" in VERIFIER_INSTRUCTION
    assert "materiell falsche Klassifikation" in VERIFIER_INSTRUCTION


@pytest.mark.django_db
@pytest.mark.parametrize(
    "case",
    json.loads(
        Path("tests/fixtures/issue117_structured_mapping_replays_v1.json").read_text(
            encoding="utf-8"
        )
    )["cases"],
    ids=lambda item: item["name"],
)
def test_historical_ap1_mapping_replay(case, owner, business_unit, tmp_path):
    process = make_process(
        owner=owner,
        business_unit=business_unit,
        name=f"Issue 117 replay {case['name']}",
    )
    (tmp_path / "cases.csv").write_text(case["csv"], encoding="utf-8")
    snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    source = source_by_filename(owner, snapshot, "cases.csv")
    ob = {
        "obligation_id": case["obligation_id"],
        "source_id": str(source.source_id),
        "case_key_column": "case_id",
        "case_keys": case["case_keys"],
        "mapping_dimension": "test-only historical routing classification",
        "exhaustive": True,
    }
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot.snapshot_id,
            f"replay-{content_hash(case['name'])[:12]}",
            structured_mapping_obligations=(ob,),
        ),
    )
    assignments = [
        assignment(source, item["case_key"], item["value"], item["row"])
        for item in case["assignments"]
    ]
    run = persist_brief(
        owner=owner,
        handle=handle,
        payload=mapping_payload(case["obligation_id"], assignments),
    )
    blocked = bool(structured_mapping_blockers(run))
    assert blocked is case["expected_blocked"]
    if blocked:
        assert (
            f"structured_mapping_coverage_incomplete:{case['obligation_id']}"
            in structured_mapping_blockers(run)
        )
