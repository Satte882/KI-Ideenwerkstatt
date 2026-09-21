from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0015_solutionarchitectureassessment"),
    ]

    operations = [
        migrations.AddField(
            model_name="processanalysis",
            name="diagnostic_observations",
            field=models.TextField(blank=True, verbose_name="Beobachtung / Problem"),
        ),
        migrations.AddField(
            model_name="processanalysis",
            name="cause_hypotheses",
            field=models.TextField(blank=True, verbose_name="Ursachenhypothese"),
        ),
        migrations.AddField(
            model_name="processanalysis",
            name="confirmed_causes",
            field=models.TextField(blank=True, verbose_name="Bestätigte Ursache"),
        ),
        migrations.AddField(
            model_name="processanalysis",
            name="constraints",
            field=models.TextField(blank=True, verbose_name="Randbedingung / Constraint"),
        ),
    ]
