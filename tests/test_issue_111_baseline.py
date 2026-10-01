from __future__ import annotations

from datetime import timedelta
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from ki_radar.accelerator.investigation_diagnostics import build_investigation_diagnostic
from ki_radar.accelerator.investigation_models import (
    InvestigationEvidenceCampaign,
    InvestigationModelCall,
    InvestigationProviderReservation,
    InvestigationRun,
)
from ki_radar.accelerator.issue106_baseline import (
    GOLDEN_CASE_IDS,
    REPETITIONS,
    aggregate_baseline,
    baseline_runs,
    baseline_slots,
    review_template,
    validate_reviews,
)
from ki_radar.accelerator.management.commands import run_issue106_baseline
from ki_radar.accelerator.management.commands.run_issue106_baseline import (
    Command as BaselineRunCommand,
    baseline_execution_lock,
)
from ki_radar.architecture.models import ProcessAnalysis
from tests.test_issue_3_investigation_hardening import start_csv_run


def _record(
    case_id: str,
    repetition: int,
    runtime: float,
    cost: float,
    *,
    tested_commit: str = "a" * 40,
    status: str = "ready",
    boundary: bool = True,
):
    allowed = {
        "AP4-01": ["ready"],
        "AP4-02": ["ready"],
        "AP4-04": ["ready"],
        "AP4-05": ["waiting_human"],
        "AP4-06": ["ready", "waiting_human"],
    }[case_id]
    return {
        "run_id": f"{case_id}-{repetition}",
        "case_id": case_id,
        "repetition": repetition,
        "tested_commit": tested_commit,
        "status": status,
        "terminal_state_check": {
            "observed": status,
            "allowed": allowed,
            "conforms": status in allowed,
            "system_boundary_reached": boundary,
        },
        "performance": {
            "run_seconds": runtime,
            "cost_usd": cost,
            "budget_accounted_cost_usd": cost,
            "uncertain_provider_attempts": 0,
        },
        "recovery": {
            "has_timeout": False,
            "has_retry": False,
            "has_repair": False,
        },
    }


def _complete_review(template: dict) -> None:
    for review in template["reviews"]:
        review["reviewer"] = "human-reviewer"
        review["reviewed_at"] = "2026-10-01T20:00:00+02:00"
        for key in review["semantic_rubric"]:
            review["semantic_rubric"][key] = "pass"
        for group in (
            "expected_key_findings",
            "required_counterevidence",
            "hard_fail_checks",
        ):
            for item in review[group]:
                item["status"] = "pass"


def test_issue111_baseline_contract_has_exactly_twenty_five_slots():
    slots = baseline_slots()

    assert len(slots) == 25
    assert {case_id for case_id, _repeat in slots} == set(GOLDEN_CASE_IDS)
    for case_id in GOLDEN_CASE_IDS:
        repeats = [repeat for slot_case, repeat in slots if slot_case == case_id]
        assert repeats == list(REPETITIONS)


def test_issue111_aa_summary_uses_median_and_two_mad_noise_floor():
    records = []
    runtimes = [100.0, 102.0, 104.0, 106.0, 108.0]
    for case_id in GOLDEN_CASE_IDS:
        for repetition, runtime in enumerate(runtimes, start=1):
            records.append(_record(case_id, repetition, runtime, 0.10))

    summary = aggregate_baseline(records)

    assert summary["complete_slots"] is True
    assert summary["single_tested_commit"] is True
    assert summary["observed_run_count"] == 25
    assert summary["total_actual_cost_usd"] == 2.5
    assert summary["total_budget_accounted_cost_usd"] == 2.5
    for case_id in GOLDEN_CASE_IDS:
        runtime = summary["by_case"][case_id]["runtime"]
        assert runtime["raw_seconds"] == runtimes
        assert runtime["median_seconds"] == 104.0
        assert runtime["mad_seconds"] == 2.0
        assert runtime["noise_floor_2x_mad_seconds"] == 4.0


def test_issue111_duplicate_slot_or_mixed_commit_makes_baseline_incomplete():
    records = [
        _record(case_id, repetition, 100.0, 0.10)
        for case_id in GOLDEN_CASE_IDS
        for repetition in REPETITIONS
    ]
    records.append(_record("AP4-01", 1, 101.0, 0.11, tested_commit="b" * 40))

    summary = aggregate_baseline(records)

    assert summary["complete_slots"] is False
    assert summary["duplicate_slots"] == ["AP4-01:R1"]
    assert summary["single_tested_commit"] is False


def test_issue111_unassessed_review_cannot_become_quality_complete():
    records = [_record("AP4-01", 1, 100.0, 0.1)]
    template = review_template(records)
    reviews = validate_reviews(template, records)
    summary = aggregate_baseline(records, reviews=reviews)

    review = reviews["AP4-01-1"]
    assert review["assessment_complete"] is False
    assert review["overall_status"] == "unassessed"
    assert review["hard_fail_observed"] is False
    assert summary["quality_complete"] is False
    assert summary["observed_hard_fail_count"] == 0


def test_issue111_hard_fail_requires_explicit_assessment_and_is_not_averaged_away():
    records = [_record("AP4-01", 1, 100.0, 0.1)]
    template = review_template(records)
    _complete_review(template)
    template["reviews"][0]["hard_fail_checks"][0]["status"] = "fail"

    reviews = validate_reviews(template, records)
    summary = aggregate_baseline(records, reviews=reviews)

    review = reviews["AP4-01-1"]
    assert review["assessment_complete"] is True
    assert review["hard_fail_observed"] is True
    assert review["overall_status"] == "fail"
    assert summary["quality_complete"] is True
    assert summary["observed_hard_fail_count"] == 1
    assert summary["quality_statuses"] == {"fail": 1}


@pytest.mark.django_db
def test_issue111_prepare_creates_isolated_slots_without_provider_runs(
    owner,
    monkeypatch,
):
    monkeypatch.setenv("ISSUE106_OWNER_USERNAME", owner.username)
    out = StringIO()

    call_command("prepare_issue106_baseline", stdout=out)

    processes = ProcessAnalysis.objects.filter(name__startswith="Issue #106 AP1 AP4-")
    assert processes.count() == 25
    assert sum(process.investigation_runs.count() for process in processes) == 0
    assert sum(process.investigation_source_snapshots.count() for process in processes) == 25
    assert "ISSUE106_AP1_PREPARED" in out.getvalue()


@pytest.mark.django_db
def test_issue111_waiting_human_diagnostic_excludes_later_human_wait(
    owner,
    business_unit,
    tmp_path,
):
    _process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue111-wait-runtime",
    )
    started = timezone.now() - timedelta(seconds=60)
    boundary = started + timedelta(seconds=20)
    InvestigationRun.objects.filter(pk=handle.run_id).update(
        status=InvestigationRun.Status.WAITING_HUMAN,
        started_at=started,
        updated_at=boundary,
        clarification_reason="missing_evidence",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    report = build_investigation_diagnostic(
        run,
        now=started + timedelta(hours=4),
    )

    assert report["run_seconds"] == 20.0


@pytest.mark.django_db
def test_issue111_diagnostic_reports_actual_role_cost_and_uncertain_budget_cost(
    owner,
    business_unit,
    tmp_path,
):
    process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue111-cost-diagnostic",
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    campaign = InvestigationEvidenceCampaign.objects.create(
        process_analysis=process,
        campaign_key="issue111-cost-diagnostic",
        limits={
            "max_provider_calls": 10,
            "max_input_tokens": 100_000,
            "max_output_tokens": 100_000,
            "max_cost_microunits": 1_000_000,
        },
        usage={},
        pricing={"input_per_million": "1", "output_per_million": "1"},
        currency="USD",
        pricing_version="test",
        authorized_by=owner,
    )
    started = timezone.now() - timedelta(seconds=10)
    planner = InvestigationModelCall.objects.create(
        run=run,
        role=InvestigationModelCall.Role.PLANNER,
        status=InvestigationModelCall.Status.SUCCESS,
        executor_generation=run.executor_generation,
        requested_model="test",
        returned_model="test",
        prompt_version="test",
        prompt_hash="a" * 64,
        instruction_template="test",
        schema_version="test",
        prompt_tokens=100,
        completion_tokens=20,
        total_tokens=120,
        started_at=started,
        finished_at=started + timedelta(seconds=2),
    )
    synthesizer = InvestigationModelCall.objects.create(
        run=run,
        role=InvestigationModelCall.Role.SYNTHESIZER,
        status=InvestigationModelCall.Status.FAILED,
        error_code="timeout",
        executor_generation=run.executor_generation,
        requested_model="test",
        prompt_version="test",
        prompt_hash="b" * 64,
        instruction_template="test",
        schema_version="test",
        started_at=started + timedelta(seconds=3),
        finished_at=started + timedelta(seconds=8),
    )
    InvestigationProviderReservation.objects.create(
        campaign=campaign,
        run=run,
        model_call=planner,
        status=InvestigationProviderReservation.Status.SETTLED,
        reserved_input_tokens=1000,
        reserved_output_tokens=1000,
        reserved_cost_microunits=200_000,
        actual_input_tokens=100,
        actual_output_tokens=20,
        actual_cost_microunits=100_000,
        settled_at=timezone.now(),
    )
    InvestigationProviderReservation.objects.create(
        campaign=campaign,
        run=run,
        model_call=synthesizer,
        status=InvestigationProviderReservation.Status.UNCERTAIN,
        reserved_input_tokens=1000,
        reserved_output_tokens=1000,
        reserved_cost_microunits=300_000,
        uncertainty_reason="timeout",
    )

    report = build_investigation_diagnostic(run)

    assert report["cost_usd"] == 0.1
    assert report["budget_accounted_cost_usd"] == 0.4
    assert report["uncertain_provider_attempts"] == 1
    assert report["role_totals"]["planner"]["cost_usd"] == 0.1
    assert report["role_totals"]["synthesizer"]["cost_usd"] == 0.0
    assert report["model_calls"][0]["cost_usd"] == 0.1
    assert report["model_calls"][1]["reserved_cost_microunits"] == 300_000



def test_issue111_population_requires_boundary_and_every_commit_value():
    records = [
        _record(case_id, repetition, 100.0, 0.10)
        for case_id in GOLDEN_CASE_IDS
        for repetition in REPETITIONS
    ]
    records[0]["terminal_state_check"]["system_boundary_reached"] = False
    records[1]["tested_commit"] = ""

    summary = aggregate_baseline(records)

    assert summary["complete_slots"] is True
    assert summary["population_complete"] is False
    assert summary["all_runs_at_system_boundary"] is False
    assert summary["all_tested_commits_present_and_valid"] is False
    assert summary["single_tested_commit"] is False


def test_issue111_ap4_06_runtime_is_stratified_when_terminal_states_differ():
    records = [
        _record("AP4-06", 1, 100.0, 0.1, status="ready"),
        _record("AP4-06", 2, 110.0, 0.1, status="ready"),
        _record("AP4-06", 3, 40.0, 0.1, status="waiting_human"),
        _record("AP4-06", 4, 44.0, 0.1, status="waiting_human"),
        _record("AP4-06", 5, 42.0, 0.1, status="waiting_human"),
    ]

    summary = aggregate_baseline(records)
    case = summary["by_case"]["AP4-06"]

    assert case["comparison_runtime"] is None
    assert case["comparison_runtime_mode"] == "stratified_only"
    assert case["runtime_by_terminal_state"]["ready"]["sample_size"] == 2
    assert case["runtime_by_terminal_state"]["ready"]["raw_seconds"] == [100.0, 110.0]
    waiting = case["runtime_by_terminal_state"]["waiting_human"]
    assert waiting["sample_size"] == 3
    assert waiting["median_seconds"] == 42.0


def test_issue111_review_binds_terminal_state_check():
    records = [_record("AP4-05", 1, 30.0, 0.1, status="ready")]
    template = review_template(records)
    _complete_review(template)

    reviews = validate_reviews(template, records)

    assert reviews["AP4-05-1"]["assessment_complete"] is True
    assert reviews["AP4-05-1"]["overall_status"] == "fail"


def test_issue111_commit_env_cannot_override_verified_head(monkeypatch):
    command = BaselineRunCommand()
    monkeypatch.setattr(run_issue106_baseline.shutil, "which", lambda _name: "git")
    monkeypatch.setenv("ISSUE106_TESTED_COMMIT", "b" * 40)

    responses = iter(
        [
            SimpleNamespace(stdout=""),
            SimpleNamespace(stdout=("a" * 40) + "\n"),
        ]
    )
    monkeypatch.setattr(
        run_issue106_baseline.subprocess,
        "run",
        lambda *args, **kwargs: next(responses),
    )

    with pytest.raises(CommandError, match="must exactly match"):
        command._tested_commit()


def test_issue111_global_lock_fails_closed_without_postgresql(monkeypatch):
    monkeypatch.setattr(
        run_issue106_baseline,
        "connection",
        SimpleNamespace(vendor="sqlite"),
    )

    with pytest.raises(CommandError, match="requires PostgreSQL"):
        with baseline_execution_lock():
            pass


def test_issue111_global_lock_rejects_second_command(monkeypatch):
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _sql, _params):
            return None

        def fetchone(self):
            return (False,)

    fake_connection = SimpleNamespace(
        vendor="postgresql",
        cursor=lambda: FakeCursor(),
    )
    monkeypatch.setattr(run_issue106_baseline, "connection", fake_connection)

    with pytest.raises(CommandError, match="currently owns the project lock"):
        with baseline_execution_lock():
            pass


@pytest.mark.django_db
def test_issue111_running_slot_without_inflight_provider_state_is_resumed(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue111-resume-running",
    )
    campaign = InvestigationEvidenceCampaign.objects.create(
        process_analysis=process,
        campaign_key="issue111-resume-running",
        limits={},
        usage={},
        pricing={},
        currency="USD",
        pricing_version="test",
        authorized_by=owner,
    )
    InvestigationRun.objects.filter(pk=handle.run_id).update(
        evidence_campaign=campaign,
        evidence_metadata={
            "experiment_id": "issue106-ap1-baseline-v1",
            "phase": "baseline",
            "case_id": "AP4-01",
            "repetition": 1,
            "tested_commit": "a" * 40,
        },
    )
    run = (
        InvestigationRun.objects.select_related("evidence_campaign__authorized_by")
        .get(pk=handle.run_id)
    )
    called = {}
    command = BaselineRunCommand()

    def fake_execute_run(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(command, "_execute_run", fake_execute_run)

    command._handle_existing_run(run=run, case_id="AP4-01", repetition=1)

    assert called["run_id"] == run.pk
    assert called["executor_token"] == run.executor_token
    assert called["actor"] == owner


@pytest.mark.django_db
def test_issue111_interrupted_inflight_slot_is_fenced_without_replacement(
    owner,
    business_unit,
    tmp_path,
):
    process, _snapshot, handle, _source = start_csv_run(
        owner=owner,
        business_unit=business_unit,
        tmp_path=tmp_path,
        key="issue111-fence-running",
    )
    campaign = InvestigationEvidenceCampaign.objects.create(
        process_analysis=process,
        campaign_key="issue111-fence-running",
        limits={"max_cost_microunits": 1_000_000},
        usage={},
        pricing={"input_per_million": "1", "output_per_million": "1"},
        currency="USD",
        pricing_version="test",
        authorized_by=owner,
    )
    InvestigationRun.objects.filter(pk=handle.run_id).update(
        evidence_campaign=campaign,
        evidence_metadata={
            "experiment_id": "issue106-ap1-baseline-v1",
            "phase": "baseline",
            "case_id": "AP4-01",
            "repetition": 1,
            "tested_commit": "a" * 40,
        },
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    call = InvestigationModelCall.objects.create(
        run=run,
        role=InvestigationModelCall.Role.PLANNER,
        status=InvestigationModelCall.Status.RUNNING,
        executor_generation=run.executor_generation,
        requested_model="test",
        prompt_version="test",
        prompt_hash="a" * 64,
        instruction_template="test",
        schema_version="test",
        started_at=timezone.now(),
    )
    reservation = InvestigationProviderReservation.objects.create(
        campaign=campaign,
        run=run,
        model_call=call,
        status=InvestigationProviderReservation.Status.OPEN,
        reserved_input_tokens=10,
        reserved_output_tokens=10,
        reserved_cost_microunits=100_000,
    )
    command = BaselineRunCommand()
    run = (
        InvestigationRun.objects.select_related("evidence_campaign__authorized_by")
        .get(pk=run.pk)
    )

    command._handle_existing_run(run=run, case_id="AP4-01", repetition=1)

    run.refresh_from_db()
    reservation.refresh_from_db()
    call.refresh_from_db()
    assert run.status == InvestigationRun.Status.FAILED
    assert run.clarification_payload["error_code"] == "execution_interrupted"
    assert reservation.status == InvestigationProviderReservation.Status.UNCERTAIN
    assert call.status == InvestigationModelCall.Status.DISCARDED
    assert baseline_runs().filter(
        evidence_metadata__case_id="AP4-01",
        evidence_metadata__repetition=1,
    ).count() == 1


@pytest.mark.django_db
def test_issue111_export_preserves_existing_review_without_explicit_overwrite(tmp_path):
    output = tmp_path / "baseline.json"
    review = tmp_path / "review.json"
    review.write_text('{"human":"work"}\n', encoding="utf-8")

    call_command(
        "export_issue106_baseline",
        "--output",
        str(output),
        "--review-template",
        str(review),
    )

    assert review.read_text(encoding="utf-8") == '{"human":"work"}\n'


def test_issue111_real_provider_command_requires_explicit_confirmation():
    with pytest.raises(CommandError, match="confirm-real-provider"):
        call_command(
            "run_issue106_baseline",
            "--case",
            "AP4-01",
            "--repeat",
            "1",
        )
