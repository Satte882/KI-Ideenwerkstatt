import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0002_go_live_exception_confirmed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EarlyGoLiveException",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("original_planned_pilot_end", models.DateField()),
                ("decision_date", models.DateField()),
                ("reason", models.TextField()),
                ("evidence_basis", models.TextField()),
                ("unobserved_risks", models.TextField()),
                ("mitigation_measures", models.TextField()),
                ("confirmed_by_label", models.CharField(max_length=200)),
                ("confirmed_role", models.CharField(max_length=100)),
                (
                    "confirmed_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="confirmed_early_go_live_exceptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "review",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="early_go_live_exception",
                        to="reviews.review",
                    ),
                ),
            ],
            options={
                "ordering": ["-decision_date", "-created_at"],
            },
        ),
    ]
