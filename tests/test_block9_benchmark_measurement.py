import json
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from ki_radar.accelerator.benchmark_measurement import (
    append_raw_record,
    build_raw_record,
    capture_telemetry,
)
from ki_radar.accelerator.models import (
    CaptureAnalysis,
    CaptureFieldSuggestion,
    CaptureSession,
    FieldAdoptionCandidate,
)

pytestmark = pytest.mark.django_db


def _session(owner):
    return CaptureSession.objects.create(
        owner=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        catalog_version="1",
        schema_version="1",
        active_entry_seconds=42,
        save_count=3,
        answered_required_count=4,
        required_question_count=5,
        expires_at=timezone.now() + timedelta(hours=1),
    )


def test_build_raw_record_normalizes_missing_metrics():
    record = build_raw_record(
        run_id="manual-A-1",
        path="manual",
        case_key="A",
        status="completed",
        times={"end_to_end_seconds": 120},
        quality={"correct_field_mappings": 21},
    )

    assert record["benchmark_version"] == "block9-v1"
    assert record["times"]["end_to_end_seconds"] == 120
    assert record["times"]["review_seconds"] == 0
    assert record["quality"]["correct_field_mappings"] == 21
    assert record["quality"]["errors"] == 0


def test_append_raw_record_is_append_only_per_run_id(tmp_path):
    output = tmp_path / "raw.jsonl"
    record = build_raw_record(
        run_id="manual-A-1",
        path="manual",
        case_key="A",
        status="completed",
        times={},
        quality={},
    )

    append_raw_record(output, record)

    with pytest.raises(ValueError, match="already recorded"):
        append_raw_record(output, record)

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in rows] == ["manual-A-1"]


def test_capture_telemetry_reuses_existing_accelerator_data(owner):
    session = _session(owner)
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=0,
        source_hash="a" * 64,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        catalog_version="1",
        answer_schema_version="1",
        provider="openrouter",
        model_name="benchmark-model",
        prompt_version="1",
        extraction_schema_version="1",
        finished_at=timezone.now(),
        duration_ms=250,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost=Decimal("0.010000"),
    )
    suggestion = CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.USE_CASE,
        target_field="problem_statement",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Problem",
        source_question="problem",
        source_excerpt="Problem",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Direkter Fakt",
    )
    FieldAdoptionCandidate.objects.create(
        suggestion=suggestion,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.USE_CASE,
        target_object_id=uuid.uuid4(),
        target_field="problem_statement",
        proposed_value="Problem",
        previous_value="",
        previous_value_hash="b" * 64,
        target_updated_at=timezone.now(),
        source_revision=0,
        source_hash="a" * 64,
        catalog_version="1",
        answer_schema_version="1",
        prompt_version="1",
        extraction_schema_version="1",
        status=FieldAdoptionCandidate.Status.ADOPTED,
        resolved_at=timezone.now(),
    )

    telemetry = capture_telemetry(session)

    assert telemetry["capture"]["active_entry_seconds"] == 42
    assert telemetry["capture"]["save_count"] == 3
    assert telemetry["llm"]["calls"] == 1
    assert telemetry["llm"]["total_tokens"] == 15
    assert telemetry["llm"]["cost"] == Decimal("0.010000")
    assert telemetry["adoption"]["adopted"] == 1
