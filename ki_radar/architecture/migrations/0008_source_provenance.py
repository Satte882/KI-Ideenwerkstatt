from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0007_process_validation"),
    ]

    operations = [
        migrations.AddField(
            model_name="processanalysis",
            name="source_snapshot",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
        migrations.AddField(
            model_name="usecaseorigin",
            name="source_snapshot",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
    ]
