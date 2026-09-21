# Issue #322 – Gap-Analyse vor Umsetzung

**Stand:** 22.08.2026  
**Issue:** #322 – Use Case optional mit Ursprungsprozess verknüpfen und strategischen Value-Stream-Kontext ableiten

## Ziel der Analyse

Vor der Implementierung wurde der damalige `main` gegen das Issue geprüft, um die kleinste belastbare reuse-first Lösung zu bestimmen. Maßgeblich war die Frage, ob für die gewünschte Traceability ein neues Datenmodell benötigt wird oder ob vorhandene Architecture- und Discovery-Relationen ausreichen.

## Ergebnis in einem Satz

Die benötigte fachliche Hierarchie und die kanonische Herkunftsrelation existierten bereits. Die tatsächliche Lücke lag im **direkten Intake, in der konsistenten Übernahme des Discovery-Ursprungs und in der Sichtbarkeit des abgeleiteten strategischen Kontexts**, nicht im Datenmodell.

## 1. Bereits vorhandene kanonische Struktur

Die Architecture-Domäne verfügte bereits über die für #322 erforderlichen Objekte und Relationen:

```text
ValueStream
→ ValueStreamStage
→ ProcessAnalysis
→ SolutionOption
```

Zusätzlich existierte bereits `UseCaseOrigin` als kanonische Herkunft eines Use Cases mit:

- `use_case` als One-to-One-Relation,
- `stage` als geschützter Bezug auf `ValueStreamStage`,
- optionaler `process_analysis` als geschützter Bezug auf `ProcessAnalysis`,
- optionaler `solution_option` als geschützter Bezug auf `SolutionOption`.

Damit war **keine neue `UseCase.process_analysis`-Foreign-Key** erforderlich.

## 2. Strategischer Kontext war bereits ableitbar

Der übergeordnete fachliche und strategische Kontext lag bereits an der bestehenden Architecture-Hierarchie:

- `ValueStream.strategic_objective`,
- `ValueStreamFocus.business_domain`,
- `ValueStreamFocus.capability`,
- strategischer Impact des Fokuskontexts.

Bei bekanntem Prozess lässt sich damit die Kette

```text
ProcessAnalysis
→ ValueStreamStage
→ ValueStream
→ strategisches Ziel / Fokuskontext
```

bereits eindeutig auflösen. Ein zusätzliches Strategiefeld am Use Case hätte denselben Sachverhalt redundant persistiert und neue Synchronisationsprobleme erzeugt.

## 3. Discovery kannte den Ursprung bereits

Die geführte Discovery-Journey transportierte bereits Herkunftsinformationen beim Start des Use-Case-Intakes:

- `source_stage_id`,
- bei Start aus einer Lösungsoption zusätzlich `source_process_analysis_id`,
- `source_solution_option_id`.

Die vorhandene Herkunft durfte deshalb nicht durch eine zweite manuelle Auswahl ersetzt oder überschrieben werden. Die Lücke bestand darin, den bekannten Prozess im Intake verbindlich zu übernehmen und die bestehende Provenance zu schützen.

## 4. Direkter Intake hatte die eigentliche UX-Lücke

Direkt angelegte Use Cases konnten weiterhin sinnvoll ohne Architecture-/Prozessbezug existieren. Das Issue verlangte deshalb bewusst **kein neues Pflicht-Gate**.

Fehlend war lediglich eine optionale Auswahl einer vorhandenen `ProcessAnalysis` im bestehenden Intake. Wenn eine solche Auswahl erfolgt, sollen Prozessname, Stage, Value Stream und strategischer Kontext aus der kanonischen Hierarchie stammen statt mehrfach manuell gepflegt zu werden.

## 5. Bestehende Klassifikationslogik konnte wiederverwendet werden

Mit `inherit_classification_from_discovery` existierte bereits eine Signal-Logik auf `UseCaseOrigin`, die aus dem vorhandenen `ValueStreamFocus` Fachdomäne, Capability und Prozessbereich in die operative `UseCaseClassification` übernimmt.

Für #322 war daher kein zweiter Klassifikations- oder Synchronisationsmechanismus erforderlich. Notwendig war lediglich, die bestehende Vererbung explizit als Regression abzusichern.

## 6. Konsistenzrisiken

Die Analyse identifizierte insbesondere folgende Risiken, die serverseitig abgesichert werden mussten:

1. **Business-Unit-Wechsel nach Prozessauswahl:** Wizard-Backtracking darf keinen Prozess aus einer anderen Organisationseinheit am Use Case belassen.
2. **Manipulierter manueller Session-Wert:** Ein bereits aus Discovery bekannter Prozess muss Vorrang vor einer nachträglich eingeschleusten manuellen Auswahl haben.
3. **Inkonsistente Discovery-Kette:** Stage, Prozess und Lösungsoption müssen weiterhin zueinander gehören.
4. **Teilweise Persistenz:** Ein ungültiger Ursprung darf keinen bereits gespeicherten Use Case ohne konsistente Herkunft hinterlassen.

Daraus folgte eine finale serverseitige Konsistenzprüfung und atomare Persistenz von Use Case und optionalem Ursprung.

## 7. Reuse-first Entscheidung

Aus der Gap-Analyse wurde folgende Umsetzung abgeleitet:

- `UseCaseOrigin` bleibt die einzige kanonische Herkunftsrelation;
- direkter Intake erhält eine **optionale** Prozessauswahl;
- Discovery-Ursprung wird automatisch übernommen und geschützt;
- Stage, Value Stream und strategischer Kontext werden nur abgeleitet beziehungsweise read-only angezeigt;
- bestehende `UseCaseClassification`-Vererbung wird weiterverwendet;
- bestehende `PROTECT`-Semantik bleibt erhalten;
- keine Migration und kein Backfill bestehender Use Cases.

## 8. Bewusst verworfene Erweiterungen

Nicht erforderlich beziehungsweise außerhalb des Scopes waren:

- neue direkte Prozess-, Stage-, Value-Stream- oder Strategiefelder am `UseCase`,
- ein neues Strategie-/Business-Driver-Metamodell,
- heuristische oder LLM-basierte Rückzuordnung bestehender Use Cases,
- ein neuer `ValueStreamFocus.post_save`-Synchronisationsmechanismus,
- Prozess-Retirement-Logik,
- Änderungen an Bewertung, Governance, Delivery oder Lifecycle.

## 9. Konsequenz für die Implementierung

Der technische Umfang konnte dadurch klein bleiben:

```text
bestehender Intake
+ optionale ProcessAnalysis-Auswahl
+ serverseitige Herkunftsvalidierung
+ UseCaseOrigin wiederverwenden
+ strategischen Kontext read-only ableiten
+ Regressionstests
```

Die Umsetzung brauchte **keine Schemaänderung**. Die ausführliche Abnahme und der technische Abschluss sind in [`ISSUE_322_COMPLETION.md`](ISSUE_322_COMPLETION.md) dokumentiert.
