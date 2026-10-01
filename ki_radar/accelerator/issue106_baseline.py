from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import median
from typing import Any

from django.conf import settings
from django.db.models import QuerySet

from .investigation_diagnostics import build_investigation_diagnostic
from .investigation_models import (
    InvestigationProviderReservation,
    InvestigationRun,
)

EXPERIMENT_ID = "issue106-ap1-baseline-v1"
GOLDEN_CASE_IDS = ("AP4-01", "AP4-02", "AP4-04", "AP4-05", "AP4-06")
REPETITIONS = (1, 2, 3, 4, 5)
PERFORMANCE_CONTRACT_PATH = (
    Path(settings.BASE_DIR) / "tests/fixtures/issue106_performance_contract_v1.json"
)
AP4_MANIFEST_PATH = Path(settings.BASE_DIR) / "tests/fixtures/ap4_case_manifest_v1.json"
SEMANTIC_RUBRIC = (
    "all_expected_key_findings_present_or_explicitly_marked_unknown_when_source_does_not_support_them",
    "all_required_counterevidence_represented",
    "facts_hypotheses_and_unknowns_separated",
    "solution_openness_preserved",
    "decision_brief_internally_consistent",
    "human_authority_preserved",
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def performance_contract() -> dict[str, Any]:
    return _load_json(PERFORMANCE_CONTRACT_PATH)


def ap4_manifest() -> dict[str, Any]:
    return _load_json(AP4_MANIFEST_PATH)


def golden_case_specs() -> dict[str, dict[str, Any]]:
    contract_cases = {
        item["case_id"]: dict(item)
        for item in performance_contract()["golden_cases"]
        if item["case_id"] in GOLDEN_CASE_IDS
    }
    manifest_cases = {
        item["case_id"]: dict(item)
        for item in ap4_manifest()["cases"]
        if item["case_id"] in GOLDEN_CASE_IDS
    }
    if set(contract_cases) != set(GOLDEN_CASE_IDS) or set(manifest_cases) != set(GOLDEN_CASE_IDS):
        raise ValueError("Issue #106 golden set is incomplete")
    return {
        case_id: {
            **manifest_cases[case_id],
            "quality_contract": contract_cases[case_id],
        }
        for case_id in GOLDEN_CASE_IDS
    }


def baseline_slots() -> tuple[tuple[str, int], ...]:
    return tuple((case_id, repetition) for case_id in GOLDEN_CASE_IDS for repetition in REPETITIONS)


def slot_process_name(case_id: str, repetition: int) -> str:
    if case_id not in GOLDEN_CASE_IDS or repetition not in REPETITIONS:
        raise ValueError("unknown Issue #106 baseline slot")
    return f"Issue #106 AP1 {case_id} R{repetition}"


def slot_campaign_key(case_id: str, repetition: int) -> str:
    if case_id not in GOLDEN_CASE_IDS or repetition not in REPETITIONS:
        raise ValueError("unknown Issue #106 baseline slot")
    return f"i106-ap1-{case_id.lower()}-r{repetition}-v1"


def baseline_runs() -> QuerySet[InvestigationRun]:
    return InvestigationRun.objects.filter(
        evidence_metadata__experiment_id=EXPERIMENT_ID,
        evidence_metadata__phase="baseline",
    )


def consumed_or_reserved_cost_microunits() -> int:
    total = 0
    reservations = InvestigationProviderReservation.objects.filter(
        run__evidence_metadata__experiment_id=EXPERIMENT_ID
    )
    for item in reservations:
        if item.actual_cost_microunits is not None:
            total += int(item.actual_cost_microunits)
        elif item.reserved_cost_microunits is not None:
            total += int(item.reserved_cost_microunits)
    return total


def _repair_summary(model_calls: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    triggers = Counter(
        str(item.get("synthesis_trigger") or "")
        for item in model_calls
        if item.get("synthesis_trigger")
    )
    errors = Counter(
        str(item.get("error_code") or "") for item in model_calls if item.get("error_code")
    )
    repeated_role_after_failure = 0
    for index, item in enumerate(model_calls[:-1]):
        if item.get("status") != "failed":
            continue
        role = item.get("role")
        if any(later.get("role") == role for later in model_calls[index + 1 :]):
            repeated_role_after_failure += 1
    return {
        "synthesis_triggers": dict(triggers),
        "errors": dict(errors),
        "pre_verifier_repairs": int(triggers.get("pre_verifier_repair", 0)),
        "verifier_repairs": int(triggers.get("verifier_repair", 0)),
        "contract_retries": int(triggers.get("contract_retry", 0)),
        "same_role_after_failure": repeated_role_after_failure,
        "has_timeout": any("timeout" in code for code in errors),
        "has_invalid_response": bool(errors.get("invalid_response", 0)),
        "has_retry": bool(triggers.get("contract_retry", 0) or repeated_role_after_failure),
        "has_repair": bool(
            triggers.get("pre_verifier_repair", 0) or triggers.get("verifier_repair", 0)
        ),
    }


def build_baseline_record(run: InvestigationRun) -> dict[str, Any]:
    report = build_investigation_diagnostic(run)
    metadata = dict(run.evidence_metadata or {})
    latest_verifier = run.verifier_reports.order_by("-revision").first()
    brief = run.brief_payload if isinstance(run.brief_payload, Mapping) else {}
    risks_unknowns = brief.get("risks_unknowns")
    unknown_count = len(risks_unknowns) if isinstance(risks_unknowns, list) else 0
    quality = {
        "source_relevance_complete": bool(run.source_relevance_complete),
        "source_relevance_count": len(run.source_relevance or {}),
        "source_count": run.source_snapshot.sources.count(),
        "counterevidence_search_executed": bool(run.counterevidence_search_executed),
        "counterevidence_hits_processed": bool(run.counterevidence_hits_processed),
        "critical_claims_checked": (
            list(latest_verifier.checked_critical_claims or [])
            if latest_verifier is not None
            else []
        ),
        "verifier_critical_findings": (
            int(latest_verifier.critical_findings) if latest_verifier is not None else None
        ),
        "verifier_source_references_valid": (
            bool(latest_verifier.source_references_valid) if latest_verifier is not None else None
        ),
        "unknown_count": unknown_count,
        "clarification_reason": run.clarification_reason,
        "clarification_payload": dict(run.clarification_payload or {}),
    }
    return {
        "run_id": str(run.pk),
        "experiment_id": metadata.get("experiment_id"),
        "case_id": metadata.get("case_id"),
        "repetition": metadata.get("repetition"),
        "tested_commit": metadata.get("tested_commit"),
        "status": run.status,
        "manifest_hash": run.manifest_hash,
        "execution_contract": {
            "loop_version": run.loop_version,
            "budget_version": run.budget_version,
            "policy_version": run.policy_version,
            "runtime": dict((run.execution_snapshot or {}).get("runtime") or {}),
            "model_transport": dict((run.execution_snapshot or {}).get("model_transport") or {}),
            "planner": dict((run.execution_snapshot or {}).get("planner") or {}),
            "synthesizer": dict((run.execution_snapshot or {}).get("synthesizer") or {}),
            "verifier": dict((run.execution_snapshot or {}).get("verifier") or {}),
        },
        "performance": report,
        "recovery": _repair_summary(report["model_calls"]),
        "quality_observables": quality,
    }


def review_template(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    cases = golden_case_specs()
    reviews = []
    for record in records:
        case_id = str(record.get("case_id") or "")
        quality_contract = cases[case_id]["quality_contract"]
        reviews.append(
            {
                "run_id": record["run_id"],
                "case_id": case_id,
                "repetition": record["repetition"],
                "reviewer": "",
                "reviewed_at": "",
                "semantic_rubric": {criterion: "unassessed" for criterion in SEMANTIC_RUBRIC},
                "expected_key_findings": [
                    {
                        "criterion": item["criterion"],
                        "status": "unassessed",
                        "notes": "",
                    }
                    for item in quality_contract["expected_key_findings"]
                ],
                "required_counterevidence": [
                    {
                        "criterion": item["criterion"],
                        "status": "unassessed",
                        "notes": "",
                    }
                    for item in quality_contract["required_counterevidence"]
                ],
                "hard_fail_observed": False,
                "notes": "",
            }
        )
    return {
        "experiment_id": EXPERIMENT_ID,
        "allowed_statuses": ["pass", "fail", "unassessed"],
        "reviews": reviews,
    }


def validate_reviews(
    payload: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    raw_reviews = payload.get("reviews")
    if not isinstance(raw_reviews, list):
        raise ValueError("review file requires a reviews list")
    expected_ids = {str(item["run_id"]) for item in records}
    reviews: dict[str, dict[str, Any]] = {}
    for raw in raw_reviews:
        if not isinstance(raw, Mapping):
            raise ValueError("review entries must be objects")
        item = dict(raw)
        run_id = str(item.get("run_id") or "")
        if not run_id or run_id in reviews:
            raise ValueError("review run_id must be unique and non-empty")
        semantic = item.get("semantic_rubric")
        if not isinstance(semantic, Mapping) or set(semantic) != set(SEMANTIC_RUBRIC):
            raise ValueError(f"{run_id}: semantic rubric is incomplete")
        statuses = [str(value) for value in semantic.values()]
        for group in ("expected_key_findings", "required_counterevidence"):
            entries = item.get(group)
            if not isinstance(entries, list) or not entries:
                raise ValueError(f"{run_id}: {group} must be non-empty")
            statuses.extend(str(entry.get("status") or "") for entry in entries)
        if any(status not in {"pass", "fail", "unassessed"} for status in statuses):
            raise ValueError(f"{run_id}: invalid assessment status")
        item["assessment_complete"] = (
            bool(str(item.get("reviewer") or "").strip())
            and bool(str(item.get("reviewed_at") or "").strip())
            and all(status != "unassessed" for status in statuses)
        )
        reviews[run_id] = item
    if set(reviews) != expected_ids:
        raise ValueError("review file must contain exactly the exported baseline runs")
    return reviews


def _mad(values: Sequence[float]) -> float:
    center = median(values)
    return float(median(abs(value - center) for value in values))


def _rate(records: Sequence[Mapping[str, Any]], flag: str) -> float:
    if not records:
        return 0.0
    hits = sum(bool(item["recovery"].get(flag)) for item in records)
    return round((hits / len(records)) * 100, 2)


def aggregate_baseline(
    records: Sequence[Mapping[str, Any]],
    *,
    reviews: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    by_case: dict[str, Any] = {}
    for case_id in GOLDEN_CASE_IDS:
        case_records = [item for item in records if item.get("case_id") == case_id]
        runtimes = [float(item["performance"]["run_seconds"]) for item in case_records]
        costs = [float(item["performance"]["cost_usd"]) for item in case_records]
        if runtimes:
            runtime_median = float(median(runtimes))
            runtime_mad = _mad(runtimes)
            runtime = {
                "median_seconds": round(runtime_median, 3),
                "mad_seconds": round(runtime_mad, 3),
                "noise_floor_2x_mad_seconds": round(2 * runtime_mad, 3),
                "min_seconds": round(min(runtimes), 3),
                "max_seconds": round(max(runtimes), 3),
            }
        else:
            runtime = {}
        by_case[case_id] = {
            "attempted_runs": len(case_records),
            "statuses": dict(Counter(str(item["status"]) for item in case_records)),
            "runtime": runtime,
            "cost": {
                "total_usd": round(sum(costs), 6),
                "median_usd": round(float(median(costs)), 6) if costs else None,
            },
            "timeout_rate_percent": _rate(case_records, "has_timeout"),
            "retry_rate_percent": _rate(case_records, "has_retry"),
            "repair_rate_percent": _rate(case_records, "has_repair"),
        }

    expected_slots = set(baseline_slots())
    present_slots = {
        (str(item.get("case_id")), int(item.get("repetition")))
        for item in records
        if item.get("case_id") in GOLDEN_CASE_IDS and item.get("repetition") in REPETITIONS
    }
    quality_complete = False
    hard_fail_count = None
    if reviews is not None:
        quality_complete = all(
            bool(reviews[str(item["run_id"])].get("assessment_complete")) for item in records
        )
        hard_fail_count = sum(
            bool(reviews[str(item["run_id"])].get("hard_fail_observed")) for item in records
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "expected_run_count": len(expected_slots),
        "observed_run_count": len(records),
        "complete_slots": present_slots == expected_slots,
        "missing_slots": sorted(
            f"{case_id}:R{repetition}" for case_id, repetition in expected_slots - present_slots
        ),
        "tested_commits": sorted(
            {str(item.get("tested_commit") or "") for item in records if item.get("tested_commit")}
        ),
        "total_cost_usd": round(sum(float(item["performance"]["cost_usd"]) for item in records), 6),
        "by_case": by_case,
        "quality_complete": quality_complete,
        "observed_hard_fail_count": hard_fail_count,
        "non_observable": [
            "provider_internal_queue_vs_inference_time",
            "cache_effects_when_provider_metadata_does_not_expose_them",
        ],
    }
