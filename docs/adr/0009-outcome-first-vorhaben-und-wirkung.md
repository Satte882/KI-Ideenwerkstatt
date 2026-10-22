# ADR 0009: Outcome-first – vorhabensbezogene Identität und Wirkungsbezug

**Status: Vorgeschlagen (NICHT angenommen)**  
**Datum:** 22.10.2026  
**Issue:** #144 · **Folge-Issues:** #145, #146, #147; #148 separat  
**Basis:** `main` / `f8cabbc418b4777d7bfd075e6c0dc1a3322aaa41`  
**Geltung:** Architekturvorschlag; **keine** Freigabe zur Implementierung oder zum Merge.

## 1. Problem und Entscheidungsziel

KI-Ideenwerkstatt bildet heute einen problem- und prozessbezogenen Discovery-Pfad ab: Idee/Problem → Value Stream → Fokus/Prozess → Lösungsalternativen → gegebenenfalls KI-Use-Case. `SolutionSelectionDecision` hält Vergleich und Diagnose unveränderlich fest, aber kein fachlich führendes **vorhabensbezogenes Geschäftsergebnis**. Eine Non-KI-Präferenz kann die Discovery regulär beenden; strukturierte Pilot-/Wirkungsnachweise hängen dagegen überwiegend am `UseCase`.

`ValueStreamFocus` und `StageFocusDecision` referenzieren je einen `ValueStream` per `OneToOne`. `save_stage_focus_decision` nutzt `update_or_create(value_stream=...)`: unabhängige Vorhaben können denselben Phasenfokus überschreiben. Die `post_save`-Kurzpfade erstellen nur bei bisher fehlender Entscheidung; sie überschreiben nicht unmittelbar, nutzen aber denselben globalen Zustand. Auch `focus_readiness_blockers` prüft nur die globale Value-Stream-Selektion.

**Ziel:** Geschäftsergebnis, begrenzten Vorhabens-/Pilotbeitrag und **Wirkannahme** über beide Lösungsklassen (KI/Non-KI) nachvollziehbar führen; bestehende Legacy-Pfade, Hard Gates und unveränderliche Nachweise erhalten. Ein korrektes **„noch nicht nachgewiesen“** ist zulässig. Dies ist **kein** Vorschlag, zuerst ein KI-Tool, eine Baseline oder einen vollständigen Zielprozess zu erzwingen.

## 2. Glossar und logische Bounded Contexts

| Begriff | Bedeutung / Source of Truth | Nicht verwechseln mit |
|---|---|---|
| **Geschäftsergebnis (Business Outcome)** | Angestrebte Kunden-/Unternehmenswirkung **eines Verbesserungsvorhabens**, z. B. mehr wirtschaftlich tragfähige Buchungen | `ValueStream.outcome`, Prozessoutput oder eine gelungene Teilaufgabe |
| **Vorhabens-/Pilotbeitrag** | Abgegrenzte, überprüfbare Veränderung, die das Vorhaben leisten soll | Übergeordnetes Geschäftsergebnis oder KI-Feature |
| **Wirkannahme** | Explizit falsifizierbarer vermuteter Kausalpfad *Beitrag → Geschäftsergebnis*; nach Evidenzstufe und Bestätigung getrennt | Bereits bewiesener ROI bzw. bestätigte Hauptursache |
| **Value-Stream-Outcome** | Vom Wertstrom für seinen Empfänger erzeugtes Endergebnis; heute `ValueStream.outcome` | Vorhabensbezogenes Geschäftsergebnis |
| **Prozessergebnis** | Output des analysierten Teilprozesses; heute `ProcessAnalysis.outcome` | Business Outcome |
| **Prozesswirkung** | Gemessene Veränderung der Prozesskennzahl (Zeit, Qualität, Aufwand etc.) | Nachweis, dass Umsatz, Konversion oder Marge dadurch stiegen |
| **Wirkungsreview / Outcome Workspace** | Nachgelagerte Evidenz- und Entscheidungsansicht; bestehende `OUTCOME_WORKSPACE` führt Use-Case-Pilot/Betrieb | Ort zur Definition des frühen Geschäftsziels |
| **Outcome Owner** | Fachlich verantwortliche Person/Rolle für Ziel und Nutzenrealisierung | Automatische Berechtigung zur Bewertung, Freigabe, Pilot oder Go-live |

DDD-light innerhalb des **bestehenden Django-Monolithen**: (A) **Vorhaben & Outcomes** verantwortet Geschäftsergebnis, Wirkannahme, Evidenzstand und Identität; (B) **Business Architecture & Discovery** verantwortet Value Stream, Fokus, Prozess und Diagnose; (C) **Solution Decision** verantwortet Vergleich und unveränderliche Wahl; (D) **Delivery, Review & Evidence** verantwortet existierende KI-Use-Case-Freigaben sowie belegte Wirkung. Dies sind logische Ownership-Grenzen, **keine** neuen Microservices/Django-Apps.

## 3. Gleichwertiger Variantenvergleich – erst Vergleich, dann Vorschlag

Alle Varianten werden an denselben Anforderungen gemessen: **(a)** direkter Use Case ohne Idee/Discovery; **(b)** mehrere Phasen/Prozesse pro Vorhaben; **(c)** mehrere Vorhaben pro Value Stream; **(d)** KI- und Non-KI-Wirkung; **(e)** Identität/Historie; **(f)** Legacy-Migration; **(g)** Rollen; **(h)** Umfang realer Aufrufer und Wartbarkeit.

### Variante A – `IdeaCandidate` zum führenden Vorhaben ausbauen
- **(a)** Direkte Use Cases benötigen eine nachträglich angelegte synthetische Idee oder werden eine dauerhafte Ausnahme; auch vorhandene direkte Use Cases sind zu respektieren.
- **(b/c)** `IdeaCandidate.discovery_process_analysis` und `promoted_use_case` sind heute `OneToOne`; für 0..n Prozesse und Umsetzungen wären beide Beziehungen bzw. die Promotion-Semantik neu zu definieren. Das globale Focus-Problem bleibt separat.
- **(d/e)** Positiv: Idee und Urheber sind vorhanden. Negativ: Status `promoted` verlangt heute einen `promoted_use_case`; ein erfolgreiches Non-KI-Vorhaben lässt sich nicht ohne Bedeutungsänderung abschließen.
- **(f/g/h)** Weniger neue Entitäten, aber hohe Änderungstiefe in Inbox, Triage, Discovery-Handover, Direkt-Intake und Berechtigungen; die langfristige Vorhabensverantwortung würde auf den niederschwelligen Eingangskorb übergreifen.
- **Tragfähig wenn:** Der Produktentscheid ausdrücklich jede Initiative als IdeaCandidate mit revidierter Inbox-/Promotionssemantik definiert.

### Variante B – eigene vorhabensbezogene Identität (z. B. `ImprovementInitiative`)
- **(a)** Direkte Use Cases können **ohne** Vorhaben weiterleben; bei späterem oder neuem Anlass kann ein fachlich begründetes Vorhaben explizit zugeordnet werden.
- **(b/c)** 0..n Prozesse und unabhängige vorhabensbezogene Phasenentscheidungen möglich, ohne den Value Stream selbst zum Projekt zu machen. Bereits vorhandene per-Prozess-Lösungswahl bleibt fachlich konsistent, sofern jeder neue Prozess genau einem Vorhaben zugeordnet ist.
- **(d/e)** Derselbe Outcome-Träger für Non-KI und KI; eindeutige revisionsfähige Identität und dokumentierbarer Outcome-Change-Impact.
- **(f/g/h)** Neue Tabelle und kontrollierte Links/Policies nötig; migrations- und aufruferseitig vor allem Discovery-Fokus, Outcome-Gates, Exporte und Intake betroffen. Der bestehende Inbox-/Use-Case-Lifecycle muss aber nicht semantisch umdefiniert werden.
- **Tragfähig wenn:** Kein schwergewichtiger zweiter Status-/Governance-Lifecycle entsteht; der neue Datensatz ausschließlich Outcome/Identität besitzt.

### Variante C – `ProcessAnalysis` als Vorhabensanker
- **(a)** Direkte Use Cases ohne Prozess müssten künstliche Prozesse erhalten oder dauerhaft ohne Outcome-Führung bleiben.
- **(b/c)** `ProcessAnalysis` gehört heute genau zu **einer** `ValueStreamStage`. Mehrere Prozesse unter einem Vorhaben benötigen wiederum einen darüberliegenden Anker oder eine fachlich fragwürdige „Masterprozess“-Hierarchie. Gemeinsame Stage kann weiterhin mehrere Prozessanalysen enthalten, beseitigt aber keinen Vorhabensanker.
- **(d/e)** Vorteil: Diagnose und Versionierung existieren bereits. Nachteil: Outcome-Definition käme **nach** der Fokusentscheidung und KI-/Non-KI-Nutzung bleibt prozesszentriert.
- **(f/g/h)** Kurzfristig wenig Schema-Neuaufbau, langfristig hohe Kopplung in ProcessValidation, SolutionOptions, Prozessversionen, Discovery- und Direktpfaden.
- **Tragfähig wenn:** Das Produkt bewusst nur Einzelprozess-Vorhaben kennt. Das widerspricht dem geforderten frühzeitigen Outcome-first- und Mehrprozesspfad.

### Entscheidungsvorschlag (noch NICHT angenommen)

**Variante B bevorzugen.** Sie erfüllt die Identitäts- und KI-/Non-KI-Anforderungen mit der saubersten fachlichen Trennung. Der zusätzliche Modell-/Zuordnungsaufwand ist real; der vermeintlich einfachere Ausbau von `IdeaCandidate` verlangt jedoch umfassende Änderungen der bestehenden Promotion-/OneToOne-Semantik. `ProcessAnalysis` ist für Outcome-first zu spät und zu eng.

Keine Variante vermeidet die gesonderte **Fokus- und Entscheidungsumstellung**. Diese ist ein eigenes Implementierungsinkrement. Die Entscheidung über Variante B ist **ausdrücklich durch den Nutzer zu treffen**, nicht durch dieses Dokument automatisch wirksam.

## 4. Vorgeschlagene Kardinalitäten und Grenzen (falls B angenommen wird)

- `ImprovementInitiative` (Vorhaben): identitätsstabil, 0..n verknüpfte **IdeaCandidates**, 0..n **ProcessAnalyses**, 0..n realisierte Lösungen/Reviews. Ein vorhabenloser Eingang oder direkter Use Case bleibt möglich.
- Jede **IdeaCandidate** ist in der ersten Ausbaustufe höchstens einem Vorhaben zugeordnet; unverknüpfte Inbox-Einträge behalten sämtliche bisherigen Statusregeln. Verschiedene Ideen dürfen in **einem** Vorhaben gebündelt werden. Keine automatische Promotion oder fiktive Idee.
- Jede neue **ProcessAnalysis** gehört höchstens **einem** Vorhaben; alte Prozessanalysen dürfen ungebunden bleiben. Mehrere Vorhaben können **denselben Value Stream und dieselbe Phase** nutzen, erhalten aber separate Prozess- und Lösungsentscheidungen. Eine spätere Mehrfachnutzung derselben Prozessanalyse wäre ein eigener Architekturentscheid; nicht stillschweigend ermöglichen.
- **ValueStream** bleibt organisationsweit und langlebig; 0..n Vorhaben können ihn verwenden. Er besitzt **kein** vorhabensspezifisches Business Outcome.
- **ValueStreamFocus** bleibt zunächst **einmaliges/globales Screening** des Value Streams (Capability, strategische Relevanz etc.). Seine Auswahl bedeutet **nicht**, dass die Fokusphase eines konkreten Vorhabens bereits gewählt wurde.
- **StageFocusDecision** wird für neue Vorhaben **vorhabensbezogen, nachvollziehbar versioniert/append-only**. `ValueStream` + `Initiative` + `Stage` müssen zusammenpassen; aktive Wahl je Vorhaben und betrachteten Value Stream eindeutig, ältere Zustände lesbar. Bestehende globale Fokusentscheidungen sind **Legacy**, keine automatisch übernommenen Vorhabensentscheidungen. Ob eine konditionale FK-Migration derselben Tabelle oder eine strikt isolierte Legacy-Projektion der sicherere Implementierungsweg ist, muss #145 gegen die konkrete Datenlage abgleichen; **fachliche Identität und Nichtüberschreiben sind verbindlich**.
- Der neue **Fokus-Gate** verlangt bei vorhabensgebundenem Prozess eine dazugehörige, aktuelle Phasenentscheidung; das globale Screening allein ist **unzureichend**. Bei historischen ungebundenen Prozessen bleibt der bisherige Gate-Vertrag erhalten, bis eine bewusste Migration erfolgt.
- `SolutionOption` und `SolutionSelectionDecision` bleiben **pro Prozess**. Die bereits existierende „genau eine bevorzugte Option pro ProcessAnalysis“-Regel erfordert die oben festgelegte exklusive Prozesszuordnung; keine global bevorzugte Option für mehrere Vorhaben.
- `UseCase` kann 0..1 Vorhabenbezug erhalten, ein Vorhaben kann 0..n KI-Use-Cases unterstützen; `UseCaseOrigin` bleibt Quelle der prozessualen Herkunft. Ein direkter Use Case ohne Idee, Initiative oder Prozess bleibt gültig und vollständig funktionsfähig. Zuordnung nicht aus Texten raten.

**Kurzpfade/Signale:** `stage_focus.persist_focus_from_existing_process` und `persist_focus_from_existing_origin` dürfen für neue vorhabensgebundene Artefakte **keine globale Freigabe erzeugen oder implizit zuordnen**. Legacy-Fälle behalten ihren bisherigen bewusst dokumentierten Kurzpfad. `save_stage_focus_decision(update_or_create)` darf nach der Umstellung nicht über eine globale Key-Kombination vorhabensspezifische Entscheidungen überschreiben.

## 5. Source of Truth, Bestandsfelder, Zuständigkeit

**Führende Quelle (nur für neue/ausdrücklich gebundene Vorhaben):** `ImprovementInitiative` hält Geschäftsergebnis, abgegrenzten Beitrag, Wirkannahme, benannte Evaluationskriterien, Evidenzgrad, fachlichen Bestätigungs-/Versionsstand und Outcome Owner. Baseline und Zahlenziel dürfen im frühen Stadium fehlen.

| Bereits existierendes Feld | Vorschlag | Warum |
|---|---|---|
| `ValueStream.outcome` | **Beibehalten** als Endergebnis des Value Streams | Fachlich andere Bedeutung |
| `ProcessAnalysis.outcome` | **Beibehalten** als Output des Teilprozesses | Kein Business Outcome |
| `ValueStream.strategic_objective` | **Beibehalten** als langfristigen Kontext; nicht in Vorhabensziel umetikettieren | Ein Value Stream trägt viele Vorhaben |
| `WorkDesignAssessment.business_outcome` | **Beibehalten** als Arbeitsgestaltungs-/Rollenbezug; bei gebundenem Vorhaben aus dessen aktueller Zielrevision **kontextualisieren**, nicht als zweite führende Zieldefinition fortschreiben | TASKSHIFT ist optional; vorhandene historische Assessments bleiben lesbar |
| `UseCase.expected_benefit` | **Beibehalten** als konkrete KI-Interventions-/Nutzenbeschreibung; auf Outcome-ID/-Revision verweisen, nicht als führendes Gesamtgeschäftsziel interpretieren | Direkte und historische Use Cases behalten ihre Semantik |
| `SolutionOption.expected_value` | **Beibehalten** für interventionsspezifischen erwarteten Beitrag; zusätzlich belastbare Verknüpfung zur gemeinsamen Outcome-Revision im **Entscheidungssnapshot** | Ein Text allein belegt keinen geschäftlichen Wirkzusammenhang |
| `UseCase.metric_*` | **Beibehalten** als bestehende KI-Use-Case-/Pilotmetriken; für Non-KI keinen künstlichen Use Case oder synchronisierten Spiegel anlegen | Andere fachliche Messgrenze |
| `DecisionAssessment.strategic_fit`, `business_value`, `IdeaCandidate.quick_score` | **Nicht blind entfernen**; sie bleiben heuristische Einordnungen, dürfen aber einen konkret benannten Outcome-Beitrag bei bindender Auswahl nicht ersetzen | Bestand, bestehende UI/Gates |

**Outcome Owner:** Ein registrierter Benutzer ist **nicht fachlich zwingend**. Vorschlag: notwendige benannte verantwortliche Funktion/Organisation (auch ohne Login), optional referenziertes Systemkonto; nur aktive berechtigte Systemnutzer dürfen im Namen ihrer Rolle bestätigen, bewerten oder freigeben. Diese Zuordnung erteilt **keine** neuen Berechtigungen und hebt bestehende Personen-/Rollentrennung nicht auf. Eine externe/unklare verantwortliche Person bleibt zur Freigabe als ungeklärte Zuordnung sichtbar.

## 6. Decision Contract, Evidenz und Stale-Verhalten

**Keine Intake-Sperre.** Ein Mitarbeitender darf ein Problem ohne bekannte Gesamtkennzahl melden. Verbindliches Gate wird bei der **vorhabensgebundenen Lösungspräferenz** in `select_preferred_solution` durchgesetzt, **nicht** allein in Form, View oder LLM:
1. Ein eindeutiges fachlich akzeptiertes Geschäftsergebnis, Vorhabensbeitrag und eine explizit als **Hypothese oder stärkere Evidenz** gekennzeichnete Wirkannahme sind vorhanden.
2. Der Beitrag **jeder** verglichenen Option zum gleichen Outcome und das zugrunde liegende Belegniveau müssen prüfbar sein; Nicht-KI-Alternativen bleiben vollwertig. Keine automatische Lösungsauswahl durch Generator/Critic.
3. Ein KI-generierter Outcome-/Wirkannahmetext gilt bis zu expliziter menschlicher fachlicher Annahme **nur als unbestätigter Vorschlag**. **Die Annahme einer Hypothese macht sie nicht zum bewiesenen Geschäftserfolg.**
4. Numerische Baseline, Zielwert, ROI und Evidenz einer bestätigten Kausalwirkung sind **im frühen Vergleich nicht Voraussetzung**; die vorhandenen späteren Use-Case-Freigabe-/Pilot-Gates bleiben unverändert.
5. Ungeklärte Ursachen/Geschäftsgrenzen bleiben offen; die heutige Pflicht zu einer bestätigten Ursache wird **nicht** in diesem ADR gelockert. #146 muss fallbezogen prüfen, ob bei nicht-kausal begründeten Maßnahmen ein eigener, gesicherter Entscheidungsmodus nötig wäre.

Bei der Wahl: **immutable Outcome-Snapshot** (Initiative-ID, Outcome-Revision, Wortlaut, Beitragsdefinition, Hypothese, Evidenzgrad, fachlicher Bestätiger, betroffene Metrikdefinition) zusätzlich zu unveränderlichem Vergleichs- und Diagnosesnapshot. **Keine** nachträgliche Änderung bestehender Entscheidungen.

Bei Änderung der führenden Outcome-Revision: neu gebundene bisherige Entscheidungen werden als **„Neubewertung notwendig“** *abgeleitet*, nicht mutiert; neue verbindliche Übernahmen/Entscheidungen verlangen erneuten Review. Historische Entscheidungen **ohne Bindung** bleiben gültig und werden als **„historisch nicht gebunden“**, **nicht automatisch „stale“**, angezeigt. Eine inhaltliche Zieländerung darf nicht bloß durch Synchronisieren redundanter Freitexte verborgen werden.

## 7. Minimale gemeinsame KI-/Non-KI-Wirkungsverfolgung

Eine Non-KI-Entscheidung darf Discovery ohne künstlichen KI-Use-Case beenden; **die Frage, ob das Geschäftsergebnis eintritt, bleibt trotzdem offen**.

Für #147 vorgeschlagen: ein **kleiner, vorhabensbezogener Review-/Wirkungsnachweis** mit Interventions-/Entscheidungsbezug, benannter Verantwortung, Messdefinition, einmaligem aktuellem Messstand und Nachweisreferenz. **Getrennte Feststellungen**:
- Prozess-/Capability-Ergebnis erreicht, verfehlt oder unbekannt;
- übergeordnetes Geschäftsergebnis gemessen/noch offen;
- Plausibilität bzw. Attribution der **Wirkannahme** gesondert gekennzeichnet; Prozessziel „erreicht“ darf nicht zu „geschäftlicher Erfolg nachgewiesen“ konvertieren;
- offene Non-KI-Wirkungsfrage sichtbar, auch wenn die Discovery-Entscheidung abgeschlossen ist.

Die bestehenden `UseCase.metric_*`-, `Review`-, Governance-, Pilot-/Go-live- und `OUTCOME_WORKSPACE`-Mechanismen bleiben für KI führend; der zusätzliche gemeinsame Review darf kein zweiter vollständiger Use-Case-Lifecycle werden. **Keine** jetzt vorgezogene versionierte Messreihe, Trend-/Drift-Engine oder External-Delivery-Integration (Roadmap: „Later/Priorität 3“). Operative Umsetzung außerhalb des Systems bleibt erlaubt.

## 8. Abhängigkeiten, Migration und Legacy-Regeln

1. **#145 – Identität/Fokus:** neue fachliche Identität und optionale Verknüpfungen; Varianten der konkreten Stage-Focus-Persistenz anhand realer Daten und Signal-Aufrufer prüfen, mit migrationssicheren Defaults. Neu-Pfade strikt initiative-scoped; Legacy-Pfade weiter gültig.
2. **#146 – Vergleich/Entscheidung:** bindender Outcome-/Bestätigungs-/Evidenzvertrag und immutable Snapshot; altes Auswahl-/Process-Gate erhalten, Änderungen der Outcome-Revision machen **nur gebundene** Entscheidungen erneuerungsbedürftig.
3. **#147 – gemeinsame Wirksamkeit:** kleine Review-Projektion für Non-KI plus Trennung von Prozess- und Business-Messung; vorhandene `UseCase`-Gates werden nicht an ein neues Vorhaben zwangsweise gekoppelt.
4. **#148 – separat:** ambitioniertes AI-first-Zielbild, kontrollierte frühe Capability-Tests, erste betriebsfähige Ausbaustufe und Learning Value. **Keinen neuen Experiment-Status oder Governance-Bypass voraussetzen.**

**Migrationsgrundsätze:** `NULL`/„nicht gebunden“ für Altobjekte; keine fiktiven Geschäftsergebnisse, keine Massen-Backfills aus `strategic_objective` oder `expected_benefit`, keine Umschreibung von `SolutionSelectionDecision`/Historie. Datentransfer nur explizit, nachvollziehbar und autorisiert. Alte Demo-Daten und direkte Use Cases bleiben reproduzierbar. Vor produktiver Umstellung DB-Invarianten, Sperren, Parallelität, Exporte und APIs prüfen.

## 9. Prüf- und Risiko-Inventar

Datei-/Funktionsübersicht siehe **[Issue-144-Aufruferinventar](../planning/ISSUE_144_OUTCOME_CALLER_INVENTORY.md)**. Besonders kritisch: `get_value_stream_focus`, `get_stage_focus_decision`, `stage_is_selected`, `save_stage_focus_decision`, `focus_readiness_blockers`, `DEMO_FOCUS_DEFAULTS`, `metric_*`, Signals, Templates, API/View-Pfade, CSV/Review-Export, Accelerator-Contracts/Prompts und Demo-Seeds.

**Einschränkung:** Hier wurde Quellcode über GitHub gelesen; ein lokaler repo-weiter textueller Vollscan inklusive aller Templates, Tests, Migrationen und dynamischer Aufrufe war in dieser Umgebung **nicht ausführbar**. Das Inventar trennt verifizierte Aufrufe von noch nachzuprüfenden Flächen. Der dokumentierte `rg`-Vollscan sowie ein gezielter Review der dynamischen Nutzung ist **Abnahmevoraussetzung vor ADR-Annahme**. Keine aus der Teilprüfung extrapolierten exakten Gesamtzahlen.

## 10. Akzeptanz- und Negativszenarien für Folge-Issues

Nach Annahme dieses ADR **auf konkrete Beziehungen/Policies zuschneiden**, nicht zuvor als Produktbeweis ausgeben:

- **Zwei Vorhaben, ein Value Stream:** Auswahl unterschiedlicher Fokusphasen verändert jeweils **nicht** die andere; globale Legacy-Signale setzen keine vorhabensspezifische Auswahl.
- **Bindende Wahl ohne Outcome-Bezug:** serverseitig verboten; unverbindliche Exploration weiter möglich.
- **KI-Wirkannahme:** nur Hypothese bis zur ausdrücklichen fachlichen Annahme; menschliche Annahme ist **keine** höhere Belegstufe.
- **Outcome geändert:** gebundene Wahl ist neu zu prüfen; historischer Snapshot unverändert.
- **Non-KI bevorzugt:** kein KI-Use-Case erforderlich; Nachverfolgung der Wirkung bleibt sichtbar offen.
- **Prozesswert erreicht, Geschäftsoutcome offen:** keine automatische Behauptung bestätigter Geschäftswirkung.
- **Direkte/alte Use Cases:** unverändert gültig, keine erfundene Initiative, Baseline oder Bestätigung.
- **Governance:** positive Freigaben/Pilot/Go-live bleiben an heutige Hard Gates und Rollentrennung gebunden.

Tests benötigen echte negative Service-/View-Aufrufe und DB-Invarianten, nicht nur ausgefüllte Formulare. Synthetischer Fall B aus #133 ist Regression, **kein realer RSD-Nutzenbeleg**. Neue zuvor nicht verwendete Fälle einschließlich Non-KI-Pfad ergänzen.

## 11. Noch ausdrücklich vom Nutzer zu entscheidende Punkte

1. **Variante B** als führendes Vorhaben-Objekt gegenüber A/C annehmen oder ablehnen?
2. **Vorgeschlagene Kardinalitäten** (ein Prozess in höchstens einem Vorhaben; mehrere Prozesse pro Vorhaben; viele Vorhaben pro Value Stream) sowie globales Value-Stream-Screening plus vorhabenbezogene, append-only Stage-Fokus-Entscheidungen annehmen?
3. **Nicht-Login-fähiger Outcome Owner** als fachlich benannte Rolle/Person mit optionalem User-Link, aber ohne geerbte Systemrechte annehmen?
4. **Minimalen gemeinsamen einmaligen Outcome-Review** statt eines universellen neuen Lifecycle oder einer Messreihe annehmen?

**Governance dieses ADR:** Status „Vorgeschlagen“. Erst die **ausdrückliche Entscheidung des Nutzers** erlaubt Änderung auf „Angenommen“. Vorher dürfen #145–#147 **nicht** implementiert werden; #148 bleibt separat priorisiert. Ein grüner CI-Check oder der Merge eines reinen Dokumentations-PR ersetzt die fachliche Zustimmung nicht.
