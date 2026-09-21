# Generated for VS1/3 decision brief and end-to-end evidence

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accelerator", "0012_adaptive_investigation"),
        ("architecture", "0020_solutionoption_work_design_origin"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InvestigationEvidenceCampaign",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("campaign_key", models.CharField(max_length=64, unique=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("limits", models.JSONField(default=dict)),
                ("usage", models.JSONField(default=dict)),
                ("pricing", models.JSONField(blank=True, default=dict)),
                ("currency", models.CharField(blank=True, max_length=8)),
                ("pricing_version", models.CharField(blank=True, max_length=80)),
                ("authorized_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("continuation_reason", models.TextField(blank=True)),
                (
                    "authorized_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="authorized_investigation_evidence_campaigns",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "process_analysis",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="investigation_evidence_campaigns",
                        to="architecture.processanalysis",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="InvestigationEvidenceBudgetRevision",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("revision", models.PositiveIntegerField()),
                ("limits", models.JSONField(default=dict)),
                ("pricing", models.JSONField(blank=True, default=dict)),
                ("currency", models.CharField(blank=True, max_length=8)),
                ("pricing_version", models.CharField(blank=True, max_length=80)),
                ("usage_at_authorization", models.JSONField(default=dict)),
                ("reason", models.TextField()),
                ("authorized_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "authorized_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="investigation_evidence_budget_revisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_revisions",
                        to="accelerator.investigationevidencecampaign",
                    ),
                ),
            ],
            options={"ordering": ["campaign", "revision"]},
        ),
        migrations.AddConstraint(
            model_name="investigationevidencebudgetrevision",
            constraint=models.UniqueConstraint(
                fields=("campaign", "revision"),
                name="uniq_investigation_budget_revision",
            ),
        ),
        migrations.AddField(
            model_name="investigationrun",
            name="evidence_campaign",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="investigation_runs",
                to="accelerator.investigationevidencecampaign",
            ),
        ),
        migrations.AddField(
            model_name="investigationrun",
            name="evidence_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="investigationrun",
            name="execution_mode",
            field=models.CharField(default="adaptive", max_length=20),
        ),
        migrations.CreateModel(
            name="InvestigationProviderReservation",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Reserviert"),
                            ("settled", "Abgerechnet"),
                            ("uncertain", "Verbrauch unklar"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                ("reserved_input_tokens", models.PositiveIntegerField()),
                ("reserved_output_tokens", models.PositiveIntegerField()),
                ("reserved_cost_microunits", models.PositiveBigIntegerField(blank=True, null=True)),
                ("actual_input_tokens", models.PositiveIntegerField(blank=True, null=True)),
                ("actual_output_tokens", models.PositiveIntegerField(blank=True, null=True)),
                ("actual_cost_microunits", models.PositiveBigIntegerField(blank=True, null=True)),
                ("uncertainty_reason", models.CharField(blank=True, max_length=80)),
                ("settled_at", models.DateTimeField(blank=True, null=True)),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="provider_reservations",
                        to="accelerator.investigationevidencecampaign",
                    ),
                ),
                (
                    "model_call",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="evidence_reservation",
                        to="accelerator.investigationmodelcall",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="provider_reservations",
                        to="accelerator.investigationrun",
                    ),
                ),
            ],
            options={"ordering": ["campaign", "created_at"]},
        ),
        migrations.CreateModel(
            name="InvestigationMaterialization",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("operation_key", models.CharField(max_length=64)),
                (
                    "outcome",
                    models.CharField(
                        choices=[("applied", "Übernommen"), ("conflict", "Differenz erkannt")],
                        max_length=20,
                    ),
                ),
                ("base_domain_hash", models.CharField(max_length=64)),
                ("resulting_domain_hash", models.CharField(blank=True, max_length=64)),
                ("applied_fields", models.JSONField(default=dict)),
                ("created_solution_option_ids", models.JSONField(default=list)),
                ("updated_solution_option_ids", models.JSONField(default=list)),
                ("conflicts", models.JSONField(default=list)),
                (
                    "brief_revision",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="materialization",
                        to="accelerator.investigationbriefrevision",
                    ),
                ),
                (
                    "materialized_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="investigation_materializations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="materializations",
                        to="accelerator.investigationrun",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="investigationmaterialization",
            constraint=models.UniqueConstraint(
                fields=("run", "operation_key"),
                name="uniq_investigation_materialization_operation",
            ),
        ),
    ]
