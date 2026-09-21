from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.core.management import call_command

from ki_radar.accelerator.block5_demo import run_block5_real_demo
from ki_radar.accelerator.models import (
    CaptureSession,
    FieldAdoptionAudit,
    FieldAdoptionCandidate,
)


@pytest.fixture(autouse=True)
def enable_field_adoption(settings):
    settings.ACCELERATOR_FIELD_ADOPTION_ENABLED = True


@pytest.mark.django_db
def test_real_demo_covers_both_targets_and_required_candidate_outcomes():
    report = run_block5_real_demo()

    counts = report["candidate_counts"]
    assert report["marker"] == "[Real-DEMO]"
    assert len(report["session_ids"]) == 2
    assert counts == {
        "direct_adopted": 1,
        "edited_adopted": 1,
        "rejected": 2,
        "conflict": 1,
        "superseded": 1,
        "open": 0,
    }
    assert CaptureSession.objects.filter(pk__in=report["session_ids"]).count() == 2
    assert set(
        CaptureSession.objects.filter(pk__in=report["session_ids"]).values_list(
            "capture_type", flat=True
        )
    ) == {
        CaptureSession.CaptureType.VALUE_STREAM,
        CaptureSession.CaptureType.USE_CASE,
    }
    assert (
        FieldAdoptionCandidate.objects.filter(
            suggestion__analysis__session_id__in=report["session_ids"]
        ).count()
        == 6
    )
    assert (
        FieldAdoptionAudit.objects.filter(session_id_snapshot__in=report["session_ids"]).count()
        == 5
    )


@pytest.mark.django_db
def test_real_demo_counts_unique_analysis_costs_and_separates_times():
    report = run_block5_real_demo()

    assert report["unique_analysis_runs"] == 3
    assert report["unique_used_analysis_runs"] == 2
    assert report["used_field_count"] == 2
    assert Decimal(report["all_analysis_cost"]) == Decimal("0.006000")
    assert Decimal(report["used_analysis_cost"]) == Decimal("0.005000")
    assert Decimal(report["cost_per_used_field"]) == Decimal("0.002500")
    assert report["provider_wait_time_ms"] == 3200
    assert report["review_time_ms"] >= 4
    assert report["correction_time_ms"] >= 1


@pytest.mark.django_db
def test_real_demo_management_command_writes_reproducible_json(tmp_path):
    output_path = tmp_path / "block5-real-demo.json"

    call_command("run_block5_real_demo", output=output_path)
    first = json.loads(output_path.read_text(encoding="utf-8"))
    call_command("run_block5_real_demo", output=output_path)
    second = json.loads(output_path.read_text(encoding="utf-8"))

    assert first["candidate_counts"] == second["candidate_counts"]
    assert first["unique_analysis_runs"] == second["unique_analysis_runs"] == 3
    assert first["all_analysis_cost"] == second["all_analysis_cost"] == "0.006000"
