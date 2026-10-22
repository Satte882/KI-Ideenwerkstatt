"""Optional early AI capability evidence; never a binding decision or business outcome."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from ki_radar.architecture.audit import ImmutableDecisionManager
from ki_radar.core.models import TimeStampedModel


class CapabilityExperiment(TimeStampedModel):
    """A draft or an immutable human-recorded finding for one improvement initiative."""

    class DataKind(models.TextChoices):
        SYNTHETIC = "synthetic", "Synthetisch / Testdaten"
        REAL = "real", "Reale Daten (gesonderte Governance erforderlich)"

    class Finding(models.TextChoices):
        OPEN = "open", "Noch nicht überprüft"
        SUPPORTED = "supported", "Capability im Test gestützt"
        PARTIAL = "partial", "Teilweise / mit Grenzen"
        NOT_SUPPORTED = "not_supported", "Capability nicht bestätigt"

    initiative = models.ForeignKey(
        "use_cases.ImprovementInitiative",
        on_delete=models.PROTECT,
        related_name="capability_experiments",
    )
    title = models.CharField(max_length=200, verbose_name="Experiment / Fragestellung")
    ai_vision = models.TextField(blank=True, verbose_name="Ambitionierte AI-first-Zielhypothese")
    first_viable_step = models.TextField(
        blank=True, verbose_name="Erste realistisch betreibbare Ausbaustufe"
    )
    capability_hypothesis = models.TextField(
        blank=True, verbose_name="Zu testende KI-Fähigkeit / Widerlegungskriterium"
    )
    tested_configuration = models.TextField(
        blank=True, verbose_name="Version, Konfiguration und Änderungen"
    )
    test_case_ids = models.TextField(
        blank=True,
        verbose_name="Geprüfte Fall-Referenzen (eine ID pro Zeile)",
        help_text="Keine echten Falldaten oder personenbezogenen Inhalte hier speichern.",
    )
    holdout_case_ids = models.TextField(
        blank=True,
        verbose_name="Unverbrauchte Fall-Referenzen (eine ID pro Zeile)",
        help_text=(
            "Unbekannte Fälle separat führen; keine bereits getesteten Fälle wiederverwenden."
        ),
    )
    holdout_unseen_confirmed = models.BooleanField(
        default=False,
        verbose_name="Die Holdout-Fälle waren vor dem Test nicht zur Anpassung verwendet",
    )
    failure_modes = models.TextField(blank=True, verbose_name="Fehlerbilder und Grenzen")
    assumptions = models.TextField(blank=True, verbose_name="Daten-, System- und Betriebsannahmen")
    effort = models.TextField(blank=True, verbose_name="Aufwand / Time-to-Value")
    finding = models.CharField(
        max_length=20,
        choices=Finding.choices,
        default=Finding.OPEN,
        verbose_name="Beobachtetes Capability-Ergebnis",
    )
    evidence_reference = models.TextField(
        blank=True, verbose_name="Prüfnachweis / Quelle / Protokollreferenz"
    )
    learning_value = models.TextField(
        blank=True,
        verbose_name="Learning Value: überprüfbare neue Erkenntnis",
        help_text="Kein finanzieller Geschäftsnutzen und keine automatische Freigabe.",
    )
    data_kind = models.CharField(
        max_length=12,
        choices=DataKind.choices,
        default=DataKind.SYNTHETIC,
        verbose_name="Art des Testmaterials",
    )
    governance_reference = models.TextField(
        blank=True, verbose_name="Freigabe-/Governance-Referenz für Real-Daten"
    )
    retest_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="retests",
        verbose_name="Vorheriger Capability-Test",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_capability_experiments",
        editable=False,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_capability_experiments",
        editable=False,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    revision = models.PositiveIntegerField(default=1, editable=False)
    objects = ImmutableDecisionManager()

    class Meta:
        ordering = ["-created_at", "-pk"]

    def clean(self):
        super().clean()
        if self.retest_of_id:
            if self.retest_of_id == self.pk:
                raise ValidationError({"retest_of": "Ein Test kann nicht sich selbst wiederholen."})
            if self.retest_of.initiative_id != self.initiative_id:
                raise ValidationError(
                    {"retest_of": "Der frühere Test gehört zu einem anderen Vorhaben."}
                )

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, reviewed_at__isnull=False).exists():
            raise ValidationError(
                "Ein geprüfter Capability-Nachweis ist unveränderlich; neuen Test anlegen."
            )
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Capability-Nachweise können nicht gelöscht werden.")

    def get_absolute_url(self):
        return reverse(
            "use_cases:capability_experiment_edit",
            kwargs={"initiative_id": self.initiative_id, "pk": self.pk},
        )

    @property
    def is_reviewed(self):
        return self.reviewed_at is not None


class CapabilityExperimentCorrection(TimeStampedModel):
    """Append-only clerical correction; the reviewed experiment stays untouched."""

    experiment = models.ForeignKey(
        CapabilityExperiment,
        on_delete=models.PROTECT,
        related_name="corrections",
    )
    note = models.TextField(
        verbose_name="Berichtigung (alter und korrigierter Stand samt Grund)",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="capability_experiment_corrections",
        editable=False,
    )
    objects = ImmutableDecisionManager()

    class Meta:
        ordering = ["created_at", "pk"]

    def clean(self):
        super().clean()
        if not self.note.strip():
            raise ValidationError({"note": "Bitte die konkrete Korrektur dokumentieren."})
        if self.experiment_id and not self.experiment.is_reviewed:
            raise ValidationError("Ungeprüfte Entwürfe können direkt bearbeitet werden.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Ein gespeicherter Korrekturvermerk ist unveränderlich.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Korrekturvermerke sind append-only.")
