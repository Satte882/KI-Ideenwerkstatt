from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from ki_radar.core.models import TimeStampedModel

from .models import CaptureAnalysis, CaptureSession

_SHA256_VALIDATOR = RegexValidator(
    regex=r"^[0-9a-f]{64}$",
    message="Der Wert muss ein kleingeschriebener SHA-256-Hash sein.",
)


class StructuredAdoptionBatch(TimeStampedModel):
    class TargetObjectType(models.TextChoices):
        VALUE_STREAM = "value_stream", "Value Stream"
        USE_CASE = "use_case", "Use Case"

    class Status(models.TextChoices):
        OPEN = "open", "Offen"
        PROCESSING = "processing", "In Bearbeitung"
        COMMITTED = "committed", "Übernommen"
        REJECTED = "rejected", "Verworfen"
        CONFLICT = "conflict", "Konflikt"
        STALE = "stale", "Veraltet"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        CaptureSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="structured_adoption_batches",
    )
    analysis = models.ForeignKey(
        CaptureAnalysis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="structured_adoption_batches",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_structured_adoption_batches",
    )
    processing_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processing_structured_adoption_batches",
    )
    session_id_snapshot = models.UUIDField(db_index=True)
    analysis_id_snapshot = models.UUIDField(db_index=True)
    actor_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    target_object_type = models.CharField(max_length=20, choices=TargetObjectType.choices)
    target_object_id = models.UUIDField()
    source_revision = models.PositiveIntegerField()
    interpretation_version = models.CharField(max_length=20)
    idempotency_key = models.CharField(
        max_length=64,
        unique=True,
        validators=[_SHA256_VALIDATOR],
    )
    selected_graph_hash = models.CharField(
        max_length=64,
        validators=[_SHA256_VALIDATOR],
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    decision_snapshot = models.JSONField(default=dict, blank=True)
    result_snapshot = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    retention_until = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["target_object_type", "target_object_id", "status"],
                name="structured_batch_target_idx",
            ),
            models.Index(
                fields=["session_id_snapshot", "-created_at"],
                name="structured_batch_session_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="open",
                        processing_by__isnull=True,
                        processing_started_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | models.Q(
                        status="processing",
                        processing_by__isnull=False,
                        processing_started_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | models.Q(
                        status__in=[
                            "committed",
                            "rejected",
                            "conflict",
                            "stale",
                            "failed",
                        ],
                        completed_at__isnull=False,
                    )
                ),
                name="structured_batch_state_valid",
            )
        ]

    def __str__(self) -> str:
        return f"{self.target_object_type}@{self.target_object_id}:{self.status}"


class StructuredAdoptionItem(TimeStampedModel):
    class CandidateKind(models.TextChoices):
        METRIC_SET = "metric_set", "Metrikgruppe"
        VALUE_STREAM_STAGE = "value_stream_stage", "Value-Stream-Phase"
        PROCESS_ANALYSIS = "process_analysis", "Prozessanalyse"

    class Status(models.TextChoices):
        OPEN = "open", "Offen"
        CONFIRMED = "confirmed", "Bestätigt"
        REJECTED = "rejected", "Verworfen"
        AMBIGUOUS = "ambiguous", "Unklar"
        INVALID = "invalid", "Ungültig"
        DEPENDENCY_INVALID = "dependency_invalid", "Abhängigkeit ungültig"
        CONFLICT = "conflict", "Konflikt"
        STALE = "stale", "Veraltet"
        ADOPTED = "adopted", "Übernommen"
        FAILED = "failed", "Fehlgeschlagen"

    class Decision(models.TextChoices):
        PENDING = "pending", "Ausstehend"
        CONFIRMED_PROPOSAL = "confirmed_proposal", "Vorschlag bestätigt"
        CONFIRMED_EDITED = "confirmed_edited", "Bearbeitung bestätigt"
        CURRENT_DATABASE = "current_database", "Aktueller Datenbankwert"
        REJECTED = "rejected", "Verworfen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        StructuredAdoptionBatch,
        on_delete=models.CASCADE,
        related_name="items",
    )
    local_key = models.SlugField(max_length=100)
    candidate_kind = models.CharField(max_length=30, choices=CandidateKind.choices)
    target_path = models.CharField(max_length=200, blank=True)
    target_group_key = models.SlugField(max_length=100, blank=True)
    depends_on = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dependents",
    )
    dependency_key_snapshot = models.SlugField(max_length=100, blank=True)
    proposed_snapshot = models.JSONField(default=dict, blank=True)
    interpretation_snapshot = models.JSONField(default=dict, blank=True)
    decision_snapshot = models.JSONField(default=dict, blank=True)
    field_snapshot = models.JSONField(default=dict, blank=True)
    source_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    decision = models.CharField(
        max_length=30,
        choices=Decision.choices,
        default=Decision.PENDING,
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_structured_adoption_items",
    )
    confirmed_by_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_object_id = models.UUIDField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["batch", "local_key"]
        indexes = [
            models.Index(
                fields=["batch", "candidate_kind", "status"],
                name="structured_item_kind_idx",
            ),
            models.Index(
                fields=["batch", "target_path"],
                name="structured_item_path_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "local_key"],
                name="uniq_structured_item_local_key",
            )
        ]

    def clean(self):
        super().clean()
        if self.depends_on_id is None:
            return
        if self.depends_on.batch_id != self.batch_id:
            raise ValidationError({"depends_on": "Die Abhängigkeit muss zum selben Batch gehören."})
        if self.dependency_key_snapshot and (
            self.dependency_key_snapshot != self.depends_on.local_key
        ):
            raise ValidationError(
                {"dependency_key_snapshot": "Der Abhängigkeitsschlüssel passt nicht zum Item."}
            )

    def __str__(self) -> str:
        return f"{self.batch_id}:{self.local_key}:{self.status}"


class StructuredAdoptionAudit(TimeStampedModel):
    class Event(models.TextChoices):
        CREATED = "created", "Erstellt"
        CONFIRMED = "confirmed", "Bestätigt"
        REJECTED = "rejected", "Verworfen"
        COMMITTED = "committed", "Übernommen"
        CONFLICT = "conflict", "Konflikt"
        FAILED = "failed", "Fehlgeschlagen"
        RETAINED = "retained", "Aufbewahrt"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        StructuredAdoptionBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    item = models.ForeignKey(
        StructuredAdoptionItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="structured_adoption_audit_events",
    )
    batch_id_snapshot = models.UUIDField(db_index=True)
    item_id_snapshot = models.UUIDField(null=True, blank=True)
    session_id_snapshot = models.UUIDField(db_index=True)
    analysis_id_snapshot = models.UUIDField(db_index=True)
    actor_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    target_object_type = models.CharField(max_length=20)
    target_object_id = models.UUIDField()
    idempotency_key = models.CharField(max_length=64, validators=[_SHA256_VALIDATOR])
    attempt_count = models.PositiveSmallIntegerField(default=0)
    event = models.CharField(max_length=20, choices=Event.choices)
    outcome = models.CharField(max_length=30)
    step = models.CharField(max_length=50, blank=True)
    item_kind = models.CharField(max_length=30, blank=True)
    item_local_key = models.SlugField(max_length=100, blank=True)
    target_field = models.CharField(max_length=200, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["batch_id_snapshot", "-created_at"],
                name="structured_audit_batch_idx",
            ),
            models.Index(
                fields=["event", "outcome", "-created_at"],
                name="structured_audit_event_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event}:{self.outcome}:{self.batch_id_snapshot}"
