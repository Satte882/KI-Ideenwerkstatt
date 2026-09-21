# Block 9 AP 9: Rohmessungen und Ausführungsgrenze

**Issue:** #125  
**Benchmarkvertrag:** `ki_radar/accelerator/block9_benchmark.v1.json`  
**Messhilfe:** `ki_radar/accelerator/benchmark_measurement.py`

## Zweck

AP 9 führt nur Messungen aus, die in der jeweiligen Ausführungsumgebung tatsächlich
beobachtbar sind. Automatisierte Test- oder CI-Zeiten werden nicht als menschliche
Bearbeitungszeit ausgegeben.

Die technische Messstrecke läuft in einer frischen CI-Datenbank und erzeugt ein unverändertes
Raw-Artefakt. Sie misst:

- einen echten `run_blueprint(..., apply=True)`-Kontrolllauf des unveränderten Real-DEMO-
  Blueprints,
- drei echte Block-8-Delivery-Mapping-Läufe mit `create_delivery_package(...,
  use_evidence_mapper=True)`.

Die Delivery-Läufe verwenden denselben bereits vorbereiteten Upstream-Zustand. Jeder Lauf
wird innerhalb einer DB-Transaktion ausgeführt und nach Erfassung der Rohwerte
zurückgerollt. Dadurch beginnt der nächste Lauf ohne vorheriges DeliveryPackage.

## Technisch gemessene Rohdaten

Der Workflow `.github/workflows/block9-technical-measurements.yml` erzeugt:

- `raw-technical.jsonl`
- `interactive-status.json`

und lädt beide Dateien unverändert als GitHub-Actions-Artefakt
`block9-ap9-raw-<run-id>` hoch.

`raw-technical.jsonl` enthält genau:

1. `blueprint-A-control-1`
2. `delivery-A-1`
3. `delivery-A-2`
4. `delivery-A-3`

Für den Blueprint werden ausschließlich Systemwarte- und End-to-End-Systemzeit sowie
Ergebnis, Objektanzahlen und Blueprint-Prüfsumme erfasst.

Für Delivery werden Systemwarte- und End-to-End-Systemzeit sowie die im Block-8-Manifest
beobachteten Anzahlen deterministischer Felder, LLM-Felder, Gaps und Konflikte erfasst.
Bestätigungen, Übergabe oder andere fachliche Gates werden nicht ausgeführt.

## Interaktive Läufe

Die eingefrorenen menschlichen Läufe bleiben:

1. `manual-A-1`
2. `accelerator-A-1`
3. `accelerator-A-2`
4. `manual-A-2`
5. `manual-A-3`
6. `accelerator-A-3`

Diese Läufe benötigen einen realen Operator in derselben Browser-/Stack-Umgebung. Die
aktuelle CI-/Connector-Ausführung besitzt keine menschliche Browser-Session. Deshalb werden
für diese Läufe **keine automatisierten Ersatzzeiten erzeugt**.

`interactive-status.json` markiert jeden dieser Läufe als `not_executed` mit dem Grund
`operator_measurement_required`. Benchmark B wird aus demselben Grund als `not_executed`
geführt.

Ein fehlender menschlicher Lauf wird insbesondere nicht mit `0` Sekunden, einer Django-
Testclient-Laufzeit oder einer CI-Testdauer ersetzt.

## Interpretationsgrenze

Dieses Dokument enthält bewusst keine Aussage dazu, ob der Accelerator die 30-Minuten-
Grenze erreicht, keinen Beschleunigungsfaktor und keine finale Qualitätsbewertung.

Eine solche Interpretation ist erst zulässig, wenn die eingefrorenen interaktiven Läufe
real durchgeführt und zusammen mit den technischen Rohdaten in AP 10 ausgewertet wurden.

Bis dahin ist AP 9 technisch teilweise ausgeführt, aber der vollständige empirische
Messvertrag noch nicht erfüllt.
