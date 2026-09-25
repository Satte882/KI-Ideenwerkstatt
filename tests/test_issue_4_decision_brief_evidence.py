from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.investigation_benchmark import (
    assert_comparable_runs,
    comparison_contract,
    evidence_campaign_report,
    prepare_fixed_route,
    request_fixed_route_synthesis,
)
from ki_radar.accelerator.investigation_brief import (
    materialize_decision_brief,
    preview_decision_brief_materialization,
    render_decision_brief_markdown,
)
from ki_radar.accelerator.investigation_evidence import (
    authorize_campaign_continuation,
    create_evidence_campaign,
    mark_provider_attempt_uncertain,
    reserve_provider_attempt,
)
from ki_radar.accelerator.investigation_llm import (
    PlannerAction,
    _estimate_tokens,
    _reserve_model_call,
    _structured_provider_call,
)
from ki_radar.accelerator.investigation_models import (
    InvestigationBriefRevision,
    InvestigationModelCall,
    InvestigationProviderReservation,
    InvestigationRun,
    InvestigationSource,
    InvestigationSourceFolder,
    InvestigationStep,
)
from ki_radar.accelerator.investigation_policy import PolicyDecision, PolicyOutcome, ReasonCode
from ki_radar.accelerator.investigation_runtime import (
    ISSUE4_INVESTIGATION_PROVIDER_POLICY,
    InvestigationRunError,
    StartInvestigationRequest,
    abort_investigation,
    apply_planner_state,
    canonical_json,
    content_hash,
    evaluate_run_policy,
    execute_tool_step,
    pre_verifier_blockers_for_run,
    set_source_relevance,
    start_investigation,
)
from ki_radar.accelerator.investigation_tools import (
    SnapshotRequest,
    create_source_snapshot,
)
from ki_radar.accelerator.management.commands import run_issue4_evidence as issue4_evidence_command
from ki_radar.architecture.investigation_adoption import (
    InvestigationDraftAdoptionError,
    adopt_investigation_drafts,
    preview_investigation_draft_adoption,
)
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.openrouter import OpenRouterUnavailable


def make_process(*, owner, business_unit, name="VS1/3 Fall"):
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


def write_variant_pack(root: Path, variant: str):
    root.mkdir(parents=True, exist_ok=True)
    if variant == "A":
        (root / "01_case_note.md").write_text("Hypothese Wissenslücke.", encoding="utf-8")
        (root / "02_counterevidence.md").write_text(
            "Gegenbeleg: Freigeberverfügbarkeit beeinflusst Laufzeit.",
            encoding="utf-8",
        )
        (root / "cases.csv").write_text(
            "approver_available,approval_hours,unit\nyes,5,h\nyes,5,h\nno,29,h\nno,30,h\n",
            encoding="utf-8",
        )
    elif variant == "B":
        (root / "01_case_note.md").write_text("Bezugsgröße unklar.", encoding="utf-8")
        (root / "02_report.md").write_text(
            "18 Eskalationen, Grundgesamtheit fehlt.",
            encoding="utf-8",
        )
        (root / "cases.csv").write_text(
            "period,escalations,total_eligible,unit\n"
            "2026-06,5,,cases\n"
            "2026-07,7,,cases\n"
            "2026-08,6,,cases\n",
            encoding="utf-8",
        )
    elif variant == "C":
        (root / "01_case_note.md").write_text(
            "Queue-Fehler als alternative Ursache.",
            encoding="utf-8",
        )
        (root / "02_system_note.md").write_text(
            "Queue-Retries bei langsamen Fällen.",
            encoding="utf-8",
        )
        (root / "cases.csv").write_text(
            "queue_retries,approval_hours,unit\n0,5,h\n0,6,h\n4,23,h\n5,27,h\n",
            encoding="utf-8",
        )
    else:
        raise AssertionError(f"unknown test variant: {variant}")


def evidence_campaign(*, owner, process, max_calls=20, input_tokens=200_000, output_tokens=50_000):
    return create_evidence_campaign(
        actor=owner,
        process_analysis_id=process.pk,
        campaign_key=f"issue4-{uuid.uuid4().hex[:24]}",
        limits={
            "max_provider_calls": max_calls,
            "max_input_tokens": input_tokens,
            "max_output_tokens": output_tokens,
        },
    )


def model_call(run, suffix):
    return InvestigationModelCall.objects.create(
        run=run,
        role=InvestigationModelCall.Role.PLANNER,
        executor_generation=run.executor_generation,
        requested_model="stub-model",
        prompt_version=f"stub-{suffix}",
        prompt_hash=(suffix[0] if suffix else "a") * 64,
        instruction_template="stub",
        schema_version="stub-schema",
    )


def source_reference(source, *, row=1, column=None):
    locator = {"row": row}
    if column is not None:
        locator["column"] = column
    return {
        "source_id": str(source.pk),
        "revision_hash": source.content_sha256,
        "locator": locator,
    }


def full_brief(*, run, source, result_id, existing_option_id=None):
    ref = source_reference(source, row=1, column="group")
    tool_ref = {
        "tool_result_id": str(result_id),
        "revision_hash": source.content_sha256,
    }
    first_option = {
        "name": "Freigabe organisatorisch stabilisieren",
        "option_type": SolutionOption.OptionType.ORGANIZATIONAL,
        "description": "Vertretungsregel und klare Übergabe etablieren.",
        "expected_value": "Wartezeiten bei Abwesenheit reduzieren.",
        "bottleneck_coverage": "Adressiert die beobachtete Wartezeit.",
        "data_requirements": "Keine zusätzlichen Daten.",
        "application_impact": "Keine.",
        "integration_impact": "Keine.",
        "risks": "Vertretungsregel muss fachlich tragfähig sein.",
        "architecture_fit": "Prozessnahe organisatorische Option.",
        "non_ai": True,
        "status_quo": False,
    }
    if existing_option_id is not None:
        first_option["existing_option_id"] = str(existing_option_id)
    return {
        "question_scope": {
            "question": run.decision_question,
            "scope": "Nur der autorisierte Freigabeprozess und der eingefrorene Quellenraum.",
        },
        "problem": {
            "statement": "Freigabezeiten schwanken deutlich.",
            "references": [ref],
        },
        "hypotheses": [
            {
                "statement": "Freigeberverfügbarkeit beeinflusst die Wartezeit.",
                "status": "supported",
                "references": [ref],
                "counterevidence_refs": [],
            },
            {
                "statement": "Fehlendes Wissen ist die alleinige Hauptursache.",
                "status": "refuted",
                "references": [],
                "counterevidence_refs": [ref],
            },
        ],
        "calculations": [
            {
                "summary": "Gruppenunterschied wurde reproduzierbar berechnet.",
                "reference": tool_ref,
                "population": {"rows_total": 4, "aggregated_rows": 4},
                "limits": "Kleine synthetische Stichprobe; keine Kausalitätsaussage.",
            }
        ],
        "options": [
            first_option,
            {
                "name": "Status quo beibehalten",
                "option_type": SolutionOption.OptionType.NO_TECH,
                "description": "Keine Änderung vornehmen und weitere Daten sammeln.",
                "expected_value": "Vermeidet voreilige Investitionen.",
                "bottleneck_coverage": "Bottleneck bleibt zunächst bestehen.",
                "data_requirements": "Weitere Beobachtungsdaten.",
                "application_impact": "Keine.",
                "integration_impact": "Keine.",
                "risks": "Bestehende Verzögerungen bleiben bestehen.",
                "architecture_fit": "Explizite Status-quo-Alternative.",
                "non_ai": True,
                "status_quo": True,
            },
        ],
        "recommendation": {
            "summary": "Organisatorische Stabilisierung fachlich prüfen.",
            "rationale": "Die verfügbare Evidenz stützt diese Richtung stärker als Status quo.",
            "references": [ref],
        },
        "risks_unknowns": [
            "Die Stichprobe ist klein.",
            "Die beobachtete Differenz beweist keine Kausalität.",
        ],
        "validation_step": {
            "step": "Vertretungsregel in einem begrenzten Pilotzeitraum prüfen.",
            "measurement": "Durchlaufzeit vor und nach der Änderung vergleichen.",
        },
    }


@pytest.mark.django_db
def test_real_evidence_and_fixed_runs_require_persistent_campaign(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(
        owner=owner,
        process=process,
        root=tmp_path,
    )

    with pytest.raises(InvestigationRunError) as exc_info:
        start_investigation(
            actor=owner,
            request=StartInvestigationRequest(
                snapshot_id=snapshot.snapshot_id,
                idempotency_key="real-without-budget",
                execution_mode="adaptive",
                evidence_metadata={
                    "provider_mode": "real",
                    "phase": "scored",
                    "variant": "A",
                },
                decision_brief_required=True,
            ),
        )
    assert exc_info.value.code == "evidence_budget_required"

    with pytest.raises(InvestigationRunError) as exc_info:
        start_investigation(
            actor=owner,
            request=StartInvestigationRequest(
                snapshot_id=snapshot.snapshot_id,
                idempotency_key="fixed-without-budget",
                execution_mode="fixed",
                decision_brief_required=True,
            ),
        )
    assert exc_info.value.code == "evidence_budget_required"
    assert InvestigationRun.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_campaign_reservation_is_atomic_for_parallel_provider_attempts(
    owner,
    business_unit,
    tmp_path,
):
    if connection.vendor != "postgresql":
        pytest.skip("Parallel budget row locking is validated on PostgreSQL.")

    process = make_process(owner=owner, business_unit=business_unit, name="Budget parallel")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(
        owner=owner,
        process=process,
        max_calls=1,
        input_tokens=1_000,
        output_tokens=1_000,
    )
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="parallel-budget",
            evidence_campaign_id=campaign.pk,
            evidence_metadata={"provider_mode": "real", "phase": "scored", "variant": "A"},
            decision_brief_required=True,
        ),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    calls = [model_call(run, "a"), model_call(run, "b")]
    barrier = Barrier(2)

    def attempt(call_id):
        close_old_connections()
        barrier.wait()
        try:
            reserve_provider_attempt(
                run_id=run.pk,
                model_call_id=call_id,
                max_input_tokens=100,
                max_output_tokens=100,
            )
            return "reserved"
        except InvestigationRunError as exc:
            return exc.code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [call.pk for call in calls]))

    assert results.count("reserved") == 1
    assert results.count("evidence_budget_exhausted") == 1
    campaign.refresh_from_db()
    assert campaign.usage["provider_calls"] == 1
    assert campaign.usage["reserved_input_tokens"] == 100
    assert campaign.usage["reserved_output_tokens"] == 100
    assert InvestigationProviderReservation.objects.count() == 1


@pytest.mark.django_db
def test_unknown_provider_usage_remains_reserved_and_continuation_keeps_history(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Budget uncertain")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(
        owner=owner,
        process=process,
        max_calls=2,
        input_tokens=1_000,
        output_tokens=1_000,
    )
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="uncertain-budget",
            evidence_campaign_id=campaign.pk,
            evidence_metadata={"provider_mode": "real", "phase": "calibration", "variant": "A"},
            decision_brief_required=True,
        ),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    call = model_call(run, "c")
    reservation = reserve_provider_attempt(
        run_id=run.pk,
        model_call_id=call.pk,
        max_input_tokens=100,
        max_output_tokens=100,
    )
    assert reservation is not None

    mark_provider_attempt_uncertain(
        reservation_id=reservation.pk,
        reason="timeout",
    )
    reservation.refresh_from_db()
    campaign.refresh_from_db()
    assert reservation.status == InvestigationProviderReservation.Status.UNCERTAIN
    assert campaign.usage["provider_calls"] == 1
    assert campaign.usage["reserved_input_tokens"] == 100
    assert campaign.usage["reserved_output_tokens"] == 100
    assert campaign.usage["uncertain_attempts"] == 1

    reloaded = type(campaign).objects.get(pk=campaign.pk)
    assert reloaded.usage == campaign.usage

    second_call = model_call(run, "d")
    with pytest.raises(InvestigationRunError) as exc_info:
        reserve_provider_attempt(
            run_id=run.pk,
            model_call_id=second_call.pk,
            max_input_tokens=901,
            max_output_tokens=100,
        )
    assert exc_info.value.code == "evidence_budget_exhausted"

    before_usage = dict(campaign.usage)
    campaign = authorize_campaign_continuation(
        actor=owner,
        campaign_id=campaign.pk,
        limits={
            "max_provider_calls": 3,
            "max_input_tokens": 2_000,
            "max_output_tokens": 2_000,
        },
        reason="Explizit autorisierte Fortsetzung nach dokumentiertem Timeout.",
    )
    assert campaign.revision == 2
    assert campaign.usage == before_usage
    revisions = list(campaign.budget_revisions.order_by("revision"))
    assert [item.revision for item in revisions] == [1, 2]
    assert revisions[1].usage_at_authorization == before_usage


@pytest.mark.django_db
def test_variant_b_missing_denominator_stays_human_clarification(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Variante B")
    (tmp_path / "01_case_note.md").write_text(
        "Die Gesamtzahl aller freigabepflichtigen Vorgänge ist nicht dokumentiert.",
        encoding="utf-8",
    )
    (tmp_path / "02_report.md").write_text(
        "Es wurden 18 Eskalationen dokumentiert; die Bezugsgröße fehlt.",
        encoding="utf-8",
    )
    (tmp_path / "cases.csv").write_text(
        "period,escalations,total_eligible,unit\n"
        "2026-06,5,,cases\n"
        "2026-07,7,,cases\n"
        "2026-08,6,,cases\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="variant-b",
            decision_brief_required=True,
        ),
    )
    csv_source = InvestigationSource.objects.get(
        snapshot_id=snapshot.snapshot_id,
        filename="cases.csv",
    )
    step = execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="profile_csv",
        parameters={"source_id": str(csv_source.pk)},
        target_claim_id="critical-denominator",
    )
    assert step.result_payload["columns"]["total_eligible"]["missing"] == 3
    assert step.result_payload["columns"]["total_eligible"]["type"] == "empty"

    run = InvestigationRun.objects.get(pk=handle.run_id)
    decision = evaluate_run_policy(run, external_critical_gap=True)
    assert decision.outcome == PolicyOutcome.HUMAN_CLARIFICATION
    assert decision.reason_code == ReasonCode.MISSING_EVIDENCE
    assert decision.outcome != PolicyOutcome.READY_FOR_DECISION


@pytest.mark.django_db
def test_future_validation_plan_and_open_options_do_not_block_pre_verifier(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="A23 regression")
    (tmp_path / "cases.csv").write_text(
        "group,value,unit\nA,10,h\nA,20,h\nB,30,h\nB,40,h\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="a23-validation-regression",
            decision_brief_required=True,
        ),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    source = InvestigationSource.objects.get(
        snapshot_id=snapshot.snapshot_id,
        filename="cases.csv",
    )
    calculation = execute_tool_step(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(source.pk),
            "group_by": "group",
            "aggregation": "mean",
            "value_column": "value",
            "filters": [],
            "unit_column": "unit",
        },
        target_claim_id="hyp-a",
    )
    execute_tool_step(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        tool_name="search_sources",
        parameters={"query": "counter-never-present", "cursor": 0, "limit": 20},
        target_claim_id="hyp-b",
    )
    ref = source_reference(source, row=1, column="group")
    claims = (
        {
            "claim_id": "problem",
            "statement": "problem",
            "area": "problem_context",
            "claim_kind": "fact",
            "critical": True,
            "status": "supported",
            "evidence_refs": [ref],
        },
        {
            "claim_id": "hyp-a",
            "statement": "hyp-a",
            "area": "competing_hypotheses",
            "claim_kind": "hypothesis",
            "critical": True,
            "status": "supported",
            "evidence_refs": [ref],
        },
        {
            "claim_id": "hyp-b",
            "statement": "hyp-b",
            "area": "competing_hypotheses",
            "claim_kind": "hypothesis",
            "critical": True,
            "status": "refuted",
            "counterevidence_refs": [ref],
        },
        {
            "claim_id": "recommendation",
            "statement": "recommendation",
            "area": "recommendation_validation",
            "claim_kind": "recommendation",
            "critical": True,
            "status": "supported",
            "evidence_refs": [ref],
        },
        {
            "claim_id": "candidate-option",
            "statement": "candidate-option",
            "area": "solution_options",
            "claim_kind": "option",
            "critical": True,
            "status": "open",
        },
        {
            "claim_id": "future-validation",
            "statement": "future-validation",
            "area": "recommendation_validation",
            "claim_kind": "validation",
            "critical": True,
            "status": "open",
        },
    )
    brief = full_brief(
        run=run,
        source=source,
        result_id=calculation.result_ref["tool_result_id"],
    )
    apply_planner_state(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        claim_register=claims,
        brief_payload=brief,
        progress_kind="evidence",
        progress_payload={"coverage_change": True},
    )
    set_source_relevance(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        relevance={
            str(source.pk): {
                "relevant": True,
                "reason": "CSV enthält Problem-, Hypothesen- und Berechnungsbelege.",
                "reference": ref,
            }
        },
    )
    run.refresh_from_db()

    assert pre_verifier_blockers_for_run(run) == ()
    decision = evaluate_run_policy(run)
    assert decision.outcome == PolicyOutcome.CONTINUE
    assert decision.blockers == ("verifier_missing",)
    assert brief["validation_step"]["step"]
    assert "critical_unresolved:candidate-option" not in decision.blockers
    assert "critical_unresolved:future-validation" not in decision.blockers


@pytest.mark.django_db
def test_materialization_preview_is_read_only_and_describes_domain_changes(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Preview")
    (tmp_path / "cases.csv").write_text(
        "group,value,unit\nA,10,h\nA,20,h\nB,30,h\nB,40,h\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="materialize-preview",
            decision_brief_required=True,
        ),
    )
    source = InvestigationSource.objects.get(
        snapshot_id=snapshot.snapshot_id,
        filename="cases.csv",
    )
    step = execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(source.pk),
            "group_by": "group",
            "aggregation": "mean",
            "value_column": "value",
            "filters": [],
            "unit_column": "unit",
        },
        target_claim_id="calculation",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    payload = full_brief(
        run=run,
        source=source,
        result_id=step.result_ref["tool_result_id"],
    )
    InvestigationRun.objects.filter(pk=run.pk).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
        brief_payload=payload,
        brief_hash=content_hash(payload),
    )
    before_version = process.version

    preview = preview_decision_brief_materialization(actor=owner, run_id=run.pk)

    process.refresh_from_db()
    assert process.version == before_version
    assert process.solution_options.count() == 0
    assert {item["label"] for item in preview["process_changes"]} == {
        "Beobachtung / Problem",
        "Ursachenhypothesen",
        "Baseline und Kennzahlen",
    }
    assert [item["action"] for item in preview["solution_changes"]] == ["create", "create"]
    assert preview["conflicts"] == []


@pytest.mark.django_db
def test_materialization_ui_requires_confirmation_and_redirects_to_existing_comparison(
    client,
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Safe handoff")
    (tmp_path / "cases.csv").write_text(
        "group,value,unit\nA,10,h\nA,20,h\nB,30,h\nB,40,h\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="materialize-ui-confirm",
            decision_brief_required=True,
        ),
    )
    source = InvestigationSource.objects.get(
        snapshot_id=snapshot.snapshot_id,
        filename="cases.csv",
    )
    step = execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(source.pk),
            "group_by": "group",
            "aggregation": "mean",
            "value_column": "value",
            "filters": [],
            "unit_column": "unit",
        },
        target_claim_id="calculation",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    payload = full_brief(
        run=run,
        source=source,
        result_id=step.result_ref["tool_result_id"],
    )
    InvestigationRun.objects.filter(pk=run.pk).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
        brief_payload=payload,
        brief_hash=content_hash(payload),
    )
    client.force_login(owner)
    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_views.evaluate_run_policy",
        lambda _run: PolicyDecision(PolicyOutcome.READY_FOR_DECISION, None, ()),
    )
    materialize_url = reverse("accelerator:investigation_materialize", args=[run.pk])

    response = client.post(materialize_url, {"operation_key": "ui-safe-handoff"})
    assert response.status_code == 302
    assert process.solution_options.count() == 0
    assert run.materializations.count() == 0

    response = client.post(
        materialize_url,
        {
            "operation_key": "ui-safe-handoff",
            "confirm_materialization": "yes",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("architecture:solution_option_compare", args=[process.pk])
    assert process.solution_options.count() == 2
    assert run.materializations.count() == 1

    process.refresh_from_db()
    assert "Durch Evidenz gestützt:" in process.cause_hypotheses
    assert "Durch Evidenz nicht gestützt:" in process.cause_hypotheses
    assert "[supported]" not in process.cause_hypotheses
    assert "[refuted]" not in process.cause_hypotheses
    assert "Datenbasis: 4 Datensätze" in process.baseline_metrics
    assert "Aussagegrenze: Kleine synthetische Stichprobe" in process.baseline_metrics
    assert "tool-result:" not in process.baseline_metrics
    assert "source-sha256:" not in process.baseline_metrics

    process_page = client.get(process.get_absolute_url())
    process_body = process_page.content.decode()
    assert process_page.status_code == 200
    assert 'data-testid="process-decision-surface"' in process_body
    assert process_body.index("1 · Situation") < process_body.index("2 · Wichtigster Befund")
    assert process_body.index("2 · Wichtigster Befund") < process_body.index(
        "3 · Evidenzbasierte Empfehlung"
    )
    assert process_body.index("3 · Evidenzbasierte Empfehlung") < process_body.index(
        "4 · Nächster Schritt"
    )
    assert payload["recommendation"]["summary"] in process_body
    assert "setzt keine bevorzugte Lösungsoption" in process_body
    assert "Rohdaten und Herkunft anzeigen" in process_body

    comparison = client.get(response.url)
    body = comparison.content.decode()
    assert comparison.status_code == 200
    assert "Letzte evidenzgestützte Übernahme" in body
    assert reverse("accelerator:investigation_detail", args=[run.pk]) in body

    detail = client.get(reverse("accelerator:investigation_detail", args=[run.pk]))
    detail_body = detail.content.decode()
    assert detail.status_code == 200
    assert "Lösungsoptionen fachlich vergleichen" in detail_body
    assert reverse("architecture:solution_option_compare", args=[process.pk]) in detail_body


@pytest.mark.django_db
def test_human_solution_option_change_is_reported_not_overwritten(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Conflict")
    existing = SolutionOption.objects.create(
        process_analysis=process,
        name="Freigabe organisatorisch stabilisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        description="Menschlicher Ausgangsentwurf.",
        expected_value="Wartezeit reduzieren.",
        created_by=owner,
    )
    (tmp_path / "cases.csv").write_text(
        "group,value,unit\nA,10,h\nA,20,h\nB,30,h\nB,40,h\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="materialize-conflict",
            decision_brief_required=True,
        ),
    )
    source = InvestigationSource.objects.get(
        snapshot_id=snapshot.snapshot_id,
        filename="cases.csv",
    )
    step = execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(source.pk),
            "group_by": "group",
            "aggregation": "mean",
            "value_column": "value",
            "filters": [],
            "unit_column": "unit",
        },
        target_claim_id="calculation",
    )
    payload = full_brief(
        run=InvestigationRun.objects.get(pk=handle.run_id),
        source=source,
        result_id=step.result_ref["tool_result_id"],
        existing_option_id=existing.pk,
    )
    InvestigationRun.objects.filter(pk=handle.run_id).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
        brief_payload=payload,
        brief_hash=content_hash(payload),
    )

    existing.description = "Vom Menschen nach dem Run bewusst geändert."
    existing.save()

    preview = preview_decision_brief_materialization(
        actor=owner,
        run_id=handle.run_id,
    )
    assert any(item["type"] == "solution_option_changed" for item in preview["conflicts"])
    assert not any(
        item.get("option_id") == str(existing.pk) for item in preview["solution_changes"]
    )

    result = materialize_decision_brief(
        actor=owner,
        run_id=handle.run_id,
        operation_key="materialize-once",
    )
    existing.refresh_from_db()
    process.refresh_from_db()
    assert result.outcome == result.Outcome.CONFLICT
    assert any(item["type"] == "solution_option_changed" for item in result.conflicts)
    assert existing.description == "Vom Menschen nach dem Run bewusst geändert."
    assert process.confirmed_causes == ""
    assert not process.solution_options.filter(
        recommendation=SolutionOption.Recommendation.PREFERRED
    ).exists()
    created = process.solution_options.exclude(pk=existing.pk).get(name="Status quo beibehalten")
    assert created.recommendation == SolutionOption.Recommendation.CANDIDATE
    assert created.evaluation_status == SolutionOption.EvaluationStatus.DRAFT

    retry = materialize_decision_brief(
        actor=owner,
        run_id=handle.run_id,
        operation_key="materialize-once",
    )
    assert retry.pk == result.pk


@pytest.mark.django_db
def test_architecture_adoption_rechecks_permission(owner, reader, business_unit):
    process = make_process(owner=owner, business_unit=business_unit, name="Boundary permission")

    with pytest.raises(InvestigationDraftAdoptionError) as exc_info:
        preview_investigation_draft_adoption(
            actor=reader,
            process_analysis_id=process.pk,
            expected_process_version=process.version,
            base_process={"diagnostic_observations": process.diagnostic_observations},
            base_options={},
            process_fields={"diagnostic_observations": "Neuer belegter Befund."},
            solution_proposals=[],
        )

    assert exc_info.value.code == "architecture_edit_forbidden"


@pytest.mark.django_db
def test_architecture_adoption_preserves_process_revalidation_semantics(owner, business_unit):
    process = make_process(owner=owner, business_unit=business_unit, name="Revalidation")
    process.status = ProcessAnalysis.Status.VALIDATED
    process.save(update_fields=["status", "updated_at"])
    ProcessValidation.objects.create(
        process_analysis=process,
        process_version=process.version,
        validated_by=owner,
        validator_role="Business Owner",
        note="Ausgangsstand geprüft.",
    )
    base_value = process.diagnostic_observations

    preview = preview_investigation_draft_adoption(
        actor=owner,
        process_analysis_id=process.pk,
        expected_process_version=process.version,
        base_process={"diagnostic_observations": base_value},
        base_options={},
        process_fields={"diagnostic_observations": "Neue evidenzgestützte Beobachtung."},
        solution_proposals=[],
    )
    assert preview["side_effects"] == [
        {
            "type": "process_revalidation_required",
            "label": "Prozessvalidierung",
            "description": (
                "Die aktuelle Validierung wird durch die Prozessänderung prüfbedürftig; "
                "die neue Prozessversion muss erneut validiert werden."
            ),
        }
    ]

    result = adopt_investigation_drafts(
        actor=owner,
        process_analysis_id=process.pk,
        expected_process_version=process.version,
        base_process={"diagnostic_observations": base_value},
        base_options={},
        process_fields={"diagnostic_observations": "Neue evidenzgestützte Beobachtung."},
        solution_proposals=[],
    )

    process.refresh_from_db()
    assert result.applied_fields == {
        "diagnostic_observations": "Neue evidenzgestützte Beobachtung."
    }
    assert process.version == 2
    assert process.status == ProcessAnalysis.Status.REVIEW_REQUIRED


@pytest.mark.django_db
def test_architecture_adoption_rejects_red_solution_state_fields(owner, business_unit):
    process = make_process(owner=owner, business_unit=business_unit, name="Red fields")

    with pytest.raises(InvestigationDraftAdoptionError) as exc_info:
        preview_investigation_draft_adoption(
            actor=owner,
            process_analysis_id=process.pk,
            expected_process_version=process.version,
            base_process={},
            base_options={},
            process_fields={},
            solution_proposals=[
                {
                    "name": "Unzulässiger Vorschlag",
                    "option_type": SolutionOption.OptionType.ORGANIZATIONAL,
                    "recommendation": SolutionOption.Recommendation.PREFERRED,
                }
            ],
        )

    assert exc_info.value.code == "unsupported_solution_fields"


@pytest.mark.django_db
def test_architecture_adoption_never_resets_decided_solution_option(owner, business_unit):
    process = make_process(owner=owner, business_unit=business_unit, name="Decision boundary")
    option = SolutionOption.objects.create(
        process_analysis=process,
        created_by=owner,
        name="Bestehende Option",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        description="Menschlicher Entwurf.",
        expected_value="Nutzenhypothese.",
    )
    base_updated_at = option.updated_at.isoformat()
    SolutionOption.objects.filter(pk=option.pk).update(
        recommendation=SolutionOption.Recommendation.REJECTED
    )

    proposal = {
        "existing_option_id": str(option.pk),
        "name": "Bestehende Option",
        "option_type": SolutionOption.OptionType.ORGANIZATIONAL,
        "description": "Agentisch geänderter Entwurf.",
        "expected_value": "Neue Nutzenhypothese.",
        "bottleneck_coverage": "",
        "data_requirements": "",
        "application_impact": "",
        "integration_impact": "",
        "risks": "",
        "architecture_fit": "",
        "evidence_basis": option.evidence_basis,
    }
    kwargs = {
        "actor": owner,
        "process_analysis_id": process.pk,
        "expected_process_version": process.version,
        "base_process": {},
        "base_options": {
            str(option.pk): {
                "id": str(option.pk),
                "updated_at": base_updated_at,
            }
        },
        "process_fields": {},
        "solution_proposals": [proposal],
    }

    preview = preview_investigation_draft_adoption(**kwargs)
    assert [item["type"] for item in preview["conflicts"]] == ["solution_option_decision_changed"]
    assert preview["solution_changes"] == []

    result = adopt_investigation_drafts(**kwargs)
    option.refresh_from_db()
    assert [item["type"] for item in result.conflicts] == ["solution_option_decision_changed"]
    assert option.recommendation == SolutionOption.Recommendation.REJECTED
    assert option.description == "Menschlicher Entwurf."


@pytest.mark.django_db
def test_fixed_and_adaptive_arms_share_execution_contract(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Comparison")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process)

    fixed_handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="fixed-arm",
            evidence_campaign_id=campaign.pk,
            execution_mode="fixed",
            evidence_metadata={"provider_mode": "stub", "phase": "comparison", "variant": "A"},
            decision_brief_required=True,
        ),
    )
    fixed = InvestigationRun.objects.get(pk=fixed_handle.run_id)
    abort_investigation(actor=owner, run_id=fixed.pk)

    adaptive_handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="adaptive-arm",
            evidence_campaign_id=campaign.pk,
            execution_mode="adaptive",
            evidence_metadata={"provider_mode": "stub", "phase": "comparison", "variant": "A"},
            decision_brief_required=True,
        ),
    )
    adaptive = InvestigationRun.objects.get(pk=adaptive_handle.run_id)
    fixed.refresh_from_db()
    assert_comparable_runs(fixed=fixed, adaptive=adaptive)
    assert ISSUE4_INVESTIGATION_PROVIDER_POLICY == {
        "zdr": True,
        "data_collection": "deny",
        "order": ["deepinfra/fp8"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert fixed.execution_snapshot["model_transport"]["provider_policy"] == (
        ISSUE4_INVESTIGATION_PROVIDER_POLICY
    )
    assert comparison_contract(fixed)["model_transport"]["provider_policy"] == (
        ISSUE4_INVESTIGATION_PROVIDER_POLICY
    )
    assert fixed.execution_snapshot["model_transport"]["endpoint_capability"] == {
        "version": "vs1-openrouter-deepinfra-fp8-v3",
        "model": "deepseek/deepseek-v4.1-flash",
        "provider": "deepinfra/fp8",
        "context_tokens": 1_048_576,
        "completion_tokens": 131_072,
    }

    changed = dict(adaptive.execution_snapshot)
    transport = dict(changed["model_transport"])
    provider_policy = dict(transport["provider_policy"])
    provider_policy["allow_fallbacks"] = True
    transport["provider_policy"] = provider_policy
    changed["model_transport"] = transport
    InvestigationRun.objects.filter(pk=adaptive.pk).update(execution_snapshot=changed)
    adaptive.refresh_from_db()
    with pytest.raises(InvestigationRunError) as exc_info:
        assert_comparable_runs(fixed=fixed, adaptive=adaptive)
    assert exc_info.value.code == "comparison_contract_mismatch"


@pytest.mark.django_db
def test_fixed_route_boundary_is_not_reported_as_missing_evidence(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Fixed boundary")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="fixed-boundary-reason",
            evidence_campaign_id=campaign.pk,
            execution_mode="fixed",
            evidence_metadata={"provider_mode": "stub", "phase": "comparison", "variant": "B"},
            decision_brief_required=True,
        ),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    tool_action = PlannerAction(
        action="tool",
        target_claim_id="claim-1",
        expected_discriminating_finding="Weitere adaptive Prüfung.",
        rationale="Noch ein Werkzeug wäre hilfreich.",
        tool_name="search_sources",
        parameters={"query": "weitere Evidenz", "cursor": 0, "limit": 20},
        claim_register=(),
        brief_payload={},
        source_relevance={},
        progress_kind="",
        progress_payload={},
        clarification_reason="",
        clarification_payload={},
    )
    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_benchmark.request_planner_action",
        lambda **_kwargs: tool_action,
    )

    action = request_fixed_route_synthesis(
        actor=owner,
        run=run,
        executor_token=handle.executor_token,
    )

    assert action.action == "clarify"
    assert action.clarification_reason == ReasonCode.FIXED_ROUTE_BOUNDARY.value
    assert action.clarification_reason != ReasonCode.MISSING_EVIDENCE.value


@pytest.mark.django_db
def test_fixed_route_reads_full_small_pack_and_profiles_missing_denominator(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Fixed B")
    (tmp_path / "01_case_note.md").write_text(
        "Die Bezugsgröße ist nicht dokumentiert.",
        encoding="utf-8",
    )
    (tmp_path / "02_report.md").write_text(
        "18 Eskalationen; Gesamtzahl nicht verfügbar.",
        encoding="utf-8",
    )
    (tmp_path / "cases.csv").write_text(
        "period,escalations,total_eligible,unit\n"
        "2026-06,5,,cases\n"
        "2026-07,7,,cases\n"
        "2026-08,6,,cases\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="fixed-b",
            evidence_campaign_id=campaign.pk,
            execution_mode="fixed",
            evidence_metadata={"provider_mode": "stub", "phase": "comparison", "variant": "B"},
            decision_brief_required=True,
        ),
    )

    run = prepare_fixed_route(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
    )
    assert run.execution_snapshot["fixed_route_version"] == "vs1-fixed-route-v1"
    assert run.steps.filter(tool_name="read_source", status="success").count() == 3
    profile = run.steps.get(tool_name="profile_csv", status="success")
    assert profile.result_payload["columns"]["total_eligible"]["missing"] == 3
    assert profile.result_payload["columns"]["total_eligible"]["type"] == "empty"
    assert run.counterevidence_search_executed is True
    assert run.counterevidence_hits_processed is True
    assert run.source_relevance_complete is True


@pytest.mark.django_db
def test_incomplete_campaign_report_never_claims_effectiveness_or_ten_x(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Report")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, _snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process)

    report = evidence_campaign_report(campaign)
    assert report["nine_real_adaptive_runs_complete"] is False
    assert report["fixed_comparison_present"] is False
    assert report["effectiveness_proof_complete"] is False
    assert report["ten_x_claim_allowed"] is False
    assert report["human_active_time_seconds"] is None
    assert report["independent_human_review"] == "not_recorded"
    assert any("A:" in item for item in report["outstanding_requirements"])


@pytest.mark.django_db
def test_process_workspace_authorizes_visible_source_and_budget_then_starts(
    client,
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit, name="UI Start")
    (tmp_path / "notes.txt").write_text("Beleg für den Fall.", encoding="utf-8")
    folder = InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name="Registrierter Fallordner",
        root_path=str(tmp_path),
        registered_by=owner,
    )
    client.force_login(owner)

    authorize_url = reverse(
        "accelerator:investigation_authorize",
        args=[process.pk],
    )
    response = client.get(authorize_url)
    assert response.status_code == 200
    assert "Feste Run-Limits" in response.content.decode()
    assert "max_model_calls" in response.content.decode()
    assert "Einzeldateien oder Werkzeuge werden nicht manuell ausgewählt" in (
        response.content.decode()
    )

    question = "Welche Ursache und Lösungsrichtung ist durch die Evidenz gestützt?"
    response = client.post(
        authorize_url,
        {
            "folder_id": str(folder.pk),
            "decision_question": question,
        },
    )
    assert response.status_code == 302

    snapshot = process.investigation_source_snapshots.get()
    assert snapshot.folder_id == folder.pk
    assert snapshot.decision_question == question
    assert snapshot.run_limits == {}
    assert snapshot.sources.count() == 1

    detail = client.get(process.get_absolute_url())
    body = detail.content.decode()
    assert detail.status_code == 200
    assert "Autorisierter Quellenstand" in body
    assert "max_model_calls" in body
    assert "Untersuchung starten" in body

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_views.run_until_boundary",
        lambda **_kwargs: None,
    )
    start_url = reverse(
        "accelerator:investigation_start",
        args=[process.pk],
    )
    response = client.post(
        start_url,
        {"idempotency_key": "ui-no-file-selection"},
    )
    assert response.status_code == 302
    run = process.investigation_runs.get()
    assert run.source_snapshot_id == snapshot.pk
    assert run.execution_snapshot["decision_brief_required"] is True
    assert run.status == InvestigationRun.Status.RUNNING


@pytest.mark.django_db
def test_investigation_read_only_views_do_not_require_transaction(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Read only UI")
    (tmp_path / "notes.txt").write_text("Beleg für die Detailansicht.", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="read-only-investigation-view",
        ),
    )
    source = InvestigationSource.objects.get(snapshot_id=snapshot.snapshot_id)
    run = InvestigationRun.objects.get(pk=handle.run_id)
    run.brief_payload = full_brief(
        run=run,
        source=source,
        result_id=uuid.uuid4(),
    )
    run.save(update_fields=["brief_payload"])
    client.force_login(owner)

    detail = client.get(reverse("accelerator:investigation_detail", args=[handle.run_id]))
    assert detail.status_code == 200
    detail_body = detail.content.decode()
    assert "Konkurrierende Ursachen" in detail_body
    assert str(source.pk) in detail_body

    source_detail = client.get(
        reverse("accelerator:investigation_source", args=[handle.run_id, source.pk])
    )
    assert source_detail.status_code == 200


@pytest.mark.django_db
def test_decision_surface_prioritizes_human_decision_over_technical_audit(
    client,
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Human decision surface")
    (tmp_path / "cases.csv").write_text(
        "approver_available,approval_hours,unit\nyes,5,h\nyes,5,h\nno,29,h\nno,30,h\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="human-decision-surface",
            decision_brief_required=True,
        ),
    )
    source = InvestigationSource.objects.get(
        snapshot_id=snapshot.snapshot_id,
        filename="cases.csv",
    )
    step = execute_tool_step(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(source.pk),
            "group_by": "approver_available",
            "aggregation": "mean",
            "value_column": "approval_hours",
            "filters": [],
            "unit_column": "unit",
        },
        target_claim_id="approval-delay",
        expected_discriminating_finding=(
            "Unterscheidet sich approval_hours nach approver_available?"
        ),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    payload = full_brief(
        run=run,
        source=source,
        result_id=step.result_ref["tool_result_id"],
    )
    payload["recommendation"]["rationale"] = (
        "compare_groups zeigt höhere approval_hours nach approver_available; "
        "profile_csv bestätigt die Datengrundlage."
    )
    payload["calculations"][0] = {
        "summary": (
            "Mittlere approval_hours nach approver_available unterscheidet sich "
            "zwischen den Gruppen."
        ),
        "reference": {
            "tool_result_id": str(step.result_ref["tool_result_id"]),
            "revision_hash": source.content_sha256,
        },
        "population": {
            "rows_total": 4,
            "included_rows": [1, 2, 3, 4],
            "aggregated_rows": [1, 2, 3, 4],
            "filter_matched_rows": 4,
        },
        "limits": "Kleine Stichprobe; keine Kausalitätsaussage.",
    }
    brief_hash = content_hash(payload)
    InvestigationRun.objects.filter(pk=run.pk).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
        brief_payload=payload,
        brief_hash=brief_hash,
    )
    client.force_login(owner)
    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_views.evaluate_run_policy",
        lambda _run: PolicyDecision(PolicyOutcome.READY_FOR_DECISION, None, ()),
    )
    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_views.preview_decision_brief_materialization",
        lambda **_kwargs: {
            "process_changes": [
                {
                    "label": "Beobachtung / Problem",
                    "current": "Laufzeiten schwanken",
                    "proposed": "Freigabezeiten schwanken deutlich.",
                }
            ],
            "solution_changes": [],
            "conflicts": [],
            "side_effects": [],
        },
    )

    response = client.get(reverse("accelerator:investigation_detail", args=[run.pk]))
    body = response.content.decode()

    assert response.status_code == 200
    assert body.index("1 · Situation") < body.index("2 · Wichtigster Befund")
    assert body.index("2 · Wichtigster Befund") < body.index("3 · Empfehlung")
    assert body.index("3 · Empfehlung") < body.index("4 · Nächster Schritt")
    assert "Entscheidungsgrundlage bereit" in body
    assert "READY_FOR_DECISION" not in body
    assert "Durch aktuelle Evidenz gestützt" in body
    assert "Gegenbeleg vorhanden" in body
    assert "Freigabedauer (Stunden)" in body
    assert "Freigeber verfügbar" in body
    assert "Begründung" in body
    assert (
        "Gruppenvergleich zeigt höhere Freigabedauer (Stunden) nach Freigeber verfügbar; "
        "Datenprüfung bestätigt die Datengrundlage." in body
    )
    assert "compare_groups zeigt höhere approval_hours" not in body
    assert "approval_hours" not in body
    assert "approver_available" not in body
    assert "Prozessanalyse öffnen" in body
    assert "Population: {" not in body
    assert "coverage_change" not in body
    assert "Gruppenvergleich reproduzierbar berechnet" in body
    assert reverse("accelerator:investigation_source", args=[run.pk, source.pk]) in body
    assert (
        reverse(
            "accelerator:investigation_tool_result",
            args=[run.pk, step.result_ref["tool_result_id"]],
        )
        in body
    )

    stored_run = InvestigationRun.objects.get(pk=run.pk)
    revision = InvestigationBriefRevision.objects.create(
        run=stored_run,
        revision=1,
        payload=stored_run.brief_payload,
        content_hash=stored_run.brief_hash,
        operation_key="decision-surface-render-check",
        process_version=stored_run.process_version,
    )
    export_body = render_decision_brief_markdown(revision)
    assert payload["recommendation"]["summary"] in body
    assert payload["recommendation"]["summary"] in export_body
    assert brief_hash == stored_run.brief_hash

    process_page = client.get(process.get_absolute_url())
    process_body = process_page.content.decode()
    assert process_page.status_code == 200
    assert "Prozessanalyse ·" in process_body
    assert "Decision Brief öffnen" in process_body
    assert reverse("accelerator:investigation_detail", args=[run.pk]) in process_body


@pytest.mark.django_db
def test_ready_run_with_current_policy_blockers_is_not_presented_as_decision_ready(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Stale ready")
    (tmp_path / "notes.txt").write_text("Unvollständiger Stand.", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="stale-ready-surface",
            decision_brief_required=True,
        ),
    )
    InvestigationRun.objects.filter(pk=handle.run_id).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
    )
    client.force_login(owner)

    response = client.get(reverse("accelerator:investigation_detail", args=[handle.run_id]))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Entscheidungsgrundlage noch unvollständig" in body
    assert "Noch keine belastbare Empfehlung aus diesem Lauf." in body
    assert "Entscheidungsgrundlage bereit" not in body
    assert "Lösungsoptionen fachlich vergleichen" not in body
    assert "Geplante Übernahme in den Lösungsraum prüfen" not in body

    response = client.post(
        reverse("accelerator:investigation_materialize", args=[handle.run_id]),
        {
            "operation_key": "stale-ready-must-not-materialize",
            "confirm_materialization": "yes",
        },
    )
    assert response.status_code == 302
    assert InvestigationRun.objects.get(pk=handle.run_id).materializations.count() == 0
    assert process.solution_options.count() == 0


@pytest.mark.django_db
def test_aborted_clarification_is_presented_as_open_evidence_question(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Aborted clarification")
    process.diagnostic_observations = (
        "18 Eskalationen sollen eingeordnet werden, um eine belastbare Lösungsrichtung abzuleiten."
    )
    process.save(update_fields=["diagnostic_observations", "updated_at"])
    (tmp_path / "notes.txt").write_text("Bezugsgröße fehlt.", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="aborted-clarification-surface",
        ),
    )
    InvestigationRun.objects.filter(pk=handle.run_id).update(
        status=InvestigationRun.Status.ABORTED,
        clarification_reason=ReasonCode.MISSING_EVIDENCE.value,
        clarification_payload={
            "question": "Wie hoch war die Gesamtzahl aller freigabepflichtigen Vorgänge?",
            "impact": (
                "Ohne diese Bezugsgröße kann keine belastbare Eskalationsquote berechnet werden."
            ),
            "needed_evidence": (
                "Dokumentierte Gesamtzahl im gleichen Zeitraum wie die 18 Eskalationen."
            ),
        },
        finished_at=timezone.now(),
    )
    process.diagnostic_observations = "Später durch einen anderen Run veränderter Prozessbefund."
    process.save(update_fields=["diagnostic_observations", "updated_at"])
    client.force_login(owner)

    response = client.get(reverse("accelerator:investigation_detail", args=[handle.run_id]))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Untersuchung beendet" in body
    assert body.count("Der Lauf wurde beendet.") == 1
    assert (
        "18 Eskalationen sollen eingeordnet werden, um eine belastbare Lösungsrichtung abzuleiten."
        in body
    )
    assert "Später durch einen anderen Run veränderter Prozessbefund." not in body
    assert "Fragestellung: Welche Lösungsrichtung ist durch die Evidenz gestützt?" in body
    assert (
        "Entscheidungskritischer Nachweis fehlt: Dokumentierte Gesamtzahl im gleichen "
        "Zeitraum wie die 18 Eskalationen." in body
    )
    assert "Noch keine belastbare Empfehlung aus diesem Lauf." in body
    assert "Wie hoch war die Gesamtzahl aller freigabepflichtigen Vorgänge?" in body
    assert "Fehlenden Nachweis ergänzen und Untersuchung neu starten" in body
    assert 'name="answer"' not in body
    assert process.get_absolute_url() in body


@pytest.mark.django_db
def test_waiting_human_surface_uses_real_continue_contract(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Clarification")
    (tmp_path / "notes.txt").write_text("Bezugsgröße fehlt.", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="waiting-human-surface",
        ),
    )
    InvestigationRun.objects.filter(pk=handle.run_id).update(
        status=InvestigationRun.Status.WAITING_HUMAN,
        clarification_reason=ReasonCode.MISSING_EVIDENCE.value,
        clarification_payload={
            "question": "Wie viele Vorgänge waren insgesamt freigabepflichtig?",
            "impact": "Ohne Bezugsgröße ist die Quote nicht belastbar.",
            "needed_evidence": "Gesamtzahl für denselben Zeitraum.",
        },
    )
    client.force_login(owner)

    response = client.get(reverse("accelerator:investigation_detail", args=[handle.run_id]))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Klärung erforderlich" in body
    assert "Wie viele Vorgänge waren insgesamt freigabepflichtig?" in body
    assert "Gesamtzahl für denselben Zeitraum." in body
    assert 'name="answer"' in body
    assert reverse("accelerator:investigation_continue", args=[handle.run_id]) in body


@pytest.mark.django_db
def test_investigation_tool_results_are_scoped_to_run_references(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Run scoped evidence")
    (tmp_path / "cases.csv").write_text(
        "group,value,unit\nA,10,h\nA,20,h\nB,30,h\nB,40,h\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    source = InvestigationSource.objects.get(
        snapshot_id=snapshot.snapshot_id,
        filename="cases.csv",
    )

    run_b = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="run-scoped-tool-results-b",
        ),
    )
    step_b = execute_tool_step(
        actor=owner,
        run_id=run_b.run_id,
        executor_token=run_b.executor_token,
        tool_name="profile_csv",
        parameters={"source_id": str(source.pk)},
        target_claim_id="run-b-profile",
    )
    abort_investigation(actor=owner, run_id=run_b.run_id)

    run_a = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="run-scoped-tool-results-a",
        ),
    )
    step_a = execute_tool_step(
        actor=owner,
        run_id=run_a.run_id,
        executor_token=run_a.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(source.pk),
            "group_by": "group",
            "aggregation": "mean",
            "value_column": "value",
            "filters": [],
            "unit_column": "unit",
        },
        target_claim_id="run-a-calculation",
    )
    result_a_id = step_a.result_ref["tool_result_id"]
    result_b_id = step_b.result_ref["tool_result_id"]
    result_b_url = reverse(
        "accelerator:investigation_tool_result",
        args=[run_a.run_id, result_b_id],
    )
    client.force_login(owner)

    detail_a = client.get(reverse("accelerator:investigation_detail", args=[run_a.run_id]))
    detail_body = detail_a.content.decode()
    assert detail_a.status_code == 200
    assert str(result_a_id) in detail_body
    assert result_b_url not in detail_body
    assert client.get(result_b_url).status_code == 404

    apply_planner_state(
        actor=owner,
        run_id=run_a.run_id,
        executor_token=run_a.executor_token,
        brief_payload={
            "calculations": [
                {
                    "reference": {
                        "tool_result_id": str(result_b_id),
                        "revision_hash": "0" * 64,
                    },
                },
            ],
        },
    )
    invalid_detail = client.get(reverse("accelerator:investigation_detail", args=[run_a.run_id]))
    assert result_b_url not in invalid_detail.content.decode()
    assert client.get(result_b_url).status_code == 404

    apply_planner_state(
        actor=owner,
        run_id=run_a.run_id,
        executor_token=run_a.executor_token,
        brief_payload={
            "calculations": [
                {
                    "reference": {
                        "tool_result_id": str(result_b_id),
                        "revision_hash": source.content_sha256,
                    },
                },
            ],
        },
    )

    detail_a = client.get(reverse("accelerator:investigation_detail", args=[run_a.run_id]))
    assert result_b_url in detail_a.content.decode()
    assert client.get(result_b_url).status_code == 200


@pytest.mark.django_db
def test_model_call_reserves_estimated_tokens_not_utf8_bytes(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Token reservation")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process, output_tokens=200_000)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="token-reservation",
            evidence_campaign_id=campaign.pk,
            evidence_metadata={
                "provider_mode": "real",
                "phase": "calibration",
                "variant": "A",
            },
            decision_brief_required=True,
        ),
    )
    instruction = "Prüfe die Evidenz einschließlich Ä, Ö und Ü."
    context = {"text": "äöüß" * 100}
    payload = {"instruction": instruction, "context": context}

    call = _reserve_model_call(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        role=InvestigationModelCall.Role.PLANNER,
        instruction=instruction,
        prompt_version="test-token-reservation-v1",
        schema_version="test-token-reservation-schema-v1",
        context=context,
    )

    reservation = InvestigationProviderReservation.objects.get(model_call=call)
    serialized = canonical_json(payload)
    expected_tokens = _estimate_tokens(serialized)
    utf8_bytes = len(serialized.encode("utf-8"))

    assert reservation.reserved_input_tokens == expected_tokens
    assert reservation.reserved_input_tokens < utf8_bytes


@pytest.mark.django_db
def test_evidence_report_counts_attempts_but_only_expected_scored_boundaries(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Scored outcomes")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process)

    def start_scored(key, variant, attempt, execution_mode="adaptive"):
        handle = start_investigation(
            actor=owner,
            request=StartInvestigationRequest(
                snapshot_id=snapshot.snapshot_id,
                idempotency_key=key,
                evidence_campaign_id=campaign.pk,
                execution_mode=execution_mode,
                evidence_metadata={
                    "provider_mode": "real",
                    "phase": "scored",
                    "variant": variant,
                    "attempt": attempt,
                },
                decision_brief_required=True,
            ),
        )
        return InvestigationRun.objects.get(pk=handle.run_id)

    a_ready = start_scored("a-ready", "A", 1)
    InvestigationRun.objects.filter(pk=a_ready.pk).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
    )

    a_failed = start_scored("a-failed", "A", 2)
    InvestigationRun.objects.filter(pk=a_failed.pk).update(
        status=InvestigationRun.Status.FAILED,
        finished_at=timezone.now(),
    )

    b_expected = start_scored("b-missing-evidence", "B", 1)
    InvestigationRun.objects.filter(pk=b_expected.pk).update(
        status=InvestigationRun.Status.WAITING_HUMAN,
        clarification_reason=ReasonCode.MISSING_EVIDENCE.value,
        clarification_payload={"required_action": "Fehlende Bezugsgröße bereitstellen."},
    )
    abort_investigation(actor=owner, run_id=b_expected.pk)

    b_aborted_without_expected_boundary = start_scored("b-aborted", "B", 2)
    abort_investigation(actor=owner, run_id=b_aborted_without_expected_boundary.pk)

    b_fixed_boundary = start_scored("b-fixed-boundary", "B", 1, execution_mode="fixed")
    InvestigationRun.objects.filter(pk=b_fixed_boundary.pk).update(
        status=InvestigationRun.Status.WAITING_HUMAN,
        clarification_reason=ReasonCode.FIXED_ROUTE_BOUNDARY.value,
        clarification_payload={"required_action": "Fixed-Route-Grenze dokumentieren."},
    )
    abort_investigation(actor=owner, run_id=b_fixed_boundary.pk)

    report = evidence_campaign_report(campaign)

    assert report["matrix"]["A"]["adaptive_real_attempted"] == 2
    assert report["matrix"]["A"]["adaptive_real_sampled"] == 2
    assert report["matrix"]["A"]["adaptive_real_scored"] == 0
    assert report["matrix"]["B"]["adaptive_real_attempted"] == 2
    assert report["matrix"]["B"]["adaptive_real_sampled"] == 2
    assert report["matrix"]["B"]["adaptive_real_scored"] == 1
    assert report["matrix"]["B"]["fixed_real_attempted"] == 1
    assert report["matrix"]["B"]["fixed_real_sampled"] == 1
    assert report["matrix"]["B"]["fixed_real_scored"] == 0
    assert report["nine_real_adaptive_runs_complete"] is False
    assert report["nine_real_adaptive_runs_passed"] is False
    assert report["scored_sample_run_ids"]["A"] == [str(a_ready.pk), str(a_failed.pk)]
    assert len(report["attempts"]) == 5


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("mode", "runner_name"),
    (
        ("adaptive", "run_until_boundary"),
        ("fixed", "run_fixed_route_until_boundary"),
    ),
)
def test_issue4_runner_builds_controlled_real_attempt_without_manual_metadata(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
    mode,
    runner_name,
):
    process = make_process(owner=owner, business_unit=business_unit, name=f"Runner {mode}")
    write_variant_pack(tmp_path, "C")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process)
    captured = {}

    def fake_runner(**kwargs):
        captured.update(kwargs)
        return type(
            "Result",
            (),
            {"run_id": kwargs["run_id"], "status": InvestigationRun.Status.RUNNING},
        )()

    def wrong_runner(**_kwargs):
        raise AssertionError("Wrong Issue #4 execution arm used.")

    monkeypatch.setattr(issue4_evidence_command, "run_until_boundary", wrong_runner)
    monkeypatch.setattr(issue4_evidence_command, "run_fixed_route_until_boundary", wrong_runner)
    monkeypatch.setattr(issue4_evidence_command, runner_name, fake_runner)

    call_command(
        "run_issue4_evidence",
        campaign=str(campaign.pk),
        variant="C",
        mode=mode,
        phase="calibration",
        attempt=1,
        snapshot=str(snapshot.snapshot_id),
    )

    run = InvestigationRun.objects.get(evidence_campaign=campaign)
    assert run.source_snapshot_id == snapshot.snapshot_id
    assert run.execution_mode == mode
    assert run.evidence_metadata == {
        "provider_mode": "real",
        "phase": "calibration",
        "variant": "C",
        "attempt": 1,
    }
    assert run.execution_snapshot["decision_brief_required"] is True
    assert captured["run_id"] == run.pk
    assert captured["actor"] == owner
    assert run.model_calls.count() == 0


@pytest.mark.django_db
def test_issue4_runner_binds_variant_to_calibrated_snapshot_and_freezes_scored_sample(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Frozen sample")
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    write_variant_pack(first_root, "A")
    write_variant_pack(second_root, "A")
    _folder1, snapshot1 = snapshot_for_root(owner=owner, process=process, root=first_root)
    _folder2, snapshot2 = snapshot_for_root(owner=owner, process=process, root=second_root)
    campaign = evidence_campaign(owner=owner, process=process)

    def fake_runner(**kwargs):
        return type(
            "Result",
            (),
            {"run_id": kwargs["run_id"], "status": InvestigationRun.Status.RUNNING},
        )()

    monkeypatch.setattr(issue4_evidence_command, "run_until_boundary", fake_runner)

    call_command(
        "run_issue4_evidence",
        campaign=str(campaign.pk),
        variant="A",
        mode="adaptive",
        phase="calibration",
        attempt=1,
        snapshot=str(snapshot1.snapshot_id),
    )
    calibration = InvestigationRun.objects.get(evidence_campaign=campaign)
    abort_investigation(actor=owner, run_id=calibration.pk)

    call_command(
        "run_issue4_evidence",
        campaign=str(campaign.pk),
        variant="A",
        mode="adaptive",
        phase="scored",
        attempt=1,
    )
    scored = InvestigationRun.objects.exclude(pk=calibration.pk).get(evidence_campaign=campaign)
    assert scored.source_snapshot_id == snapshot1.snapshot_id
    assert scored.source_snapshot_id != snapshot2.snapshot_id
    abort_investigation(actor=owner, run_id=scored.pk)

    with pytest.raises(CommandError):
        call_command(
            "run_issue4_evidence",
            campaign=str(campaign.pk),
            variant="A",
            mode="adaptive",
            phase="scored",
            attempt=4,
        )

    with pytest.raises(CommandError):
        call_command(
            "run_issue4_evidence",
            campaign=str(campaign.pk),
            variant="A",
            mode="adaptive",
            phase="calibration",
            attempt=2,
            snapshot=str(snapshot1.snapshot_id),
        )


@pytest.mark.django_db
def test_issue4_runner_rejects_variant_snapshot_mismatch(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Variant mismatch")
    write_variant_pack(tmp_path, "B")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process)

    monkeypatch.setattr(
        issue4_evidence_command,
        "run_until_boundary",
        lambda **_kwargs: None,
    )

    with pytest.raises(CommandError):
        call_command(
            "run_issue4_evidence",
            campaign=str(campaign.pk),
            variant="A",
            mode="adaptive",
            phase="calibration",
            attempt=1,
            snapshot=str(snapshot.snapshot_id),
        )
    assert not campaign.investigation_runs.exists()


@pytest.mark.django_db
def test_adaptive_a_requires_agentic_effect_not_ready_status_only(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Agentic A")
    write_variant_pack(tmp_path, "A")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="agentic-a",
            evidence_campaign_id=campaign.pk,
            execution_mode="adaptive",
            evidence_metadata={
                "provider_mode": "real",
                "phase": "scored",
                "variant": "A",
                "attempt": 1,
            },
            decision_brief_required=True,
        ),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    csv_source = InvestigationSource.objects.get(
        snapshot_id=snapshot.snapshot_id,
        filename="cases.csv",
    )
    step = execute_tool_step(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        tool_name="compare_groups",
        parameters={
            "source_id": str(csv_source.pk),
            "group_by": "approver_available",
            "aggregation": "mean",
            "value_column": "approval_hours",
            "filters": [],
            "unit_column": "unit",
        },
        target_claim_id="cause",
    )
    assert step.progress_kind == InvestigationStep.ProgressKind.COVERAGE
    ref = source_reference(csv_source, row=3, column="approver_available")
    run.refresh_from_db()
    apply_planner_state(
        actor=owner,
        run_id=run.pk,
        executor_token=handle.executor_token,
        claim_register=(
            {
                "claim_id": "initial-cause",
                "statement": "Freigeberverfügbarkeit erklärt die Verzögerung.",
                "area": "competing_hypotheses",
                "claim_kind": "hypothesis",
                "status": "refuted",
                "counterevidence_refs": [ref],
            },
        ),
        brief_payload=full_brief(
            run=run,
            source=csv_source,
            result_id=step.result_payload["result_id"],
        ),
    )
    InvestigationRun.objects.filter(pk=run.pk).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
        counterevidence_search_executed=True,
        counterevidence_hits_processed=True,
        data_check_executed=True,
    )

    report = evidence_campaign_report(campaign)
    assert report["matrix"]["A"]["adaptive_real_scored"] == 1

    InvestigationRun.objects.filter(pk=run.pk).update(
        counterevidence_hits_processed=False,
    )
    report = evidence_campaign_report(campaign)
    assert report["matrix"]["A"]["adaptive_real_scored"] == 0


@pytest.mark.django_db
def test_runtime_ready_does_not_automatically_pass_issue4_methodology(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="READY vs benchmark")
    write_variant_pack(tmp_path, "A")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="ready-not-benchmark-complete",
            evidence_campaign_id=campaign.pk,
            execution_mode="adaptive",
            evidence_metadata={
                "provider_mode": "real",
                "phase": "scored",
                "variant": "A",
                "attempt": 1,
            },
            decision_brief_required=True,
        ),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    InvestigationRun.objects.filter(pk=run.pk).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
        data_check_executed=True,
        counterevidence_search_executed=True,
        counterevidence_hits_processed=True,
        brief_payload={
            "question_scope": {"question": run.decision_question, "scope": "Test"},
            "problem": {"statement": "Problem", "references": []},
            "recommendation": {"summary": "Richtung", "rationale": "Test", "references": []},
        },
    )

    report = evidence_campaign_report(campaign)

    assert report["matrix"]["A"]["adaptive_real_sampled"] == 1
    assert report["matrix"]["A"]["adaptive_real_scored"] == 0
    attempt = next(item for item in report["attempts"] if item["run_id"] == str(run.pk))
    assert attempt["status"] == InvestigationRun.Status.READY
    assert attempt["benchmark_brief_complete"] is False


@pytest.mark.django_db
def test_evidence_report_rejects_noncomparable_fixed_pair(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Report comparison")
    write_variant_pack(tmp_path, "C")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process)

    adaptive_handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="report-adaptive-c1",
            evidence_campaign_id=campaign.pk,
            execution_mode="adaptive",
            evidence_metadata={
                "provider_mode": "real",
                "phase": "scored",
                "variant": "C",
                "attempt": 1,
            },
            decision_brief_required=True,
        ),
    )
    adaptive = InvestigationRun.objects.get(pk=adaptive_handle.run_id)
    abort_investigation(actor=owner, run_id=adaptive.pk)

    fixed_handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key="report-fixed-c1",
            evidence_campaign_id=campaign.pk,
            execution_mode="fixed",
            evidence_metadata={
                "provider_mode": "real",
                "phase": "scored",
                "variant": "C",
                "attempt": 1,
            },
            decision_brief_required=True,
        ),
    )
    fixed = InvestigationRun.objects.get(pk=fixed_handle.run_id)
    abort_investigation(actor=owner, run_id=fixed.pk)

    changed = dict(fixed.execution_snapshot)
    transport = dict(changed["model_transport"])
    transport["requested_model"] = "different-model"
    changed["model_transport"] = transport
    InvestigationRun.objects.filter(pk=fixed.pk).update(execution_snapshot=changed)

    report = evidence_campaign_report(campaign)
    assert report["fixed_comparison_present"] is False
    assert report["comparison_issues"]
    assert any("C:" in item for item in report["comparison_issues"])


@pytest.mark.django_db
@pytest.mark.parametrize("campaign_output", [40_000, 200_000])
def test_campaign_headroom_protects_verification_without_allocating_entire_campaign(
    owner, business_unit, tmp_path, campaign_output
):
    process = make_process(owner=owner, business_unit=business_unit, name="Campaign headroom")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process, output_tokens=campaign_output)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key=f"campaign-headroom-{campaign_output}",
            evidence_campaign_id=campaign.pk,
            evidence_metadata={"provider_mode": "real", "phase": "calibration"},
            decision_brief_required=True,
        ),
    )
    args = {
        "actor": owner,
        "run_id": handle.run_id,
        "executor_token": handle.executor_token,
        "role": InvestigationModelCall.Role.PLANNER,
        "instruction": "Produce a structured decision",
        "prompt_version": "headroom-test",
        "schema_version": "headroom-test",
        "context": {},
    }
    call = _reserve_model_call(**args)
    campaign.refresh_from_db()

    protected_output = 28_884
    expected_max_tokens = min(131_072, campaign_output - protected_output)
    assert call.effective_parameters["max_tokens"] == expected_max_tokens
    assert campaign.usage["provider_calls"] == 1
    assert campaign.usage["reserved_output_tokens"] == expected_max_tokens
    assert campaign.usage["reserved_output_tokens"] < campaign.limits["max_output_tokens"]


@pytest.mark.django_db
@pytest.mark.parametrize("complete_usage", [False, True])
def test_truncated_campaign_attempt_settles_known_usage_or_retains_reservation(
    owner, business_unit, tmp_path, monkeypatch, complete_usage
):
    process = make_process(owner=owner, business_unit=business_unit, name="Truncation accounting")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process, output_tokens=200_000)
    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.snapshot_id,
            idempotency_key=f"truncation-accounting-{complete_usage}",
            evidence_campaign_id=campaign.pk,
            evidence_metadata={"provider_mode": "real", "phase": "calibration"},
            decision_brief_required=True,
        ),
    )

    def truncated_provider(**_kwargs):
        diagnostics = {"finish_reason": "length"}
        if complete_usage:
            diagnostics.update(
                usage_prompt_tokens=120,
                usage_completion_tokens=8192,
                returned_model="test-model",
            )
        raise OpenRouterUnavailable(
            "Completion limit", code="output_truncated", diagnostics=diagnostics
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_llm.request_openrouter", truncated_provider
    )
    with pytest.raises(InvestigationRunError) as exc_info:
        _structured_provider_call(
            actor=owner,
            run_id=handle.run_id,
            executor_token=handle.executor_token,
            role=InvestigationModelCall.Role.PLANNER,
            instruction="Produce a structured decision",
            prompt_version="truncation-test",
            schema_version="truncation-test",
            context={},
            response_format={"type": "json_schema"},
        )
    assert exc_info.value.code == "output_truncated"
    run = InvestigationRun.objects.get(pk=handle.run_id)
    call = run.model_calls.get()
    reservation = call.evidence_reservation
    campaign.refresh_from_db()
    if complete_usage:
        assert reservation.status == InvestigationProviderReservation.Status.SETTLED
        assert campaign.usage["output_tokens"] == 8192
        assert campaign.usage["reserved_output_tokens"] == 0
        assert run.usage["output_tokens"] == 8192
        assert call.completion_tokens == 8192
    else:
        assert reservation.status == InvestigationProviderReservation.Status.UNCERTAIN
        assert campaign.usage["output_tokens"] == 0
        assert campaign.usage["reserved_output_tokens"] > 0
        assert run.usage["output_tokens"] == 0
