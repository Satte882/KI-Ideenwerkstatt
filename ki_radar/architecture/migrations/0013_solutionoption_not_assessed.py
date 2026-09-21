from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0012_update_value_stream_focus_status_label"),
    ]

    operations = [
        migrations.AlterField(
            model_name="solutionoption",
            name="feasibility",
            field=models.CharField(
                choices=[
                    ("not_assessed", "Noch nicht bewertet"),
                    ("low", "Niedrig"),
                    ("medium", "Mittel"),
                    ("high", "Hoch"),
                ],
                default="not_assessed",
                max_length=20,
                verbose_name="Machbarkeit",
            ),
        ),
        migrations.AlterField(
            model_name="solutionoption",
            name="integration_effort",
            field=models.CharField(
                choices=[
                    ("not_assessed", "Noch nicht bewertet"),
                    ("low", "Niedrig"),
                    ("medium", "Mittel"),
                    ("high", "Hoch"),
                ],
                default="not_assessed",
                max_length=20,
                verbose_name="Integrationsaufwand",
            ),
        ),
    ]
