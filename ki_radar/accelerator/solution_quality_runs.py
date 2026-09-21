from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import SolutionGenerationRun, SolutionQualityRun

_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class SolutionQualityRunError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SolutionQualityReservation:
    run: SolutionQualityRun
    created: bool


def _normalized_input_hash(value: str) -> str:
    text = str(value).strip()
    if not _HASH_RE.fullmatch(text):
        raise SolutionQualityRunError(
            "Der Quality-Snapshot-Hash ist ungültig.",
            code="invalid_quality_input_hash",
        )
    return text.lower()


def _normalized_text(value: str, *, field: str, maximum: int, code: str) -> str:
    text = str(value).strip()
    if not text or len(text) > maximum:
        raise SolutionQualityRunError(
            f"{field} ist für den Quality-Step ungültig.",
            code=code,
        )
    return text


def _optional_usage(value: int | None, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SolutionQualityRunError(
            f"{field} ist für den Quality-Step ungültig.",
            code="invalid_quality_usage",
        )
    return value


def _duration_ms(started_at, finished_at) -> int:
    return max(0, round((finished_at - started_at).total_seconds() * 1000))


@transaction.atomic
def reserve_solution_quality_step(
    *,
    solution_generation_run_id,
    actor,
    step_type: str,
    input_hash: str,
    prompt_version: str,
    output_schema_version: str,
    provider: str = "openrouter",
    input_chars: int = 0,
) -> SolutionQualityReservation:
    normalized_step = str(step_type).strip()
    if normalized_step not in SolutionQualityRun.StepType.values:
        raise SolutionQualityRunError(
            "Der Quality-Step ist unbekannt.",
            code="invalid_quality_step",
        )
    normalized_hash = _normalized_input_hash(input_hash)
    normalized_prompt = _normalized_text(
        prompt_version,
        field="Prompt-Version",
        maximum=20,
        code="invalid_quality_contract",
    )
    normalized_schema = _normalized_text(
        output_schema_version,
        field="Output-Schema-Version",
        maximum=20,
        code="invalid_quality_contract",
    )
    normalized_provider = _normalized_text(
        provider,
        field="Provider",
        maximum=50,
        code="invalid_quality_provider",
    )
    if isinstance(input_chars, bool) or not isinstance(input_chars, int) or input_chars < 0:
        raise SolutionQualityRunError(
            "Die Eingabelänge des Quality-Steps ist ungültig.",
            code="invalid_quality_usage",
        )

    generation_run = SolutionGenerationRun.objects.select_for_update().get(
        pk=solution_generation_run_id
    )
    if (
        generation_run.status != SolutionGenerationRun.Status.SUCCESS
        or not generation_run.preview_payload
    ):
        raise SolutionQualityRunError(
            "Für diesen Quality-Step liegt keine valide Lösungs-Preview vor.",
            code="quality_preview_unavailable",
        )

    existing = SolutionQualityRun.objects.filter(
        solution_generation_run=generation_run,
        step_type=normalized_step,
    ).first()
    if existing is not None:
        return SolutionQualityReservation(run=existing, created=False)

    quality_run = SolutionQualityRun.objects.create(
        solution_generation_run=generation_run,
        requested_by=actor,
        step_type=normalized_step,
        provider=normalized_provider,
        prompt_version=normalized_prompt,
        output_schema_version=normalized_schema,
        input_hash=normalized_hash,
        input_chars=input_chars,
    )
    return SolutionQualityReservation(run=quality_run, created=True)


def _terminal_quality_run(run_id) -> SolutionQualityRun:
    quality_run = SolutionQualityRun.objects.select_for_update().get(pk=run_id)
    if quality_run.status != SolutionQualityRun.Status.RUNNING:
        raise SolutionQualityRunError(
            "Der Quality-Step wurde bereits abgeschlossen.",
            code="quality_step_terminal",
        )
    return quality_run


@transaction.atomic
def mark_solution_quality_step_success(
    *,
    run_id,
    result_payload: dict[str, Any],
    model_name: str = "",
    output_chars: int = 0,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    cost: Decimal | None = None,
) -> SolutionQualityRun:
    if not isinstance(result_payload, dict):
        raise SolutionQualityRunError(
            "Das Quality-Ergebnis ist nicht strukturiert.",
            code="invalid_quality_result",
        )
    normalized_model = str(model_name).strip()
    if len(normalized_model) > 200:
        raise SolutionQualityRunError(
            "Der Modellname des Quality-Steps ist ungültig.",
            code="invalid_quality_provider",
        )
    if isinstance(output_chars, bool) or not isinstance(output_chars, int) or output_chars < 0:
        raise SolutionQualityRunError(
            "Die Ausgabelänge des Quality-Steps ist ungültig.",
            code="invalid_quality_usage",
        )
    normalized_prompt_tokens = _optional_usage(prompt_tokens, field="Prompt-Tokens")
    normalized_completion_tokens = _optional_usage(
        completion_tokens,
        field="Completion-Tokens",
    )
    normalized_total_tokens = _optional_usage(total_tokens, field="Gesamt-Tokens")
    if cost is not None and cost < 0:
        raise SolutionQualityRunError(
            "Die Kosten des Quality-Steps sind ungültig.",
            code="invalid_quality_usage",
        )

    quality_run = _terminal_quality_run(run_id)
    finished_at = timezone.now()
    quality_run.status = SolutionQualityRun.Status.SUCCESS
    quality_run.model_name = normalized_model
    quality_run.finished_at = finished_at
    quality_run.duration_ms = _duration_ms(quality_run.started_at, finished_at)
    quality_run.error_code = ""
    quality_run.output_chars = output_chars
    quality_run.prompt_tokens = normalized_prompt_tokens
    quality_run.completion_tokens = normalized_completion_tokens
    quality_run.total_tokens = normalized_total_tokens
    quality_run.cost = cost
    quality_run.result_payload = result_payload
    quality_run.save(
        update_fields=[
            "status",
            "model_name",
            "finished_at",
            "duration_ms",
            "error_code",
            "output_chars",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost",
            "result_payload",
            "updated_at",
        ]
    )
    return quality_run


@transaction.atomic
def mark_solution_quality_step_failed(
    *,
    run_id,
    error_code: str,
    model_name: str = "",
    output_chars: int = 0,
) -> SolutionQualityRun:
    normalized_error = _normalized_text(
        error_code,
        field="Fehlercode",
        maximum=50,
        code="invalid_quality_error",
    )
    normalized_model = str(model_name).strip()
    if len(normalized_model) > 200:
        raise SolutionQualityRunError(
            "Der Modellname des Quality-Steps ist ungültig.",
            code="invalid_quality_provider",
        )
    if isinstance(output_chars, bool) or not isinstance(output_chars, int) or output_chars < 0:
        raise SolutionQualityRunError(
            "Die Ausgabelänge des Quality-Steps ist ungültig.",
            code="invalid_quality_usage",
        )

    quality_run = _terminal_quality_run(run_id)
    finished_at = timezone.now()
    quality_run.status = SolutionQualityRun.Status.FAILED
    quality_run.model_name = normalized_model
    quality_run.finished_at = finished_at
    quality_run.duration_ms = _duration_ms(quality_run.started_at, finished_at)
    quality_run.error_code = normalized_error
    quality_run.output_chars = output_chars
    quality_run.result_payload = {}
    quality_run.save(
        update_fields=[
            "status",
            "model_name",
            "finished_at",
            "duration_ms",
            "error_code",
            "output_chars",
            "result_payload",
            "updated_at",
        ]
    )
    return quality_run
