from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from ki_radar.core.llm_policy import (
    AcceleratorLLMPolicy,
    LLMConfigurationError,
    get_accelerator_llm_policy,
)
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable, request_openrouter

from .catalogs import CaptureCatalog, get_capture_catalog, validate_answer_document
from .extraction_contract import (
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SCHEMA_VERSION,
    build_extraction_json_schema,
)
from .models import AcceleratorLLMQuota, CaptureAnalysis, CaptureSession
from .retention_policy import (
    CaptureRetentionConfigurationError,
    completed_capture_expiry,
)
from .services import get_owned_capture_session

logger = logging.getLogger(__name__)


EXTRACTION_SYSTEM_PROMPT = (
    "Du extrahierst ausschließlich vorhandene Nutzerangaben in das vorgegebene JSON-Schema. "
    "Erfinde keine Fakten, Gruppen, Referenzen, Zahlen oder Entscheidungen. "
    "Jeder Vorschlag muss eine zulässige Quellfrage und einen wörtlichen Quellausschnitt nennen. "
    "Scope-In und Scope-Out bleiben strikt getrennt. Fehlende oder mehrdeutige Angaben werden "
    "als offene Frage oder Widerspruch ausgegeben. Gib ausschließlich ein JSON-Objekt zurück."
)


class CaptureAnalysisError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class CaptureAnalysisQuotaExceeded(CaptureAnalysisError):
    pass


class CaptureAnalysisAlreadyRunning(CaptureAnalysisError):
    pass


@dataclass(frozen=True)
class PreparedCaptureAnalysis:
    analysis: CaptureAnalysis
    catalog: CaptureCatalog
    answers: dict[str, str]
    messages: list[dict[str, str]]
    policy: AcceleratorLLMPolicy


@dataclass(frozen=True)
class CaptureProviderPayload:
    result: OpenRouterResult
    payload: dict[str, Any]


def log_capture_analysis(analysis: CaptureAnalysis) -> None:
    logger.info(
        "llm_request purpose=capture_extraction provider=%s model=%s "
        "object_type=capture_session object_id=%s analysis_id=%s status=%s "
        "error_code=%s duration_ms=%s input_chars=%s output_chars=%s "
        "prompt_tokens=%s completion_tokens=%s total_tokens=%s cost=%s",
        analysis.provider,
        analysis.model_name or "provider-default",
        analysis.session_id,
        analysis.pk,
        analysis.status,
        analysis.error_code or "none",
        analysis.duration_ms if analysis.duration_ms is not None else "",
        analysis.input_chars,
        analysis.output_chars,
        analysis.prompt_tokens if analysis.prompt_tokens is not None else "",
        analysis.completion_tokens if analysis.completion_tokens is not None else "",
        analysis.total_tokens if analysis.total_tokens is not None else "",
        analysis.cost if analysis.cost is not None else "",
    )


def canonical_answer_hash(answers: dict[str, str]) -> str:
    serialized = json.dumps(
        answers,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _extraction_input(
    *,
    session: CaptureSession,
    catalog: CaptureCatalog,
    answers: dict[str, str],
) -> dict[str, Any]:
    questions = []
    for question in catalog.questions:
        answer = answers.get(question.key, "").strip()
        if not answer:
            continue
        questions.append(
            {
                "id": question.key,
                "label": question.label,
                "answer": answer,
                "allowed_targets": list(question.target_paths),
            }
        )
    return {
        "capture_type": session.capture_type,
        "catalog_version": session.catalog_version,
        "answer_schema_version": session.schema_version,
        "extraction_schema_version": EXTRACTION_SCHEMA_VERSION,
        "prompt_version": EXTRACTION_PROMPT_VERSION,
        "questions": questions,
    }


def _quota_subject(
    scope: str,
    *,
    actor,
    session: CaptureSession,
) -> dict[str, object]:
    if scope == AcceleratorLLMQuota.Scope.CONTEXT:
        return {"session": session}
    if scope == AcceleratorLLMQuota.Scope.USER:
        return {"user": actor}
    return {}


def _increment_quota(
    *,
    scope: str,
    actor,
    session: CaptureSession,
    quota_date,
    limit: int,
) -> None:
    subject = _quota_subject(scope, actor=actor, session=session)
    quota, _created = AcceleratorLLMQuota.objects.get_or_create(
        scope=scope,
        quota_date=quota_date,
        defaults={"calls": 0, **subject},
        **subject,
    )
    updated = AcceleratorLLMQuota.objects.filter(pk=quota.pk, calls__lt=limit).update(
        calls=F("calls") + 1
    )
    if not updated:
        labels = {
            AcceleratorLLMQuota.Scope.CONTEXT: "Diese Erfassung",
            AcceleratorLLMQuota.Scope.USER: "Ihr Benutzerkonto",
            AcceleratorLLMQuota.Scope.GLOBAL: "Der Accelerator",
        }
        raise CaptureAnalysisQuotaExceeded(
            f"{labels[scope]} hat das tägliche Analyselimit erreicht.",
            code=f"{scope}_quota_exceeded",
        )


def _reserve_quotas(
    *, actor, session: CaptureSession, policy: AcceleratorLLMPolicy, quota_date
) -> None:
    for scope, limit in (
        (AcceleratorLLMQuota.Scope.CONTEXT, policy.max_calls_per_context),
        (AcceleratorLLMQuota.Scope.USER, policy.max_calls_per_user_day),
        (AcceleratorLLMQuota.Scope.GLOBAL, policy.max_calls_global_day),
    ):
        _increment_quota(
            scope=scope,
            actor=actor,
            session=session,
            quota_date=quota_date,
            limit=limit,
        )


def _duration_ms(analysis: CaptureAnalysis, finished_at) -> int:
    return max(0, round((finished_at - analysis.started_at).total_seconds() * 1000))


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


@sensitive_variables("answers", "input_document", "user_content", "messages")
@transaction.atomic
def prepare_capture_analysis(*, actor, session_id) -> PreparedCaptureAnalysis:
    owned = get_owned_capture_session(actor=actor, session_id=session_id)
    session = CaptureSession.objects.select_for_update().get(pk=owned.pk, owner=actor)
    if session.status != CaptureSession.Status.COMPLETED:
        raise CaptureAnalysisError(
            "Nur abgeschlossene Erfassungen können analysiert werden.",
            code="invalid_capture_state",
        )

    catalog = get_capture_catalog(session.capture_type, session.catalog_version)
    if session.schema_version != catalog.schema_version:
        raise CaptureAnalysisError(
            "Die gespeicherte Antwortschema-Version passt nicht zum eingefrorenen Fragenkatalog.",
            code="unsupported_capture_schema",
        )
    answers = validate_answer_document(catalog, session.answers, require_complete=True)
    source_hash = canonical_answer_hash(answers)
    try:
        policy = get_accelerator_llm_policy()
        completed_expiry = completed_capture_expiry()
    except (LLMConfigurationError, CaptureRetentionConfigurationError) as exc:
        raise CaptureAnalysisError(
            f"Die LLM-Konfiguration ist ungültig: {exc}",
            code="invalid_configuration",
        ) from exc

    input_document = _extraction_input(session=session, catalog=catalog, answers=answers)
    user_content = json.dumps(input_document, ensure_ascii=False, separators=(",", ":"))
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    input_chars = len(EXTRACTION_SYSTEM_PROMPT) + len(user_content)
    if input_chars > policy.max_input_chars:
        raise CaptureAnalysisError(
            "Die für die Analyse vorgesehenen Antworten überschreiten das Größenlimit.",
            code="input_too_large",
        )

    _reserve_quotas(
        actor=actor,
        session=session,
        policy=policy,
        quota_date=timezone.localdate(),
    )
    try:
        analysis = CaptureAnalysis.objects.create(
            session=session,
            requested_by=actor,
            source_revision=session.revision,
            source_hash=source_hash,
            capture_type=session.capture_type,
            catalog_version=session.catalog_version,
            answer_schema_version=session.schema_version,
            prompt_version=EXTRACTION_PROMPT_VERSION,
            extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
            input_chars=input_chars,
        )
    except IntegrityError as exc:
        raise CaptureAnalysisAlreadyRunning(
            "Für diesen unveränderten Antwortstand läuft bereits eine Analyse.",
            code="analysis_already_running",
        ) from exc

    session.expires_at = completed_expiry
    session.save(update_fields=["expires_at", "updated_at"])
    return PreparedCaptureAnalysis(
        analysis=analysis,
        catalog=catalog,
        answers=answers,
        messages=messages,
        policy=policy,
    )


@transaction.atomic
def mark_capture_analysis_failed(
    *, analysis_id, error_code: str, result: OpenRouterResult | None = None
) -> CaptureAnalysis:
    analysis = CaptureAnalysis.objects.select_for_update().get(pk=analysis_id)
    if analysis.status != CaptureAnalysis.Status.RUNNING:
        return analysis
    finished_at = timezone.now()
    analysis.status = CaptureAnalysis.Status.FAILED
    analysis.finished_at = finished_at
    analysis.duration_ms = _duration_ms(analysis, finished_at)
    analysis.error_code = error_code
    if result is not None:
        analysis.model_name = result.model
        analysis.output_chars = result.output_chars
        analysis.prompt_tokens = _usage_int(result.usage.get("prompt_tokens"))
        analysis.completion_tokens = _usage_int(result.usage.get("completion_tokens"))
        analysis.total_tokens = _usage_int(result.usage.get("total_tokens"))
        analysis.cost = _cost(result.usage.get("cost"))
    analysis.save(
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
    log_capture_analysis(analysis)
    return analysis


@sensitive_variables("prepared", "result", "payload", "response_schema")
def request_capture_provider(prepared: PreparedCaptureAnalysis) -> CaptureProviderPayload:
    response_schema = build_extraction_json_schema(prepared.catalog)
    try:
        result = request_openrouter(
            messages=prepared.messages,
            max_tokens=prepared.policy.capture_max_output_tokens,
            timeout_seconds=prepared.policy.timeout_seconds,
            temperature=prepared.policy.capture_temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "accelerator_capture_extraction_v1",
                    "strict": True,
                    "schema": response_schema,
                },
            },
            provider={"require_parameters": True},
        )
    except OpenRouterUnavailable as exc:
        mark_capture_analysis_failed(analysis_id=prepared.analysis.pk, error_code=exc.code)
        raise CaptureAnalysisError(str(exc), code=exc.code) from exc

    if result.finish_reason == "length":
        mark_capture_analysis_failed(
            analysis_id=prepared.analysis.pk,
            error_code="output_truncated",
            result=result,
        )
        raise CaptureAnalysisError(
            "Die Providerantwort wurde am konfigurierten Ausgabelimit abgeschnitten.",
            code="output_truncated",
        )

    try:
        payload = json.loads(result.content)
    except json.JSONDecodeError as exc:
        mark_capture_analysis_failed(
            analysis_id=prepared.analysis.pk,
            error_code="invalid_response",
            result=result,
        )
        raise CaptureAnalysisError(
            "OpenRouter hat kein gültiges JSON-Objekt zurückgegeben.",
            code="invalid_response",
        ) from exc
    if not isinstance(payload, dict):
        mark_capture_analysis_failed(
            analysis_id=prepared.analysis.pk,
            error_code="invalid_response",
            result=result,
        )
        raise CaptureAnalysisError(
            "OpenRouter hat kein JSON-Objekt zurückgegeben.",
            code="invalid_response",
        )
    return CaptureProviderPayload(result=result, payload=payload)
