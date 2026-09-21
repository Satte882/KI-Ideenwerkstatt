from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0003_earlygoliveexception"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="scale_readiness_schema_version",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="review",
            name="scale_readiness_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="historicalreview",
            name="scale_readiness_schema_version",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="historicalreview",
            name="scale_readiness_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
