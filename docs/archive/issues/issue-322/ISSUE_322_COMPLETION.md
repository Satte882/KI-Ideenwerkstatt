# Issue #322 – Completion

**Stand:** 22.08.2026  
**Issue:** #322 – Use Case optional mit Ursprungsprozess verknüpfen und strategischen Value-Stream-Kontext ableiten

## Ergebnis

Issue #322 wurde reuse-first über die bereits vorhandene `UseCaseOrigin`-Relation umgesetzt. Es entstand **kein** neues Prozess-, Stage-, Value-Stream- oder Strategiefeld am `UseCase` und deshalb auch keine Datenmigration.

Die kanonische Kette lautet bei vorhandenem Prozessbezug:

```text
UseCase
→ UseCaseOrigin
→ ProcessAnalysis
→ ValueStreamStage
→ ValueStream
→ ValueStreamFocus / strategic_objective
```

Use Cases ohne Prozess- oder Discovery-Ursprung bleiben unverändert gültig.

Die vorausgehende Gap-Analyse ist in [`ISSUE_322_GAP_ANALYSIS.md`](ISSUE_322_GAP_ANALYSIS.md) archiviert.

## Umgesetzte Änderungen

### Direkter Intake

Schritt 2 des bestehenden sechs-stufigen Intake-Wizards bietet optional eine vorhandene `ProcessAnalysis` als **Ursprungsprozess** an.

- Die Auswahl wird auf die in Schritt 1 gewählte Organisationseinheit eingeschränkt.
- Bei einem aus einer Value-Stream-Phase gestarteten Intake werden nur Prozesse dieser Phase angeboten.
- Bei einem aus einer bevorzugten KI-Lösungsoption gestarteten Intake ist der bereits bekannte Discovery-Prozess gesperrt und kann im Wizard nicht auf einen anderen Prozess umgebogen werden.
- Wird ein Prozess gewählt, wird `affected_process` aus `ProcessAnalysis.name` abgeleitet; eine zweite manuelle Pflege desselben Prozessnamens ist nicht erforderlich.
- Ohne Prozessauswahl bleibt die bestehende Freitext-Erfassung von `affected_process` möglich.

### Persistenz und Konsistenz

`UseCaseOrigin` bleibt die einzige kanonische Herkunftsrelation.

Vor dem Anlegen des Ursprungs werden serverseitig geprüft:

- Prozess ↔ Stage,
- Discovery-Stage ↔ Discovery-Prozess,
- Discovery-Lösungsoption ↔ Discovery-Prozess,
- Ursprungs-Value-Stream ↔ Organisationseinheit des Use Cases,
- abgeleiteter Prozessname ↔ `affected_process`.

Discovery-Herkunft besitzt Vorrang vor einem gegebenenfalls manipulierten manuellen Session-Wert. `UseCase` und `UseCaseOrigin` werden atomar gespeichert; eine inkonsistente Herkunft hinterlässt keinen halb angelegten Use Case.

Die bereits vorhandenen `PROTECT`-Beziehungen von `UseCaseOrigin` auf Stage, Prozessanalyse und Lösungsoption bleiben unverändert.

### Klassifikation

Die bestehende Signal-Logik `inherit_classification_from_discovery` wird wiederverwendet. Besitzt der zugehörige Value Stream einen `ValueStreamFocus`, werden Fachdomäne, Capability und Prozessbereich weiterhin aus diesem kanonischen Fokuskontext in die operative `UseCaseClassification` übernommen.

Es wurde bewusst **kein** zusätzlicher Synchronisationsmechanismus bei späteren Änderungen des `ValueStreamFocus` eingeführt. Das wäre eine allgemeine Klassifikations-/Synchronisationsfrage und liegt außerhalb von #322.

### Strategischer Kontext in der Detailansicht

Die bestehende Use-Case-Detailansicht zeigt bei vorhandenem Ursprung zusätzlich read-only:

- Value Stream,
- Phase,
- Prozessanalyse,
- gegebenenfalls Lösungsoption,
- `ValueStream.strategic_objective`,
- Fachdomäne,
- Business Capability,
- strategischen Impact aus `ValueStreamFocus`.

Dafür wurde keine zweite Persistenz und kein mutierender Read-Helper eingeführt; die bereits geladene kanonische Relation wird direkt gelesen.

## Bewusste Nicht-Änderungen

Nicht Bestandteil der Umsetzung sind:

- direkte `UseCase.process_analysis`-Foreign-Key,
- redundante `UseCase.value_stream`-, `UseCase.stage`- oder Strategiefelder,
- heuristisches oder LLM-basiertes Backfill bestehender Use Cases,
- neue Strategie-/Business-Driver-Metamodelle,
- neue Prozess-Retirement-Logik,
- allgemeine Synchronisation historischer `UseCaseClassification`-Snapshots,
- Änderungen an Bewertung, Governance, Delivery oder Lifecycle,
- Änderung der #331-Regel: Nur eine ausdrücklich bevorzugte Lösung mit tatsächlicher KI-Komponente darf den KI-Use-Case-Pfad starten; Non-AI bleibt ein gültiger Abschluss ohne Use Case.

## Berücksichtigtes externes Review

Das externe Review wurde als Prüfinput bewertet, nicht als Pflichtumfang.

Übernommen wurden:

1. finale BU-Konsistenzprüfung wegen möglichem Wizard-Backtracking,
2. expliziter Schutz des bereits bekannten Discovery-Ursprungs,
3. Regressionstest für die bestehende Klassifikationsvererbung.

Nicht übernommen wurde ein neuer `ValueStreamFocus.post_save`-Synchronisationsmechanismus, da er den Scope von #322 zu einer allgemeinen Synchronisationsarchitektur erweitert hätte.

## Testabdeckung

Issue-spezifische Tests decken ab:

- Prozessauswahl nur innerhalb der gewählten Organisationseinheit,
- Ableitung von `affected_process` aus dem Ursprungsprozess,
- gesperrten Discovery-Prozess,
- direkten Intake mit Prozessbezug Ende-zu-Ende,
- Vorrang der Discovery-Herkunft vor manipuliertem Session-Wert,
- Ablehnung eines Ursprungs nach BU-Wechsel,
- abgeleiteten strategischen Kontext in der Detailansicht,
- fehlende redundante Prozess-/Strategiefelder am `UseCase`,
- `PROTECT` für verknüpfte Prozessanalysen.

Die bestehende Guided-Intake-Regression deckt weiterhin den direkten Intake **ohne** Prozessbezug ab. Die vorhandenen Discovery- und #331-Tests bleiben die Regression für automatische Herkunft beziehungsweise den No-AI-Ausgang.

## Migration

Keine Migration erforderlich. `UseCaseOrigin.process_analysis` existierte bereits optional; #322 schloss die verbleibende Intake-, Validierungs- und Sichtbarkeitslücke durch Wiederverwendung dieser Relation.

## Abschlussnachweis

- **Pull Request:** #337 – `feat: Use Cases mit kanonischem Ursprungsprozess verknüpfen (#322)`
- **Merge nach `main`:** 22.08.2026
- **Merge-Commit:** `b1dc7b0295c2cc457fdb70e1044c518ae0f2960f`
- **Issue:** #322 wurde durch den Merge geschlossen.
- **Finaler PR-CI-Lauf:** #1564 vollständig erfolgreich.

CI #1564 umfasste erfolgreich Ruff Lint und Format, Django System Check, Migrationsprüfung und -anwendung, Architecture Real-DEMO E2E, die vollständige Testsuite, Bandit, Dependency Audit, lokale/Production-/Staging-Compose-Prüfungen sowie Production- und Development-Docker-Builds.

Der vorausgehende CI-Lauf #1563 war vollständig beendet worden, bevor eine Korrektur erfolgte. Der einzige konkrete Fehler war `ruff format --check` für `ki_radar/use_cases/intake_views.py`; nach Auswertung des vollständigen Logs wurde dieser blockierende Formatfehler in einem einzelnen Fix-Commit korrigiert. Erst danach wurde CI #1564 gestartet und vollständig grün abgeschlossen.
