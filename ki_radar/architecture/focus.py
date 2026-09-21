from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from ki_radar.core.models import TimeStampedModel
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


class ValueStreamFocus(TimeStampedModel):
    class Status(models.TextChoices):
        NOT_SCREENED = "not_screened", "Noch nicht bewertet"
        CANDIDATE = "candidate", "Kandidat für Vertiefung"
        SELECTED = "selected", "Für Prozessanalyse ausgewählt"
        DEFERRED = "deferred", "Zurückgestellt"
        NOT_SELECTED = "not_selected", "Nicht ausgewählt"

    value_stream = models.OneToOneField(
        "architecture.ValueStream",
        on_delete=models.CASCADE,
        related_name="focus",
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
    strategic_impact = models.CharField(
        max_length=10,
        choices=ScreeningLevel.choices,
        blank=True,
        verbose_name="Strategischer Impact",
    )
    economic_potential = models.CharField(
        max_length=10,
        choices=ScreeningLevel.choices,
        blank=True,
        verbose_name="Wirtschaftliches Potenzial",
    )
    pain_intensity = models.CharField(
        max_length=10,
        choices=ScreeningLevel.choices,
        blank=True,
        verbose_name="Problem- und Schmerzintensität",
    )
    data_accessibility = models.CharField(
        max_length=10,
        choices=ScreeningLevel.choices,
        blank=True,
        verbose_name="Datenzugänglichkeit",
    )
    change_effort = models.CharField(
        max_length=10,
        choices=ScreeningLevel.choices,
        blank=True,
        verbose_name="Veränderungsaufwand",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_SCREENED,
        db_index=True,
        verbose_name="Fokusentscheidung",
    )
    rationale = models.TextField(blank=True, verbose_name="Begründung der Fokusentscheidung")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_value_stream_focuses",
    )

    class Meta:
        ordering = ["value_stream__business_unit__name", "value_stream__name"]

    def __str__(self) -> str:
        return f"{self.value_stream}: {self.get_status_display()}"

    @property
    def missing_screening_fields(self) -> tuple[str, ...]:
        required = {
            "capability": "Business Capability",
            "strategic_impact": "Strategischer Impact",
            "economic_potential": "Wirtschaftliches Potenzial",
            "pain_intensity": "Problem- und Schmerzintensität",
            "data_accessibility": "Datenzugänglichkeit",
            "change_effort": "Veränderungsaufwand",
            "rationale": "Begründung der Fokusentscheidung",
        }
        return tuple(
            label for name, label in required.items() if not str(getattr(self, name, "")).strip()
        )

    @property
    def is_selected(self) -> bool:
        return self.status == self.Status.SELECTED and not self.missing_screening_fields

    @property
    def is_terminal(self) -> bool:
        return self.status in {self.Status.DEFERRED, self.Status.NOT_SELECTED}


def get_value_stream_focus(value_stream) -> ValueStreamFocus | None:
    try:
        return value_stream.focus
    except ObjectDoesNotExist:
        return None


DEMO_FOCUS_DEFAULTS = {
    "invoice-check-golden-path": {
        "business_domain": BusinessDomain.FINANCE,
        "capability": "Accounts Payable und Rechnungsprüfung",
        "strategic_impact": ScreeningLevel.HIGH,
        "economic_potential": ScreeningLevel.HIGH,
        "pain_intensity": ScreeningLevel.HIGH,
        "data_accessibility": ScreeningLevel.MEDIUM,
        "change_effort": ScreeningLevel.MEDIUM,
        "status": ValueStreamFocus.Status.SELECTED,
        "rationale": (
            "Hoher manueller Aufwand, messbare Baseline und klar abgegrenzte Prozessanalyse."
        ),
    },
    "supplier-selection-incomplete": {
        "business_domain": BusinessDomain.PROCUREMENT,
        "capability": "Supplier Sourcing und Angebotsvergleich",
        "strategic_impact": ScreeningLevel.HIGH,
        "economic_potential": ScreeningLevel.MEDIUM,
        "pain_intensity": ScreeningLevel.HIGH,
        "data_accessibility": ScreeningLevel.MEDIUM,
        "change_effort": ScreeningLevel.MEDIUM,
        "status": ValueStreamFocus.Status.SELECTED,
        "rationale": (
            "Der Angebotsvergleich wurde wegen hoher Reibung für die Prozessanalyse ausgewählt."
        ),
    },
    "order-approval-non-ai": {
        "business_domain": BusinessDomain.PROCUREMENT,
        "capability": "Purchase Approval",
        "strategic_impact": ScreeningLevel.MEDIUM,
        "economic_potential": ScreeningLevel.MEDIUM,
        "pain_intensity": ScreeningLevel.HIGH,
        "data_accessibility": ScreeningLevel.HIGH,
        "change_effort": ScreeningLevel.LOW,
        "status": ValueStreamFocus.Status.SELECTED,
        "rationale": "Häufige Standardfälle und eindeutige Regeln rechtfertigen die Vertiefung.",
    },
}


@receiver(post_save, sender="architecture.ValueStream")
def persist_focus_payload(sender, instance, **kwargs):
    payload = getattr(instance, "_focus_payload", None)
    if payload is None and instance.demo_key:
        payload = DEMO_FOCUS_DEFAULTS.get(instance.demo_key)
    if payload is None:
        return
    ValueStreamFocus.objects.update_or_create(
        value_stream=instance,
        defaults=payload,
    )
