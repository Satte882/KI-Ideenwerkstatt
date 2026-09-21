from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from ki_radar.core.models import TimeStampedModel
from ki_radar.use_cases.models import UseCase


class GovernanceAssessment(TimeStampedModel):
    class Result(models.TextChoices):
        NO_FLAGS = "no_flags", "Keine besonderen Hinweise festgestellt"
        CLARIFICATION = "clarification", "Fachliche Klärung erforderlich"
        PRIVACY = "privacy", "Datenschutzprüfung erforderlich"
        SECURITY = "security", "Informationssicherheitsprüfung erforderlich"
        LEGAL = "legal", "Rechtliche Prüfung erforderlich"
        COMPLETED = "completed", "Prüfung abgeschlossen"

    use_case = models.ForeignKey(
        UseCase, on_delete=models.CASCADE, related_name="governance_assessments"
    )
    assessment_date = models.DateField()
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="governance_reviews",
    )
    basis_version = models.CharField(max_length=100)
    personal_data = models.BooleanField(default=False)
    employee_data = models.BooleanField(default=False)
    automated_person_assessment = models.BooleanField(default=False)
    influences_person_decisions = models.BooleanField(default=False)
    biometric_data = models.BooleanField(default=False)
    safety_critical = models.BooleanField(default=False)
    regulated_product = models.BooleanField(default=False)
    health_safety_rights_impact = models.BooleanField(default=False)
    external_ai_or_cloud = models.BooleanField(default=False)
    generated_external_content = models.BooleanField(default=False)
    human_oversight_planned = models.BooleanField(default=False)
    privacy_review_required = models.BooleanField(default=False)
    privacy_review_rationale = models.TextField(blank=True)
    security_review_required = models.BooleanField(default=False)
    security_review_rationale = models.TextField(blank=True)
    legal_review_required = models.BooleanField(default=False)
    legal_review_rationale = models.TextField(blank=True)
    result = models.CharField(max_length=30, choices=Result.choices)
    rationale = models.TextField(blank=True)
    evidence_url = models.URLField(blank=True)
    next_assessment_date = models.DateField(null=True, blank=True)
    history = HistoricalRecords(inherit=True)

    class Meta:
        ordering = ["-assessment_date", "-created_at"]

    def review_rationale(self, review_type: str) -> str:
        field_name = f"{review_type}_review_rationale"
        return (getattr(self, field_name, "") or self.rationale).strip()

    def __str__(self) -> str:
        return f"{self.use_case.short_id} - {self.assessment_date}"


class GovernanceReview(TimeStampedModel):
    class ReviewType(models.TextChoices):
        PRIVACY = "privacy", "Datenschutzprüfung"
        SECURITY = "security", "Informationssicherheitsprüfung"
        LEGAL = "legal", "Rechtsprüfung"

    class Status(models.TextChoices):
        OPEN = "open", "Offen"
        COMPLETED = "completed", "Abgeschlossen"
        NOT_RELEVANT = "not_relevant", "Nicht relevant"

    class Result(models.TextChoices):
        PASSED = "passed", "Bestanden"
        PASSED_WITH_CONDITIONS = "passed_with_conditions", "Bestanden mit Auflagen"
        FAILED = "failed", "Nicht bestanden"

    use_case = models.ForeignKey(
        UseCase,
        on_delete=models.CASCADE,
        related_name="governance_reviews",
    )
    screening = models.ForeignKey(
        GovernanceAssessment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="review_artifacts",
    )
    review_type = models.CharField(max_length=20, choices=ReviewType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
    )
    reviewed_at = models.DateField(default=timezone.localdate)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="completed_governance_reviews",
    )
    responsible_role = models.CharField(max_length=120, blank=True)
    result = models.CharField(
        max_length=30,
        choices=Result.choices,
        blank=True,
        default="",
    )
    rationale = models.TextField(blank=True)
    risks = models.TextField(blank=True)
    measures = models.TextField(blank=True)
    conditions = models.TextField(blank=True)
    evidence_url = models.URLField(blank=True)
    history = HistoricalRecords(inherit=True)

    class Meta:
        ordering = ["-created_at", "-reviewed_at"]

    def clean(self):
        super().clean()
        errors = {}
        result = self.result.strip()

        if self.screening_id and self.screening.use_case_id != self.use_case_id:
            errors["screening"] = "Screening und Prüfartefakt müssen zum selben Use Case gehören."

        if self.status == self.Status.OPEN:
            if result:
                errors["result"] = "Eine offene Prüfung darf noch kein Prüfergebnis enthalten."
        elif self.status == self.Status.NOT_RELEVANT:
            if result:
                errors["result"] = "Für 'Nicht relevant' darf kein Prüfergebnis gesetzt sein."
            if self.screening_id:
                required_field = f"{self.review_type}_review_required"
                if getattr(self.screening, required_field):
                    errors["status"] = (
                        "Eine laut Screening erforderliche Prüfung kann nicht als "
                        "'Nicht relevant' dokumentiert werden."
                    )
        elif self.status == self.Status.COMPLETED:
            if not result:
                errors["result"] = "Für eine abgeschlossene Prüfung ist ein Ergebnis erforderlich."
            if result == self.Result.PASSED_WITH_CONDITIONS and not self.conditions.strip():
                errors["conditions"] = "Auflagen müssen strukturiert dokumentiert werden."

        if errors:
            raise ValidationError(errors)

    @property
    def is_completed(self) -> bool:
        return self.status == self.Status.COMPLETED and self.result in {
            self.Result.PASSED,
            self.Result.PASSED_WITH_CONDITIONS,
        }

    @property
    def display_status(self) -> str:
        if self.status == self.Status.COMPLETED and self.result:
            return f"{self.get_status_display()} · {self.get_result_display()}"
        return self.get_status_display()

    def __str__(self) -> str:
        return f"{self.use_case.short_id} - {self.get_review_type_display()}"
