# Generated for Issue #104 AP3 delivery task

from django.db import migrations, models


TASK_CHOICES = [
    ("delivery_field_draft", "Delivery-Feldentwurf"),
    ("ap2_metric_pilot_draft", "AP2 Metrik- und Pilotentwurf"),
    ("ap2_architecture_inputs", "AP2 Architecture-Advisor-Eingaben"),
    ("ap2_decision_governance_draft", "AP2 Entscheidungs- und Governance-Entwurf"),
    ("ap3_delivery_package", "AP3 Delivery Package"),
    ("origin_consistency_review", "Herkunfts-Konsistenzprüfung"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_alter_llmtaskquota_task_type_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="llmtaskquota",
            name="task_type",
            field=models.CharField(
                blank=True,
                choices=TASK_CHOICES,
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="llmtaskrun",
            name="task_type",
            field=models.CharField(
                choices=TASK_CHOICES,
                db_index=True,
                max_length=40,
            ),
        ),
    ]
