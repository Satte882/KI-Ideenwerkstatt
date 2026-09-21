from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import SolutionGenerationRun, SolutionQualityRun
from .solution_generation_contract import GENERATED_OPTION_FIELDS, OPTION_LANES
from .solution_generation_sources import build_solution_generation_source_context
from .solution_repair_contract import SolutionRepairContractError, build_solution_repair_plan


class SolutionGenerationPreviewError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SolutionGenerationPreviewState:
    stale: bool
    expired: bool
    current_ready: bool
    validation_state: str
    adopted: bool

    @property
    def editable(self) -> bool:
        return not self.stale and not self.expired and self.current_ready and not self.adopted


@dataclass(frozen=True)
class SolutionQualityPreviewState:
    status: str
    findings: tuple[dict[str, Any], ...]
    repair_available: bool
    human_review: bool
    repair_consumed: bool
    stale: bool


def build_solution_generation_preview_state(
    run: SolutionGenerationRun,
) -> SolutionGenerationPreviewState:
    current_context = build_solution_generation_source_context(run.process_analysis)
    stale = (
        current_context.source_hash != run.source_hash
        or current_context.process_version != run.process_version
    )
    adoption = run.preview_payload.get("adoption", {}) if run.preview_payload else {}
    adopted = isinstance(adoption, dict) and adoption.get("status") == "adopted"
    return SolutionGenerationPreviewState(
        stale=stale,
        expired=run.expires_at <= timezone.now(),
        current_ready=current_context.is_ready,
        validation_state=current_context.validation_state,
        adopted=adopted,
    )


def _critic_findings(run: SolutionQualityRun | None) -> tuple[dict[str, Any], ...]:
    if run is None or run.status != SolutionQualityRun.Status.SUCCESS:
        return ()
    payload = run.result_payload if isinstance(run.result_payload, dict) else {}
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        return ()
    return tuple(item for item in findings if isinstance(item, dict))


def build_solution_quality_preview_state(
    run: SolutionGenerationRun,
    *,
    preview_state: SolutionGenerationPreviewState,
) -> SolutionQualityPreviewState:
    quality_runs = {quality_run.step_type: quality_run for quality_run in run.quality_runs.all()}
    initial = quality_runs.get(SolutionQualityRun.StepType.INITIAL_CRITIC)
    repair = quality_runs.get(SolutionQualityRun.StepType.REPAIR)
    final = quality_runs.get(SolutionQualityRun.StepType.FINAL_CRITIC)
    repair_consumed = repair is not None

    if initial is None or initial.status == SolutionQualityRun.Status.RUNNING:
        return SolutionQualityPreviewState(
            status="initial_pending",
            findings=(),
            repair_available=False,
            human_review=False,
            repair_consumed=repair_consumed,
            stale=preview_state.stale,
        )

    if initial.status == SolutionQualityRun.Status.FAILED:
        return SolutionQualityPreviewState(
            status="human_review",
            findings=(),
            repair_available=False,
            human_review=True,
            repair_consumed=repair_consumed,
            stale=preview_state.stale,
        )

    initial_findings = _critic_findings(initial)

    if repair is not None:
        if repair.status == SolutionQualityRun.Status.RUNNING:
            return SolutionQualityPreviewState(
                status="repair_running",
                findings=initial_findings,
                repair_available=False,
                human_review=False,
                repair_consumed=True,
                stale=preview_state.stale,
            )
        if repair.status == SolutionQualityRun.Status.FAILED:
            return SolutionQualityPreviewState(
                status="human_review",
                findings=initial_findings,
                repair_available=False,
                human_review=True,
                repair_consumed=True,
                stale=preview_state.stale,
            )

        if final is None or final.status == SolutionQualityRun.Status.RUNNING:
            return SolutionQualityPreviewState(
                status="final_pending",
                findings=initial_findings,
                repair_available=False,
                human_review=False,
                repair_consumed=True,
                stale=preview_state.stale,
            )
        if final.status == SolutionQualityRun.Status.FAILED:
            return SolutionQualityPreviewState(
                status="human_review",
                findings=initial_findings,
                repair_available=False,
                human_review=True,
                repair_consumed=True,
                stale=preview_state.stale,
            )
        return SolutionQualityPreviewState(
            status="human_review",
            findings=_critic_findings(final),
            repair_available=False,
            human_review=True,
            repair_consumed=True,
            stale=preview_state.stale,
        )

    if not initial_findings:
        return SolutionQualityPreviewState(
            status="human_review",
            findings=(),
            repair_available=False,
            human_review=True,
            repair_consumed=False,
            stale=preview_state.stale,
        )

    if preview_state.stale:
        return SolutionQualityPreviewState(
            status="repair_stale",
            findings=initial_findings,
            repair_available=False,
            human_review=True,
            repair_consumed=False,
            stale=True,
        )

    try:
        build_solution_repair_plan(
            generation_run=run,
            initial_critic_run=initial,
        )
    except SolutionRepairContractError as exc:
        if exc.code == "no_repairable_findings":
            status = "human_review"
            stale = False
        elif exc.code in {"repair_stale", "human_edit_conflict"}:
            status = "repair_stale"
            stale = True
        else:
            status = "human_review"
            stale = False
        return SolutionQualityPreviewState(
            status=status,
            findings=initial_findings,
            repair_available=False,
            human_review=True,
            repair_consumed=False,
            stale=stale,
        )

    return SolutionQualityPreviewState(
        status="repair_available",
        findings=initial_findings,
        repair_available=True,
        human_review=False,
        repair_consumed=False,
        stale=False,
    )


def _normalize_edits(
    preview_payload: dict,
    edits: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    options = preview_payload.get("options", {})
    unknown_lanes = set(edits) - set(OPTION_LANES)
    if unknown_lanes:
        raise SolutionGenerationPreviewError(
            "Die Bearbeitung enthält eine unbekannte Lösungsrichtung.",
            code="invalid_preview_edit",
        )

    normalized: dict[str, dict[str, str]] = {}
    for lane, lane_edits in edits.items():
        unknown_fields = set(lane_edits) - set(GENERATED_OPTION_FIELDS)
        if unknown_fields:
            raise SolutionGenerationPreviewError(
                "Die Bearbeitung enthält ein nicht freigegebenes Entwurfsfeld.",
                code="invalid_preview_edit",
            )
        normalized_lane: dict[str, str] = {}
        for field_name, value in lane_edits.items():
            text = str(value).strip()
            if not text:
                raise SolutionGenerationPreviewError(
                    "Entwurfsfelder dürfen nicht leer gespeichert werden.",
                    code="invalid_preview_edit",
                )
            original = str(options[lane][field_name]["text"]).strip()
            if text != original:
                normalized_lane[field_name] = text
        if normalized_lane:
            normalized[lane] = normalized_lane
    return normalized


@transaction.atomic
def update_solution_generation_preview_edits(
    *,
    run_id,
    edits: dict[str, dict[str, str]],
) -> SolutionGenerationRun:
    run = (
        SolutionGenerationRun.objects.select_for_update()
        .select_related("process_analysis__stage__value_stream")
        .prefetch_related("process_analysis__validations")
        .get(pk=run_id)
    )
    if run.status != SolutionGenerationRun.Status.SUCCESS or not run.preview_payload:
        raise SolutionGenerationPreviewError(
            "Diese KI-Vorschau ist nicht zur Bearbeitung verfügbar.",
            code="preview_unavailable",
        )

    state = build_solution_generation_preview_state(run)
    if state.adopted:
        raise SolutionGenerationPreviewError(
            "Diese KI-Vorschau wurde bereits übernommen und ist nicht mehr bearbeitbar.",
            code="preview_adopted",
        )
    if state.expired:
        raise SolutionGenerationPreviewError(
            "Diese KI-Vorschau ist abgelaufen. Bitte neu generieren.",
            code="preview_expired",
        )
    if state.stale or not state.current_ready:
        raise SolutionGenerationPreviewError(
            "Die Prozessdaten haben sich geändert. Bitte die Entwürfe neu generieren.",
            code="preview_stale",
        )

    preview_payload = dict(run.preview_payload)
    preview_payload["edits"] = _normalize_edits(preview_payload, edits)
    run.preview_payload = preview_payload
    run.save(update_fields=["preview_payload", "updated_at"])
    return run
