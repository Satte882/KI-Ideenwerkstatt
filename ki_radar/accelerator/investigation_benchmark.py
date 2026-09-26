from __future__ import annotations

from dataclasses import replace
from typing import Any

from .investigation_evidence import campaign_budget_snapshot
from .investigation_llm import PlannerAction, request_planner_action
from .investigation_loop import AdvanceResult, run_until_boundary
from .investigation_models import (
    InvestigationEvidenceCampaign,
    InvestigationProviderReservation,
    InvestigationRun,
    InvestigationSource,
    InvestigationSourceSnapshot,
    InvestigationStep,
)
from .investigation_policy import ReasonCode
from .investigation_runtime import (
    FIXED_ROUTE_VERSION,
    InvestigationRunError,
    execute_tool_step,
    mark_counterevidence_processed,
    set_source_relevance,
)

FIXED_COUNTEREVIDENCE_QUERY = "nicht"
FIXED_READ_LIMIT = 100
FIXED_MAX_GROUP_CHECKS = 3
_OUTCOME_MARKERS = ("hour", "duration", "time", "lead", "cycle", "latency", "day", "minute")

BENCHMARK_VARIANT_FILENAMES = {
    "A": ("01_case_note.md", "02_counterevidence.md", "cases.csv"),
    "B": ("01_case_note.md", "02_report.md", "cases.csv"),
    "C": ("01_case_note.md", "02_system_note.md", "cases.csv"),
}
SCORED_ATTEMPTS = {
    "adaptive": frozenset({1, 2, 3}),
    "fixed": frozenset({1}),
}


def scored_sample_slot_counts(
    campaign: InvestigationEvidenceCampaign,
) -> dict[tuple[str, str, int], int]:
    """Count only the predeclared real scored slots; post-fix runs never enter this sample."""
    counts: dict[tuple[str, str, int], int] = {}
    for run in campaign.investigation_runs.all():
        metadata = dict(run.evidence_metadata or {})
        if (
            str(metadata.get("provider_mode") or "") != "real"
            or str(metadata.get("phase") or "") != "scored"
        ):
            continue
        variant = str(metadata.get("variant") or "").upper()
        mode = str(run.execution_mode or "")
        allowed = SCORED_ATTEMPTS.get(mode)
        try:
            attempt = int(metadata.get("attempt"))
        except (TypeError, ValueError):
            continue
        if variant not in {"A", "B", "C"} or allowed is None or attempt not in allowed:
            continue
        key = (variant, mode, attempt)
        counts[key] = counts.get(key, 0) + 1
    return counts


def scored_sample_is_frozen(campaign: InvestigationEvidenceCampaign) -> bool:
    counts = scored_sample_slot_counts(campaign)
    expected = {
        (variant, mode, attempt)
        for variant in ("A", "B", "C")
        for mode, attempts in SCORED_ATTEMPTS.items()
        for attempt in attempts
    }
    return set(counts) == expected and all(counts[key] == 1 for key in expected)


EXPECTED_ANALYSIS_GROUP = {
    "A": "approver_available",
    "C": "queue_retries",
}


def _variant_runs(
    campaign: InvestigationEvidenceCampaign,
    *,
    variant: str,
) -> list[InvestigationRun]:
    result: list[InvestigationRun] = []
    for run in campaign.investigation_runs.select_related("source_snapshot").order_by("created_at"):
        metadata = dict(run.evidence_metadata or {})
        if (
            str(metadata.get("provider_mode") or "") == "real"
            and str(metadata.get("variant") or "").upper() == variant
        ):
            result.append(run)
    return result


def _snapshot_signature(snapshot: InvestigationSourceSnapshot) -> tuple[str, ...]:
    return tuple(snapshot.sources.order_by("filename").values_list("filename", flat=True))


def assert_variant_snapshot(
    *,
    snapshot: InvestigationSourceSnapshot,
    variant: str,
) -> None:
    expected = BENCHMARK_VARIANT_FILENAMES.get(variant)
    if expected is None:
        raise InvestigationRunError(
            "Unbekannte Benchmark-Variante.",
            code="invalid_benchmark_variant",
        )
    if _snapshot_signature(snapshot) != expected:
        raise InvestigationRunError(
            "Der Source-Snapshot entspricht nicht dem eingefrorenen A/B/C-Quellenpaket.",
            code="benchmark_variant_snapshot_mismatch",
        )


def resolve_benchmark_snapshot(
    *,
    campaign: InvestigationEvidenceCampaign,
    variant: str,
    phase: str,
    requested_snapshot_id=None,
) -> InvestigationSourceSnapshot:
    variant = variant.upper()
    existing = _variant_runs(campaign, variant=variant)
    bindings = {(str(run.source_snapshot_id), str(run.manifest_hash)) for run in existing}
    if len(bindings) > 1:
        raise InvestigationRunError(
            "Die Variante besitzt widersprüchliche Snapshot-Bindungen.",
            code="benchmark_snapshot_binding_conflict",
        )

    if bindings:
        snapshot_id, manifest_hash = next(iter(bindings))
        if requested_snapshot_id is not None and str(requested_snapshot_id) != snapshot_id:
            raise InvestigationRunError(
                "Die Variante ist bereits an einen anderen Source-Snapshot gebunden.",
                code="benchmark_snapshot_binding_conflict",
            )
        snapshot = InvestigationSourceSnapshot.objects.select_related("folder").get(pk=snapshot_id)
        if snapshot.manifest_hash != manifest_hash:
            raise InvestigationRunError(
                "Die eingefrorene Manifest-Bindung der Variante stimmt nicht mehr.",
                code="benchmark_snapshot_binding_conflict",
            )
    else:
        if phase == "scored":
            raise InvestigationRunError(
                "Vor einem gewerteten Lauf muss die Variante in der Kalibrierung an einen "
                "Source-Snapshot gebunden werden.",
                code="benchmark_calibration_required",
            )
        if phase == "post_fix":
            raise InvestigationRunError(
                "Post-Fix-Verifikation darf nur die bereits eingefrorene Snapshot-Bindung "
                "der Variante wiederverwenden.",
                code="benchmark_post_fix_binding_required",
            )
        if requested_snapshot_id is None:
            raise InvestigationRunError(
                "Der erste Kalibrierungslauf einer Variante benötigt einen expliziten Snapshot.",
                code="benchmark_snapshot_required",
            )
        try:
            snapshot = InvestigationSourceSnapshot.objects.select_related("folder").get(
                pk=requested_snapshot_id,
                process_analysis=campaign.process_analysis,
            )
        except (InvestigationSourceSnapshot.DoesNotExist, ValueError) as exc:
            raise InvestigationRunError(
                "Der angegebene Benchmark-Snapshot ist für diese Campaign nicht verfügbar.",
                code="benchmark_snapshot_invalid",
            ) from exc

        other_bindings = {
            (str(run.source_snapshot_id), str(run.manifest_hash))
            for run in campaign.investigation_runs.select_related("source_snapshot").all()
            if str((run.evidence_metadata or {}).get("provider_mode") or "") == "real"
            and str((run.evidence_metadata or {}).get("variant") or "").upper() != variant
        }
        if (str(snapshot.pk), str(snapshot.manifest_hash)) in other_bindings:
            raise InvestigationRunError(
                "Ein Benchmark-Snapshot darf nicht mehreren A/B/C-Varianten zugeordnet werden.",
                code="benchmark_snapshot_reused_across_variants",
            )

    if snapshot.process_analysis_id != campaign.process_analysis_id:
        raise InvestigationRunError(
            "Der Benchmark-Snapshot gehört nicht zur Campaign.",
            code="benchmark_snapshot_invalid",
        )
    if phase != "post_fix" and snapshot.process_version != campaign.process_analysis.version:
        raise InvestigationRunError(
            "Der Benchmark-Snapshot gehört nicht zur aktuellen ProcessAnalysis-Version.",
            code="benchmark_snapshot_stale",
        )
    if not snapshot.folder.is_active:
        raise InvestigationRunError(
            "Der gebundene Benchmark-Quellenraum ist nicht mehr autorisiert.",
            code="benchmark_snapshot_inactive",
        )
    assert_variant_snapshot(snapshot=snapshot, variant=variant)
    return snapshot


def validate_evidence_attempt(
    *,
    campaign: InvestigationEvidenceCampaign,
    variant: str,
    mode: str,
    phase: str,
    attempt: int,
) -> None:
    if phase == "calibration":
        scored_started = any(
            str((run.evidence_metadata or {}).get("provider_mode") or "") == "real"
            and str((run.evidence_metadata or {}).get("phase") or "") == "scored"
            for run in campaign.investigation_runs.all()
        )
        if scored_started:
            raise InvestigationRunError(
                "Nach Beginn der gewerteten Phase sind keine neuen Kalibrierungsläufe erlaubt.",
                code="benchmark_scoring_already_started",
            )
        return

    if phase == "post_fix":
        if not scored_sample_is_frozen(campaign):
            raise InvestigationRunError(
                "Post-Fix-Verifikation ist erst nach exakt einem eingefrorenen Real-Run "
                "für jeden der 12 vorab definierten Scored-Slots erlaubt.",
                code="benchmark_post_fix_before_sample_complete",
            )
        return

    if phase != "scored":
        raise InvestigationRunError(
            "Unbekannte Evidence-Phase.",
            code="invalid_benchmark_phase",
        )

    allowed = SCORED_ATTEMPTS.get(mode)
    if allowed is None or attempt not in allowed:
        expected = ", ".join(str(value) for value in sorted(allowed or ()))
        raise InvestigationRunError(
            f"Gewertete {mode}-Versuche sind vorab auf Attempts {expected} fixiert.",
            code="benchmark_attempt_out_of_sample",
        )


def _fixed_reference(source: InvestigationSource) -> dict[str, Any]:
    if source.source_type in {
        InvestigationSource.SourceType.TEXT,
        InvestigationSource.SourceType.MARKDOWN,
    }:
        locator = {"line": 1}
    else:
        locator = {
            "row": 1,
            "column": source.columns[0] if source.columns else None,
        }
    return {
        "source_id": str(source.pk),
        "revision_hash": source.content_sha256,
        "locator": locator,
    }


def _profile_columns(run: InvestigationRun, source_id) -> dict[str, dict[str, Any]]:
    step = (
        run.steps.filter(
            status="success",
            tool_name="profile_csv",
            parameters__source_id=str(source_id),
        )
        .order_by("-sequence")
        .first()
    )
    if step is None:
        return {}
    columns = step.result_payload.get("columns")
    return dict(columns) if isinstance(columns, dict) else {}


def _fixed_comparison_specs(
    source: InvestigationSource,
    columns: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    numeric = [
        name
        for name, metadata in columns.items()
        if metadata.get("type") in {"integer", "decimal"}
        and int(metadata.get("non_missing", 0)) > 0
    ]
    if not numeric:
        return []
    outcome = next(
        (name for name in numeric if any(marker in name.casefold() for marker in _OUTCOME_MARKERS)),
        numeric[0],
    )
    excluded_names = {outcome}
    unit_column = "unit" if "unit" in columns else None
    if unit_column:
        excluded_names.add(unit_column)
    group_candidates = [
        name
        for name, metadata in columns.items()
        if name not in excluded_names
        and "id" not in name.casefold()
        and int(metadata.get("non_missing", 0)) > 0
        and metadata.get("type") in {"string", "integer", "decimal", "boolean"}
    ][:FIXED_MAX_GROUP_CHECKS]
    return [
        {
            "source_id": str(source.pk),
            "group_by": group,
            "aggregation": "mean",
            "value_column": outcome,
            "filters": [],
            "unit_column": unit_column,
        }
        for group in group_candidates
    ]


def prepare_fixed_route(*, actor, run_id, executor_token) -> InvestigationRun:
    run = InvestigationRun.objects.select_related("source_snapshot").get(pk=run_id)
    if run.execution_mode != "fixed":
        raise InvestigationRunError(
            "Die feste Analysestrecke darf nur auf einem fixed-Run ausgeführt werden.",
            code="invalid_execution_mode",
        )
    if run.execution_snapshot.get("fixed_route_version") != FIXED_ROUTE_VERSION:
        raise InvestigationRunError(
            "Die fixierte Kontrollstrecke ist nicht verfügbar.",
            code="execution_version_unavailable",
        )

    execute_tool_step(
        actor=actor,
        run_id=run.pk,
        executor_token=executor_token,
        tool_name="search_sources",
        parameters={
            "query": FIXED_COUNTEREVIDENCE_QUERY,
            "cursor": 0,
            "limit": 20,
        },
        expected_discriminating_finding="Vorab definierte Gegenbelegsuche der Kontrollstrecke.",
    )

    sources = list(run.source_snapshot.sources.order_by("filename"))
    for source in sources:
        size = (
            source.row_count
            if source.source_type == InvestigationSource.SourceType.CSV
            else len(source.content.splitlines())
        )
        if size and size > FIXED_READ_LIMIT:
            raise InvestigationRunError(
                "Die feste VS1-Vergleichsstrecke ist nur für die eingefrorenen kleinen "
                "A/B/C-Packs definiert und darf größere Quellen nicht still abschneiden.",
                code="fixed_route_source_too_large",
            )
        execute_tool_step(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
            tool_name="read_source",
            parameters={
                "source_id": str(source.pk),
                "cursor": 0,
                "limit": FIXED_READ_LIMIT,
                "columns": [],
            },
            expected_discriminating_finding=(
                "Vollständiges Lesen der kleinen Benchmarkquelle ohne adaptive Auswahl."
            ),
        )

    for source in sources:
        if source.source_type != InvestigationSource.SourceType.CSV:
            continue
        execute_tool_step(
            actor=actor,
            run_id=run.pk,
            executor_token=executor_token,
            tool_name="profile_csv",
            parameters={"source_id": str(source.pk)},
            expected_discriminating_finding="Vorab definierter CSV-Profilcheck.",
        )
        run.refresh_from_db()
        columns = _profile_columns(run, source.pk)
        for spec in _fixed_comparison_specs(source, columns):
            execute_tool_step(
                actor=actor,
                run_id=run.pk,
                executor_token=executor_token,
                tool_name="compare_groups",
                parameters=spec,
                expected_discriminating_finding=(
                    "Deterministischer Gruppencheck der vorab definierten Kontrollstrecke."
                ),
            )

    run.refresh_from_db()
    mark_counterevidence_processed(
        actor=actor,
        run_id=run.pk,
        executor_token=executor_token,
    )
    relevance = {
        str(source.pk): {
            "relevant": True,
            "reason": "Quelle gehört zum vollständig gelesenen, autorisierten Benchmark-Pack.",
            "reference": _fixed_reference(source),
        }
        for source in sources
    }
    set_source_relevance(
        actor=actor,
        run_id=run.pk,
        executor_token=executor_token,
        relevance=relevance,
    )
    return InvestigationRun.objects.get(pk=run.pk)


def request_fixed_route_synthesis(
    *,
    actor,
    run: InvestigationRun,
    executor_token,
) -> PlannerAction:
    action = request_planner_action(
        actor=actor,
        run=run,
        executor_token=executor_token,
    )
    if action.action != "tool":
        return action
    return replace(
        action,
        action="clarify",
        tool_name="",
        parameters={},
        clarification_reason=ReasonCode.FIXED_ROUTE_BOUNDARY.value,
        clarification_payload={
            "impact": (
                "Die vor den gewerteten Läufen festgelegte Kontrollstrecke hat ihre "
                "Datenprüfungen ausgeschöpft; zusätzliche adaptive Exploration ist hier "
                "bewusst nicht erlaubt."
            ),
            "required_action": (
                "Als Grenze der festen Strecke berichten; nicht durch einen nachträglichen "
                "Toolschritt verbessern."
            ),
            "requested_tool": action.tool_name,
        },
    )


def run_fixed_route_until_boundary(*, actor, run_id, executor_token) -> AdvanceResult:
    prepare_fixed_route(
        actor=actor,
        run_id=run_id,
        executor_token=executor_token,
    )
    return run_until_boundary(
        actor=actor,
        run_id=run_id,
        executor_token=executor_token,
        planner=request_fixed_route_synthesis,
    )


def comparison_contract(run: InvestigationRun) -> dict[str, Any]:
    snapshot = run.execution_snapshot
    planner = snapshot.get("planner") or {}
    synthesizer = snapshot.get("synthesizer") or {}
    verifier = snapshot.get("verifier") or {}
    return {
        "process_version": snapshot.get("process_version"),
        "source_snapshot_id": snapshot.get("source_snapshot_id"),
        "manifest_hash": snapshot.get("manifest_hash"),
        "budget_limits": snapshot.get("budget_limits"),
        "model_transport": snapshot.get("model_transport"),
        "planner": {
            "prompt_version": planner.get("prompt_version"),
            "instruction_hash": planner.get("instruction_hash"),
            "schema_version": planner.get("schema_version"),
        },
        "synthesizer": {
            "prompt_version": synthesizer.get("prompt_version"),
            "instruction_hash": synthesizer.get("instruction_hash"),
            "schema_version": synthesizer.get("schema_version"),
        },
        "verifier": {
            "prompt_version": verifier.get("prompt_version"),
            "instruction_hash": verifier.get("instruction_hash"),
            "schema_version": verifier.get("schema_version"),
        },
        "tools": snapshot.get("tools"),
        "evidence_campaign": snapshot.get("evidence_campaign"),
    }


def assert_comparable_runs(*, fixed: InvestigationRun, adaptive: InvestigationRun) -> None:
    if fixed.execution_mode != "fixed" or adaptive.execution_mode != "adaptive":
        raise InvestigationRunError(
            "Vergleich benötigt genau einen fixed- und einen adaptive-Run.",
            code="comparison_arm_mismatch",
        )
    if comparison_contract(fixed) != comparison_contract(adaptive):
        raise InvestigationRunError(
            "Fixed und adaptive Strecke besitzen nicht dieselben Vergleichsbedingungen.",
            code="comparison_contract_mismatch",
        )


def _expected_analysis_observed(run: InvestigationRun, *, variant: str) -> bool:
    group_by = EXPECTED_ANALYSIS_GROUP.get(variant)
    if group_by is None:
        return True
    return run.steps.filter(
        status=InvestigationStep.Status.SUCCESS,
        tool_name="compare_groups",
        parameters__group_by=group_by,
    ).exists()


def _agentic_course_change_observed(run: InvestigationRun) -> bool:
    # Keep historical step markers readable, but the Lean-Reset runtime now
    # separates tool execution from synthesis. The authoritative course-change
    # signal is therefore an evidence-backed competing hypothesis that the
    # synthesizer has refuted or marked conflicting.
    if run.steps.filter(
        status=InvestigationStep.Status.SUCCESS,
        progress_kind__in=[
            InvestigationStep.ProgressKind.REFUTATION,
            InvestigationStep.ProgressKind.CONTRADICTION,
        ],
    ).exists():
        return True
    for item in run.claim_register:
        if str(item.get("area") or "") != "competing_hypotheses":
            continue
        status = str(item.get("status") or "")
        evidence_refs = item.get("evidence_refs") or []
        counterevidence_refs = item.get("counterevidence_refs") or []
        if status == "refuted" and counterevidence_refs:
            return True
        if status == "conflicting" and evidence_refs and counterevidence_refs:
            return True
    return False


def _benchmark_brief_complete(run: InvestigationRun) -> bool:
    """Issue-#4 method completeness, deliberately separate from runtime READY."""
    payload = run.brief_payload if isinstance(run.brief_payload, dict) else {}
    hypotheses = [item for item in payload.get("hypotheses", []) if isinstance(item, dict)]
    calculations = [item for item in payload.get("calculations", []) if isinstance(item, dict)]
    options = [item for item in payload.get("options", []) if isinstance(item, dict)]
    validation = payload.get("validation_step")
    return (
        len(hypotheses) >= 2
        and bool(calculations)
        and len(options) >= 2
        and any(bool(item.get("non_ai")) for item in options)
        and any(bool(item.get("status_quo")) for item in options)
        and isinstance(payload.get("risks_unknowns"), list)
        and isinstance(validation, dict)
        and bool(str(validation.get("step") or "").strip())
        and bool(str(validation.get("measurement") or "").strip())
    )


def _scored_run_reached_expected_boundary(
    run: InvestigationRun,
    *,
    variant: str,
) -> bool:
    if variant == "B":
        return run.clarification_reason == ReasonCode.MISSING_EVIDENCE.value and run.status in {
            InvestigationRun.Status.WAITING_HUMAN,
            InvestigationRun.Status.ABORTED,
        }
    if (
        run.status != InvestigationRun.Status.READY
        or not _expected_analysis_observed(run, variant=variant)
        or not _benchmark_brief_complete(run)
    ):
        return False
    if run.execution_mode == "fixed":
        return True
    return (
        run.data_check_executed
        and run.counterevidence_search_executed
        and run.counterevidence_hits_processed
        and _agentic_course_change_observed(run)
    )


def evidence_campaign_report(campaign: InvestigationEvidenceCampaign) -> dict[str, Any]:
    runs = list(campaign.investigation_runs.order_by("created_at"))
    reservations = list(
        campaign.provider_reservations.select_related("run", "model_call").order_by("created_at")
    )
    reservations_by_run: dict[str, list[InvestigationProviderReservation]] = {}
    for reservation in reservations:
        reservations_by_run.setdefault(str(reservation.run_id), []).append(reservation)

    matrix: dict[str, dict[str, int]] = {
        variant: {
            "adaptive_real_attempted": 0,
            "adaptive_real_scored": 0,
            "adaptive_real_sampled": 0,
            "fixed_real_attempted": 0,
            "fixed_real_scored": 0,
            "fixed_real_sampled": 0,
        }
        for variant in ("A", "B", "C")
    }
    usage_by_arm: dict[str, dict[str, int]] = {}
    usage_by_variant: dict[str, dict[str, int]] = {}
    attempts: list[dict[str, Any]] = []
    sample_runs: dict[tuple[str, str, int], list[InvestigationRun]] = {}

    def add_usage(bucket: dict[str, dict[str, int]], key: str, values: dict[str, int]) -> None:
        target = bucket.setdefault(
            key or "unspecified",
            {
                "tool_calls": 0,
                "model_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "provider_calls": 0,
                "cost_microunits": 0,
            },
        )
        for metric, value in values.items():
            target[metric] += int(value)

    for run in runs:
        metadata = dict(run.evidence_metadata or {})
        variant = str(metadata.get("variant") or "").upper()
        phase = str(metadata.get("phase") or "")
        provider_mode = str(metadata.get("provider_mode") or "unspecified")
        attempt_number = metadata.get("attempt")
        if (
            variant in matrix
            and phase == "scored"
            and provider_mode == "real"
            and run.execution_mode in {"adaptive", "fixed"}
        ):
            attempted_key = f"{run.execution_mode}_real_attempted"
            matrix[variant][attempted_key] += 1
            try:
                normalized_attempt = int(attempt_number)
            except (TypeError, ValueError):
                normalized_attempt = 0
            if normalized_attempt in SCORED_ATTEMPTS[run.execution_mode]:
                sample_runs.setdefault(
                    (variant, run.execution_mode, normalized_attempt),
                    [],
                ).append(run)
                if _scored_run_reached_expected_boundary(run, variant=variant):
                    scored_key = f"{run.execution_mode}_real_scored"
                    matrix[variant][scored_key] += 1

        run_reservations = reservations_by_run.get(str(run.pk), [])
        provider_calls = len(run_reservations)
        cost_microunits = sum(
            int(item.actual_cost_microunits or 0)
            for item in run_reservations
            if item.status == InvestigationProviderReservation.Status.SETTLED
        )
        usage = {
            "tool_calls": int(run.usage.get("tool_calls", 0)),
            "model_calls": int(run.usage.get("model_calls", 0)),
            "input_tokens": int(run.usage.get("input_tokens", 0)),
            "output_tokens": int(run.usage.get("output_tokens", 0)),
            "provider_calls": provider_calls,
            "cost_microunits": cost_microunits,
        }
        add_usage(usage_by_arm, run.execution_mode, usage)
        add_usage(usage_by_variant, variant, usage)

        runtime_seconds = None
        if run.finished_at is not None:
            runtime_seconds = max(0, int((run.finished_at - run.started_at).total_seconds()))
        attempts.append(
            {
                "run_id": str(run.pk),
                "variant": variant,
                "phase": phase,
                "provider_mode": provider_mode,
                "arm": run.execution_mode,
                "attempt": attempt_number,
                "status": run.status,
                "clarification_reason": run.clarification_reason,
                "runtime_seconds": runtime_seconds,
                "benchmark_brief_complete": _benchmark_brief_complete(run),
                **usage,
            }
        )

    sample_issues: list[str] = []
    review_run_ids: dict[str, list[str]] = {variant: [] for variant in ("A", "B", "C")}
    fixed_runs: dict[str, InvestigationRun] = {}
    adaptive_runs: dict[str, list[InvestigationRun]] = {variant: [] for variant in ("A", "B", "C")}

    for variant in ("A", "B", "C"):
        for mode, required_attempts in SCORED_ATTEMPTS.items():
            for attempt_number in sorted(required_attempts):
                key = (variant, mode, attempt_number)
                matched = sample_runs.get(key, [])
                if len(matched) != 1:
                    sample_issues.append(
                        f"{variant}/{mode}/attempt-{attempt_number}: erwartet genau ein "
                        f"gewerteter Run, gefunden {len(matched)}."
                    )
                    continue
                run = matched[0]
                matrix[variant][f"{mode}_real_sampled"] += 1
                if mode == "adaptive":
                    adaptive_runs[variant].append(run)
                    review_run_ids[variant].append(str(run.pk))
                else:
                    fixed_runs[variant] = run

    comparison_issues: list[str] = []
    for variant in ("A", "B", "C"):
        fixed = fixed_runs.get(variant)
        if fixed is None:
            continue
        for adaptive in adaptive_runs[variant]:
            try:
                assert_comparable_runs(fixed=fixed, adaptive=adaptive)
            except InvestigationRunError as exc:
                comparison_issues.append(
                    f"{variant}: Fixed {fixed.pk} und Adaptive {adaptive.pk} sind nicht "
                    f"vergleichbar ({exc.code})."
                )

    reservation_summary = {
        status: sum(1 for item in reservations if item.status == status)
        for status in (
            InvestigationProviderReservation.Status.OPEN,
            InvestigationProviderReservation.Status.SETTLED,
            InvestigationProviderReservation.Status.UNCERTAIN,
        )
    }
    outstanding: list[str] = []
    for variant in ("A", "B", "C"):
        adaptive_sample_missing = max(0, 3 - matrix[variant]["adaptive_real_sampled"])
        if adaptive_sample_missing:
            outstanding.append(
                f"{variant}: {adaptive_sample_missing} vorab fixierte adaptive gewertete "
                "Läufe fehlen."
            )
        adaptive_failed = max(
            0,
            matrix[variant]["adaptive_real_sampled"] - matrix[variant]["adaptive_real_scored"],
        )
        if adaptive_failed:
            outstanding.append(
                f"{variant}: {adaptive_failed} gewertete adaptive Läufe erfüllen den "
                "fachlichen/agentischen Prüfpunkt nicht."
            )
        if matrix[variant]["fixed_real_sampled"] < 1:
            outstanding.append(f"{variant}: vorab fixierter Fixed-Route-Vergleich fehlt.")
    outstanding.extend(sample_issues)
    outstanding.extend(comparison_issues)
    outstanding.extend(
        [
            "Unabhängiger verblindeter menschlicher Fachreview ist noch nicht dokumentiert.",
            "Aktive menschliche Bearbeitungszeit ist noch nicht gemessen.",
        ]
    )

    nine_real_adaptive_complete = all(
        matrix[variant]["adaptive_real_sampled"] == 3 for variant in ("A", "B", "C")
    ) and not any("/adaptive/" in item for item in sample_issues)
    nine_real_adaptive_passed = all(
        matrix[variant]["adaptive_real_scored"] == 3 for variant in ("A", "B", "C")
    )
    fixed_sample_complete = all(
        matrix[variant]["fixed_real_sampled"] == 1 for variant in ("A", "B", "C")
    ) and not any("/fixed/" in item for item in sample_issues)
    fixed_comparison_present = fixed_sample_complete and not comparison_issues
    return {
        "budget": campaign_budget_snapshot(campaign),
        "fixed_route_version": FIXED_ROUTE_VERSION,
        "matrix": matrix,
        "nine_real_adaptive_runs_complete": nine_real_adaptive_complete,
        "nine_real_adaptive_runs_passed": nine_real_adaptive_passed,
        "fixed_comparison_present": fixed_comparison_present,
        "effectiveness_proof_complete": False,
        "attempts": attempts,
        "scored_sample_run_ids": review_run_ids,
        "sample_issues": sample_issues,
        "comparison_issues": comparison_issues,
        "usage_by_arm": usage_by_arm,
        "usage_by_variant": usage_by_variant,
        "provider_reservations": reservation_summary,
        "outstanding_requirements": outstanding,
        "human_active_time_seconds": None,
        "independent_human_review": "not_recorded",
        "ten_x_claim_allowed": False,
    }
