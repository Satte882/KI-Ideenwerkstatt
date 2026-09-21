from django.db import migrations, models


AI_OPTION_TYPES = {"analytics_ml", "generative_ai", "assistant"}


def backfill_existing_solution_semantics(apps, schema_editor):
    SolutionOption = apps.get_model("architecture", "SolutionOption")
    SolutionOption.objects.all().update(time_to_value="unknown")
    SolutionOption.objects.filter(option_type__in=AI_OPTION_TYPES).update(
        contains_ai_component=True
    )


def reverse_backfill(apps, schema_editor):
    SolutionOption = apps.get_model("architecture", "SolutionOption")
    SolutionOption.objects.all().update(
        time_to_value="not_assessed",
        contains_ai_component=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0017_solutionselectiondecision_diagnosis_snapshot"),
    ]

    operations = [
        migrations.AlterField(
            model_name="solutionoption",
            name="option_type",
            field=models.CharField(
                choices=[
                    ("organizational", "Organisatorische Änderung"),
                    ("rule_automation", "Regelbasierte Automatisierung"),
                    ("standard_software", "Standardsoftware"),
                    ("custom_software", "Individuelle Software"),
                    ("analytics_ml", "Analytics oder Machine Learning"),
                    ("generative_ai", "Generative KI"),
                    ("assistant", "Assistenzsystem"),
                    ("hybrid", "Hybride Lösung"),
                    ("no_tech", "Keine technische Lösung"),
                    ("other", "Sonstige Option"),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="solutionoption",
            name="contains_ai_component",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Für hybride, individuelle oder sonstige Lösungen explizit angeben. "
                    "Eindeutige KI- bzw. Nicht-KI-Typen werden automatisch eingeordnet."
                ),
                verbose_name="Enthält KI-Komponente",
            ),
        ),
        migrations.AddField(
            model_name="solutionoption",
            name="evidence_basis",
            field=models.CharField(
                choices=[
                    ("hypothesis", "Hypothese / unbestätigt"),
                    ("indicative", "Indiz / qualitativ belegt"),
                    ("measured", "Gemessen / nachgewiesen"),
                ],
                default="hypothesis",
                max_length=20,
                verbose_name="Evidenzbasis",
            ),
        ),
        migrations.AddField(
            model_name="solutionoption",
            name="time_to_value",
            field=models.CharField(
                choices=[
                    ("not_assessed", "Noch nicht bewertet"),
                    ("unknown", "Unbekannt"),
                    ("short", "Kurz"),
                    ("medium", "Mittel"),
                    ("long", "Lang"),
                ],
                default="not_assessed",
                max_length=20,
                verbose_name="Time-to-Value",
            ),
        ),
        migrations.RunPython(backfill_existing_solution_semantics, reverse_backfill),
    ]
