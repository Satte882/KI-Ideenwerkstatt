from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from ki_radar.core.models import TimeStampedModel
from ki_radar.use_cases.models import UseCase


class EvidenceLink(TimeStampedModel):
    class DocumentType(models.TextChoices):
        PROJECT = "project", "Projektauftrag"
        PRIVACY = "privacy", "Datenschutzbewertung"
        SECURITY = "security", "Informationssicherheitsbewertung"
        LEGAL = "legal", "Rechtsbewertung"
        TECHNICAL = "technical", "Technische Dokumentation"
        PILOT = "pilot", "Pilotbericht"
        OPERATIONS = "operations", "Betriebsdokumentation"
        CONTRACT = "contract", "Lieferantenvertrag"
        COST = "cost", "Kostenrechnung"
        DECISION = "decision", "Entscheidungsvorlage"
        OTHER = "other", "Sonstiger Nachweis"

    use_case = models.ForeignKey(UseCase, on_delete=models.CASCADE, related_name="evidence_links")
    label = models.CharField(max_length=200)
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    url = models.URLField(max_length=1000)
    version = models.CharField(max_length=100, blank=True)
    comment = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_evidence_links",
    )
    history = HistoricalRecords(inherit=True)

    def __str__(self) -> str:
        return self.label


class NotificationLog(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Ausstehend"
        SENT = "sent", "Versendet"
        FAILED = "failed", "Fehlgeschlagen"
        SKIPPED = "skipped", "Übersprungen"

    use_case = models.ForeignKey(
        UseCase, null=True, blank=True, on_delete=models.SET_NULL, related_name="notification_logs"
    )
    notification_type = models.CharField(max_length=100)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    recipient_label = models.CharField(max_length=200, blank=True)
    recipient_email = models.EmailField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    review_due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["-created_at"]
