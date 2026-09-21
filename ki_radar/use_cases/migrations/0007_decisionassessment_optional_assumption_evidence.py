from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("use_cases", "0006_guided_second_approval")]

    operations = [
        migrations.AlterField(
            model_name="decisionassessment",
            name="evidence_url",
            field=models.URLField(blank=True),
        ),
    ]
