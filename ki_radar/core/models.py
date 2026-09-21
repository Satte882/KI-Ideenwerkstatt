import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SystemJobRun(TimeStampedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "Läuft"
        SUCCESS = "success", "Erfolgreich"
        FAILED = "failed", "Fehlgeschlagen"

    job_name = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    exit_code = models.IntegerField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["job_name", "-started_at"])]

    def __str__(self) -> str:
        return f"{self.job_name}: {self.status} ({self.started_at:%Y-%m-%d %H:%M})"


class LLMTaskRun(TimeStampedModel):
    class TaskType(models.TextChoices):
        DELIVERY_FIELD_DRAFT = "delivery_field_draft", "Delivery-Feldentwurf"
        ORIGIN_CONSISTENCY_REVIEW = (
            "origin_consistency_review",
            "Herkunfts-Konsistenzprüfung",
        )

    class Status(models.TextChoices):
        RUNNING = "running", "Läuft"
        SUCCESS = "success", "Erfolgreich"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_type = models.CharField(max_length=40, choices=TaskType.choices, db_index=True)
    object_type = models.CharField(max_length=50)
    object_id = models.CharField(max_length=64)
    field_key = models.CharField(max_length=100, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="llm_task_runs",
    )
    source_hash = models.CharField(max_length=64)
    prompt_version = models.CharField(max_length=20)
    schema_version = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )
    provider = models.CharField(max_length=50, default="openrouter")
    model_name = models.CharField(max_length=200, blank=True)
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
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["task_type", "status", "-created_at"],
                name="llm_task_run_task_status_idx",
            ),
            models.Index(
                fields=["object_type", "object_id", "field_key"],
                name="llm_task_run_object_idx",
            ),
            models.Index(fields=["expires_at"], name="llm_task_run_expires_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(status="running", finished_at__isnull=True)
                    | models.Q(status__in=["success", "failed"], finished_at__isnull=False)
                ),
                name="llm_task_run_status_finished",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.task_type}:{self.object_type}:{self.object_id}"


class LLMTaskQuota(TimeStampedModel):
    class Scope(models.TextChoices):
        CONTEXT = "context", "Kontext"
        USER = "user", "Benutzer"
        GLOBAL = "global", "Global"

    scope = models.CharField(max_length=20, choices=Scope.choices)
    quota_date = models.DateField()
    task_type = models.CharField(max_length=40, choices=LLMTaskRun.TaskType.choices, blank=True)
    object_type = models.CharField(max_length=50, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    field_key = models.CharField(max_length=100, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="llm_task_quotas",
    )
    calls = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(
                fields=["scope", "quota_date"],
                name="llm_task_quota_scope_date_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        scope="global",
                        user__isnull=True,
                        task_type="",
                        object_type="",
                        object_id="",
                        field_key="",
                    )
                    | models.Q(
                        scope="user",
                        user__isnull=False,
                        task_type="",
                        object_type="",
                        object_id="",
                        field_key="",
                    )
                    | (
                        models.Q(scope="context", user__isnull=True)
                        & ~models.Q(task_type="")
                        & ~models.Q(object_type="")
                        & ~models.Q(object_id="")
                    )
                ),
                name="llm_task_quota_scope_subject",
            ),
            models.UniqueConstraint(
                fields=["quota_date"],
                condition=models.Q(scope="global"),
                name="uniq_llm_task_quota_global",
            ),
            models.UniqueConstraint(
                fields=["user", "quota_date"],
                condition=models.Q(scope="user"),
                name="uniq_llm_task_quota_user",
            ),
            models.UniqueConstraint(
                fields=[
                    "task_type",
                    "object_type",
                    "object_id",
                    "field_key",
                    "quota_date",
                ],
                condition=models.Q(scope="context"),
                name="uniq_llm_task_quota_context",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.scope}:{self.quota_date}={self.calls}"
