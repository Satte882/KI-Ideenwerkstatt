# Block 6: Persistenz- und Retention-Regeln

## Zweck

Structured Adoption speichert nur die für Bestätigung, Konfliktprüfung, Idempotenz und Audit notwendigen Snapshots. Capture-Rohantworten und vollständige Providerantworten werden nicht in Batch, Item oder Audit kopiert.

## Lebenszyklus

- `StructuredAdoptionBatch` bleibt nach Löschung einer Capture Session oder Capture Analysis erhalten. Die optionalen Fremdschlüssel werden auf `NULL` gesetzt; Session-, Analyse-, Actor- und Ziel-IDs bleiben als Snapshots nachvollziehbar.
- `StructuredAdoptionItem` gehört zum Batch und wird nur gemeinsam mit diesem gelöscht. Abhängigkeiten werden über Item-Fremdschlüssel und stabile lokale Schlüssel dokumentiert.
- `StructuredAdoptionAudit` bleibt auch dann erhalten, wenn Batch, Item oder Actor später gelöscht werden. Es enthält neutrale Ergebnis-, Schritt- und Fehlerdaten, aber keine vollständigen Rohantworten.
- `retention_until` markiert den frühesten Zeitpunkt für eine spätere kontrollierte Bereinigung. Block 6 führt keinen automatischen Löschjob ein.

## Datensparsame Herkunft

Zulässig sind insbesondere:

- Question-IDs,
- Hashes kurzer Originalausschnitte,
- Interpretations- und Entscheidungssnapshots,
- Feldsnapshots bestätigter Werte,
- Versionen und technische IDs.

Nicht zulässig sind unkontrollierte Kopien von `CaptureSession.answers`, vollständigen Providerantworten oder vollständigen Gesprächsverläufen.
