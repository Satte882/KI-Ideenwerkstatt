"""The shared outcome identity; intake and legacy decisions remain independent."""

import uuid

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
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
    measurement_method = models.TextField(blank=True, verbose_name="Business-Messmethode")
    measurement_period = models.TextField(
        blank=True, verbose_name="Geplanter Business-Messzeitraum"
    )
    measurement_population = models.TextField(blank=True, verbose_name="Business-Messpopulation")
    measurement_reference = models.TextField(
        blank=True,
        verbose_name="Referenz / Vergleichsverfahren",
        help_text="Absolutes Ziel oder geeigneter Vorher-/Vergleichsbezug; keine Pflicht-Baseline.",
    )
    measurement_unknowns = models.TextField(
        blank=True,
        verbose_name="Offene Messangaben und Klärungspunkt",
        help_text="Fehlende Angaben begründen und geplanten Klärungspunkt benennen.",
    )
    measurement_change_reason = models.TextField(
        blank=True,
        verbose_name="Grund der Messplan-/Kriterienänderung",
        help_text="Historie hält Person und Zeitpunkt fest. Nachträgliches bleibt nachträglich.",
    )
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
                from .initiatives import initiative_claim_matches

                previous = (
                    type(self).objects.filter(pk=self.pk).first()
                    if not self._state.adding
                    else None
                )
                claim_changed = previous is None or not initiative_claim_matches(previous, self)
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
    process_measurement_kind = models.CharField(
        max_length=30,
        blank=True,
        choices=[("organizational", "Andere organisatorische Teilwirkung")],
        verbose_name="Einordnung der zusätzlichen Prozessmessung",
        help_text="Bei KI nur für eine andere organisatorische Messgröße auswählen. "
        "Dieselbe KI-Metrik ausschließlich im Use Case führen.",
    )
    process_measurement_boundary = models.TextField(
        blank=True,
        verbose_name="Abgrenzung der organisatorischen Teilwirkung",
        help_text="Gemessene Größe, organisatorische Komponente, Methode und Population "
        "benennen und gegenüber der referenzierten KI-Metrik abgrenzen. "
        "Menschliche Einordnung; keine automatische semantische Duplikatprüfung.",
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
    criteria_assessment = models.TextField(
        blank=True,
        verbose_name="Abgleich mit den historischen Prüfkriterien",
        help_text="Je Kriterium erfüllt, verfehlt oder unklar; Messung und Evidenz zuordnen.",
    )
    assessment_basis = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ("original", "Ursprünglicher Entscheidungsmaßstab"),
            ("retrospective", "Nachträgliche Bewertung / Vorab-Beleg fehlt"),
        ],
        verbose_name="Zeitliche Grundlage der Bewertung",
    )
    criteria_deviation = models.TextField(
        blank=True,
        verbose_name="Abweichungen, Zeitpunkt und Evidenzgrenzen",
        help_text="Spätere Änderungen und Ergebniskenntnis einordnen; keine Rückdatierung.",
    )
    contribution_boundary = models.TextField(
        blank=True,
        verbose_name="Weitere Beiträge, Wechselwirkungen und Abdeckungsgrenze",
        help_text="Ein strukturierter Auswahl-/Use-Case-Bezug; keine vollständige Aggregation.",
    )
    criteria_snapshot = models.JSONField(default=dict, blank=True, editable=False)
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
        blocker = self.measurement_reference_blocker()
        if blocker:
            raise ValidationError(blocker)

    def measurement_reference_blocker(self, *, finalize=False):
        """One explicit human boundary, shared by writes and freshness; no text inference."""
        has_measurement = bool(
            self.process_measurement.strip() or self.process_result != self.ProcessResult.UNKNOWN
        )
        ai_selection = bool(self.selection_id and self.selection.selected_option.starts_ai_use_case)
        if not (self.use_case_id or ai_selection) or not has_measurement:
            return ""
        # Preserve the existing draft contract: linked UseCases/fixed AI types
        # reject copies already on save; ambiguous historical types may save drafts.
        strict_draft = bool(
            self.use_case_id
            or (
                self.selection_id
                and self.selection.selected_option.option_type
                in self.selection.selected_option.fixed_ai_option_types()
            )
        )
        if not self.process_measurement_kind:
            if finalize or strict_draft:
                return (
                    "KI-Prozesswirkung aus UseCase.metric_* referenzieren. Eine andere "
                    "organisatorische Teilwirkung ausdrücklich einordnen und abgrenzen."
                )
            return ""
        if finalize:
            if not self.use_case_id:
                return (
                    "Bitte den tatsächlich zugehörigen Use Case mit seiner KI-Metrik referenzieren."
                )
            if not self.process_measurement_boundary.strip():
                return "Bitte die andere organisatorische Messgröße zur KI-Metrik abgrenzen."
        return ""

    @property
    def measurement_review_blocker(self):
        return self.measurement_reference_blocker(finalize=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def criteria_review_blocker(self):
        from .measurement_plan import criteria_review_blocker

        return criteria_review_blocker(self)

    @property
    def review_required(self):
        from .impact_reviews import REVIEW_FIELDS
        from .initiatives import initiative_claim_matches
        from .outcome_contract import _origin_blockers

        if (
            not self.reviewed_at
            or self.measurement_review_blocker
            or bool(
                self.criteria_snapshot
                and self.initiative.effect_status != "unclear"
                and self.criteria_review_blocker
            )
            or self.outcome_revision != self.initiative.outcome_revision
            or bool(self.selection_id and self.selection.outcome_review_required)
        ):
            return True
        # Existing audit rows preserve the actual reviewed content. A technical
        # revision still protects writes, but metadata does not change the claim.
        original_initiative = (
            self.initiative.history.filter(revision=self.initiative_revision)
            .order_by("history_date", "history_id")
            .first()
        )
        if original_initiative is None or not initiative_claim_matches(
            original_initiative, self.initiative
        ):
            return True
        original_review = (
            self.history.filter(reviewed_at=self.reviewed_at)
            .order_by("history_date", "history_id")
            .first()
        )
        # Reference, measurement and evidence edits cannot inherit a prior
        # interpretation, including edits through an individual ORM save.
        if original_review is None or any(
            getattr(original_review, field) != getattr(self, field)
            for field in (
                *(
                    f"{name}_id" if name in {"selection", "use_case"} else name
                    for name in REVIEW_FIELDS
                ),
                "reviewed_by_id",
                "metric_history_id",
                "criteria_snapshot",
            )
        ):
            return True
        if not self.use_case_id:
            return False
        if self.use_case.is_archived or self.metric_history_id is None:
            return True
        original = self.use_case.history.filter(history_id=self.metric_history_id).first()
        if original is None:
            return True
        if original.initiative_id != self.use_case.initiative_id:
            return True
        try:
            origin = self.use_case.architecture_origin
        except ObjectDoesNotExist:
            origin = None
        if (
            origin
            and self.use_case.outcome_contract_version
            and _origin_blockers(self.use_case, origin.process_analysis)
        ):
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
