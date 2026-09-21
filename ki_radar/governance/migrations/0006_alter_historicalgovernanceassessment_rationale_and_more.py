from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("governance", "0005_relax_governance_rationale_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicalgovernanceassessment",
            name="rationale",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="historicalgovernancereview",
            name="rationale",
            field=models.TextField(blank=True),
        ),
    ]
