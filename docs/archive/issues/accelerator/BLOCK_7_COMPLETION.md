# Accelerator Block 7 – Abschlussnachweis

## 1. Ergebnis

Block 7 ergänzt den Accelerator-MVP um einen begrenzten generativen Lösungsvergleich aus einer
bestehenden `ProcessAnalysis`. Genau drei lösungsoffene Entwürfe werden in einem strukturierten
LLM-Aufruf erzeugt, serverseitig fail-closed validiert, mit Quellen und Unsicherheiten als
Preview angezeigt und erst nach expliziter Nutzeraktion atomar in reguläre `SolutionOption`-
Objekte übernommen.

Das LLM erzeugt Kandidaten, keine Entscheidung. Bewertung, Rangfolge, bevorzugte Option,
Entscheidungsbegründung, Governance, Delivery und Lifecycle bleiben in den bestehenden manuellen
Pfaden.

## 2. Sequenzielle Umsetzung

| Paket | Pull Request | Ergebnis |
|---|---:|---|
| Arbeitsplan | #192 | Verbindlicher Block-7-Plan und Gap-Analyse |
| AP 1 | #193 | Bewertungsneutralität und Vergleichskompatibilität |
| AP 2 | #194 | Readiness, Source Snapshot und Datenminimierung |
| AP 3 | #195 | Generierungsvertrag, Prompt-Datentrennung und Provenance |
| AP 4 | #196 | Laufpersistenz, Quoten und Nebenläufigkeit |
| AP 5 | #197 | Einmalige strukturierte LLM-Generierung |
| AP 6 | #198 | Fail-closed Validierung und Halluzinationsgrenzen |
| AP 7 | #199 | Preview- und Bearbeitungs-UI |
| AP 8 | #200 | Atomare Übernahme in reguläre Lösungsoptionen |
| AP 9 | #201 | Sicherheits-, Ausfall- und Gate-Regression |
| AP 10 | dieser PR | Real-DEMO, Drift-Schutz und Blockabschluss |

Issue #116 bleibt unverändert.

## 3. Fachliche Blockgrenze

Version 1 unterstützt genau drei feste Lösungsrichtungen:

1. organisatorische Änderung,
2. regelbasierte Automatisierung,
3. Assistenzlösung.

Das LLM darf ausschließlich folgende vorhandene Vergleichsfelder formulieren:

- `name`,
- `description`,
- `expected_value`,
- `bottleneck_coverage`,
- `data_requirements`,
- `application_impact`,
- `integration_impact`,
- `technology_constraints`,
- `risks`,
- `architecture_fit`.

Nicht generiert werden `feasibility`, `integration_effort`, `evaluation_status`,
`recommendation`, Rangfolge, Präferenz, Auswahlbegründung oder Governance-Entscheidungen.
Bei der Übernahme werden die ausgewählten Optionen explizit als `draft`, `candidate`,
`not_assessed` und `not_assessed` angelegt.

## 4. Readiness, Quellen und Datenminimierung

Die Generierung ist nur möglich, wenn exakt die elf verpflichtenden Prozessfelder befüllt sind:

`name`, `scope_start`, `scope_end`, `trigger`, `outcome`, `current_flow`, `roles`, `systems`,
`data_objects`, `bottlenecks`, `baseline_metrics`.

Eine formale `ProcessValidation` ist bewusst kein zusätzliches KI-Gate. Ihr Zustand wird als
`current_validated`, `not_validated` oder `validation_stale` sichtbar mitgeführt.

Der Provider erhält nur den whitelisted Source Snapshot mit stabilen Source-IDs, Prozessversion
und Source-Hash. Interne IDs, Benutzerinformationen und nicht benötigte Objekte werden nicht in
den Provider-Payload aufgenommen.

## 5. Prompt- und Provenance-Vertrag

Systeminstruktion und Prozessdaten sind getrennt. Prozessfreitext wird ausschließlich als
`untrusted_source_data` übergeben; eingebettete Rollen-, System- oder Formatbefehle werden nicht
zu Systeminstruktionen.

Jede generierte Aussage enthält zwingend:

- Text,
- Source-IDs,
- Annahmen,
- offene Evidenz,
- Unsicherheitsstufe und Begründung.

Unbekannte Source-IDs, zusätzliche Lanes oder Felder, verbotene Bewertungsfelder und nicht durch
referenzierte Quellen belegte quantitative Angaben werden vollständig verworfen.

## 6. Lauf, Quoten und Providerpfad

`SolutionGenerationRun` hält den schmalen technischen Laufnachweis einschließlich Source-Version
und Hash, Provider/Modell, Prompt-/Schema-Version, Token-, Kosten-, Größen- und Laufzeitmetadaten.
Die bestehende `AcceleratorLLMQuota` wurde für `ProcessAnalysis` als Context wiederverwendet.

Pro Prozessanalyse darf höchstens ein aktiver Lauf existieren. Ein konkurrierender Zweitstart
wird vor zusätzlichem Provideraufruf und zusätzlichem Quotenverbrauch abgewiesen.

Für ein vollständiges Drei-Optionen-Bundle gibt es exakt einen OpenRouter-Aufruf. Es existiert
keine automatische Retry-Schleife.

## 7. Preview und Bearbeitung

Die Preview zeigt die gemeinsame eingefrorene Ausgangslage einmal und stellt die drei Entwürfe
gleichrangig als responsive Karten dar. Pro Entwurfsfeld bleiben Quellen, Annahmen, offene
Evidenz und Unsicherheit sichtbar.

Nutzer können ausschließlich die freigegebenen Entwurfstexte bearbeiten. Die Änderungen werden
als menschliche Deltas getrennt vom validierten Provideroutput gespeichert. Stale, abgelaufene,
unvollständige oder bereits übernommene Previews sind nicht mehr bearbeitbar.

## 8. Atomare Übernahme

Die Generierung liefert weiterhin exakt drei Entwürfe. In der Preview wählt der Nutzer jedoch
explizit 1–3 Vorschläge für die Übernahme aus. Innerhalb der Transaktion werden Berechtigung,
Quellversion, Source-Hash, Readiness, Previewvertrag und menschliche Bearbeitungen erneut geprüft.

Alle ausgewählten `SolutionOptionForm`-Instanzen müssen vor dem ersten Fachobjektschreibvorgang
gültig sein. Persistenzfehler rollen die gesamte ausgewählte Teilmenge zurück. Der
Übernahmenachweis speichert die übernommenen Lanes und Option-IDs atomar im Generation-Run;
Wiederholung derselben Übernahme erzeugt keine Duplikate.

Die übernommenen Optionen bleiben danach regulär über die bestehenden fachlichen Pfade
bearbeitbar und bewertbar.

## 9. Sicherheits-, Ausfall- und Gate-Schutz

Die Regression deckt unter anderem ab:

- fehlende Pflichtquellen,
- widersprüchliche Daten,
- Prompt Injection in Prozessfreitext,
- unbekannte Source-IDs und zusätzliche Optionstypen,
- verbotene Bewertungsfelder,
- unbelegte quantitative Erfindungen,
- Provider-/Autorisierungsfehler, Rate Limit, Timeout, ungültiges JSON und abgeschnittene Antwort,
- konkurrierende Generierung,
- stale Preview,
- Rollback und idempotente Doppelübernahme,
- Rückwärtskompatibilität bestehender manueller Optionen,
- unveränderten expliziten `select_preferred_solution`-Pfad.

Keine dieser Accelerator-Aktionen erzeugt automatisch `ProcessValidation`,
`SolutionSelectionDecision`, Use-Case-, Governance-, Delivery- oder Lifecycle-Entscheidungen.

## 10. Reproduzierbarer `[Real-DEMO]`

Der Management-Command

`python manage.py run_block7_real_demo --output <pfad>`

setzt zuerst den realen Block-6-`Angebotsvergleich` als funktionale Ausgangslage auf. Danach
läuft der produktive Block-7-Pfad:

`build source context -> generate_solution_preview -> server validation -> preview -> adopt_solution_generation_bundle`.

Nur die externe Providergrenze wird für CI und Drift-Nachweis deterministisch ersetzt. Der
Real-DEMO bestätigt:

- genau einen Provideraufruf für das gesamte Bundle,
- genau drei Lanes,
- sichtbare Quellen, Annahmen, offene Evidenz und Unsicherheit,
- genau drei übernommene reguläre Lösungsoptionen,
- alle drei Optionen `draft`, `candidate` und in beiden Aufwandsfeldern `not_assessed`,
- keine automatische Prozessvalidierung oder Auswahlentscheidung,
- unveränderte Use-Case-, Governance-, Delivery- und Lifecycle-Gates.

Ein getrennter Rollback-Nachweis lässt den zweiten `SolutionOption.save()` gezielt scheitern.
Danach existiert für den Rollback-Prozess keine Option und kein Übernahmenachweis.

## 11. Drift-Schutz

Die kanonische Referenz liegt unter:

- `tests/fixtures/accelerator/block7_real_demo.v1.json`
- `tests/fixtures/accelerator/block7_real_demo.v1.sha256`

SHA-256 der Version 1:

`ed05ee8c45677cf889f97537bcda370b34136e3cb86062ce4c417215e4604d48`

Der Regressionstest berechnet die Prüfsumme aus den tatsächlichen JSON-Bytes neu. Referenz und
Prüfsumme müssen bei einer bewussten fachlichen Änderung gemeinsam aktualisiert werden.

## 12. UI-Evidenz

Der AP-10-Test öffnet nach dem real ausgeführten Generierungs- und Übernahmepfad die produktive
Preview sowie den bestehenden Lösungsvergleich.

Für die Preview wird nachgewiesen:

- gemeinsame Ausgangslage und Real-DEMO-Prozessinhalt sichtbar,
- Quellen, Annahmen, offene Evidenz und Unsicherheit sichtbar,
- alle drei Lösungsrichtungen sichtbar,
- übernommene Preview klar gesperrt,
- responsive `col-12 col-xl-4`-Karten,
- keine HTML-Tabelle und keine feste `min-width` als Preview-Layout.

Im bestehenden Lösungsvergleich sind alle drei regulären Optionen anschließend sichtbar.

## 13. Abnahmekriterien aus Issue #123

| Abnahmekriterium | Ergebnis | Nachweis |
|---|---|---|
| Gap-Analyse dokumentiert | erfüllt | `BLOCK_7_WORKPLAN.md`, AP 1 |
| Drei vergleichbare, lösungsoffene Entwurfsoptionen erzeugbar | erfüllt | Generierungsvertrag, Provider-/Validierungstests und Block-7-Real-DEMO |
| Quellen, Annahmen, Lücken und Unsicherheiten sichtbar | erfüllt | Preview-UI-Tests und Block-7-Real-DEMO |
| Gemeinsame Fakten nicht unnötig vom LLM neu erfunden | erfüllt | deterministischer Source Snapshot, Source-ID-Vertrag und quantitative Fail-closed-Validierung |
| Keine Option automatisch bewertet oder bevorzugt | erfüllt | Neutralitäts-, Adoption-, Gate- und Real-DEMO-Tests |
| Ausfall und Rate Limit ohne Teil- oder Statusänderungen | erfüllt | Provider-, Rollback- und Gate-Regression |
| Tests für fehlende Quellen, widersprüchliche Daten, Erfindungen und Gate-Schutz | erfüllt | AP-2-, AP-6- und AP-9-Regression |
| Lösung auf bestehenden Lösungsvergleich begrenzt | erfüllt | drei feste Lanes, regulärer `SolutionOptionForm`-Pfad, unveränderter manueller Auswahlservice |

## 14. Testmatrix nach Kategorie

Der finale Blockstand enthält dedizierte Regressionen für:

- Readiness und Source Snapshot,
- Prompt-Datentrennung und Provenance,
- Quoten und Nebenläufigkeit,
- genau einen strukturierten Provideraufruf sowie Providerfehler,
- fail-closed Vertrags- und Halluzinationsgrenzen,
- Preview und responsive Bearbeitung,
- Atomarität, Rollback und Idempotenz,
- Rückwärtskompatibilität und Gate-Invarianz,
- Real-DEMO, Reproduzierbarkeit und SHA-256-Drift-Schutz.

Die vollständige Repository-CI führt zusätzlich alle bestehenden Regressionstests aus.

## 15. Dokumentierte technische Abweichungen vom Workplan

Es gab keine fachliche Scope-Erweiterung. Dokumentierte technische Realisierungsabweichungen:

1. AP 2 verwendet kleine `__slots__`-Klassen statt Dataclasses für den Source Context; Semantik
   und Vertrag bleiben identisch.
2. AP 3 modelliert die drei Lanes als festes Schlüsselobjekt statt als freie Liste. Dadurch ist
   die Forderung nach exakt drei Standardoptionen bereits strukturell strenger abgesichert.
3. AP 8 verzichtet beim PostgreSQL-`SELECT FOR UPDATE` auf einen nullable `select_related`-
   Outer-Join; Prozess und Generation-Run bleiben in stabiler Reihenfolge gesperrt.
4. AP 8 respektiert für die spätere normale Bearbeitung weiterhin das bestehende
   Value-Stream-Fokus-Gate; der Test richtet den bestehenden Fokus ein, statt ihn zu umgehen.
5. AP 9 ergänzt querschnittliche Gate-/Kompatibilitätsregressionen und nutzt für einzelne
   Provider- und Vertragsfehler bewusst die bereits vorhandenen AP-5/AP-6-Tests weiter, statt
   identische Fälle zu duplizieren.
6. AP 10 ersetzt ausschließlich die externe Providerantwort deterministisch. Source-Aufbau,
   Generierungsservice, Validierung, Preview-Persistenz und atomare Übernahme bleiben produktive
   Pfade.

Ruff-/Format- und Testkorrekturen während einzelner PRs waren technische CI-Korrekturen und
änderten die fachliche Blockgrenze nicht.

## 16. Definition of Done

Block 7 ist abgeschlossen, wenn der AP-10-PR mit unveränderter vollständiger Repository-CI grün
gemergt ist, der anschließende `main`-Lauf ebenfalls vollständig grün ist und Issue #123 mit
allen zehn Arbeitspaketen geschlossen wird.

Die Repository-CI bleibt unverändert und prüft repository-weit Ruff, `ruff format --check .`,
Django-Systemcheck, Migrationen, vollständige Tests, Bandit, Dependency Audit, alle Compose-
Konfigurationen sowie Produktions- und Entwicklungs-Image-Build.
