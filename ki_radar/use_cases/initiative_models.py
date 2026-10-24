"""The shared outcome identity; intake and legacy decisions remain independent."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from simple_history.models import HistoricalRecords

from ki_radar.core.models import TimeStampedModel

from .outcome_guards import InitiativeManager


class ImprovementInitiative(TimeStampedModel):
    objects = InitiativeManager()

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
    preparation_drafts = models.JSONField(default=dict, blank=True, editable=False)
    context_provenance = models.JSONField(default=list, blank=True, editable=False)
    outcome_revision = models.PositiveIntegerField(default=1, editable=False)
    target_group = models.TextField(blank=True, verbose_name="Betroffene Empfängergruppe")
    hypothesis_origin = models.CharField(max_length=10, default="human", editable=False)
    confirmation_reason = models.TextField(blank=True, editable=False)
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
            if self.effect_status in {self.Effect.CONFIRMED, self.Effect.REFUTED}:
                from .initiatives import OUTCOME_FIELDS

                previous = (
                    type(self).objects.filter(pk=self.pk).first()
                    if not self._state.adding
                    else None
                )
                claim_changed = previous is None or any(
                    getattr(previous, field) != getattr(self, field)
                    for field in (*OUTCOME_FIELDS, "effect_status", "effect_reason")
                )
                # Grandfather unchanged historical completions, not new claims.
                changing_claim = (
                    previous is None or previous.status != self.Status.COMPLETED or claim_changed
                )
                if changing_claim:
                    review = (
                        InitiativeImpactReview.objects.select_related("initiative")
                        .filter(initiative_id=self.pk)
                        .first()
                        if previous
                        else None
                    )
                    if (
                        review is None
                        or review.review_required
                        or claim_changed
                        or previous.outcome_revision != self.outcome_revision
                        or not review.reviewed_by_id
                        or not (review.selection_id or review.use_case_id)
                        or not review.business_measurement.strip()
                        or not review.business_evidence.strip()
                    ):
                        errors["status"] = (
                            "Bestätigter oder widerlegter Geschäftserfolg darf nur mit "
                            "aktuellem abgeschlossenen Wirkungsreview als abgeschlossen gelten. "
                            "Ein ungeklärter Abschluss bleibt möglich."
                        )
            if errors:
                raise ValidationError(errors)

    @transaction.atomic
    def save(self, *args, **kwargs):
        previous = (
            type(self).objects.select_for_update().filter(pk=self.pk).first()
            if not self._state.adding
            else None
        )
        transition_to_proven_completion = (
            self.status == self.Status.COMPLETED
            and self.effect_status in {self.Effect.CONFIRMED, self.Effect.REFUTED}
            and (previous is None or previous.status != self.Status.COMPLETED)
        )
        self.full_clean()
        super().save(*args, **kwargs)
        if transition_to_proven_completion:
            # The proof was current before the status-only transition. Keep the
            # same reviewed evidence current for its new initiative revision.
            review = InitiativeImpactReview.objects.get(initiative_id=self.pk)
            review.initiative_revision = self.revision
            review._history_user = self.updated_by
            review.save(update_fields=["initiative_revision", "updated_at"])

    @property
    def review_hint(self):
        if not self.next_review_date and self.status in {self.Status.DRAFT, self.Status.ACTIVE}:
            return "Review-Termin noch offen; Speichern und Weiterarbeiten sind möglich."
        return ""

    def get_absolute_url(self):
        return reverse("use_cases:initiative_edit", kwargs={"pk": self.pk})

    @property
    def effect_statement_label(self):
        """A saved statement is not evidence of business success."""
        if not self.effect_status:
            return "Noch nicht nachgewiesen"
        try:
            reviewed = not self.impact_review.review_required
        except InitiativeImpactReview.DoesNotExist:
            reviewed = False
        qualifier = (
            "Geprüfte Wirkungsaussage" if reviewed else "Ungeprüfte Wirkungsaussage (Entwurf)"
        )
        return f"{qualifier}: {self.get_effect_status_display()}"

    def __str__(self):
        return self.title


class InitiativeImpactReview(TimeStampedModel):
    """One current finding, not a delivery lifecycle or a measurement series."""

    class ProcessResult(models.TextChoices):
        UNKNOWN = "unknown", "Noch nicht nachgewiesen"
        ACHIEVED = "achieved", "Prozessziel erreicht"
        MISSED = "missed", "Prozessziel verfehlt"

    initiative = models.OneToOneField(
        ImprovementInitiative, on_delete=models.PROTECT, related_name="impact_review"
    )
    selection = models.ForeignKey(
        "architecture.SolutionSelectionDecision",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Lösungsentscheidung",
    )
    use_case = models.ForeignKey(
        "use_cases.UseCase",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="KI-Prozessmetrik aus Use Case",
    )
    process_result = models.CharField(
        max_length=20,
        choices=ProcessResult.choices,
        default=ProcessResult.UNKNOWN,
        verbose_name="Non-KI-Prozesswirkung",
    )
    process_measurement = models.TextField(
        blank=True,
        verbose_name="Non-KI-Messdefinition und aktueller Messstand",
        help_text="Kennzahl, Methode, Zeitraum, Population, Stand und Nachweis benennen.",
    )
    business_measurement = models.TextField(
        blank=True,
        verbose_name="Geschäftsergebnismetrik und aktueller Messstand",
        help_text="Andere Größe, Methode, Zeitraum, Population und Stand; unbekannt bleibt offen.",
    )
    business_evidence = models.TextField(
        blank=True, verbose_name="Nachweis des Geschäftsergebnisses"
    )
    measurement_difference = models.TextField(
        blank=True,
        verbose_name="Abgrenzung zur KI-Prozessmetrik",
        help_text="Welche andere Größe misst das Geschäftsergebnis? Keine Messwertkopie.",
    )
    attribution = models.CharField(
        max_length=20,
        choices=ImprovementInitiative.Effect.choices,
        default=ImprovementInitiative.Effect.UNCLEAR,
        verbose_name="Attribution / Wirkannahme",
    )
    attribution_reason = models.TextField(
        blank=True,
        verbose_name="Begründung und Grenzen der Attribution",
    )
    outcome_revision = models.PositiveIntegerField(null=True, blank=True, editable=False)
    initiative_revision = models.PositiveIntegerField(null=True, blank=True, editable=False)
    metric_history_id = models.PositiveIntegerField(null=True, blank=True, editable=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    history = HistoricalRecords()

    def clean(self):
        super().clean()
        if (
            self.selection_id
            and self.selection.process_analysis.initiative_id != self.initiative_id
        ):
            raise ValidationError(
                {"selection": "Die Entscheidung gehört zu einem anderen Vorhaben."}
            )
        if (
            self.selection_id
            and self.selection.selected_option.option_type
            in self.selection.selected_option.fixed_ai_option_types()
            and (
                self.process_measurement.strip()
                or self.process_result != self.ProcessResult.UNKNOWN
            )
        ):
            raise ValidationError(
                "KI-Prozesswirkung bitte über den bestehenden Use Case referenzieren."
            )
        if self.use_case_id:
            if self.use_case.initiative_id != self.initiative_id:
                raise ValidationError(
                    {"use_case": "Der Use Case gehört zu einem anderen Vorhaben."}
                )
            if self.selection_id:
                from ki_radar.architecture.models import UseCaseOrigin

                if not UseCaseOrigin.objects.filter(
                    use_case_id=self.use_case_id,
                    process_analysis_id=self.selection.process_analysis_id,
                    solution_option_id=self.selection.selected_option_id,
                ).exists():
                    raise ValidationError(
                        "Use Case und Lösungsentscheidung haben verschiedene Herkunft."
                    )
            if (
                self.process_measurement.strip()
                or self.process_result != self.ProcessResult.UNKNOWN
            ):
                raise ValidationError(
                    "KI-Prozesswirkung ausschließlich aus UseCase.metric_* referenzieren."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def review_required(self):
        if (
            not self.reviewed_at
            or self.initiative_revision != self.initiative.revision
            or self.outcome_revision != self.initiative.outcome_revision
            or bool(self.selection_id and self.selection.outcome_review_required)
        ):
            return True
        if not self.use_case_id:
            return False
        if self.use_case.is_archived or self.metric_history_id is None:
            return True
        original = self.use_case.history.filter(history_id=self.metric_history_id).first()
        if original is None:
            return True
        # Compare the reviewed metric snapshot, not the entire UseCase revision:
        # owner, dates or status changes must not invalidate unchanged measurements.
        metric_fields = (
            "metric_name",
            "metric_type",
            "metric_direction",
            "metric_unit",
            "metric_baseline",
            "metric_target",
            "metric_actual",
            "metric_measurement_method",
            "metric_measurement_period",
            "metric_measurement_population",
            "metric_measured_at",
            "metric_evidence_url",
        )
        return any(
            getattr(original, field) != getattr(self.use_case, field) for field in metric_fields
        )
