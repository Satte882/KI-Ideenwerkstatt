import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("architecture", "0003_valuestream_demo_key"),
    ]

    operations = [
        migrations.CreateModel(
            name="ValueStreamFocus",
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
                (
                    "business_domain",
                    models.CharField(
                        choices=[
                            ("procurement", "Einkauf und Beschaffung"),
                            ("sales", "Vertrieb"),
                            ("marketing", "Marketing"),
                            ("production", "Produktion und Leistungserbringung"),
                            ("logistics", "Logistik und Supply Chain"),
                            ("finance", "Finanzen und Controlling"),
                            ("human_resources", "Personal"),
                            ("customer_service", "Kundenservice"),
                            ("it", "IT und Technologie"),
                            ("legal_compliance", "Recht und Compliance"),
                            ("research_development", "Forschung und Entwicklung"),
                            ("corporate_services", "Unternehmensfunktionen"),
                            ("other", "Sonstige Fachdomäne"),
                        ],
                        db_index=True,
                        default="other",
                        max_length=40,
                        verbose_name="Fachdomäne",
                    ),
                ),
                (
                    "capability",
                    models.CharField(
                        blank=True,
                        max_length=200,
                        verbose_name="Business Capability",
                    ),
                ),
                (
                    "strategic_impact",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("low", "Niedrig"),
                            ("medium", "Mittel"),
                            ("high", "Hoch"),
                        ],
                        max_length=10,
                        verbose_name="Strategischer Impact",
                    ),
                ),
                (
                    "economic_potential",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("low", "Niedrig"),
                            ("medium", "Mittel"),
                            ("high", "Hoch"),
                        ],
                        max_length=10,
                        verbose_name="Wirtschaftliches Potenzial",
                    ),
                ),
                (
                    "pain_intensity",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("low", "Niedrig"),
                            ("medium", "Mittel"),
                            ("high", "Hoch"),
                        ],
                        max_length=10,
                        verbose_name="Problem- und Schmerzintensität",
                    ),
                ),
                (
                    "data_accessibility",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("low", "Niedrig"),
                            ("medium", "Mittel"),
                            ("high", "Hoch"),
                        ],
                        max_length=10,
                        verbose_name="Datenzugänglichkeit",
                    ),
                ),
                (
                    "change_effort",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("low", "Niedrig"),
                            ("medium", "Mittel"),
                            ("high", "Hoch"),
                        ],
                        max_length=10,
                        verbose_name="Veränderungsaufwand",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("not_screened", "Noch nicht bewertet"),
                            ("candidate", "Kandidat für Vertiefung"),
                            ("selected", "Für Deep Dive ausgewählt"),
                            ("deferred", "Zurückgestellt"),
                            ("not_selected", "Nicht ausgewählt"),
                        ],
                        db_index=True,
                        default="not_screened",
                        max_length=20,
                        verbose_name="Fokusentscheidung",
                    ),
                ),
                (
                    "rationale",
                    models.TextField(
                        blank=True,
                        verbose_name="Begründung der Fokusentscheidung",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_value_stream_focuses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "value_stream",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="focus",
                        to="architecture.valuestream",
                    ),
                ),
            ],
            options={
                "ordering": [
                    "value_stream__business_unit__name",
                    "value_stream__name",
                ]
            },
        ),
    ]
