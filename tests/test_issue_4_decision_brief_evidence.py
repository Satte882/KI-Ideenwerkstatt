from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.investigation_benchmark import (
    assert_comparable_runs,
    evidence_campaign_report,
    prepare_fixed_route,
    request_fixed_route_synthesis,
)
from ki_radar.accelerator.investigation_brief import materialize_decision_brief
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
)
from ki_radar.accelerator.management.commands import run_issue4_evidence as issue4_evidence_command
from ki_radar.accelerator.investigation_models import (
    InvestigationModelCall,
    InvestigationProviderReservation,
    InvestigationRun,
    InvestigationSource,
    InvestigationSourceFolder,
)
from ki_radar.accelerator.investigation_policy import PolicyOutcome, ReasonCode
from ki_radar.accelerator.investigation_runtime import (
    InvestigationRunError,
    StartInvestigationRequest,
    abort_investigation,
    canonical_json,
    content_hash,
    evaluate_run_policy,
    execute_tool_step,
    start_investigation,
)
from ki_radar.accelerator.investigation_tools import (
    SnapshotRequest,
    create_source_snapshot,
)
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
)


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

    changed = dict(adaptive.execution_snapshot)
    transport = dict(changed["model_transport"])
    transport["requested_model"] = "different-model"
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
def test_model_call_reserves_estimated_tokens_not_utf8_bytes(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Token reservation")
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    _folder, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    campaign = evidence_campaign(owner=owner, process=process)
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

    def start_scored(key, variant, execution_mode="adaptive"):
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
                },
                decision_brief_required=True,
            ),
        )
        return InvestigationRun.objects.get(pk=handle.run_id)

    a_ready = start_scored("a-ready", "A")
    InvestigationRun.objects.filter(pk=a_ready.pk).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
    )

    a_failed = start_scored("a-failed", "A")
    InvestigationRun.objects.filter(pk=a_failed.pk).update(
        status=InvestigationRun.Status.FAILED,
        finished_at=timezone.now(),
    )

    b_expected = start_scored("b-missing-evidence", "B")
    InvestigationRun.objects.filter(pk=b_expected.pk).update(
        status=InvestigationRun.Status.WAITING_HUMAN,
        clarification_reason=ReasonCode.MISSING_EVIDENCE.value,
        clarification_payload={"required_action": "Fehlende Bezugsgröße bereitstellen."},
    )
    abort_investigation(actor=owner, run_id=b_expected.pk)

    b_aborted_without_expected_boundary = start_scored("b-aborted", "B")
    abort_investigation(actor=owner, run_id=b_aborted_without_expected_boundary.pk)

    b_fixed_boundary = start_scored("b-fixed-boundary", "B", execution_mode="fixed")
    InvestigationRun.objects.filter(pk=b_fixed_boundary.pk).update(
        status=InvestigationRun.Status.WAITING_HUMAN,
        clarification_reason=ReasonCode.FIXED_ROUTE_BOUNDARY.value,
        clarification_payload={"required_action": "Fixed-Route-Grenze dokumentieren."},
    )
    abort_investigation(actor=owner, run_id=b_fixed_boundary.pk)

    report = evidence_campaign_report(campaign)

    assert report["matrix"]["A"]["adaptive_real_attempted"] == 2
    assert report["matrix"]["A"]["adaptive_real_scored"] == 1
    assert report["matrix"]["B"]["adaptive_real_attempted"] == 2
    assert report["matrix"]["B"]["adaptive_real_scored"] == 1
    assert report["matrix"]["B"]["fixed_real_attempted"] == 1
    assert report["matrix"]["B"]["fixed_real_scored"] == 0
    assert report["nine_real_adaptive_runs_complete"] is False
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
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
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
        phase="scored",
        attempt=2,
    )

    run = InvestigationRun.objects.get(evidence_campaign=campaign)
    assert run.source_snapshot_id == snapshot.snapshot_id
    assert run.execution_mode == mode
    assert run.evidence_metadata == {
        "provider_mode": "real",
        "phase": "scored",
        "variant": "C",
        "attempt": 2,
    }
    assert run.execution_snapshot["decision_brief_required"] is True
    assert captured["run_id"] == run.pk
    assert captured["actor"] == owner
    assert run.model_calls.count() == 0
