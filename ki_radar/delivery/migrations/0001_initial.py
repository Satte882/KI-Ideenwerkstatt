import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("use_cases", "0003_guided_intake_hard_gates"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DeliveryPackage",
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
                ("version", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Entwurf"),
                            ("ready", "Bereit zur Übergabe"),
                            ("handed_over", "Übergeben"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "problem_context",
                    models.TextField(verbose_name="Problem und Geschäftskontext"),
                ),
                (
                    "target_outcome",
                    models.TextField(verbose_name="Ziel und erwartetes Ergebnis"),
                ),
                ("in_scope", models.TextField(verbose_name="Im Scope")),
                ("out_of_scope", models.TextField(verbose_name="Nicht im Scope")),
                (
                    "users_and_scenarios",
                    models.TextField(verbose_name="Nutzer und Nutzungsszenarien"),
                ),
                (
                    "solution_outline",
                    models.TextField(verbose_name="Lösungsrahmen und Zielbild"),
                ),
                (
                    "system_context",
                    models.TextField(verbose_name="System- und Anwendungskontext"),
                ),
                (
                    "data_context",
                    models.TextField(verbose_name="Datenobjekte und Datenquellen"),
                ),
                (
                    "integrations",
                    models.TextField(blank=True, verbose_name="Schnittstellen und Integrationen"),
                ),
                (
                    "functional_requirements",
                    models.TextField(verbose_name="Funktionale Anforderungen"),
                ),
                (
                    "non_functional_requirements",
                    models.TextField(verbose_name="Nichtfunktionale Anforderungen"),
                ),
                (
                    "security_privacy_requirements",
                    models.TextField(
                        verbose_name="Security-, Datenschutz- und Rechtsanforderungen"
                    ),
                ),
                ("human_oversight", models.TextField(verbose_name="Menschliche Aufsicht")),
                (
                    "logging_and_audit",
                    models.TextField(verbose_name="Logging und Nachvollziehbarkeit"),
                ),
                (
                    "operations_and_support",
                    models.TextField(verbose_name="Betrieb und Support"),
                ),
                ("mvp_scope", models.TextField(verbose_name="MVP-Scope")),
                (
                    "acceptance_criteria",
                    models.TextField(verbose_name="Akzeptanzkriterien"),
                ),
                (
                    "test_scenarios",
                    models.TextField(verbose_name="Testfälle und Qualitätssicherung"),
                ),
                (
                    "measurement_plan",
                    models.TextField(verbose_name="Erfolgsmessung und Pilot"),
                ),
                ("dependencies", models.TextField(blank=True, verbose_name="Abhängigkeiten")),
                ("risks", models.TextField(blank=True, verbose_name="Risiken")),
                ("assumptions", models.TextField(blank=True, verbose_name="Annahmen")),
                (
                    "architecture_decisions",
                    models.TextField(
                        blank=True,
                        verbose_name="Architekturentscheidungen und Leitplanken",
                    ),
                ),
                ("initial_backlog", models.TextField(verbose_name="Initiales Backlog")),
                (
                    "external_delivery_url",
                    models.URLField(blank=True, verbose_name="Delivery-System"),
                ),
                (
                    "handover_notes",
                    models.TextField(blank=True, verbose_name="Übergabehinweise"),
                ),
                ("handed_over_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_delivery_packages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "generated_from_decision",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="delivery_packages",
                        to="use_cases.approvaldecision",
                    ),
                ),
                (
                    "handed_over_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="handed_over_delivery_packages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "use_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="delivery_packages",
                        to="use_cases.usecase",
                    ),
                ),
            ],
            options={"ordering": ["-version"]},
        ),
        migrations.AddConstraint(
            model_name="deliverypackage",
            constraint=models.UniqueConstraint(
                fields=("use_case", "version"),
                name="unique_delivery_package_version",
            ),
        ),
    ]
