from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from .llm_policy import LLMConfigurationError, LLMTaskPolicy, get_llm_task_policy
from .models import LLMTaskQuota, LLMTaskRun
from .openrouter import OpenRouterResult, OpenRouterUnavailable, request_openrouter

logger = logging.getLogger(__name__)

SOURCE_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
FIRST_WAVE_PROVIDER_POLICY = {
    "zdr": True,
    "data_collection": "deny",
    "require_parameters": True,
}


class LLMTaskError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class LLMTaskQuotaExceeded(LLMTaskError):
    pass


@dataclass(frozen=True)
class PreparedLLMTask:
    run: LLMTaskRun
    policy: LLMTaskPolicy
    messages: list[dict[str, str]]


def _require_text(name: str, value: object, *, max_length: int) -> str:
    cleaned = str(value or "").strip()
    if not cleaned or len(cleaned) > max_length:
        raise LLMTaskError(
            f"{name} ist leer oder überschreitet die zulässige Länge.",
            code="invalid_task_context",
        )
    return cleaned


def _validate_source_hash(source_hash: object) -> str:
    cleaned = str(source_hash or "").strip().casefold()
    if not SOURCE_HASH_RE.fullmatch(cleaned):
        raise LLMTaskError(
            "Der LLM-Task benötigt einen gültigen SHA-256-Source-Hash.",
            code="invalid_source_hash",
        )
    return cleaned


def _message_input_chars(messages: list[dict[str, str]]) -> int:
    total = 0
    if not messages:
        raise LLMTaskError(
            "Der LLM-Task benötigt einen nicht-leeren Nachrichtenkontext.",
            code="invalid_task_context",
        )
    for message in messages:
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise LLMTaskError(
                "Der LLM-Task enthält einen ungültigen Nachrichtenkontext.",
                code="invalid_task_context",
            )
        total += len(message["content"])
    return total


def _quota_subject(
    scope: str,
    *,
    actor,
    task_type: str,
    object_type: str,
    object_id: str,
    field_key: str,
) -> dict[str, object]:
    if scope == LLMTaskQuota.Scope.CONTEXT:
        return {
            "task_type": task_type,
            "object_type": object_type,
            "object_id": object_id,
            "field_key": field_key,
        }
    if scope == LLMTaskQuota.Scope.USER:
        return {"user": actor}
    return {}


def _increment_quota(
    *,
    scope: str,
    actor,
    task_type: str,
    object_type: str,
    object_id: str,
    field_key: str,
    quota_date,
    limit: int,
) -> None:
    subject = _quota_subject(
        scope,
        actor=actor,
        task_type=task_type,
        object_type=object_type,
        object_id=object_id,
        field_key=field_key,
    )
    quota, _created = LLMTaskQuota.objects.get_or_create(
        scope=scope,
        quota_date=quota_date,
        defaults={"calls": 0, **subject},
        **subject,
    )
    updated = LLMTaskQuota.objects.filter(pk=quota.pk, calls__lt=limit).update(calls=F("calls") + 1)
    if updated:
        return

    labels = {
        LLMTaskQuota.Scope.CONTEXT: "Dieser Arbeitskontext",
        LLMTaskQuota.Scope.USER: "Ihr Benutzerkonto",
        LLMTaskQuota.Scope.GLOBAL: "Die KI-Unterstützung",
    }
    raise LLMTaskQuotaExceeded(
        f"{labels[scope]} hat das tägliche Aufruflimit erreicht.",
        code=f"{scope}_quota_exceeded",
    )


def _reserve_quotas(
    *,
    actor,
    task_type: str,
    object_type: str,
    object_id: str,
    field_key: str,
    policy: LLMTaskPolicy,
) -> None:
    quota_date = timezone.localdate()
    for scope, limit in (
        (LLMTaskQuota.Scope.CONTEXT, policy.max_calls_per_context_day),
        (LLMTaskQuota.Scope.USER, policy.max_calls_per_user_day),
        (LLMTaskQuota.Scope.GLOBAL, policy.max_calls_global_day),
    ):
        _increment_quota(
            scope=scope,
            actor=actor,
            task_type=task_type,
            object_type=object_type,
            object_id=object_id,
            field_key=field_key,
            quota_date=quota_date,
            limit=limit,
        )


def _duration_ms(run: LLMTaskRun, finished_at) -> int:
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


def _apply_provider_metadata(run: LLMTaskRun, result: OpenRouterResult) -> None:
    run.model_name = result.model
    run.output_chars = result.output_chars
    run.prompt_tokens = _usage_int(result.usage.get("prompt_tokens"))
    run.completion_tokens = _usage_int(result.usage.get("completion_tokens"))
    run.total_tokens = _usage_int(result.usage.get("total_tokens"))
    run.cost = _cost(result.usage.get("cost"))


def log_llm_task_run(run: LLMTaskRun) -> None:
    logger.info(
        "llm_task task_type=%s provider=%s model=%s object_type=%s object_id=%s "
        "field_key=%s run_id=%s status=%s error_code=%s duration_ms=%s "
        "input_chars=%s output_chars=%s prompt_tokens=%s completion_tokens=%s "
        "total_tokens=%s cost=%s",
        run.task_type,
        run.provider,
        run.model_name or "provider-default",
        run.object_type,
        run.object_id,
        run.field_key or "none",
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


@sensitive_variables("messages")
@transaction.atomic
def prepare_llm_task(
    *,
    task_type: str,
    actor,
    object_type: str,
    object_id: object,
    source_hash: str,
    prompt_version: str,
    schema_version: str,
    messages: list[dict[str, str]],
    field_key: str = "",
) -> PreparedLLMTask:
    if actor is None or getattr(actor, "pk", None) is None:
        raise LLMTaskError(
            "LLM-Tasks müssen von einem angemeldeten Benutzer gestartet werden.",
            code="invalid_actor",
        )
    try:
        policy = get_llm_task_policy(task_type)
    except LLMConfigurationError as exc:
        raise LLMTaskError(
            f"Die LLM-Task-Konfiguration ist ungültig: {exc}",
            code="invalid_configuration",
        ) from exc

    normalized_object_type = _require_text("object_type", object_type, max_length=50)
    normalized_object_id = _require_text("object_id", object_id, max_length=64)
    normalized_field_key = str(field_key or "").strip()
    if len(normalized_field_key) > 100:
        raise LLMTaskError(
            "field_key überschreitet die zulässige Länge.",
            code="invalid_task_context",
        )
    normalized_prompt_version = _require_text(
        "prompt_version",
        prompt_version,
        max_length=20,
    )
    normalized_schema_version = _require_text(
        "schema_version",
        schema_version,
        max_length=20,
    )
    normalized_source_hash = _validate_source_hash(source_hash)
    input_chars = _message_input_chars(messages)
    if input_chars > policy.max_input_chars:
        raise LLMTaskError(
            "Die für den LLM-Task vorgesehenen Eingaben überschreiten das Größenlimit.",
            code="input_too_large",
        )

    run = LLMTaskRun.objects.create(
        task_type=task_type,
        object_type=normalized_object_type,
        object_id=normalized_object_id,
        field_key=normalized_field_key,
        requested_by=actor,
        source_hash=normalized_source_hash,
        prompt_version=normalized_prompt_version,
        schema_version=normalized_schema_version,
        input_chars=input_chars,
        expires_at=timezone.now() + timedelta(days=policy.run_retention_days),
    )
    _reserve_quotas(
        actor=actor,
        task_type=task_type,
        object_type=normalized_object_type,
        object_id=normalized_object_id,
        field_key=normalized_field_key,
        policy=policy,
    )
    return PreparedLLMTask(run=run, policy=policy, messages=messages)


@transaction.atomic
def mark_llm_task_failed(
    *,
    run_id,
    error_code: str,
    result: OpenRouterResult | None = None,
) -> LLMTaskRun:
    run = LLMTaskRun.objects.select_for_update().get(pk=run_id)
    if run.status != LLMTaskRun.Status.RUNNING:
        return run
    finished_at = timezone.now()
    run.status = LLMTaskRun.Status.FAILED
    run.finished_at = finished_at
    run.duration_ms = _duration_ms(run, finished_at)
    run.error_code = _require_text("error_code", error_code, max_length=50)
    if result is not None:
        _apply_provider_metadata(run, result)
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "error_code",
            "model_name",
            "output_chars",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost",
            "updated_at",
        ]
    )
    log_llm_task_run(run)
    return run


@transaction.atomic
def record_llm_task_provider_result(
    *,
    run_id,
    result: OpenRouterResult,
) -> LLMTaskRun:
    run = LLMTaskRun.objects.select_for_update().get(pk=run_id)
    if run.status != LLMTaskRun.Status.RUNNING:
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
def mark_llm_task_success(*, run_id) -> LLMTaskRun:
    run = LLMTaskRun.objects.select_for_update().get(pk=run_id)
    if run.status != LLMTaskRun.Status.RUNNING:
        return run
    finished_at = timezone.now()
    run.status = LLMTaskRun.Status.SUCCESS
    run.finished_at = finished_at
    run.duration_ms = _duration_ms(run, finished_at)
    run.error_code = ""
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "error_code",
            "updated_at",
        ]
    )
    log_llm_task_run(run)
    return run


@sensitive_variables("prepared", "response_format")
def request_llm_task_provider(
    prepared: PreparedLLMTask,
    *,
    response_format: dict[str, Any],
) -> OpenRouterResult:
    try:
        result = request_openrouter(
            messages=prepared.messages,
            max_tokens=prepared.policy.max_output_tokens,
            timeout_seconds=prepared.policy.timeout_seconds,
            temperature=prepared.policy.temperature,
            response_format=response_format,
            provider=dict(FIRST_WAVE_PROVIDER_POLICY),
            reasoning_effort=prepared.policy.reasoning_effort,
        )
    except OpenRouterUnavailable as exc:
        mark_llm_task_failed(run_id=prepared.run.pk, error_code=exc.code)
        raise LLMTaskError(str(exc), code=exc.code) from exc

    if result.finish_reason == "length":
        mark_llm_task_failed(
            run_id=prepared.run.pk,
            error_code="output_truncated",
            result=result,
        )
        raise LLMTaskError(
            "Die LLM-Antwort wurde wegen des Ausgabelimits abgeschnitten.",
            code="output_truncated",
        )

    recorded = record_llm_task_provider_result(run_id=prepared.run.pk, result=result)
    if recorded.status != LLMTaskRun.Status.RUNNING:
        raise LLMTaskError(
            "Dieser LLM-Task wurde serverseitig bereits beendet und verworfen.",
            code="task_superseded",
        )
    return result
