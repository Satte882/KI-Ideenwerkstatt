from django.db import migrations, models


PRODUCTIVE_UNITS = {
    "Unternehmenssteuerung": (
        "Geschäftsführung, Strategie und bereichsübergreifende Steuerung."
    ),
    "Touristik & Operations": (
        "Reiseportfolio, touristische Leistungserstellung und operative Reiseabwicklung."
    ),
    "Kundenservice & Buchung": (
        "Kundenberatung, Buchungsbetreuung, Kundenanfragen und Serviceprozesse."
    ),
    "Marketing & Vertrieb": (
        "Direktvertrieb, Kampagnen, Online-Marketing und Mediakooperationen."
    ),
    "IT & Digitalisierung": (
        "IT, Anwendungen, Integrationen, Daten- und KI-Plattformen sowie technische Digitalisierung."
    ),
    "Finanzen & Administration": (
        "Kaufmännische und administrative Querschnittsthemen."
    ),
}


def seed_productive_catalog(apps, schema_editor):
    BusinessUnit = apps.get_model("accounts", "BusinessUnit")
    for name, description in PRODUCTIVE_UNITS.items():
        unit, _created = BusinessUnit.objects.get_or_create(
            name=name,
            defaults={
                "description": description,
                "is_active": True,
                "catalog_scope": "productive",
            },
        )
        changed = []
        if unit.catalog_scope != "productive":
            unit.catalog_scope = "productive"
            changed.append("catalog_scope")
        if not unit.is_active:
            unit.is_active = True
            changed.append("is_active")
        if unit.description != description:
            unit.description = description
            changed.append("description")
        if changed:
            unit.save(update_fields=[*changed, "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessunit",
            name="catalog_scope",
            field=models.CharField(
                choices=[
                    ("productive", "Produktiv"),
                    ("demo_test", "Demo/Test"),
                    ("legacy", "Bestand"),
                ],
                db_index=True,
                default="legacy",
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(seed_productive_catalog, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="businessunit",
            name="catalog_scope",
            field=models.CharField(
                choices=[
                    ("productive", "Produktiv"),
                    ("demo_test", "Demo/Test"),
                    ("legacy", "Bestand"),
                ],
                db_index=True,
                default="productive",
                max_length=20,
            ),
        ),
    ]
