from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0004_review_scale_readiness_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="funding_status",
            field=models.CharField(
                blank=True,
                default="",
                choices=[
                    ("satisfied", "Erfüllt / verbindlich zugesagt"),
                    ("open", "Offen / nicht zugesagt"),
                    ("not_required", "Für diesen Scope nicht erforderlich"),
                ],
                max_length=20,
                verbose_name="Finanzierung für diesen Entscheidungsscope",
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="funding_evidence",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Finanzierungsnachweis / Begründung",
            ),
        ),
        migrations.AddField(
            model_name="historicalreview",
            name="funding_status",
            field=models.CharField(
                blank=True,
                default="",
                choices=[
                    ("satisfied", "Erfüllt / verbindlich zugesagt"),
                    ("open", "Offen / nicht zugesagt"),
                    ("not_required", "Für diesen Scope nicht erforderlich"),
                ],
                max_length=20,
                verbose_name="Finanzierung für diesen Entscheidungsscope",
            ),
        ),
        migrations.AddField(
            model_name="historicalreview",
            name="funding_evidence",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Finanzierungsnachweis / Begründung",
            ),
        ),
    ]
