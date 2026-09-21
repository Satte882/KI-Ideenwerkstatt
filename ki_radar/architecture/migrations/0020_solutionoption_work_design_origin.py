import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0019_work_design"),
    ]

    operations = [
        migrations.AddField(
            model_name="solutionoption",
            name="source_work_design_snapshot",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
        migrations.AddField(
            model_name="solutionoption",
            name="source_work_design_task",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="solution_options",
                to="architecture.workdesigntask",
            ),
        ),
    ]
