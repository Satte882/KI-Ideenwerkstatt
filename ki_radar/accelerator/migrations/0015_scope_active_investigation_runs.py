# Generated for Issue #72 guided-path product/evidence run separation

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accelerator", "0014_alter_investigationmodelcall_role"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="investigationrun",
            name="uniq_active_investigation_run",
        ),
        migrations.AddConstraint(
            model_name="investigationrun",
            constraint=models.UniqueConstraint(
                fields=("process_analysis",),
                condition=models.Q(
                    ("evidence_campaign__isnull", True),
                    ("status__in", ["running", "waiting_human"]),
                ),
                name="uniq_active_product_run",
            ),
        ),
        migrations.AddConstraint(
            model_name="investigationrun",
            constraint=models.UniqueConstraint(
                fields=("process_analysis",),
                condition=models.Q(
                    ("evidence_campaign__isnull", False),
                    ("status__in", ["running", "waiting_human"]),
                ),
                name="uniq_active_evidence_run",
            ),
        ),
    ]
