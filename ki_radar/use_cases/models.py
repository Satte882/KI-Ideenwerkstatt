import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from simple_history.models import HistoricalRecords

from ki_radar.accounts.models import BusinessUnit
from ki_radar.core.models import TimeStampedModel


class UseCaseCounter(models.Model):
    id = models.BigAutoField(primary_key=True)

    def __str__(self) -> str:
        return str(self.pk)


class UseCase(TimeStampedModel):
    class Status(models.TextChoices):
        IDEA = "idea", "Idee"
        REVIEW = "review", "Prüfung"
        PILOT = "pilot", "Pilot"
        OPERATION = "operation", "Betrieb"
        ENDED = "ended", "Beendet"

    class DecisionStatus(models.TextChoices):
        CLARIFICATION = "clarification", "In Klärung"
        READY = "ready", "Bereit zur Bewertung"
        DEFERRED = "deferred", "Zurückgestellt"
        APPROVED = "approved", "Freigegeben"
        APPROVED_WITH_CONDITIONS = (
            "approved_with_conditions",
            "Freigegeben mit Auflagen",
        )
        NOT_PURSUED = "not_pursued", "Nicht weiterverfolgt"

    class Level(models.TextChoices):
        LOW = "low", "Niedrig"
        MEDIUM = "medium", "Mittel"
        HIGH = "high", "Hoch"

    class Priority(models.TextChoices):
        LOW = "low", "Niedrig"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Hoch"
        CRITICAL = "critical", "Kritisch"

    class SolutionType(models.TextChoices):
        STANDARD = "standard", "Standardsoftware"
        CUSTOM = "custom", "Individuelle Anwendung"
        EMBEDDED = "embedded", "Eingebettete Systemfunktion"
        ANALYTICS = "analytics", "Analyse- oder Prognosemodell"
        GENERATIVE = "generative", "Generative KI"
        ASSISTANT = "assistant", "Assistenzsystem"
        AUTOMATION = "automation", "Automatisierungslösung"
        OTHER = "other", "Sonstige Lösung"

    class HostingType(models.TextChoices):
        INTERNAL = "internal", "Intern"
        EXTERNAL = "external", "Extern"
        HYBRID = "hybrid", "Hybrid"
        UNKNOWN = "unknown", "Noch offen"

    class MetricType(models.TextChoices):
        NUMBER = "number", "Zahl"
        PERCENT = "percent", "Prozent"
        DURATION = "duration", "Dauer"
        CURRENCY = "currency", "Geldbetrag"
        COUNT = "count", "Anzahl"
        RATING = "rating", "Bewertungsskala"

    class MetricDirection(models.TextChoices):
        LOWER = "lower", "Niedriger ist besser"
        HIGHER = "higher", "Höher ist besser"

    class MetricResult(models.TextChoices):
        NOT_DEFINED = "not_defined", "Metrik nicht definiert"
        NOT_MEASURED = "not_measured", "Noch nicht gemessen"
        ACHIEVED = "achieved", "Ziel erreicht"
        NOT_ACHIEVED = "not_achieved", "Ziel nicht erreicht"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    short_id = models.CharField(max_length=20, unique=True, blank=True)
    demo_key = models.SlugField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    problem_statement = models.TextField()
    business_unit = models.ForeignKey(
        BusinessUnit, on_delete=models.PROTECT, related_name="use_cases"
    )
    affected_process = models.CharField(max_length=200)
    target_users = models.TextField(blank=True)
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="submitted_use_cases",
    )
    business_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_use_cases"
    )
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="coordinated_use_cases",
    )
    technical_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="technical_use_cases",
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IDEA, db_index=True
    )
    decision_status = models.CharField(
        max_length=30,
        choices=DecisionStatus.choices,
        default=DecisionStatus.CLARIFICATION,
        db_index=True,
        verbose_name="Entscheidungsstatus",
    )
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    next_review_date = models.DateField(null=True, blank=True, db_index=True)
    pilot_start = models.DateField(null=True, blank=True)
    planned_pilot_end = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)

    solution_type = models.CharField(
        max_length=30, choices=SolutionType.choices, default=SolutionType.OTHER
    )
    hosting_type = models.CharField(
        max_length=20, choices=HostingType.choices, default=HostingType.UNKNOWN
    )
    provider = models.CharField(max_length=200, blank=True)
    product_name = models.CharField(max_length=200, blank=True)
    model_name = models.CharField(max_length=200, blank=True)
    source_systems = models.TextField(blank=True)
    data_sources = models.TextField(blank=True)
    interface_description = models.TextField(blank=True)
    intended_users = models.TextField(blank=True)
    intended_purpose = models.TextField(blank=True)

    expected_benefit = models.TextField()
    benefit_category = models.CharField(max_length=120, blank=True)
    baseline = models.TextField(blank=True)
    success_criterion = models.TextField(blank=True)
    target_value = models.CharField(max_length=200, blank=True)
    realized_result = models.TextField(blank=True)

    metric_name = models.CharField(max_length=200, blank=True, verbose_name="Primäre Erfolgsmetrik")
    metric_type = models.CharField(
        max_length=20, choices=MetricType.choices, blank=True, verbose_name="Metriktyp"
    )
    metric_direction = models.CharField(
        max_length=10,
        choices=MetricDirection.choices,
        blank=True,
        verbose_name="Optimierungsrichtung",
    )
    metric_unit = models.CharField(max_length=80, blank=True, verbose_name="Einheit")
    metric_baseline = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Baseline-Wert",
    )
    metric_target = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Zielwert",
    )
    metric_actual = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Gemessener Ist-Wert",
    )
    metric_measurement_method = models.TextField(blank=True, verbose_name="Messmethode")
    metric_measurement_period = models.CharField(
        max_length=200, blank=True, verbose_name="Messzeitraum"
    )
    metric_measured_at = models.DateField(null=True, blank=True, verbose_name="Messdatum")
    metric_evidence_url = models.URLField(blank=True, verbose_name="Messnachweis")

    one_time_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    recurring_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )

    business_value = models.CharField(max_length=10, choices=Level.choices, default=Level.MEDIUM)
    technical_feasibility = models.CharField(
        max_length=10, choices=Level.choices, default=Level.MEDIUM
    )
    data_readiness = models.CharField(max_length=10, choices=Level.choices, default=Level.MEDIUM)
    risk_complexity = models.CharField(max_length=10, choices=Level.choices, default=Level.MEDIUM)

    privacy_review_required = models.BooleanField(default=False)
    security_review_required = models.BooleanField(default=False)
    legal_review_required = models.BooleanField(default=False)
    privacy_review_completed = models.BooleanField(default=False)
    security_review_completed = models.BooleanField(default=False)
    legal_review_completed = models.BooleanField(default=False)
    human_oversight = models.TextField(blank=True)
    support_responsibility = models.TextField(blank=True)

    ending_reason = models.TextField(blank=True)
    final_assessment = models.TextField(blank=True)
    lessons_learned = models.TextField(blank=True)
    data_and_access_handling = models.TextField(blank=True)
    replacement_solution = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False)

    history = HistoricalRecords(inherit=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["status", "next_review_date"]),
            models.Index(fields=["business_unit", "status"]),
            models.Index(fields=["decision_status", "updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.short_id or 'Neu'} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.short_id:
            counter = UseCaseCounter.objects.create()
            self.short_id = f"KI-{counter.pk:04d}"
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
        for required_field, completed_field in [
            ("privacy_review_required", "privacy_review_completed"),
            ("security_review_required", "security_review_completed"),
            ("legal_review_required", "legal_review_completed"),
        ]:
            if not getattr(self, required_field) and getattr(self, completed_field):
                setattr(self, completed_field, False)
                if update_fields is not None:
                    update_fields.add(completed_field)
        if update_fields is not None:
            kwargs["update_fields"] = update_fields
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("use_cases:detail", kwargs={"pk": self.pk})

    @property
    def metric_result(self) -> str:
        if not all([self.metric_name, self.metric_direction]) or self.metric_target is None:
            return self.MetricResult.NOT_DEFINED
        if self.metric_actual is None:
            return self.MetricResult.NOT_MEASURED
        if self.metric_direction == self.MetricDirection.LOWER:
            achieved = self.metric_actual <= self.metric_target
        else:
            achieved = self.metric_actual >= self.metric_target
        return self.MetricResult.ACHIEVED if achieved else self.MetricResult.NOT_ACHIEVED

    @property
    def metric_result_label(self) -> str:
        metric_definition_complete = all(
            [
                self.metric_name,
                self.metric_type,
                self.metric_direction,
                self.metric_unit,
                self.metric_measurement_method,
            ]
        )
        if metric_definition_complete:
            if self.metric_baseline is None and self.metric_target is None:
                return "Metrik definiert · Baseline und Ziel offen"
            if self.metric_baseline is None:
                return "Metrik definiert · Baseline offen"
            if self.metric_target is None:
                return "Metrik definiert · Zielwert offen"
        return self.MetricResult(self.metric_result).label

    @property
    def metric_delta(self) -> Decimal | None:
        if self.metric_actual is None or self.metric_baseline is None:
            return None
        return self.metric_actual - self.metric_baseline

    @property
    def recommendation(self) -> str:
        high_positive = sum(
            x == self.Level.HIGH
            for x in [self.business_value, self.technical_feasibility, self.data_readiness]
        )
        if self.risk_complexity == self.Level.HIGH or self.data_readiness == self.Level.LOW:
            return "Weitere Klärung erforderlich"
        if high_positive >= 2 and self.risk_complexity != self.Level.HIGH:
            return "Bevorzugt prüfen"
        return "Vorläufig zurückstellen"


class DecisionAssessment(TimeStampedModel):
    class EvidenceQuality(models.IntegerChoices):
        ASSUMPTION = 1, "Unbestätigte Annahme"
        EXPERT_OPINION = 2, "Fachliche Einschätzung"
        SAMPLE = 3, "Stichprobe oder Einzelmessung"
        REPRESENTATIVE = 4, "Repräsentative Messung"
        INDEPENDENT = 5, "Unabhängig bestätigte Messung"

    class ConfidenceFactor(models.IntegerChoices):
        CRITICAL = 1, "Unzureichend"
        LIMITED = 2, "Eingeschränkt"
        SOLID = 3, "Belastbar"
        STRONG = 4, "Sehr belastbar"

    class Recommendation(models.TextChoices):
        DEFERRED = UseCase.DecisionStatus.DEFERRED, "Zurückstellen"
        APPROVED = UseCase.DecisionStatus.APPROVED, "Freigeben"
        APPROVED_WITH_CONDITIONS = (
            UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
            "Mit Auflagen freigeben",
        )
        NOT_PURSUED = UseCase.DecisionStatus.NOT_PURSUED, "Nicht weiterverfolgen"

    use_case = models.ForeignKey(
        UseCase, on_delete=models.CASCADE, related_name="decision_assessments"
    )
    version = models.PositiveIntegerField()
    assessment_date = models.DateField(default=timezone.localdate)
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="decision_assessments",
    )
    business_value = models.CharField(max_length=10, choices=UseCase.Level.choices)
    strategic_fit = models.CharField(max_length=10, choices=UseCase.Level.choices)
    technical_feasibility = models.CharField(max_length=10, choices=UseCase.Level.choices)
    data_readiness = models.CharField(max_length=10, choices=UseCase.Level.choices)
    risk_complexity = models.CharField(max_length=10, choices=UseCase.Level.choices)
    evidence_quality = models.PositiveSmallIntegerField(choices=EvidenceQuality.choices)
    evidence_recency = models.PositiveSmallIntegerField(choices=ConfidenceFactor.choices)
    evidence_coverage = models.PositiveSmallIntegerField(choices=ConfidenceFactor.choices)
    independent_review = models.PositiveSmallIntegerField(choices=ConfidenceFactor.choices)
    assumptions_resolved = models.PositiveSmallIntegerField(choices=ConfidenceFactor.choices)
    evidence_url = models.URLField(blank=True)
    rationale = models.TextField()
    governance_precheck_completed = models.BooleanField(
        default=False,
        verbose_name="Governance-Vorprüfung durchgeführt",
    )
    recommendation = models.CharField(max_length=30, choices=Recommendation.choices)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["use_case", "version"],
                name="unique_decision_assessment_version",
            )
        ]

    def __str__(self) -> str:
        return f"{self.use_case.short_id} - Bewertung v{self.version}"

    def clean(self):
        super().clean()
        if (
            self.evidence_quality is not None
            and self.evidence_quality > self.EvidenceQuality.ASSUMPTION
            and not self.evidence_url
        ):
            raise ValidationError(
                {
                    "evidence_url": (
                        "Ab einer fachlichen Einschätzung ist ein Nachweislink erforderlich."
                    )
                }
            )

    @property
    def confidence_level(self) -> str:
        factors = [
            self.evidence_recency,
            self.evidence_coverage,
            self.independent_review,
            self.assumptions_resolved,
        ]
        if self.evidence_quality >= self.EvidenceQuality.REPRESENTATIVE and all(
            value >= self.ConfidenceFactor.SOLID for value in factors
        ):
            return UseCase.Level.HIGH
        if self.evidence_quality >= self.EvidenceQuality.EXPERT_OPINION and all(
            value >= self.ConfidenceFactor.LIMITED for value in factors
        ):
            return UseCase.Level.MEDIUM
        return UseCase.Level.LOW

    @property
    def confidence_label(self) -> str:
        return UseCase.Level(self.confidence_level).label


class ApprovalDecision(TimeStampedModel):
    use_case = models.ForeignKey(
        UseCase, on_delete=models.CASCADE, related_name="approval_decisions"
    )
    assessment = models.ForeignKey(
        DecisionAssessment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approval_decisions",
    )
    decision_status = models.CharField(max_length=30, choices=UseCase.DecisionStatus.choices)
    rationale = models.TextField()
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="approval_decisions",
    )
    governance_confirmed = models.BooleanField(default=False)
    conditions = models.TextField(blank=True)
    condition_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decision_conditions",
    )
    condition_due_date = models.DateField(null=True, blank=True)
    second_approval_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_second_approval_decisions",
    )
    second_approval_requested_at = models.DateTimeField(null=True, blank=True)
    second_approval_returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="returned_second_approval_decisions",
    )
    second_approval_returned_at = models.DateTimeField(null=True, blank=True)
    second_approval_return_reason = models.TextField(blank=True)
    second_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="second_approval_decisions",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.use_case.short_id} - {self.get_decision_status_display()}"

    @property
    def is_pending_second_approval(self) -> bool:
        return (
            self.decision_status == UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS
            and self.finalized_at is None
            and self.second_approval_returned_at is None
        )

    @property
    def is_returned_from_second_approval(self) -> bool:
        return self.second_approval_returned_at is not None

    @property
    def is_final(self) -> bool:
        return self.finalized_at is not None
