from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from django.utils import timezone

from ki_radar.core.models import SystemJobRun

from .scenario_blueprint_apply import BlueprintApplyResult, apply_blueprint
from .scenario_blueprint_diff import BlueprintGraphDiff, build_blueprint_diff
from .scenario_blueprint_validation import validate_blueprint

JOB_NAME = "scenario_blueprint"


@dataclass(frozen=True)
class BlueprintExecutionResult:
    mode: str
    job_run_id: int
    summary: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_error(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    return text[:1000]


def _diff_counts(diff: BlueprintGraphDiff) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in diff.objects:
        key = item.status.value.lower()
        counts[key] = counts.get(key, 0) + 1
    return counts


def _success_details(
    *,
    mode: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    details = {
        "mode": mode,
        "scenario_key": summary["scenario_key"],
        "schema_version": summary["schema_version"],
        "checksum": summary["checksum"],
        "result": summary.get("result") or summary.get("graph_status"),
    }
    if mode == "dry_run":
        details["object_counts"] = summary["object_counts"]
    else:
        details["created_counts"] = summary["created_counts"]
        details["object_ids"] = summary["object_ids"]
    return details


def _dry_run_summary(diff: BlueprintGraphDiff) -> dict[str, Any]:
    summary = diff.as_dict()
    summary["object_counts"] = _diff_counts(diff)
    return summary


def run_blueprint(
    payload: dict[str, Any],
    *,
    apply: bool = False,
) -> BlueprintExecutionResult:
    mode = "apply" if apply else "dry_run"
    started_at = timezone.now()
    job = SystemJobRun.objects.create(
        job_name=JOB_NAME,
        status=SystemJobRun.Status.RUNNING,
        started_at=started_at,
        details={"mode": mode},
    )
    try:
        resolved = validate_blueprint(payload)
        result: BlueprintApplyResult | BlueprintGraphDiff
        if apply:
            result = apply_blueprint(resolved)
            summary = result.as_dict()
        else:
            result = build_blueprint_diff(resolved)
            summary = _dry_run_summary(result)
        finished_at = timezone.now()
        job.status = SystemJobRun.Status.SUCCESS
        job.finished_at = finished_at
        job.exit_code = 0
        job.details = _success_details(mode=mode, summary=summary)
        job.error_message = ""
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "exit_code",
                "details",
                "error_message",
                "updated_at",
            ]
        )
        return BlueprintExecutionResult(
            mode=mode,
            job_run_id=job.pk,
            summary=summary,
        )
    except Exception as exc:
        job.status = SystemJobRun.Status.FAILED
        job.finished_at = timezone.now()
        job.exit_code = 1
        job.details = {
            "mode": mode,
            "error_type": type(exc).__name__,
        }
        job.error_message = _safe_error(exc)
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "exit_code",
                "details",
                "error_message",
                "updated_at",
            ]
        )
        raise
