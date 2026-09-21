from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("governance", "0004_backfill_governance_review_artifacts"),
    ]

    operations = [
        migrations.AlterField(
            model_name="governanceassessment",
            name="rationale",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="governancereview",
            name="rationale",
            field=models.TextField(blank=True),
        ),
    ]
