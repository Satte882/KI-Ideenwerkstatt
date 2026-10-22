"""The shared outcome identity; intake and legacy decisions remain independent."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from simple_history.models import HistoricalRecords

from ki_radar.core.models import TimeStampedModel


class ImprovementInitiative(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        ACTIVE = "active", "Aktiv"
        COMPLETED = "completed", "Abgeschlossen"
        CANCELLED = "cancelled", "Abgebrochen"

    class Evidence(models.TextChoices):
        HYPOTHESIS = "hypothesis", "Hypothese"
        INDICATIVE = "indicative", "Indiz"
        MEASURED = "measured", "Gemessen"

    class Effect(models.TextChoices):
        CONFIRMED = "confirmed", "Bestätigt"
        REFUTED = "refuted", "Widerlegt"
        UNCLEAR = "unclear", "Noch ungeklärt"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, verbose_name="Vorhaben")
    business_outcome = models.TextField(blank=True, verbose_name="Geschäftsergebnis")
    contribution = models.TextField(blank=True, verbose_name="Abgegrenzter Vorhabensbeitrag")
    impact_hypothesis = models.TextField(blank=True, verbose_name="Wirkannahme")
    evaluation_criteria = models.TextField(blank=True, verbose_name="Prüfkriterien")
    evidence_level = models.CharField(
        max_length=20,
        choices=Evidence.choices,
        default=Evidence.HYPOTHESIS,
        verbose_name="Evidenzstand",
    )
    evidence_note = models.TextField(blank=True, verbose_name="Evidenz / Quelle")
    outcome_owner = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Outcome Owner (Person oder Funktion)",
    )
    revision = models.PositiveIntegerField(default=1, editable=False)
    confirmed_revision = models.PositiveIntegerField(null=True, blank=True, editable=False)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_initiatives",
        editable=False,
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    next_review_date = models.DateField(null=True, blank=True, verbose_name="Nächster Review")
    effect_status = models.CharField(
        max_length=20,
        choices=Effect.choices,
        blank=True,
        verbose_name="Wirkungsaussage",
    )
    effect_reason = models.TextField(blank=True, verbose_name="Begründung der Wirkungsaussage")
    cancellation_reason = models.TextField(blank=True, verbose_name="Abbruchbegründung")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_initiatives",
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="updated_initiatives",
        editable=False,
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["title", "id"]
        verbose_name = "Verbesserungsvorhaben"
        verbose_name_plural = "Verbesserungsvorhaben"

    def clean(self):
        super().clean()
        if self.status == self.Status.CANCELLED and not self.cancellation_reason.strip():
            raise ValidationError({"cancellation_reason": "Bitte den Abbruch begründen."})
        if self.status == self.Status.COMPLETED:
            errors = {}
            if not self.effect_status:
                errors["effect_status"] = "Bitte eine ehrliche Wirkungsaussage dokumentieren."
            if not self.effect_reason.strip():
                errors["effect_reason"] = "Bitte die Wirkungsaussage begründen."
            if errors:
                raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def review_hint(self):
        if not self.next_review_date and self.status in {self.Status.DRAFT, self.Status.ACTIVE}:
            return "Review-Termin noch offen; Speichern und Weiterarbeiten sind möglich."
        return ""

    def get_absolute_url(self):
        return reverse("use_cases:initiative_edit", kwargs={"pk": self.pk})

    def __str__(self):
        return self.title
