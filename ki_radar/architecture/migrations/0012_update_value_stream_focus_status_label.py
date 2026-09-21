from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0011_stage_focus_decision"),
    ]

    operations = [
        migrations.AlterField(
            model_name="valuestreamfocus",
            name="status",
            field=models.CharField(
                choices=[
                    ("not_screened", "Noch nicht bewertet"),
                    ("candidate", "Kandidat für Vertiefung"),
                    ("selected", "Für Prozessanalyse ausgewählt"),
                    ("deferred", "Zurückgestellt"),
                    ("not_selected", "Nicht ausgewählt"),
                ],
                db_index=True,
                default="not_screened",
                max_length=20,
                verbose_name="Fokusentscheidung",
            ),
        ),
    ]
