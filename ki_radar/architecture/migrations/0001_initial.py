import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("use_cases", "0003_guided_intake_hard_gates"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ValueStream",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("trigger", models.TextField(verbose_name="Auslöser")),
                ("outcome", models.TextField(verbose_name="Ergebnis für den Empfänger")),
                ("scope", models.TextField(verbose_name="Scope und Abgrenzung")),
                (
                    "strategic_objective",
                    models.TextField(blank=True, verbose_name="Strategisches Ziel"),
                ),
                ("stakeholders", models.TextField(blank=True, verbose_name="Stakeholder")),
                (
                    "constraints",
                    models.TextField(blank=True, verbose_name="Leitplanken und Einschränkungen"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Entwurf"),
                            ("active", "Aktiv"),
                            ("archived", "Archiviert"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "business_unit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="value_streams",
                        to="accounts.businessunit",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_value_streams",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="owned_value_streams",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["business_unit__name", "name"]},
        ),
        migrations.CreateModel(
            name="ValueStreamStage",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("sequence", models.PositiveSmallIntegerField(verbose_name="Reihenfolge")),
                ("name", models.CharField(max_length=200)),
                (
                    "description",
                    models.TextField(blank=True, verbose_name="Aktivität und Ergebnis"),
                ),
                ("actors", models.TextField(blank=True, verbose_name="Beteiligte Rollen")),
                ("systems", models.TextField(blank=True, verbose_name="Systeme")),
                (
                    "documents",
                    models.TextField(blank=True, verbose_name="Daten und Dokumente"),
                ),
                (
                    "pain_points",
                    models.TextField(blank=True, verbose_name="Probleme und Engpässe"),
                ),
                (
                    "baseline_metrics",
                    models.TextField(blank=True, verbose_name="Kennzahlen und Baseline"),
                ),
                (
                    "value_stream",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stages",
                        to="architecture.valuestream",
                    ),
                ),
            ],
            options={"ordering": ["sequence", "created_at"]},
        ),
        migrations.AddConstraint(
            model_name="valuestreamstage",
            constraint=models.UniqueConstraint(
                fields=("value_stream", "sequence"),
                name="unique_value_stream_stage_sequence",
            ),
        ),
        migrations.CreateModel(
            name="UseCaseOrigin",
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
                    "stage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="use_case_origins",
                        to="architecture.valuestreamstage",
                    ),
                ),
                (
                    "use_case",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="architecture_origin",
                        to="use_cases.usecase",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
