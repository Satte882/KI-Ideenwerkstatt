import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


LEVEL_CHOICES = [("low", "Niedrig"), ("medium", "Mittel"), ("high", "Hoch")]
DECISION_STATUS_CHOICES = [
    ("clarification", "In Klärung"),
    ("ready", "Bereit zur Bewertung"),
    ("deferred", "Zurückgestellt"),
    ("approved", "Freigegeben"),
    ("approved_with_conditions", "Freigegeben mit Auflagen"),
    ("not_pursued", "Nicht weiterverfolgt"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("use_cases", "0002_decision_quality_metrics"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="usecase",
            name="decision_status",
            field=models.CharField(
                choices=DECISION_STATUS_CHOICES,
                db_index=True,
                default="clarification",
                max_length=30,
                verbose_name="Entscheidungsstatus",
            ),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="decision_status",
            field=models.CharField(
                choices=DECISION_STATUS_CHOICES,
                db_index=True,
                default="clarification",
                max_length=30,
                verbose_name="Entscheidungsstatus",
            ),
        ),
        migrations.AddIndex(
            model_name="usecase",
            index=models.Index(
                fields=["decision_status", "updated_at"],
                name="use_cases_u_decisio_55feda_idx",
            ),
        ),
        migrations.CreateModel(
            name="DecisionAssessment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("version", models.PositiveIntegerField()),
                ("assessment_date", models.DateField(default=django.utils.timezone.localdate)),
                ("business_value", models.CharField(choices=LEVEL_CHOICES, max_length=10)),
                ("strategic_fit", models.CharField(choices=LEVEL_CHOICES, max_length=10)),
                (
                    "technical_feasibility",
                    models.CharField(choices=LEVEL_CHOICES, max_length=10),
                ),
                ("data_readiness", models.CharField(choices=LEVEL_CHOICES, max_length=10)),
                ("risk_complexity", models.CharField(choices=LEVEL_CHOICES, max_length=10)),
                (
                    "evidence_quality",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Unbestätigte Annahme"),
                            (2, "Fachliche Einschätzung"),
                            (3, "Stichprobe oder Einzelmessung"),
                            (4, "Repräsentative Messung"),
                            (5, "Unabhängig bestätigte Messung"),
                        ]
                    ),
                ),
                (
                    "evidence_recency",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Unzureichend"),
                            (2, "Eingeschränkt"),
                            (3, "Belastbar"),
                            (4, "Sehr belastbar"),
                        ]
                    ),
                ),
                (
                    "evidence_coverage",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Unzureichend"),
                            (2, "Eingeschränkt"),
                            (3, "Belastbar"),
                            (4, "Sehr belastbar"),
                        ]
                    ),
                ),
                (
                    "independent_review",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Unzureichend"),
                            (2, "Eingeschränkt"),
                            (3, "Belastbar"),
                            (4, "Sehr belastbar"),
                        ]
                    ),
                ),
                (
                    "assumptions_resolved",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Unzureichend"),
                            (2, "Eingeschränkt"),
                            (3, "Belastbar"),
                            (4, "Sehr belastbar"),
                        ]
                    ),
                ),
                ("evidence_url", models.URLField()),
                ("rationale", models.TextField()),
                (
                    "governance_precheck_completed",
                    models.BooleanField(
                        default=False,
                        verbose_name="Governance-Vorprüfung durchgeführt",
                    ),
                ),
                (
                    "recommendation",
                    models.CharField(
                        choices=[
                            ("deferred", "Zurückstellen"),
                            ("approved", "Freigeben"),
                            ("approved_with_conditions", "Mit Auflagen freigeben"),
                            ("not_pursued", "Nicht weiterverfolgen"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "assessed_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="decision_assessments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "use_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="decision_assessments",
                        to="use_cases.usecase",
                    ),
                ),
            ],
            options={"ordering": ["-version"]},
        ),
        migrations.AddConstraint(
            model_name="decisionassessment",
            constraint=models.UniqueConstraint(
                fields=("use_case", "version"),
                name="unique_decision_assessment_version",
            ),
        ),
        migrations.CreateModel(
            name="ApprovalDecision",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "decision_status",
                    models.CharField(choices=DECISION_STATUS_CHOICES, max_length=30),
                ),
                ("rationale", models.TextField()),
                ("governance_confirmed", models.BooleanField(default=False)),
                ("conditions", models.TextField(blank=True)),
                ("condition_due_date", models.DateField(blank=True, null=True)),
                ("finalized_at", models.DateTimeField(blank=True, null=True)),
                (
                    "assessment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approval_decisions",
                        to="use_cases.decisionassessment",
                    ),
                ),
                (
                    "condition_owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="decision_conditions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "decided_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approval_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "second_approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="second_approval_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "use_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_decisions",
                        to="use_cases.usecase",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
