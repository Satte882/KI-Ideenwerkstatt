from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accelerator", "0008_solution_generation_run"),
    ]

    operations = [
        migrations.AddField(
            model_name="solutiongenerationrun",
            name="preview_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
