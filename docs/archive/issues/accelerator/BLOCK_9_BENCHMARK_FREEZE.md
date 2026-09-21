# Block 9 AP 7: Eingefrorener Benchmarkvertrag

**Issue:** #125  
**Workplan:** `docs/accelerator/BLOCK_9_WORKPLAN.md`  
**Fixture:** `ki_radar/accelerator/block9_benchmark.v1.json`  
**Fixture-Version:** `block9-v1`  
**Kanonische SHA-256-Prüfsumme:** `e3c894f6ee2a87cc7755380fc6dc43f7352796bfaa31cddd56491997f38f7dab`

## Zweck

AP 7 friert Faktenset, technische Startzustände, fachlichen Zielzustand, Messgrenze,
Reihenfolge und Qualitätskriterien **vor dem ersten gewerteten Lauf** ein. Ab dem ersten
gewerteten Lauf dürfen diese Regeln nicht anhand der Ergebnisse angepasst werden.

Die Fixture ist ein Benchmarkvertrag, keine Produktiv- oder Demo-Datenbank. Gewertete Läufe
verwenden isolierte Benchmark-Objekte und dedizierte Benchmark-Nutzer. Der vorhandene
`[Real-DEMO]`-Blueprint bleibt unverändert und dient ausschließlich als fachliche Referenz
und Driftanker.

## 1. Referenz und Fallfamilie

Benchmark A übernimmt den bekannten Beschaffungsfall aus
`ki_radar/core/scenario_blueprints/real_demo.v1.json`. Seine im Block-2-Nachweis
festgeschriebene kanonische Prüfsumme bleibt
`a910863c3f677eb95b593e8031f48e54f811c5bb55295b4e601ae6f13a0b70d5`.

Die Benchmark-Fixture kopiert nur die für den Vergleich benötigten fachlichen Fakten in
isolierte `[BENCHMARK-*]`-Datensätze. Sie ändert weder den Real-DEMO-Blueprint noch dessen
Golden-Path-Graph.

### Benchmark A – Zeitbenchmark

Vollständiger Golden Path ohne künstliche Fehler. Enthalten sind unter anderem:

- Problem, Prozess und Zielnutzer,
- Source-Systeme und Datenquellen,
- Assistenzzweck und Human Oversight,
- Baseline `11,0 Minuten`,
- Ziel `8,25 Minuten`,
- Messmethode,
- Scope-In und Scope-Out,
- bewusst unbekannter Provider und Modellname.

Unbekannte Provider-/Modellangaben bleiben unbekannt. Auch im Golden Path darf nichts
erfunden werden.

### Benchmark B – Robustheitsbenchmark

Der Robustheitsfall enthält exakt die vorab geforderten Herausforderungen:

- **eine Pflichtlücke:** Support-Verantwortung ist unbekannt,
- **einen Quellenkonflikt:** Zielwert `8,25 Minuten` versus neuere, noch nicht bestätigte
  Fachnotiz `8,5 Minuten`,
- **eine Scope-Falle:** finale Lieferantenauswahl und Vergabeentscheidung stehen im Satz,
  müssen aber im Scope-Out verbleiben,
- **eine Zahl mit Einheit:** Baseline `11 Minuten`,
- **No-Invention-Fakten:** Provider, Modell und Support-Verantwortung dürfen nicht ergänzt
  werden.

Erwartet wird nicht, dass der Accelerator den Konflikt selbst fachlich entscheidet.
Erwartet wird, dass er ihn nicht still auflöst und fehlende Fakten offen lässt.

## 2. Gemeinsamer fachlicher Zielzustand

Der Primärbenchmark endet bei einem gespeicherten strukturierten **Use-Case-Draft** mit:

- `status = idea`,
- `decision_status = clarification`,
- den in der Fixture aufgelisteten 21 Scoring-Feldern,
- explizit offenen Feldern, wenn das Faktenset keinen Wert trägt.

Ein offener Wert gilt nur dann als korrekt, wenn die Fixture ihn als fehlend oder
widersprüchlich definiert. Ein Vorschlag allein zählt nicht als gespeicherter Endzustand.

Nicht Bestandteil des Zielzustands sind:

- Governance-Prüfergebnis,
- Freigabe oder finale Entscheidung,
- Delivery-Section-Bestätigung,
- Übergabe,
- Pilotstart,
- Go-live.

Die Uhr stoppt erst, wenn jedes Scoring-Feld entweder fachlich korrekt gespeichert oder
begründet offen ist und keine ausgeschlossene Gate-Aktion ausgeführt wurde.

## 3. Technische Startzustände

Die technischen Startzustände dürfen sich unterscheiden; identisch ist das Faktenset.

### Manueller Pfad

- kein Benchmark-Use-Case vorhanden,
- Intake-Session leer beziehungsweise zurückgesetzt,
- Benchmark-Business-Unit und dedizierte Benchmark-Nutzer vorhanden,
- Start mit der ersten Nutzeraktion im regulären `use_cases:new`-Intake.

### Blueprint-Kontrollpfad

- Referenznutzer/-gruppen/-Business-Unit vorhanden,
- kein Benchmark-Szenariograph vorhanden,
- Start unmittelbar vor `apply_scenario_blueprint --apply`,
- Ende nach erfolgreicher atomarer Persistierung.

Der Blueprint bleibt ein technischer Kontrollpfad. Seine Laufzeit wird nicht als
menschlicher Produktivitätsvergleich interpretiert.

### Geführter Accelerator

Der bestehende Accelerator benötigt für Adoption ein bereits existierendes bearbeitbares
Zielobjekt. Deshalb startet der Pfad mit einer neuen Capture Session und einem minimalen
Benchmark-Use-Case.

Nur technisch unvermeidbare Seed-Werte sind vom Scoring ausgeschlossen:

- Business Unit,
- Business Owner,
- Submitter,
- `status = idea`,
- `decision_status = clarification`.

Diese Seed-Werte sind kein fachlicher Vorsprung. Alle eigentlichen Scoring-Inhalte müssen
über den regulären Accelerator-Pfad geprüft und explizit übernommen werden.

### Delivery-Sekundärbenchmark

Delivery startet für manuelle und Mapper-Variante aus demselben isolierten, bereits
positiv entschiedenen Upstream-Zustand. Freigabe- oder Rollenwartezeit wird nicht
hineingerechnet. Der Delivery-Benchmark bleibt vollständig außerhalb der primären
30-Minuten-Grenze.

## 4. Eingefrorene Reihenfolge

Ein Warm-up ist nicht gewertet.

Danach gelten für Benchmark A exakt drei gewertete Durchläufe je interaktivem Pfad:

1. Manual A1
2. Accelerator A1
3. Accelerator A2
4. Manual A2
5. Manual A3
6. Accelerator A3

Damit wechselt die Reihenfolge je Run-Paar: Manual→Accelerator, Accelerator→Manual,
Manual→Accelerator.

Zusätzlich:

- ein Blueprint-Kontrolllauf,
- drei Delivery-Mapping-Läufe auf jeweils zurückgesetztem identischem Upstream-Zustand.

Benchmark B wird als Qualitäts-/Robustheitsfall ausgeführt und nicht nachträglich in einen
Speed-Golden-Path umgedeutet.

## 5. Zeitmessung

Für jeden gewerteten interaktiven Lauf werden getrennt erfasst:

- aktive Eingabezeit,
- Navigation,
- Review,
- Korrektur,
- System-/LLM-Wartezeit,
- gesamte End-to-End-Zeit.

Die End-to-End-Zeit enthält die Systemwartezeit. Zeiten werden nicht nachträglich
umklassifiziert, um ein Ziel zu erreichen.

## 6. Qualitätsmessung

Je Lauf werden mindestens erfasst:

- korrekte Feldzuordnungen und Fehlzuordnungen,
- Zahlen-/Einheitenfehler,
- Scope-Fehler,
- erfundene Werte,
- übersehene Pflichtlücken,
- übersehene Stale-/Quellenkonflikte,
- unverändert angenommene Vorschläge,
- bearbeitet angenommene Vorschläge,
- verworfene Vorschläge,
- Fehler und Abbrüche.

Vorhandene LLM-Daten werden separat übernommen:

- Aufrufe,
- Prompt Tokens,
- Completion Tokens,
- Total Tokens,
- Kosten,
- Laufzeit,
- Fehler/Timeouts.

Für Delivery werden zusätzlich deterministische Felder, LLM-Felder, offene Gaps,
Konflikte und manuell korrigierte Felder gezählt.

## 7. Reset und Isolation

Vor jedem Lauf wird ausschließlich der jeweilige `[BENCHMARK-*]`-Datensatz auf den
definierten Startzustand zurückgesetzt. Real-DEMO-Daten werden nicht als veränderliche
Arbeitskopie verwendet.

Benchmark-Nutzer dürfen keine realen Empfänger adressieren. Benchmark-Audits bleiben bei
den isolierten Benchmark-Objekten. Produktive oder manuell gepflegte Real-Daten werden
nicht zurückgesetzt oder überschrieben.

## 8. Operator und Limitation

Die Messung ist als kontrollierte **Einzeloperator-Messung mit systemkundigem Operator**
definiert. Warm-up und Reihenfolgewechsel reduzieren Lern- und Reihenfolgeeffekte, beseitigen
aber weder Vertrautheit mit der Anwendung noch Erinnerung an den Fall.

AP 10 muss diese Limitation unabhängig vom Ergebnis ausweisen.

## 9. Drift-Regel

`tests/test_block9_benchmark_fixture.py` prüft die kanonische SHA-256-Prüfsumme der
vollständigen JSON-Fixture sowie die wesentlichen invarianten Messregeln.

Änderungen an Faktenset, Scoring-Feldern, Reihenfolge, Start-/Stop-Regeln oder
Qualitätskriterien erfordern eine neue Benchmark-Version. Eine Änderung derselben Version
nach Beginn der gewerteten Läufe ist unzulässig.
