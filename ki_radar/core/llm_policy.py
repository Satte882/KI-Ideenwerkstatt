from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from django.conf import settings


class LLMConfigurationError(RuntimeError):
    """Raised when an LLM setting is invalid."""


@dataclass(frozen=True)
class AcceleratorLLMPolicy:
    timeout_seconds: int
    max_input_chars: int
    max_output_tokens: int
    capture_max_output_tokens: int
    capture_temperature: float | None
    max_calls_per_context: int
    max_calls_per_user_day: int
    max_calls_global_day: int
    solution_generation_max_output_tokens: int
    solution_generation_max_calls_per_context: int
    solution_critic_max_input_chars: int


@dataclass(frozen=True)
class LLMTaskPolicy:
    task_type: str
    timeout_seconds: int
    max_input_chars: int
    max_output_tokens: int
    reasoning_effort: str
    temperature: float
    max_calls_per_context_day: int
    max_calls_per_user_day: int
    max_calls_global_day: int
    run_retention_days: int


_SETTING_BOUNDS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": (1, 120),
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": (1, 100_000),
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": (1, 4_096),
    "ACCELERATOR_CAPTURE_MAX_OUTPUT_TOKENS": (1, 32_768),
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": (1, 50),
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": (1, 1_000),
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": (1, 100_000),
    "ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS": (4_096, 16_384),
    "ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT": (1, 50),
    "ACCELERATOR_SOLUTION_CRITIC_MAX_INPUT_CHARS": (1, 100_000),
}

_TASK_SETTING_BOUNDS = {
    "LLM_TASK_TIMEOUT_SECONDS": (1, 120),
    "LLM_TASK_MAX_CALLS_PER_CONTEXT_DAY": (1, 50),
    "LLM_TASK_MAX_CALLS_PER_USER_DAY": (1, 1_000),
    "LLM_TASK_MAX_CALLS_GLOBAL_DAY": (1, 100_000),
    "LLM_TASK_RUN_RETENTION_DAYS": (1, 365),
    "LLM_DELIVERY_FIELD_DRAFT_MAX_INPUT_CHARS": (1, 100_000),
    "LLM_DELIVERY_FIELD_DRAFT_MAX_OUTPUT_TOKENS": (1, 32_768),
    "LLM_ORIGIN_CONSISTENCY_REVIEW_MAX_INPUT_CHARS": (1, 100_000),
    "LLM_ORIGIN_CONSISTENCY_REVIEW_MAX_OUTPUT_TOKENS": (1, 32_768),
}

_TASK_DEFAULTS = {
    "LLM_TASK_TIMEOUT_SECONDS": "60",
    "LLM_TASK_MAX_CALLS_PER_CONTEXT_DAY": "3",
    "LLM_TASK_MAX_CALLS_PER_USER_DAY": "20",
    "LLM_TASK_MAX_CALLS_GLOBAL_DAY": "100",
    "LLM_TASK_RUN_RETENTION_DAYS": "90",
    "LLM_TASK_TEMPERATURE": "0.1",
    "LLM_DELIVERY_FIELD_DRAFT_MAX_INPUT_CHARS": "12000",
    "LLM_DELIVERY_FIELD_DRAFT_MAX_OUTPUT_TOKENS": "16384",
    "LLM_DELIVERY_FIELD_DRAFT_REASONING_EFFORT": "low",
    "LLM_ORIGIN_CONSISTENCY_REVIEW_MAX_INPUT_CHARS": "16000",
    "LLM_ORIGIN_CONSISTENCY_REVIEW_MAX_OUTPUT_TOKENS": "4096",
    "LLM_ORIGIN_CONSISTENCY_REVIEW_REASONING_EFFORT": "medium",
}

_TASK_SETTINGS = {
    "delivery_field_draft": {
        "input": "LLM_DELIVERY_FIELD_DRAFT_MAX_INPUT_CHARS",
        "output": "LLM_DELIVERY_FIELD_DRAFT_MAX_OUTPUT_TOKENS",
        "reasoning": "LLM_DELIVERY_FIELD_DRAFT_REASONING_EFFORT",
    },
    "origin_consistency_review": {
        "input": "LLM_ORIGIN_CONSISTENCY_REVIEW_MAX_INPUT_CHARS",
        "output": "LLM_ORIGIN_CONSISTENCY_REVIEW_MAX_OUTPUT_TOKENS",
        "reasoning": "LLM_ORIGIN_CONSISTENCY_REVIEW_REASONING_EFFORT",
    },
}


def _bounded_int(name: str, value: Any, bounds: dict[str, tuple[int, int]]) -> int:
    lower, upper = bounds[name]
    if isinstance(value, bool):
        raise LLMConfigurationError(f"{name} muss eine ganze Zahl sein.")
    raw = str(value).strip()
    try:
        parsed = int(raw)
    except (TypeError, ValueError) as exc:
        raise LLMConfigurationError(f"{name} muss eine ganze Zahl sein.") from exc
    if not lower <= parsed <= upper:
        raise LLMConfigurationError(f"{name} muss zwischen {lower} und {upper} liegen.")
    return parsed


def _positive_int(name: str, value: Any) -> int:
    return _bounded_int(name, value, _SETTING_BOUNDS)


def _optional_temperature(value: Any) -> float | None:
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = float(raw)
    except (TypeError, ValueError) as exc:
        raise LLMConfigurationError(
            "ACCELERATOR_CAPTURE_TEMPERATURE muss leer oder eine Zahl sein."
        ) from exc
    if not 0.0 <= parsed <= 2.0:
        raise LLMConfigurationError("ACCELERATOR_CAPTURE_TEMPERATURE muss zwischen 0 und 2 liegen.")
    return parsed


def _task_temperature(value: Any) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise LLMConfigurationError("LLM_TASK_TEMPERATURE muss eine Zahl sein.") from exc
    if not 0.0 <= parsed <= 2.0:
        raise LLMConfigurationError("LLM_TASK_TEMPERATURE muss zwischen 0 und 2 liegen.")
    return parsed


def _reasoning_effort(name: str, value: Any) -> str:
    parsed = str(value).strip().casefold()
    if parsed not in {"low", "medium", "high"}:
        raise LLMConfigurationError(f"{name} muss low, medium oder high sein.")
    return parsed


def _task_setting(name: str) -> Any:
    default = _TASK_DEFAULTS[name]
    return getattr(settings, name, os.getenv(name, default))


def get_accelerator_llm_policy() -> AcceleratorLLMPolicy:
    """Return the validated repository-wide Accelerator LLM limits.

    Compact Accelerator calls keep the shared output/context limits. Capture
    structured extraction and the much larger Block-7 three-option bundle have
    dedicated output limits so they can be sized realistically without widening
    every Accelerator LLM call. User and global limits remain effective upper
    caps for every purpose.
    """

    values = {name: _positive_int(name, getattr(settings, name)) for name in _SETTING_BOUNDS}
    context_limit = values["ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT"]
    solution_context_limit = values["ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT"]
    user_limit = values["ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY"]
    global_limit = values["ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY"]
    if context_limit > user_limit:
        raise LLMConfigurationError(
            "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT darf die nutzerbezogene "
            "Tagesgrenze nicht überschreiten."
        )
    if user_limit > global_limit:
        raise LLMConfigurationError(
            "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY darf die globale "
            "Tagesgrenze nicht überschreiten."
        )
    return AcceleratorLLMPolicy(
        timeout_seconds=values["ACCELERATOR_LLM_TIMEOUT_SECONDS"],
        max_input_chars=values["ACCELERATOR_LLM_MAX_INPUT_CHARS"],
        max_output_tokens=values["ACCELERATOR_LLM_MAX_OUTPUT_TOKENS"],
        capture_max_output_tokens=values["ACCELERATOR_CAPTURE_MAX_OUTPUT_TOKENS"],
        capture_temperature=_optional_temperature(
            getattr(settings, "ACCELERATOR_CAPTURE_TEMPERATURE", "")
        ),
        max_calls_per_context=context_limit,
        max_calls_per_user_day=user_limit,
        max_calls_global_day=global_limit,
        solution_generation_max_output_tokens=values[
            "ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS"
        ],
        solution_generation_max_calls_per_context=solution_context_limit,
        solution_critic_max_input_chars=values["ACCELERATOR_SOLUTION_CRITIC_MAX_INPUT_CHARS"],
    )


def get_llm_task_policy(task_type: str) -> LLMTaskPolicy:
    """Return validated limits for one explicitly supported first-wave task."""

    task_settings = _TASK_SETTINGS.get(task_type)
    if task_settings is None:
        raise LLMConfigurationError(f"Unbekannter LLM-Task: {task_type}.")

    values = {
        name: _bounded_int(name, _task_setting(name), _TASK_SETTING_BOUNDS)
        for name in _TASK_SETTING_BOUNDS
    }
    context_limit = values["LLM_TASK_MAX_CALLS_PER_CONTEXT_DAY"]
    user_limit = values["LLM_TASK_MAX_CALLS_PER_USER_DAY"]
    global_limit = values["LLM_TASK_MAX_CALLS_GLOBAL_DAY"]
    if context_limit > user_limit:
        raise LLMConfigurationError(
            "LLM_TASK_MAX_CALLS_PER_CONTEXT_DAY darf die nutzerbezogene "
            "Tagesgrenze nicht überschreiten."
        )
    if user_limit > global_limit:
        raise LLMConfigurationError(
            "LLM_TASK_MAX_CALLS_PER_USER_DAY darf die globale Tagesgrenze nicht überschreiten."
        )

    reasoning_setting = task_settings["reasoning"]
    return LLMTaskPolicy(
        task_type=task_type,
        timeout_seconds=values["LLM_TASK_TIMEOUT_SECONDS"],
        max_input_chars=values[task_settings["input"]],
        max_output_tokens=values[task_settings["output"]],
        reasoning_effort=_reasoning_effort(
            reasoning_setting,
            _task_setting(reasoning_setting),
        ),
        temperature=_task_temperature(_task_setting("LLM_TASK_TEMPERATURE")),
        max_calls_per_context_day=context_limit,
        max_calls_per_user_day=user_limit,
        max_calls_global_day=global_limit,
        run_retention_days=values["LLM_TASK_RUN_RETENTION_DAYS"],
    )
