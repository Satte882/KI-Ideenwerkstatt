# Generated for VS1/2 adaptive investigation

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accelerator", "0011_investigation_source_tools"),
        ("architecture", "0020_solutionoption_work_design_origin"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InvestigationRun",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Läuft"),
                            ("waiting_human", "Wartet auf Klärung"),
                            ("ready", "Entscheidungsgrundlage bereit"),
                            ("aborted", "Abgebrochen"),
                            ("failed", "Technisch fehlgeschlagen"),
                        ],
                        db_index=True,
                        default="running",
                        max_length=20,
                    ),
                ),
                ("idempotency_key", models.CharField(max_length=64)),
                ("process_version", models.PositiveIntegerField()),
                ("decision_question", models.TextField()),
                ("contract_hash", models.CharField(max_length=64)),
                ("manifest_hash", models.CharField(max_length=64)),
                ("policy_version", models.CharField(max_length=40)),
                ("budget_version", models.CharField(max_length=40)),
                ("loop_version", models.CharField(max_length=40)),
                ("budget_limits", models.JSONField(default=dict)),
                ("usage", models.JSONField(default=dict)),
                ("execution_snapshot", models.JSONField(default=dict)),
                ("claim_register", models.JSONField(default=list)),
                ("register_revision", models.PositiveIntegerField(default=1)),
                ("register_hash", models.CharField(max_length=64)),
                ("brief_payload", models.JSONField(default=dict)),
                ("brief_revision", models.PositiveIntegerField(default=1)),
                ("brief_hash", models.CharField(max_length=64)),
                ("data_check_executed", models.BooleanField(default=False)),
                ("counterevidence_search_executed", models.BooleanField(default=False)),
                ("counterevidence_hits_processed", models.BooleanField(default=False)),
                ("source_relevance_complete", models.BooleanField(default=False)),
                ("no_progress_streak", models.PositiveSmallIntegerField(default=0)),
                ("repair_cycles", models.PositiveSmallIntegerField(default=0)),
                ("executor_token", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("executor_generation", models.PositiveIntegerField(default=1)),
                ("clarification_reason", models.CharField(blank=True, max_length=40)),
                ("clarification_payload", models.JSONField(default=dict)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("last_progress_at", models.DateTimeField(blank=True, null=True)),
                (
                    "process_analysis",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="investigation_runs",
                        to="architecture.processanalysis",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="investigation_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source_snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="investigation_runs",
                        to="accelerator.investigationsourcesnapshot",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="investigationrun",
            index=models.Index(
                fields=["process_analysis", "status", "-created_at"],
                name="invrun_process_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="investigationrun",
            index=models.Index(
                fields=["source_snapshot", "-created_at"],
                name="invrun_snapshot_created_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="investigationrun",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ["running", "waiting_human"])),
                fields=("process_analysis",),
                name="uniq_active_investigation_run",
            ),
        ),
        migrations.AddConstraint(
            model_name="investigationrun",
            constraint=models.UniqueConstraint(
                fields=("process_analysis", "idempotency_key"),
                name="uniq_investigation_start_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="investigationrun",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("finished_at__isnull", True), ("status__in", ["running", "waiting_human"]))
                    | models.Q(("finished_at__isnull", False), ("status__in", ["ready", "aborted", "failed"]))
                ),
                name="investigation_run_finished_valid",
            ),
        ),
        migrations.CreateModel(
            name="InvestigationStep",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sequence", models.PositiveIntegerField()),
                ("step_key", models.CharField(max_length=64)),
                ("target_claim_id", models.CharField(blank=True, max_length=100)),
                ("expected_discriminating_finding", models.TextField(blank=True)),
                ("tool_name", models.CharField(max_length=40)),
                ("parameters", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Läuft"),
                            ("success", "Erfolgreich"),
                            ("failed", "Fehlgeschlagen"),
                            ("discarded", "Verworfen"),
                        ],
                        db_index=True,
                        default="running",
                        max_length=20,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=1)),
                ("executor_generation", models.PositiveIntegerField()),
                ("result_payload", models.JSONField(default=dict)),
                ("result_hash", models.CharField(blank=True, max_length=64)),
                ("result_ref", models.JSONField(default=dict)),
                (
                    "progress_kind",
                    models.CharField(
                        choices=[
                            ("none", "Kein Erkenntnisfortschritt"),
                            ("evidence", "Neuer Beleg"),
                            ("refutation", "Begründeter Ausschluss"),
                            ("contradiction", "Neuer Widerspruch"),
                            ("coverage", "Neue begründete Abdeckung"),
                        ],
                        default="none",
                        max_length=20,
                    ),
                ),
                ("progress_payload", models.JSONField(default=dict)),
                ("error_code", models.CharField(blank=True, max_length=50)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="accelerator.investigationrun",
                    ),
                ),
            ],
            options={"ordering": ["run", "sequence"]},
        ),
        migrations.AddConstraint(
            model_name="investigationstep",
            constraint=models.UniqueConstraint(
                fields=("run", "sequence"),
                name="uniq_investigation_step_sequence",
            ),
        ),
        migrations.AddConstraint(
            model_name="investigationstep",
            constraint=models.UniqueConstraint(
                fields=("run", "step_key"),
                name="uniq_investigation_step_key",
            ),
        ),
        migrations.CreateModel(
            name="InvestigationModelCall",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "role",
                    models.CharField(
                        choices=[("planner", "Planner"), ("verifier", "Verifier")],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Läuft"),
                            ("success", "Erfolgreich"),
                            ("failed", "Fehlgeschlagen"),
                            ("discarded", "Verworfen"),
                        ],
                        default="running",
                        max_length=20,
                    ),
                ),
                ("attempt", models.PositiveSmallIntegerField(default=1)),
                ("executor_generation", models.PositiveIntegerField()),
                ("requested_provider", models.CharField(default="openrouter", max_length=50)),
                ("requested_model", models.CharField(blank=True, max_length=200)),
                ("returned_model", models.CharField(blank=True, max_length=200)),
                ("model_revision", models.CharField(blank=True, max_length=200)),
                ("effective_parameters", models.JSONField(default=dict)),
                ("provider_attempt_id", models.CharField(blank=True, max_length=200)),
                ("prompt_version", models.CharField(max_length=40)),
                ("prompt_hash", models.CharField(max_length=64)),
                ("instruction_template", models.TextField()),
                ("schema_version", models.CharField(max_length=40)),
                ("context_refs", models.JSONField(default=dict)),
                ("accepted_payload", models.JSONField(default=dict)),
                ("accepted_payload_hash", models.CharField(blank=True, max_length=64)),
                ("prompt_tokens", models.PositiveIntegerField(blank=True, null=True)),
                ("completion_tokens", models.PositiveIntegerField(blank=True, null=True)),
                ("total_tokens", models.PositiveIntegerField(blank=True, null=True)),
                ("error_code", models.CharField(blank=True, max_length=50)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="model_calls",
                        to="accelerator.investigationrun",
                    ),
                ),
                (
                    "step",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="model_calls",
                        to="accelerator.investigationstep",
                    ),
                ),
            ],
            options={"ordering": ["run", "created_at"]},
        ),
        migrations.AddIndex(
            model_name="investigationmodelcall",
            index=models.Index(fields=["run", "role", "created_at"], name="invmodel_run_role_idx"),
        ),
        migrations.CreateModel(
            name="InvestigationVerifierReport",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("revision", models.PositiveIntegerField()),
                ("success", models.BooleanField(default=False)),
                ("findings", models.JSONField(default=list)),
                ("critical_findings", models.PositiveIntegerField(default=0)),
                ("source_references_valid", models.BooleanField(default=False)),
                ("checked_critical_claims", models.JSONField(default=list)),
                ("bound_hashes", models.JSONField(default=dict)),
                ("created_for_executor_generation", models.PositiveIntegerField()),
                (
                    "model_call",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="verifier_report",
                        to="accelerator.investigationmodelcall",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verifier_reports",
                        to="accelerator.investigationrun",
                    ),
                ),
            ],
            options={"ordering": ["run", "-revision"]},
        ),
        migrations.AddConstraint(
            model_name="investigationverifierreport",
            constraint=models.UniqueConstraint(
                fields=("run", "revision"),
                name="uniq_investigation_verifier_revision",
            ),
        ),
        migrations.CreateModel(
            name="InvestigationInputRevision",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("revision", models.PositiveIntegerField()),
                ("payload", models.JSONField(default=dict)),
                ("payload_hash", models.CharField(max_length=64)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="input_revisions",
                        to="accelerator.investigationrun",
                    ),
                ),
                (
                    "supplied_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="investigation_input_revisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["run", "revision"]},
        ),
        migrations.AddConstraint(
            model_name="investigationinputrevision",
            constraint=models.UniqueConstraint(
                fields=("run", "revision"),
                name="uniq_investigation_input_revision",
            ),
        ),
        migrations.CreateModel(
            name="InvestigationBriefRevision",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("revision", models.PositiveIntegerField()),
                ("payload", models.JSONField(default=dict)),
                ("content_hash", models.CharField(max_length=64)),
                ("operation_key", models.CharField(max_length=64)),
                ("process_version", models.PositiveIntegerField()),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="brief_revisions",
                        to="accelerator.investigationrun",
                    ),
                ),
            ],
            options={"ordering": ["run", "revision"]},
        ),
        migrations.AddConstraint(
            model_name="investigationbriefrevision",
            constraint=models.UniqueConstraint(
                fields=("run", "revision"),
                name="uniq_investigation_brief_revision",
            ),
        ),
        migrations.AddConstraint(
            model_name="investigationbriefrevision",
            constraint=models.UniqueConstraint(
                fields=("run", "operation_key"),
                name="uniq_investigation_brief_operation",
            ),
        ),
    ]
