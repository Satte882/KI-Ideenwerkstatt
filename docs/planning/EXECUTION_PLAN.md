# KI-Radar Execution Plan

**Stand:** 19.09.2026

**Zweck:** Konkrete Abarbeitungsreihenfolge offener Issues nach fachlichen und technischen Abhängigkeiten.

## Leitprinzip

Dieser Plan beantwortet nicht, welches Thema laut Produkt-Roadmap grundsätzlich wichtiger ist, sondern **in welcher Reihenfolge die offenen Arbeitspakete sinnvoll umgesetzt werden sollten, um Rework zu vermeiden**.

Entscheidend sind insbesondere:

- zuerst Domain-, Journey- und Entscheidungssemantik stabilisieren;
- danach Funktionen anbauen, die diese Semantik konsumieren;
- API-Verträge erst auf ausreichend stabilen internen Verträgen aufsetzen;
- Analyse-Issues vor nachgelagerten Implementierungen abschließen;
- E2E-Demo erst nach Abschluss des zusammengehörigen fachlichen Blocks durchführen;
- unabhängige Stränge parallelisieren, wenn keine relevante Kopplung besteht.

Die Produkt-Roadmap unter [`../ROADMAP.md`](../ROADMAP.md) bleibt davon getrennt und beschreibt Produktstand und strategische Richtung.

---

## Kürzlich abgeschlossen

**#351 – Discovery→Use-Case-Konsistenzprüfung** wurde am 23.08.2026 als dritter Schritt der First Wave abgeschlossen. Die Prüfung wird explizit durch den Nutzer gestartet, vergleicht den aktuellen Use Case read-only mit seiner belastbaren Discovery-Herkunft, arbeitet mit einer engen Context-Allowlist und source-gebundenen Findings und verändert keine fachlichen Daten oder Entscheidungen. Bei fehlender, veralteter oder mehrdeutiger Herkunft wird fail-closed gearbeitet.

**#350 – Grounded KI-Entwurf für Delivery-MVP-Scope** wurde am 23.08.2026 abgeschlossen. Der Delivery-Bereich kann nun auf Nutzeranforderung einen source-gebundenen, editierbaren MVP-Scope-Entwurf erzeugen; Übernahme bleibt eine bewusste fachliche Aktion über den regulären Schreibpfad.

**#349 – First-Wave LLM-Task-Runtime** wurde am 23.08.2026 abgeschlossen. Der gemeinsame Runtime-Layer bündelt Provider-/Privacy-Policy, Quotas, technische Run-Metadaten und Fehlerbehandlung für die ersten task-spezifischen KI-Funktionen, ohne fachliche Kontexte oder Ergebnisse in den Core-Layer zu ziehen.

**#328 – KI-Rollout konsolidieren** wurde am 23.08.2026 abgeschlossen. Die Analysen #325, #326 und #327 wurden in eine bewusst kleine First Wave überführt; daraus entstanden #349, #350 und #351. Der Rollout bleibt task-spezifisch, nutzerinitiiert und ohne automatische Freigabe-, Status- oder Domainänderungen.

**#333 – Scale Readiness vor produktivem Betrieb** wurde am 23.08.2026 abgeschlossen. Die bestehende Ergebnisentscheidung bündelt nun sechs Prüfdimensionen aus Pilotwirkung, Governance, Delivery, ML Test Score und Betriebsnachweisen. Hard Blocker verhindern den Go-live, ein Conditional Go verlangt Maßnahme, Owner und Frist, und der bestehende `Review` bleibt die einzige persistente Lifecycle-Entscheidungsquelle.

**#320 – Delivery-Readiness analysieren** wurde am 23.08.2026 als reine Re-Analyse abgeschlossen. Die mit #321 geschlossenen Owner-, Source-Decision-, Finding- und Review-Reset-Lücken sind weiterhin wirksam; es wurde keine verbleibende Restlücke festgestellt.

**#310 – Reiseveranstalter E2E-Demo und lokale UI-Abnahme** wurde am 23.08.2026 im regulären Browser abgeschlossen. Der Referenzfall wurde vom Value Stream über Fokus, Prozessanalyse und technologieoffenen Lösungsvergleich bis zum bewerteten und governance-seitig vorbereiteten KI-Use-Case durchgeführt.

---

# Aktueller Ablaufplan

Die frühere API V1 (#330) wurde am 13.09.2026 als `not_planned` geschlossen. Die TASKSHIFT-Integration (#435) wurde am 19.09.2026 über PR #456 nach `main` gemergt.

| Status | Issue | Inhalt | Ergebnis |
|---|---|---|---|
| **abgeschlossen** | **#436 – TASKSHIFT Domain Contract** | Serverseitiges v1.7-Scoring, Work-Design-Datenmodell, Validierung und Regressionstestvektoren. | Stabiler Domain- und Entscheidungskontrakt. |
| **abgeschlossen** | **#437 – Arbeitsgestaltungs-Workspace** | Optionaler Work-Design-Arbeitsraum innerhalb einer `ProcessAnalysis`; Rolle bestätigen, mehrere Aufgaben bewerten und vergleichen. | TASKSHIFT bleibt untergeordnet in der Prozessanalyse, ohne zweite Journey. |
| **abgeschlossen** | **#438 – Provenienz in den Lösungsraum** | Frozen TASKSHIFT-Herkunft an nachgelagerten SolutionOptions nachvollziehbar halten. | Provenienz bis SolutionOption und UseCaseOrigin bleibt auditierbar. |
| **abgeschlossen** | **#447 – UI-/Flow-Hardening** | Matrix, kompakte Aufgabenzeilen, klare Aktionen, Fail-closed-Bewertung und konsistenter Rücksprung in den Lösungsraum. | Technisch und im Browser verifiziert; mit #435 nach `main` gemergt. |
| **abgeschlossen** | **#450 – Task ≠ SolutionOption** | Task-Auswahl erzeugt keine SolutionOption mehr; erst im Lösungsraum entstehen 0..n echte Optionen. Zusätzlich Matrixpositionierung und visueller Abstand. | Trennung und Matrix im Browser geprüft; mit #435 nach `main` gemergt. |
| **abgeschlossen** | **#435 – TASKSHIFT-Integration** | Optionale Arbeitsgestaltung zwischen Prozessdiagnose und bestehendem Lösungsraum. | PR #456 am 19.09.2026 nach `main` gemergt. |
| **geparkt** | **#307 – optionaler Entscheidungsraum** | Zusätzlicher Decision Case für echte strittige Entscheidungen. | Keine automatische Folgepriorität nach TASKSHIFT. |

## Finaler fachlicher Übergang

```text
ProcessAnalysis
      ↓
optionale Arbeitsgestaltung
      ↓
Rolle + mehrere WorkDesignTasks
      ↓
TASKSHIFT-Bewertung / Ziel-Aufgabenteilung
      ↓
eine Aufgabe als Lösungsdesign-Kontext auswählen
      ↓
0..n echte SolutionOptions bewusst anlegen
      ↓
bestehender Vergleich / Preferred-Entscheid
      ↓
Use Case → Governance → Delivery → Pilot → Betrieb
```

Die zentrale Korrektur aus #450 ist verbindlich: **WorkDesignTask ≠ SolutionOption**. Der CTA `Für Lösungsdesign auswählen` erzeugt kein Lösungsobjekt. Dadurch bleibt TASKSHIFT für Arbeitsgestaltung zuständig und der bestehende Lösungsraum für die bewusste Wahl konkreter organisatorischer oder technischer Lösungsalternativen.

## Verifikation und nächster Schritt

- PR #451 wurde als Squash nach `agent/ui-control-room-integration` gemergt: `b551cb5415637b82875f373ce3fd5814462db542`.
- CI Run `35444131210` / Run 1875 ist vollständig grün: Ruff, Django Check, Migrationen, Real-DEMO E2E, vollständige Testsuite, Bandit, Dependency Audit, Compose local/prod/staging sowie Production-/Development-Images.
- Die Regression beweist explizit: Task-Auswahl erzeugt keine SolutionOption; mehrere echte SolutionOptions können dieselbe TASKSHIFT-Aufgabe als Provenienz referenzieren.
- Die manuelle Browser-Nachprüfung bestätigte Matrixpositionierung, Aufgabenaktionen, Kontextübergabe ohne automatische SolutionOption und die sichtbare Trennung zwischen Arbeitsgestaltung und `Lösungsoptionen vergleichen`.
- PR #456 wurde nach vollständiger grüner CI einschließlich Real-DEMO-E2E, Testsuite, Bandit, Dependency Audit, Compose- und Image-Prüfungen nach `main` gemergt.

Als nächster verbindlicher Schritt folgt eine neue Priorisierungsentscheidung gegen den aktuellen `main`. #307 bleibt geparkt und wird nicht automatisch vorgezogen.

---

# Entscheidungsregeln für Änderungen am Plan

1. **Rework vor nomineller Priorität vermeiden.** Wenn Issue B einen Vertrag, Zustand oder Übergang konsumiert, den Issue A noch verändert, kommt A zuerst.
2. **Analyse vor Verbraucher.** Ein reopened Analyse-Issue wird abgeschlossen und ein daraus notwendiges Fix-Issue umgesetzt, bevor abhängige Funktionen darauf aufsetzen.
3. **E2E-Abnahme nach Blockabschluss.** Ein Referenzdurchlauf wird nicht nach jedem kleinen Teilinkrement wiederholt, wenn mehrere direkt zusammengehörige Änderungen unmittelbar folgen.
4. **Explizite API-Verträge schützen.** Interne Modelle dürfen sich ändern; externe API-Contracts sollen möglichst erst nach Stabilisierung der dafür relevanten Domain-Semantik eingeführt werden.
5. **Parallelisierung nur ohne relevante Kopplung.** Unabhängige Stränge dürfen parallel laufen, solange sie nicht dieselben instabilen Domain-Verträge oder Journeys verändern.
6. **Aufwände sind Planungswerte.** Vor Implementierung bleibt der jeweilige Gap-Check gegen den aktuellen `main` maßgeblich; daraus können Umfang und Reihenfolge angepasst werden.

---

# Pflege

- Nach Abschluss eines Issues den Plan kurz gegen den aktuellen `main` und die verbleibenden offenen Issues prüfen.
- Neue Issues nicht automatisch hinten anhängen, sondern anhand ihrer technischen und fachlichen Abhängigkeiten einordnen.
- Abgeschlossene issue-spezifische Analyse- und Completion-Artefakte werden unter `docs/archive/issues/` abgelegt, sofern sie keine aktive fachliche oder technische Referenz mehr sind.
