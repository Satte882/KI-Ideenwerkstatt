# UX-Hardening Audit – #360 / #361

**Stand:** 24.08.2026  
**Issue:** #361 · `[#360][01][Analyse] UI-Inventur, A/B/C/D & Read-only-Audit`  
**Parent:** #360 · `[EPIC][UX-Hardening] Informationshierarchie, Read-only & Progressive Disclosure`  
**Referenzstand Code:** `main` @ `a539abed1ce5323f91242f138f2d53eb83719ce1`

## 0. Zweck, Scope und Grenzen

Dieses Dokument ist die verbindliche Analysebasis für #362–#365. Es beschreibt den Ist-Zustand und priorisiert sichtbare Informationen, ohne bereits das Redesign umzusetzen.

Geprüft wurden:

- Arbeitsvorrat
- Portfolio
- Value Stream
- Prozessanalyse
- Use Case Detail
- Lifecycle-/Review-Ansicht, soweit sie für die Aktionen des Use Cases relevant ist

Verbindliche Quellen und Leitplanken:

- `AGENTS.md`
- `DESIGN.md`
- `docs/ROADMAP.md`
- `OPEN_QUESTIONS.md`
- ADR `docs/adr/0007-golden-path-review-reuse.md`
- aktueller Code auf `main`
- die zum Auftrag bereitgestellten Screenshots als visuelle Ausgangspunkte

**Nicht Bestandteil von #361:** UI-Umbau, neue Komponentenbibliothek, Änderung von Models, Business-Logik, URLs, Berechtigungen, JourneyState, Reviews oder Hard Gates.

### Klassifizierung

| Klasse | Bedeutung |
| --- | --- |
| **A – primär** | Für die aktuelle Aufgabe oder Entscheidung unmittelbar erforderlich; muss schnell erfassbar bleiben. |
| **B – sekundär** | Fachlich relevant, aber nicht in jedem Zustand sofort nötig. |
| **C – Nachweis / Metadaten / Historie** | Für Vertiefung, Auditierbarkeit oder Herkunft relevant; darf visuell klar nachrangig sein. |
| **D – ohne zusätzlichen Darstellungswert** | In der aktuellen Darstellung redundant, doppelt oder kontextlos. Die zugrunde liegenden Daten bleiben erhalten; nur die Darstellung soll entfallen oder zusammengeführt werden. |

Die Einordnung ist bewusst **zustandsabhängig**: Ein Governance-Status ist z. B. A, wenn er das aktuelle Gate blockiert, sonst typischerweise B/C.

---

### Verbindlicher UI-Vertrag für zustandsabhängige Einordnung

„Zustandsabhängig“ beschreibt in diesem Dokument **keinen Ermessensspielraum**. Die Folge-Issues dürfen die unten stehenden Regeln anwenden, aber weder eigene Sichtbarkeitskriterien noch abweichende Klassifizierungen erfinden. Trifft mehr als eine Regel zu, gewinnt die Regel mit der höheren Prominenz (A vor B vor C); eine D-Regel entfernt oder konsolidiert ausschließlich die zusätzliche Darstellung, nie die Daten oder Historie.

| Information | Wenn | Dann | Klasse / verbindliche Darstellung |
| --- | --- | --- | --- |
| Governance-Prüfung | sie blockiert das aktuelle Gate oder die kanonische Next Action | muss zusammen mit Gate/Blocker im primären Arbeitsbereich erscheinen | **A** |
| Governance-Prüfung | sie ist abgeschlossen und beeinflusst keine aktuelle Entscheidung | erscheint nur als kompakter Status oder in der Vertiefung | **B/C** |
| Erfolgsmetrik (Ziel/Ist) | Pilotstart, Pilotbewertung oder Ergebnis-/Scale-Entscheidung ansteht | Ziel und Ist stehen im primären Entscheidungsbereich; die Messgrundlage bleibt erreichbar | **A** |
| Erfolgsmetrik | eine frühe Bewertung ohne Ergebnisentscheidung vorliegt | Ziel/Ist bleibt als unterstützender Kontext sichtbar, nicht vor Gate/Next Action | **B** |
| Review-Historie | kein konkreter Historieneintrag die aktuelle Entscheidung begründet | wird ausschließlich nachrangig in Disclosure/History gezeigt | **C** |
| Lifecycle | Orientierung über den aktuellen Fortschritt benötigt wird | genau **eine** primäre Lifecycle-Rail zeigt den Status | **A, einmalig** |
| Lifecycle-Status in Statusbox/Dimension/Fact | dieselbe Lifecycle-Aussage bereits durch die primäre Rail dargestellt wird | zusätzliche Wiederholung wird entfernt oder auf einen Link zur Rail reduziert | **D** |
| Owner | diese Person für den aktuellen Blocker, die kanonische Next Action oder die fällige Entscheidung zuständig ist | Name und Rolle stehen beim jeweiligen Arbeitskontext | **A/B** |
| Owner | die Angabe nur Stammdaten/Traceability ist | erscheint nachrangig in den Stammdaten | **B** |
| Nächste Lifecycle-Entscheidung | sie ist fällig oder die kanonische Next Action | konkrete Entscheidung benennen und als primäre Aktion zeigen | **A** |
| Nächste Lifecycle-Entscheidung | sie ist nicht fällig | nur als Steuerungsinformation zeigen | **B** |
| Entscheidungs-, Mess- oder Statusinformation | dieselbe fachliche Aussage bereits in der führenden Quelle vollständig sichtbar ist | weitere identische Kurzfassung entfernen oder in einen Link/Verweis überführen | **D** |

**Umsetzungsregel:** #363–#365 dürfen aus diesen Regeln nur Darstellung und Gruppierung ableiten. Status-, Review-, Gate- und Permission-Logik bleiben in ihren bestehenden fachlichen Quellen; das Template erfindet keine neue Zustandslogik.

# 1. Screenshot → Route → Template → Aktion

Die Screenshots sind keine technische Quelle. Bei Abweichungen ist `main` maßgeblich.

| Screenshot / sichtbarer Bereich | Seite | Route | Haupt-Template / Komponenten | Sichtbare Hauptaktionen | Abgleich mit `main` |
| --- | --- | --- | --- | --- | --- |
| `2b30d51b-7641-4e35-b132-bae1ae2f26fb.png` | Arbeitsvorrat | `/` | `templates/reporting/dashboard.html`, Worklist-Tag, Bootstrap-Tabs | Alle Use Cases, Monatsreview, zeilenbezogene Next Actions | **entspricht weitgehend `main`** |
| `8ff75929-9d91-4b5c-9d14-0c54c5d33ebc.png` | Portfolio | `/portfolio/` | `templates/reporting/portfolio.html` | Filter anwenden/zurücksetzen, Use-Case-Links, Matrix-/Landkarten-Navigation | **entspricht dem aktuellen Aufbau** |
| `00a37087-ba65-4384-aec1-afbf29453321.png` und `6937bf88-f809-4d34-a1eb-a13d826f3150.png` | Value Stream | `/architecture/<uuid>/` | `templates/architecture/value_stream_detail.html`, `includes/lifecycle_rail.html`, `includes/next_action.html` | Zur Übersicht, bearbeiten/priorisieren, kanonische Next Action, Fokusphase/Phasenaktionen | **strukturell aktuell**; konkrete Next Action hängt vom Objektzustand ab |
| `ed121b03-b1c6-40e4-86e1-fefd6baac3fc.png` | Prozessanalyse, Ausschnitt „Ist-Prozess und Ursachen“ | `/architecture/processes/<uuid>/` | `templates/architecture/process_analysis_detail.html`, `includes/lifecycle_rail.html`, `includes/next_action.html` | Zum Value Stream, validieren, bearbeiten, Lösungsoptionen | **Ausschnitt entspricht dem aktuellen Grid** |
| `1ef7ff66-218f-4b78-bd1d-ff87a13d4436.png` | Use Case Detail | `/use-cases/<uuid>/` | `templates/use_cases/detail.html`, `includes/decision_state.html`, `includes/next_action.html`, `includes/status_dimensions.html`, `includes/lifecycle_rail.html` | Stammdaten, Lifecycle-Review, Bewertung, Freigabe, Gate-/Blocker-Aktionen | **teilweise veraltet**: `main` bündelt die vier Kopfaktionen bereits in „Weitere Aktionen“. Die Status-/Arbeitszustandsblöcke existieren weiterhin. |
| kein eigener Screenshot, aus Use Case erreichbar | Lifecycle-/Review-Entscheidung | `/reviews/use-case/<uuid>/new/` plus optionale `?action=...` | `templates/reviews/form.html`, `ReviewForm`, Scale-Readiness-Include | Pilot starten / Entscheidung speichern | **Code ist maßgeblich** |

## 1.1 Route- und Berechtigungsgrenzen

### Arbeitsvorrat / Portfolio

- Beide sind lesende Steuerungssichten.
- Filter und Tabs verändern die Sicht, nicht das fachliche Objekt.
- Zeilen/Chips führen zu echten Objekt- oder Arbeitslinks.

### Value Stream / Prozessanalyse

- Value Stream bearbeiten: KI-Koordinator oder Business Owner, wenn er Value-Stream-Owner ist.
- Prozessanalyse bearbeiten/validieren verwendet dieselbe Value-Stream-Berechtigungsgrenze.
- Validierter Prozessstatus wird nicht frei über das normale Formular gesetzt; die Validierungsaktion ist fachlich eigenständig.

### Use Case

- Lesen: authentifizierte Nutzer bei nicht archivierten Use Cases.
- Bearbeiten: KI-Koordinator oder zugeordneter Business Owner.
- Lifecycle-Statuswechsel erfolgen ausschließlich über Reviews.
- Regulärer Lifecycle-Review: KI-Koordinator.
- Pilotstart: zusätzlich für den verantwortlichen Business Owner zulässig.
- Go-live-Ausnahmen: nur KI-Koordinator.

Diese Grenzen sind **keine UX-Optimierungsmasse** und müssen in #362–#365 erhalten bleiben.

---

# 2. A/B/C/D-Klassifizierung nach Seite

## 2.1 Arbeitsvorrat

**Gesamturteil:** Bereits stark auf Scanbarkeit und Aufgabe ausgerichtet. Kein strukturelles Redesign ohne neuen Befund.

| Information / Element | Klasse | Editierbarkeit / Quelle | Begründung / Konsequenz |
| --- | --- | --- | --- |
| konkrete Aufgabe / anstehende Entscheidung | **A** | abgeleitet, read-only | Kernzweck der Seite |
| Grund / erster Blocker | **A** | abgeleitet | erklärt unmittelbar, warum Handlungsbedarf besteht |
| Fälligkeit / Überfälligkeit | **A** | indirekt über Fachobjekt/Review | bestimmt Priorität |
| Zeilenaktion | **A** | Aktion | muss eindeutig bleiben |
| Entscheidungsreife | **A** | abgeleitet | zentral für Entscheidungsqueue |
| Phase | **B** | abgeleitet | Orientierung, aber nicht die eigentliche Aufgabe |
| Owner / Organisationseinheit | **B** | Quellobjekt | wichtig für Zuständigkeit/Einordnung |
| Top-Kennzahlen Überfällig/Blockiert/Aktiv | **B** | aggregiert | gute Management-/Scanübersicht, nicht zeilenbezogen |
| Nutzen gemessen / Ziel erreicht | **B** | aggregiert | Kontext zur Wirkung; nicht für jede aktuelle Aufgabe nötig |
| Priorisierungs-Erklärung | **C** | statische Erklärung | Transparenz über Sortierung |
| Stand-Datum | **C** | Systemdatum | Nachvollziehbarkeit |
| klare D-Kandidaten | – | – | **keine belastbare D-Darstellung identifiziert**; nicht künstlich reduzieren |

**Bestehendes Interaktionsmuster:** Bootstrap-Tabs trennen zwei echte Peer-Sichten („Meine Aufgaben“ vs. „Anstehende Entscheidungen“). Dieses Muster ist sinnvoll für **Ansichtswechsel**, nicht automatisch für sekundäre Detailinformationen.

---

## 2.2 Portfolio

**Gesamturteil:** Fachlich reichhaltig, aber die primäre Entscheidungsarbeit konkurriert mit mehreren gleichrangigen Analyseebenen.

| Information / Element | Klasse | Editierbarkeit / Quelle | Begründung / Konsequenz |
| --- | --- | --- | --- |
| Filter | **A** | GET-Controls | bestimmen die komplette Arbeitssicht; sichtbar lassen |
| Entscheidungs-Matrix | **A** | read-only, Links zu Use Cases | primäre Portfolioentscheidung |
| Nicht einordenbar / Klärungsbedarf | **A** | abgeleitet, handlungsfähige Links | konkrete nächste Klärung |
| Nutzen/Machbarkeit je Use Case | **A** | strukturierte Bewertung | Achsen der Matrix |
| Confidence | **A/B** | Bewertung | A bei Einordnungsunsicherheit, sonst unterstützend |
| Entscheidungsstatus | **A/B** | Entscheidung | wichtig zur Einordnung der Chips |
| Status-/Klärungs-Kennzahlen | **B** | aggregiert | gute Übersicht, aber sekundär zur Matrix |
| Fachdomänen-Verteilung | **B** | Klassifikation | relevant für Portfolio-Schnitt, nicht primäre Entscheidung |
| Portfolio-Landkarte / Gruppierungsverteilung | **B/C** | aggregiert | Analyseebene für Vertiefung; sollte Matrix nicht verdrängen |
| Confidence-/Status-Legenden | **B** | statisch | notwendig zum Lesen der Kodierung |
| tabellarische Matrix-Alternative | **B** | read-only | wichtige zugängliche Alternative; bestehendes `<details>` ist passend |
| erklärende Untertexte | **C** | statisch | Methodik-/Interpretationshilfe |
| `visible_total` im Header **und** erneut „Sichtbar“ im Stat-Strip | **D (eine der beiden Darstellungen)** | aggregiert | derselbe Wert wird in direkter Nähe doppelt exponiert; eine Darstellung genügt |

**Prioritärer Befund:** `Fachdomänen` steht aktuell vor der `Entscheidungs-Matrix`, obwohl die Matrix die eigentliche Arbeitsentscheidung trägt. Die lange Folge `Filter → Stats → Fachdomänen → Matrix → Tabellenalternative → Landkarte → Nicht einordenbar` erzeugt unnötig viele gleichwertige Ebenen.

---

## 2.3 Value Stream

**Gesamturteil:** Fachlich sauber, aber fünf gleichwertige Summary-Cards erzeugen eine falsche Gleichrangigkeit zwischen Kern des Wertstroms und Rahmeninformationen.

| Information / Element | Klasse | Editierbarkeit / Quelle | Begründung / Konsequenz |
| --- | --- | --- | --- |
| primärer Lifecycle / Arbeitsmodell | **A** | abgeleitet | obere Orientierung gemäß `DESIGN.md` |
| kanonische Next Action | **A** | Journey, Aktion | genau einmal dominant |
| Auslöser | **A** | ValueStreamForm | definiert Beginn / Bedarf |
| Ergebnis | **A** | ValueStreamForm | definiert den Wert-/Ergebnisendpunkt |
| Fokusentscheidung | **A** | Fokusmodell / ValueStreamForm | entscheidet über Vertiefung |
| Begründung der Fokusentscheidung | **A** | Fokusmodell | erklärt die Entscheidung |
| ausgewählte Fokusphase | **A** | Stage-Focus-Entscheidung | bestimmt Prozess-Deep-Dive |
| Im Scope / Nicht im Scope | **B** | ValueStreamForm | wichtige Begrenzung, aber nicht gleichrangig mit Trigger/Outcome |
| Strategisches Ziel | **B** | ValueStreamForm | strategischer Rahmen |
| Fachdomäne / Capability | **B** | Fokusmodell | Einordnung |
| Screening-Dimensionen | **B** | Fokusmodell | Entscheidungsbasis; kompakt halten |
| Stakeholder / Leitplanken | **B** | ValueStreamForm | Rahmen für weitere Analyse |
| E2E-Phasen | **B** | StageForm | Arbeitsstruktur; Fokusphase ist wichtiger als alle Detailfelder gleichzeitig |
| Rollen/Systeme/Dokumente/Engpässe/Baseline je Phase | **B/C** | StageForm | Deep-Dive-Kontext; nicht alles dauerhaft gleichrangig präsentieren |
| „Ausgewählt durch“ und Entscheidungsweg | **C** | Stage-Focus-Entscheidung | Audit-/Herkunftsinformation |
| Fokusstatus als Badge **und** gleichlautendes Feld „Entscheidung“ im selben Panel | **D-Kandidat** | Fokusmodell | doppelte Darstellung desselben Zustands; in #364 gegen finalen Kontext prüfen |

**State-gated disabled Aktionen im Detail:** Buttons wie „Nicht als Fokusphase ausgewählt“, „Erst Phasenerfassung abschließen“ und „Erst Fokusentscheidung abschließen“ sind keine deaktivierten Formularfelder. Ihre Beschriftung erklärt bereits den Grund. Sie sind dennoch in #364 darauf zu prüfen, ob Statuskopie statt eines deaktivierten Button-Looks klarer wäre.

---

## 2.4 Prozessanalyse

**Gesamturteil:** Größtes Read-only-Hierarchieproblem neben dem Use Case. Der Screenshot bestätigt exakt die aktuelle Card-in-Card-/Grid-Struktur.

| Information / Element | Klasse | Editierbarkeit / Quelle | Begründung / Konsequenz |
| --- | --- | --- | --- |
| primärer Lifecycle / kanonische Next Action | **A** | Journey | Orientierung und konkrete Arbeit |
| aktuelle Validierungsreife / Validierungsbedarf | **A** | ProcessValidation | entscheidet, ob die Analyse belastbar weiterverwendet werden darf |
| Prozessstart / Prozessende | **A/B** | ProcessAnalysisForm | Scoping-Rahmen |
| Auslöser / Ergebnis | **A** | ProcessAnalysisForm | Prozesszweck / Ergebnis |
| Ist-Ablauf | **A** | ProcessAnalysisForm | Kerndiagnose |
| Bottlenecks / Ursachen | **A** | ProcessAnalysisForm | Kerndiagnose |
| Baseline / Kennzahlen | **A** | ProcessAnalysisForm | Größenordnung / Evidenz |
| Rollen / Verantwortung | **A/B** | ProcessAnalysisForm | wichtig für Ursache und Ownership |
| zentrale Findings / bevorzugte Lösung / offener Lösungsvergleich | **A**, sobald Prozessdiagnose reif | abgeleitet / SolutionOption | nächste fachliche Entscheidung |
| Geschäftsregeln | **B** | ProcessAnalysisForm | Vertiefung der Diagnose |
| Übergaben / Schnittstellen | **B** | ProcessAnalysisForm | Vertiefung |
| Ausnahmen / Fehlerfälle | **B** | ProcessAnalysisForm | Vertiefung |
| Soll-Prinzipien | **B** | ProcessAnalysisForm | Rahmen für spätere Lösungswahl |
| Systeme / Datenobjekte | **B** | ProcessAnalysisForm | Architektur-/Informationskontext |
| Fokusphase + Kriterien als Auswahlquelle | **B/C** | vorgelagerte Stage-Focus-Entscheidung | Provenance; relevant, aber nicht Kerndiagnose |
| Quellenänderungen | **A/B bei Drift**, sonst nicht sichtbar | Provenance | bei tatsächlicher Abweichung entscheidungsrelevant |
| geprüfte Version, Validator, Rolle, Zeitpunkt, Notiz, Nachweis | **C** | ProcessValidation | Auditierbarkeit |
| historische Validierungen | **C** | ProcessValidation-Historie | Nachvollziehbarkeit |
| Prozessstatus bereits im Header **und** nochmals als Validierungsbadge | **D-Kandidat** | ProcessAnalysis | prüfen, ob eine Darstellung als Status genügt |

**Prioritärer Befund:** Im Block „Ist-Prozess und Ursachen“ werden Ist-Ablauf, Rollen, Bottlenecks, Baseline, Regeln, Handoffs, Ausnahmen und Soll-Prinzipien in gleichartigen, umrandeten Read-only-Flächen dargestellt. Die Oberfläche codiert dadurch keinen Unterschied zwischen Kerndiagnose und Detailkontext.

---

## 2.5 Use Case Detail

**Gesamturteil:** Höchste Priorität. `main` hat die Kopfaktionen gegenüber dem Screenshot bereits sinnvoll in „Weitere Aktionen“ konsolidiert. Im Arbeitszustand bestehen jedoch mehrere echte Darstellungsduplikate und zu viele gleichrangige Status-/Nachweisbereiche.

| Information / Element | Klasse | Editierbarkeit / Quelle | Begründung / Konsequenz |
| --- | --- | --- | --- |
| kanonische Next Action | **A** | Journey | genau einmal dominant |
| aktuelles Gate / Blocker / erster offener Punkt | **A** | WorkCheck/Blocker | unmittelbar handlungsleitend |
| Entscheidungsstatus | **A** | ApprovalDecision | zentrale Freigabeinformation |
| primärer Lifecycle-Rail | **A** | Journey/Review | einzige primäre Lifecycle-Darstellung gemäß `DESIGN.md` |
| aktuelle Bewertungs-Empfehlung | **A** | DecisionAssessment | Entscheidungsgrundlage |
| Confidence | **A** | DecisionAssessment | Belastbarkeit der Bewertung |
| primäre Erfolgsmetrik Ziel/Ist | **A** | UseCase | Ergebnisentscheidung |
| Problem / erwarteter Nutzen | **A/B** | UseCaseForm | fachliche Begründung des Vorhabens |
| Baseline | **B** | UseCaseForm | Vergleichsbasis; wichtig, aber nach Ziel/Ist |
| Prozess / Zielgruppe | **B** | UseCaseForm | Kontext |
| Business Owner / KI-Koordinator / Technical Owner | **B** | UseCaseForm | Steuerung und Accountability |
| nächste Lifecycle-Entscheidung / Termin | **A/B** | Review-/Servicelogik | A bei Fälligkeit, sonst Steuerungsinformation |
| Kosten | **B** | UseCaseForm | Portfolio-/Entscheidungskontext |
| Governance-Status | **A wenn Blocker**, sonst **B** | Governance-Artefakte | zustandsabhängig |
| Assessment-Rationale / Evidenz | **B** | DecisionAssessment | Begründung/Vertiefung |
| Metrikmethode / Zeitraum | **B** | UseCaseForm | Messqualität |
| Messdatum / Messnachweis | **B/C** | UseCaseForm | Evidenz/Audit |
| Architektur-Ursprung / Value Stream / Phase / Prozess / Lösungsoption | **B/C** | UseCaseOrigin | Traceability; nachrangig zur aktuellen Entscheidung |
| Assessment-Version, Datum, Assessor | **C** | DecisionAssessment | Metadaten |
| Governance-Akteur/Zeitpunkt/Rationale/Nachweislinks | **C**, sofern kein aktueller Blocker | Governance | Auditierbarkeit |
| Entscheidungs-/Änderungshistorie | **C** | Review/History | Nachvollziehbarkeit |
| Review-Copilot | **B/C** | optionaler Service | Hinweisgeber, keine Freigabeinstanz |
| Entscheidungsstatus als Überschrift **und identisches Badge** | **D** | ApprovalDecision | gleiche Aussage direkt nebeneinander |
| Lifecycle als Fact in `decision_state` **und** Dimension in `status_dimensions` **und** eigener Lifecycle-Rail | **D** für die zusätzlichen Lifecycle-Wiederholungen | Journey | `DESIGN.md` verlangt eine primäre Lifecycle-Darstellung |
| Erfolgsmetrik-Resultat im Decision-State **und** Messungsdimension **und** vollständiger Metrikbereich | **D/B** | UseCase | mindestens eine der kompakten Wiederholungen ist entbehrlich; genaue Zusammenführung in #363 |
| „Nächste Lifecycle-Entscheidung“ im Status-Dimensions-Block **und** Termin in Steuerung | **D/B** | Service | in #363 auf eine eindeutige Steuerungsstelle konsolidieren |
| `Use Case: <short_id> · <title>` am Ende der Ursprungskette | **D** | aktuelles Objekt | wiederholt das Objekt, auf dessen Detailseite man sich bereits befindet |

### Screenshot-Abweichung

Der bereitgestellte Use-Case-Screenshot zeigt vier gleichrangige Kopfbuttons. Auf `main` existiert bereits nur noch der sekundäre Dropdown „Weitere Aktionen“. Dieser Teil des Screenshot-Befunds ist **bereits überholt** und darf nicht erneut „repariert“ werden.

---

## 2.6 Lifecycle-/Review-Ansicht

**Gesamturteil:** Das fachliche Review-System ist nicht das Problem. Die Einstiegsbezeichnung auf dem Use Case ist zu generisch; die Zielansicht selbst ist bereits deutlich zustandsbezogener.

| Information / Element | Klasse | Editierbarkeit / Quelle | Begründung / Konsequenz |
| --- | --- | --- | --- |
| konkrete anstehende Entscheidung | **A** | ReviewForm | Hauptzweck |
| Gate-Blocker / Hinweise | **A** | DecisionCheck | Voraussetzung für Entscheidung |
| Entscheidung / neuer Status | **A** | ReviewForm/Service | fachlicher Beschluss; nur zulässige Zustände |
| Entscheidungsbegründung | **A** | ReviewForm | revisionsfähige Begründung |
| Pilotstart-Datum bei Pilotstart | **A** | ReviewForm | verbindlicher Übergang |
| Scale-Readiness-Nachweise bei Go-live | **A/B** | ReviewForm | für Produktiventscheidung erforderlich |
| Kompensationsmaßnahme, Owner, Frist bei Conditional Go | **A** | ReviewForm | zwingender Steuerungsinhalt |
| Ziel-gegen-Ergebnis-Kurzsicht | **A/B** | UseCase-Metrik | unterstützt Entscheidung |
| Review-Datum / nächster Termin | **B/C** | ReviewForm | Steuerung und Historie |
| Detailnachweise, Versionsreferenzen | **B/C** | ReviewForm | Evidenz |
| ursprüngliches geplantes Pilotende | **B** | sichtbares `disabled` DateField | Referenz für vorzeitige Produktivsetzung; sinnvoll read-only, aber visuell eindeutig kennzeichnen |

### Lifecycle-Review: wann und was passiert danach?

- Statusänderungen erfolgen laut `OPEN_QUESTIONS.md` ausschließlich über Reviews.
- ADR 0007 hält das bestehende Review als einzige führende Entscheidungs- und Historienquelle fest.
- Der reguläre Review ist für KI-Koordinatoren zugänglich; ein expliziter Pilotstart ist zusätzlich für den verantwortlichen Business Owner möglich.
- Die Review-Zielseite passt Überschrift und Felder bereits an den Zustand an, z. B. „Pilot starten“, „Scale Readiness & Entscheidung“ oder „Entscheidung dokumentieren“.
- Bei erfolgreichem Pilotstart wird in den Pilot-Arbeitsraum weitergeleitet.
- Bei Scale-Readiness-/Ergebnisentscheidung wird in den Entscheidungsbereich von `Wirkung & Betrieb` weitergeleitet.
- Sonstige Review-Entscheidungen führen zurück zum Use Case.

**UX-Befund:** Auf dem Use Case steht für Koordinatoren derzeit dennoch pauschal „Lifecycle-Review“ im Dropdown. Diese generische Einstiegsbezeichnung sagt weder, **welche** Entscheidung gerade ansteht, noch ob sie aktuell die kanonische Next Action ist. #363 soll deshalb die bereits vorhandene Journey-/Review-Logik für eine zustandsbezogene Beschriftung und Prominenz verwenden – ohne neue Statuslogik im Template zu erfinden.

---

# 3. Read-only vs. editierbar – Ist-Audit

## 3.1 Grundmuster

Die Detailseiten sind überwiegend **read-only Arbeitsansichten**. Änderungen erfolgen über explizite Edit-/Review-/Validierungsrouten. Das ist fachlich korrekt. Das UX-Problem entsteht dort, wo reine Anzeigeinformationen durch viele gleichartige umrandete Flächen dieselbe visuelle Sprache wie Arbeits-/Formbereiche erhalten.

Ziel für die Folge-Issues:

- Read-only bevorzugt als Text, Key-Value-Struktur oder flache Section.
- Karten/angehobene Flächen nur für echte Entscheidungs-, Interaktions- oder zusammengehörige Arbeitsblöcke.
- Berechtigungsbedingt nicht editierbare Formularfelder müssen ihren Grund erklären.

## 3.2 Tatsächlich deaktivierte Formular-Controls im relevanten Scope

| Ort | Control | Wann deaktiviert? | Grund | Aktuelle Erklärung | Audit-Befund |
| --- | --- | --- | --- | --- | --- |
| Use-Case-Bearbeitung | `business_owner` | bestehender UC, Benutzer ist **kein KI-Koordinator** | Owner-Zuordnung darf hier nicht durch Business Owner geändert werden | **keine feldbezogene Erklärung** | **Problem**: wirkt wie defektes Select; #363 soll Grund/Änderungsweg erklären oder klar read-only darstellen |
| Use-Case-Bearbeitung | `coordinator` | bestehender UC, Benutzer ist **kein KI-Koordinator** | gleiche Rollen-/Berechtigungsgrenze | **keine feldbezogene Erklärung** | **Problem**: wie oben |
| Review / vorzeitiger Go-live | `early_go_live_original_pilot_end` | wenn Ausnahmeblock sichtbar ist | unveränderliche Referenz auf ursprünglich geplantes Pilotende | Label vorhanden, aber normales disabled DateField | **vertretbar**, in #363 auf eindeutigere Read-only-Darstellung prüfen |
| Review / Pilotstart-only | `decision`, `new_status`, `go_live_exception_confirmed` | Pilotstart-Sonderpfad | festgelegter fachlicher Übergang | Controls werden zusätzlich in `HiddenInput` umgewandelt | **kein sichtbares Disabled-UX-Problem** |
| Review / vorzeitiger Go-live | `early_go_live_exception_confirmed` | falls ein nicht berechtigter Actor diesen Zustand erreicht | Ausnahme nur KI-Koordinator | expliziter Help-Text nennt Berechtigung | **gut erklärt**; kein genereller Handlungsbedarf |

## 3.3 Deaktivierte Aktionsbuttons, keine Formularfelder

| Ort | Beispiel | Befund |
| --- | --- | --- |
| Value Stream Phase | „Nicht als Fokusphase ausgewählt“, „Erst Phasenerfassung abschließen“, „Erst Fokusentscheidung abschließen“ | Grund steht direkt im Button. Semantisch verständlich, aber #364 soll prüfen, ob ein Statushinweis statt Button-Optik klarer ist. |
| Prozessanalyse / KI-Entwurf | „3 Lösungsentwürfe mit KI erstellen“ deaktiviert | Bei fehlender Readiness wird zusätzlich ein Warnhinweis mit fehlenden Voraussetzungen gezeigt. Fachlich gut erklärt. |
| Use Case / Review-Copilot | „Analyse starten“ deaktiviert, wenn OpenRouter fehlt | Begleittext erklärt fehlende Konfiguration. Optionaler Bereich; eher B/C als zentrale Arbeitsaktion. |

## 3.4 Read-only-Inhalte, die visuell zu stark wie Eingabe-/Arbeitscontainer wirken

- Value Stream: fünf gleichartige Summary-Cards für Trigger, Outcome, Scope und strategisches Ziel.
- Prozessanalyse: acht gleichartige umrandete Artefakt-Sections innerhalb einer bereits umrandeten Card.
- Prozessanalyse: Validierungsmetadaten und Kerndiagnose liegen als ähnlich gewichtete Panels in einer langen Folge.
- Use Case: mehrere Status-, Readiness-, Arbeitszustands-, Steuerungs-, Governance-, Copilot- und Historienflächen stehen nacheinander; die fachliche Rangordnung ist nur teilweise sichtbar.

---

# 4. Problem → Ursache → Auswirkung → Priorität

| Bereich | Problem | Ursache | Auswirkung | Priorität | Empfohlene Richtung |
| --- | --- | --- | --- | --- | --- |
| Use Case | Lifecycle wird mehrfach dargestellt | Decision-State-Fact + Arbeitszustandsdimension + Lifecycle-Rail | Nutzer muss gleiche Zustandsinformation mehrfach interpretieren | **sehr hoch** | Rail als primäre Darstellung; zusätzliche Wiederholungen entfernen/zusammenführen |
| Use Case | Entscheidungsstatus steht als Text und identisches Badge nebeneinander | doppelte Statuscodierung ohne Zusatzinformation | visueller Lärm | **hoch** | eine semantisch vollständige Darstellung |
| Use Case | Metrikstatus wird in mehreren Status-/Metrikblöcken wiederholt | Status-Dimensionen und fachlicher Metrikblock parallel | Ziel/Ist verliert gegenüber Statusetiketten an Klarheit | **hoch** | Metrikblock als fachliche Quelle priorisieren; kompakte Wiederholung nur bei echtem Entscheidungsnutzen |
| Use Case | generischer Menüpunkt „Lifecycle-Review“ | Einstieg ist nicht an die bereits vorhandene zustandsabhängige Review-/Journey-Logik gekoppelt | unklar, wann und wofür die Aktion ausgeführt werden soll | **sehr hoch** | fällige konkrete Entscheidung benennen; nur als dominante Aktion, wenn tatsächlich Next Action |
| Use Case Form | Business Owner / Koordinator sichtbar disabled ohne Grund | serverseitige Berechtigungsregel wird UI-seitig nicht erklärt | Nutzer vermutet Fehler oder fehlende Berechtigung ohne Lösungsweg | **hoch** | Read-only-Hinweis: wer ändern darf / wo ändern |
| Use Case | Ursprung endet mit aktuellem Use Case als eigener Zeile | Traceability-Kette wiederholt das aktuelle Objekt | kein Zusatzwert | **mittel** | aktuelle Objektzeile entfernen; Herkunft bis zur Quelle zeigen |
| Use Case | viele sekundäre Bereiche dauerhaft offen | Governance, Herkunft, Copilot, Historie gleichwertig gestapelt | lange Seite, zentrale Entscheidung verliert Dominanz | **sehr hoch** | A sichtbar; B/C über gemeinsamen Disclosure-Primitive aus #362 |
| Prozessanalyse | Kerndiagnose und Detailkontext haben identische Kartenform | `architecture-artifact-grid` behandelt 8 Felder gleich | Ursache/Baseline/Ablauf sind nicht schneller erfassbar als Regeln/Ausnahmen | **sehr hoch** | Diagnosekern flach priorisieren; Details sekundär |
| Prozessanalyse | Card-in-Card-Optik | umrandete Sections in umrandetem Arbeitsblock | unnötige visuelle Schwere, Read-only wirkt formularartig | **hoch** | Linien/Abstand/Key-Value statt Container pro Feld |
| Prozessanalyse | Validierungsmetadaten früh und groß | Auditinformation als kompletter Panelblock | Kerndiagnose rutscht nach unten | **hoch** | Validierungszustand sichtbar, Metadaten C nachrangig |
| Value Stream | Trigger, Outcome, Scope und Strategie exakt gleich gewichtet | 5 gleiche Summary-Cards | Wertstromkern und Rahmen sind nicht unterscheidbar | **hoch** | Trigger/Outcome primär; Scope/Strategie gebündelt sekundär |
| Value Stream | detaillierte Stage-Facts und Fokuskontext können lange Seite erzeugen | alle Phaseninformationen gleichzeitig sichtbar | Deep-Dive beginnt vor bewusster Auswahl | **mittel/hoch** | Fokusentscheidung prominent; Detaildaten bedarfsgerecht |
| Portfolio | Entscheidungs-Matrix kommt erst nach Fachdomänen | Analyseverteilung steht vor Arbeitsentscheidung | primärer Entscheidungszweck wird verzögert | **hoch** | Matrix + Klärungsbedarf nach Filter/kompakter Übersicht priorisieren |
| Portfolio | mehrere Analyseebenen in langer Folge | Domains, Matrix, Tabelle, Landkarte, Unclassified jeweils eigene große Section | hohe vertikale kognitive Länge | **hoch** | sekundäre Analysen klar nachrangig / Disclosure |
| Portfolio | sichtbare Gesamtzahl doppelt | Header und Stat-Strip | unnötige Wiederholung | **niedrig/mittel** | eine Darstellung genügt |
| Arbeitsvorrat | kein relevanter Strukturmangel identifiziert | – | unnötiger Umbau würde Regression erzeugen | **niedrig** | nur gegen gemeinsame Regeln validieren |
| Cross-cutting | mehrere Disclosure-/Ansichtsmuster | `portfolio-secondary-view`, `architecture-disclosure`, Bootstrap-Tabs | Gefahr eines dritten Parallelpatterns | **hoch für #362** | bestehende Muster inventarisieren und Zweckgrenzen definieren |

---

# 5. Bestehende Interaktions-/Disclosure-Muster als Übergabe an #362

Bereits auf `main` eindeutig vorhanden:

1. **Bootstrap-Tabs im Arbeitsvorrat**
   - sinnvoll für zwei gleichrangige, wechselseitige Arbeitsansichten;
   - kein Ersatz für das Auf-/Zuklappen sekundärer Detailinformationen.

2. **Native `<details>/<summary>` im Portfolio**
   - Klasse `portfolio-secondary-view`;
   - bereits für eine sekundäre tabellarische Alternative eingesetzt;
   - responsive Styles vorhanden.

3. **Native `<details>/<summary>`-Styling in `static/css/architecture.css`**
   - `.architecture-disclosure`, `.artifact-disclosure`, `.source-disclosure`;
   - sichtbarer `:focus-visible` ist bereits vorgesehen.

4. **Use-Case-Historie**
   - Scale-Readiness-Snapshot verwendet ebenfalls native `<details>`.

**Vorgabe für #362:** Nicht pauschal Tabs und Disclosures vereinheitlichen. Erst die Semantik trennen:

- **Tabs:** Peer-Views / alternative Arbeitsansichten.
- **Disclosure:** sekundäre oder vertiefende Information innerhalb derselben Ansicht.

#362 soll daraus einen gemeinsamen, semantisch dokumentierten Disclosure-Primitive ableiten, ohne eine neue UI-Bibliothek oder ein drittes paralleles Pattern einzuführen.

---

# 6. Verbindliche Übergabe an die Folge-Issues

## #362 · UI-Grundlage

Muss auf Basis dieses Audits:

- alle vorhandenen `<details>/<summary>`-/Disclosure-Varianten vollständig inventarisieren;
- `portfolio-secondary-view`, `architecture-disclosure`, Use-Case-Details und weitere Fundstellen vergleichen;
- einen gemeinsamen Disclosure-Primitive plus klare Einsatzregel in `DESIGN.md` festlegen;
- Bootstrap-Tabs als separates Peer-View-Muster behandeln;
- Fokus, Tastatur, Reduced Motion, Touch-Ziele und Responsive-Verhalten absichern;
- keinen neuen Parallelstandard schaffen.

## #363 · Use Case Detail & Lifecycle-Aktionen

Muss mindestens adressieren:

- eine primäre Lifecycle-Darstellung statt der aktuellen Wiederholungen;
- eine klare Entscheidung-/Gate-/Next-Action-Hierarchie;
- D-Duplikate im Decision State und Ursprung entfernen/zusammenführen;
- Assessment-Empfehlung, Confidence und Ziel/Ist priorisieren;
- Governance, Nachweise, Herkunft und Historie nachrangig behandeln;
- `business_owner` und `coordinator` bei Nicht-Koordinatoren verständlich als nicht editierbar erklären;
- generischen „Lifecycle-Review“-Einstieg anhand vorhandener Journey-/Review-Logik zustandsbezogen machen;
- keine Review-, Status-, Permission- oder Gate-Logik duplizieren.

## #364 · Prozessanalyse & Value Stream

Muss mindestens adressieren:

- Prozessanalyse: Ist-Ablauf, Bottlenecks/Ursachen, Baseline und Rollen als Diagnosekern vor Regeln/Handoffs/Ausnahmen/Soll-Prinzipien;
- Prozessvalidierungsstatus sichtbar halten, Auditmetadaten nachrangig;
- Card-in-Card-/Read-only-Gleichrangigkeit reduzieren;
- Value Stream: Auslöser und Ergebnis vor Scope/Strategie;
- Fokus-/Phasenentscheidung prominent halten;
- detaillierte Rahmen-/Stage-Daten bedarfsgerecht nachrangig darstellen;
- state-gated deaktivierte Aktionsbuttons auf verständliche Statuskommunikation prüfen.

## #365 · Portfolio & Abschluss

Muss mindestens adressieren:

- Portfolio-Matrix und Klärungsbedarf als primäre Arbeitsansicht;
- Fachdomänen-/Landkarten-/Verteilungsanalyse nachrangig;
- doppelte Summary-Werte reduzieren, ohne Informationsverlust;
- Arbeitsvorrat nur auf Konsistenz prüfen, nicht ohne Befund redesignen;
- danach alle #360-Seiten gegen Responsive, Accessibility, Read-only/Editierbar, eine dominante Next Action und Regression validieren.

---

# 7. Entscheidungen und ausdrücklich offene Punkte nach #361

## Durch das Audit entschieden

- Das Problem ist primär **Informationshierarchie und Darstellungsredundanz**, nicht das Dark Theme.
- Arbeitsvorrat benötigt aktuell keinen strukturellen Umbau.
- Use Case und Prozessanalyse besitzen die höchste UX-Priorität.
- Kategorie D bedeutet **Darstellung konsolidieren**, nicht Datenmodell oder Historie löschen.
- Das bestehende Review-System bleibt fachlich führend.
- Die bereitgestellte Use-Case-Kopfzeile ist gegenüber `main` teilweise veraltet; `main` hat die Aktionen bereits konsolidiert.
- Es existieren bereits mehrere native Disclosure-Muster; #362 muss diese konsolidieren statt einen neuen Standard daneben zu setzen.

## Noch bewusst offen für #362–#365

- exakte gemeinsame CSS-Klasse / Include-Struktur des Disclosure-Primitives;
- welche B-Informationen standardmäßig offen oder geschlossen sind (nur soweit der obige UI-Vertrag keine Sichtbarkeitsregel festlegt);
- exakte neue visuelle Gruppierung je Seite;
- exakte zustandsbezogene Bezeichnung des Review-Einstiegs je Journey-Zustand;
- ob einzelne D-Kandidaten mit zusätzlichem Kontext doch einen B-Wert erhalten – dies ist bei Umsetzung gegen den realen Zustand zu verifizieren.

---

# 8. Abschlusscheck #361

- [x] Screenshots den aktuellen Seiten, Routes und Templates zugeordnet
- [x] Screenshot-vs.-`main`-Abweichungen dokumentiert
- [x] wesentliche sichtbare Informationen A/B/C/D klassifiziert
- [x] zustandsabhängige A/B/C/D-Einstufungen als verbindliche Wenn–Dann-Regeln festgelegt
- [x] relevante Edit-/Permission-Grenzen dokumentiert
- [x] tatsächlich deaktivierte Formular-Controls im geprüften Scope getrennt erfasst
- [x] rein visuelle Read-only-Probleme getrennt erfasst
- [x] Problem/Ursache/Auswirkung/Priorität dokumentiert
- [x] vorhandene Tab-/Disclosure-Muster als Input für #362 identifiziert
- [x] konkrete Übergabeanforderungen für #362–#365 abgeleitet
- [x] keine Business-Logik, URLs, Berechtigungen oder Lifecycle-Logik geändert

**Ergebnis:** #361 liefert mit diesem Dokument die fachliche Baseline. Die nächste technische Entscheidung erfolgt erst in #362.
