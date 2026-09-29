from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_llm_task_runtime"),
    ]

    operations = [
        migrations.AlterField(
            model_name="llmtaskrun",
            name="task_type",
            field=models.CharField(
                choices=[
                    ("delivery_field_draft", "Delivery-Feldentwurf"),
                    ("ap2_metric_pilot_draft", "AP2 Metrik- und Pilotentwurf"),
                    (
                        "origin_consistency_review",
                        "Herkunfts-Konsistenzprüfung",
                    ),
                ],
                db_index=True,
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="llmtaskquota",
            name="task_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("delivery_field_draft", "Delivery-Feldentwurf"),
                    ("ap2_metric_pilot_draft", "AP2 Metrik- und Pilotentwurf"),
                    (
                        "origin_consistency_review",
                        "Herkunfts-Konsistenzprüfung",
                    ),
                ],
                max_length=40,
            ),
        ),
    ]
