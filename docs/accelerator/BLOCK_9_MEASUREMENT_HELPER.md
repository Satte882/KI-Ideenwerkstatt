# Block 9 AP 8: Minimale Messhilfe

**Issue:** #125  
**Benchmarkvertrag:** `ki_radar/accelerator/block9_benchmark.v1.json`

## Zweck

Die Messhilfe ergänzt ausschließlich die im Produkt noch fehlenden manuellen Zeitsegmente und
führt sie mit bereits vorhandener Accelerator-Telemetrie zusammen. Sie ist kein dauerhaftes
Analytics-Produkt und legt keine neuen Datenbanktabellen an.

## Vorhandene Daten werden wiederverwendet

Für einen angegebenen `CaptureSession`-Datensatz übernimmt die Messhilfe direkt:

- `active_entry_seconds`, `save_count`, beantwortete und erforderliche Fragen,
- Anzahl tatsächlicher `CaptureAnalysis`-Aufrufe,
- Prompt-, Completion- und Total-Tokens,
- Kosten und LLM-Laufzeit,
- Analysefehler,
- Adoption-Status `adopted`, `adopted_edited`, `rejected`, `conflict`, `stale`, `failed`.

Die Messhilfe dupliziert diese Werte nicht in einem neuen Produktmodell.

## Manuell zu erfassende Segmente

Pro Lauf werden gemäß AP 7 separat übergeben:

- aktive Eingabezeit,
- Navigation,
- Review,
- Korrektur,
- System-/LLM-Wartezeit,
- End-to-End-Zeit.

Zusätzlich können die eingefrorenen Qualitätszähler und beim Delivery-Benchmark die bereits
ermittelten Delivery-Zähler als JSON übergeben werden.

## Raw-Format

Der Management-Command
`python manage.py record_block9_benchmark` hängt genau einen JSON-Datensatz an eine explizit
angegebene JSONL-Datei an. Jede Zeile enthält `benchmark_version`, `run_id`, Pfad, Fall,
Status, Zeitsegmente, Qualitätszähler und optional bestehende Accelerator-/Delivery-Daten.

Eine bereits vorhandene `run_id` wird abgelehnt. Es gibt bewusst keinen Update-, Delete- oder
Dashboard-Pfad. Fehlgeschlagene, abgebrochene oder blockierte Läufe können als solche
unverändert protokolliert werden.

Beispiel für einen manuellen Lauf:

```text
python manage.py record_block9_benchmark --output artifacts/block9/raw.jsonl --run-id manual-A-1 --path manual --case A --active-input-seconds 600 --navigation-seconds 60 --review-seconds 120 --correction-seconds 30 --system-wait-seconds 5 --end-to-end-seconds 815 --quality-json '{"correct_field_mappings":21}'
```

Für einen Accelerator-Lauf kann zusätzlich `--capture-session <UUID>` übergeben werden. Dann
werden die vorhandenen Capture-/LLM-/Adoption-Metriken automatisch ergänzt.

## Abgrenzung

- keine Migration,
- kein neues Telemetrie- oder Auditmodell,
- kein Event-Streaming,
- kein BI-/Analytics-Dashboard,
- keine automatische Interpretation der 30-Minuten-Grenze,
- kein nachträgliches Überschreiben bereits erfasster Run-IDs.
