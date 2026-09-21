from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from .models import SolutionGenerationRun, SolutionQualityRun
from .solution_critic_contract import (
    SolutionCriticContractError,
    validate_solution_critic_payload,
)
from .solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from .solution_generation_effective import (
    SolutionGenerationEffectivePayloadError,
    normalize_solution_generation_edits,
)
from .solution_generation_sources import build_solution_generation_source_context
from .solution_quality_runs import (
    SolutionQualityRunError,
    reserve_solution_quality_step,
)
from .solution_quality_snapshot import build_solution_quality_snapshot
from .solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
    REPAIR_PROMPT_VERSION,
    REPAIR_SCHEMA_VERSION,
)


class SolutionRepairContractError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        stale_reason: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.stale_reason = stale_reason


@dataclass(frozen=True)
class SolutionRepairTarget:
    option: str
    field: str

    def as_dict(self) -> dict[str, str]:
        return {"option": self.option, "field": self.field}


@dataclass(frozen=True)
class SolutionRepairPlan:
    snapshot_hash: str
    finding_ids: tuple[str, ...]
    targets: tuple[SolutionRepairTarget, ...]


@dataclass(frozen=True)
class SolutionRepairReservation:
    run: SolutionQualityRun
    plan: SolutionRepairPlan


def _target_sort_key(target: SolutionRepairTarget) -> tuple[int, int]:
    return OPTION_LANES.index(target.option), GENERATED_OPTION_FIELDS.index(target.field)


def _fail(
    message: str,
    *,
    code: str,
    stale_reason: str = "",
) -> None:
    raise SolutionRepairContractError(
        message,
        code=code,
        stale_reason=stale_reason,
    )


def _validate_initial_critic_result(
    *,
    initial_critic_run: SolutionQualityRun,
    source_context,
) -> list[dict[str, Any]]:
    payload = initial_critic_run.result_payload
    if not isinstance(payload, dict):
        _fail(
            "Das Ergebnis der initialen Qualitätsprüfung ist ungültig.",
            code="invalid_initial_critic_result",
        )

    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        _fail(
            "Das Ergebnis der initialen Qualitätsprüfung ist ungültig.",
            code="invalid_initial_critic_result",
        )

    provider_payload: dict[str, Any] = {
        "schema_version": payload.get("schema_version"),
        "prompt_version": payload.get("prompt_version"),
        "findings": [],
    }
    persisted_ids: list[str] = []
    for finding in raw_findings:
        if not isinstance(finding, dict):
            _fail(
                "Das Ergebnis der initialen Qualitätsprüfung ist ungültig.",
                code="invalid_initial_critic_result",
            )
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or not finding_id.strip():
            _fail(
                "Ein Finding der initialen Qualitätsprüfung hat keine stabile ID.",
                code="invalid_initial_critic_result",
            )
        persisted_ids.append(finding_id.strip())
        provider_finding = dict(finding)
        provider_finding.pop("finding_id", None)
        provider_payload["findings"].append(provider_finding)

    if len(set(persisted_ids)) != len(persisted_ids):
        _fail(
            "Die initiale Qualitätsprüfung enthält doppelte Finding-IDs.",
            code="invalid_initial_critic_result",
        )

    try:
        normalized = validate_solution_critic_payload(provider_payload, source_context)
    except SolutionCriticContractError as exc:
        raise SolutionRepairContractError(
            "Das Ergebnis der initialen Qualitätsprüfung ist nicht mehr vertragskonform.",
            code="invalid_initial_critic_result",
        ) from exc

    normalized_findings = normalized["findings"]
    if [item["finding_id"] for item in normalized_findings] != persisted_ids:
        _fail(
            "Die Finding-IDs der initialen Qualitätsprüfung sind nicht reproduzierbar.",
            code="invalid_initial_critic_result",
        )
    return normalized_findings


def _human_edit_targets(preview_payload: dict[str, Any]) -> set[SolutionRepairTarget]:
    try:
        edits = normalize_solution_generation_edits(preview_payload)
    except SolutionGenerationEffectivePayloadError as exc:
        raise SolutionRepairContractError(
            "Die gespeicherten Human Edits sind ungültig.",
            code="invalid_preview",
        ) from exc
    return {
        SolutionRepairTarget(option=option, field=field)
        for option, lane_edits in edits.items()
        for field in lane_edits
    }


def _repair_scope(
    findings: list[dict[str, Any]],
) -> tuple[tuple[str, ...], tuple[SolutionRepairTarget, ...]]:
    finding_ids: list[str] = []
    targets: set[SolutionRepairTarget] = set()

    for finding in findings:
        if not finding["repairable"]:
            continue
        finding_ids.append(finding["finding_id"])

        field = finding.get("field")
        if field:
            targets.add(
                SolutionRepairTarget(
                    option=finding["option"],
                    field=field,
                )
            )
        for related_target in finding["related_targets"]:
            targets.add(
                SolutionRepairTarget(
                    option=related_target["option"],
                    field=related_target["field"],
                )
            )

    if not finding_ids:
        _fail(
            "Es liegen keine reparierbaren Findings vor.",
            code="no_repairable_findings",
        )
    if not targets:
        _fail(
            "Die reparierbaren Findings enthalten keine explizit freigegebenen Feldziele.",
            code="invalid_initial_critic_result",
        )

    return tuple(finding_ids), tuple(sorted(targets, key=_target_sort_key))


def build_solution_repair_plan(
    *,
    generation_run: SolutionGenerationRun,
    initial_critic_run: SolutionQualityRun,
) -> SolutionRepairPlan:
    if (
        generation_run.status != SolutionGenerationRun.Status.SUCCESS
        or not generation_run.preview_payload
    ):
        _fail(
            "Für den Repair liegt keine valide Lösungs-Preview vor.",
            code="repair_preview_unavailable",
        )

    if (
        initial_critic_run.solution_generation_run_id != generation_run.pk
        or initial_critic_run.step_type != SolutionQualityRun.StepType.INITIAL_CRITIC
        or initial_critic_run.status != SolutionQualityRun.Status.SUCCESS
    ):
        _fail(
            "Für den Repair liegt keine erfolgreiche initiale Qualitätsprüfung vor.",
            code="initial_critic_unavailable",
        )

    if generation_run.prompt_version != GENERATION_PROMPT_VERSION:
        _fail(
            "Der Generator-Prompt-Vertrag hat sich seit der Preview geändert.",
            code="repair_stale",
            stale_reason="generation_prompt_version_changed",
        )
    if generation_run.generation_schema_version != GENERATION_SCHEMA_VERSION:
        _fail(
            "Das Generator-Schema hat sich seit der Preview geändert.",
            code="repair_stale",
            stale_reason="generation_schema_version_changed",
        )

    if initial_critic_run.prompt_version != CRITIC_PROMPT_VERSION:
        _fail(
            "Der Critic-Prompt-Vertrag hat sich seit der Prüfung geändert.",
            code="repair_stale",
            stale_reason="critic_prompt_version_changed",
        )
    if initial_critic_run.output_schema_version != CRITIC_SCHEMA_VERSION:
        _fail(
            "Das Critic-Schema hat sich seit der Prüfung geändert.",
            code="repair_stale",
            stale_reason="critic_schema_version_changed",
        )

    current_source_context = build_solution_generation_source_context(
        generation_run.process_analysis
    )
    if (
        current_source_context.process_version != generation_run.process_version
        or current_source_context.source_hash != generation_run.source_hash
    ):
        _fail(
            "Die Prozess- oder Quellenbasis hat sich seit der Prüfung geändert.",
            code="repair_stale",
            stale_reason="source_context_changed",
        )

    try:
        current_snapshot = build_solution_quality_snapshot(
            preview_payload=generation_run.preview_payload,
            source_context=current_source_context,
        )
    except SolutionGenerationEffectivePayloadError as exc:
        raise SolutionRepairContractError(
            "Die aktuelle Lösungs-Preview ist nicht mehr vertragskonform.",
            code="invalid_preview",
        ) from exc

    if current_snapshot.snapshot_hash != initial_critic_run.input_hash:
        _fail(
            "Die Preview oder ein gebundener Quality-Vertrag hat sich seit der Prüfung geändert.",
            code="repair_stale",
            stale_reason="quality_snapshot_changed",
        )

    findings = _validate_initial_critic_result(
        initial_critic_run=initial_critic_run,
        source_context=current_source_context,
    )
    finding_ids, targets = _repair_scope(findings)

    conflicting_targets = set(targets) & _human_edit_targets(generation_run.preview_payload)
    if conflicting_targets:
        _fail(
            "Mindestens ein Repair-Ziel enthält einen kollidierenden Human Edit.",
            code="human_edit_conflict",
        )

    return SolutionRepairPlan(
        snapshot_hash=current_snapshot.snapshot_hash,
        finding_ids=finding_ids,
        targets=targets,
    )


@transaction.atomic
def reserve_solution_repair_attempt(
    *,
    solution_generation_run_id,
    actor,
    provider: str = "openrouter",
    input_chars: int = 0,
) -> SolutionRepairReservation:
    generation_run = (
        SolutionGenerationRun.objects.select_for_update()
        .select_related("process_analysis__stage__value_stream")
        .prefetch_related("process_analysis__validations")
        .get(pk=solution_generation_run_id)
    )

    existing_repair = SolutionQualityRun.objects.filter(
        solution_generation_run=generation_run,
        step_type=SolutionQualityRun.StepType.REPAIR,
    ).first()
    if existing_repair is not None:
        _fail(
            "Der einmalige Repair-Versuch wurde bereits verbraucht.",
            code="repair_attempt_consumed",
        )

    initial_critic_run = SolutionQualityRun.objects.filter(
        solution_generation_run=generation_run,
        step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
    ).first()
    if initial_critic_run is None:
        _fail(
            "Für den Repair liegt keine initiale Qualitätsprüfung vor.",
            code="initial_critic_unavailable",
        )

    plan = build_solution_repair_plan(
        generation_run=generation_run,
        initial_critic_run=initial_critic_run,
    )

    try:
        reservation = reserve_solution_quality_step(
            solution_generation_run_id=generation_run.pk,
            actor=actor,
            step_type=SolutionQualityRun.StepType.REPAIR,
            input_hash=plan.snapshot_hash,
            prompt_version=REPAIR_PROMPT_VERSION,
            output_schema_version=REPAIR_SCHEMA_VERSION,
            provider=provider,
            input_chars=input_chars,
        )
    except SolutionQualityRunError as exc:
        raise SolutionRepairContractError(
            str(exc),
            code=exc.code,
        ) from exc

    if not reservation.created:
        _fail(
            "Der einmalige Repair-Versuch wurde bereits verbraucht.",
            code="repair_attempt_consumed",
        )
    return SolutionRepairReservation(run=reservation.run, plan=plan)
