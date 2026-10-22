"""Add append-only correction notices without modifying reviewed evidence."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("use_cases", "0018_capability_experiment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CapabilityExperimentCorrection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "note",
                    models.TextField(
                        verbose_name="Berichtigung (alter und korrigierter Stand samt Grund)"
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="capability_experiment_corrections",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "experiment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="corrections",
                        to="use_cases.capabilityexperiment",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
    ]
