from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from ki_radar.core.models import TimeStampedModel


class CaptureSession(TimeStampedModel):
    class CaptureType(models.TextChoices):
        VALUE_STREAM = "value_stream", "Value Stream"
        USE_CASE = "use_case", "Use Case"

    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        COMPLETED = "completed", "Abgeschlossen"
        DISCARDED = "discarded", "Verworfen"
        EXPIRED = "expired", "Abgelaufen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="capture_sessions",
    )
    capture_type = models.CharField(max_length=20, choices=CaptureType.choices, db_index=True)
    working_title = models.CharField(max_length=200, blank=True)
    catalog_version = models.CharField(max_length=20)
    schema_version = models.CharField(max_length=20)
    target_value_stream = models.ForeignKey(
        "architecture.ValueStream",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capture_sessions",
    )
    target_use_case = models.ForeignKey(
        "use_cases.UseCase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capture_sessions",
    )
    answers = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    revision = models.PositiveIntegerField(default=0)
    answered_required_count = models.PositiveSmallIntegerField(default=0)
    required_question_count = models.PositiveSmallIntegerField(default=0)
    active_entry_seconds = models.PositiveIntegerField(default=0)
    save_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    discarded_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(
                fields=["owner", "status", "capture_type"],
                name="capture_owner_status_type_idx",
            ),
            models.Index(
                fields=["owner", "-updated_at"],
                name="capture_owner_updated_idx",
            ),
            models.Index(
                fields=["status", "expires_at"],
                name="capture_status_expires_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        capture_type="value_stream",
                        target_use_case__isnull=True,
                    )
                    | models.Q(
                        capture_type="use_case",
                        target_value_stream__isnull=True,
                    )
                ),
                name="capture_target_matches_type",
            ),
        ]

    @property
    def progress_percent(self) -> int:
        if self.required_question_count == 0:
            return 0
        return round(self.answered_required_count / self.required_question_count * 100)

    @property
    def is_editable(self) -> bool:
        return self.status == self.Status.DRAFT

    @property
    def target_object(self):
        if self.capture_type == self.CaptureType.VALUE_STREAM:
            return self.target_value_stream
        if self.capture_type == self.CaptureType.USE_CASE:
            return self.target_use_case
        return None

    def __str__(self) -> str:
        label = self.working_title or self.get_capture_type_display()
        return f"{label} ({self.get_status_display()})"


class CaptureAnalysis(TimeStampedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "Läuft"
        SUCCESS = "success", "Erfolgreich"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        CaptureSession,
        on_delete=models.CASCADE,
        related_name="analyses",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capture_analyses",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )
    source_revision = models.PositiveIntegerField()
    source_hash = models.CharField(max_length=64)
    capture_type = models.CharField(max_length=20, choices=CaptureSession.CaptureType.choices)
    catalog_version = models.CharField(max_length=20)
    answer_schema_version = models.CharField(max_length=20)
    provider = models.CharField(max_length=50, default="openrouter")
    model_name = models.CharField(max_length=200, blank=True)
    prompt_version = models.CharField(max_length=20)
    extraction_schema_version = models.CharField(max_length=20)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    input_chars = models.PositiveIntegerField(default=0)
    output_chars = models.PositiveIntegerField(default=0)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    open_questions = models.JSONField(default=list, blank=True)
    contradictions = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["session", "status", "-created_at"],
                name="analysis_session_status_idx",
            ),
            models.Index(
                fields=["requested_by", "-created_at"],
                name="analysis_user_created_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "source_hash"],
                condition=models.Q(status="running"),
                name="uniq_running_analysis_source",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="running", finished_at__isnull=True)
                    | models.Q(status__in=["success", "failed"], finished_at__isnull=False)
                ),
                name="analysis_status_finished_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.session_id}: {self.get_status_display()}"


class CaptureFieldSuggestion(TimeStampedModel):
    class TargetObjectType(models.TextChoices):
        VALUE_STREAM = "value_stream", "Value Stream"
        VALUE_STREAM_STAGE = "value_stream_stage", "Value-Stream-Phase"
        PROCESS_ANALYSIS = "process_analysis", "Prozessanalyse"
        SOLUTION_OPTION = "solution_option", "Lösungsoption"
        USE_CASE = "use_case", "Use Case"

    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        TEXT_LIST = "text_list", "Textliste"
        INTEGER = "integer", "Ganzzahl"
        DECIMAL = "decimal", "Dezimalzahl"
        ENUM = "enum", "Auswahlliste"
        BOOLEAN = "boolean", "Boolean"
        DATE = "date", "Datum"
        UUID = "uuid", "UUID"
        REFERENCE = "reference", "Referenz"

    class Uncertainty(models.TextChoices):
        LOW = "low", "Niedrig"
        MEDIUM = "medium", "Mittel"
        HIGH = "high", "Hoch"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis = models.ForeignKey(
        CaptureAnalysis,
        on_delete=models.CASCADE,
        related_name="suggestions",
    )
    target_object_type = models.CharField(max_length=30, choices=TargetObjectType.choices)
    target_field = models.CharField(max_length=200)
    target_object_id = models.UUIDField(null=True, blank=True)
    target_group_key = models.SlugField(max_length=100, blank=True)
    field_type = models.CharField(max_length=20, choices=FieldType.choices)
    suggested_value = models.JSONField()
    source_question = models.CharField(max_length=100)
    source_excerpt = models.TextField()
    uncertainty = models.CharField(max_length=10, choices=Uncertainty.choices)
    uncertainty_reason = models.TextField()

    class Meta:
        ordering = ["target_object_type", "target_group_key", "target_field"]
        indexes = [
            models.Index(
                fields=["analysis", "target_object_type", "target_group_key"],
                name="suggest_analysis_target_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["analysis", "target_field", "target_group_key"],
                name="uniq_analysis_target_group",
            )
        ]

    def __str__(self) -> str:
        return f"{self.target_object_type}.{self.target_field}"


class FieldAdoptionCandidate(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Offen"
        PROCESSING = "processing", "In Bearbeitung"
        ADOPTED = "adopted", "Übernommen"
        ADOPTED_EDITED = "adopted_edited", "Bearbeitet übernommen"
        REJECTED = "rejected", "Verworfen"
        CONFLICT = "conflict", "Konflikt"
        SUPERSEDED = "superseded", "Ersetzt"
        STALE = "stale", "Veraltet"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    suggestion = models.OneToOneField(
        CaptureFieldSuggestion,
        on_delete=models.CASCADE,
        related_name="adoption_candidate",
    )
    target_object_type = models.CharField(
        max_length=30,
        choices=CaptureFieldSuggestion.TargetObjectType.choices,
    )
    target_object_id = models.UUIDField()
    target_field = models.CharField(max_length=200)
    proposed_value = models.TextField()
    previous_value = models.TextField(blank=True)
    previous_value_hash = models.CharField(max_length=64)
    target_updated_at = models.DateTimeField()
    source_revision = models.PositiveIntegerField()
    source_hash = models.CharField(max_length=64)
    catalog_version = models.CharField(max_length=20)
    answer_schema_version = models.CharField(max_length=20)
    prompt_version = models.CharField(max_length=20)
    extraction_schema_version = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    processing_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processing_field_adoption_candidates",
    )
    processing_started_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["target_object_type", "target_object_id", "target_field"]
        indexes = [
            models.Index(
                fields=["target_object_type", "target_object_id", "target_field"],
                name="adopt_candidate_target_idx",
            ),
            models.Index(
                fields=["status", "-created_at"],
                name="adopt_candidate_status_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["target_object_type", "target_object_id", "target_field"],
                condition=models.Q(status="open"),
                name="uniq_open_adoption_target_field",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="processing",
                        processing_by__isnull=False,
                        processing_started_at__isnull=False,
                        resolved_at__isnull=True,
                    )
                    | models.Q(
                        status="open",
                        processing_by__isnull=True,
                        processing_started_at__isnull=True,
                        resolved_at__isnull=True,
                    )
                    | models.Q(
                        status__in=[
                            "adopted",
                            "adopted_edited",
                            "rejected",
                            "conflict",
                            "superseded",
                            "stale",
                            "failed",
                        ],
                        resolved_at__isnull=False,
                    )
                ),
                name="adoption_candidate_state_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.target_object_type}.{self.target_field}@{self.target_object_id}"


class FieldAdoptionAudit(TimeStampedModel):
    class Action(models.TextChoices):
        ADOPT = "adopt", "Übernehmen"
        REJECT = "reject", "Verwerfen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(
        FieldAdoptionCandidate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    suggestion = models.ForeignKey(
        CaptureFieldSuggestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adoption_audit_events",
    )
    analysis = models.ForeignKey(
        CaptureAnalysis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adoption_audit_events",
    )
    session = models.ForeignKey(
        CaptureSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adoption_audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="field_adoption_audit_events",
    )
    candidate_id_snapshot = models.UUIDField(unique=True)
    suggestion_id_snapshot = models.UUIDField()
    analysis_id_snapshot = models.UUIDField(db_index=True)
    session_id_snapshot = models.UUIDField(db_index=True)
    actor_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    target_object_type = models.CharField(max_length=30)
    target_object_id = models.UUIDField()
    target_field = models.CharField(max_length=200)
    previous_value = models.TextField(blank=True)
    previous_value_hash = models.CharField(max_length=64)
    proposed_value = models.TextField(blank=True)
    edited_value = models.TextField(blank=True)
    current_value = models.TextField(blank=True)
    final_value = models.TextField(blank=True)
    action = models.CharField(max_length=20, choices=Action.choices)
    outcome = models.CharField(max_length=30)
    error_code = models.CharField(max_length=50, blank=True)
    target_updated_at_changed = models.BooleanField(default=False)
    source_question = models.CharField(max_length=100, blank=True)
    source_excerpt_hash = models.CharField(max_length=64, blank=True)
    provider = models.CharField(max_length=50, blank=True)
    model_name = models.CharField(max_length=200, blank=True)
    catalog_version = models.CharField(max_length=20)
    answer_schema_version = models.CharField(max_length=20)
    prompt_version = models.CharField(max_length=20)
    extraction_schema_version = models.CharField(max_length=20)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["target_object_type", "target_object_id", "target_field"],
                name="adopt_audit_target_idx",
            ),
            models.Index(
                fields=["outcome", "-created_at"],
                name="adopt_audit_outcome_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.action}:{self.outcome}:{self.candidate_id_snapshot}"


class SolutionGenerationRun(TimeStampedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "Läuft"
        SUCCESS = "success", "Erfolgreich"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    process_analysis = models.ForeignKey(
        "architecture.ProcessAnalysis",
        on_delete=models.CASCADE,
        related_name="solution_generation_runs",
    )
    process_version = models.PositiveIntegerField()
    source_hash = models.CharField(max_length=64)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solution_generation_runs",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )
    provider = models.CharField(max_length=50, default="openrouter")
    model_name = models.CharField(max_length=200, blank=True)
    prompt_version = models.CharField(max_length=20)
    generation_schema_version = models.CharField(max_length=20)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    input_chars = models.PositiveIntegerField(default=0)
    output_chars = models.PositiveIntegerField(default=0)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    preview_payload = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["process_analysis", "status", "-created_at"],
                name="solgen_process_status_idx",
            ),
            models.Index(
                fields=["requested_by", "-created_at"],
                name="solgen_user_created_idx",
            ),
            models.Index(fields=["expires_at"], name="solgen_expires_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["process_analysis"],
                condition=models.Q(status="running"),
                name="uniq_running_solution_generation",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="running", finished_at__isnull=True)
                    | models.Q(status__in=["success", "failed"], finished_at__isnull=False)
                ),
                name="solution_generation_status_finished_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.process_analysis_id}: {self.get_status_display()}"


class SolutionQualityRun(TimeStampedModel):
    class StepType(models.TextChoices):
        INITIAL_CRITIC = "initial_critic", "Initial Critic"
        REPAIR = "repair", "Repair"
        FINAL_CRITIC = "final_critic", "Final Critic"

    class Status(models.TextChoices):
        RUNNING = "running", "Läuft"
        SUCCESS = "success", "Erfolgreich"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    solution_generation_run = models.ForeignKey(
        SolutionGenerationRun,
        on_delete=models.CASCADE,
        related_name="quality_runs",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solution_quality_runs",
    )
    step_type = models.CharField(max_length=20, choices=StepType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )
    provider = models.CharField(max_length=50, default="openrouter")
    model_name = models.CharField(max_length=200, blank=True)
    prompt_version = models.CharField(max_length=20)
    output_schema_version = models.CharField(max_length=20)
    input_hash = models.CharField(max_length=64)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    input_chars = models.PositiveIntegerField(default=0)
    output_chars = models.PositiveIntegerField(default=0)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    result_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["solution_generation_run", "status", "-created_at"],
                name="solquality_run_status_idx",
            ),
            models.Index(
                fields=["requested_by", "-created_at"],
                name="solquality_user_created_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["solution_generation_run", "step_type"],
                name="uniq_solution_quality_step",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="running", finished_at__isnull=True)
                    | models.Q(status__in=["success", "failed"], finished_at__isnull=False)
                ),
                name="solution_quality_status_finished_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.solution_generation_run_id}:{self.step_type}:{self.status}"


class AcceleratorLLMQuota(TimeStampedModel):
    class Scope(models.TextChoices):
        CONTEXT = "context", "Kontext"
        USER = "user", "Benutzer"
        GLOBAL = "global", "Global"

    scope = models.CharField(max_length=20, choices=Scope.choices)
    quota_date = models.DateField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="accelerator_llm_quotas",
    )
    session = models.ForeignKey(
        CaptureSession,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="llm_quotas",
    )
    process_analysis = models.ForeignKey(
        "architecture.ProcessAnalysis",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="llm_quotas",
    )
    calls = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(
                fields=["scope", "quota_date"],
                name="accel_quota_scope_date_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        scope="global",
                        user__isnull=True,
                        session__isnull=True,
                        process_analysis__isnull=True,
                    )
                    | models.Q(
                        scope="user",
                        user__isnull=False,
                        session__isnull=True,
                        process_analysis__isnull=True,
                    )
                    | models.Q(
                        scope="context",
                        user__isnull=True,
                        session__isnull=False,
                        process_analysis__isnull=True,
                    )
                    | models.Q(
                        scope="context",
                        user__isnull=True,
                        session__isnull=True,
                        process_analysis__isnull=False,
                    )
                ),
                name="valid_accel_quota_scope_owner",
            ),
            models.UniqueConstraint(
                fields=["quota_date"],
                condition=models.Q(scope="global"),
                name="uniq_accel_quota_global_date",
            ),
            models.UniqueConstraint(
                fields=["user", "quota_date"],
                condition=models.Q(scope="user"),
                name="uniq_accel_quota_user_date",
            ),
            models.UniqueConstraint(
                fields=["session", "quota_date"],
                condition=models.Q(scope="context"),
                name="uniq_accel_quota_context_date",
            ),
            models.UniqueConstraint(
                fields=["process_analysis", "quota_date"],
                condition=models.Q(scope="context"),
                name="uniq_accel_quota_process_date",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.scope}:{self.quota_date}={self.calls}"
