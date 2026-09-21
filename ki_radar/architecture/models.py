from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import BusinessUnit
from ki_radar.core.models import TimeStampedModel

from .audit import ImmutableDecisionManager


class EvidenceBasis(models.TextChoices):
    HYPOTHESIS = "hypothesis", "Hypothese / unbestätigt"
    INDICATIVE = "indicative", "Indiz / qualitativ belegt"
    MEASURED = "measured", "Gemessen / nachgewiesen"


class TimeToValue(models.TextChoices):
    NOT_ASSESSED = "not_assessed", "Noch nicht bewertet"
    UNKNOWN = "unknown", "Unbekannt"
    SHORT = "short", "Kurz"
    MEDIUM = "medium", "Mittel"
    LONG = "long", "Lang"


class ValueStream(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        ACTIVE = "active", "Aktiv"
        ARCHIVED = "archived", "Archiviert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    demo_key = models.SlugField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    business_unit = models.ForeignKey(
        BusinessUnit,
        on_delete=models.PROTECT,
        related_name="value_streams",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_value_streams",
    )
    trigger = models.TextField(verbose_name="Auslöser")
    outcome = models.TextField(verbose_name="Ergebnis für den Empfänger")
    scope_in = models.TextField(verbose_name="Im Scope")
    scope_out = models.TextField(blank=True, verbose_name="Nicht im Scope")
    strategic_objective = models.TextField(
        blank=True,
        verbose_name="Strategisches Ziel",
    )
    stakeholders = models.TextField(blank=True, verbose_name="Stakeholder")
    constraints = models.TextField(blank=True, verbose_name="Leitplanken und Einschränkungen")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_value_streams",
    )

    class Meta:
        ordering = ["business_unit__name", "name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self):
        return reverse("architecture:value_stream_detail", kwargs={"pk": self.pk})


class ValueStreamStage(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    value_stream = models.ForeignKey(
        ValueStream,
        on_delete=models.CASCADE,
        related_name="stages",
    )
    sequence = models.PositiveSmallIntegerField(verbose_name="Reihenfolge")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, verbose_name="Aktivität und Ergebnis")
    actors = models.TextField(blank=True, verbose_name="Beteiligte Rollen")
    systems = models.TextField(blank=True, verbose_name="Systeme")
    documents = models.TextField(blank=True, verbose_name="Daten und Dokumente")
    pain_points = models.TextField(blank=True, verbose_name="Probleme und Engpässe")
    baseline_metrics = models.TextField(blank=True, verbose_name="Kennzahlen und Baseline")

    class Meta:
        ordering = ["sequence", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["value_stream", "sequence"],
                name="unique_value_stream_stage_sequence",
            )
        ]

    def __str__(self) -> str:
        return f"{self.sequence}. {self.name}"

    def get_absolute_url(self):
        return self.value_stream.get_absolute_url()


class ProcessAnalysis(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        REVIEW_REQUIRED = "review_required", "Prüfbedürftig"
        VALIDATED = "validated", "Ist-Prozess validiert"
        TARGET_DEFINED = "target_defined", "Zielbild beschrieben"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stage = models.ForeignKey(
        ValueStreamStage,
        on_delete=models.CASCADE,
        related_name="process_analyses",
    )
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1, editable=False)
    source_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    scope_start = models.TextField(verbose_name="Prozessstart")
    scope_end = models.TextField(verbose_name="Prozessende")
    trigger = models.TextField(verbose_name="Auslöser")
    outcome = models.TextField(verbose_name="Ergebnis")
    current_flow = models.TextField(verbose_name="Ist-Ablauf")
    roles = models.TextField(verbose_name="Rollen und Verantwortlichkeiten")
    systems = models.TextField(verbose_name="Anwendungen und Arbeitsmittel")
    data_objects = models.TextField(verbose_name="Datenobjekte und Dokumente")
    business_rules = models.TextField(blank=True, verbose_name="Geschäftsregeln")
    handoffs = models.TextField(blank=True, verbose_name="Übergaben und Schnittstellen")
    bottlenecks = models.TextField(verbose_name="Bottlenecks und Ursachen")
    diagnostic_observations = models.TextField(blank=True, verbose_name="Beobachtung / Problem")
    cause_hypotheses = models.TextField(blank=True, verbose_name="Ursachenhypothese")
    confirmed_causes = models.TextField(blank=True, verbose_name="Bestätigte Ursache")
    constraints = models.TextField(blank=True, verbose_name="Randbedingung / Constraint")
    exceptions = models.TextField(blank=True, verbose_name="Ausnahmen und Fehlerfälle")
    baseline_metrics = models.TextField(verbose_name="Baseline und Prozesskennzahlen")
    target_state_principles = models.TextField(
        blank=True,
        verbose_name="Prinzipien für den Soll-Prozess",
    )
    analyzed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="process_analyses",
    )

    class Meta:
        ordering = ["stage__sequence", "name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self):
        return reverse("architecture:process_analysis_detail", kwargs={"pk": self.pk})


class ProcessValidation(TimeStampedModel):
    process_analysis = models.ForeignKey(
        ProcessAnalysis,
        on_delete=models.CASCADE,
        related_name="validations",
    )
    process_version = models.PositiveIntegerField()
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="process_validations",
    )
    validator_role = models.CharField(max_length=100)
    validated_at = models.DateTimeField(default=timezone.now, editable=False)
    note = models.TextField(blank=True, verbose_name="Validierungsnotiz")
    evidence_url = models.URLField(blank=True, verbose_name="Nachweis")

    class Meta:
        ordering = ["-validated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["process_analysis", "process_version"],
                name="unique_process_validation_version",
            )
        ]

    def __str__(self) -> str:
        return f"{self.process_analysis.name} · Validierung v{self.process_version}"


class WorkDesignAssessment(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        ASSESSED = "assessed", "Bewertet"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    process_analysis = models.ForeignKey(
        ProcessAnalysis,
        on_delete=models.CASCADE,
        related_name="work_design_assessments",
    )
    process_version = models.PositiveIntegerField()
    version = models.PositiveIntegerField(default=1)
    role_name = models.CharField(max_length=200, verbose_name="Betrachtete Rolle")
    business_outcome = models.TextField(verbose_name="Geschäftsergebnis")
    method_version = models.CharField(max_length=20, default="1.7.0", editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_work_design_assessments",
    )

    class Meta:
        ordering = ["role_name", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["process_analysis", "role_name", "version"],
                name="unique_work_design_role_version",
            )
        ]

    @property
    def is_stale(self) -> bool:
        return self.process_version != self.process_analysis.version

    def __str__(self) -> str:
        return f"{self.process_analysis.name} · {self.role_name} · v{self.version}"


class WorkDesignTask(TimeStampedModel):
    class Recommendation(models.TextChoices):
        PREPARE_ONLY = "prepare-only", "Vorbereiten, nicht freigeben"
        OWN = "own", "Übernehmen + pilotieren"
        OWN_WITH_APPROVAL = "own-with-approval", "Übernehmen + Fachfreigabe"
        EXPLORE = "explore", "Gezielt explorieren"
        KEEP_HANDOFF = "keep-handoff", "Handoff vorerst beibehalten"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(
        WorkDesignAssessment,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    sequence = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=240, verbose_name="Aufgabe")
    source_area = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Herkunftsbereich",
    )
    target_work_split = models.TextField(
        blank=True,
        verbose_name="Vorgesehene Aufgabenteilung",
    )
    approval_role = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Fachfreigabe",
    )

    business_value = models.PositiveSmallIntegerField(null=True, blank=True)
    handoff_friction = models.PositiveSmallIntegerField(null=True, blank=True)
    recurrence = models.PositiveSmallIntegerField(null=True, blank=True)
    context_proximity = models.PositiveSmallIntegerField(null=True, blank=True)
    ai_leverage = models.PositiveSmallIntegerField(null=True, blank=True)
    data_readiness = models.PositiveSmallIntegerField(null=True, blank=True)
    judgment_stakes = models.PositiveSmallIntegerField(null=True, blank=True)
    specialist_accountability = models.PositiveSmallIntegerField(null=True, blank=True)

    potential_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    boundary_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    recommendation = models.CharField(
        max_length=30,
        choices=Recommendation.choices,
        blank=True,
        editable=False,
    )
    approval_required = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["sequence", "created_at"]

    def __str__(self) -> str:
        return self.name

    @property
    def criteria(self) -> dict[str, int | None]:
        return {
            "business_value": self.business_value,
            "handoff_friction": self.handoff_friction,
            "recurrence": self.recurrence,
            "context_proximity": self.context_proximity,
            "ai_leverage": self.ai_leverage,
            "data_readiness": self.data_readiness,
            "judgment_stakes": self.judgment_stakes,
            "specialist_accountability": self.specialist_accountability,
        }

    def clean(self):
        super().clean()
        from .work_design import score_task, validate_task

        validation = validate_task(self.criteria)
        if validation.invalid:
            errors = {
                field: "Bewertung muss zwischen 0 und 4 liegen." for field in validation.invalid
            }
            raise ValidationError(errors)
        if validation.complete:
            result = score_task(self.criteria)
            if result.approval_required and not self.approval_role.strip():
                raise ValidationError(
                    {
                        "approval_role": (
                            "Für diese Verantwortungsgrenze muss eine Fachfreigabe benannt werden."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        from .work_design import score_task, validate_task

        self.full_clean()
        validation = validate_task(self.criteria)
        if validation.complete:
            result = score_task(self.criteria)
            self.potential_score = result.potential_score
            self.boundary_score = result.boundary_score
            self.recommendation = result.recommendation
            self.approval_required = result.approval_required
        else:
            self.potential_score = None
            self.boundary_score = None
            self.recommendation = ""
            self.approval_required = False
        super().save(*args, **kwargs)


class SolutionOption(TimeStampedModel):
    class OptionType(models.TextChoices):
        ORGANIZATIONAL = "organizational", "Organisatorische Änderung"
        RULE_AUTOMATION = "rule_automation", "Regelbasierte Automatisierung"
        STANDARD_SOFTWARE = "standard_software", "Standardsoftware"
        CUSTOM_SOFTWARE = "custom_software", "Individuelle Software"
        ANALYTICS_ML = "analytics_ml", "Analytics oder Machine Learning"
        GENERATIVE_AI = "generative_ai", "Generative KI"
        ASSISTANT = "assistant", "Assistenzsystem"
        HYBRID = "hybrid", "Hybride Lösung"
        NO_TECH = "no_tech", "Keine technische Lösung"
        OTHER = "other", "Sonstige Option"

    class Recommendation(models.TextChoices):
        CANDIDATE = "candidate", "Kandidat"
        PREFERRED = "preferred", "Bevorzugte Option"
        REJECTED = "rejected", "Verworfen"

    class EvaluationStatus(models.TextChoices):
        DRAFT = "draft", "Noch nicht vollständig bewertet"
        ASSESSED = "assessed", "Bewertet"

    class Effort(models.TextChoices):
        NOT_ASSESSED = "not_assessed", "Noch nicht bewertet"
        LOW = "low", "Niedrig"
        MEDIUM = "medium", "Mittel"
        HIGH = "high", "Hoch"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    process_analysis = models.ForeignKey(
        ProcessAnalysis,
        on_delete=models.CASCADE,
        related_name="solution_options",
    )
    source_work_design_task = models.ForeignKey(
        WorkDesignTask,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="solution_options",
        editable=False,
    )
    source_work_design_snapshot = models.JSONField(
        default=dict,
        blank=True,
        editable=False,
    )
    name = models.CharField(max_length=200)
    option_type = models.CharField(max_length=30, choices=OptionType.choices)
    contains_ai_component = models.BooleanField(
        default=False,
        verbose_name="Enthält KI-Komponente",
        help_text=(
            "Für hybride, individuelle oder sonstige Lösungen explizit angeben. "
            "Eindeutige KI- bzw. Nicht-KI-Typen werden automatisch eingeordnet."
        ),
    )
    recommendation = models.CharField(
        max_length=20,
        choices=Recommendation.choices,
        default=Recommendation.CANDIDATE,
    )
    evaluation_status = models.CharField(
        max_length=20,
        choices=EvaluationStatus.choices,
        default=EvaluationStatus.DRAFT,
        verbose_name="Bewertungsstatus",
    )
    evidence_basis = models.CharField(
        max_length=20,
        choices=EvidenceBasis.choices,
        default=EvidenceBasis.HYPOTHESIS,
        verbose_name="Evidenzbasis",
    )
    description = models.TextField(verbose_name="Lösungsbeschreibung")
    expected_value = models.TextField(verbose_name="Erwarteter Beitrag")
    time_to_value = models.CharField(
        max_length=20,
        choices=TimeToValue.choices,
        default=TimeToValue.NOT_ASSESSED,
        verbose_name="Time-to-Value",
    )
    bottleneck_coverage = models.TextField(
        blank=True,
        verbose_name="Abdeckung von Bottleneck und Ursache",
    )
    feasibility = models.CharField(
        max_length=20,
        choices=Effort.choices,
        default=Effort.NOT_ASSESSED,
        verbose_name="Machbarkeit",
    )
    data_requirements = models.TextField(blank=True, verbose_name="Datenanforderungen")
    application_impact = models.TextField(
        blank=True,
        verbose_name="Auswirkung auf Anwendungen",
    )
    integration_impact = models.TextField(blank=True, verbose_name="Integrationen")
    integration_effort = models.CharField(
        max_length=20,
        choices=Effort.choices,
        default=Effort.NOT_ASSESSED,
        verbose_name="Integrationsaufwand",
    )
    technology_constraints = models.TextField(
        blank=True,
        verbose_name="Technologieleitplanken",
    )
    risks = models.TextField(blank=True, verbose_name="Risiken und Nachteile")
    architecture_fit = models.TextField(
        blank=True,
        verbose_name="Begründung und Architecture Fit",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="solution_options",
    )

    class Meta:
        ordering = ["recommendation", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["process_analysis"],
                condition=models.Q(recommendation="preferred"),
                name="single_preferred_solution_per_process",
            )
        ]

    @classmethod
    def fixed_ai_option_types(cls) -> set[str]:
        return {
            cls.OptionType.ANALYTICS_ML,
            cls.OptionType.GENERATIVE_AI,
            cls.OptionType.ASSISTANT,
        }

    @classmethod
    def fixed_non_ai_option_types(cls) -> set[str]:
        return {
            cls.OptionType.ORGANIZATIONAL,
            cls.OptionType.RULE_AUTOMATION,
            cls.OptionType.STANDARD_SOFTWARE,
            cls.OptionType.NO_TECH,
        }

    def clean(self):
        super().clean()
        if self.evaluation_status != self.EvaluationStatus.ASSESSED:
            return
        errors = {}
        if self.feasibility == self.Effort.NOT_ASSESSED:
            errors["feasibility"] = "Machbarkeit muss für den Status 'Bewertet' bewertet sein."
        if self.integration_effort == self.Effort.NOT_ASSESSED:
            errors["integration_effort"] = (
                "Integrationsaufwand muss für den Status 'Bewertet' bewertet sein."
            )
        if self.time_to_value == TimeToValue.NOT_ASSESSED:
            errors["time_to_value"] = (
                "Time-to-Value muss für den Status 'Bewertet' eingeordnet werden; "
                "'Unbekannt' ist zulässig, wenn keine belastbare Zeitangabe vorliegt."
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.option_type in self.fixed_ai_option_types():
            self.contains_ai_component = True
        elif self.option_type in self.fixed_non_ai_option_types():
            self.contains_ai_component = False
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self):
        return self.process_analysis.get_absolute_url()

    @property
    def comparison_complete(self) -> bool:
        required = (
            self.description,
            self.expected_value,
            self.bottleneck_coverage,
            self.data_requirements,
            self.application_impact,
            self.integration_impact,
            self.risks,
            self.architecture_fit,
        )
        assessed_efforts = (
            self.feasibility,
            self.integration_effort,
        )
        return (
            self.evaluation_status == self.EvaluationStatus.ASSESSED
            and all(str(value).strip() for value in required)
            and all(value != self.Effort.NOT_ASSESSED for value in assessed_efforts)
            and self.time_to_value != TimeToValue.NOT_ASSESSED
        )

    @property
    def starts_ai_use_case(self) -> bool:
        if self.option_type in self.fixed_ai_option_types():
            return True
        if self.option_type in self.fixed_non_ai_option_types():
            return False
        return bool(self.contains_ai_component)


class SolutionSelectionDecision(TimeStampedModel):
    process_analysis = models.ForeignKey(
        ProcessAnalysis,
        on_delete=models.PROTECT,
        related_name="solution_selection_decisions",
    )
    selected_option = models.ForeignKey(
        SolutionOption,
        on_delete=models.PROTECT,
        related_name="selection_decisions",
    )
    rationale = models.TextField(verbose_name="Auswahlbegründung")
    comparison_snapshot = models.JSONField(default=list, editable=False)
    process_version = models.PositiveIntegerField(null=True, blank=True, editable=False)
    diagnosis_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="solution_selection_decisions",
    )
    decided_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = ImmutableDecisionManager()

    class Meta:
        ordering = ["-decided_at", "-created_at"]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Eine dokumentierte Lösungsentscheidung ist unveränderlich.")
        if (
            self.selected_option_id
            and self.process_analysis_id
            and self.selected_option.process_analysis_id != self.process_analysis_id
        ):
            raise ValidationError("Die ausgewählte Option gehört nicht zu dieser Prozessanalyse.")
        if not self.rationale.strip():
            raise ValidationError("Für die Lösungsentscheidung ist eine Begründung erforderlich.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Eine dokumentierte Lösungsentscheidung darf nicht gelöscht werden.")

    def __str__(self) -> str:
        return f"{self.process_analysis}: {self.selected_option}"


class UseCaseOrigin(TimeStampedModel):
    use_case = models.OneToOneField(
        "use_cases.UseCase",
        on_delete=models.CASCADE,
        related_name="architecture_origin",
    )
    stage = models.ForeignKey(
        ValueStreamStage,
        on_delete=models.PROTECT,
        related_name="use_case_origins",
    )
    process_analysis = models.ForeignKey(
        ProcessAnalysis,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="use_case_origins",
    )
    source_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    solution_option = models.ForeignKey(
        SolutionOption,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="use_case_origins",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.use_case.short_id} aus {self.stage}"
