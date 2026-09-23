# KI-Ideenwerkstatt Produkt-Roadmap

**Stand:** 21.09.2026

**Status:** Produktstand und strategische Richtung, kein Terminversprechen

## Zweck dieser Roadmap

Diese Datei beschreibt **was KI-Ideenwerkstatt als Produkt bereits kann und welche größeren Produktprobleme als Nächstes oder später adressiert werden könnten**.

Sie beschreibt bewusst **nicht**, wie einzelne Funktionen technisch umgesetzt wurden. Dafür sind die jeweiligen GitHub-Issues, Pull Requests, Gap-Analysen, Completion-Dokumente und – bei architekturrelevanten Entscheidungen – die ADRs maßgeblich.

Für die aktuelle Transformation ist GitHub Issue [#1 „10x: Autonomes Evidence-to-Decision-System“](https://github.com/Satte882/KI-Ideenwerkstatt/issues/1) der verbindliche Produktauftrag. Der bisherige [`planning/EXECUTION_PLAN.md`](planning/EXECUTION_PLAN.md) bleibt als historische und technische Referenz erhalten, begrenzt aber die Sequenzierung von Issue #1 nicht.

Die Zukunftssicht folgt den Horizonten **Now / Next / Later**:

- **Shipped:** auf `main` vorhandene Produktfähigkeiten;
- **Now:** aktuell bearbeiteter Produktfokus;
- **Next:** priorisierte nächste Produktprobleme, deren konkreter Scope noch nicht festgeschrieben sein muss;
- **Later:** strategische Optionen ohne Umsetzungszusage oder feste Reihenfolge.

Je weiter ein Thema vom aktuellen Produktstand entfernt ist, desto geringer ist bewusst die Planungssicherheit.

---

## Produktgrenze

KI-Ideenwerkstatt ist ein **AI-Business-Architecture-, Portfolio-, Governance- und Entscheidungs-Cockpit** für KI-Vorhaben. Es ersetzt kein operatives Projektmanagement- oder Delivery-System.

**Externes Delivery-System bleibt führend für:**

- Backlog, Tasks, Sprints und technische Detailprobleme;
- tägliche Maßnahmen, Ressourcen und operativen Fortschritt;
- Release-, Incident-, Change- und Service-Steuerung.

**KI-Ideenwerkstatt bleibt führend für:**

- fachliche Herkunft, Problemverständnis und Nutzenhypothese;
- Value-Stream-, Prozess- und Lösungsanalyse;
- Bewertung, Governance, Freigabe und Auflagen;
- Architekturentscheidung auf angemessenem Abstraktionsniveau;
- Delivery Readiness, Evidenzherkunft und verbindliche Übergabe;
- entscheidungsrelevante Review-Snapshots;
- Lifecycle, Ownership, Wirkung und Abschluss.

Der Rückfluss aus Jira, Azure DevOps, GitHub oder einem anderen Delivery-System erfolgt weiterhin bewusst als **verdichteter Review-Snapshot**. KI-Ideenwerkstatt wird nicht zum zweiten operativen Delivery-System.

---

# Shipped – aktuelle Produkt-Baseline

## 1. Business Architecture, Discovery und methodische Führung

KI-Ideenwerkstatt kann fachlichen Kontext vom Geschäftsbereich bis zum konkreten Analysegegenstand strukturiert führen:

- Fachdomänen und Business Capabilities;
- End-to-End-Value-Streams mit Trigger, Outcome, Scope und Stakeholdern;
- geordnete Phasen mit nachvollziehbarem Wertfortschritt;
- Fokus-Screening und dokumentierte Auswahl für den Deep Dive;
- innerhalb eines Value Streams ein evidenzbewusster Phasenvergleich mit Business Impact, Problemintensität, Verbesserungspotenzial, Datenzugang/Validierbarkeit, Veränderungsaufwand und Time-to-Value;
- frühe hypothesenbasierte Fokuswahl ohne erfundene Baselines oder Pflichtmesswerte;
- klare Trennung von Value Stream, Capability und Prozess;
- kontextsensitive Methodik-Hilfe und kalibrierte qualitative Bewertungsskalen.

Zentrale Nachweise: #54, #57, #308, #331; methodische Gegenprüfung über #313–#316.

## 2. Prozessdiagnose und lösungsoffene Auswahl

Die Prozessanalyse verbindet Ablauf, Rollen, Systeme, Daten, Handoffs, Ausnahmen und Baselines mit einer belastbareren Diagnose vor der verbindlichen Lösungsauswahl:

- SIPOC ist als kompakter Scopingrahmen `Supplier → Input → Process → Output → Customer` sichtbar, ohne ein separates SIPOC-Artefakt oder neue Pflichtfelder einzuführen;
- fachliche Inputs/Daten/Dokumente, das Prozessergebnis sowie Quellen und Empfänger werden über die bestehenden ProcessAnalysis-Felder geführt;
- Beobachtung beziehungsweise Problem ist von Ursachenhypothese und bestätigter Ursache unterscheidbar;
- ein systembestimmender Constraint bleibt optional und wird nicht mit jedem lokalen Problem gleichgesetzt;
- frühe Exploration und Lösungsentwürfe bleiben möglich;
- Evidenzbasis ist als Hypothese, Indiz oder Messwert sichtbar, während `ProcessValidation`, Provenance und Versions-/Stale-Mechanismen die fachliche Validierung und Herkunft tragen;
- organisatorische, regelbasierte, klassische technische, KI-gestützte und hybride Lösungen bleiben echte Alternativen;
- Time-to-Value ist ein expliziter Trade-off und keine automatische Rangfolge;
- Hybrid-, Custom- und sonstige Lösungen werden nicht automatisch als KI interpretiert;
- eine bevorzugte Non-AI-Lösung ist ein gültiger Discovery-Abschluss und erzwingt keinen KI-Use-Case;
- Auswahl und Begründung bleiben historisiert und auditierbar.

Die **optionale Arbeitsgestaltung mit TASKSHIFT** ergänzt diesen Pfad: Eine bestätigte Rolle kann mehrere Aufgaben mit deterministischer Bewertung, Ziel-Aufgabenteilung und Verantwortungsgrenze vergleichen. Die Auswahl einer Aufgabe übergibt nur Kontext in den bestehenden Lösungsraum. Erst dort werden 0..n konkrete SolutionOptions bewusst angelegt; `source_work_design_task` und ein Frozen Snapshot erhalten die Herkunft. Arbeitsgestaltung führt weder ein zusätzliches Gate noch einen zweiten Lifecycle ein.

Zentrale Nachweise: #47, #60, #63, #318, #323, #331 sowie #435–#438, #447 und #450; Integration über PR #456 am 19.09.2026 nach `main` gemergt.

## 3. AI Accelerator und kontrollierte LLM-Unterstützung

Der Accelerator reduziert manuelle Erstbefüllung, ohne Entscheidungsrechte an ein LLM zu übertragen:

- geführte, wiederaufnehmbare Erfassung;
- strukturierte LLM-Extraktionsvorschläge mit Quelle, Unsicherheit und Validierung;
- konfliktgeschützte feldweise Übernahme;
- strukturierte Entwurfsobjekte für Metriken, Phasen und Prozessanalyse;
- generative, lösungsoffene Lösungsentwürfe;
- deterministisches Evidence-to-Delivery-Mapping;
- nachvollziehbare Rollen-Defaults;
- kontrollierte Mess- und Regressionstrecke für Qualität, Laufzeit und Providerfehler;
- gemeinsame task-spezifische LLM-Runtime mit Privacy-/Quota-/Fehlerleitplanken statt eines generischen KI-Layers;
- nutzerinitiierter, source-gebundener KI-Entwurf für den Delivery-MVP-Scope mit bewusster fachlicher Übernahme;
- nutzerinitiierte, read-only Discovery→Use-Case-Konsistenzprüfung mit maximal fünf source-gebundenen Findings und fail-closed Verhalten bei nicht belastbarer Herkunft.

Der Accelerator und die neuen task-spezifischen KI-Funktionen erzeugen Entwürfe und Hinweise, **keine Freigaben, Governance-Entscheidungen, bindenden Lösungspräferenzen, automatischen Domainänderungen oder Lifecycle-Entscheidungen**.

Zentrale Nachweise: #116–#125, #328 sowie #349–#351; ergänzend die Completion-Dokumente unter `docs/accelerator/`.

## 4. Architecture Advisor und Solution Quality Control

Für vorhandene Lösungsoptionen kann KI-Ideenwerkstatt die minimal hinreichende technische Autonomie transparent einordnen:

- deterministische Architekturklassen `No LLM required`, `Controlled LLM`, `LLM Workflow`, `Bounded Agent` und `Assessment open`;
- erklärbare Reason Codes und sichtbares „Warum / Warum kein Agent?“;
- strukturierter semantischer Critic für generierte Lösungsentwürfe;
- maximal ein gezielter Repair und danach erneute deterministische Validierung;
- Human Review bleibt der Endpunkt;
- keine automatische Rangfolge, Präferenz oder Governance-Wirkung.

Zentrale Nachweise: #210–#213, #274 und #276.

## 5. Use Case, Decision Governance und Portfolio

Use Cases werden als nachvollziehbare Entscheidungsobjekte geführt:

- direkter oder systematisch abgeleiteter Intake;
- optionaler kanonischer Ursprungsprozess über die bestehende `UseCaseOrigin`-Relation;
- automatische Ableitung von Phase, Value Stream und vorhandenem strategischem Kontext bei bekanntem Prozessursprung statt redundanter Use-Case-Felder;
- bestehende Use Cases ohne Prozessursprung bleiben vollständig gültig;
- Nutzenhypothese und definierte Erfolgsmetrik mit Name, Typ, Richtung, Einheit und Messmethode;
- Baseline und Zielwert dürfen in früher Aufnahme noch unbekannt bleiben und werden nicht durch künstliche Platzhalter ersetzt;
- eine strukturierte Bewertung ist auch mit noch unbekannter Baseline beziehungsweise unbekanntem Zielwert möglich; positive Freigaben bleiben bis zu deren belastbarer Erfassung serverseitig blockiert;
- versionierte Bewertung mit Evidenz und Confidence;
- getrennte Governance-, Datenschutz-, Security- und Rechtsprüfungen;
- getrennte Bewertung, finale Freigabe und unabhängige Bestätigungen;
- deterministische serverseitige Hard Gates;
- Portfolio- und Arbeitsvorratssichten ohne künstlichen Gesamtscore;
- konkrete Blocker, Zuständigkeit und Next Actions.

Die vorgelagerte Discovery-Lösungsentscheidung und die spätere Use-Case-Freigabe bleiben getrennte Entscheidungsobjekte. KI-Ausgaben können unterstützen, aber keine verbindliche fachliche Entscheidung auslösen.

Zentrale Nachweise für Prozess-Traceability und Messreife: #322 und #340.

## 6. Delivery Readiness, Provenance und Übergabe

Das versionierte Delivery Package bildet den kontrollierten Übergang von der Entscheidung in die Umsetzung:

- sieben fachlich beziehungsweise technisch prüfbare Delivery-Sektionen;
- System-, Daten-, Integrations- und Architekturkontext;
- MVP-Scope, Anforderungen, Akzeptanz, Test- und Messkonzept;
- Risiken, Annahmen, Abhängigkeiten und Architekturentscheidungen;
- Quellenmanifest, Snapshots, Staleness und kontrollierte Source Decisions;
- strukturierte Readiness-Findings mit konkreter Regel, Ursache, Zuständigkeit und Behebungsaktion;
- konsistente Handover-Gates und unabhängige Bestätigung;
- output-typ-spezifische Confidence-/Unsicherheitssemantik sowie präzisierte Evaluation-, Latenz- und Retention-Regeln;
- unveränderliche übergebene Package-Versionen.

Zentrale Nachweise: #37–#39, #49, #50, #55, #124, #311, #320 und #321.

## 7. Lifecycle, Wirkung und Betrieb

Die fachliche Journey endet nicht mit dem Delivery-Handover:

- Lifecycle `Idee → Prüfung → Pilot → Betrieb → Beendet`;
- expliziter Pilotstart nach verbindlicher Übergabe;
- Baseline, Ziel, aktueller Ist-Wert, Messzeitraum, Messdatum und Messnachweis;
- Scale Readiness als explizites Gate zwischen validierter Pilotwirkung und produktivem Betrieb;
- sechs verständliche Prüfdimensionen für Pilotwirkung, Daten/Wissen, AI-/Systemqualität, Deployment, Monitoring/Betrieb sowie Verantwortung/Governance/Restrisiko;
- deterministische Vorschläge `GO`, `CONDITIONAL GO` und `NO-GO` ohne neuen Scale-Gesamtscore;
- Go-live-Gate mit aktuellen Pilot-, Governance-, Delivery-, ML-Test-Score- und Betriebsinformationen;
- nicht überstimmbare Hard Blocker sowie verpflichtende Maßnahme, Owner und Frist bei `CONDITIONAL GO`;
- Findings, dominante nächste Aktion und historischer Scale-Readiness-Snapshot im bestehenden Lifecycle-Review;
- geplanter Pilotzeitraum und dokumentierte Ausnahme für vorzeitige Produktivsetzung;
- Betriebsreviews und Hinweis auf veraltete Nutzenmessungen;
- Abschluss mit Beendigungsgrund, Daten-/Zugangsbehandlung und Lessons Learned;
- entscheidungsrelevanter Workspace `Wirkung & Betrieb`.

Der aktuelle Messstand reicht für Golden Path, Pilotbewertung und Go-live. Ein erfolgreicher Pilot kann nicht ohne Scale-Readiness-Prüfung in Betrieb überführt werden. Mehrere fachlich eigenständige Messstände sind noch keine eigene Messreihe.

Zentraler Nachweis für das Go-live-/Scale-Gate: #333.

## 8. Business & Decision Control Room

Die Oberfläche wurde auf die fachliche Arbeit und die jeweils nächste Entscheidung ausgerichtet:

- Portfolio als Querschnitt statt pseudo-linearer Journey;
- konkrete Arbeitsobjekte mit kontextuellem Lifecycle;
- genau eine dominante Next Action je Zustand;
- getrennte Darstellung von Arbeitsstatus, Prüfstatus und Readiness;
- gemeinsame UI-Archetypen für Listen, Workspaces und Formulare;
- konsistente Desktop-, Tablet- und Mobile-Darstellung;
- sichtbarer Tastaturfokus, semantische Zustände und zugängliche Interaktionen;
- reduzierte Legacy- und Duplicate-Journey-Strukturen;
- lokal im regulären Browser abgenommene Referenzstrecke vom Value Stream bis zur bewerteten, governance-seitig vorbereiteten KI-Idee einschließlich No-AI-Gegenprobe und hypothesenfähiger Messreife.

Zentrale Nachweise: #279–#287, #295 und #310.

---

# Now – aktueller Fokus

**Verbindlicher Produktauftrag:** GitHub Issue [#1 „10x: Autonomes Evidence-to-Decision-System“](https://github.com/Satte882/KI-Ideenwerkstatt/issues/1).

Der heute ausgelieferte Funktionsumfang unter **Shipped** ist die Baseline. Ziel ist die Transformation vom geführten Workflow mit punktueller KI-Unterstützung zu einem System, das die fachliche Analysearbeit zwischen Problem, Evidenz, Diagnose, Lösungsraum, Entscheidung, Governance, Pilot und Delivery weitgehend autonom erledigt.

Erfolg wird nicht an Codeumfang oder sichtbaren KI-Features gemessen, sondern insbesondere an:

- deutlich weniger aktiver menschlicher Arbeitszeit bis zum reviewfähigen Decision Package;
- mindestens 90 % weniger manueller Feldpflege;
- wenigen, nur entscheidungsrelevanten Rückfragen;
- vollständiger Provenance relevanter Aussagen;
- null erfundenen Fakten oder Messwerten;
- automatisch geprüfter Konsistenz von Discovery bis Delivery;
- mindestens gleichwertiger oder besserer Ergebnisqualität gegenüber der manuellen Referenz.

Bis der autonome Consultant den Decision Brief samt unabhängiger Verifikation
zuverlässig erzeugt, hat diese Funktionsfähigkeit Vorrang vor Token- und
Kostenoptimierung. Harte Run- und Campaign-Grenzen, persistente Abrechnung und
Safety-Gates bleiben bestehen; Verbrauch wird weiterhin transparent gemessen.

Die detaillierte Definition of Done und Verifikation stehen in Issue #1.

**VS1-Stand am 21.09.2026:** Der begrenzte Evidence-to-Decision-Slice verfügt technisch
über den fallgebundenen Quellenraum, reproduzierbare Tools, adaptiven Planner/Verifier,
Stopppolicy, Decision Brief, konfliktgeschützte Materialisierung und eine vorab festgelegte
Fixed-Route-Vergleichsstrecke. Die reale Wirksamkeitsprüfung aus Issue #4 ist noch nicht
abgeschlossen; insbesondere fehlen die vollständigen realen A/B/C-Läufe, der reale
Fixed-vs-Adaptive-Vergleich, unabhängiger menschlicher Review und menschliche Zeitmessung.
Issue #1 bleibt deshalb unverändert offen.

---

# Next – priorisierte nächste Probleme

**Next zuletzt geprüft:** 2026-09-21

Bis Issue #1 umgesetzt und gegen die Baseline gemessen wurde, gibt es keinen konkurrierenden separaten Next-Scope. Danach wird auf Basis der Messergebnisse neu priorisiert. Bestehende Later-Themen bleiben Optionen und dürfen innerhalb von Issue #1 nur dann vorgezogen werden, wenn sie nachweislich dem 10x-Ziel dienen.

---

# Later – strategische Optionen

Die folgenden Themen sind bewusst **Optionen, keine Zusagen und keine feste Reihenfolge**.

## Priorität 3 – Versionierte Wirkungsmessungen

Fachlich relevant, aber bewusst geparkt. Der bestehende Einzel-Messstand deckt Pilotbewertung und Go-live bereits ab.

Eine spätere Messreihe könnte zusätzlich ermöglichen:

- Messwert und Zeitpunkt historisch als eigenständige Messstände führen;
- Zeitraum, Population und Stichprobengröße je Messstand dokumentieren;
- Messmethode und Methodenversion nachvollziehen;
- Datenqualität und Confidence je Messstand festhalten;
- Evidenz je Messung verknüpfen;
- Trend- und Drift-Betrachtung statt Überschreiben eines einzelnen Ist-Werts.

Die Umsetzung benötigt eine neue explizite Produktpriorisierung.

## Wirkungsreviews und Ergebnisentscheidungen

Auf Basis belastbarer wiederkehrender Messungen könnte KI-Ideenwerkstatt später:

- quantitative und qualitative Ergebnisse zu einem Review bündeln;
- Nebenwirkungen, Nutzerfeedback und offene Governance-Auflagen einbeziehen;
- Empfehlung und tatsächliche Folgeentscheidung verknüpfen;
- Entscheidungen wie `skalieren`, `verlängern`, `nachbessern`, `begrenzt betreiben`, `pausieren` oder `beenden` strukturiert und auditierbar festhalten.

## Lifecycle- und Outcome-Analytics

Mögliche spätere Ausbaustufen:

- explizites Lifecycle-Event-Log;
- Time-to-Value und Verweildauer je Phase;
- verdichtete Delivery-Ergebnisse und Kostenabweichungen;
- Adoption, aktive Nutzung, Human Overrides und Nutzerzufriedenheit.

Diese Punkte werden nur umgesetzt, wenn ein konkreter Steuerungsnutzen den zusätzlichen Pflegeaufwand rechtfertigt.

## Optionale Integration externer Delivery-Systeme

Erst nach stabiler manueller Review-Strecke prüfen:

- nur verdichtete entscheidungsrelevante Daten übernehmen;
- Quelle und Aktualität sichtbar machen;
- Konflikte explizit behandeln;
- keine doppelte Task-, Sprint- oder Maßnahmenpflege erzeugen.

## Später lernendes System

Erst bei ausreichend hochwertigen, versionierten historischen Daten bewerten:

- Merkmals-Snapshots und klar definierte Zielgrößen;
- Vergleich ähnlicher historischer Fälle;
- Muster-, Risiko- oder Erfolgsfaktoren;
- Bias- und Datenqualitätsprüfung vor Modellentwicklung.

Ein späteres Modell darf keine Freigaben oder Lifecycle-Entscheidungen autonom auslösen.

## Optionaler Entscheidungsraum

Der in #307 beschriebene zusätzliche Decision-Space bleibt als strategische Option geparkt. Er wird nur priorisiert, wenn die bestehende Decision-Governance bei realen komplexen oder strittigen Entscheidungen nachweislich nicht ausreicht.

---

# Pflege- und Dokumentationsregeln

1. Die Roadmap beschreibt **Produktfähigkeit, Problem und Richtung**, nicht technische Implementierungsdetails.
2. `Shipped` wird nach relevanten Produktmerges auf Capability-Ebene aktualisiert; einzelne Fixes werden nicht als eigene Roadmap-Punkte gespiegelt.
3. `Now`, `Next` und `Later` sind Prioritätshorizonte, keine Kalendertermine.
4. Während Issue #1 läuft, bestimmt dessen Ziel und Definition of Done die Sequenzierung; separate Zwischenfreigaben sind nur für irreversible fachliche Entscheidungen oder echte Produkt-Trade-offs erforderlich. Nach Abschluss von Issue #1 gilt für neue `Next`- oder `Later`-Themen wieder eine explizite Produktpriorisierung.
5. GitHub-Issues und Pull Requests bleiben der detaillierte Umsetzungs- und Änderungssachverhalt.
6. Gap-Analysen, Methodik- und Completion-Dokumente bleiben der vertiefende fachliche beziehungsweise technische Nachweis.
7. ADRs dokumentieren ausschließlich relevante Architekturentscheidungen mit Kontext, Entscheidung und Konsequenzen; sie dienen nicht als Capability-Inventar.
8. README beschreibt das **heutige Produktbild**; diese Roadmap beschreibt **erreichten Stand und strategische Richtung**.
9. Ein `CHANGELOG.md` wird erst sinnvoll, wenn versionierte Releases beziehungsweise Release-Tags als eigenes Kommunikationsobjekt geführt werden.
