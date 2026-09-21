# Accelerator Block 6 – Abschlussnachweis

## 1. Ergebnis

Block 6 erweitert den Accelerator-MVP um einen eng begrenzten Structured-Adoption-Pfad für
strukturierte Use-Case-Metriken, neue Value-Stream-Phasen und neue Prozessanalysen als Entwurf.

Der Block erzeugt keinen generischen Objektimporter. Jeder Provider-Vorschlag bleibt bis zur
sichtbaren Einzelentscheidung ein Vorschlag. Strukturierte Werte werden deterministisch
normalisiert, bestehende Django-Forms werden wiederverwendet und zusammengehörige
Schreibvorgänge werden atomar ausgeführt.

## 2. Sequenzielle Umsetzung

| Paket | Pull Request | Ergebnis |
|---|---:|---|
| Arbeitsplan | #176 | Verbindlicher Block-6-Plan und Gap-Analyse |
| AP 1 | #178 | Structured Contract, Feldfreigabe und Abhängigkeitsgraph |
| AP 2 | #182 | Typ-, Zahlen- und Ambiguitätsnormalisierung |
| AP 3 | #183 | Batch-, Item- und Audit-Persistenz |
| AP 4 | #184 | Metrik-Merge und feldbezogener Konfliktschutz |
| AP 5 | #185 | Value-Stream-Phasen und Cascade-Invalidierung |
| AP 6 | #186 | Prozessanalyse, lokale Referenzen und Herkunft |
| AP 7 | #187 | Atomare Orchestrierung, Lock-Reihenfolge und Idempotenz |
| AP 8 | #188 | Review-UI, Teilverwerfung und Bestätigung |
| AP 9 | #190 | Sicherheits-, Rollback- und Gate-Regression |
| AP 10 | dieser PR | Real-DEMO, Drift-Schutz und Blockabschluss |

Issue #116 bleibt unverändert.

## 3. Fachliche Blockgrenze

Aktiv unterstützt werden ausschließlich:

- die sieben freigegebenen Use-Case-Metrikfelder,
- `ValueStreamStage`-Entwürfe aus den katalogisierten Phasenfeldern,
- `ProcessAnalysis`-Entwürfe aus den katalogisierten Prozessfeldern,
- eine explizite Prozessreferenz auf eine bestehende zulässige Phase oder einen lokalen
  Phasenschlüssel desselben Batches.

Nicht Teil des Blocks sind insbesondere:

- generische Schema- oder Objektgraph-Generatoren,
- automatische Rollen- oder Personenauflösung,
- Fokus-, Prozessvalidierungs-, Lösungs-, Governance- oder Lifecycle-Entscheidungen,
- Sammelübernahme ohne Einzelprüfung,
- der alte Scenario-Blueprint-Importer als Nutzerpfad.

## 4. Normalisierung und Review

Vor jeder Übernahme werden Original, Vorschlag, kanonische Interpretation, Datentyp,
Einheit und Validierungsstatus getrennt gehalten und in der Review-UI dargestellt.

Die Normalisierung ist fail-closed:

- deutsche Dezimal- und Tausenderformate werden nur bei eindeutiger Schreibweise übernommen,
- Einheiten werden nur über statische Aliaslisten kanonisiert und nicht umgerechnet,
- Enums akzeptieren nur kanonische Werte oder dokumentierte eindeutige Aliase,
- mehrdeutige Werte bleiben `ambiguous`,
- nicht katalogisierte Boolean-, Datums- und Referenzziele werden nicht aktiviert.

Jedes Item wird einzeln bestätigt, bearbeitet bestätigt oder verworfen. Ein
„Alle übernehmen“-Pfad existiert nicht.

## 5. Metrik-Merge

Der Metrik-Commit bildet den vollständigen effektiven Metrikzustand aus zwei Quellen:

- bestätigte Vorschläge beziehungsweise bestätigte Bearbeitungen,
- aktuelle Datenbankwerte für nicht ausgewählte oder verworfene Felder.

Nur bestätigte Felder ersetzen den aktuellen Datenbankwert. Unmittelbar vor dem Schreiben
werden die Feldsnapshots geprüft und der vollständige Payload durch `UseCaseForm` validiert.

Im AP-10-Real-DEMO wird nachgewiesen:

- `metric_baseline`: bestätigt und von `10` auf `11` geändert,
- `metric_target`: verworfen und daher unverändert `8.25`,
- `metric_measurement_method`: bestätigt und aktualisiert.

## 6. Phasen, Prozessanalyse und Cascade

Der Real-DEMO erzeugt über Structured Adoption genau drei Phasen:

1. Bedarf klären
2. Angebote vergleichen
3. Bestellung auslösen

Die Prozessanalyse `Angebotsvergleich` referenziert die neue Phase
`local:stage-02`.

Der Abschlusslauf bestätigt außerdem die Cascade-Regel:

1. Phase 2 und die abhängige Prozessanalyse werden bestätigt.
2. Phase 2 wird verworfen.
3. Die Prozessanalyse wird serverseitig `dependency_invalid` und verliert ihre Bestätigung.
4. Phase 2 wird erneut bestätigt.
5. Die Prozessanalyse muss ausdrücklich erneut bestätigt werden.
6. Erst danach ist der atomare Commit ausführbar.

Nach dem Commit existiert genau eine Prozessanalyse, sie gehört zur Phase
`Angebote vergleichen` und bleibt `draft`.

## 7. Atomarität und Rollback

Der Real-DEMO enthält einen getrennten Fehlerfall. Nach gültiger Bestätigung einer neuen
Phase und einer lokal abhängigen Prozessanalyse wird der Erfolgs-Audit-Schritt gezielt zum
Fehlschlagen gebracht.

Erwarteter und im Referenzartefakt festgeschriebener Zustand:

- Batchstatus `failed`,
- Fehlercode `unexpected_commit_failure`,
- Fehler-Step `orchestration`,
- keine Phase persistiert,
- keine Prozessanalyse persistiert.

Damit bleibt bei einem Fehler in den letzten Transaktionsschritten kein Teilgraph zurück.

## 8. Ausschluss des alten Blueprint-Importers

`tests/test_block6_completion.py` ersetzt für den Real-DEMO per Spy sowohl
`scenario_blueprint_apply.apply_blueprint` als auch die in `scenario_blueprint_run`
gebundenen Blueprint-Einstiege durch eine Funktion, die sofort fehlschlägt.

Der vollständige Block-6-Real-DEMO läuft trotzdem erfolgreich und meldet:

- `path = structured_adoption`,
- `legacy_blueprint_importer_used = false`,
- keine Spy-Aufrufe.

Damit ist direkte und indirekte Nutzung des alten Blueprint-Importers im Block-6-Nutzerpfad
explizit regressiv ausgeschlossen.

## 9. Reproduzierbarer `[Real-DEMO]`

Der Management-Command

`python manage.py run_block6_real_demo --output <pfad>`

erzeugt einen deterministischen Abschlussbericht ohne externe Provideraufrufe. Er verwendet
reale Datenbankobjekte sowie die produktiven Structured-Adoption-Services:

`get_or_create_review_batch -> decide_review_item -> commit_review_batch`

Der Command wird im Test zweimal ausgeführt. Beide Ergebnisse müssen byte-inhaltlich dieselbe
fachliche Referenz ergeben.

## 10. Drift-Schutz

Die kanonische Referenz liegt unter:

- `tests/fixtures/accelerator/block6_real_demo.v1.json`
- `tests/fixtures/accelerator/block6_real_demo.v1.sha256`

SHA-256 der Version 1:

`063af47b2bbd85b030d058ac4c5853228e2a2874a6184c82dbf8e38ee85703ad`

Der Regressionstest berechnet die Prüfsumme aus den tatsächlichen JSON-Bytes neu. Jede
stille Änderung des Referenzartefakts schlägt fehl, bis Referenz und Prüfsumme bewusst
gemeinsam aktualisiert werden.

## 11. Gate-Postconditions

Der Abschlussbericht schreibt folgende Postconditions fest:

- Value Stream bleibt `draft`,
- Use Case bleibt `idea`,
- Use-Case-Entscheidung bleibt `clarification`,
- keine `ProcessValidation`,
- keine `SolutionOption`,
- keine `SolutionSelectionDecision`.

Damit setzt Block 6 weder rote Entscheidungen noch Bestätigungen oder Folge-Gates.

## 12. UI-Evidenz

Der AP-10-Test öffnet nach dem real ausgeführten Structured-Adoption-Durchlauf die produktive
Review-Seite und prüft den konkreten Real-DEMO-Inhalt einschließlich aller drei Phasen und der
Prozessanalyse.

Zusätzlich bleiben die in AP 9 eingeführten Responsive-Regressionen Bestandteil der
vollständigen Repository-CI. Für die Review-Seite werden weiterhin ausgeschlossen:

- HTML-Tabellen als Layout,
- horizontaler Overflow,
- `white-space: nowrap`,
- feste `min-width`,
- fehlendes Wrapping beziehungsweise fehlende Textumbrüche.

Damit wird die Desktop-/Mobile-Leitplanke auf dem finalen Block-6-Stand erneut geprüft.

## 13. Sicherheits- und Regressionstestmatrix

Mit AP 1 bis AP 10 sind mindestens nachgewiesen:

- explizite Feld- und Typwhitelists,
- mehrdeutige Zahlen und Enums ohne automatische Übernahme,
- Fremdziel-, Stale- und Manipulationsschutz,
- feldbezogener Metrikkonfliktschutz,
- lokale Abhängigkeitsintegrität,
- Cascade-Invalidierung und notwendige erneute Bestätigung,
- feste Lock-Reihenfolge und Idempotenz,
- vollständiger Rollback bei terminalen Fehlern,
- unveränderte Gate-Zustände,
- responsive Review-UI,
- reproduzierbarer Real-DEMO ohne Blueprint-Importer,
- Referenzartefakt mit SHA-256-Drift-Schutz.

## 14. Definition of Done

Block 6 ist abgeschlossen, wenn der AP-10-PR mit unveränderter vollständiger Repository-CI
grün gemergt ist, der anschließende `main`-Lauf ebenfalls grün ist und Issue #122 mit allen
zehn Arbeitspaketen als erfüllt geschlossen wird.

Die Repository-CI bleibt unverändert und prüft repository-weit unter anderem Ruff,
`ruff format --check .`, Django-Systemcheck, Migrationen, vollständige Tests, Bandit,
Dependency Audit, alle Compose-Konfigurationen sowie Produktions- und Entwicklungs-Image-Build.
