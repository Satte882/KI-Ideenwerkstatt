from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from ki_radar.core.llm_policy import LLMConfigurationError, get_accelerator_llm_policy
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable, request_openrouter

from .models import SolutionGenerationRun, SolutionQualityRun
from .solution_critic_contract import (
    SolutionCriticContractError,
    build_solution_critic_json_schema,
    validate_solution_critic_payload,
)
from .solution_critic_prompt import build_solution_critic_messages
from .solution_generation_service import (
    SolutionGenerationQuotaExceeded,
    _reserve_solution_generation_quotas,
)
from .solution_generation_sources import (
    ALLOWED_SOURCE_IDS,
    SOURCE_SCHEMA_VERSION,
    SolutionGenerationSourceContext,
    SourceFact,
)
from .solution_quality_runs import (
    mark_solution_quality_step_failed,
    mark_solution_quality_step_success,
    reserve_solution_quality_step,
)
from .solution_quality_snapshot import build_solution_quality_snapshot
from .solution_quality_versions import CRITIC_PROMPT_VERSION, CRITIC_SCHEMA_VERSION

logger = logging.getLogger(__name__)


class InitialSolutionCriticError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class FinalSolutionCriticError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _source_context_from_generation_run(
    generation_run: SolutionGenerationRun,
) -> SolutionGenerationSourceContext:
    payload = generation_run.preview_payload.get("source_context")
    if not isinstance(payload, dict):
        raise InitialSolutionCriticError(
            "Die persistierte Preview enthält keinen gültigen Quellenkontext.",
            code="critic_source_context_invalid",
        )
    if payload.get("source_schema_version") != SOURCE_SCHEMA_VERSION:
        raise InitialSolutionCriticError(
            "Die persistierte Preview verwendet eine unbekannte Quellenkontext-Version.",
            code="critic_source_context_invalid",
        )
    if payload.get("process_version") != generation_run.process_version:
        raise InitialSolutionCriticError(
            "Prozessversion von Preview und Generation-Run stimmen nicht überein.",
            code="critic_source_context_invalid",
        )

    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, list):
        raise InitialSolutionCriticError(
            "Die persistierte Preview enthält keine gültige Quellenliste.",
            code="critic_source_context_invalid",
        )
    facts: list[SourceFact] = []
    for item in raw_facts:
        if not isinstance(item, dict):
            raise InitialSolutionCriticError(
                "Die persistierte Preview enthält einen ungültigen Quelleneintrag.",
                code="critic_source_context_invalid",
            )
        source_id = str(item.get("source_id") or "").strip()
        field = str(item.get("field") or "").strip()
        value = str(item.get("value") or "").strip()
        if source_id not in ALLOWED_SOURCE_IDS or not field or not value:
            raise InitialSolutionCriticError(
                "Die persistierte Preview enthält einen ungültigen Quelleneintrag.",
                code="critic_source_context_invalid",
            )
        facts.append(SourceFact(source_id=source_id, field=field, value=value))

    validation_state = str(payload.get("validation_state") or "").strip()
    if not validation_state:
        raise InitialSolutionCriticError(
            "Die persistierte Preview enthält keinen Validierungsstatus.",
            code="critic_source_context_invalid",
        )
    return SolutionGenerationSourceContext(
        process_analysis_id=str(generation_run.process_analysis_id),
        process_version=generation_run.process_version,
        validation_state=validation_state,
        source_hash=generation_run.source_hash,
        missing_required=(),
        facts=tuple(facts),
    )


def _usage_int(value: object) -> int | None:
    if value in {None, ""}:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _cost(value: object) -> Decimal | None:
    if value in {None, ""}:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _failed_quality_step(
    *,
    run_id,
    error_code: str,
    result: OpenRouterResult | None = None,
) -> SolutionQualityRun:
    failed = mark_solution_quality_step_failed(
        run_id=run_id,
        error_code=error_code,
        model_name=result.model if result is not None else "",
        output_chars=result.output_chars if result is not None else 0,
    )
    if result is None:
        return failed
    failed.prompt_tokens = _usage_int(result.usage.get("prompt_tokens"))
    failed.completion_tokens = _usage_int(result.usage.get("completion_tokens"))
    failed.total_tokens = _usage_int(result.usage.get("total_tokens"))
    failed.cost = _cost(result.usage.get("cost"))
    failed.save(
        update_fields=[
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost",
            "updated_at",
        ]
    )
    return failed


def _success_quality_step(
    *,
    run_id,
    payload: dict[str, Any],
    result: OpenRouterResult,
) -> SolutionQualityRun:
    return mark_solution_quality_step_success(
        run_id=run_id,
        result_payload=payload,
        model_name=result.model,
        output_chars=result.output_chars,
        prompt_tokens=_usage_int(result.usage.get("prompt_tokens")),
        completion_tokens=_usage_int(result.usage.get("completion_tokens")),
        total_tokens=_usage_int(result.usage.get("total_tokens")),
        cost=_cost(result.usage.get("cost")),
    )


def _reserve_critic_quotas(*, generation_run: SolutionGenerationRun, policy) -> None:
    actor = generation_run.requested_by
    if actor is None:
        raise InitialSolutionCriticError(
            "Der Critic kann keinem Benutzer zugeordnet werden.",
            code="critic_actor_unavailable",
        )
    with transaction.atomic():
        _reserve_solution_generation_quotas(
            actor=actor,
            process_analysis=generation_run.process_analysis,
            policy=policy,
            quota_date=timezone.localdate(),
        )


def _successful_repair_run(generation_run: SolutionGenerationRun) -> SolutionQualityRun:
    try:
        repair_run = SolutionQualityRun.objects.get(
            solution_generation_run=generation_run,
            step_type=SolutionQualityRun.StepType.REPAIR,
        )
    except SolutionQualityRun.DoesNotExist as exc:
        raise FinalSolutionCriticError(
            "Der Final Critic benötigt einen erfolgreichen Repair.",
            code="final_critic_repair_unavailable",
        ) from exc
    if repair_run.status != SolutionQualityRun.Status.SUCCESS:
        raise FinalSolutionCriticError(
            "Der Final Critic darf nur nach einem erfolgreichen Repair laufen.",
            code="final_critic_repair_unavailable",
        )
    return repair_run


def _repair_output_snapshot_hash(
    *,
    generation_run: SolutionGenerationRun,
    repair_run: SolutionQualityRun,
) -> str:
    machine_repair = generation_run.preview_payload.get("machine_repair")
    if not isinstance(machine_repair, dict) or machine_repair.get("quality_run_id") != str(
        repair_run.pk
    ):
        raise FinalSolutionCriticError(
            "Die reparierte Preview ist nicht an den erfolgreichen Repair-Run gebunden.",
            code="final_critic_repair_binding_invalid",
        )
    result_payload = repair_run.result_payload
    output_snapshot_hash = (
        result_payload.get("output_snapshot_hash") if isinstance(result_payload, dict) else None
    )
    if not isinstance(output_snapshot_hash, str) or len(output_snapshot_hash) != 64:
        raise FinalSolutionCriticError(
            "Der erfolgreiche Repair enthält keinen gültigen Output-Snapshot.",
            code="final_critic_repair_binding_invalid",
        )
    return output_snapshot_hash


@sensitive_variables("source_context", "snapshot", "messages", "result", "payload")
def _run_solution_critic(
    *,
    solution_generation_run_id,
    step_type: str,
    expected_input_hash: str | None = None,
) -> SolutionQualityRun:
    generation_run = SolutionGenerationRun.objects.select_related(
        "process_analysis", "requested_by"
    ).get(pk=solution_generation_run_id)
    if (
        generation_run.status != SolutionGenerationRun.Status.SUCCESS
        or not generation_run.preview_payload
    ):
        raise InitialSolutionCriticError(
            "Der Critic benötigt eine persistierte valide Lösungs-Preview.",
            code="critic_preview_unavailable",
        )

    source_context = _source_context_from_generation_run(generation_run)
    snapshot = build_solution_quality_snapshot(
        preview_payload=generation_run.preview_payload,
        source_context=source_context,
    )
    messages = build_solution_critic_messages(snapshot, source_context)
    input_chars = sum(len(message["content"]) for message in messages)
    reservation = reserve_solution_quality_step(
        solution_generation_run_id=generation_run.pk,
        actor=generation_run.requested_by,
        step_type=step_type,
        input_hash=snapshot.snapshot_hash,
        prompt_version=CRITIC_PROMPT_VERSION,
        output_schema_version=CRITIC_SCHEMA_VERSION,
        input_chars=input_chars,
    )
    if not reservation.created:
        return reservation.run

    quality_run = reservation.run
    if expected_input_hash is not None and snapshot.snapshot_hash != expected_input_hash:
        return _failed_quality_step(run_id=quality_run.pk, error_code="final_critic_stale")

    try:
        policy = get_accelerator_llm_policy()
    except LLMConfigurationError:
        return _failed_quality_step(run_id=quality_run.pk, error_code="invalid_configuration")

    if input_chars > policy.solution_critic_max_input_chars:
        return _failed_quality_step(run_id=quality_run.pk, error_code="input_too_large")

    try:
        _reserve_critic_quotas(generation_run=generation_run, policy=policy)
    except SolutionGenerationQuotaExceeded as exc:
        return _failed_quality_step(run_id=quality_run.pk, error_code=exc.code)
    except InitialSolutionCriticError as exc:
        return _failed_quality_step(run_id=quality_run.pk, error_code=exc.code)

    response_schema = build_solution_critic_json_schema(
        allowed_source_ids=(fact.source_id for fact in source_context.facts)
    )
    try:
        result = request_openrouter(
            messages=messages,
            max_tokens=policy.max_output_tokens,
            timeout_seconds=policy.timeout_seconds,
            temperature=None,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "accelerator_solution_critic_v1",
                    "strict": True,
                    "schema": response_schema,
                },
            },
            provider={"require_parameters": True},
        )
    except OpenRouterUnavailable as exc:
        return _failed_quality_step(run_id=quality_run.pk, error_code=exc.code)
    except Exception:
        logger.exception(
            "solution_critic provider_failure generation_run_id=%s quality_run_id=%s step_type=%s",
            generation_run.pk,
            quality_run.pk,
            step_type,
        )
        return _failed_quality_step(run_id=quality_run.pk, error_code="internal_error")

    if result.finish_reason == "length":
        return _failed_quality_step(
            run_id=quality_run.pk,
            error_code="output_truncated",
            result=result,
        )

    try:
        payload = json.loads(result.content)
    except json.JSONDecodeError:
        return _failed_quality_step(
            run_id=quality_run.pk,
            error_code="invalid_response",
            result=result,
        )
    if not isinstance(payload, dict):
        return _failed_quality_step(
            run_id=quality_run.pk,
            error_code="invalid_response",
            result=result,
        )

    try:
        validated = validate_solution_critic_payload(payload, source_context)
    except SolutionCriticContractError as exc:
        logger.warning(
            "solution_critic contract_failure generation_run_id=%s quality_run_id=%s "
            "step_type=%s validation_errors=%s",
            generation_run.pk,
            quality_run.pk,
            step_type,
            exc.errors,
        )
        return _failed_quality_step(
            run_id=quality_run.pk,
            error_code="invalid_critic_payload",
            result=result,
        )
    return _success_quality_step(run_id=quality_run.pk, payload=validated, result=result)


def run_initial_solution_critic(*, solution_generation_run_id) -> SolutionQualityRun:
    return _run_solution_critic(
        solution_generation_run_id=solution_generation_run_id,
        step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
    )


def run_final_solution_critic(*, solution_generation_run_id) -> SolutionQualityRun:
    generation_run = SolutionGenerationRun.objects.get(pk=solution_generation_run_id)
    repair_run = _successful_repair_run(generation_run)
    expected_input_hash = _repair_output_snapshot_hash(
        generation_run=generation_run,
        repair_run=repair_run,
    )
    return _run_solution_critic(
        solution_generation_run_id=solution_generation_run_id,
        step_type=SolutionQualityRun.StepType.FINAL_CRITIC,
        expected_input_hash=expected_input_hash,
    )
