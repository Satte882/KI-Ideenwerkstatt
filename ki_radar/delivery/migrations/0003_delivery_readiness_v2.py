import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


SECTION_KEYS = (
    "problem_and_target",
    "scope_and_users",
    "solution_direction",
    "architecture_and_data",
    "requirements_and_governance",
    "acceptance_and_measurement",
    "delivery_control",
)


def migrate_delivery_readiness(apps, schema_editor):
    delivery_package = apps.get_model("delivery", "DeliveryPackage")
    section_review = apps.get_model("delivery", "DeliverySectionReview")
    architecture_artifacts = apps.get_model("delivery", "DeliveryArchitectureArtifacts")
    migrated_at = timezone.now().isoformat()

    for package in delivery_package.objects.all().iterator():
        if package.status == "handed_over":
            package.readiness_schema_version = 1
            package.save(update_fields=["readiness_schema_version"])
            continue

        if package.status == "ready":
            package.status = "draft"
        package.readiness_schema_version = 2
        package.save(update_fields=["status", "readiness_schema_version"])
        manifest = {"legacy_migration": {"migrated_at": migrated_at}}
        for section_key in SECTION_KEYS:
            section_review.objects.get_or_create(
                delivery_package=package,
                section_key=section_key,
                defaults={
                    "content_origin": "mixed",
                    "review_status": "needs_review",
                    "source_manifest": manifest,
                },
            )

    for artifacts in architecture_artifacts.objects.all().iterator():
        artifacts.system_responsibilities = (
            "Führendes System, fachlichen Owner, technischen Owner und Zielkomponenten "
            "konkretisieren."
        )
        artifacts.data_quality_and_access = (
            "Datenqualität, Zugriffsweg, Datenverantwortung, Schutzbedarf und Aktualisierung "
            "konkretisieren."
        )
        artifacts.integration_operations = (
            "Authentifizierung, Auslöser, Fehlerbehandlung, Retry/Fallback, Monitoring und "
            "technische Verantwortung konkretisieren."
        )
        artifacts.save(
            update_fields=[
                "system_responsibilities",
                "data_quality_and_access",
                "integration_operations",
            ]
        )


def reverse_delivery_readiness(apps, schema_editor):
    delivery_package = apps.get_model("delivery", "DeliveryPackage")
    delivery_package.objects.filter(readiness_schema_version=2).update(
        readiness_schema_version=1
    )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("delivery", "0002_delivery_architecture_artifacts"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliverypackage",
            name="readiness_schema_version",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="deliveryarchitectureartifacts",
            name="data_quality_and_access",
            field=models.TextField(
                blank=True,
                verbose_name="Datenqualität, Zugriff und Schutzbedarf",
            ),
        ),
        migrations.AddField(
            model_name="deliveryarchitectureartifacts",
            name="integration_operations",
            field=models.TextField(
                blank=True,
                verbose_name="Integrationsbetrieb und Fehlerbehandlung",
            ),
        ),
        migrations.AddField(
            model_name="deliveryarchitectureartifacts",
            name="system_responsibilities",
            field=models.TextField(
                blank=True,
                verbose_name="Systemverantwortung und Zielkomponenten",
            ),
        ),
        migrations.CreateModel(
            name="DeliverySectionReview",
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
                    "section_key",
                    models.CharField(
                        choices=[
                            ("problem_and_target", "Problem und Ziel"),
                            ("scope_and_users", "Scope, Nutzer und MVP"),
                            ("solution_direction", "Gewählte Lösungsrichtung"),
                            (
                                "architecture_and_data",
                                "System-, Daten- und Integrationskontext",
                            ),
                            (
                                "requirements_and_governance",
                                "Anforderungen und Governance",
                            ),
                            (
                                "acceptance_and_measurement",
                                "Akzeptanz und Erfolgsmessung",
                            ),
                            (
                                "delivery_control",
                                "Risiken, Abhängigkeiten und Umsetzungsstart",
                            ),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "content_origin",
                    models.CharField(
                        choices=[
                            ("inherited", "Übernommen"),
                            ("mixed", "Übernommen und ergänzt"),
                            ("new", "Neu für Delivery"),
                            ("not_applicable", "Nicht relevant"),
                        ],
                        default="new",
                        max_length=30,
                    ),
                ),
                (
                    "review_status",
                    models.CharField(
                        choices=[
                            ("needs_review", "Prüfung erforderlich"),
                            ("confirmed", "Bestätigt"),
                            ("blocked", "Blockiert"),
                            ("not_applicable", "Nicht relevant"),
                        ],
                        default="needs_review",
                        max_length=30,
                    ),
                ),
                ("source_manifest", models.JSONField(blank=True, default=dict)),
                ("review_note", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("business_confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("technical_confirmed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "business_confirmed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="business_confirmed_delivery_sections",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "delivery_package",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="section_reviews",
                        to="delivery.deliverypackage",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_delivery_sections",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "technical_confirmed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="technical_confirmed_delivery_sections",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["delivery_package", "section_key"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("delivery_package", "section_key"),
                        name="unique_delivery_section_review",
                    )
                ],
            },
        ),
        migrations.RunPython(migrate_delivery_readiness, reverse_delivery_readiness),
    ]
