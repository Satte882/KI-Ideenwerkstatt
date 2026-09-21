from __future__ import annotations

import json
import logging
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from ki_radar.core.llm_policy import LLMConfigurationError, get_accelerator_llm_policy
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable, request_openrouter

from .models import SolutionGenerationRun, SolutionQualityRun
from .solution_generation_effective import (
    SolutionGenerationEffectivePayloadError,
    build_validated_effective_solution_payload,
)
from .solution_generation_service import (
    SolutionGenerationQuotaExceeded,
    _reserve_solution_generation_quotas,
)
from .solution_generation_sources import build_solution_generation_source_context
from .solution_quality_runs import (
    SolutionQualityRunError,
    mark_solution_quality_step_failed,
    mark_solution_quality_step_success,
)
from .solution_quality_snapshot import build_solution_quality_snapshot
from .solution_repair_contract import (
    SolutionRepairContractError,
    SolutionRepairPlan,
    build_solution_repair_plan,
    reserve_solution_repair_attempt,
)
from .solution_repair_output import (
    SolutionRepairPayloadError,
    build_solution_repair_json_schema,
    validate_solution_repair_payload,
)
from .solution_repair_prompt import build_solution_repair_messages

logger = logging.getLogger(__name__)


class TargetedSolutionRepairError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


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


def _failed_repair_step(
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


def _reserve_repair_quotas(*, generation_run: SolutionGenerationRun, actor, policy) -> None:
    if actor is None:
        raise TargetedSolutionRepairError(
            "Der Repair kann keinem Benutzer zugeordnet werden.",
            code="repair_actor_unavailable",
        )
    with transaction.atomic():
        _reserve_solution_generation_quotas(
            actor=actor,
            process_analysis=generation_run.process_analysis,
            policy=policy,
            quota_date=timezone.localdate(),
        )


def _same_plan(left: SolutionRepairPlan, right: SolutionRepairPlan) -> bool:
    return (
        left.snapshot_hash == right.snapshot_hash
        and left.finding_ids == right.finding_ids
        and left.targets == right.targets
    )


def _load_repair_input(*, solution_generation_run_id, reserved_plan: SolutionRepairPlan):
    generation_run = (
        SolutionGenerationRun.objects.select_related(
            "process_analysis__stage__value_stream",
            "requested_by",
        )
        .prefetch_related("process_analysis__validations")
        .get(pk=solution_generation_run_id)
    )
    initial_critic = SolutionQualityRun.objects.get(
        solution_generation_run=generation_run,
        step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
    )
    current_plan = build_solution_repair_plan(
        generation_run=generation_run,
        initial_critic_run=initial_critic,
    )
    if not _same_plan(current_plan, reserved_plan):
        raise SolutionRepairContractError(
            "Der Repair-Kontext hat sich seit der Reservierung geändert.",
            code="repair_stale",
            stale_reason="quality_snapshot_changed",
        )

    source_context = build_solution_generation_source_context(generation_run.process_analysis)
    effective_payload = build_validated_effective_solution_payload(
        generation_run.preview_payload,
        source_context,
    )
    messages = build_solution_repair_messages(
        plan=current_plan,
        initial_critic_run=initial_critic,
        effective_payload=effective_payload,
        source_context=source_context,
    )
    return generation_run, current_plan, source_context, effective_payload, messages


@transaction.atomic
def _activate_repair(
    *,
    solution_generation_run_id,
    quality_run_id,
    expected_plan: SolutionRepairPlan,
    repair_payload: dict,
    result: OpenRouterResult,
) -> SolutionQualityRun:
    generation_run = (
        SolutionGenerationRun.objects.select_for_update()
        .select_related("process_analysis__stage__value_stream")
        .prefetch_related("process_analysis__validations")
        .get(pk=solution_generation_run_id)
    )
    quality_run = SolutionQualityRun.objects.select_for_update().get(pk=quality_run_id)
    if (
        quality_run.solution_generation_run_id != generation_run.pk
        or quality_run.step_type != SolutionQualityRun.StepType.REPAIR
        or quality_run.status != SolutionQualityRun.Status.RUNNING
    ):
        raise TargetedSolutionRepairError(
            "Der reservierte Repair-Step ist nicht mehr aktiv.",
            code="repair_step_terminal",
        )

    initial_critic = SolutionQualityRun.objects.get(
        solution_generation_run=generation_run,
        step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
    )
    current_plan = build_solution_repair_plan(
        generation_run=generation_run,
        initial_critic_run=initial_critic,
    )
    if (
        not _same_plan(current_plan, expected_plan)
        or quality_run.input_hash != current_plan.snapshot_hash
    ):
        raise SolutionRepairContractError(
            "Die Preview oder der Repair-Vertrag hat sich während des Repairs geändert.",
            code="repair_stale",
            stale_reason="quality_snapshot_changed",
        )

    source_context = build_solution_generation_source_context(generation_run.process_analysis)
    effective_payload = build_validated_effective_solution_payload(
        generation_run.preview_payload,
        source_context,
    )
    validated_repair = validate_solution_repair_payload(
        repair_payload,
        plan=current_plan,
        effective_payload=effective_payload,
        source_context=source_context,
    )

    candidate_preview = deepcopy(generation_run.preview_payload)
    candidate_preview["machine_repair"] = {
        "quality_run_id": str(quality_run.pk),
        "input_hash": current_plan.snapshot_hash,
        "prompt_version": quality_run.prompt_version,
        "schema_version": quality_run.output_schema_version,
        "patches": deepcopy(validated_repair["patches"]),
    }
    build_validated_effective_solution_payload(candidate_preview, source_context)
    output_snapshot = build_solution_quality_snapshot(
        preview_payload=candidate_preview,
        source_context=source_context,
    )

    generation_run.preview_payload = candidate_preview
    generation_run.save(update_fields=["preview_payload", "updated_at"])
    persisted_result = {
        "repair_payload": validated_repair,
        "finding_ids": list(current_plan.finding_ids),
        "input_hash": current_plan.snapshot_hash,
        "output_snapshot_hash": output_snapshot.snapshot_hash,
    }
    return mark_solution_quality_step_success(
        run_id=quality_run.pk,
        result_payload=persisted_result,
        model_name=result.model,
        output_chars=result.output_chars,
        prompt_tokens=_usage_int(result.usage.get("prompt_tokens")),
        completion_tokens=_usage_int(result.usage.get("completion_tokens")),
        total_tokens=_usage_int(result.usage.get("total_tokens")),
        cost=_cost(result.usage.get("cost")),
    )


@sensitive_variables(
    "reserved_plan",
    "source_context",
    "effective_payload",
    "messages",
    "result",
    "payload",
    "validated",
)
def run_targeted_solution_repair(
    *,
    solution_generation_run_id,
    actor,
) -> SolutionQualityRun:
    reservation = reserve_solution_repair_attempt(
        solution_generation_run_id=solution_generation_run_id,
        actor=actor,
    )
    quality_run = reservation.run
    reserved_plan = reservation.plan

    try:
        generation_run, current_plan, source_context, effective_payload, messages = (
            _load_repair_input(
                solution_generation_run_id=solution_generation_run_id,
                reserved_plan=reserved_plan,
            )
        )
    except (
        SolutionRepairContractError,
        SolutionGenerationEffectivePayloadError,
        ValueError,
    ) as exc:
        error_code = getattr(exc, "code", "invalid_repair_context")
        return _failed_repair_step(run_id=quality_run.pk, error_code=error_code)

    input_chars = sum(len(message["content"]) for message in messages)
    SolutionQualityRun.objects.filter(
        pk=quality_run.pk,
        status=SolutionQualityRun.Status.RUNNING,
    ).update(input_chars=input_chars)

    try:
        policy = get_accelerator_llm_policy()
    except LLMConfigurationError:
        return _failed_repair_step(run_id=quality_run.pk, error_code="invalid_configuration")

    if input_chars > policy.solution_critic_max_input_chars:
        return _failed_repair_step(run_id=quality_run.pk, error_code="input_too_large")

    try:
        _reserve_repair_quotas(generation_run=generation_run, actor=actor, policy=policy)
    except SolutionGenerationQuotaExceeded as exc:
        return _failed_repair_step(run_id=quality_run.pk, error_code=exc.code)
    except TargetedSolutionRepairError as exc:
        return _failed_repair_step(run_id=quality_run.pk, error_code=exc.code)

    response_schema = build_solution_repair_json_schema(
        allowed_source_ids=(fact.source_id for fact in source_context.facts),
        target_count=len(current_plan.targets),
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
                    "name": "accelerator_solution_repair_v1",
                    "strict": True,
                    "schema": response_schema,
                },
            },
            provider={"require_parameters": True},
        )
    except OpenRouterUnavailable as exc:
        return _failed_repair_step(run_id=quality_run.pk, error_code=exc.code)
    except Exception:
        logger.exception(
            "targeted_solution_repair provider_failure generation_run_id=%s quality_run_id=%s",
            solution_generation_run_id,
            quality_run.pk,
        )
        return _failed_repair_step(run_id=quality_run.pk, error_code="internal_error")

    if result.finish_reason == "length":
        return _failed_repair_step(
            run_id=quality_run.pk,
            error_code="output_truncated",
            result=result,
        )

    try:
        payload = json.loads(result.content)
    except json.JSONDecodeError:
        return _failed_repair_step(
            run_id=quality_run.pk,
            error_code="invalid_response",
            result=result,
        )
    if not isinstance(payload, dict):
        return _failed_repair_step(
            run_id=quality_run.pk,
            error_code="invalid_response",
            result=result,
        )

    try:
        validated = validate_solution_repair_payload(
            payload,
            plan=current_plan,
            effective_payload=effective_payload,
            source_context=source_context,
        )
    except SolutionRepairPayloadError as exc:
        logger.warning(
            "targeted_solution_repair contract_failure generation_run_id=%s "
            "quality_run_id=%s validation_errors=%s",
            solution_generation_run_id,
            quality_run.pk,
            exc.errors,
        )
        return _failed_repair_step(
            run_id=quality_run.pk,
            error_code="invalid_repair_payload",
            result=result,
        )

    try:
        return _activate_repair(
            solution_generation_run_id=solution_generation_run_id,
            quality_run_id=quality_run.pk,
            expected_plan=current_plan,
            repair_payload=validated,
            result=result,
        )
    except SolutionRepairContractError as exc:
        return _failed_repair_step(run_id=quality_run.pk, error_code=exc.code, result=result)
    except (SolutionRepairPayloadError, SolutionGenerationEffectivePayloadError):
        return _failed_repair_step(
            run_id=quality_run.pk,
            error_code="invalid_repair_payload",
            result=result,
        )
    except (TargetedSolutionRepairError, SolutionQualityRunError) as exc:
        error_code = getattr(exc, "code", "internal_error")
        return _failed_repair_step(run_id=quality_run.pk, error_code=error_code, result=result)
