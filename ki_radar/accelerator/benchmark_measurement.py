from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from django.db.models import Sum

from .models import CaptureAnalysis, FieldAdoptionCandidate

BENCHMARK_VERSION = "block9-v1"
SUPPORTED_BENCHMARK_VERSIONS = {"block9-v1", "block9-v2"}
VALID_PATHS = {"manual", "blueprint", "accelerator", "delivery"}
VALID_STATUSES = {"completed", "failed", "aborted", "blocked"}
TIME_KEYS = (
    "active_input_seconds",
    "navigation_seconds",
    "review_seconds",
    "correction_seconds",
    "system_wait_seconds",
    "end_to_end_seconds",
)
QUALITY_KEYS = (
    "correct_field_mappings",
    "field_mapping_errors",
    "number_unit_errors",
    "scope_errors",
    "invented_values",
    "missed_required_gaps",
    "stale_source_conflicts_missed",
    "suggestions_adopted",
    "suggestions_adopted_edited",
    "suggestions_rejected",
    "errors",
    "aborts",
)


def _nonnegative_number(value, key):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{key} must be a non-negative number")
    return value


def normalize_times(values):
    unknown = set(values) - set(TIME_KEYS)
    if unknown:
        raise ValueError(f"Unknown time keys: {sorted(unknown)}")
    return {key: _nonnegative_number(values.get(key, 0), key) for key in TIME_KEYS}


def normalize_quality(values):
    unknown = set(values) - set(QUALITY_KEYS)
    if unknown:
        raise ValueError(f"Unknown quality keys: {sorted(unknown)}")
    result = {}
    for key in QUALITY_KEYS:
        value = values.get(key, 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{key} must be a non-negative integer")
        result[key] = value
    return result


def capture_telemetry(session):
    analyses = session.analyses.all()
    candidates = FieldAdoptionCandidate.objects.filter(
        suggestion__analysis__session=session,
    )
    totals = analyses.aggregate(
        prompt_tokens=Sum("prompt_tokens"),
        completion_tokens=Sum("completion_tokens"),
        total_tokens=Sum("total_tokens"),
        cost=Sum("cost"),
        duration_ms=Sum("duration_ms"),
    )
    return {
        "capture": {
            "session_id": str(session.pk),
            "active_entry_seconds": session.active_entry_seconds,
            "save_count": session.save_count,
            "answered_required_count": session.answered_required_count,
            "required_question_count": session.required_question_count,
        },
        "llm": {
            "calls": analyses.count(),
            "prompt_tokens": totals["prompt_tokens"] or 0,
            "completion_tokens": totals["completion_tokens"] or 0,
            "total_tokens": totals["total_tokens"] or 0,
            "cost": totals["cost"] or Decimal("0"),
            "duration_ms": totals["duration_ms"] or 0,
            "errors": analyses.exclude(error_code="").count()
            + analyses.filter(status=CaptureAnalysis.Status.FAILED, error_code="").count(),
        },
        "adoption": {
            "adopted": candidates.filter(
                status=FieldAdoptionCandidate.Status.ADOPTED,
            ).count(),
            "adopted_edited": candidates.filter(
                status=FieldAdoptionCandidate.Status.ADOPTED_EDITED,
            ).count(),
            "rejected": candidates.filter(
                status=FieldAdoptionCandidate.Status.REJECTED,
            ).count(),
            "conflicts": candidates.filter(
                status=FieldAdoptionCandidate.Status.CONFLICT,
            ).count(),
            "stale": candidates.filter(
                status=FieldAdoptionCandidate.Status.STALE,
            ).count(),
            "failed": candidates.filter(
                status=FieldAdoptionCandidate.Status.FAILED,
            ).count(),
        },
    }


def build_raw_record(
    *,
    run_id,
    path,
    case_key,
    status,
    times,
    quality,
    benchmark_version=BENCHMARK_VERSION,
    capture_session=None,
    delivery=None,
    notes="",
):
    if benchmark_version not in SUPPORTED_BENCHMARK_VERSIONS:
        raise ValueError(f"Unknown benchmark version: {benchmark_version}")
    if path not in VALID_PATHS:
        raise ValueError(f"Unknown benchmark path: {path}")
    if status not in VALID_STATUSES:
        raise ValueError(f"Unknown benchmark status: {status}")
    if case_key not in {"A", "B"}:
        raise ValueError(f"Unknown benchmark case: {case_key}")
    record = {
        "benchmark_version": benchmark_version,
        "run_id": run_id,
        "path": path,
        "case": case_key,
        "status": status,
        "times": normalize_times(times),
        "quality": normalize_quality(quality),
        "notes": notes,
    }
    if capture_session is not None:
        record["existing_telemetry"] = capture_telemetry(capture_session)
    if delivery is not None:
        record["delivery"] = delivery
    return record


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def append_raw_record(output_path, record):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and json.loads(line).get("run_id") == record["run_id"]:
                raise ValueError(f"run_id already recorded: {record['run_id']}")
    payload = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        default=_json_default,
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")
