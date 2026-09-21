from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("architecture", "0002_process_analysis_solution_options")]

    operations = [
        migrations.AddField(
            model_name="valuestream",
            name="demo_key",
            field=models.SlugField(
                max_length=100,
                null=True,
                blank=True,
                unique=True,
                editable=False,
            ),
        )
    ]
