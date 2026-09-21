from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

DEMO_METRICS = {
    "[DEMO] Interner Wissensassistent": {
        "metric_name": "Recherchezeit pro komplexer Anfrage",
        "metric_type": "duration",
        "metric_direction": "lower",
        "metric_unit": "Minuten",
        "metric_baseline": Decimal("18"),
        "metric_target": Decimal("12.6"),
        "metric_actual": Decimal("11.5"),
        "metric_measurement_method": "Vergleich von 40 repräsentativen Rechercheaufgaben.",
        "metric_measurement_period": "Letzte 30 Tage",
        "metric_measured_at": lambda today: today - timedelta(days=14),
        "metric_evidence_url": "https://example.invalid/evidence/demo-wissensassistent-messung",
    },
    "[DEMO] Automatische Rechnungspruefung": {
        "metric_name": "Prüfzeit je Rechnung",
        "metric_type": "duration",
        "metric_direction": "lower",
        "metric_unit": "Minuten",
        "metric_baseline": Decimal("11"),
        "metric_target": Decimal("8.25"),
        "metric_actual": Decimal("8.9"),
        "metric_measurement_method": "Zeitmessung bei 100 Standardrechnungen.",
        "metric_measurement_period": "Pilotwochen 5 bis 8",
        "metric_measured_at": lambda today: today - timedelta(days=5),
        "metric_evidence_url": "https://example.invalid/evidence/demo-rechnungspruefung-messung",
    },
    "[DEMO] Zusammenfassung von Besprechungen": {
        "metric_name": "Nachbereitungszeit pro Besprechung",
        "metric_type": "duration",
        "metric_direction": "lower",
        "metric_unit": "Minuten",
        "metric_baseline": Decimal("25"),
        "metric_target": Decimal("12.5"),
        "metric_measurement_method": "20 interne Besprechungen mit manueller Zeitmessung.",
    },
    "[DEMO] Klassifikation eingehender Dokumente": {
        "metric_name": "Manueller Sortieraufwand je Dokument",
        "metric_type": "duration",
        "metric_direction": "lower",
        "metric_unit": "Minuten",
        "metric_baseline": Decimal("3"),
        "metric_target": Decimal("1"),
        "metric_actual": Decimal("0.8"),
        "metric_measurement_method": "Stichprobe aus 250 eingehenden Dokumenten.",
        "metric_measurement_period": "Juni 2026",
        "metric_measured_at": lambda today: today - timedelta(days=21),
        "metric_evidence_url": "https://example.invalid/evidence/demo-dokumentklassifikation",
    },
    "[DEMO] Unterstuetzung bei Kundenanfragen": {
        "metric_name": "Antworten ohne wesentliche Nacharbeit",
        "metric_type": "percent",
        "metric_direction": "higher",
        "metric_unit": "Prozent",
        "metric_baseline": Decimal("45"),
        "metric_target": Decimal("75"),
        "metric_actual": Decimal("68"),
        "metric_measurement_method": "Fachliche Bewertung von 80 Pilotantworten.",
        "metric_measurement_period": "Letzte vier Pilotwochen",
        "metric_measured_at": lambda today: today - timedelta(days=3),
        "metric_evidence_url": "https://example.invalid/evidence/demo-kundenanfragen",
    },
    "[DEMO] Absatz- oder Bedarfsprognose": {
        "metric_name": "Prognosegenauigkeit",
        "metric_type": "percent",
        "metric_direction": "higher",
        "metric_unit": "Prozent",
        "metric_baseline": Decimal("65"),
        "metric_target": Decimal("80"),
        "metric_measurement_method": "Backtesting auf zwölf historischen Monatsperioden.",
    },
    "[DEMO] Qualitaetspruefung von Texten": {
        "metric_name": "Texte ohne wesentliche Nacharbeit",
        "metric_type": "percent",
        "metric_direction": "higher",
        "metric_unit": "Prozent",
        "metric_baseline": Decimal("60"),
        "metric_target": Decimal("85"),
        "metric_measurement_method": "Blindbewertung von 50 Beispieltexten.",
    },
    "[DEMO] Extraktion von Vertragsinformationen": {
        "metric_name": "Bearbeitungszeit je Vertrag",
        "metric_type": "duration",
        "metric_direction": "lower",
        "metric_unit": "Minuten",
        "metric_baseline": Decimal("12"),
        "metric_target": Decimal("4"),
        "metric_measurement_method": "Zeitmessung bei 40 freigegebenen Musterverträgen.",
    },
    "[DEMO] Priorisierung interner Anfragen": {
        "metric_name": "Zeit bis zur korrekten Priorisierung",
        "metric_type": "duration",
        "metric_direction": "lower",
        "metric_unit": "Stunden",
        "metric_baseline": Decimal("18"),
        "metric_target": Decimal("8"),
        "metric_measurement_method": "Auswertung von 100 historischen und neuen Tickets.",
    },
}


def enrich_demo_metrics() -> int:
    from ki_radar.use_cases.models import UseCase

    today = timezone.localdate()
    updated = 0
    for title, values in DEMO_METRICS.items():
        try:
            use_case = UseCase.objects.get(title=title)
        except UseCase.DoesNotExist:
            continue
        for field_name, value in values.items():
            setattr(use_case, field_name, value(today) if callable(value) else value)
        use_case.save()
        updated += 1
    return updated
