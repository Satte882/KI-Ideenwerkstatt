from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict

from ki_radar.core.llm_policy import LLMConfigurationError, get_accelerator_llm_policy
from ki_radar.core.openrouter import OpenRouterUnavailable, request_openrouter

from .models import UseCase
from .services import current_decision_check

logger = logging.getLogger(__name__)


class CopilotUnavailable(RuntimeError):
    def __init__(self, message: str, *, code: str = "unavailable") -> None:
        super().__init__(message)
        self.code = code


def _payload_for_use_case(use_case: UseCase) -> dict:
    decision = current_decision_check(use_case)
    return {
        "id": use_case.short_id,
        "title": use_case.title,
        "status": use_case.get_status_display(),
        "problem": use_case.problem_statement,
        "expected_benefit": use_case.expected_benefit,
        "primary_metric": {
            "name": use_case.metric_name,
            "type": use_case.get_metric_type_display() if use_case.metric_type else "",
            "direction": (
                use_case.get_metric_direction_display() if use_case.metric_direction else ""
            ),
            "unit": use_case.metric_unit,
            "baseline": (
                str(use_case.metric_baseline) if use_case.metric_baseline is not None else ""
            ),
            "target": str(use_case.metric_target) if use_case.metric_target is not None else "",
            "actual": str(use_case.metric_actual) if use_case.metric_actual is not None else "",
            "method": use_case.metric_measurement_method,
            "period": use_case.metric_measurement_period,
        },
        "legacy_success_criterion": use_case.success_criterion,
        "legacy_result": use_case.realized_result,
        "costs": {
            "one_time": str(use_case.one_time_cost or ""),
            "recurring": str(use_case.recurring_cost or ""),
        },
        "deterministic_check": asdict(decision),
    }


def _log_request(
    *,
    use_case: UseCase,
    model: str,
    status: str,
    error_code: str,
    started_at: float,
    input_chars: int,
    output_chars: int,
    usage: dict[str, object],
) -> None:
    logger.info(
        "llm_request purpose=use_case_review provider=openrouter model=%s "
        "object_type=use_case object_id=%s status=%s error_code=%s "
        "duration_ms=%s input_chars=%s output_chars=%s "
        "prompt_tokens=%s completion_tokens=%s total_tokens=%s cost=%s",
        model or "provider-default",
        getattr(use_case, "pk", ""),
        status,
        error_code or "none",
        round((time.monotonic() - started_at) * 1000),
        input_chars,
        output_chars,
        usage.get("prompt_tokens", ""),
        usage.get("completion_tokens", ""),
        usage.get("total_tokens", ""),
        usage.get("cost", ""),
    )


def analyze_use_case(use_case: UseCase) -> str:
    started_at = time.monotonic()
    status = "failed"
    error_code = "unexpected"
    input_chars = 0
    output_chars = 0
    usage: dict[str, object] = {}
    model = ""

    try:
        try:
            policy = get_accelerator_llm_policy()
        except LLMConfigurationError as exc:
            error_code = "invalid_configuration"
            raise CopilotUnavailable(
                f"Die LLM-Konfiguration ist ungültig: {exc}",
                code=error_code,
            ) from exc

        system_prompt = (
            "Du bist ein kritischer Review-Copilot für KI-Piloten in deutschen KMU. "
            "Du triffst keine Freigabeentscheidung und ersetzt keine Rechts-, Datenschutz- oder "
            "Security-Prüfung. Prüfe ausschließlich die semantische Konsistenz zwischen Problem, "
            "erwartetem Nutzen, primärer Erfolgsmetrik, Ziel, gemessenem Ergebnis, Kosten und der "
            "anstehenden Entscheidung. Antworte auf Deutsch, kompakt und ohne erfundene Fakten. "
            "Nutze genau die Überschriften 'Konsistenz', 'Auffälligkeiten', 'Rückfragen' und "
            "'Entscheidungshinweis'. Kennzeichne Unsicherheit ausdrücklich."
        )
        user_content = json.dumps(_payload_for_use_case(use_case), ensure_ascii=False)
        input_chars = len(system_prompt) + len(user_content)
        if input_chars > policy.max_input_chars:
            error_code = "input_too_large"
            raise CopilotUnavailable(
                "Die für die Analyse vorgesehenen Eingaben überschreiten das konfigurierte "
                "Größenlimit.",
                code=error_code,
            )

        try:
            result = request_openrouter(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=policy.max_output_tokens,
                timeout_seconds=policy.timeout_seconds,
                temperature=0.1,
            )
        except OpenRouterUnavailable as exc:
            error_code = exc.code
            raise CopilotUnavailable(str(exc), code=exc.code) from exc

        model = result.model
        usage = result.usage
        output_chars = result.output_chars
        status = "success"
        error_code = ""
        return result.content
    finally:
        _log_request(
            use_case=use_case,
            model=model,
            status=status,
            error_code=error_code,
            started_at=started_at,
            input_chars=input_chars,
            output_chars=output_chars,
            usage=usage,
        )
