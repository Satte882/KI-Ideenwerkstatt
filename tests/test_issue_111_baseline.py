from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from ki_radar.accelerator.investigation_diagnostics import build_investigation_diagnostic
from ki_radar.accelerator.investigation_models import InvestigationRun
from ki_radar.accelerator.issue106_baseline import (
    GOLDEN_CASE_IDS,
    REPETITIONS,
    aggregate_baseline,
    baseline_slots,
    review_template,
    validate_reviews,
)
from ki_radar.architecture.models import ProcessAnalysis
from tests.test_issue_3_investigation_hardening import start_csv_run


def _record(case_id: str, repetition: int, runtime: float, cost: float):
    return {
        "run_id": f"{case_id}-{repetition}",
        "case_id": case_id,
        "repetition": repetition,
        "tested_commit": "a" * 40,
        "status": "ready",
        "performance": {
            "run_seconds": runtime,
            "cost_usd": cost,
        },
        "recovery": {
            "has_timeout": False,
            "has_retry": False,
            "has_repair": False,
        },
    }


def test_issue111_baseline_contract_has_exactly_twenty_five_slots():
    slots = baseline_slots()

    assert len(slots) == 25
    assert set(case_id for case_id, _repeat in slots) == set(GOLDEN_CASE_IDS)
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
    assert summary["observed_run_count"] == 25
    assert summary["total_cost_usd"] == 2.5
    for case_id in GOLDEN_CASE_IDS:
        runtime = summary["by_case"][case_id]["runtime"]
        assert runtime["median_seconds"] == 104.0
        assert runtime["mad_seconds"] == 2.0
        assert runtime["noise_floor_2x_mad_seconds"] == 4.0


def test_issue111_unassessed_review_cannot_become_quality_complete():
    records = [_record("AP4-01", 1, 100.0, 0.1)]
    template = review_template(records)
    reviews = validate_reviews(template, records)
    summary = aggregate_baseline(records, reviews=reviews)

    assert reviews["AP4-01-1"]["assessment_complete"] is False
    assert summary["quality_complete"] is False
    assert summary["observed_hard_fail_count"] == 0


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


def test_issue111_real_provider_command_requires_explicit_confirmation():
    with pytest.raises(Exception, match="confirm-real-provider"):
        call_command(
            "run_issue106_baseline",
            "--case",
            "AP4-01",
            "--repeat",
            "1",
        )
