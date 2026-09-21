import django.db.models.deletion
from django.db import migrations, models


def backfill_use_case_classification(apps, schema_editor):
    use_case_model = apps.get_model("use_cases", "UseCase")
    classification_model = apps.get_model("use_cases", "UseCaseClassification")
    origin_model = apps.get_model("architecture", "UseCaseOrigin")
    focus_model = apps.get_model("architecture", "ValueStreamFocus")

    origins = {
        origin.use_case_id: origin
        for origin in origin_model.objects.select_related(
            "stage__value_stream",
            "process_analysis",
        ).all()
    }
    focus_by_stream = {
        focus.value_stream_id: focus
        for focus in focus_model.objects.all()
    }

    for use_case in use_case_model.objects.all().iterator():
        origin = origins.get(use_case.pk)
        focus = (
            focus_by_stream.get(origin.stage.value_stream_id)
            if origin is not None
            else None
        )
        classification_model.objects.get_or_create(
            use_case=use_case,
            defaults={
                "business_domain": focus.business_domain if focus else "other",
                "capability": focus.capability if focus else "",
                "process_area": (
                    origin.process_analysis.name
                    if origin is not None and origin.process_analysis_id
                    else origin.stage.name
                    if origin is not None
                    else use_case.affected_process
                ),
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0005_backfill_value_stream_focus"),
        ("use_cases", "0004_usecase_demo_key"),
    ]

    operations = [
        migrations.CreateModel(
            name="UseCaseClassification",
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
                    "process_area",
                    models.CharField(
                        blank=True,
                        max_length=200,
                        verbose_name="Prozessbereich",
                    ),
                ),
                (
                    "use_case",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="classification",
                        to="use_cases.usecase",
                    ),
                ),
            ],
            options={
                "ordering": [
                    "business_domain",
                    "capability",
                    "use_case__short_id",
                ]
            },
        ),
        migrations.RunPython(
            backfill_use_case_classification,
            migrations.RunPython.noop,
        ),
    ]
