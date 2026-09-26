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

    @property
    def product_display_name(self) -> str:
        """Hide benchmark-only A/B/C labels from the normal product surface."""
        normalized = " ".join(self.name.strip().casefold().replace("_", "-").split())
        benchmark_labels = {
            "a-fall",
            "b-fall",
            "c-fall",
            "fall a",
            "fall b",
            "fall c",
            "a fall",
            "b fall",
            "c fall",
        }
        if normalized in benchmark_labels:
            return f"Quellenbasis für „{self.process_analysis.name}“"
        return self.name

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


class InvestigationRun(TimeStampedModel):
    """Persistent technical VS1/2 run; not a fachlicher lifecycle status."""

    class Status(models.TextChoices):
        RUNNING = "running", "Läuft"
        WAITING_HUMAN = "waiting_human", "Wartet auf Klärung"
        READY = "ready", "Entscheidungsgrundlage bereit"
        ABORTED = "aborted", "Abgebrochen"
        FAILED = "failed", "Technisch fehlgeschlagen"

    ACTIVE_STATUSES = ("running", "waiting_human")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    process_analysis = models.ForeignKey(
        "architecture.ProcessAnalysis",
        on_delete=models.PROTECT,
        related_name="investigation_runs",
    )
    source_snapshot = models.ForeignKey(
        InvestigationSourceSnapshot,
        on_delete=models.PROTECT,
        related_name="investigation_runs",
    )
    evidence_campaign = models.ForeignKey(
        "accelerator.InvestigationEvidenceCampaign",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="investigation_runs",
    )
    execution_mode = models.CharField(max_length=20, default="adaptive")
    evidence_metadata = models.JSONField(default=dict, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="investigation_runs",
    )
    idempotency_key = models.CharField(max_length=64)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )
    process_version = models.PositiveIntegerField()
    decision_question = models.TextField()
    contract_hash = models.CharField(max_length=64)
    manifest_hash = models.CharField(max_length=64)
    policy_version = models.CharField(max_length=40)
    budget_version = models.CharField(max_length=40)
    loop_version = models.CharField(max_length=40)
    budget_limits = models.JSONField(default=dict)
    usage = models.JSONField(default=dict)
    execution_snapshot = models.JSONField(default=dict)
    claim_register = models.JSONField(default=list)
    source_relevance = models.JSONField(default=dict)
    register_revision = models.PositiveIntegerField(default=1)
    register_hash = models.CharField(max_length=64)
    brief_payload = models.JSONField(default=dict)
    brief_revision = models.PositiveIntegerField(default=1)
    brief_hash = models.CharField(max_length=64)
    data_check_executed = models.BooleanField(default=False)
    counterevidence_search_executed = models.BooleanField(default=False)
    counterevidence_hits_processed = models.BooleanField(default=False)
    source_relevance_complete = models.BooleanField(default=False)
    no_progress_streak = models.PositiveSmallIntegerField(default=0)
    repair_cycles = models.PositiveSmallIntegerField(default=0)
    executor_token = models.UUIDField(default=uuid.uuid4, editable=False)
    executor_generation = models.PositiveIntegerField(default=1)
    clarification_reason = models.CharField(max_length=40, blank=True)
    clarification_payload = models.JSONField(default=dict)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_progress_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["process_analysis", "status", "-created_at"],
                name="invrun_process_status_idx",
            ),
            models.Index(
                fields=["source_snapshot", "-created_at"],
                name="invrun_snapshot_created_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["process_analysis"],
                condition=models.Q(
                    status__in=["running", "waiting_human"],
                    evidence_campaign__isnull=True,
                ),
                name="uniq_active_product_run",
            ),
            models.UniqueConstraint(
                fields=["process_analysis"],
                condition=models.Q(
                    status__in=["running", "waiting_human"],
                    evidence_campaign__isnull=False,
                ),
                name="uniq_active_evidence_run",
            ),
            models.UniqueConstraint(
                fields=["process_analysis", "idempotency_key"],
                name="uniq_investigation_start_key",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status__in=["running", "waiting_human"], finished_at__isnull=True)
                    | models.Q(status__in=["ready", "aborted", "failed"], finished_at__isnull=False)
                ),
                name="investigation_run_finished_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            immutable_fields = (
                "process_analysis_id",
                "source_snapshot_id",
                "evidence_campaign_id",
                "execution_mode",
                "evidence_metadata",
                "idempotency_key",
                "process_version",
                "decision_question",
                "contract_hash",
                "manifest_hash",
                "policy_version",
                "budget_version",
                "loop_version",
                "budget_limits",
                "execution_snapshot",
            )
            current = type(self).objects.filter(pk=self.pk).values(*immutable_fields).first()
            if current and any(current[name] != getattr(self, name) for name in immutable_fields):
                raise ValidationError(
                    "Der Ausführungssnapshot eines Investigation-Runs ist unveränderlich."
                )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.process_analysis_id}:{self.status}:{self.id}"


class InvestigationStep(TimeStampedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "Läuft"
        SUCCESS = "success", "Erfolgreich"
        FAILED = "failed", "Fehlgeschlagen"
        DISCARDED = "discarded", "Verworfen"

    class ProgressKind(models.TextChoices):
        NONE = "none", "Kein Erkenntnisfortschritt"
        EVIDENCE = "evidence", "Neuer Beleg"
        REFUTATION = "refutation", "Begründeter Ausschluss"
        CONTRADICTION = "contradiction", "Neuer Widerspruch"
        COVERAGE = "coverage", "Neue begründete Abdeckung"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        InvestigationRun,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    sequence = models.PositiveIntegerField()
    step_key = models.CharField(max_length=64)
    target_claim_id = models.CharField(max_length=100, blank=True)
    expected_discriminating_finding = models.TextField(blank=True)
    tool_name = models.CharField(max_length=40)
    parameters = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )
    attempts = models.PositiveSmallIntegerField(default=1)
    executor_generation = models.PositiveIntegerField()
    result_payload = models.JSONField(default=dict)
    result_hash = models.CharField(max_length=64, blank=True)
    result_ref = models.JSONField(default=dict)
    progress_kind = models.CharField(
        max_length=20,
        choices=ProgressKind.choices,
        default=ProgressKind.NONE,
    )
    progress_payload = models.JSONField(default=dict)
    error_code = models.CharField(max_length=50, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["run", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "sequence"],
                name="uniq_investigation_step_sequence",
            ),
            models.UniqueConstraint(
                fields=["run", "step_key"],
                name="uniq_investigation_step_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.sequence}:{self.tool_name}"


class InvestigationModelCall(TimeStampedModel):
    class Role(models.TextChoices):
        PLANNER = "planner", "Planner"
        SYNTHESIZER = "synthesizer", "Synthesizer"
        VERIFIER = "verifier", "Verifier"

    class Status(models.TextChoices):
        RUNNING = "running", "Läuft"
        SUCCESS = "success", "Erfolgreich"
        FAILED = "failed", "Fehlgeschlagen"
        DISCARDED = "discarded", "Verworfen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        InvestigationRun,
        on_delete=models.CASCADE,
        related_name="model_calls",
    )
    step = models.ForeignKey(
        InvestigationStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="model_calls",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    attempt = models.PositiveSmallIntegerField(default=1)
    executor_generation = models.PositiveIntegerField()
    requested_provider = models.CharField(max_length=50, default="openrouter")
    requested_model = models.CharField(max_length=200, blank=True)
    returned_model = models.CharField(max_length=200, blank=True)
    model_revision = models.CharField(max_length=200, blank=True)
    effective_parameters = models.JSONField(default=dict)
    provider_attempt_id = models.CharField(max_length=200, blank=True)
    prompt_version = models.CharField(max_length=40)
    prompt_hash = models.CharField(max_length=64)
    instruction_template = models.TextField()
    schema_version = models.CharField(max_length=40)
    context_refs = models.JSONField(default=dict)
    accepted_payload = models.JSONField(default=dict)
    accepted_payload_hash = models.CharField(max_length=64, blank=True)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["run", "created_at"]
        indexes = [
            models.Index(
                fields=["run", "role", "created_at"],
                name="invmodel_run_role_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.role}:{self.id}"


class InvestigationVerifierReport(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        InvestigationRun,
        on_delete=models.CASCADE,
        related_name="verifier_reports",
    )
    revision = models.PositiveIntegerField()
    model_call = models.OneToOneField(
        InvestigationModelCall,
        on_delete=models.PROTECT,
        related_name="verifier_report",
    )
    success = models.BooleanField(default=False)
    findings = models.JSONField(default=list)
    critical_findings = models.PositiveIntegerField(default=0)
    source_references_valid = models.BooleanField(default=False)
    checked_critical_claims = models.JSONField(default=list)
    bound_hashes = models.JSONField(default=dict)
    created_for_executor_generation = models.PositiveIntegerField()

    class Meta:
        ordering = ["run", "-revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "revision"],
                name="uniq_investigation_verifier_revision",
            )
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:verifier:{self.revision}"


class InvestigationInputRevision(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        InvestigationRun,
        on_delete=models.CASCADE,
        related_name="input_revisions",
    )
    revision = models.PositiveIntegerField()
    supplied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="investigation_input_revisions",
    )
    payload = models.JSONField(default=dict)
    payload_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["run", "revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "revision"],
                name="uniq_investigation_input_revision",
            )
        ]


class InvestigationBriefRevision(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        InvestigationRun,
        on_delete=models.CASCADE,
        related_name="brief_revisions",
    )
    revision = models.PositiveIntegerField()
    payload = models.JSONField(default=dict)
    content_hash = models.CharField(max_length=64)
    operation_key = models.CharField(max_length=64)
    process_version = models.PositiveIntegerField()

    class Meta:
        ordering = ["run", "revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "revision"],
                name="uniq_investigation_brief_revision",
            ),
            models.UniqueConstraint(
                fields=["run", "operation_key"],
                name="uniq_investigation_brief_operation",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Materialisierte Briefrevisionen sind unveränderlich.")
        super().save(*args, **kwargs)


class InvestigationEvidenceCampaign(TimeStampedModel):
    """Technical VS1/3 evidence budget shared across all benchmark attempts."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    process_analysis = models.ForeignKey(
        "architecture.ProcessAnalysis",
        on_delete=models.PROTECT,
        related_name="investigation_evidence_campaigns",
    )
    campaign_key = models.CharField(max_length=64, unique=True)
    revision = models.PositiveIntegerField(default=1)
    limits = models.JSONField(default=dict)
    usage = models.JSONField(default=dict)
    pricing = models.JSONField(default=dict, blank=True)
    currency = models.CharField(max_length=8, blank=True)
    pricing_version = models.CharField(max_length=80, blank=True)
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authorized_investigation_evidence_campaigns",
    )
    authorized_at = models.DateTimeField(default=timezone.now)
    continuation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.campaign_key}:v{self.revision}"


class InvestigationEvidenceBudgetRevision(TimeStampedModel):
    """Immutable authorization history for evidence-budget changes."""

    objects = ImmutableEvidenceManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        InvestigationEvidenceCampaign,
        on_delete=models.PROTECT,
        related_name="budget_revisions",
    )
    revision = models.PositiveIntegerField()
    limits = models.JSONField(default=dict)
    pricing = models.JSONField(default=dict, blank=True)
    currency = models.CharField(max_length=8, blank=True)
    pricing_version = models.CharField(max_length=80, blank=True)
    usage_at_authorization = models.JSONField(default=dict)
    reason = models.TextField()
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="investigation_evidence_budget_revisions",
    )
    authorized_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["campaign", "revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "revision"],
                name="uniq_investigation_budget_revision",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Budgetrevisionen sind nach der Autorisierung unveränderlich.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Budgetrevisionen sind unveränderlich.")


class InvestigationProviderReservation(TimeStampedModel):
    """Atomic campaign reservation for one real provider attempt."""

    class Status(models.TextChoices):
        OPEN = "open", "Reserviert"
        SETTLED = "settled", "Abgerechnet"
        UNCERTAIN = "uncertain", "Verbrauch unklar"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        InvestigationEvidenceCampaign,
        on_delete=models.PROTECT,
        related_name="provider_reservations",
    )
    run = models.ForeignKey(
        InvestigationRun,
        on_delete=models.PROTECT,
        related_name="provider_reservations",
    )
    model_call = models.OneToOneField(
        InvestigationModelCall,
        on_delete=models.PROTECT,
        related_name="evidence_reservation",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    reserved_input_tokens = models.PositiveIntegerField()
    reserved_output_tokens = models.PositiveIntegerField()
    reserved_cost_microunits = models.PositiveBigIntegerField(null=True, blank=True)
    actual_input_tokens = models.PositiveIntegerField(null=True, blank=True)
    actual_output_tokens = models.PositiveIntegerField(null=True, blank=True)
    actual_cost_microunits = models.PositiveBigIntegerField(null=True, blank=True)
    uncertainty_reason = models.CharField(max_length=80, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["campaign", "created_at"]


class InvestigationMaterialization(TimeStampedModel):
    """Audit record for conflict-safe materialization into existing domain objects."""

    class Outcome(models.TextChoices):
        APPLIED = "applied", "Übernommen"
        CONFLICT = "conflict", "Differenz erkannt"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        InvestigationRun,
        on_delete=models.PROTECT,
        related_name="materializations",
    )
    brief_revision = models.OneToOneField(
        InvestigationBriefRevision,
        on_delete=models.PROTECT,
        related_name="materialization",
    )
    operation_key = models.CharField(max_length=64)
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    base_domain_hash = models.CharField(max_length=64)
    resulting_domain_hash = models.CharField(max_length=64, blank=True)
    applied_fields = models.JSONField(default=dict)
    created_solution_option_ids = models.JSONField(default=list)
    updated_solution_option_ids = models.JSONField(default=list)
    conflicts = models.JSONField(default=list)
    materialized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="investigation_materializations",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "operation_key"],
                name="uniq_investigation_materialization_operation",
            )
        ]
