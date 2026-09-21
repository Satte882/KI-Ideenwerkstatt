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
    return run.status == InvestigationRun.Status.READY


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
            "fixed_real_attempted": 0,
            "fixed_real_scored": 0,
        }
        for variant in ("A", "B", "C")
    }
    usage_by_arm: dict[str, dict[str, int]] = {}
    usage_by_variant: dict[str, dict[str, int]] = {}
    attempts: list[dict[str, Any]] = []

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
        if (
            variant in matrix
            and phase == "scored"
            and provider_mode == "real"
            and run.execution_mode in {"adaptive", "fixed"}
        ):
            attempted_key = f"{run.execution_mode}_real_attempted"
            matrix[variant][attempted_key] += 1
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
                "status": run.status,
                "clarification_reason": run.clarification_reason,
                "runtime_seconds": runtime_seconds,
                **usage,
            }
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
        adaptive_missing = max(0, 3 - matrix[variant]["adaptive_real_scored"])
        if adaptive_missing:
            outstanding.append(
                f"{variant}: {adaptive_missing} reale adaptive gewertete Läufe fehlen."
            )
        if matrix[variant]["fixed_real_scored"] < 1:
            outstanding.append(f"{variant}: realer Fixed-Route-Vergleich fehlt.")
    outstanding.extend(
        [
            "Unabhängiger verblindeter menschlicher Fachreview ist noch nicht dokumentiert.",
            "Aktive menschliche Bearbeitungszeit ist noch nicht gemessen.",
        ]
    )

    nine_real_adaptive_complete = all(
        matrix[variant]["adaptive_real_scored"] >= 3 for variant in ("A", "B", "C")
    )
    fixed_comparison_present = all(
        matrix[variant]["fixed_real_scored"] >= 1 for variant in ("A", "B", "C")
    )
    return {
        "budget": campaign_budget_snapshot(campaign),
        "fixed_route_version": FIXED_ROUTE_VERSION,
        "matrix": matrix,
        "nine_real_adaptive_runs_complete": nine_real_adaptive_complete,
        "fixed_comparison_present": fixed_comparison_present,
        "effectiveness_proof_complete": False,
        "attempts": attempts,
        "usage_by_arm": usage_by_arm,
        "usage_by_variant": usage_by_variant,
        "provider_reservations": reservation_summary,
        "outstanding_requirements": outstanding,
        "human_active_time_seconds": None,
        "independent_human_review": "not_recorded",
        "ten_x_claim_allowed": False,
    }
