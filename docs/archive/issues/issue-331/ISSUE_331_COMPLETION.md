# Issue #331 – Completion

**Issue:** #331 – Fokuswahl & Lösungsentscheidung: Evidenzstatus, Time-to-Value und No-AI-Ausgang  
**PR:** #334 – `feat: Fokuswahl und technologieoffene Lösungsentscheidung (#331)`  
**Merge-Commit:** `28fbfc31f6a960d0c29a497192f809896ff136cc`  
**Abgeschlossen:** 22.08.2026

## Ergebnis

#331 schließt die methodische Lücke zwischen Value-Stream-/Prozessanalyse und einem gegebenenfalls daraus entstehenden KI-Use-Case. Die Discovery setzt KI nicht mehr implizit als Ergebnis voraus und macht die Belastbarkeit der Fokus- und Lösungsentscheidung expliziter nachvollziehbar.

Umgesetzt wurden insbesondere:

- hypothesenfähige Fokuswahl ohne Pflicht zu frühen Messwerten;
- eigenes Fokuskriterium **Verbesserungspotenzial**, getrennt vom **Veränderungsaufwand**;
- explizites **Time-to-Value** als qualitativer Trade-off statt automatischer Rangfolge;
- persistente **Evidenzbasis** als Hypothese, Indiz oder Messwert/Nachweis;
- Wiederverwendung von `ProcessValidation`, Provenance sowie Version-/Stale-Mechanismen für fachliche Validierung und Herkunft;
- technologieoffener Lösungsraum mit organisatorischen, klassischen, KI- und hybriden Optionen;
- explizite KI-Komponenten-Semantik für hybride beziehungsweise uneindeutige Lösungstypen;
- korrigierte KI-Pfad-Klassifikation für Custom-/Other-Optionen;
- immutable Vergleichs-, Diagnose- und Evidenz-Snapshots der Lösungsentscheidung;
- gültiger **No-AI-Ausgang**: eine bevorzugte Non-AI-Lösung beendet Discovery erfolgreich und erzwingt keinen KI-Use-Case;
- bestehende Lifecycle-, Governance-, Retirement- und Delivery-Invarianten bleiben bestehen; keine automatischen Deletes oder Resets.

## Bewusst nicht gebaut

- keine zweite allgemeine Evidence-/Validation-Engine;
- keine neue Portfolio- oder TTV-Scoring-Engine;
- keine automatische gewichtete Rangfolge;
- keine automatische KI-Empfehlung;
- kein verpflichtendes AI-Suitability-Gate vor dem Lösungsraum;
- keine starre Kaskade `Standardisierung → Automation → KI`;
- keine automatische bindende Lösungsentscheidung durch LLM;
- keine automatische Use-Case-Anlage aus einer KI-Option;
- keine künstlichen Baselines oder erfundenen TTV-Werte;
- keine neue Governance-/Freigabe-Parallelstruktur;
- kein Render-Deployment im Scope von #331.

## Tests und CI

Der finale PR-Head `991cb72d0ec63c74b6588292025d165f49695c7d` bestand CI #1558 vollständig.

Grün waren unter anderem:

- Lockfile-Prüfung und Dependency-Installation;
- Ruff lint und format;
- Django System Check;
- Migrationsprüfung und Migrationen;
- Architecture Real-DEMO E2E;
- vollständige Test-Suite mit **1300 Tests**;
- Bandit;
- Dependency Audit;
- Local-, Production- und Staging-Compose-Validierung;
- Production- und Development-Image-Build.

Die Regressionstests decken insbesondere Fokus-Snapshot, Verbesserungspotenzial, Evidenz/TTV, technologieoffenen Lösungsvergleich, Hybrid-/AI-Komponenten-Semantik, Non-AI-Journey und bestehende Diagnose-/Governance-Verträge ab.

## Abnahmehinweis

Das ursprüngliche Issue verlangte zusätzlich einen manuellen lokalen E2E-/UI-Durchlauf für den neutralisierten #310-Demo-Case plus No-AI-/Hybrid-Gegenfall. Dieser Browserlauf konnte in der damaligen Ausführungsumgebung nicht glaubwürdig durchgeführt werden und wurde deshalb nicht fingiert.

Die relevanten Verhaltenspfade wurden automatisiert nachgewiesen: #310 Real-DEMO E2E, No-AI-Journey, Hybrid-Semantik sowie UI-/Template-Regressionsverträge waren grün.

Der **manuelle lokale #310-Durchlauf bleibt als eigenständiger Demo-/Abnahmeschritt offen** und soll auf dem nach #331 aktualisierten Produktstand durchgeführt werden. Render ist davon getrennt und kein Blocker für die lokale Demo.

## Folgepflege

Im selben Post-Merge-Dokumentationspaket wurden die aktiven Referenzdokumente `DECISION_METHOD.md`, `DISCOVERY_ARCHITECTURE.md`, `VALUE_STREAM_METHODOLOGY.md`, `ROADMAP.md` und `planning/EXECUTION_PLAN.md` auf die neue #331-Semantik synchronisiert. Das offene Demo-Runbook #310 erhält ergänzend einen Issue-Nachtrag für die neuen Fokus- und Lösungsdimensionen.
