# ruff: noqa: I001
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import DeliveryPackage
from .readiness import evaluate_delivery_readiness


ENFORCEMENT_FINDING_CODES = {"SECTION_BLOCKED"}


def delivery_enforcement_findings(package: DeliveryPackage):
    """Return only findings that #403 classifies as true Delivery enforcement."""

    return [
        finding
        for finding in evaluate_delivery_readiness(package)
        if finding.code in ENFORCEMENT_FINDING_CODES
    ]


def delivery_readiness_findings(package: DeliveryPackage):
    """Keep the complete evaluator as decision support without making it a hard gate."""

    return evaluate_delivery_readiness(package)


@transaction.atomic
def mark_package_ready(package: DeliveryPackage) -> None:
    package = DeliveryPackage.objects.select_for_update().get(pk=package.pk)
    if package.status == DeliveryPackage.Status.HANDED_OVER:
        raise ValidationError("Ein übergebenes Delivery Package ist unveränderlich.")
    blockers = delivery_enforcement_findings(package)
    if blockers:
        raise ValidationError(
            "Das Delivery Package enthält einen ausdrücklich gesetzten fachlichen Blocker: "
            + " | ".join(finding.message for finding in blockers)
        )
    package.status = DeliveryPackage.Status.READY
    package.save(update_fields=["status", "updated_at"])


@transaction.atomic
def hand_over_package(package: DeliveryPackage, actor) -> None:
    package = (
        DeliveryPackage.objects.select_for_update(of=("self",))
        .select_related("technical_owner")
        .get(pk=package.pk)
    )
    if package.status != DeliveryPackage.Status.READY:
        raise ValidationError(
            "Nur ein als bereit markiertes Delivery Package kann übergeben werden."
        )
    if package.technical_owner_id is None or not package.technical_owner.is_active:
        raise ValidationError(
            "Vor der verbindlichen Übergabe muss ein aktiver Technical Owner benannt sein."
        )
    blockers = delivery_enforcement_findings(package)
    if blockers:
        raise ValidationError(
            "Die Übergabe ist fachlich blockiert: "
            + " | ".join(finding.message for finding in blockers)
        )
    package.status = DeliveryPackage.Status.HANDED_OVER
    package.handed_over_by = actor
    package.handed_over_at = timezone.now()
    package.save(update_fields=["status", "handed_over_by", "handed_over_at", "updated_at"])
