import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("architecture", "0018_solutionoption_issue_331"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkDesignAssessment",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("process_version", models.PositiveIntegerField()),
                ("version", models.PositiveIntegerField(default=1)),
                (
                    "role_name",
                    models.CharField(max_length=200, verbose_name="Betrachtete Rolle"),
                ),
                ("business_outcome", models.TextField(verbose_name="Geschäftsergebnis")),
                (
                    "method_version",
                    models.CharField(default="1.7.0", editable=False, max_length=20),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Entwurf"),
                            ("assessed", "Bewertet"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_work_design_assessments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "process_analysis",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="work_design_assessments",
                        to="architecture.processanalysis",
                    ),
                ),
            ],
            options={
                "ordering": ["role_name", "-version"],
            },
        ),
        migrations.CreateModel(
            name="WorkDesignTask",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("name", models.CharField(max_length=240, verbose_name="Aufgabe")),
                (
                    "source_area",
                    models.CharField(
                        blank=True,
                        max_length=120,
                        verbose_name="Herkunftsbereich",
                    ),
                ),
                (
                    "target_work_split",
                    models.TextField(
                        blank=True,
                        verbose_name="Vorgesehene Aufgabenteilung",
                    ),
                ),
                (
                    "approval_role",
                    models.CharField(
                        blank=True,
                        max_length=200,
                        verbose_name="Fachfreigabe",
                    ),
                ),
                ("business_value", models.PositiveSmallIntegerField(blank=True, null=True)),
                (
                    "handoff_friction",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("recurrence", models.PositiveSmallIntegerField(blank=True, null=True)),
                (
                    "context_proximity",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("ai_leverage", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("data_readiness", models.PositiveSmallIntegerField(blank=True, null=True)),
                (
                    "judgment_stakes",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "specialist_accountability",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "potential_score",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        editable=False,
                        null=True,
                    ),
                ),
                (
                    "boundary_score",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        editable=False,
                        null=True,
                    ),
                ),
                (
                    "recommendation",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("prepare-only", "Vorbereiten, nicht freigeben"),
                            ("own", "Übernehmen + pilotieren"),
                            ("own-with-approval", "Übernehmen + Fachfreigabe"),
                            ("explore", "Gezielt explorieren"),
                            ("keep-handoff", "Handoff vorerst beibehalten"),
                        ],
                        editable=False,
                        max_length=30,
                    ),
                ),
                (
                    "approval_required",
                    models.BooleanField(default=False, editable=False),
                ),
                (
                    "assessment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="architecture.workdesignassessment",
                    ),
                ),
            ],
            options={
                "ordering": ["sequence", "created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="workdesignassessment",
            constraint=models.UniqueConstraint(
                fields=("process_analysis", "role_name", "version"),
                name="unique_work_design_role_version",
            ),
        ),
    ]
