from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("use_cases", "0007_decisionassessment_optional_assumption_evidence"),
    ]

    operations = [
        migrations.AlterField(
            model_name="approvaldecision",
            name="assessment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="approval_decisions",
                to="use_cases.decisionassessment",
            ),
        ),
    ]
