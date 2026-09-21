from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("use_cases", "0003_guided_intake_hard_gates"),
    ]

    operations = [
        migrations.AddField(
            model_name="usecase",
            name="demo_key",
            field=models.SlugField(
                blank=True,
                editable=False,
                max_length=100,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="demo_key",
            field=models.SlugField(
                blank=True,
                editable=False,
                max_length=100,
                null=True,
            ),
        ),
    ]
