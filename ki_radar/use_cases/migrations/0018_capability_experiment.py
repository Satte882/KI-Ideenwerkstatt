# Additive #148 experiment evidence; no legacy backfill or lifecycle change.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("use_cases", "0017_initiative_impact_review"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CapabilityExperiment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=200, verbose_name="Experiment / Fragestellung")),
                ("ai_vision", models.TextField(blank=True, verbose_name="Ambitionierte AI-first-Zielhypothese")),
                ("first_viable_step", models.TextField(blank=True, verbose_name="Erste realistisch betreibbare Ausbaustufe")),
                ("capability_hypothesis", models.TextField(blank=True, verbose_name="Zu testende KI-Fähigkeit / Widerlegungskriterium")),
                ("tested_configuration", models.TextField(blank=True, verbose_name="Version, Konfiguration und Änderungen")),
                ("test_case_ids", models.TextField(blank=True, help_text="Keine echten Falldaten oder personenbezogenen Inhalte hier speichern.", verbose_name="Geprüfte Fall-Referenzen (eine ID pro Zeile)")),
                ("holdout_case_ids", models.TextField(blank=True, help_text="Unbekannte Fälle separat führen; keine bereits getesteten Fälle wiederverwenden.", verbose_name="Unverbrauchte Fall-Referenzen (eine ID pro Zeile)")),
                ("holdout_unseen_confirmed", models.BooleanField(default=False, verbose_name="Die Holdout-Fälle waren vor dem Test nicht zur Anpassung verwendet")),
                ("failure_modes", models.TextField(blank=True, verbose_name="Fehlerbilder und Grenzen")),
                ("assumptions", models.TextField(blank=True, verbose_name="Daten-, System- und Betriebsannahmen")),
                ("effort", models.TextField(blank=True, verbose_name="Aufwand / Time-to-Value")),
                ("finding", models.CharField(choices=[
                    ("open", "Noch nicht überprüft"),
                    ("supported", "Capability im Test gestützt"),
                    ("partial", "Teilweise / mit Grenzen"),
                    ("not_supported", "Capability nicht bestätigt"),
                ], default="open", max_length=20, verbose_name="Beobachtetes Capability-Ergebnis")),
                ("evidence_reference", models.TextField(blank=True, verbose_name="Prüfnachweis / Quelle / Protokollreferenz")),
                ("learning_value", models.TextField(blank=True, help_text="Kein finanzieller Geschäftsnutzen und keine automatische Freigabe.", verbose_name="Learning Value: überprüfbare neue Erkenntnis")),
                ("data_kind", models.CharField(choices=[
                    ("synthetic", "Synthetisch / Testdaten"),
                    ("real", "Reale Daten (gesonderte Governance erforderlich)"),
                ], default="synthetic", max_length=12, verbose_name="Art des Testmaterials")),
                ("governance_reference", models.TextField(blank=True, verbose_name="Freigabe-/Governance-Referenz für Real-Daten")),
                ("revision", models.PositiveIntegerField(default=1, editable=False)),
                ("reviewed_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("created_by", models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_capability_experiments", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_capability_experiments", to=settings.AUTH_USER_MODEL)),
                ("initiative", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="capability_experiments", to="use_cases.improvementinitiative")),
                ("retest_of", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="retests", to="use_cases.capabilityexperiment", verbose_name="Vorheriger Capability-Test")),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
    ]
