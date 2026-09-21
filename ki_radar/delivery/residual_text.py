from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from ki_radar.accelerator.solution_generation_service import (
    SolutionGenerationQuotaExceeded,
    _reserve_solution_generation_quotas,
)
from ki_radar.core.llm_policy import LLMConfigurationError, get_accelerator_llm_policy
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable, request_openrouter

from .evidence_mapping_contract import LLMRestTask, mapping_spec
from .mapping_integration import (
    ARCHITECTURE_MAPPING_FIELDS,
    BLOCK8_MAPPING_MANIFEST_KEY,
    block8_mapping_source_differences,
    build_delivery_mapping_candidates,
    build_existing_package_refresh_plan,
    delivery_mapping_manifest,
)
from .mapping_refresh import MappingStatus
from .models import DeliveryPackage

logger = logging.getLogger(__name__)

RESIDUAL_PROMPT_VERSION = "block8-language-compaction-v1"
RESIDUAL_SCHEMA_VERSION = "1"
RESIDUAL_CACHE_KEY = "residual_texts"


class ResidualTextError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ResidualTextResult:
    target_field: str
    value: str
    evidence_hash: str
    cached: bool
    model: str
    usage: dict[str, object]


@sensitive_variables("messages", "provider_result")
def refine_delivery_residual_text(
    *,
    package: DeliveryPackage,
    target_field: str,
    actor,
) -> ResidualTextResult:
    """Language-compact one approved V1 field after an explicit user action."""

    started = time.monotonic()
    prepared = _prepare_residual_request(package=package, target_field=target_field)
    cached = _cached_result(prepared, target_field)
    if cached is not None:
        _log_request(
            package=package,
            target_field=target_field,
            status="cache_hit",
            error_code="",
            duration_ms=_elapsed_ms(started),
            input_chars=0,
            result=None,
        )
        return cached

    try:
        policy = get_accelerator_llm_policy()
    except LLMConfigurationError as exc:
        raise ResidualTextError(
            f"Die Accelerator-Konfiguration ist ungültig: {exc}",
            code="invalid_configuration",
        ) from exc

    messages = _build_messages(target_field, str(prepared["candidate_value"]))
    input_chars = sum(len(message["content"]) for message in messages)
    if input_chars > policy.max_input_chars:
        raise ResidualTextError(
            "Die bestätigte Evidence überschreitet das zulässige Eingabelimit.",
            code="input_too_large",
        )

    process_analysis = _process_analysis(package)
    if process_analysis is None:
        raise ResidualTextError(
            "Für den LLM-Resttext fehlt der bestehende Prozessanalyse-Kontext für die Quote.",
            code="context_unavailable",
        )
    try:
        _reserve_quotas(actor=actor, process_analysis=process_analysis, policy=policy)
    except SolutionGenerationQuotaExceeded as exc:
        raise ResidualTextError(str(exc), code=exc.code) from exc

    try:
        provider_result = request_openrouter(
            messages=messages,
            max_tokens=policy.max_output_tokens,
            timeout_seconds=policy.timeout_seconds,
            temperature=0.0,
        )
    except OpenRouterUnavailable as exc:
        _log_request(
            package=package,
            target_field=target_field,
            status="failed",
            error_code=exc.code,
            duration_ms=_elapsed_ms(started),
            input_chars=input_chars,
            result=None,
        )
        raise ResidualTextError(str(exc), code=exc.code) from exc

    if provider_result.finish_reason == "length":
        _log_request(
            package=package,
            target_field=target_field,
            status="failed",
            error_code="output_truncated",
            duration_ms=_elapsed_ms(started),
            input_chars=input_chars,
            result=provider_result,
        )
        raise ResidualTextError(
            "Die LLM-Antwort wurde wegen des Ausgabelimits abgeschnitten.",
            code="output_truncated",
        )
    output = provider_result.content.strip()
    if not output:
        raise ResidualTextError(
            "OpenRouter hat keinen verwendbaren Resttext geliefert.",
            code="invalid_response",
        )

    _apply_success(
        package=package,
        target_field=target_field,
        value=output,
        evidence_hash=str(prepared["evidence_hash"]),
        provider_result=provider_result,
    )
    _log_request(
        package=package,
        target_field=target_field,
        status="success",
        error_code="",
        duration_ms=_elapsed_ms(started),
        input_chars=input_chars,
        result=provider_result,
    )
    return ResidualTextResult(
        target_field=target_field,
        value=output,
        evidence_hash=str(prepared["evidence_hash"]),
        cached=False,
        model=provider_result.model,
        usage=dict(provider_result.usage),
    )


def _prepare_residual_request(package: DeliveryPackage, target_field: str) -> dict[str, object]:
    if package.status == DeliveryPackage.Status.HANDED_OVER:
        raise ResidualTextError(
            "Ein übergebenes Delivery Package ist unveränderlich.",
            code="package_handed_over",
        )
    try:
        spec = mapping_spec(target_field)
    except KeyError as exc:
        raise ResidualTextError(
            "Dieses Feld ist kein Block-8-V1-Zielfeld.",
            code="unsupported_field",
        ) from exc
    if spec.llm_rest_task is not LLMRestTask.LANGUAGE_COMPACTION:
        raise ResidualTextError(
            "Für dieses Feld ist kein LLM-Resttext freigegeben.",
            code="unsupported_field",
        )

    manifest = delivery_mapping_manifest(package)
    if manifest is None:
        raise ResidualTextError(
            "Das Bestands-Package besitzt noch keinen Block-8-Mappingnachweis.",
            code="legacy_package",
        )
    plan = build_existing_package_refresh_plan(package)
    decision = next((item for item in plan.decisions if item.target_field == target_field), None)
    if decision is None or decision.status is MappingStatus.GAP:
        raise ResidualTextError(
            "Für dieses Feld fehlt bestätigte Evidence; die Lücke bleibt offen.",
            code="evidence_gap",
        )
    if decision.status is MappingStatus.CONFLICT:
        raise ResidualTextError(
            "Der Mapping-Konflikt muss vor einer sprachlichen Verdichtung geklärt werden.",
            code="mapping_conflict",
        )

    source_change = next(
        (
            item
            for item in block8_mapping_source_differences(package)
            if item["package_field"] == target_field
        ),
        None,
    )
    if source_change and source_change["changed"]:
        raise ResidualTextError(
            "Die Quelle hat sich geändert; zuerst ist ein deterministischer Refresh erforderlich.",
            code="stale_source",
        )

    field_entry = dict((manifest.get("fields") or {}).get(target_field) or {})
    previous_mapped = str(field_entry.get("mapped_value") or "")
    current_value = _current_value(package, target_field)
    if current_value != previous_mapped:
        raise ResidualTextError(
            "Der Delivery-Wert wurde manuell verändert und wird nicht automatisch überschrieben.",
            code="manual_divergence",
        )

    candidate = next(
        (
            item
            for item in build_delivery_mapping_candidates(
                package.use_case,
                package.generated_from_decision,
            )
            if item.target_field == target_field
        ),
        None,
    )
    if candidate is None or candidate.is_gap:
        raise ResidualTextError(
            "Für dieses Feld fehlt bestätigte Evidence; die Lücke bleibt offen.",
            code="evidence_gap",
        )
    return {
        "manifest": manifest,
        "candidate_value": candidate.value,
        "evidence_hash": candidate.evidence_hash,
        "current_value": current_value,
    }


def _cached_result(prepared: dict[str, object], target_field: str) -> ResidualTextResult | None:
    manifest = prepared["manifest"]
    cache = dict(manifest.get(RESIDUAL_CACHE_KEY) or {}).get(target_field)
    if not isinstance(cache, dict):
        return None
    if (
        cache.get("evidence_hash") != prepared["evidence_hash"]
        or cache.get("prompt_version") != RESIDUAL_PROMPT_VERSION
        or cache.get("schema_version") != RESIDUAL_SCHEMA_VERSION
    ):
        return None
    output = str(cache.get("output") or "")
    if not output or output != prepared["current_value"]:
        return None
    return ResidualTextResult(
        target_field=target_field,
        value=output,
        evidence_hash=str(prepared["evidence_hash"]),
        cached=True,
        model=str(cache.get("model") or ""),
        usage=dict(cache.get("usage") or {}),
    )


def _build_messages(target_field: str, confirmed_text: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Du verdichtest ausschließlich bestätigten Text sprachlich. Füge keine neuen "
                "Fakten, Systeme, Schnittstellen, Anforderungen, Risiken, "
                "Architekturentscheidungen, Governance-Aussagen, Rollen, Freigaben oder "
                "Bestätigungen hinzu. Gib nur den überarbeiteten deutschen Text zurück."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Delivery-Feld: {target_field}\nBestätigter Ausgangstext:\n{confirmed_text}"
            ),
        },
    ]


def _process_analysis(package: DeliveryPackage):
    try:
        return package.use_case.architecture_origin.process_analysis
    except ObjectDoesNotExist:
        return None


@transaction.atomic
def _reserve_quotas(*, actor, process_analysis, policy) -> None:
    _reserve_solution_generation_quotas(
        actor=actor,
        process_analysis=process_analysis,
        policy=policy,
        quota_date=timezone.localdate(),
    )


@transaction.atomic
def _apply_success(
    *,
    package: DeliveryPackage,
    target_field: str,
    value: str,
    evidence_hash: str,
    provider_result: OpenRouterResult,
) -> None:
    current_value = _current_value(package, target_field)
    field_changed = current_value != value
    if field_changed and target_field in ARCHITECTURE_MAPPING_FIELDS:
        artifacts = package.architecture_artifacts
        setattr(artifacts, target_field, value)
        artifacts.save(update_fields=[target_field, "updated_at"])
    elif field_changed:
        setattr(package, target_field, value)
        package.save(update_fields=[target_field, "updated_at"])

    tracking_review = package.section_reviews.select_for_update().get(
        section_key="problem_and_target"
    )
    manifest = dict(tracking_review.source_manifest or {})
    mapping_manifest = dict(manifest.get(BLOCK8_MAPPING_MANIFEST_KEY) or {})
    fields = dict(mapping_manifest.get("fields") or {})
    field_entry = dict(fields.get(target_field) or {})
    field_entry["mapped_value"] = value
    fields[target_field] = field_entry
    residual_texts = dict(mapping_manifest.get(RESIDUAL_CACHE_KEY) or {})
    residual_texts[target_field] = {
        "evidence_hash": evidence_hash,
        "prompt_version": RESIDUAL_PROMPT_VERSION,
        "schema_version": RESIDUAL_SCHEMA_VERSION,
        "output": value,
        "model": provider_result.model,
        "usage": _usage_metadata(provider_result),
    }
    mapping_manifest["fields"] = fields
    mapping_manifest[RESIDUAL_CACHE_KEY] = residual_texts
    manifest[BLOCK8_MAPPING_MANIFEST_KEY] = mapping_manifest
    for review in package.section_reviews.select_for_update().all():
        if review.source_manifest != manifest:
            review.source_manifest = manifest
            review.save(update_fields=["source_manifest", "updated_at"])

    if field_changed:
        from .services import reset_section_reviews

        reset_section_reviews(package, {mapping_spec(target_field).section_key})


def _current_value(package: DeliveryPackage, target_field: str) -> str:
    if target_field in ARCHITECTURE_MAPPING_FIELDS:
        return str(getattr(package.architecture_artifacts, target_field) or "")
    return str(getattr(package, target_field) or "")


def _usage_metadata(result: OpenRouterResult) -> dict[str, object]:
    return {
        key: result.usage.get(key)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cost")
        if result.usage.get(key) is not None
    }


def _log_request(
    *,
    package: DeliveryPackage,
    target_field: str,
    status: str,
    error_code: str,
    duration_ms: int,
    input_chars: int,
    result: OpenRouterResult | None,
) -> None:
    usage = result.usage if result is not None else {}
    logger.info(
        "llm_request purpose=delivery_residual_text provider=openrouter model=%s "
        "object_type=delivery_package object_id=%s field=%s status=%s error_code=%s "
        "duration_ms=%s input_chars=%s output_chars=%s prompt_tokens=%s "
        "completion_tokens=%s total_tokens=%s cost=%s",
        result.model if result is not None else "provider-default",
        package.pk,
        target_field,
        status,
        error_code or "none",
        duration_ms,
        input_chars,
        result.output_chars if result is not None else "",
        usage.get("prompt_tokens", ""),
        usage.get("completion_tokens", ""),
        usage.get("total_tokens", ""),
        usage.get("cost", ""),
    )


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
