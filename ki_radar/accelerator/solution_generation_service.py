from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from ki_radar.architecture.models import ProcessAnalysis
from ki_radar.core.llm_policy import (
    AcceleratorLLMPolicy,
    LLMConfigurationError,
    get_accelerator_llm_policy,
)
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable, request_openrouter

from .models import AcceleratorLLMQuota, SolutionGenerationRun
from .retention_policy import (
    CaptureRetentionConfigurationError,
    completed_capture_expiry,
)
from .solution_generation_contract import (
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    build_solution_generation_json_schema,
    build_solution_generation_messages,
)
from .solution_generation_sources import (
    SolutionGenerationReadinessError,
    SolutionGenerationSourceContext,
    require_solution_generation_ready,
)
from .solution_generation_validation import (
    SolutionGenerationContractError,
    validate_solution_generation_payload,
)

logger = logging.getLogger(__name__)

RUNNING_RECOVERY_GRACE_SECONDS = 15
MAX_CONTRACT_ERROR_DETAILS = 3
MAX_CONTRACT_ERROR_DETAIL_CHARS = 220


class SolutionGenerationError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class SolutionGenerationAlreadyRunning(SolutionGenerationError):
    pass


class SolutionGenerationQuotaExceeded(SolutionGenerationError):
    pass


@dataclass(frozen=True)
class PreparedSolutionGeneration:
    run: SolutionGenerationRun
    source_context: SolutionGenerationSourceContext
    policy: AcceleratorLLMPolicy
    messages: list[dict[str, str]]


@dataclass(frozen=True)
class SolutionGenerationProviderPayload:
    result: OpenRouterResult
    payload: dict[str, Any]


def log_solution_generation_run(run: SolutionGenerationRun) -> None:
    logger.info(
        "llm_request purpose=solution_generation provider=%s model=%s "
        "object_type=process_analysis object_id=%s run_id=%s status=%s "
        "error_code=%s duration_ms=%s input_chars=%s output_chars=%s "
        "prompt_tokens=%s completion_tokens=%s total_tokens=%s cost=%s",
        run.provider,
        run.model_name or "provider-default",
        run.process_analysis_id,
        run.pk,
        run.status,
        run.error_code or "none",
        run.duration_ms if run.duration_ms is not None else "",
        run.input_chars,
        run.output_chars,
        run.prompt_tokens if run.prompt_tokens is not None else "",
        run.completion_tokens if run.completion_tokens is not None else "",
        run.total_tokens if run.total_tokens is not None else "",
        run.cost if run.cost is not None else "",
    )


def _quota_subject(scope: str, *, actor, process_analysis: ProcessAnalysis) -> dict[str, object]:
    if scope == AcceleratorLLMQuota.Scope.CONTEXT:
        return {"process_analysis": process_analysis}
    if scope == AcceleratorLLMQuota.Scope.USER:
        return {"user": actor}
    return {}


def _increment_quota(
    *,
    scope: str,
    actor,
    process_analysis: ProcessAnalysis,
    quota_date,
    limit: int,
) -> None:
    subject = _quota_subject(scope, actor=actor, process_analysis=process_analysis)
    quota, _created = AcceleratorLLMQuota.objects.get_or_create(
        scope=scope,
        quota_date=quota_date,
        defaults={"calls": 0, **subject},
        **subject,
    )
    updated = AcceleratorLLMQuota.objects.filter(pk=quota.pk, calls__lt=limit).update(
        calls=F("calls") + 1
    )
    if updated:
        return

    labels = {
        AcceleratorLLMQuota.Scope.CONTEXT: "Diese Prozessanalyse",
        AcceleratorLLMQuota.Scope.USER: "Ihr Benutzerkonto",
        AcceleratorLLMQuota.Scope.GLOBAL: "Der Accelerator",
    }
    raise SolutionGenerationQuotaExceeded(
        f"{labels[scope]} hat das tägliche Generierungslimit erreicht.",
        code=f"{scope}_quota_exceeded",
    )


def _reserve_solution_generation_quotas(
    *,
    actor,
    process_analysis: ProcessAnalysis,
    policy: AcceleratorLLMPolicy,
    quota_date,
) -> None:
    for scope, limit in (
        (
            AcceleratorLLMQuota.Scope.CONTEXT,
            policy.solution_generation_max_calls_per_context,
        ),
        (AcceleratorLLMQuota.Scope.USER, policy.max_calls_per_user_day),
        (AcceleratorLLMQuota.Scope.GLOBAL, policy.max_calls_global_day),
    ):
        _increment_quota(
            scope=scope,
            actor=actor,
            process_analysis=process_analysis,
            quota_date=quota_date,
            limit=limit,
        )


def _duration_ms(run: SolutionGenerationRun, finished_at) -> int:
    return max(0, round((finished_at - run.started_at).total_seconds() * 1000))


def _usage_int(value: object) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _cost(value: object) -> Decimal | None:
    if value in {None, ""}:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _apply_provider_metadata(run: SolutionGenerationRun, result: OpenRouterResult) -> None:
    run.model_name = result.model
    run.output_chars = result.output_chars
    run.prompt_tokens = _usage_int(result.usage.get("prompt_tokens"))
    run.completion_tokens = _usage_int(result.usage.get("completion_tokens"))
    run.total_tokens = _usage_int(result.usage.get("total_tokens"))
    run.cost = _cost(result.usage.get("cost"))


def _recover_or_reject_running_generation(
    *,
    process_analysis: ProcessAnalysis,
    policy: AcceleratorLLMPolicy,
) -> None:
    running = (
        SolutionGenerationRun.objects.filter(
            process_analysis=process_analysis,
            status=SolutionGenerationRun.Status.RUNNING,
        )
        .order_by("started_at")
        .first()
    )
    if running is None:
        return

    stale_after = running.started_at + timedelta(
        seconds=policy.timeout_seconds + RUNNING_RECOVERY_GRACE_SECONDS
    )
    if timezone.now() < stale_after:
        raise SolutionGenerationAlreadyRunning(
            "Für diese Prozessanalyse läuft bereits eine Generierung.",
            code="generation_already_running",
        )

    mark_solution_generation_failed(
        run_id=running.pk,
        error_code="stale_running_recovered",
    )


def _contract_error_summary(exc: SolutionGenerationContractError) -> str:
    details: list[str] = []
    for error in exc.errors[:MAX_CONTRACT_ERROR_DETAILS]:
        normalized = " ".join(str(error).split())
        if len(normalized) > MAX_CONTRACT_ERROR_DETAIL_CHARS:
            normalized = f"{normalized[: MAX_CONTRACT_ERROR_DETAIL_CHARS - 1]}…"
        details.append(normalized)
    return " | ".join(details)


@sensitive_variables("source_context", "messages")
@transaction.atomic
def prepare_solution_generation_run(*, actor, process_analysis_id) -> PreparedSolutionGeneration:
    process_analysis = (
        ProcessAnalysis.objects.select_for_update()
        .select_related("stage__value_stream")
        .prefetch_related("validations")
        .get(pk=process_analysis_id)
    )

    try:
        policy = get_accelerator_llm_policy()
        expires_at = completed_capture_expiry()
    except (LLMConfigurationError, CaptureRetentionConfigurationError) as exc:
        raise SolutionGenerationError(
            f"Die Accelerator-Konfiguration ist ungültig: {exc}",
            code="invalid_configuration",
        ) from exc

    _recover_or_reject_running_generation(
        process_analysis=process_analysis,
        policy=policy,
    )

    try:
        source_context = require_solution_generation_ready(process_analysis)
    except SolutionGenerationReadinessError as exc:
        raise SolutionGenerationError(str(exc), code="process_not_ready") from exc

    messages = build_solution_generation_messages(source_context)
    input_chars = sum(len(message["content"]) for message in messages)
    if input_chars > policy.max_input_chars:
        raise SolutionGenerationError(
            "Die für die Generierung vorgesehenen Prozessdaten überschreiten das Größenlimit.",
            code="input_too_large",
        )

    try:
        run = SolutionGenerationRun.objects.create(
            process_analysis=process_analysis,
            process_version=source_context.process_version,
            source_hash=source_context.source_hash,
            requested_by=actor,
            prompt_version=GENERATION_PROMPT_VERSION,
            generation_schema_version=GENERATION_SCHEMA_VERSION,
            input_chars=input_chars,
            expires_at=expires_at,
        )
    except IntegrityError as exc:
        raise SolutionGenerationAlreadyRunning(
            "Für diese Prozessanalyse läuft bereits eine Generierung.",
            code="generation_already_running",
        ) from exc

    _reserve_solution_generation_quotas(
        actor=actor,
        process_analysis=process_analysis,
        policy=policy,
        quota_date=timezone.localdate(),
    )
    return PreparedSolutionGeneration(
        run=run,
        source_context=source_context,
        policy=policy,
        messages=messages,
    )


@transaction.atomic
def mark_solution_generation_failed(
    *,
    run_id,
    error_code: str,
    result: OpenRouterResult | None = None,
) -> SolutionGenerationRun:
    run = SolutionGenerationRun.objects.select_for_update().get(pk=run_id)
    if run.status != SolutionGenerationRun.Status.RUNNING:
        return run

    finished_at = timezone.now()
    run.status = SolutionGenerationRun.Status.FAILED
    run.finished_at = finished_at
    run.duration_ms = _duration_ms(run, finished_at)
    run.error_code = error_code
    run.preview_payload = {}
    if result is not None:
        _apply_provider_metadata(run, result)
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "error_code",
            "preview_payload",
            "model_name",
            "output_chars",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost",
            "updated_at",
        ]
    )
    log_solution_generation_run(run)
    return run


@transaction.atomic
def record_solution_generation_provider_result(
    *,
    run_id,
    result: OpenRouterResult,
) -> SolutionGenerationRun:
    run = SolutionGenerationRun.objects.select_for_update().get(pk=run_id)
    if run.status != SolutionGenerationRun.Status.RUNNING:
        return run
    _apply_provider_metadata(run, result)
    run.save(
        update_fields=[
            "model_name",
            "output_chars",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost",
            "updated_at",
        ]
    )
    return run


@transaction.atomic
def mark_solution_generation_success(
    *,
    run_id,
    preview_payload: dict[str, Any],
) -> SolutionGenerationRun:
    run = SolutionGenerationRun.objects.select_for_update().get(pk=run_id)
    if run.status != SolutionGenerationRun.Status.RUNNING:
        return run
    finished_at = timezone.now()
    run.status = SolutionGenerationRun.Status.SUCCESS
    run.finished_at = finished_at
    run.duration_ms = _duration_ms(run, finished_at)
    run.error_code = ""
    run.preview_payload = preview_payload
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "error_code",
            "preview_payload",
            "updated_at",
        ]
    )
    log_solution_generation_run(run)
    return run


@sensitive_variables("prepared", "result", "payload", "response_schema")
def request_solution_generation_provider(
    prepared: PreparedSolutionGeneration,
) -> SolutionGenerationProviderPayload:
    response_schema = build_solution_generation_json_schema()
    try:
        result = request_openrouter(
            messages=prepared.messages,
            max_tokens=prepared.policy.solution_generation_max_output_tokens,
            timeout_seconds=prepared.policy.timeout_seconds,
            temperature=None,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "accelerator_solution_generation_v1",
                    "strict": True,
                    "schema": response_schema,
                },
            },
            provider={"require_parameters": True},
        )
    except OpenRouterUnavailable as exc:
        mark_solution_generation_failed(run_id=prepared.run.pk, error_code=exc.code)
        raise SolutionGenerationError(str(exc), code=exc.code) from exc

    if result.finish_reason == "length":
        mark_solution_generation_failed(
            run_id=prepared.run.pk,
            error_code="output_truncated",
            result=result,
        )
        raise SolutionGenerationError(
            "Die LLM-Antwort wurde wegen des Ausgabelimits abgeschnitten.",
            code="output_truncated",
        )

    try:
        payload = json.loads(result.content)
    except json.JSONDecodeError as exc:
        mark_solution_generation_failed(
            run_id=prepared.run.pk,
            error_code="invalid_response",
            result=result,
        )
        raise SolutionGenerationError(
            "OpenRouter hat kein gültiges JSON-Dokument zurückgegeben.",
            code="invalid_response",
        ) from exc
    if not isinstance(payload, dict):
        mark_solution_generation_failed(
            run_id=prepared.run.pk,
            error_code="invalid_response",
            result=result,
        )
        raise SolutionGenerationError(
            "OpenRouter hat kein JSON-Objekt zurückgegeben.",
            code="invalid_response",
        )

    recorded_run = record_solution_generation_provider_result(
        run_id=prepared.run.pk,
        result=result,
    )
    if recorded_run.status != SolutionGenerationRun.Status.RUNNING:
        raise SolutionGenerationError(
            "Dieser Generierungsversuch wurde serverseitig bereits beendet und verworfen.",
            code="generation_superseded",
        )
    return SolutionGenerationProviderPayload(result=result, payload=payload)


def _validated_preview_payload(
    *,
    prepared: PreparedSolutionGeneration,
    payload: dict[str, Any],
) -> dict[str, Any]:
    validated = validate_solution_generation_payload(payload, prepared.source_context)
    return {
        "schema_version": validated["schema_version"],
        "prompt_version": validated["prompt_version"],
        "source_context": prepared.source_context.provider_payload(),
        "options": validated["options"],
        "edits": {},
    }


@sensitive_variables("prepared", "provider_payload", "preview_payload")
def generate_solution_preview(*, actor, process_analysis_id) -> SolutionGenerationRun:
    prepared = prepare_solution_generation_run(
        actor=actor,
        process_analysis_id=process_analysis_id,
    )
    try:
        provider_payload = request_solution_generation_provider(prepared)
        preview_payload = _validated_preview_payload(
            prepared=prepared,
            payload=provider_payload.payload,
        )
    except SolutionGenerationContractError as exc:
        mark_solution_generation_failed(
            run_id=prepared.run.pk,
            error_code="invalid_generation_payload",
        )
        detail = _contract_error_summary(exc)
        raise SolutionGenerationError(
            "Die KI-Antwort hat die fachlichen Sicherheitsregeln nicht erfüllt und wurde "
            f"vollständig verworfen. Validierungsgrund: {detail}",
            code="invalid_generation_payload",
        ) from exc
    except SolutionGenerationError:
        raise
    except Exception as exc:
        mark_solution_generation_failed(
            run_id=prepared.run.pk,
            error_code="internal_error",
        )
        logger.exception(
            "solution_generation unexpected_failure process_analysis_id=%s run_id=%s",
            prepared.run.process_analysis_id,
            prepared.run.pk,
        )
        raise SolutionGenerationError(
            "Die KI-Generierung ist unerwartet fehlgeschlagen. Der Lauf wurde sauber beendet; "
            "es wurden keine Lösungsoptionen angelegt.",
            code="internal_error",
        ) from exc

    run = mark_solution_generation_success(
        run_id=prepared.run.pk,
        preview_payload=preview_payload,
    )
    if run.status != SolutionGenerationRun.Status.SUCCESS:
        raise SolutionGenerationError(
            "Dieser Generierungsversuch wurde serverseitig bereits beendet und verworfen.",
            code="generation_superseded",
        )
    return run
