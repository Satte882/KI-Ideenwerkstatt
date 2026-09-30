from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ki_radar.accelerator.architect_contract import (
    DISCOVERY_PROMPT_VERSION,
    DISCOVERY_SCHEMA_VERSION,
    DISCOVERY_VERIFIER_PROMPT_VERSION,
    DISCOVERY_VERIFIER_SCHEMA_VERSION,
)
from ki_radar.accelerator.investigation_prompts import (
    PLANNER_PROMPT_VERSION,
    PLANNER_SCHEMA_VERSION,
    SYNTHESIS_PROMPT_VERSION,
    SYNTHESIS_SCHEMA_VERSION,
    VERIFIER_PROMPT_VERSION,
    VERIFIER_SCHEMA_VERSION,
)
from ki_radar.accelerator.investigation_runtime import (
    BUDGET_VERSION,
    LOOP_VERSION,
    TRANSPORT_VERSION,
)
from ki_radar.delivery import ap3_autonomous
from ki_radar.use_cases import ap2_decision_governance, ap2_metric_pilot

REQUIRED_CATEGORIES = frozenset(
    {
        "organizational_non_ai",
        "rule_automation",
        "controlled_llm",
        "llm_workflow_hybrid",
        "missing_decision_critical_evidence",
        "conflicting_evidence",
        "governance_relevant",
        "data_csv",
    }
)
VALID_PHASES = frozenset({"scored", "post_fix"})
VALID_PATHS = frozenset({"manual", "autonomous"})
REQUIRED_TARGETS = frozenset(
    {
        "active_human_work_median_seconds_max",
        "manual_field_reduction_min",
        "avoidable_questions_median_max",
        "provenance_ratio_min",
        "hallucinated_facts_max",
        "human_rework_ratio_max",
    }
)
TIME_KEYS = (
    "active_input_seconds",
    "navigation_seconds",
    "authority_decision_seconds",
    "post_draft_review_seconds",
    "post_draft_correction_seconds",
    "system_wait_seconds",
)


class AP4EvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class FrozenCase:
    case_id: str
    run_slot: str
    category: str
    source_pack: str
    files: tuple[str, ...]
    problem_statement: str
    expected_branch: str
    acceptance_focus: tuple[str, ...]


@dataclass(frozen=True)
class FrozenManifest:
    contract_version: str
    plan_commit: str
    metric_targets: Mapping[str, float]
    versions: Mapping[str, str]
    baseline_case_ids: tuple[str, ...]
    cases: tuple[FrozenCase, ...]


@dataclass(frozen=True)
class FrozenValidation:
    manifest: FrozenManifest
    source_hashes: Mapping[str, str]


def current_contract_versions() -> dict[str, str]:
    return {
        "discovery_prompt": DISCOVERY_PROMPT_VERSION,
        "discovery_schema": DISCOVERY_SCHEMA_VERSION,
        "discovery_verifier_prompt": DISCOVERY_VERIFIER_PROMPT_VERSION,
        "discovery_verifier_schema": DISCOVERY_VERIFIER_SCHEMA_VERSION,
        "investigation_planner_prompt": PLANNER_PROMPT_VERSION,
        "investigation_planner_schema": PLANNER_SCHEMA_VERSION,
        "investigation_synthesis_prompt": SYNTHESIS_PROMPT_VERSION,
        "investigation_synthesis_schema": SYNTHESIS_SCHEMA_VERSION,
        "investigation_verifier_prompt": VERIFIER_PROMPT_VERSION,
        "investigation_verifier_schema": VERIFIER_SCHEMA_VERSION,
        "investigation_loop": LOOP_VERSION,
        "investigation_budget": BUDGET_VERSION,
        "investigation_transport": TRANSPORT_VERSION,
        "ap2_metric_pilot_prompt": ap2_metric_pilot.PROMPT_VERSION,
        "ap2_metric_pilot_schema": ap2_metric_pilot.SCHEMA_VERSION,
        "ap2_decision_governance_prompt": ap2_decision_governance.PROMPT_VERSION,
        "ap2_decision_governance_schema": ap2_decision_governance.SCHEMA_VERSION,
        "ap3_delivery_prompt": ap3_autonomous.PROMPT_VERSION,
        "ap3_delivery_schema": ap3_autonomous.SCHEMA_VERSION,
    }


def _require_text(name: str, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise AP4EvidenceError(f"{name} must not be empty")
    return text


def _nonnegative_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise AP4EvidenceError(f"{name} must be a non-negative number")
    return float(value)


def _nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AP4EvidenceError(f"{name} must be a non-negative integer")
    return value


def load_frozen_manifest(path: str | Path) -> FrozenManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AP4EvidenceError("manifest root must be an object")

    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != 8:
        raise AP4EvidenceError("manifest must contain exactly eight cases")

    cases: list[FrozenCase] = []
    seen_ids: set[str] = set()
    seen_slots: set[str] = set()
    categories: set[str] = set()

    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise AP4EvidenceError("each case must be an object")
        case_id = _require_text("case_id", raw.get("case_id"))
        run_slot = _require_text("run_slot", raw.get("run_slot"))
        category = _require_text("category", raw.get("category"))
        files = raw.get("files")
        focus = raw.get("acceptance_focus")
        if case_id in seen_ids:
            raise AP4EvidenceError(f"duplicate case_id: {case_id}")
        if run_slot in seen_slots:
            raise AP4EvidenceError(f"duplicate run_slot: {run_slot}")
        if not isinstance(files, list) or not files or any(not str(item).strip() for item in files):
            raise AP4EvidenceError(f"{case_id}: files must be a non-empty list")
        if not isinstance(focus, list) or not focus:
            raise AP4EvidenceError(f"{case_id}: acceptance_focus must be non-empty")

        seen_ids.add(case_id)
        seen_slots.add(run_slot)
        categories.add(category)
        cases.append(
            FrozenCase(
                case_id=case_id,
                run_slot=run_slot,
                category=category,
                source_pack=_require_text("source_pack", raw.get("source_pack")),
                files=tuple(str(item).strip() for item in files),
                problem_statement=_require_text("problem_statement", raw.get("problem_statement")),
                expected_branch=_require_text("expected_branch", raw.get("expected_branch")),
                acceptance_focus=tuple(_require_text("acceptance_focus", item) for item in focus),
            )
        )

    if categories != REQUIRED_CATEGORIES:
        raise AP4EvidenceError(
            "manifest categories differ from AP4 contract: "
            f"missing={sorted(REQUIRED_CATEGORIES - categories)}, "
            f"extra={sorted(categories - REQUIRED_CATEGORIES)}"
        )

    baseline_ids = tuple(str(item).strip() for item in payload.get("baseline_case_ids") or ())
    if not baseline_ids or any(item not in seen_ids for item in baseline_ids):
        raise AP4EvidenceError("baseline_case_ids must reference frozen cases")

    targets = payload.get("metric_targets")
    versions = payload.get("versions")
    if not isinstance(targets, dict) or not isinstance(versions, dict):
        raise AP4EvidenceError("metric_targets and versions must be objects")
    if set(targets) != REQUIRED_TARGETS:
        raise AP4EvidenceError(
            "metric_targets differ from frozen AP4 contract: "
            f"missing={sorted(REQUIRED_TARGETS - set(targets))}, "
            f"extra={sorted(set(targets) - REQUIRED_TARGETS)}"
        )

    return FrozenManifest(
        contract_version=_require_text("contract_version", payload.get("contract_version")),
        plan_commit=_require_text("plan_commit", payload.get("plan_commit")),
        metric_targets={str(k): float(v) for k, v in targets.items()},
        versions={str(k): str(v) for k, v in versions.items()},
        baseline_case_ids=baseline_ids,
        cases=tuple(cases),
    )


def _pack_files(root: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            str(path.relative_to(root)).replace("\\", "/")
            for path in root.rglob("*")
            if path.is_file()
        )
    )


def source_pack_hash(root: str | Path, expected_files: Iterable[str]) -> str:
    root_path = Path(root)
    if not root_path.is_dir():
        raise AP4EvidenceError(f"missing source pack: {root_path}")

    expected = tuple(sorted(str(item) for item in expected_files))
    actual = _pack_files(root_path)
    if actual != expected:
        raise AP4EvidenceError(
            f"source pack file set changed for {root_path}: expected={expected}, actual={actual}"
        )

    digest = hashlib.sha256()
    for relative in expected:
        data = (root_path / relative).read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def validate_frozen_manifest(
    manifest_path: str | Path,
    *,
    repo_root: str | Path,
    require_current_versions: bool = True,
) -> FrozenValidation:
    manifest = load_frozen_manifest(manifest_path)
    current_versions = current_contract_versions()
    if require_current_versions and dict(manifest.versions) != current_versions:
        missing = sorted(set(current_versions) - set(manifest.versions))
        extra = sorted(set(manifest.versions) - set(current_versions))
        changed = sorted(
            key
            for key in set(current_versions) & set(manifest.versions)
            if current_versions[key] != manifest.versions[key]
        )
        raise AP4EvidenceError(
            "frozen prompt/schema/runtime versions no longer match current code: "
            f"missing={missing}, extra={extra}, changed={changed}"
        )

    base = Path(repo_root)
    hashes = {
        case.case_id: source_pack_hash(base / case.source_pack, case.files)
        for case in manifest.cases
    }
    return FrozenValidation(manifest=manifest, source_hashes=hashes)


def normalize_record(
    raw: Mapping[str, Any],
    *,
    validation: FrozenValidation,
) -> dict[str, Any]:
    case_id = _require_text("case_id", raw.get("case_id"))
    cases = {case.case_id: case for case in validation.manifest.cases}
    if case_id not in cases:
        raise AP4EvidenceError(f"unknown case_id: {case_id}")
    case = cases[case_id]

    phase = _require_text("phase", raw.get("phase"))
    path = _require_text("path", raw.get("path"))
    if phase not in VALID_PHASES:
        raise AP4EvidenceError(f"invalid phase: {phase}")
    if path not in VALID_PATHS:
        raise AP4EvidenceError(f"invalid path: {path}")

    record_id = _require_text("record_id", raw.get("record_id"))
    run_slot = _require_text("run_slot", raw.get("run_slot"))
    if phase == "scored" and path == "autonomous" and run_slot != case.run_slot:
        raise AP4EvidenceError(
            f"{case_id}: scored autonomous run must use frozen slot {case.run_slot}"
        )
    if phase == "post_fix" and not _require_text("pre_fix_record_id", raw.get("pre_fix_record_id")):
        raise AP4EvidenceError("post_fix run requires pre_fix_record_id")

    contract_versions = raw.get("contract_versions")
    if phase == "post_fix":
        if not isinstance(contract_versions, dict):
            raise AP4EvidenceError("post_fix run requires contract_versions")
        expected_versions = current_contract_versions()
        normalized_versions = {str(key): str(value) for key, value in contract_versions.items()}
        if normalized_versions != expected_versions:
            raise AP4EvidenceError(
                "post_fix contract_versions must match the code used for the rerun"
            )
    else:
        normalized_versions = dict(validation.manifest.versions)

    source_hash = _require_text("source_pack_hash", raw.get("source_pack_hash"))
    if source_hash != validation.source_hashes[case_id]:
        raise AP4EvidenceError(f"{case_id}: source pack hash differs from frozen pack")

    times_raw = raw.get("times")
    if not isinstance(times_raw, dict):
        raise AP4EvidenceError("times must be an object")
    unknown_time_keys = set(times_raw) - set(TIME_KEYS)
    if unknown_time_keys:
        raise AP4EvidenceError(f"unknown time keys: {sorted(unknown_time_keys)}")
    times = {key: _nonnegative_number(key, times_raw.get(key, 0)) for key in TIME_KEYS}

    quality_raw = raw.get("quality")
    if not isinstance(quality_raw, dict):
        raise AP4EvidenceError("quality must be an object")

    source_claims = _nonnegative_int(
        "source_derived_claims", quality_raw.get("source_derived_claims", 0)
    )
    provenance_resolved = _nonnegative_int(
        "provenance_resolved_claims", quality_raw.get("provenance_resolved_claims", 0)
    )
    if provenance_resolved > source_claims:
        raise AP4EvidenceError("resolved provenance cannot exceed source-derived claims")

    consistency_pass = quality_raw.get("cross_domain_consistent")
    if not isinstance(consistency_pass, bool):
        raise AP4EvidenceError("cross_domain_consistent must be boolean")
    expected_outcome_pass = quality_raw.get("expected_outcome_pass")
    if not isinstance(expected_outcome_pass, bool):
        raise AP4EvidenceError("expected_outcome_pass must be boolean")

    return {
        "record_id": record_id,
        "case_id": case_id,
        "run_slot": run_slot,
        "phase": phase,
        "path": path,
        "status": _require_text("status", raw.get("status")),
        "source_pack_hash": source_hash,
        "times": times,
        "manual_fields_changed": _nonnegative_int(
            "manual_fields_changed", raw.get("manual_fields_changed", 0)
        ),
        "post_draft_fields_changed": _nonnegative_int(
            "post_draft_fields_changed", raw.get("post_draft_fields_changed", 0)
        ),
        "avoidable_questions": _nonnegative_int(
            "avoidable_questions", raw.get("avoidable_questions", 0)
        ),
        "authority_questions": _nonnegative_int(
            "authority_questions", raw.get("authority_questions", 0)
        ),
        "quality": {
            "source_derived_claims": source_claims,
            "provenance_resolved_claims": provenance_resolved,
            "hallucinated_facts": _nonnegative_int(
                "hallucinated_facts", quality_raw.get("hallucinated_facts", 0)
            ),
            "cross_domain_consistent": consistency_pass,
            "expected_outcome_pass": expected_outcome_pass,
        },
        "pre_fix_record_id": str(raw.get("pre_fix_record_id") or "").strip(),
        "contract_versions": normalized_versions,
        "notes": str(raw.get("notes") or "").strip(),
    }


def load_records(
    path: str | Path,
    *,
    validation: FrozenValidation,
) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AP4EvidenceError(f"invalid JSON on line {line_number}") from exc
        if not isinstance(raw, dict):
            raise AP4EvidenceError(f"record on line {line_number} must be an object")
        records.append(normalize_record(raw, validation=validation))
    _validate_record_uniqueness(records)
    return records


def _validate_record_uniqueness(records: Iterable[Mapping[str, Any]]) -> None:
    ids: set[str] = set()
    scored_slots: set[tuple[str, str]] = set()
    known_records: dict[str, Mapping[str, Any]] = {}
    latest_by_key: dict[tuple[str, str], str] = {}

    for record in records:
        record_id = str(record["record_id"])
        if record_id in ids:
            raise AP4EvidenceError(f"duplicate record_id: {record_id}")
        ids.add(record_id)

        key = (str(record["case_id"]), str(record["path"]))
        if record["phase"] == "scored":
            if key in scored_slots:
                raise AP4EvidenceError(
                    "success sampling forbidden: scored slot already recorded for "
                    f"{key[0]}/{key[1]}"
                )
            scored_slots.add(key)
        else:
            pre_fix = str(record.get("pre_fix_record_id") or "")
            predecessor = known_records.get(pre_fix)
            if predecessor is None:
                raise AP4EvidenceError(
                    f"post_fix record references unknown earlier record: {pre_fix}"
                )
            predecessor_key = (
                str(predecessor["case_id"]),
                str(predecessor["path"]),
            )
            if predecessor_key != key:
                raise AP4EvidenceError(
                    "post_fix record must reference the same case and path as its predecessor"
                )
            if latest_by_key.get(key) != pre_fix:
                raise AP4EvidenceError(
                    "post_fix chain must continue from the latest record; branching is forbidden"
                )

        known_records[record_id] = record
        latest_by_key[key] = record_id


def append_record(
    path: str | Path,
    raw: Mapping[str, Any],
    *,
    validation: FrozenValidation,
) -> dict[str, Any]:
    record = normalize_record(raw, validation=validation)
    existing = load_records(path, validation=validation)
    _validate_record_uniqueness([*existing, record])

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def _active_human_seconds(record: Mapping[str, Any]) -> float:
    times = record["times"]
    return sum(
        float(times[key])
        for key in (
            "active_input_seconds",
            "navigation_seconds",
            "authority_decision_seconds",
            "post_draft_review_seconds",
            "post_draft_correction_seconds",
        )
    )


def _post_draft_rework_seconds(record: Mapping[str, Any]) -> float:
    times = record["times"]
    return float(times["post_draft_review_seconds"]) + float(times["post_draft_correction_seconds"])


def _summary_view(
    autonomous: list[Mapping[str, Any]],
    manual: list[Mapping[str, Any]],
    *,
    validation: FrozenValidation,
) -> dict[str, Any]:
    autonomous_by_case = {record["case_id"]: record for record in autonomous}
    manual_by_case = {record["case_id"]: record for record in manual}
    baseline_ids = validation.manifest.baseline_case_ids

    paired = [
        (manual_by_case[case_id], autonomous_by_case[case_id])
        for case_id in baseline_ids
        if case_id in manual_by_case and case_id in autonomous_by_case
    ]

    targets = validation.manifest.metric_targets
    active_values = [_active_human_seconds(record) for record in autonomous]
    question_values = [int(record["avoidable_questions"]) for record in autonomous]

    source_claims = sum(int(record["quality"]["source_derived_claims"]) for record in autonomous)
    resolved_claims = sum(
        int(record["quality"]["provenance_resolved_claims"]) for record in autonomous
    )
    hallucinations = sum(int(record["quality"]["hallucinated_facts"]) for record in autonomous)

    baseline_fields = sum(int(base["manual_fields_changed"]) for base, _new in paired)
    autonomous_fields = sum(int(new["manual_fields_changed"]) for _base, new in paired)
    field_reduction = 1.0 - (autonomous_fields / baseline_fields) if baseline_fields > 0 else None

    baseline_active = sum(_active_human_seconds(base) for base, _new in paired)
    rework_seconds = sum(_post_draft_rework_seconds(new) for _base, new in paired)
    rework_ratio = rework_seconds / baseline_active if baseline_active > 0 else None

    provenance_ratio = resolved_claims / source_claims if source_claims else 1.0
    active_median = statistics.median(active_values) if active_values else None
    question_median = statistics.median(question_values) if question_values else None

    scored_case_ids = {record["case_id"] for record in autonomous}
    frozen_case_ids = {case.case_id for case in validation.manifest.cases}

    metrics = {
        "active_human_work_median_seconds": active_median,
        "manual_field_reduction": field_reduction,
        "avoidable_questions_median": question_median,
        "provenance_ratio": provenance_ratio,
        "hallucinated_facts": hallucinations,
        "cross_domain_consistency_all_pass": all(
            bool(record["quality"]["cross_domain_consistent"]) for record in autonomous
        )
        if autonomous
        else False,
        "expected_outcome_all_pass": all(
            bool(record["quality"]["expected_outcome_pass"]) for record in autonomous
        )
        if autonomous
        else False,
        "human_rework_ratio": rework_ratio,
    }
    checks = {
        "active_human_work": active_median is not None
        and active_median <= targets["active_human_work_median_seconds_max"],
        "manual_field_reduction": field_reduction is not None
        and field_reduction >= targets["manual_field_reduction_min"],
        "avoidable_questions": question_median is not None
        and question_median <= targets["avoidable_questions_median_max"],
        "provenance": provenance_ratio >= targets["provenance_ratio_min"],
        "hallucinations": hallucinations <= targets["hallucinated_facts_max"],
        "cross_domain_consistency": bool(autonomous)
        and all(bool(record["quality"]["cross_domain_consistent"]) for record in autonomous),
        "expected_outcome": bool(autonomous)
        and all(bool(record["quality"]["expected_outcome_pass"]) for record in autonomous),
        "human_rework": rework_ratio is not None
        and rework_ratio <= targets["human_rework_ratio_max"],
    }
    return {
        "population": {
            "autonomous_cases": len(autonomous),
            "missing_cases": sorted(frozen_case_ids - scored_case_ids),
            "paired_baseline_cases": [base["case_id"] for base, _new in paired],
        },
        "metrics": metrics,
        "pass": checks,
    }


def _current_autonomous_records(
    records: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    current: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if record["path"] != "autonomous":
            continue
        current[str(record["case_id"])] = record
    return list(current.values())


def summarize_records(
    records: Iterable[Mapping[str, Any]],
    *,
    validation: FrozenValidation,
) -> dict[str, Any]:
    records = list(records)
    scored = [record for record in records if record["phase"] == "scored"]
    initial_autonomous = [record for record in scored if record["path"] == "autonomous"]
    manual = [record for record in scored if record["path"] == "manual"]
    current_autonomous = _current_autonomous_records(records)

    initial = _summary_view(initial_autonomous, manual, validation=validation)
    post_hardening = _summary_view(current_autonomous, manual, validation=validation)

    frozen_case_ids = {case.case_id for case in validation.manifest.cases}
    post_fix_case_ids = {
        str(record["case_id"])
        for record in records
        if record["phase"] == "post_fix" and record["path"] == "autonomous"
    }

    return {
        "population": {
            "frozen_cases": len(frozen_case_ids),
            "scored_autonomous_cases": initial["population"]["autonomous_cases"],
            "missing_scored_cases": initial["population"]["missing_cases"],
            "paired_baseline_cases": initial["population"]["paired_baseline_cases"],
            "post_fix_runs": sum(1 for record in records if record["phase"] == "post_fix"),
            "post_hardening_autonomous_cases": post_hardening["population"]["autonomous_cases"],
            "post_hardening_cases": sorted(post_fix_case_ids),
        },
        "metrics": initial["metrics"],
        "pass": initial["pass"],
        "post_hardening_metrics": post_hardening["metrics"],
        "post_hardening_pass": post_hardening["pass"],
        "targets": dict(validation.manifest.metric_targets),
    }


def render_summary_markdown(summary: Mapping[str, Any]) -> str:
    population = summary["population"]

    def display(value: object, *, percent: bool = False) -> str:
        if value is None:
            return "offen"
        if percent:
            return f"{float(value) * 100:.1f}%"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    def metric_rows(metrics: Mapping[str, Any], checks: Mapping[str, Any]) -> list[str]:
        return [
            (
                "| Aktive Human Work Median | "
                f"{display(metrics['active_human_work_median_seconds'])} s | "
                f"{'PASS' if checks['active_human_work'] else 'OPEN/FAIL'} |"
            ),
            (
                "| Manuelle Feldpflege Reduktion | "
                f"{display(metrics['manual_field_reduction'], percent=True)} | "
                f"{'PASS' if checks['manual_field_reduction'] else 'OPEN/FAIL'} |"
            ),
            (
                "| Vermeidbare Rückfragen Median | "
                f"{display(metrics['avoidable_questions_median'])} | "
                f"{'PASS' if checks['avoidable_questions'] else 'OPEN/FAIL'} |"
            ),
            (
                "| Provenance | "
                f"{display(metrics['provenance_ratio'], percent=True)} | "
                f"{'PASS' if checks['provenance'] else 'OPEN/FAIL'} |"
            ),
            (
                "| Halluzinierte Fakten/Messwerte | "
                f"{display(metrics['hallucinated_facts'])} | "
                f"{'PASS' if checks['hallucinations'] else 'OPEN/FAIL'} |"
            ),
            (
                "| Cross-Domain-Konsistenz | "
                f"{display(metrics['cross_domain_consistency_all_pass'])} | "
                f"{'PASS' if checks['cross_domain_consistency'] else 'OPEN/FAIL'} |"
            ),
            (
                "| Fachlich erwarteter Endzustand | "
                f"{display(metrics['expected_outcome_all_pass'])} | "
                f"{'PASS' if checks['expected_outcome'] else 'OPEN/FAIL'} |"
            ),
            (
                "| Menschliche Nacharbeit | "
                f"{display(metrics['human_rework_ratio'], percent=True)} | "
                f"{'PASS' if checks['human_rework'] else 'OPEN/FAIL'} |"
            ),
        ]

    lines = [
        "# AP4 Evidence Summary",
        "",
        f"- Eingefrorene Fälle: **{population['frozen_cases']}**",
        f"- Gewertete autonome Fälle: **{population['scored_autonomous_cases']}**",
        (
            "- Fehlende gewertete Slots: **"
            f"{', '.join(population['missing_scored_cases']) or 'keine'}**"
        ),
        (
            "- Gepaarte E2E-Baselines: **"
            f"{', '.join(population['paired_baseline_cases']) or 'keine'}**"
        ),
        f"- Dokumentierte Post-Fix-Runs: **{population['post_fix_runs']}**",
        (f"- Post-Hardening-Fälle: **{', '.join(population['post_hardening_cases']) or 'keine'}**"),
        "",
        "## Initial scored result",
        "",
        "| Kriterium | Ergebnis | Status |",
        "|---|---:|---|",
        *metric_rows(summary["metrics"], summary["pass"]),
        "",
        "## Current post-hardening result",
        "",
        "Diese Sicht verwendet pro Fall den letzten linear verketteten Record. "
        "Der ursprüngliche scored Run bleibt unverändert erhalten.",
        "",
        "| Kriterium | Ergebnis | Status |",
        "|---|---:|---|",
        *metric_rows(summary["post_hardening_metrics"], summary["post_hardening_pass"]),
        "",
        "Blind Human Review wird separat dokumentiert und ist kein LLM-Ersatz.",
    ]
    return "\n".join(lines) + "\n"
