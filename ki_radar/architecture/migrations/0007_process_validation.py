import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def invalidate_legacy_validations(apps, schema_editor):
    ProcessAnalysis = apps.get_model("architecture", "ProcessAnalysis")
    ProcessAnalysis.objects.filter(status="validated").update(status="review_required")


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("architecture", "0006_split_value_stream_scope"),
    ]

    operations = [
        migrations.AddField(
            model_name="processanalysis",
            name="version",
            field=models.PositiveIntegerField(default=1, editable=False),
        ),
        migrations.AlterField(
            model_name="processanalysis",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Entwurf"),
                    ("review_required", "Prüfbedürftig"),
                    ("validated", "Ist-Prozess validiert"),
                    ("target_defined", "Zielbild beschrieben"),
                ],
                default="draft",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="ProcessValidation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("process_version", models.PositiveIntegerField()),
                ("validator_role", models.CharField(max_length=100)),
                ("validated_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("note", models.TextField(blank=True, verbose_name="Validierungsnotiz")),
                ("evidence_url", models.URLField(blank=True, verbose_name="Nachweis")),
                (
                    "process_analysis",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="validations", to="architecture.processanalysis"),
                ),
                (
                    "validated_by",
                    models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="process_validations", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-validated_at"]},
        ),
        migrations.AddConstraint(
            model_name="processvalidation",
            constraint=models.UniqueConstraint(fields=("process_analysis", "process_version"), name="unique_process_validation_version"),
        ),
        migrations.RunPython(invalidate_legacy_validations, migrations.RunPython.noop),
    ]
