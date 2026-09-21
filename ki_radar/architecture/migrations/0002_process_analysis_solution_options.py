import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcessAnalysis",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Entwurf"),
                            ("validated", "Ist-Prozess validiert"),
                            ("target_defined", "Zielbild beschrieben"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("scope_start", models.TextField(verbose_name="Prozessstart")),
                ("scope_end", models.TextField(verbose_name="Prozessende")),
                ("trigger", models.TextField(verbose_name="Auslöser")),
                ("outcome", models.TextField(verbose_name="Ergebnis")),
                ("current_flow", models.TextField(verbose_name="Ist-Ablauf")),
                ("roles", models.TextField(verbose_name="Rollen und Verantwortlichkeiten")),
                ("systems", models.TextField(verbose_name="Anwendungen und Arbeitsmittel")),
                ("data_objects", models.TextField(verbose_name="Datenobjekte und Dokumente")),
                ("business_rules", models.TextField(blank=True, verbose_name="Geschäftsregeln")),
                (
                    "handoffs",
                    models.TextField(blank=True, verbose_name="Übergaben und Schnittstellen"),
                ),
                ("bottlenecks", models.TextField(verbose_name="Bottlenecks und Ursachen")),
                (
                    "exceptions",
                    models.TextField(blank=True, verbose_name="Ausnahmen und Fehlerfälle"),
                ),
                (
                    "baseline_metrics",
                    models.TextField(verbose_name="Baseline und Prozesskennzahlen"),
                ),
                (
                    "target_state_principles",
                    models.TextField(blank=True, verbose_name="Prinzipien für den Soll-Prozess"),
                ),
                (
                    "analyzed_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="process_analyses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "stage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="process_analyses",
                        to="architecture.valuestreamstage",
                    ),
                ),
            ],
            options={"ordering": ["stage__sequence", "name"]},
        ),
        migrations.CreateModel(
            name="SolutionOption",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                (
                    "option_type",
                    models.CharField(
                        choices=[
                            ("organizational", "Organisatorische Änderung"),
                            ("rule_automation", "Regelbasierte Automatisierung"),
                            ("standard_software", "Standardsoftware"),
                            ("custom_software", "Individuelle Software"),
                            ("analytics_ml", "Analytics oder Machine Learning"),
                            ("generative_ai", "Generative KI"),
                            ("assistant", "Assistenzsystem"),
                            ("no_tech", "Keine technische Lösung"),
                            ("other", "Sonstige Option"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "recommendation",
                    models.CharField(
                        choices=[
                            ("candidate", "Kandidat"),
                            ("preferred", "Bevorzugte Option"),
                            ("rejected", "Verworfen"),
                        ],
                        default="candidate",
                        max_length=20,
                    ),
                ),
                ("description", models.TextField(verbose_name="Lösungsbeschreibung")),
                ("expected_value", models.TextField(verbose_name="Erwarteter Beitrag")),
                (
                    "feasibility",
                    models.CharField(
                        choices=[("low", "Niedrig"), ("medium", "Mittel"), ("high", "Hoch")],
                        default="medium",
                        max_length=10,
                        verbose_name="Machbarkeit",
                    ),
                ),
                (
                    "data_requirements",
                    models.TextField(blank=True, verbose_name="Datenanforderungen"),
                ),
                (
                    "application_impact",
                    models.TextField(blank=True, verbose_name="Auswirkung auf Anwendungen"),
                ),
                ("integration_impact", models.TextField(blank=True, verbose_name="Integrationen")),
                (
                    "technology_constraints",
                    models.TextField(blank=True, verbose_name="Technologieleitplanken"),
                ),
                ("risks", models.TextField(blank=True, verbose_name="Risiken und Nachteile")),
                (
                    "architecture_fit",
                    models.TextField(blank=True, verbose_name="Begründung und Architecture Fit"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="solution_options",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "process_analysis",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="solution_options",
                        to="architecture.processanalysis",
                    ),
                ),
            ],
            options={"ordering": ["recommendation", "name"]},
        ),
        migrations.AddConstraint(
            model_name="solutionoption",
            constraint=models.UniqueConstraint(
                condition=models.Q(("recommendation", "preferred")),
                fields=("process_analysis",),
                name="single_preferred_solution_per_process",
            ),
        ),
        migrations.AddField(
            model_name="usecaseorigin",
            name="process_analysis",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="use_case_origins",
                to="architecture.processanalysis",
            ),
        ),
        migrations.AddField(
            model_name="usecaseorigin",
            name="solution_option",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="use_case_origins",
                to="architecture.solutionoption",
            ),
        ),
    ]
