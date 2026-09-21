from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0016_processanalysis_diagnosis_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="solutionselectiondecision",
            name="diagnosis_snapshot",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
        migrations.AddField(
            model_name="solutionselectiondecision",
            name="process_version",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
    ]
