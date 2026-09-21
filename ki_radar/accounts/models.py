from django.contrib.auth.models import AbstractUser
from django.db import models

from ki_radar.core.models import TimeStampedModel


class BusinessUnit(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Organisationseinheit"
        verbose_name_plural = "Organisationseinheiten"

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    business_unit = models.ForeignKey(
        BusinessUnit, null=True, blank=True, on_delete=models.SET_NULL
    )
    job_function = models.CharField(max_length=150, blank=True)
    external_identity_id = models.CharField(max_length=255, blank=True)
    is_anonymized = models.BooleanField(default=False)
    anonymized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_display_name(self) -> str:
        if self.is_anonymized:
            return "Anonymisierter Benutzer"
        return self.get_full_name() or self.username


class PrivacyRequest(TimeStampedModel):
    class Status(models.TextChoices):
        RECEIVED = "received", "Eingegangen"
        REVIEW = "review", "In Prüfung"
        APPROVED = "approved", "Genehmigt"
        REJECTED = "rejected", "Abgelehnt"
        COMPLETED = "completed", "Umgesetzt"

    reference = models.CharField(max_length=50, unique=True)
    subject_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="privacy_requests"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    request_received_at = models.DateTimeField()
    decision_at = models.DateTimeField(null=True, blank=True)
    legal_basis_or_exception = models.TextField(blank=True)
    decision_notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-request_received_at"]

    def __str__(self) -> str:
        return self.reference
