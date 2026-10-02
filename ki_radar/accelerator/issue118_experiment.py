"""Frozen #118 measurement contract. No provider execution in this module."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess  # nosec B404 -- fixed git argv, no shell
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median

from django.conf import settings
from django.core.management.base import CommandError

from .issue106_baseline import (
    GOLDEN_CASE_IDS,
    _runtime_stats,
    aggregate_baseline,
    review_template,
    validate_reviews,
)

EXPERIMENT_ID = "issue106-exp118-source-coverage-v1"
CONTROL_COMMIT = "b37e25b6508a6e5769785c72c2fc35ac1177fae2"
AFFECTED_CASES = ("AP4-02", "AP4-04")
ARMS = ("variant", "control")
LOOPS = {"variant": "vs1-agent-loop-v20", "control": "vs1-agent-loop-v19"}
CONTRACT_KEYS = (
    "loop_version",
    "budget_version",
    "policy_version",
    "runtime",
    "model_transport",
    "planner",
    "synthesizer",
    "verifier",
    "tools",
)
FAILURE_CODES = (
    "timeout",
    "invalid_response",
    "structured_contract_error",
    "invalid_tool_parameters",
    "no_progress_loop",
    "execution_interrupted",
    "iteration_guard",
)
FIXTURE_TEST = (
    "tests/test_issue_118_planner_source_coverage.py::"
    "test_historical_early_read_survives_six_later_steps"
)


def slots():
    result = []
    for index, case in enumerate(GOLDEN_CASE_IDS):
        starts = [("variant", 1), ("control", 1)]
        if index % 2:
            starts.reverse()
        for arm, repeat in starts + [("variant", r) for r in (2, 3, 4)]:
            result.append({"arm": arm, "case_id": case, "repetition": repeat})
    return result


def slot_key(slot):
    if slot not in slots():
        raise ValueError("Unknown #118 arm/case/repetition slot")
    return f"i106-e118-{slot['arm']}-{slot['case_id'].lower()}-r{slot['repetition']}-v1"


def process_name(slot):
    return f"Issue #118 {slot_key(slot)}"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def git_output(root, *args):
    executable = shutil.which("git")
    if not executable:
        raise CommandError("Git is required for verified checkout bindings")
    try:
        return subprocess.run(  # noqa: S603 # nosec B603 -- fixed argv, shell=False
            [executable, *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CommandError("Git verification failed") from exc


def verify_checkout(root, expected):
    root = Path(root).resolve()
    if Path(git_output(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise CommandError("Checkout root must be the actual Git repository root")
    if git_output(root, "status", "--porcelain", "--untracked-files=all"):
        raise CommandError("#118 requires a clean worktree, including untracked files")
    head = git_output(root, "rev-parse", "HEAD")
    if len(expected) != 40 or head != expected:
        raise CommandError("Wrong tested commit; environment overrides are not accepted")
    return head


def pricing_from_env():
    result = {}
    for env, field in (
        ("ISSUE106_PRICE_INPUT_PER_MILLION", "input_per_million"),
        ("ISSUE106_PRICE_OUTPUT_PER_MILLION", "output_per_million"),
    ):
        try:
            value = Decimal(os.environ.get(env, ""))
        except InvalidOperation as exc:
            raise CommandError(f"{env}: explicit finite non-negative price required") from exc
        if not value.is_finite() or value < 0:
            raise CommandError(f"{env}: explicit finite non-negative price required")
        result[field] = str(value.normalize())
    currency = os.environ.get("ISSUE106_PRICING_CURRENCY", "").strip()
    version = os.environ.get("ISSUE106_PRICING_VERSION", "").strip()
    if currency != "USD" or not version or len(version) > 80:
        raise CommandError("Explicit USD currency and pricing version (1..80 characters) required")
    return {"rates": result, "currency": currency, "version": version}


def technical_contract(snapshot):
    result = {key: snapshot[key] for key in CONTRACT_KEYS}
    result["runtime"] = {
        key: value for key, value in result["runtime"].items() if key != "code_revision"
    }
    return result


def read_plan(path):
    try:
        plan = json.loads(Path(path).read_text(encoding="utf-8"))
        frozen = {key: value for key, value in plan.items() if key != "plan_hash"}
        if plan["plan_hash"] != digest(frozen):
            raise ValueError("Plan digest mismatch")
        if plan["experiment_id"] != EXPERIMENT_ID or plan["slots"] != slots():
            raise ValueError("Wrong experiment ID or changed frozen order")
        if plan["control_commit"] != CONTROL_COMMIT:
            raise ValueError("Wrong control commit")
        if len(plan["variant_commit"]) != 40:
            raise ValueError("Invalid variant commit")
        if set(plan["contracts"]) != set(ARMS):
            raise ValueError("Missing arm contract")
        for arm in ARMS:
            if plan["contracts"][arm]["loop_version"] != LOOPS[arm]:
                raise ValueError("Wrong v19/v20 contract binding")
        control = dict(plan["contracts"]["control"])
        control["loop_version"] = LOOPS["variant"]
        if control != plan["contracts"]["variant"]:
            raise ValueError("Only the declared loop contract may differ between arms")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CommandError(f"Invalid frozen #118 plan: {exc}") from exc
    return plan


def validate_record(record, plan):
    slot = {key: record.get(key) for key in ("arm", "case_id", "repetition")}
    key = slot_key(slot)
    arm = slot["arm"]
    expected = plan[f"{arm}_commit"]
    if record.get("experiment_id") != EXPERIMENT_ID or record.get("phase") != "experiment":
        raise ValueError("Wrong experiment ID/phase")
    if record.get("tested_commit") != expected or record.get("plan_hash") != plan["plan_hash"]:
        raise ValueError("Wrong commit/plan binding")
    if record.get("execution_contract") != plan["contracts"][arm]:
        raise ValueError("Wrong execution contract")
    if record.get("source_pack_hash") != plan["source_hashes"][slot["case_id"]]:
        raise ValueError("Wrong source pack hash")
    binding = plan["prepared"][key]
    if record.get("manifest_hash") != binding["manifest_hash"]:
        raise ValueError("Wrong source snapshot manifest")
    if record.get("source_file_hashes") != binding["source_file_hashes"]:
        raise ValueError("Wrong snapshot file content hashes")
    if record.get("domain_input_hash") != binding["domain_input_hash"]:
        raise ValueError("Wrong neutral domain input binding")
    return slot


def experiment_review_template(records, plan):
    result = review_template(records)
    result.update(experiment_id=EXPERIMENT_ID, plan_hash=plan["plan_hash"])
    for row, record in zip(result["reviews"], records, strict=True):
        row.update(
            arm=record["arm"], tested_commit=record["tested_commit"], record_hash=digest(record)
        )
    result["expected_slots"] = slots()
    return result


def experiment_reviews(payload, records, plan):
    if (
        payload.get("experiment_id") != EXPERIMENT_ID
        or payload.get("plan_hash") != plan["plan_hash"]
    ):
        raise ValueError("Review experiment/plan mismatch")
    by_id = {str(record["run_id"]): record for record in records}
    for row in payload.get("reviews", []):
        record = by_id.get(str(row.get("run_id")))
        if record is None or any(row.get(k) != record[k] for k in ("arm", "tested_commit")):
            raise ValueError("Review arm/commit mismatch")
        if row.get("record_hash") != digest(record):
            raise ValueError("Review context changed; review the current evidence")
    return validate_reviews(payload, records)


def historical_reference(root=None):
    root = Path(root or settings.BASE_DIR)
    baseline_path = root / "artifacts/issue106/ap1/baseline.json"
    review_path = root / "artifacts/issue106/ap1/review.json"
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    records = payload["runs"]
    assessments = validate_reviews(review, records)
    summary = aggregate_baseline(records, reviews=assessments)
    if (
        payload["experiment_id"] != "issue106-ap1-baseline-v1"
        or not summary["population_complete"]
        or not summary["quality_complete"]
        or summary["tested_commits"] != [CONTROL_COMMIT]
        or summary["observed_hard_fail_count"]
        or summary != payload["summary"]
    ):
        raise ValueError("Versioned AP1 reference is inconsistent")
    return {
        "runs": records,
        "summary": summary,
        "hashes": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (baseline_path, review_path)
        },
    }


def failure_counts(records):
    counts = Counter()
    for record in records:
        counts.update(record.get("failure_codes", {}))
    return {code: counts.get(code, 0) for code in sorted(set(FAILURE_CODES) | set(counts))}


def ap1_failure_codes(records):
    result = Counter()
    for row in records:
        result.update(row["recovery"].get("errors", {}))
        code = row.get("quality_observables", {}).get("clarification_payload", {}).get("error_code")
        if code:
            result[code] += 1
    return set(result)


def aggregate_experiment(records, plan, reference, reviews=None):
    seen = Counter()
    run_ids = set()
    for record in records:
        slot = validate_record(record, plan)
        key = slot_key(slot)
        seen[key] += 1
        if seen[key] > 1 or record["run_id"] in run_ids:
            raise ValueError("Duplicate experiment slot/run ID")
        run_ids.add(record["run_id"])
    missing = [slot_key(slot) for slot in slots() if slot_key(slot) not in seen]
    boundary = bool(records) and all(
        r["terminal_state_check"]["system_boundary_reached"] for r in records
    )
    complete = not missing and boundary
    baseline = reference["summary"]
    reference_runs = reference["runs"]
    all_reviews = reviews or {}
    quality_complete = (
        complete
        and set(all_reviews) == run_ids
        and all(r["assessment_complete"] for r in all_reviews.values())
    )
    hard_fails = sum(bool(r.get("hard_fail_observed")) for r in all_reviews.values())
    by_arm = {}
    for arm in ARMS:
        rows = [r for r in records if r["arm"] == arm]
        by_case = {}
        for case in GOLDEN_CASE_IDS:
            case_rows = [r for r in rows if r["case_id"] == case]
            by_case[case] = {
                "attempted_runs": len(case_rows),
                "runtime": _runtime_stats(case_rows),
                "statuses": dict(Counter(r["status"] for r in case_rows)),
                "runtime_by_terminal_state": {
                    state: _runtime_stats([r for r in case_rows if r["status"] == state])
                    for state in ("ready", "waiting_human", "failed", "running")
                },
                "ap1_statuses": baseline["by_case"][case]["statuses"],
                "quality_pass_count": sum(
                    all_reviews.get(r["run_id"], {}).get("overall_status") == "pass"
                    for r in case_rows
                ),
            }
            baseline_passes = baseline["by_case"][case]["quality_statuses"].get("pass", 0)
            by_case[case]["quality_rate_guard_pass"] = bool(
                case_rows
                and by_case[case]["quality_pass_count"] / len(case_rows)
                >= baseline_passes / baseline["by_case"][case]["attempted_runs"]
            )
        rates = {
            name: sum(bool(r["recovery"].get(f"has_{name}")) for r in rows) / len(rows) * 100
            if rows
            else None
            for name in ("timeout", "retry", "repair")
        }
        baseline_rates = {
            name: sum(bool(r["recovery"].get(f"has_{name}")) for r in reference_runs)
            / len(reference_runs)
            * 100
            for name in rates
        }
        rate_guards = {
            name: rates[name] is not None and rates[name] <= baseline_rates[name] + 5
            for name in rates
        }
        passes = sum(all_reviews.get(r["run_id"], {}).get("overall_status") == "pass" for r in rows)
        cost = sum(Decimal(str(r["performance"]["budget_accounted_cost_usd"])) for r in rows)
        reference_passes = baseline["quality_statuses"].get("pass", 0)
        reference_cost = (
            Decimal(str(baseline["total_budget_accounted_cost_usd"])) / reference_passes
        )
        quotient = cost / passes if passes else None
        failures = failure_counts(rows)
        by_arm[arm] = {
            "attempted_runs": len(rows),
            "by_case": by_case,
            "event_rates_percent": rates,
            "ap1_event_rates_percent": baseline_rates,
            "event_rate_guards": rate_guards,
            "budget_accounted_cost_usd": float(cost),
            "actual_cost_usd": sum(r["performance"]["cost_usd"] for r in rows),
            "uncertain_attempts": sum(
                r["performance"]["uncertain_provider_attempts"] for r in rows
            ),
            "quality_pass_count": passes,
            "quality_statuses": dict(
                Counter(
                    all_reviews.get(r["run_id"], {}).get("overall_status", "unassessed")
                    for r in rows
                )
            ),
            "cost_per_quality_pass_usd": float(quotient) if quotient is not None else None,
            "cost_metric_status": "defined" if quotient is not None else "undefined",
            "ap1_cost_per_quality_pass_usd": float(reference_cost),
            "cost_guard_pass": quotient is not None
            and quotient <= reference_cost * Decimal("1.05"),
            "failure_categories": failures,
            "new_failure_types": sorted(
                code
                for code, count in failures.items()
                if count and code not in ap1_failure_codes(reference_runs)
            ),
        }
    drift = {}
    for case in GOLDEN_CASE_IDS:
        controls = [r for r in records if r["arm"] == "control" and r["case_id"] == case]
        stats = baseline["by_case"][case]["runtime"]
        delta = (
            abs(controls[0]["performance"]["run_seconds"] - stats["median_seconds"])
            if controls
            else None
        )
        drift[case] = {
            "absolute_delta_seconds": delta,
            "noise_floor_seconds": stats["noise_floor_2x_mad_seconds"],
            "outside_noise": delta > stats["noise_floor_2x_mad_seconds"]
            if delta is not None
            else None,
            "control_status": controls[0]["status"] if controls else None,
        }
    outside = sum(row["outside_noise"] is True for row in drift.values())
    comparable = complete and outside < 2
    effects = {}
    for case in AFFECTED_CASES:
        original = [r for r in reference_runs if r["case_id"] == case]
        variant = [r for r in records if r["arm"] == "variant" and r["case_id"] == case]
        # Same boundary/work population is required for latency claims. Report all other
        # status transitions, including FAILED -> READY, as reliability evidence only.
        states_match = len({r["status"] for r in original}) == 1 and {
            r["status"] for r in original
        } == {r["status"] for r in variant}
        stats = baseline["by_case"][case]["runtime"]
        effect = (
            stats["median_seconds"] - median(r["performance"]["run_seconds"] for r in variant)
            if variant
            else None
        )
        effects[case] = {
            "case_effect_seconds": effect,
            "status_comparable": states_match,
            "ap1_statuses": dict(Counter(r["status"] for r in original)),
            "variant_statuses": dict(Counter(r["status"] for r in variant)),
        }
    runtime_comparable = comparable and all(row["status_comparable"] for row in effects.values())
    effect = median(row["case_effect_seconds"] for row in effects.values()) if complete else None
    noise = median(
        baseline["by_case"][case]["runtime"]["noise_floor_2x_mad_seconds"]
        for case in AFFECTED_CASES
    )
    baseline_center = median(
        baseline["by_case"][case]["runtime"]["median_seconds"] for case in AFFECTED_CASES
    )
    runtime_gate = bool(
        runtime_comparable and effect >= 30 and effect / baseline_center >= 0.10 and effect > noise
    )
    affected = [r for r in records if r["arm"] == "variant" and r["case_id"] in AFFECTED_CASES]
    loops = sum(bool(r.get("failure_codes", {}).get("no_progress_loop")) for r in affected)
    fixtures = plan["fixture_evidence"]
    fixture_gate = fixtures.get("tested_commit") == plan["variant_commit"] and fixtures.get(
        "passed_cases"
    ) == list(AFFECTED_CASES)
    reliability = (
        len(affected) == 8
        and loops == 0
        and not by_arm["variant"]["new_failure_types"]
        and fixture_gate
    )
    budget = sum(Decimal(str(row["budget_accounted_cost_usd"])) for row in by_arm.values())
    guards = (
        quality_complete
        and hard_fails == 0
        and by_arm["variant"]["cost_guard_pass"]
        and all(by_arm["variant"]["event_rate_guards"].values())
        and all(row["quality_rate_guard_pass"] for row in by_arm["variant"]["by_case"].values())
        and budget <= 20
    )
    adoption = comparable and guards and (runtime_gate or reliability)
    return {
        "population_complete": complete,
        "expected_variant_count": 20,
        "expected_control_count": 5,
        "missing_slots": missing,
        "all_runs_at_system_boundary": boundary,
        "quality_complete": quality_complete,
        "observed_hard_fail_count": hard_fails,
        "by_arm": by_arm,
        "drift_sentinel": drift,
        "controls_outside_noise_count": outside,
        "comparison_status": "comparable" if comparable else "not_sufficiently_proven",
        "runtime_effect": {
            "by_case": effects,
            "aggregate_effect_seconds": effect,
            "aggregate_noise_floor_seconds": noise,
            "status_comparable": runtime_comparable,
            "gate_pass": runtime_gate,
        },
        "g03": {
            "affected_variant_run_count": len(affected),
            "expected_affected_variant_run_count": 8,
            "no_progress_loop_count": loops,
            "state_fixtures_pass": fixture_gate,
            "gate_pass": reliability,
        },
        "experiment_budget_accounted_cost_usd": float(budget),
        "experiment_budget_guard_pass": budget <= 20,
        "adoption_eligible": adoption,
        "authority": (
            "Eligibility is evidence for the human parent-issue gate, never an automatic adoption."
        ),
    }
