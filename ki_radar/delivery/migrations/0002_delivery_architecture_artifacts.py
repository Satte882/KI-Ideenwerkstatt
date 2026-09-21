import django.db.models.deletion
from django.db import migrations, models


def backfill_architecture_artifacts(apps, schema_editor):
    delivery_package = apps.get_model("delivery", "DeliveryPackage")
    artifacts = apps.get_model("delivery", "DeliveryArchitectureArtifacts")
    for package in delivery_package.objects.all().iterator():
        integrations = package.integrations.strip()
        artifacts.objects.get_or_create(
            delivery_package=package,
            defaults={
                "system_landscape": (
                    f"Ist-Systeme und Arbeitsmittel:\n{package.system_context}\n\n"
                    "Ziel-Systemlandschaft und Systemverantwortung im Package konkretisieren."
                ),
                "data_flows": (
                    f"Datenobjekte und Quellen:\n{package.data_context}\n\n"
                    "Schnittstellen und Integrationen:\n"
                    f"{integrations or 'Keine Integrationen dokumentiert.'}"
                ),
                "integration_contracts": (
                    integrations
                    or "Keine technischen Integrationen vorgesehen; fachliche Verantwortlichkeiten bestätigen."
                ),
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("delivery", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeliveryArchitectureArtifacts",
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
                    "system_landscape",
                    models.TextField(
                        blank=True,
                        verbose_name="Ist-/Ziel-Systemlandschaft",
                    ),
                ),
                (
                    "data_flows",
                    models.TextField(
                        blank=True,
                        verbose_name="Daten- und Informationsflüsse",
                    ),
                ),
                (
                    "integration_contracts",
                    models.TextField(
                        blank=True,
                        verbose_name="Integrationsverträge und Verantwortlichkeiten",
                    ),
                ),
                (
                    "artifacts_url",
                    models.URLField(
                        blank=True,
                        verbose_name="Architekturartefakte und Diagramme",
                    ),
                ),
                (
                    "delivery_package",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="architecture_artifacts",
                        to="delivery.deliverypackage",
                    ),
                ),
            ],
        ),
        migrations.RunPython(
            backfill_architecture_artifacts,
            migrations.RunPython.noop,
        ),
    ]
