# Arbeitsplan – Autonomer AI Business Architect

**Stand:** 30.09.2026  
**Repository:** `Satte882/KI-Ideenwerkstatt`  
**Übergeordnetes Ziel:** GitHub Issue #1 – „10x: Autonomes Evidence-to-Decision-System“

## Verwendung und Änderungsregel

Dieses Dokument ist die **führende Ziel- und Umsetzungsgrundlage für Issue #1**.

- Die Arbeitspakete werden in der dokumentierten Reihenfolge umgesetzt.
- Pro Arbeitspaket wird genau ein primäres GitHub-Issue angelegt. Das nächste Arbeitspaket wird erst konkretisiert und angelegt, nachdem das vorherige abgeschlossen und ausgewertet wurde.
- Das jeweilige Issue konkretisiert den betreffenden Planabschnitt, ersetzt oder verändert dessen Ziel, Architekturprinzipien oder Paketgrenzen aber nicht stillschweigend.
- Während eines laufenden Arbeitspakets wird dieser Plan nicht geändert. Neue Erkenntnisse, Fehler und Abweichungen werden im laufenden Issue dokumentiert.
- Nach Abschluss eines Arbeitspakets wird vor dem nächsten geprüft, ob reale Code-, Test- oder E2E-Befunde eine dauerhafte Änderung von Ziel, Architektur, Reihenfolge, Aufwand oder Paketgrenzen erfordern. Nur dann wird der Plan versioniert aktualisiert.
- Code, Tests und reale E2E-Befunde entscheiden darüber, ob die Abnahmekriterien erfüllt sind; der vereinbarte Zielmaßstab wird dabei nicht nachträglich still verändert.
- Jedes neue AP-Issue nennt den Commit dieses Plans, auf dessen Grundlage es erstellt wurde.

---

# 1. Ziel des Umbaus

KI-Ideenwerkstatt soll von einem fachlich guten, aber überwiegend geführten Workflow zu einem **autonomen AI Business Architect** werden.

Der zentrale Unterschied ist nicht, dass KI Formulare vorausfüllt.

Das System soll die eigentliche Analyse- und Architekturarbeit übernehmen, die heute zwischen den Formularen durch einen guten AI Business Architect oder KI-Consultant erledigt werden müsste.

## Zielablauf

Der Nutzer startet im Normalfall mit:

1. wenigen Sätzen zu Geschäftsproblem, Ziel oder Verbesserungsidee;
2. vorhandenen Quellen oder Daten;
3. gegebenenfalls einem bereits bekannten organisatorischen Kontext.

Danach übernimmt das System selbständig:

```text
Problem / Ziel + Quellen
        ↓
Geschäftskontext verstehen
        ↓
Value Stream und relevanten Ausschnitt rekonstruieren
        ↓
Prozess und Problemursachen analysieren
        ↓
Gegenbelege und offene Punkte prüfen
        ↓
realistische Lösungsalternativen entwickeln
        ↓
Non-AI vs. AI vergleichen
        ↓
kleinstmögliche sinnvolle technische Architektur bestimmen
        ↓
Use Case ableiten
        ↓
Nutzen, Messung und Pilot konzipieren
        ↓
Governance- und Risikobedarf ableiten
        ↓
Delivery-Inhalte erzeugen
        ↓
Discovery → Use Case → Governance → Delivery konsistent prüfen
        ↓
reviewfähiges Decision Package
```

Menschen bleiben zuständig für **Entscheidungen**, nicht für Datenintegration.

Im Happy Path soll der Mensch primär noch:

- Scope bzw. Fokus bestätigen, wenn dieser nicht eindeutig ist;
- die weiterzuverfolgende Lösungsrichtung auswählen;
- verbindliche Freigaben treffen;
- erforderliche Privacy-/Security-/Legal-Prüfungen durchführen;
- Delivery/Handover, Pilot und Go-live verbindlich bestätigen.

Nicht mehr zum Normalfall gehören sollen:

- Value-Stream-Formulare manuell ausfüllen;
- Phasen einzeln erfassen;
- Fokusmatrizen manuell pflegen;
- ProcessAnalysis-Felder zusammensuchen;
- SolutionOption-Felder nachpflegen;
- Use-Case-Wizard durchklicken;
- Governance-Informationen aus vorhandenen Unterlagen erneut übertragen;
- Anforderungen, Testfälle und Backlog manuell aus bereits vorhandenen Erkenntnissen ableiten.

---

# 2. Produktprinzipien

## 2.1 Domain-Objekte bleiben Source of Truth

Es wird **kein zweiter fachlicher Workflow** eingeführt.

Führend bleiben insbesondere:

```text
ValueStream
ValueStreamStage
ValueStreamFocus
StageFocusDecision
ProcessAnalysis
ProcessValidation
SolutionOption
SolutionSelectionDecision
UseCase
UseCaseOrigin
DecisionAssessment
GovernanceAssessment
GovernanceReview
ApprovalDecision
DeliveryPackage
DeliverySectionReview
Review
```

Der autonome Architect liest und verändert diese Objekte ausschließlich über kontrollierte Domain-Services.

---

## 2.2 Kein neuer „ArchitectureMission“-Lifecycle

Es wird zunächst **kein neues persistentes Mission-/Workflow-System** gebaut.

Vor dem ersten Business-Architecture-Objekt existiert bereits ein geeigneter technischer Arbeitscontainer:

```text
CaptureSession
CaptureAnalysis
CaptureFieldSuggestion
```

Diese Infrastruktur wird für den autonomen Einstieg erweitert.

Sobald Value Stream und ProcessAnalysis existieren, steckt der fachliche Zustand bereits im Domain-Modell.

Der nächste Arbeitsschritt kann deshalb deterministisch aus dem vorhandenen Zustand ermittelt werden.

Beispiel:

```text
CaptureSession noch ohne ProcessAnalysis
→ Business Discovery

ProcessAnalysis vorhanden, Investigation fehlt
→ Investigation

Investigation READY, Lösungsentscheidung fehlt
→ Lösungsentscheidung

AI-Lösung gewählt, UseCase fehlt
→ UseCase ableiten

UseCase vorhanden, Governance fehlt
→ Governance analysieren

finale positive Approval vorhanden, DeliveryPackage fehlt
→ Delivery erzeugen
```

Dafür reicht eine dünne Orchestrierungs-/Application-Service-Schicht.

Es entsteht **keine zweite Statusmaschine**.

---

## 2.3 Bestehende Spezialfähigkeiten werden wiederverwendet

Nicht neu bauen:

- Investigation Planner;
- Tool Runner;
- Source Search/Read/Profile/Compare;
- Synthesizer;
- Claim Register;
- Verifier;
- WAITING_HUMAN;
- Investigation Recovery;
- SolutionSelectionDecision;
- UseCaseOrigin;
- Architecture Advisor;
- Governance Reviews;
- Approval;
- Delivery Mapping;
- Delivery Readiness;
- Lifecycle Reviews.

Neue Logik wird nur dort gebaut, wo zwischen diesen vorhandenen Komponenten heute tatsächlich menschliche Facharbeit liegt.

---

## 2.4 LLM für Semantik – Code für Regeln

Das Modell darf:

- Texte und Quellen interpretieren;
- Prozesse rekonstruieren;
- Hypothesen bilden;
- Lösungsalternativen entwickeln;
- Zusammenhänge beurteilen;
- Anforderungen und Pilotkonzepte ableiten;
- semantische Widersprüche erkennen.

Deterministische Regeln entscheiden weiterhin über:

- Berechtigungen;
- Lifecycle;
- erlaubte Übergänge;
- Required Reviews;
- Readiness;
- Source-/Version-Gültigkeit;
- Architecture-Mode-Klassifikation;
- Idempotenz;
- Konflikte;
- unveränderliche Entscheidungen.

---

## 2.5 Keine automatische Managemententscheidung

Der AI Business Architect darf eine Lösung **empfehlen**.

Er darf nicht autonom:

- `SolutionOption.PREFERRED` als menschliche Entscheidung setzen;
- eine ApprovalDecision treffen;
- Risiko akzeptieren;
- Privacy/Security/Legal als bestanden markieren;
- Pilot starten;
- Go-live durchführen.

---

## 2.6 Kein Dokumentationsprojekt

Neue Dokumentation ist kein eigener Output.

Pro Arbeitspaket entstehen primär:

1. funktionierender Code;
2. Tests;
3. reale E2E-Runs;
4. Browser-Abnahme;
5. ein kompakter Abschlusskommentar im jeweiligen Issue.

Neue ADRs nur, wenn tatsächlich eine langlebige Architektur-Invariante geändert wird.

Keine neue Sammlung von Meta-Dokumenten, Statusreports oder Planungsartefakten.

---

# 3. Was heute bereits vorhanden ist

## 3.1 Geführte Business Architecture

Bereits vorhanden:

```text
ValueStream
→ ValueStreamStage
→ ValueStreamFocus
→ StageFocusDecision
→ ProcessAnalysis
→ SolutionOption
→ SolutionSelectionDecision
```

Die Modelle enthalten bereits fast alle Informationen, die der autonome Business Architect später erzeugen soll.

ValueStream:

- Trigger;
- Outcome;
- Scope;
- strategisches Ziel;
- Stakeholder;
- Constraints;
- Fachdomäne;
- Capability.

ValueStreamStage:

- Rollen;
- Systeme;
- Dokumente;
- Pain Points;
- Baselines.

ProcessAnalysis:

- Prozessgrenzen;
- Ablauf;
- Rollen;
- Systeme;
- Daten;
- Regeln;
- Handoffs;
- Bottlenecks;
- Beobachtungen;
- Ursachenhypothesen;
- bestätigte Ursachen;
- Constraints;
- Ausnahmen;
- Baselines;
- Zielprinzipien.

SolutionOption:

- organisatorische Lösungen;
- Non-Tech;
- Regelautomatisierung;
- Standardsoftware;
- Individualsoftware;
- Analytics/ML;
- Generative AI;
- Assistenz;
- Hybrid;
- Nutzen;
- Datenanforderungen;
- Integrationen;
- Machbarkeit;
- Risiken;
- Architecture Fit;
- Time-to-Value.

**Die fachliche Struktur muss nicht neu modelliert werden.**

---

# 4. Vorhandener KI-Unterbau

## 4.1 Guided Capture

`CaptureSession` und `CaptureAnalysis` existieren bereits.

Der Value-Stream-Katalog adressiert heute bereits Target Paths für:

```text
value_stream.*
value_stream.stages[].*
process_analysis.*
solution_options[].*
```

Damit existiert schon ein semantischer Vertrag für Business Discovery.

Aktuell basiert er jedoch auf vielen menschlich beantworteten Fragen.

Der autonome Architect soll dieselben fachlichen Zielobjekte aus:

```text
wenigen Sätzen + Quellen
```

erarbeiten.

---

## 4.2 Investigation / VS1

Bereits vorhanden:

```text
ProcessAnalysis
+ immutable Source Snapshot
        ↓
Planner
        ↓
Tools
        ↓
Synthesizer
        ↓
Verifier
        ↓
READY / WAITING_HUMAN / FAILED
```

Vorhanden sind unter anderem:

- Quellenmanifest;
- `list_sources`;
- `search_sources`;
- `read_source`;
- `profile_csv`;
- `compare_groups`;
- Claim Register;
- Gegenbelegsuche;
- Replanning;
- strukturierte Decision Briefs;
- Source Provenance;
- Budgetierung;
- Recovery;
- Idempotenz;
- Versionsbindung;
- konfliktgeschützter Handoff.

**Diese Engine wird nicht ersetzt.**

---

# 5. Wo der heutige Workflow noch manuell ist

Es verbleiben vier strukturelle Lücken.

## Lücke A – autonomer Einstieg

Investigation startet heute erst, wenn bereits vorhanden sind:

```text
ValueStream
Stage
Focus
ProcessAnalysis
```

Der Nutzer muss den fachlichen Kontext also bereits strukturiert haben.

Für einen autonomen AI Business Architect ist das zu spät.

---

## Lücke B – Investigation endet vor der bindenden Lösungsentscheidung

Der Decision-Brief-Handoff erzeugt heute Lösungskandidaten, aber nicht alle Felder, die `SolutionOption.comparison_complete` verlangt.

Unter anderem fehlen bzw. bleiben teilweise offen:

- Feasibility;
- Integration Effort;
- Time-to-Value;
- Technology Constraints;
- weitere Vergleichsinformationen.

Dadurch entsteht nach dem Agentenlauf wieder manuelle Datenpflege.

---

## Lücke C – Solution → UseCase → Governance bleibt geführter Workflow

Der heutige Weg verwendet weiterhin:

- Use-Case-Wizard;
- DecisionAssessment-Form;
- Governance-Screening-Form;
- einzelne manuelle Übertragungen.

Die Informationen sind zu diesem Zeitpunkt aber größtenteils bereits in:

```text
ValueStream
ProcessAnalysis
SolutionSelectionDecision
Investigation
```

vorhanden.

---

## Lücke D – Delivery benötigt weiter erhebliche fachliche Ausarbeitung

Der vorhandene Evidence Mapper kann bereits sicher Fakten übertragen.

Viele eigentliche Architektur-/Delivery-Inhalte werden bewusst nicht automatisch erzeugt, etwa:

- MVP;
- funktionale Anforderungen;
- NFRs;
- Tests;
- Architekturentscheidungen;
- Integrationsbetrieb;
- Backlog;
- Abhängigkeiten.

Genau diese Synthesearbeit soll der AI Business Architect übernehmen.

---

# 6. Zielzustand nach der Umsetzung

## Heute

```text
Mensch strukturiert Problem
→ Mensch baut Value Stream
→ Mensch erfasst Phasen
→ Mensch bewertet Fokus
→ Mensch baut ProcessAnalysis
→ Investigation
→ Mensch vervollständigt Optionen
→ Mensch wählt Lösung
→ Mensch durchläuft UseCase Intake
→ Mensch erstellt Assessment
→ Mensch erstellt Governance Screening
→ Mensch erstellt Delivery Package weiter aus
→ Mensch prüft
```

## Ziel

```text
Problem + Quellen
        ↓
AI Business Architect

[Scope/Fokus nur bei Bedarf bestätigen]

        ↓
AI Business Architect
rekonstruiert Prozess
untersucht Ursachen
sucht Gegenbelege
entwickelt Alternativen
bewertet Alternativen

[Lösungsrichtung entscheiden]

        ↓
AI Business Architect
erzeugt Use Case
bestimmt Architecture Mode
erstellt Assessment
leitet Governance-Bedarf ab
erstellt Pilot-/Messkonzept

[verbindliche Freigabe]

        ↓
AI Business Architect
erzeugt Delivery Package
Anforderungen
Architekturkontext
MVP
Tests
Akzeptanz
Backlog
Messkonzept

        ↓
automatische Cross-Domain-Prüfung

        ↓
Review / erforderliche Fachprüfungen / Handover
```

---

# 7. Technisches Zielbild

## 7.1 Vor der ProcessAnalysis

Als temporärer Arbeitscontainer wird `CaptureSession` wiederverwendet.

Dafür bekommt der Capture-Pfad einen autonomen Modus:

```text
CaptureSession
mode = guided | autonomous
```

Der autonome Modus benötigt nicht alle heutigen Capture-Fragen.

Minimaler Input:

```text
Problem/Ziel
optional vorhandener Geschäftskontext
Quellen
```

---

## 7.2 Nach der ProcessAnalysis

Kein neuer Orchestrierungszustand.

Die vorhandenen Objekte bilden den Zustand.

Eine kleine Application-Service-Schicht ermittelt:

```text
Was fehlt als Nächstes?
Was kann autonom erzeugt werden?
Wo ist eine menschliche Entscheidung notwendig?
```

Arbeitstitel für die Implementierung:

```text
accelerator/architect_service.py
accelerator/architect_state.py
accelerator/architect_schemas.py
accelerator/architect_prompts.py
```

Kein neues Django-App-Modul nötig, solange diese Schicht klein bleibt.

---

## 7.3 Decision Package

Das Decision Package wird **kein neues editierbares Domain-Modell**.

Es ist eine Projektion aus den führenden Objekten:

```text
ValueStream
ProcessAnalysis
InvestigationBriefRevision
SolutionSelectionDecision
UseCase
DecisionAssessment
GovernanceAssessment
ApprovalDecision
DeliveryPackage
```

Damit gibt es niemals:

```text
Domain-Wahrheit
+
Decision-Package-Wahrheit
```

Das Decision Package liest die aktuellen bzw. ausgewählten unveränderlichen Snapshots.

Für Export/Blind Review kann daraus ein unveränderlicher Markdown-/JSON-Snapshot erzeugt werden.

---

# 8. Startvoraussetzung vor der Gesamttransformation

Die aktuelle VS1-Engine muss zuerst als wiederverwendbarer Baustein stabil sein.

Aktuell gehört dazu insbesondere die laufende #86-Härtung.

Vor AP1 müssen mindestens gelten:

- der aktuelle reale Product-Path erreicht reproduzierbar einen korrekten fachlichen Endzustand;
- keine 4–5-Minuten-Synthese ist ungeklärt als Normalfall akzeptiert;
- Timeout-/Repair-Verhalten ist verständlich;
- Decision Brief und Handoff funktionieren;
- bestehende #4-Nachweise werden nicht durch neue Runs überschrieben;
- offene externe Review-Abhängigkeiten sind transparent dokumentiert.

**Geschätzter Restaufwand aus heutigem Stand:**  
**2–5 fokussierte Arbeitstage**, sofern #86 keine neue grundlegende Runtime-Ursache offenlegt.

Dieser Rest ist kein neues #1-Arbeitspaket, sondern Abschluss des bereits laufenden VS1-Hardening.

---

# 9. AP1 – Autonome Business Discovery bis zur ProcessAnalysis

## Ziel

Aus:

```text
wenigen Sätzen + bestehenden Quellen
```

entsteht autonom ein belastbarer Business-/Process-Draft.

Der Nutzer muss nicht zuerst Value Stream, Phasen und ProcessAnalysis selbst modellieren.

## Endzustand von AP1

Ein Nutzer kann beispielsweise schreiben:

> Die Bearbeitung von Lieferantenangeboten dauert zu lange. Angebote kommen per Mail und PDF, anschließend werden Preise und Konditionen manuell verglichen.

Dazu lädt er vorhandene Quellen hoch.

Das System erzeugt daraus:

```text
Value Stream
Value-Stream-Phasen
ValueStreamFocus
empfohlene Fokusphase
Process Scope
ProcessAnalysis-Draft
offene relevante Unsicherheiten
```

Der Mensch prüft lediglich die vorgeschlagene Abgrenzung.

Danach wird die bestehende Investigation automatisch gestartet.

---

## AP1.1 Autonomer Capture-Pfad

`CaptureSession` erhält einen autonomen Einstieg.

Die vorhandene Guided-Capture-Funktion bleibt unverändert verfügbar.

Neuer Happy Path:

```text
Neue Analyse
→ Problem/Ziel beschreiben
→ Quellen bereitstellen
→ Analyse starten
```

Kein Fragebogen mit acht Abschnitten.

---

## AP1.2 Quellen vor der ProcessAnalysis

Die heutige Source-Infrastruktur ist an `ProcessAnalysis` gebunden.

Sie muss so generalisiert werden, dass ein Quellenstand zunächst an eine `CaptureSession` gebunden werden kann.

Prinzip:

```text
CaptureSession
→ verwaltete Quellenbasis
→ immutable Source Snapshot
```

Nach bestätigtem Scope:

```text
gleicher Quelleninhalt
→ ProcessAnalysis-bound Snapshot
→ InvestigationRun
```

Zwischen beiden Snapshots muss der Source-/Manifest-Hash identisch sein.

Damit wird kein zweites Upload-/Validierungssystem gebaut.

Die bestehende `.md/.txt/.csv`-Validierung bleibt führend.

---

## AP1.3 Autonomous Business-Architecture Synthesis

Der neue strukturierte Output enthält nur Business-/Process-Discovery.

Nicht bereits Governance oder Delivery.

Mindestens:

```text
Value Stream
- Name
- Zweck
- Trigger
- Outcome
- Scope in/out
- strategisches Ziel
- Stakeholder
- Constraints
- Fachdomäne
- Capability

Phasen
- Reihenfolge
- fachlicher Fortschritt
- Rollen
- Systeme
- Daten/Dokumente
- Pain Points
- bekannte Baselines

Fokus
- relevante Phase
- Begründung
- wesentliche Trade-offs

Prozess
- Start
- Ende
- Trigger
- Outcome
- Ablauf
- Rollen
- Systeme
- Datenobjekte
- Regeln
- Handoffs
- beobachtete Probleme
- erste Ursachenhypothesen
- Constraints
- bekannte Baselines

Unknowns
Clarifications
```

Fakten, berichtete Aussagen, Hypothesen und Unbekanntes bleiben getrennt.

---

## AP1.4 Bootstrap-Verifier

Vor der Domain-Materialisierung prüft ein separater Reviewer mindestens:

- Quellenbezug sachlicher Aussagen;
- keine erfundenen Zahlen;
- sinnvolle Value-Stream-Grenze;
- plausible Phasenfolge;
- Fokusphase entspricht dem Problem;
- Process Scope ist enger als Value Stream;
- Hypothesen werden nicht als Fakten dargestellt;
- entscheidungskritische Unbekannte sind sichtbar.

Ein kritisches Finding löst höchstens einen gezielten Repair aus.

Danach:

```text
weiter kritisch
→ WAITING_HUMAN oder FAILED
```

nicht endlos neue Synthesen.

---

## AP1.5 Menschliche Scope-Entscheidung

Die primäre Oberfläche zeigt:

```text
Vorgeschlagener Value Stream

relevante Phasen

empfohlene Fokusphase

vorgeschlagener Process Scope

wichtige Quellen/Befunde

entscheidungsrelevante Unsicherheiten
```

Primäre Aktionen:

```text
Scope übernehmen

andere Fokusphase wählen

Korrektur eingeben
```

Kein Feld-für-Feld-Review.

---

## AP1.6 Materialisierung

Nach Bestätigung werden über Domain-Services erzeugt:

```text
ValueStream
ValueStreamStage[]
ValueStreamFocus
StageFocusDecision
ProcessAnalysis
```

Bestehende Formularlogik, die fachliche Invarianten enthält, wird dafür soweit nötig in wiederverwendbare Services extrahiert.

Der autonome Pfad schreibt nicht direkt an den Formularen vorbei.

---

## AP1.7 Übergabe an VS1

Nach Materialisierung:

1. gleicher Quellenstand wird für ProcessAnalysis autorisiert;
2. Manifestgleichheit wird geprüft;
3. sinnvolle Decision Question wird erzeugt;
4. bestehender `InvestigationRun` startet.

Ab hier übernimmt VS1 unverändert.

---

## AP1 – Abnahme

AP1 ist fertig, wenn drei unterschiedliche reale Fälle bestehen:

### Fall A – eindeutiger Scope

Problem + Quellen reichen.

Keine Rückfrage vor Scope-Vorschlag.

### Fall B – mehrdeutiger Scope

System erkennt die echte Mehrdeutigkeit und stellt eine konkrete Scope-Frage.

### Fall C – widersprüchliche Quellen

System markiert den Widerspruch und erfindet keinen eindeutigen Prozessstand.

Zusätzlich:

- kein manuelles ValueStream-Formular nötig;
- keine manuelle Phasenerfassung nötig;
- keine manuelle ProcessAnalysis-Erfassung nötig;
- Provenance bleibt prüfbar;
- existierende Guided-Capture-Flows regressionsfrei;
- existierende ProcessAnalysis-Investigation regressionsfrei.

---

## AP1 – Aufwand

**Erwartung:** 8–12 fokussierte Arbeitstage  
**Komplexität:** ca. 1,0–1,3 × VS1-Härtungseinheit

Enthalten:

- Implementierung;
- Migration/Source-Generalisation;
- Unit-/Integrationstests;
- Browser-E2E;
- mindestens 3 reale Providerfälle;
- erwartbar 2–4 Root-Cause-/Hardening-Runden.

Hauptrisiko:

Der Eingaberaum ist erheblich offener als beim bisherigen VS1.

Eine First-Pass-Implementierung ohne reale Kalibrierung gilt deshalb ausdrücklich nicht als Abschluss.

---

# 10. AP2 – Von Investigation zu Lösungsentscheidung, Use Case und Governance

## Ziel

Nach einem erfolgreichen InvestigationRun darf der Nutzer nicht wieder in umfangreiche manuelle Datenpflege fallen.

Der autonome Business Architect führt den Fall von:

```text
verifiziertem Process/Decision Brief
```

bis zu:

```text
vollständig vergleichbaren Lösungsoptionen
+
menschlicher Lösungsentscheidung
+
AI Use Case
+
Architecture Mode
+
Decision Assessment
+
Governance Screening
+
Pilot-/Messkonzept
```

---

# 11. AP2.1 Solution Options vollständig machen

Der bestehende Investigation-Output wird um die Felder erweitert, die der vorhandene Lösungsvergleich benötigt.

Insbesondere:

```text
bottleneck_coverage
feasibility
data_requirements
application_impact
integration_effort
integration_impact
technology_constraints
risks
architecture_fit
time_to_value
evidence_basis
contains_ai_component
```

Der Verifier prüft diese Angaben.

Wenn alle bestehenden `SolutionOption`-Regeln erfüllt sind:

```text
evaluation_status = ASSESSED
```

darf automatisch gesetzt werden.

Nicht automatisch:

```text
recommendation = PREFERRED
```

---

# 12. AP2.2 Diagnose und Lösungsentscheidung zusammenführen

Heute benötigt der verbindliche Lösungsvergleich eine belastbare Diagnose.

Im neuen Pfad wird daraus eine echte menschliche Decision Surface.

Beispiel:

```text
Beobachtetes Problem
...

Gestützte Ursache
...

wichtige Gegenbelege / Grenzen
...

Option A
Option B
Option C
Status quo

Empfehlung des AI Business Architect
...

[Diagnose als Entscheidungsgrundlage bestätigen]

Bevorzugte Lösungsrichtung:
( ) A
( ) B
( ) C

Begründung:
...
```

Ein bestätigter Submit führt transaktional die bestehenden Domain-Aktionen aus:

```text
ProcessValidation / bestätigte Diagnose
+
SolutionSelectionDecision
```

Die menschliche Entscheidung bleibt damit unverändert explizit.

---

# 13. AP2.3 Non-AI-Zweig

Wird eine Non-AI-Lösung ausgewählt:

```text
organizational
rule_automation
standard_software
custom_software ohne AI-Komponente
no_tech
```

wird kein künstlicher KI-Use-Case erzeugt.

Der Architect erzeugt stattdessen einen abschließenden Non-AI-Umsetzungs-/Validierungsstand.

Issue #1 ist kein System zur Maximierung der Anzahl von KI-Use-Cases.

---

# 14. AP2.4 Direkte Use-Case-Erzeugung

Bei einer ausgewählten AI-Lösung entfällt der Use-Case-Wizard im Happy Path.

Ein Domain-Service erzeugt aus:

```text
ValueStream
ProcessAnalysis
SolutionSelectionDecision
selected SolutionOption
Investigation
```

einen vollständigen `UseCase`.

Wiederverwendet werden:

```text
UseCase
UseCaseClassification
UseCaseOrigin
role_defaults
```

Ableitbare Angaben werden übernommen.

Beispielsweise:

```text
Business Unit
Fachdomäne
Capability
betroffener Prozess
Problem
Zielgruppe
Systeme
Daten
Integrationen
Lösungstyp
Intended Purpose
Expected Benefit
Human Oversight
```

---

# 15. AP2.5 Messung und Pilot

Das System formuliert selbständig:

```text
Nutzenhypothese
primäre Erfolgsmetrik
Optimierungsrichtung
Einheit
Messmethode
Messpopulation/Stichprobe
Messzeitraum
kleinsten sinnvollen Pilot
Review-/Abbruchkriterien
```

Belegte numerische Baselines oder Ziele dürfen übernommen werden.

Fehlen sie:

```text
metric_baseline = NULL
metric_target = NULL
```

oder es wird eine Messaktivität beschrieben.

Keine erfundenen Zahlen.

---

# 16. AP2.6 Architecture Advisor

Der vorhandene deterministische Advisor wird automatisch verwendet.

Die vier vorhandenen Fragen werden aus dem Fall beantwortet:

```text
Reicht eine einfachere Lösung?
Ist semantisches Reasoning erforderlich?
Sind mehrere bekannte AI-Schritte erforderlich?
Ist dynamische Orchestrierung erforderlich?
```

Danach bestimmt ausschließlich die bestehende Regel:

```text
No LLM required
Controlled LLM
LLM Workflow
Bounded Agent
Assessment open
```

Der LLM-Agent darf den Modus nicht frei erfinden.

---

# 17. AP2.7 Decision Assessment

`DecisionAssessment` wird aus dem vorhandenen Fall autonom vorbereitet.

Dimensionen:

```text
Business Value
Strategic Fit
Technical Feasibility
Data Readiness
Risk Complexity
Evidence Quality
Evidence Recency
Evidence Coverage
Independent Review
Assumptions Resolved
Recommendation
Rationale
```

Diese Bewertung ist Analysearbeit und keine Approval.

Sie darf daher systemseitig erzeugt werden.

Die Herkunft muss auditierbar sein; ein systemgeneriertes Assessment darf nicht so aussehen, als hätte eine konkrete Person es manuell erstellt.

---

# 18. AP2.8 Governance

Der AI Business Architect erzeugt zunächst einen Governance-Draft.

Er untersucht insbesondere:

```text
personenbezogene Daten
Beschäftigtendaten
Personenentscheidungen
biometrische Daten
Safety
regulierte Produkte
Gesundheit/Rechte
externe Cloud/KI
extern veröffentlichte generierte Inhalte
Human Oversight
```

Wichtige Regel:

```text
unknown ≠ false
```

Im Kernpfad wird deshalb ein GovernanceAssessment erst materialisiert, wenn entscheidungskritische Governance-Fakten ausreichend geklärt sind.

Kann eine unbekannte Information den Review-Bedarf verändern:

```text
→ konkrete Rückfrage
```

Das System darf anschließend automatisch erzeugen:

```text
GovernanceAssessment
+
OPEN / NOT_RELEVANT GovernanceReview-Artefakte
```

Es darf niemals automatisch:

```text
Privacy PASSED
Security PASSED
Legal PASSED
```

setzen.

---

# 19. AP2.9 Decision Surface vor Approval

Der Entscheider erhält erstmals eine konsolidierte Sicht:

```text
Problem
Prozess
Ursachen
Alternativen
getroffene Lösungsentscheidung
AI-Begründung / Non-AI-Abgrenzung
Architecture Mode
Use Case
Nutzen
Metrik
Pilot
Governance
Risiken
Unbekanntes
offene Pflichtprüfungen
```

Diese Ansicht ist eine Projektion aus bestehenden Domain-Objekten.

Kein neues editierbares Decision-Package-Modell.

---

# 20. AP2 – Abnahme

Mindestens vier reale Fälle:

1. Non-AI gewinnt.
2. Controlled-LLM-Lösung gewinnt.
3. Hybrid-/Workflow-Lösung.
4. Governance-relevanter Fall mit echter unbekannter Information.

Erwartung:

- kein Use-Case-Wizard im autonomen AI-Pfad;
- SolutionOptions sind vor der Auswahl vollständig vergleichbar;
- Non-AI bleibt echter Endzustand;
- keine künstliche AI-Architektur;
- keine erfundenen Metriken;
- kritische Governance-Lücke erzeugt Frage statt `False`;
- Formal Reviews bleiben menschlich;
- Approval bleibt menschlich.

---

# 21. AP2 – Aufwand

**Erwartung:** 9–14 fokussierte Arbeitstage  
**Komplexität:** ca. 1,1–1,5 × VS1-Härtungseinheit

Enthalten:

- Solution-Contract-Erweiterung;
- Materialisierung;
- Decision Surface;
- direkter UseCase-Handoff;
- Architecture Advisor;
- Assessment;
- Governance;
- Pilot-/Messkonzept;
- 4+ reale Providerfälle;
- 2–4 erwartbare Hardening-Runden.

Hauptrisiko:

Mehrere bestehende Domain-Grenzen werden erstmals durch einen autonomen Pfad miteinander verbunden.

---

# 22. AP3 – Vom Approval zum delivery-ready Umsetzungspaket

## Ziel

Nach einer positiven menschlichen Approval soll der AI Business Architect aus dem bereits erarbeiteten Stand selbständig ein konkretes Umsetzungspaket erzeugen.

Der Nutzer soll nicht wieder bei generischen Delivery-Vorlagen anfangen.

---

# 23. AP3.1 Bestehenden Evidence Mapper zuerst verwenden

Der vorhandene Mapper bleibt die erste Stufe.

Was deterministisch übernommen werden kann, wird nicht erneut vom LLM formuliert.

Beispielsweise:

```text
Problem
Ziel
Scope
Nutzer
Systeme
Daten
Integrationen
Oversight
Messinformationen
Risiken
Approval Conditions
```

Damit sinken Halluzinationsrisiko und Providerkosten.

---

# 24. AP3.2 Nur echte Synthesearbeit ans LLM

LLM-Synthese ist für Felder vorgesehen, die nicht durch Copy/Compose eindeutig entstehen können.

Insbesondere:

```text
MVP Scope
Should / Could / Won't
funktionale Anforderungen
nichtfunktionale Anforderungen
Logging/Audit
Testfälle
Abhängigkeiten
Annahmen
Architekturentscheidungen
Initial Backlog
Systemverantwortlichkeiten
Data Quality / Access
Integration Contracts
Integration Operations
```

Dabei sollen nicht 15 voneinander unabhängige Feldaufrufe entstehen.

Sinnvolle fachliche Sektionen werden zusammen synthetisiert, beispielsweise:

```text
1. Lösung + MVP + Requirements

2. Architektur + Daten + Integration + Betrieb

3. Acceptance + Tests + Messung + Backlog
```

---

# 25. AP3.3 Konkretheit statt Template-Text

Nicht ausreichend:

> Kernablauf des Use Cases umsetzen.

Erwartet:

> Eingehende Angebotsmails erfassen, PDF-Anhänge einem Vorgang zuordnen, Preis- und Konditionsfelder extrahieren, regelbasierte Vergleichskriterien anwenden, unsichere Extraktionen zur manuellen Prüfung vorlegen und den finalen Vergleich mit Quellenbezug speichern.

Das Package muss umsetzbar sein.

---

# 26. AP3.4 Delivery-Verifier

Nach der Synthese prüft ein unabhängiger Reviewer:

- Requirements passen zur gewählten Lösung;
- MVP adressiert den tatsächlichen Engpass;
- Systeme sind im Ausgangskontext vorhanden oder als neue Komponenten gekennzeichnet;
- Datenanforderungen sind plausibel;
- keine erfundene Schnittstelle;
- NFRs sind fallbezogen;
- Governance-Auflagen wurden übertragen;
- Tests decken kritische Risiken;
- Acceptance Criteria passen zu Requirements und Metrik;
- Backlog passt zum MVP;
- Annahmen sind sichtbar;
- unbekannte technische Informationen werden nicht erfunden.

Maximal ein gezielter Repair je kritischem Finding-Set.

---

# 27. AP3.5 Cross-Domain-Konsistenz

Vor „delivery-ready“ laufen zunächst deterministische Prüfungen.

Beispiele:

```text
UseCaseOrigin == ausgewählte SolutionOption

UseCase gehört zum gleichen ValueStream/Process

Solution Type widerspricht der Option nicht

Architecture Assessment gehört zur gewählten Option

Governance gehört zum UseCase

Messplan verwendet dieselbe primäre Metrik

Approval Conditions sind in Delivery übernommen

DeliveryPackage basiert auf aktueller finaler Approval

keine veralteten Source Snapshots

keine widersprüchlichen Domain-Versionen
```

Danach nur für semantische Fragen ein LLM-Review:

- adressiert die Lösung tatsächlich die Diagnose?
- passt der MVP zum erwarteten Wirkmechanismus?
- widerspricht die Delivery-Architektur der gewählten Architecture-Klasse?
- fehlen entscheidungsrelevante Risiken?
- wurde eine schwache Evidenzlage später als starke Tatsache dargestellt?

---

# 28. AP3.6 Zentrales Decision Package

Das Decision Package ist eine **read-only Entscheideransicht**.

Struktur:

## Entscheidungskern

- Problem
- Ursache
- gewählte Lösung
- erwarteter Nutzen
- warum AI / warum nicht
- wichtigstes Risiko
- nächste Entscheidung

## Business und Prozess

## Quellen und Befunde

## Alternativen und Lösungsentscheidung

## Use Case

## Architecture Mode

## Governance

## Pilot und Messung

## Delivery

## offene Entscheidungen / Reviews

## Provenance / Untersuchungsspur

Die Detail-Provenance bleibt aufklappbar.

Die primäre Ansicht ist entscheidungsorientiert und kein Audit-Log.

---

# 29. AP3.7 Bestehende menschliche Delivery-Grenzen bleiben

Weiterhin menschlich:

```text
Business Confirmation
Technical Confirmation
Governance Formal Reviews
Handover
Pilotstart
Go-live
```

Der Architect bereitet diese Entscheidungen vor.

Er trifft sie nicht.

---

# 30. AP3 – Abnahme

Mindestens drei real unterschiedliche positive AI-Fälle.

Das erzeugte Delivery Package muss:

- keine generischen Pflichtplatzhalter mehr enthalten;
- Readiness soweit autonom möglich erfüllen;
- nur echte menschliche Bestätigungen als offene Blocker haben;
- gegen Discovery und Use Case konsistent sein;
- Approval-Auflagen korrekt enthalten;
- fallbezogene Requirements, Tests und MVP enthalten;
- mit vorhandenen Delivery-Seiten funktionieren;
- keinen parallelen Delivery-Lifecycle erzeugen.

---

# 31. AP3 – Aufwand

**Erwartung:** 9–15 fokussierte Arbeitstage  
**Komplexität:** ca. 1,1–1,6 × VS1-Härtungseinheit

Enthalten:

- section-level Synthesis;
- Delivery-Verifier;
- Cross-Domain-Checks;
- Decision-Package-UI;
- reale Delivery-Fälle;
- Readiness-/Handover-Regression;
- 2–4 erwartbare Hardening-Runden.

Hauptrisiko:

Delivery besitzt viele semantisch gekoppelte Felder. Der Aufwand entsteht weniger aus Codeumfang als aus der notwendigen Qualitätshärtung der erzeugten Inhalte.

---

# 32. AP4 – E2E-Härtung und 10x-Nachweis

## Ziel

Nicht mehr Funktionalität bauen.

Nachweisen, dass aus den Komponenten tatsächlich ein autonomer AI Business Architect entstanden ist.

---

# 33. Testpopulation

Vor dem gewerteten Lauf werden realistische Ausgangsfälle eingefroren.

Mindestens:

1. organisatorische/Non-AI-Lösung;
2. regelbasierte Automatisierung;
3. Controlled-LLM-Fall;
4. Workflow-/Hybrid-Fall;
5. fehlende entscheidungskritische Evidenz;
6. widersprüchliche Evidenz;
7. Governance-relevanter Fall;
8. Daten-/CSV-Fall.

Nicht jeder Fall muss bis Delivery kommen.

Ein korrekt erkannter Non-AI- oder WAITING_HUMAN-Fall ist ein valides Ergebnis.

---

# 34. Kein Success Sampling

Vor dem gewerteten Lauf werden festgelegt:

```text
Source Pack
Startzustand
Prompt-/Schema-Versionen
Run-Slots
Bewertungskriterien
```

Fehlversuche bleiben Fehlversuche.

Es werden keine späteren besseren Runs als Ersatz ausgewählt.

---

# 35. Zu messende #1-Kriterien

## Aktive Human Work

Median:

```text
≤ 15–20 Minuten
```

vom Ausgangsproblem bis zum ersten reviewfähigen Decision Package.

Systemwartezeit separat.

---

## Manuelle Feldpflege

Mindestens:

```text
90 % Reduktion
```

gegen den entsprechenden heutigen Pfad.

Gezählt werden reale Nutzereingaben.

---

## Rückfragen

Vor dem ersten vollständigen Entwurf:

```text
Median ≤ 3
```

Ausgenommen echte Authority Decisions.

---

## Provenance

```text
100 %
```

der tragenden aus vorhandenen Quellen abgeleiteten Tatsachen müssen auflösbar sein.

---

## Halluzinationen

```text
0
```

erfunden dargestellte Fakten oder Messwerte.

---

## Konsistenz

```text
Discovery
→ Solution
→ UseCase
→ Governance
→ Delivery
```

muss automatisch geprüft werden.

---

## Menschliche Nacharbeit

```text
≤ 20 %
```

des heutigen Aufwands.

---

## Qualität

Blind Review:

```text
mindestens gleichwertig oder besser
```

als der manuell erarbeitete Referenzfall.

---

# 36. Technische Härtung in AP4

Zusätzlich werden absichtlich geprüft:

```text
Provider Timeout
invalid structured response
Retry
Resume
User Abort
Concurrent Runs
Versionskonflikt
menschliche Änderung während Agentenarbeit
stale Source
stale Delivery
fehlende Quelle
irrelevante Quelle
```

Für Parallelbetrieb wird insbesondere geprüft:

- keine doppelte fachliche Materialisierung;
- keine verlorenen Updates;
- keine versteckten Budget-Resets;
- keine Starvation/Fairness-Probleme bei gleichzeitig laufenden Aufträgen.

Nur reproduzierbare Probleme werden behoben.

Keine vorsorgliche neue Scheduling-/Queue-Plattform.

---

# 37. AP4 – Aufwand

**Erwartung:** 6–10 fokussierte Arbeitstage  
**Komplexität:** ca. 0,7–1,0 × VS1-Härtungseinheit

Zusätzlich besteht eine externe Kalenderabhängigkeit für den Blind Human Review.

Diese Wartezeit ist kein Implementierungsaufwand.

AP4 enthält bewusst mehrere Post-Fix-Runden. Ein technischer Green Run allein schließt dieses Paket nicht ab.

---

# 38. Gesamtaufwand

Die Zahlen sind keine Schätzung nach Anzahl der Todos.

Sie berücksichtigen die reale VS1-Erfahrung: neue Agentenverträge funktionieren erfahrungsgemäß nicht nach einmaligem Implementieren, sondern benötigen reale Providerläufe, Fehleranalyse und mehrere Härtungsrunden.

| Block | Erwarteter Aufwand |
|---|---:|
| Aktuelle VS1/#86-Resthärtung | 2–5 Tage |
| AP1 – autonome Business Discovery | 8–12 Tage |
| AP2 – Solution → UseCase → Governance | 9–14 Tage |
| AP3 – Delivery + Decision Package | 9–15 Tage |
| AP4 – E2E-Härtung + Nachweis | 6–10 Tage |
| **Gesamt** | **34–56 fokussierte Arbeitstage** |

Das entspricht grob **4–5 bisherigen VS1-Härtungseinheiten**.

Bei konzentrierter Arbeit mit Coding Agent und kurzen Review-Zyklen ist damit eher eine Größenordnung von **mehreren Wochen** als von wenigen Tagen realistisch.

Der größte Unsicherheitsfaktor sind nicht CRUD oder UI, sondern die realen semantischen Hardening-Zyklen.

---

# 39. Separate Architekturentscheidung A – PDF/DOCX

PDF- und DOCX-Unterstützung ist **kein versteckter Bestandteil von AP1**.

AP1 startet mit dem heute beherrschten Quellenvertrag:

```text
.md
.txt
.csv
```

Während AP1 werden die realen Ziel-Source-Packs betrachtet.

## PDF/DOCX wird separat beschlossen, wenn:

ein repräsentativer Zielprozess ohne manuelle Konvertierung nicht sinnvoll bearbeitet werden kann, weil relevante Evidenz regelmäßig ausschließlich in PDF/DOCX vorliegt.

Dann entsteht ein eigenes Paket:

```text
PDF/DOCX Source Ingestion
```

mit eigenem:

- Parsing-Vertrag;
- Provenance-Vertrag;
- Seiten-/Absatzreferenzen;
- Tabellenverhalten;
- Fehlerverhalten;
- realen Source Tests.

### Erwarteter Aufwand bei Bedarf

Für textbasierte PDF/DOCX-Dateien:

**4–8 fokussierte Arbeitstage.**

OCR wäre eine **weitere separate Entscheidung** und gehört nicht automatisch dazu.

---

# 40. Separate Architekturentscheidung B – Governance Tri-State (durch #103 umgesetzt)

Der reale AP2-Fall D hat die im ursprünglichen Plan definierte Triggerbedingung erfüllt: Der boolesche kanonische Governance-Zustand hätte entweder eine fachlich unbelegte Negation oder eine unnötige menschliche Pflichtschleife erzwungen.

Die Tri-State-Migration wurde deshalb als separates Arbeitspaket #103 umgesetzt und vor Abschluss von AP2 real abgenommen.

Der kanonische Zustand kann für Governance-Fakten nun tragen:

```text
true
false
NULL = unknown
```

Der Review-Bedarf wird deterministisch aus diesen Fakten abgeleitet:

- entscheidungskritische Unknowns bleiben Klärungsbedarf;
- nicht mehr entscheidungsrelevante Unknowns dürfen sichtbar und auditierbar erhalten bleiben;
- erforderliche Governance Reviews entstehen höchstens `OPEN`;
- nicht erforderliche Reviews können `NOT_RELEVANT` sein;
- Privacy/Security/Legal werden niemals automatisch als bestanden markiert.

Dauerhafte Invariante für AP3 und folgende Pakete:

```text
unknown ≠ false
```

Delivery, Cross-Domain-Prüfung und spätere Projektionen müssen diesen kanonischen Zustand erhalten und dürfen Unknowns weder als Negation noch als Freigabe interpretieren.

Die menschliche Authority für formale Reviews, Approval, Risikoakzeptanz, Pilotstart und Go-live bleibt unverändert.

Diese reale Architekturentscheidung ändert **Ziel, Reihenfolge und Paketgrenze von AP3 nicht**.

---

# 41. Bewusste Nicht-Ziele

Nicht Teil der geplanten Transformation:

- LangGraph;
- CrewAI;
- AutoGen;
- Flock;
- eigener Multi-Agent-Framework-Layer;
- Agenten-Zoo nach Fachrollen;
- Vector DB ohne konkreten Retrieval-Bedarf;
- allgemeines RAG-Rewrite;
- automatische Freigaben;
- automatische Risikoakzeptanz;
- automatischer Pilotstart;
- automatischer Go-live;
- zweiter Business-Lifecycle;
- zweites editierbares Decision Package;
- pauschale Gate-Reduktion;
- vorsorgliche Governance-Schema-Migration;
- vorsorglicher PDF/DOCX/OCR-Ausbau.

---

# 42. Reihenfolge der Umsetzung

Die Reihenfolge ist verbindlich, weil jedes Paket eine belastbare Grundlage für das nächste schafft.

```text
Aktuelles VS1/#86 stabilisieren
        ↓
AP1
Problem + Quellen
→ Business Architecture
→ ProcessAnalysis
→ Investigation startet autonom
        ↓
AP2
Investigation
→ vollständige Lösungsalternativen
→ menschliche Lösungsentscheidung
→ UseCase
→ Architecture Mode
→ Assessment
→ Governance
→ Pilotkonzept
        ↓
AP3
menschliche Approval
→ DeliveryPackage
→ konkrete Requirements/MVP/Tests/Backlog
→ Cross-Domain-Verifier
→ vollständiges Decision Package
        ↓
AP4
eingefrorene E2E-Fälle
→ 10x-Messung
→ Blind Review
→ gezielte Härtung
→ Abschluss Issue #1
```

PDF/DOCX oder Governance Tri-State werden nur an der Stelle eingeschoben, an der ein realer Befund ihre Notwendigkeit beweist.

---

# 43. Arbeitsmodus pro Paket

Jedes Arbeitspaket folgt derselben Vorgehensweise.

## 1. Codepfad vor Änderung lesen

Nicht aus dem Plan blind implementieren.

Vor dem ersten Patch:

- relevante Models;
- Services;
- Permissions;
- vorhandene Tests;
- Journey/Workflow;
- bestehende LLM-Verträge;
- konkrete Canonical Write Paths.

## 2. Kleinstes E2E-Inkrement bauen

Nicht zuerst alle Models und dann Monate später verbinden.

Beispiel AP1:

```text
Problem
→ Source Pack
→ Bootstrap
→ Scope Review
→ ProcessAnalysis
→ Investigation Start
```

muss möglichst früh vollständig laufen.

## 3. Deterministische Tests

Zuerst:

- Permissions;
- Versionen;
- Contracts;
- Idempotenz;
- Source-Bindung;
- erlaubte Domain Writes.

## 4. Realer Browser-E2E

Danach echte Providerläufe.

Nicht nur Mock-Tests.

## 5. Diagnose aus persistiertem Zustand

Bei Fehlern:

```text
echten Run
echten Output
echte Token
echte Blocker
echten Diff
echtes CI
```

lesen.

Keine hypothetischen Fixes.

## 6. Root Cause beheben

Keine Symptom-Patches, wenn das Problem im Vertrag oder Datenfluss liegt.

## 7. Post-Fix-Bestätigung

Vorherige Fehlversuche bleiben dokumentiert.

Sie werden nicht durch neue Runs ersetzt.

## 8. Erst dann Merge und nächstes Paket

---

# 44. Definition of Done des Gesamtprojekts

Issue #1 ist erst fertig, wenn ein Nutzer einen realistischen Fall folgendermaßen bearbeiten kann:

```text
1. Problem beschreiben
2. Quellen bereitstellen
3. wenige echte Rückfragen beantworten
4. Scope bestätigen
5. Lösungsentscheidung treffen
6. erforderliche Freigaben treffen
```

und das System dazwischen selbständig:

```text
Geschäftskontext
Value Stream
Phasen
Fokus
ProcessAnalysis
Ursachenanalyse
Gegenbelege
Solution Options
Solution Assessment
AI-/Non-AI-Abgrenzung
Architecture Mode
UseCase
Governance
Risiko
Pilot
Messkonzept
Delivery
Requirements
Tests
Backlog
Konsistenzprüfung
```

erarbeitet.

Zusätzlich müssen die #1-Messgrößen real erfüllt sein:

| Messgröße | Ziel |
|---|---:|
| Aktive Human Work bis erstes reviewfähiges Decision Package | ≤ 15–20 min Median |
| Manuelle Felder | ≥ 90 % Reduktion |
| Rückfragen vor erstem vollständigem Entwurf | Median ≤ 3 |
| Provenance vorhandener Quellenaussagen | 100 % |
| erfundene Fakten/Messwerte | 0 |
| Discovery → Delivery Konsistenz | automatisch verifiziert |
| Menschliche Nacharbeit | ≤ 20 % des heutigen Aufwands |
| Blind-Review-Qualität | mindestens gleichwertig zum manuellen Referenzfall |

Erst dann ist aus KI-Ideenwerkstatt nicht nur ein Workflow mit KI-Unterstützung, sondern ein **autonomer AI Business Architect mit menschlicher Entscheidungshoheit** geworden.

---

# 45. Maßgebliche Referenzen

- Issue #1 – Produktauftrag:  
  https://github.com/Satte882/KI-Ideenwerkstatt/issues/1

- Issue #4 – VS1 / agentische Investigation:  
  https://github.com/Satte882/KI-Ideenwerkstatt/issues/4

- Issue #45 – Meta-Research und Reihenfolge:  
  https://github.com/Satte882/KI-Ideenwerkstatt/issues/45

- Aktueller `main`, bestehende Tests und reale Run-Diagnosen haben Vorrang vor älteren Planungsdokumenten.

- `AGENTS.md` bleibt verbindlich für Implementierungs- und Produktinvarianten.

- ADR 0007 bleibt verbindlich für Lifecycle-/Review-Entscheidungen.

- ADR 0008 bleibt verbindlich für die bestehende Investigation-/Server-State-Grenze.

---

# 46. Primäre nächste Aktion

AP1 und AP2 sind abgeschlossen und in `main` integriert.

Die nächste planmäßige Einheit ist:

> **AP3 – Vom positiven menschlichen Approval zum delivery-ready Umsetzungspaket.**

AP3 startet auf dem jetzt kanonischen Stand aus Discovery, Investigation, menschlicher Lösungsentscheidung, Use Case, Architecture Assessment, Decision Assessment, Governance und Pilot-/Messkonzept.

Der erste reale Zielnachweis für AP3 lautet:

```text
positive menschliche Approval
→ bestehende Evidenz deterministisch übernehmen
→ nur echte Synthesearbeit erzeugen
→ konkretes DeliveryPackage mit MVP/Requirements/Tests/Backlog
→ Cross-Domain-Konsistenz prüfen
→ menschliche Delivery-/Handover-Grenzen erhalten
```

Keine neue Approval-Automatisierung und kein paralleler Delivery-Lifecycle.
