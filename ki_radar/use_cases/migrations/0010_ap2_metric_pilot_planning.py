from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("use_cases", "0009_idea_candidate"),
    ]

    operations = [
        migrations.AddField(
            model_name="usecase",
            name="ap2_planning_provenance",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
        migrations.AddField(
            model_name="usecase",
            name="metric_measurement_population",
            field=models.TextField(blank=True, verbose_name="Messpopulation / Stichprobe"),
        ),
        migrations.AddField(
            model_name="usecase",
            name="pilot_abort_criteria",
            field=models.TextField(blank=True, verbose_name="Pilot-Abbruchkriterien"),
        ),
        migrations.AddField(
            model_name="usecase",
            name="pilot_review_criteria",
            field=models.TextField(blank=True, verbose_name="Pilot-Reviewkriterien"),
        ),
        migrations.AddField(
            model_name="usecase",
            name="pilot_scope",
            field=models.TextField(blank=True, verbose_name="Kleinster sinnvoller Pilot"),
        ),
    ]
