from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from ki_radar.core.models import TimeStampedModel
from ki_radar.core.taxonomy import BusinessDomain


class UseCaseClassification(TimeStampedModel):
    use_case = models.OneToOneField(
        "use_cases.UseCase",
        on_delete=models.CASCADE,
        related_name="classification",
    )
    business_domain = models.CharField(
        max_length=40,
        choices=BusinessDomain.choices,
        default=BusinessDomain.OTHER,
        db_index=True,
        verbose_name="Fachdomäne",
    )
    capability = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Business Capability",
    )
    process_area = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Prozessbereich",
    )

    class Meta:
        ordering = ["business_domain", "capability", "use_case__short_id"]

    def __str__(self) -> str:
        return f"{self.use_case.short_id}: {self.get_business_domain_display()}"


DEMO_CLASSIFICATION_DEFAULTS = {
    "invoice-check-golden-path": (
        BusinessDomain.FINANCE,
        "Accounts Payable und Rechnungsprüfung",
    ),
    "customer-service-conditional": (
        BusinessDomain.CUSTOMER_SERVICE,
        "Customer Service Management",
    ),
    "applicant-screening-stopped": (
        BusinessDomain.HUMAN_RESOURCES,
        "Talent Acquisition",
    ),
    "document-routing-handed-over": (
        BusinessDomain.CORPORATE_SERVICES,
        "Document Management",
    ),
    "direct-intake-incomplete": (
        BusinessDomain.CORPORATE_SERVICES,
        "Request Management",
    ),
}


@receiver(post_save, sender="use_cases.UseCase")
def persist_classification_payload(sender, instance, **kwargs):
    payload = getattr(instance, "_classification_payload", None)
    if payload is None and instance.demo_key in DEMO_CLASSIFICATION_DEFAULTS:
        domain, capability = DEMO_CLASSIFICATION_DEFAULTS[instance.demo_key]
        payload = {
            "business_domain": domain,
            "capability": capability,
            "process_area": instance.affected_process,
        }
    if payload is None and UseCaseClassification.objects.filter(use_case=instance).exists():
        return
    if payload is None:
        payload = {
            "business_domain": BusinessDomain.OTHER,
            "capability": "",
            "process_area": instance.affected_process,
        }
    UseCaseClassification.objects.update_or_create(
        use_case=instance,
        defaults=payload,
    )


@receiver(post_save, sender="architecture.UseCaseOrigin")
def inherit_classification_from_discovery(sender, instance, **kwargs):
    try:
        focus = instance.stage.value_stream.focus
    except (ObjectDoesNotExist, ValueError):
        return
    UseCaseClassification.objects.update_or_create(
        use_case=instance.use_case,
        defaults={
            "business_domain": focus.business_domain,
            "capability": focus.capability,
            "process_area": (
                instance.process_analysis.name
                if instance.process_analysis_id
                else instance.stage.name
            ),
        },
    )
