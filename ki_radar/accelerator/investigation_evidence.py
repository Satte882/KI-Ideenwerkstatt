from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from ki_radar.architecture.models import ProcessAnalysis
from ki_radar.architecture.permissions import can_edit_value_stream

from .investigation_models import (
    InvestigationEvidenceBudgetRevision,
    InvestigationEvidenceCampaign,
    InvestigationProviderReservation,
    InvestigationRun,
)
from .investigation_runtime import InvestigationRunError, normalize_idempotency_key

REQUIRED_CAMPAIGN_LIMITS = (
    "max_provider_calls",
    "max_input_tokens",
    "max_output_tokens",
)
OPTIONAL_CAMPAIGN_LIMITS = ("max_cost_microunits",)
USAGE_KEYS = (
    "provider_calls",
    "input_tokens",
    "output_tokens",
    "reserved_input_tokens",
    "reserved_output_tokens",
    "cost_microunits",
    "reserved_cost_microunits",
    "uncertain_attempts",
)


def initial_campaign_usage() -> dict[str, int]:
    return {key: 0 for key in USAGE_KEYS}


def _normalize_limits(raw: Mapping[str, Any]) -> dict[str, int]:
    supplied = dict(raw or {})
    unknown = set(supplied) - set(REQUIRED_CAMPAIGN_LIMITS) - set(OPTIONAL_CAMPAIGN_LIMITS)
    if unknown:
        raise InvestigationRunError(
            "Unbekannte Gesamtbudget-Grenzen: " + ", ".join(sorted(unknown)),
            code="invalid_evidence_budget",
        )
    normalized: dict[str, int] = {}
    for key in REQUIRED_CAMPAIGN_LIMITS:
        value = supplied.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise InvestigationRunError(
                "Provideraufrufe sowie Input-/Outputtoken benötigen positive Gesamtgrenzen.",
                code="invalid_evidence_budget",
            )
        normalized[key] = value
    if "max_cost_microunits" in supplied:
        value = supplied["max_cost_microunits"]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise InvestigationRunError(
                "Eine Kostengrenze muss positiv sein.",
                code="invalid_evidence_budget",
            )
        normalized["max_cost_microunits"] = value
    return normalized


def _normalize_pricing(
    raw: Mapping[str, Any] | None,
    *,
    currency: str,
    pricing_version: str,
    cost_cap_configured: bool,
) -> dict[str, str]:
    pricing = dict(raw or {})
    if not cost_cap_configured:
        return {
            str(key): str(value)
            for key, value in pricing.items()
            if value is not None and str(value).strip()
        }
    if not currency.strip() or not pricing_version.strip():
        raise InvestigationRunError(
            "Eine Kostengrenze benötigt Währung und versionierte Preisbasis.",
            code="invalid_evidence_budget",
        )
    required = ("input_per_million", "output_per_million")
    normalized: dict[str, str] = {}
    for key in required:
        try:
            value = Decimal(str(pricing.get(key)))
        except (InvalidOperation, TypeError, ValueError):
            value = Decimal("-1")
        if value < 0:
            raise InvestigationRunError(
                "Die Preisbasis für Input und Output muss vollständig und nichtnegativ sein.",
                code="invalid_evidence_budget",
            )
        normalized[key] = str(value)
    return normalized


def _assert_actor_can_manage_campaign(actor, process: ProcessAnalysis) -> None:
    if actor is None or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Das Nachweisbudget ist nicht zugänglich.")
    if process.status != ProcessAnalysis.Status.DRAFT:
        raise PermissionDenied("Die ProcessAnalysis ist nicht mehr bearbeitbar.")
    if not can_edit_value_stream(actor, process.stage.value_stream):
        raise PermissionDenied("Das Nachweisbudget ist nicht zugänglich.")


def _create_revision(
    *,
    campaign: InvestigationEvidenceCampaign,
    actor,
    reason: str,
) -> InvestigationEvidenceBudgetRevision:
    return InvestigationEvidenceBudgetRevision.objects.create(
        campaign=campaign,
        revision=campaign.revision,
        limits=campaign.limits,
        pricing=campaign.pricing,
        currency=campaign.currency,
        pricing_version=campaign.pricing_version,
        usage_at_authorization=campaign.usage,
        reason=reason,
        authorized_by=actor,
    )


@transaction.atomic
def create_evidence_campaign(
    *,
    actor,
    process_analysis_id,
    campaign_key: str,
    limits: Mapping[str, Any],
    pricing: Mapping[str, Any] | None = None,
    currency: str = "",
    pricing_version: str = "",
) -> InvestigationEvidenceCampaign:
    process = (
        ProcessAnalysis.objects.select_for_update()
        .select_related("stage__value_stream")
        .get(pk=process_analysis_id)
    )
    _assert_actor_can_manage_campaign(actor, process)
    key = normalize_idempotency_key(campaign_key)
    normalized_limits = _normalize_limits(limits)
    normalized_pricing = _normalize_pricing(
        pricing,
        currency=currency,
        pricing_version=pricing_version,
        cost_cap_configured="max_cost_microunits" in normalized_limits,
    )
    campaign = InvestigationEvidenceCampaign.objects.create(
        process_analysis=process,
        campaign_key=key,
        revision=1,
        limits=normalized_limits,
        usage=initial_campaign_usage(),
        pricing=normalized_pricing,
        currency=currency.strip(),
        pricing_version=pricing_version.strip(),
        authorized_by=actor,
    )
    _create_revision(
        campaign=campaign,
        actor=actor,
        reason="Initiale Autorisierung des VS1/3-Gesamtnachweisbudgets.",
    )
    return campaign


def _minimum_limits_for_usage(usage: Mapping[str, int]) -> dict[str, int]:
    return {
        "max_provider_calls": int(usage.get("provider_calls", 0)),
        "max_input_tokens": int(usage.get("input_tokens", 0))
        + int(usage.get("reserved_input_tokens", 0)),
        "max_output_tokens": int(usage.get("output_tokens", 0))
        + int(usage.get("reserved_output_tokens", 0)),
        "max_cost_microunits": int(usage.get("cost_microunits", 0))
        + int(usage.get("reserved_cost_microunits", 0)),
    }


@transaction.atomic
def authorize_campaign_continuation(
    *,
    actor,
    campaign_id,
    limits: Mapping[str, Any],
    reason: str,
    pricing: Mapping[str, Any] | None = None,
    currency: str = "",
    pricing_version: str = "",
) -> InvestigationEvidenceCampaign:
    campaign = (
        InvestigationEvidenceCampaign.objects.select_for_update()
        .select_related("process_analysis__stage__value_stream")
        .get(pk=campaign_id)
    )
    _assert_actor_can_manage_campaign(actor, campaign.process_analysis)
    if not reason.strip():
        raise InvestigationRunError(
            "Eine Budgetfortsetzung benötigt eine Begründung.",
            code="invalid_evidence_budget",
        )
    normalized_limits = _normalize_limits(limits)
    minimum = _minimum_limits_for_usage(campaign.usage)
    for key in REQUIRED_CAMPAIGN_LIMITS:
        if normalized_limits[key] < minimum[key]:
            raise InvestigationRunError(
                "Bereits verbrauchtes oder reserviertes Budget darf nicht zurückgesetzt werden.",
                code="invalid_evidence_budget",
            )
    if "max_cost_microunits" in normalized_limits:
        if normalized_limits["max_cost_microunits"] < minimum["max_cost_microunits"]:
            raise InvestigationRunError(
                "Bereits verbrauchte oder reservierte Kosten dürfen nicht zurückgesetzt werden.",
                code="invalid_evidence_budget",
            )
    elif minimum["max_cost_microunits"] > 0:
        raise InvestigationRunError(
            "Eine aktive Kostengrenze darf bei der Fortsetzung nicht still entfernt werden.",
            code="invalid_evidence_budget",
        )
    normalized_pricing = _normalize_pricing(
        pricing if pricing is not None else campaign.pricing,
        currency=currency or campaign.currency,
        pricing_version=pricing_version or campaign.pricing_version,
        cost_cap_configured="max_cost_microunits" in normalized_limits,
    )
    campaign.revision += 1
    campaign.limits = normalized_limits
    campaign.pricing = normalized_pricing
    campaign.currency = (currency or campaign.currency).strip()
    campaign.pricing_version = (pricing_version or campaign.pricing_version).strip()
    campaign.authorized_by = actor
    campaign.authorized_at = timezone.now()
    campaign.continuation_reason = reason.strip()
    campaign.save(
        update_fields=[
            "revision",
            "limits",
            "pricing",
            "currency",
            "pricing_version",
            "authorized_by",
            "authorized_at",
            "continuation_reason",
            "updated_at",
        ]
    )
    _create_revision(campaign=campaign, actor=actor, reason=reason.strip())
    return campaign


def _max_cost_for_tokens(
    campaign: InvestigationEvidenceCampaign,
    *,
    input_tokens: int,
    output_tokens: int,
) -> int | None:
    if "max_cost_microunits" not in campaign.limits:
        return None
    try:
        input_rate = Decimal(str(campaign.pricing["input_per_million"]))
        output_rate = Decimal(str(campaign.pricing["output_per_million"]))
    except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
        raise InvestigationRunError(
            "Die versionierte Preisbasis ist nicht verfügbar.",
            code="invalid_evidence_budget",
        ) from exc
    currency_units = Decimal(input_tokens) * input_rate / Decimal(1_000_000) + Decimal(
        output_tokens
    ) * output_rate / Decimal(1_000_000)
    return int((currency_units * Decimal(1_000_000)).to_integral_value(rounding="ROUND_CEILING"))


def _would_exceed(
    campaign: InvestigationEvidenceCampaign,
    *,
    input_tokens: int,
    output_tokens: int,
    reserved_cost_microunits: int | None,
) -> bool:
    usage = campaign.usage
    limits = campaign.limits
    if int(usage.get("provider_calls", 0)) + 1 > limits["max_provider_calls"]:
        return True
    if (
        int(usage.get("input_tokens", 0))
        + int(usage.get("reserved_input_tokens", 0))
        + input_tokens
        > limits["max_input_tokens"]
    ):
        return True
    if (
        int(usage.get("output_tokens", 0))
        + int(usage.get("reserved_output_tokens", 0))
        + output_tokens
        > limits["max_output_tokens"]
    ):
        return True
    if "max_cost_microunits" in limits:
        if reserved_cost_microunits is None:
            return True
        if (
            int(usage.get("cost_microunits", 0))
            + int(usage.get("reserved_cost_microunits", 0))
            + reserved_cost_microunits
            > limits["max_cost_microunits"]
        ):
            return True
    return False


@transaction.atomic
def reserve_provider_attempt(
    *,
    run_id,
    model_call_id,
    max_input_tokens: int,
    max_output_tokens: int,
) -> InvestigationProviderReservation | None:
    run = InvestigationRun.objects.select_for_update().get(pk=run_id)
    if run.evidence_campaign_id is None:
        return None
    if max_input_tokens <= 0 or max_output_tokens <= 0:
        raise InvestigationRunError(
            "Vor einem realen Provideraufruf müssen positive Tokenreservierungen bestehen.",
            code="evidence_budget_exhausted",
        )
    campaign = InvestigationEvidenceCampaign.objects.select_for_update().get(
        pk=run.evidence_campaign_id
    )
    if campaign.process_analysis_id != run.process_analysis_id:
        raise InvestigationRunError(
            "Das Nachweisbudget gehört nicht zu diesem Fall.",
            code="invalid_evidence_budget",
        )
    existing = InvestigationProviderReservation.objects.filter(model_call_id=model_call_id).first()
    if existing is not None:
        return existing
    reserved_cost = _max_cost_for_tokens(
        campaign,
        input_tokens=max_input_tokens,
        output_tokens=max_output_tokens,
    )
    if _would_exceed(
        campaign,
        input_tokens=max_input_tokens,
        output_tokens=max_output_tokens,
        reserved_cost_microunits=reserved_cost,
    ):
        raise InvestigationRunError(
            "Das persistente Gesamtbudget reicht für keinen weiteren Provideraufruf.",
            code="evidence_budget_exhausted",
        )
    usage = dict(campaign.usage)
    usage["provider_calls"] = int(usage.get("provider_calls", 0)) + 1
    usage["reserved_input_tokens"] = int(usage.get("reserved_input_tokens", 0)) + max_input_tokens
    usage["reserved_output_tokens"] = (
        int(usage.get("reserved_output_tokens", 0)) + max_output_tokens
    )
    if reserved_cost is not None:
        usage["reserved_cost_microunits"] = (
            int(usage.get("reserved_cost_microunits", 0)) + reserved_cost
        )
    campaign.usage = usage
    campaign.save(update_fields=["usage", "updated_at"])
    return InvestigationProviderReservation.objects.create(
        campaign=campaign,
        run=run,
        model_call_id=model_call_id,
        reserved_input_tokens=max_input_tokens,
        reserved_output_tokens=max_output_tokens,
        reserved_cost_microunits=reserved_cost,
    )


@transaction.atomic
def settle_provider_attempt(
    *,
    reservation_id,
    actual_input_tokens: int,
    actual_output_tokens: int,
    actual_cost_microunits: int | None,
) -> InvestigationProviderReservation:
    reservation = (
        InvestigationProviderReservation.objects.select_for_update()
        .select_related("campaign")
        .get(pk=reservation_id)
    )
    if reservation.status != InvestigationProviderReservation.Status.OPEN:
        return reservation
    campaign = InvestigationEvidenceCampaign.objects.select_for_update().get(
        pk=reservation.campaign_id
    )
    if actual_input_tokens < 0 or actual_output_tokens < 0:
        raise InvestigationRunError(
            "Providerverbrauch ist ungültig.",
            code="invalid_provider_usage",
        )
    usage = dict(campaign.usage)
    usage["reserved_input_tokens"] = max(
        0,
        int(usage.get("reserved_input_tokens", 0)) - reservation.reserved_input_tokens,
    )
    usage["reserved_output_tokens"] = max(
        0,
        int(usage.get("reserved_output_tokens", 0)) - reservation.reserved_output_tokens,
    )
    if reservation.reserved_cost_microunits is not None:
        usage["reserved_cost_microunits"] = max(
            0,
            int(usage.get("reserved_cost_microunits", 0)) - reservation.reserved_cost_microunits,
        )

    limits = campaign.limits
    if int(usage.get("input_tokens", 0)) + actual_input_tokens > limits["max_input_tokens"]:
        raise InvestigationRunError(
            "Der gemeldete Inputverbrauch überschreitet das Gesamtbudget.",
            code="provider_usage_exceeds_reservation",
        )
    if int(usage.get("output_tokens", 0)) + actual_output_tokens > limits["max_output_tokens"]:
        raise InvestigationRunError(
            "Der gemeldete Outputverbrauch überschreitet das Gesamtbudget.",
            code="provider_usage_exceeds_reservation",
        )
    usage["input_tokens"] = int(usage.get("input_tokens", 0)) + actual_input_tokens
    usage["output_tokens"] = int(usage.get("output_tokens", 0)) + actual_output_tokens

    if "max_cost_microunits" in limits:
        if actual_cost_microunits is None:
            raise InvestigationRunError(
                "Bei aktiver Kostengrenze fehlen belastbare Kostenmetadaten.",
                code="provider_cost_unknown",
            )
        if (
            int(usage.get("cost_microunits", 0)) + actual_cost_microunits
            > limits["max_cost_microunits"]
        ):
            raise InvestigationRunError(
                "Der gemeldete Kostenverbrauch überschreitet das Gesamtbudget.",
                code="provider_usage_exceeds_reservation",
            )
        usage["cost_microunits"] = int(usage.get("cost_microunits", 0)) + actual_cost_microunits
    elif actual_cost_microunits is not None:
        usage["cost_microunits"] = int(usage.get("cost_microunits", 0)) + actual_cost_microunits

    campaign.usage = usage
    campaign.save(update_fields=["usage", "updated_at"])
    reservation.status = InvestigationProviderReservation.Status.SETTLED
    reservation.actual_input_tokens = actual_input_tokens
    reservation.actual_output_tokens = actual_output_tokens
    reservation.actual_cost_microunits = actual_cost_microunits
    reservation.settled_at = timezone.now()
    reservation.save(
        update_fields=[
            "status",
            "actual_input_tokens",
            "actual_output_tokens",
            "actual_cost_microunits",
            "settled_at",
            "updated_at",
        ]
    )
    return reservation


@transaction.atomic
def mark_provider_attempt_uncertain(*, reservation_id, reason: str) -> None:
    reservation = (
        InvestigationProviderReservation.objects.select_for_update()
        .select_related("campaign")
        .get(pk=reservation_id)
    )
    if reservation.status != InvestigationProviderReservation.Status.OPEN:
        return
    campaign = InvestigationEvidenceCampaign.objects.select_for_update().get(
        pk=reservation.campaign_id
    )
    usage = dict(campaign.usage)
    usage["uncertain_attempts"] = int(usage.get("uncertain_attempts", 0)) + 1
    campaign.usage = usage
    campaign.save(update_fields=["usage", "updated_at"])
    reservation.status = InvestigationProviderReservation.Status.UNCERTAIN
    reservation.uncertainty_reason = str(reason or "unknown_usage")[:80]
    reservation.save(update_fields=["status", "uncertainty_reason", "updated_at"])


def cost_to_microunits(raw_cost: object) -> int | None:
    if raw_cost is None:
        return None
    try:
        value = Decimal(str(raw_cost))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if value < 0:
        return None
    return int((value * Decimal(1_000_000)).to_integral_value(rounding="ROUND_CEILING"))


def campaign_budget_snapshot(campaign: InvestigationEvidenceCampaign) -> dict[str, Any]:
    minimum = _minimum_limits_for_usage(campaign.usage)
    return {
        "campaign_id": str(campaign.pk),
        "campaign_key": campaign.campaign_key,
        "revision": campaign.revision,
        "limits": dict(campaign.limits),
        "usage": dict(campaign.usage),
        "minimum_committed": minimum,
        "pricing": dict(campaign.pricing),
        "currency": campaign.currency,
        "pricing_version": campaign.pricing_version,
        "cost_cap_configured": "max_cost_microunits" in campaign.limits,
    }
