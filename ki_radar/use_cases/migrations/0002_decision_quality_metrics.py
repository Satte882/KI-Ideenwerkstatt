from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("use_cases", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="usecase",
            name="metric_actual",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                max_digits=14,
                null=True,
                verbose_name="Gemessener Ist-Wert",
            ),
        ),
        migrations.AddField(
            model_name="usecase",
            name="metric_baseline",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                max_digits=14,
                null=True,
                verbose_name="Baseline-Wert",
            ),
        ),
        migrations.AddField(
            model_name="usecase",
            name="metric_direction",
            field=models.CharField(
                blank=True,
                choices=[("lower", "Niedriger ist besser"), ("higher", "Höher ist besser")],
                max_length=10,
                verbose_name="Optimierungsrichtung",
            ),
        ),
        migrations.AddField(
            model_name="usecase",
            name="metric_evidence_url",
            field=models.URLField(blank=True, verbose_name="Messnachweis"),
        ),
        migrations.AddField(
            model_name="usecase",
            name="metric_measured_at",
            field=models.DateField(blank=True, null=True, verbose_name="Messdatum"),
        ),
        migrations.AddField(
            model_name="usecase",
            name="metric_measurement_method",
            field=models.TextField(blank=True, verbose_name="Messmethode"),
        ),
        migrations.AddField(
            model_name="usecase",
            name="metric_measurement_period",
            field=models.CharField(blank=True, max_length=200, verbose_name="Messzeitraum"),
        ),
        migrations.AddField(
            model_name="usecase",
            name="metric_name",
            field=models.CharField(
                blank=True, max_length=200, verbose_name="Primäre Erfolgsmetrik"
            ),
        ),
        migrations.AddField(
            model_name="usecase",
            name="metric_target",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                max_digits=14,
                null=True,
                verbose_name="Zielwert",
            ),
        ),
        migrations.AddField(
            model_name="usecase",
            name="metric_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("number", "Zahl"),
                    ("percent", "Prozent"),
                    ("duration", "Dauer"),
                    ("currency", "Geldbetrag"),
                    ("count", "Anzahl"),
                    ("rating", "Bewertungsskala"),
                ],
                max_length=20,
                verbose_name="Metriktyp",
            ),
        ),
        migrations.AddField(
            model_name="usecase",
            name="metric_unit",
            field=models.CharField(blank=True, max_length=80, verbose_name="Einheit"),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="metric_actual",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                max_digits=14,
                null=True,
                verbose_name="Gemessener Ist-Wert",
            ),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="metric_baseline",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                max_digits=14,
                null=True,
                verbose_name="Baseline-Wert",
            ),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="metric_direction",
            field=models.CharField(
                blank=True,
                choices=[("lower", "Niedriger ist besser"), ("higher", "Höher ist besser")],
                max_length=10,
                verbose_name="Optimierungsrichtung",
            ),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="metric_evidence_url",
            field=models.URLField(blank=True, verbose_name="Messnachweis"),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="metric_measured_at",
            field=models.DateField(blank=True, null=True, verbose_name="Messdatum"),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="metric_measurement_method",
            field=models.TextField(blank=True, verbose_name="Messmethode"),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="metric_measurement_period",
            field=models.CharField(blank=True, max_length=200, verbose_name="Messzeitraum"),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="metric_name",
            field=models.CharField(
                blank=True, max_length=200, verbose_name="Primäre Erfolgsmetrik"
            ),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="metric_target",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                max_digits=14,
                null=True,
                verbose_name="Zielwert",
            ),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="metric_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("number", "Zahl"),
                    ("percent", "Prozent"),
                    ("duration", "Dauer"),
                    ("currency", "Geldbetrag"),
                    ("count", "Anzahl"),
                    ("rating", "Bewertungsskala"),
                ],
                max_length=20,
                verbose_name="Metriktyp",
            ),
        ),
        migrations.AddField(
            model_name="historicalusecase",
            name="metric_unit",
            field=models.CharField(blank=True, max_length=80, verbose_name="Einheit"),
        ),
    ]
