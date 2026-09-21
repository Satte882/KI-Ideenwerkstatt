from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from ki_radar.core.models import TimeStampedModel


class ImmutableEvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Eingefrorene Evidenz ist unveränderlich.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Eingefrorene Evidenz ist unveränderlich.")

    def delete(self):
        raise ValidationError("Eingefrorene Evidenz ist unveränderlich.")


class ImmutableEvidenceManager(models.Manager.from_queryset(ImmutableEvidenceQuerySet)):
    pass


class InvestigationSourceFolder(TimeStampedModel):
    """Administratively registered, case-bound source folder."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    process_analysis = models.ForeignKey(
        "architecture.ProcessAnalysis",
        on_delete=models.PROTECT,
        related_name="investigation_source_folders",
    )
    name = models.CharField(max_length=200)
    root_path = models.TextField()
    is_active = models.BooleanField(default=True, db_index=True)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registered_investigation_source_folders",
    )

    class Meta:
        ordering = ["process_analysis_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["process_analysis", "root_path"],
                name="uniq_investigation_folder_process_path",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            current = (
                type(self)
                .objects.filter(pk=self.pk)
                .values(
                    "process_analysis_id",
                    "root_path",
                )
                .first()
            )
            if current and self.snapshots.exists():
                if current["process_analysis_id"] != self.process_analysis_id:
                    raise ValidationError(
                        "Der Fallbezug eines verwendeten Quellenordners ist unveränderlich."
                    )
                if current["root_path"] != self.root_path:
                    raise ValidationError(
                        "Der Pfad eines verwendeten Quellenordners ist unveränderlich."
                    )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.process_analysis_id}: {self.name}"


class InvestigationSourceSnapshot(TimeStampedModel):
    """Immutable authorization, process-context and source-manifest revision."""

    objects = ImmutableEvidenceManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folder = models.ForeignKey(
        InvestigationSourceFolder,
        on_delete=models.PROTECT,
        related_name="snapshots",
    )
    process_analysis = models.ForeignKey(
        "architecture.ProcessAnalysis",
        on_delete=models.PROTECT,
        related_name="investigation_source_snapshots",
    )
    revision = models.PositiveIntegerField()
    process_version = models.PositiveIntegerField()
    decision_question = models.TextField()
    run_limits = models.JSONField(default=dict)
    process_context = models.JSONField(default=dict)
    manifest_hash = models.CharField(max_length=64)
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="captured_investigation_source_snapshots",
    )
    captured_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["process_analysis_id", "-revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["folder", "revision"],
                name="uniq_investigation_folder_revision",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Quellen-Snapshots sind nach der Erzeugung unveränderlich.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Quellen-Snapshots sind unveränderlich und nicht direkt löschbar.")

    def __str__(self) -> str:
        return f"{self.process_analysis_id}: Quellenrevision {self.revision}"


class InvestigationSource(TimeStampedModel):
    objects = ImmutableEvidenceManager()

    class SourceType(models.TextChoices):
        TEXT = "txt", "TXT"
        MARKDOWN = "md", "Markdown"
        CSV = "csv", "CSV"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(
        InvestigationSourceSnapshot,
        on_delete=models.CASCADE,
        related_name="sources",
    )
    filename = models.CharField(max_length=255)
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    size_bytes = models.PositiveIntegerField()
    content_sha256 = models.CharField(max_length=64, db_index=True)
    captured_mtime = models.DateTimeField(null=True, blank=True)
    content = models.TextField()
    row_count = models.PositiveIntegerField(null=True, blank=True)
    column_count = models.PositiveSmallIntegerField(null=True, blank=True)
    columns = models.JSONField(default=list, blank=True)
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="duplicate_sources",
    )

    class Meta:
        ordering = ["filename", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "filename"],
                name="uniq_investigation_snapshot_filename",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Eingefrorene Quellen sind nach der Erzeugung unveränderlich.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Eingefrorene Quellen sind unveränderlich und nicht direkt löschbar.")

    def __str__(self) -> str:
        return f"{self.filename}@{self.snapshot_id}"


class InvestigationToolResult(TimeStampedModel):
    objects = ImmutableEvidenceManager()

    class ToolName(models.TextChoices):
        PROFILE_CSV = "profile_csv", "CSV profilieren"
        COMPARE_GROUPS = "compare_groups", "Gruppen vergleichen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(
        InvestigationSourceSnapshot,
        on_delete=models.CASCADE,
        related_name="tool_results",
    )
    source = models.ForeignKey(
        InvestigationSource,
        on_delete=models.PROTECT,
        related_name="tool_results",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="investigation_tool_results",
    )
    tool_name = models.CharField(max_length=30, choices=ToolName.choices)
    tool_version = models.CharField(max_length=30)
    source_hash = models.CharField(max_length=64)
    parameters = models.JSONField(default=dict)
    result_payload = models.JSONField(default=dict)
    population = models.JSONField(default=dict)
    excluded_rows = models.JSONField(default=list)
    group_sizes = models.JSONField(default=dict)
    missing_values = models.JSONField(default=dict)
    units = models.JSONField(default=dict)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["snapshot", "tool_name", "created_at"],
                name="invtool_snapshot_tool_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Werkzeugresultate sind nach der Erzeugung unveränderlich.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Werkzeugresultate sind unveränderlich und nicht direkt löschbar.")

    def __str__(self) -> str:
        return f"{self.tool_name}:{self.id}"
