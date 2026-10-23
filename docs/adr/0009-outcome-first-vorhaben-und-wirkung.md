# ADR 0009: Outcome-first – vorhabensbezogene Identität und Wirkungsbezug

**Status: Angenommen (fachlich)**  
**Datum:** 22.10.2026  
**Issue:** #144 · **Folge-Issues:** #145, #146, #147; #148 separat  
**Basis:** `main` / `f8cabbc418b4777d7bfd075e6c0dc1a3322aaa41`  
**Geltung:** Fachlicher Architekturentscheid nach ausdrücklicher Nutzerannahme am 22.10.2026. **Keine Aussage über bereits implementierte Funktionen.** Der lokale vollständige Aufruferscan bleibt als technische Vorbedingung **vor der ersten Produktänderung in #145** offen; CI wird wegen `paths-ignore: docs/**/*.md` bei diesem reinen Dokumentations-PR nicht ausgelöst.

## 1. Problem und Entscheidungsziel

KI-Ideenwerkstatt bildet heute einen problem- und prozessbezogenen Discovery-Pfad ab: Idee/Problem → Value Stream → Fokus/Prozess → Lösungsalternativen → gegebenenfalls KI-Use-Case. `SolutionSelectionDecision` hält Vergleich und Diagnose unveränderlich fest, aber kein fachlich führendes **vorhabensbezogenes Geschäftsergebnis**. Eine Non-KI-Präferenz kann die Discovery regulär beenden; strukturierte Pilot-/Wirkungsnachweise hängen dagegen überwiegend am `UseCase`.

`ValueStreamFocus` und `StageFocusDecision` referenzieren je einen `ValueStream` per `OneToOne`. `save_stage_focus_decision` nutzt `update_or_create(value_stream=...)`: unabhängige Vorhaben können denselben Phasenfokus überschreiben. Die `post_save`-Kurzpfade erstellen nur bei bisher fehlender Entscheidung; sie überschreiben nicht unmittelbar, nutzen aber denselben globalen Zustand. Auch `focus_readiness_blockers` prüft nur die globale Value-Stream-Selektion.

**Ziel:** Geschäftsergebnis, begrenzten Vorhabens-/Pilotbeitrag und **Wirkannahme** über beide Lösungsklassen (KI/Non-KI) nachvollziehbar führen; bestehende Legacy-Pfade, Hard Gates und unveränderliche Nachweise erhalten. Ein korrektes **„noch nicht nachgewiesen“** ist zulässig. Dies ist **kein** Vorschlag, zuerst ein KI-Tool, eine Baseline oder einen vollständigen Zielprozess zu erzwingen.

**Leitregel: Erfassung ist kein Freigabeantrag.** Ein Mitarbeiter kann ein Thema als Freitext aufnehmen, speichern, wieder öffnen, in Discovery untersuchen, Value Streams erkunden, Hypothesen notieren und Lösungsalternativen als *Entwurf* vergleichen – auch ohne Outcome Owner, Zielmetrik, Review-Termin, bestätigte Ursache oder ausformulierte Wirkannahme. Fehlendes wird **kontextabhängig als Hinweis/Offenpunkt** angezeigt; keine leeren Pflichtformularfelder, erzwungene Initiative, erfundenen Werte oder verdeckte Auto-Freigaben. Serverseitige **Hard Gates bleiben nur an wirklich bindenden Entscheidungen und unverändert an geltenden Governance-/Pilot-/Go-live-Übergängen**; dabei wird genau gesagt, was noch fehlt. Der Nutzer darf den Entwurf jederzeit sichern und später fortsetzen.

### Stufenweise Reife ohne unnötige Blockaden

| Nutzeraktion | Outcome-first-Verhalten | Bindend? |
|---|---|---|
| Idee / Geschäftsproblem / direkter KI-Use-Case erfassen | Freitext genügt; KI kann Geschäftsergebnis, Beitrag und Wirkannahme **vorschlagen**; fehlende Angaben optional markieren | **Nein**, keine neue Aufnahmehürde |
| Value Stream wählen, Prozess analysieren, strategischen Pfad erkunden | Mit unvollständigen Angaben fortfahren; Diagnosen und Alternativen als Hypothesen sichtbar | **Nein**, keine Outcome-Pflicht beim Erkunden |
| Optionen entwerfen, evaluieren, Entwurf speichern | Stärken, Evidenz, Unsicherheiten und offene Fragen sichtbar, kein künstliches Komplettheitsgate | **Nein**, keine bindende Präferenz |
| **Bevorzugte Lösung verbindlich festlegen** | Nur für vom neuen Vertrag erfasste Vorgänge: zugeordnetes Geschäftsergebnis, Vorhabensbeitrag, gekennzeichnete Wirkannahme und passende menschliche Bestätigung; Ursache **nur** im problemgetriebenen Pfad | **Ja**, bestehendes Entscheidungs-Gate gezielt ergänzen |
| **Direkten neuen KI-Use-Case positiv freigeben** | Wenn nicht bereits gültig aus gebundener Lösung übernommen: Outcome-Kontext prüfen; kein zweites Pflichtformular für dieselbe Evidenz | **Ja**, zusätzlich zu unveränderten Freigaberegeln |
| **Pilot/Betrieb/Abschluss** | Bereits freigegebene Legacy-Fälle bleiben im Bestandsschutz; aktuelle Datenschutz-/Sicherheits-/Go-live-Gates gelten weiterhin | **Ja**, nur die jeweiligen bewussten Übergänge |

**Design-Abnahme:** Neue Hinweise dürfen die *Speichern-/Fortsetzen*-Funktionen, Exploration und Entwurfsvergleiche nicht deaktivieren. Keine Autofreigabe zur Umgehung einer tatsächlich bindenden Entscheidung.

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
- **(a)** Direkte Use Cases sowie Prozessanalysen dürfen **ohne Vorhaben** erfasst, gespeichert und untersucht werden. Für **neue bindende Lösungswahlen (auch Non-KI)** beziehungsweise **neue positive KI-Freigaben** ist dann ein validierter Outcome-Bezug zum **selben Vorhabenobjekt** erforderlich, das bei Bedarf erst an diesem Punkt schlank und nach menschlicher Bestätigung angelegt/verknüpft wird – ohne künstliche Idee oder Prozessanalyse. Historische Use Cases bleiben geschützt.
- **(b/c)** 0..n Prozesse und unabhängige vorhabensbezogene Phasenentscheidungen möglich, ohne den Value Stream selbst zum Projekt zu machen. Bereits vorhandene per-Prozess-Lösungswahl bleibt fachlich konsistent, sofern jeder neue Prozess genau einem Vorhaben zugeordnet ist.
- **(d/e)** Derselbe Outcome-Träger für Non-KI und KI; eindeutige revisionsfähige Identität und dokumentierbarer Outcome-Change-Impact.
- **(f/g/h)** Neue Tabelle und kontrollierte Links/Policies nötig; migrations- und aufruferseitig vor allem Discovery-Fokus, Outcome-Gates, Exporte und Intake betroffen. Der bestehende Inbox-/Use-Case-Lifecycle muss aber nicht semantisch umdefiniert werden.
- **Tragfähig wenn:** Kein schwergewichtiger zweiter Status-/Governance-Lifecycle entsteht; der neue Datensatz Outcome/Identität **und minimale, nicht intake-blockierende Vorhabenssteuerung** besitzt.

### Variante C – `ProcessAnalysis` als Vorhabensanker
- **(a)** Direkte Use Cases ohne Prozess müssten künstliche Prozesse erhalten oder dauerhaft ohne Outcome-Führung bleiben.
- **(b/c)** `ProcessAnalysis` gehört heute genau zu **einer** `ValueStreamStage`. Mehrere Prozesse unter einem Vorhaben benötigen wiederum einen darüberliegenden Anker oder eine fachlich fragwürdige „Masterprozess“-Hierarchie. Gemeinsame Stage kann weiterhin mehrere Prozessanalysen enthalten, beseitigt aber keinen Vorhabensanker.
- **(d/e)** Vorteil: Diagnose und Versionierung existieren bereits. Nachteil: Outcome-Definition käme **nach** der Fokusentscheidung und KI-/Non-KI-Nutzung bleibt prozesszentriert.
- **(f/g/h)** Kurzfristig wenig Schema-Neuaufbau, langfristig hohe Kopplung in ProcessValidation, SolutionOptions, Prozessversionen, Discovery- und Direktpfaden.
- **Tragfähig wenn:** Das Produkt bewusst nur Einzelprozess-Vorhaben kennt. Das widerspricht dem geforderten frühzeitigen Outcome-first- und Mehrprozesspfad.

### Angenommene Architekturentscheidung

**Variante B angenommen.** Sie erfüllt die Identitäts- und KI-/Non-KI-Anforderungen mit der saubersten fachlichen Trennung. Der zusätzliche Modell-/Zuordnungsaufwand ist real; der vermeintlich einfachere Ausbau von `IdeaCandidate` verlangt jedoch umfassende Änderungen der bestehenden Promotion-/OneToOne-Semantik. `ProcessAnalysis` ist für Outcome-first zu spät und zu eng.

Keine Variante vermeidet die gesonderte **Fokus- und Entscheidungsumstellung**. Diese ist ein eigenes Implementierungsinkrement. Die Variante ist **fachlich vom Nutzer angenommen**; die Umsetzung erfolgt separat und iterativ nach den im ADR beschriebenen Soft-/Hard-Gates.

## 4. Kardinalitäten und Grenzen der angenommenen Variante B

- `ImprovementInitiative` (Vorhaben): identitätsstabil, 0..n verknüpfte **IdeaCandidates**, 0..n **ProcessAnalyses**, 0..n realisierte Lösungen/Reviews. Ein vorhabenloser Eingang oder direkter Use Case bleibt möglich.
- Jede **IdeaCandidate** ist in der ersten Ausbaustufe höchstens einem Vorhaben zugeordnet; unverknüpfte Inbox-Einträge behalten sämtliche bisherigen Statusregeln. Verschiedene Ideen dürfen in **einem** Vorhaben gebündelt werden. Keine automatische Promotion oder fiktive Idee.
- Jede neue **ProcessAnalysis** darf beim Erfassen und Erkunden **ungebunden** bleiben, gehört aber **spätestens bei einer bindenden Lösungswahl genau einem Vorhaben** der neuen Kohorte an. Für die neue Kohorte **gibt es kein bindendes Legacy-Fallback ohne Outcome-Bezug** – auch bei Non-KI. Alte Prozessanalysen/Entscheidungen dürfen ungebunden bleiben. Mehrere Vorhaben können **denselben Value Stream und dieselbe Phase** nutzen, erhalten aber separate Prozess- und Lösungsentscheidungen. Eine spätere Mehrfachnutzung derselben Prozessanalyse wäre ein eigener Architekturentscheid.
- **ValueStream** bleibt organisationsweit und langlebig; 0..n Vorhaben können ihn verwenden. Er besitzt **kein** vorhabensspezifisches Business Outcome.
- **ValueStreamFocus** bleibt zunächst **einmaliges/globales Screening** des Value Streams (Capability, strategische Relevanz etc.). Seine Auswahl bedeutet **nicht**, dass die Fokusphase eines konkreten Vorhabens bereits gewählt wurde.
- **StageFocusDecision** wird für neue Vorhaben **vorhabensbezogen, nachvollziehbar versioniert/append-only**. `ValueStream` + `Initiative` + `Stage` müssen zusammenpassen; aktive Wahl je Vorhaben und betrachteten Value Stream eindeutig, ältere Zustände lesbar. Bestehende globale Fokusentscheidungen sind **Legacy**, keine automatisch übernommenen Vorhabensentscheidungen. Ob eine konditionale FK-Migration derselben Tabelle oder eine strikt isolierte Legacy-Projektion der sicherere Implementierungsweg ist, muss #145 gegen die konkrete Datenlage abgleichen; **fachliche Identität und Nichtüberschreiben sind verbindlich**.
- Der neue **Fokus-/Outcome-Gate** gilt **für jede neue bindende Lösungswahl der neuen Kohorte, unabhängig davon, ob die Prozessanalyse zuvor an ein Vorhaben gebunden war**. Bei bindender Wahl werden ein eindeutiger Outcome-Bezug und eine dazugehörige aktuelle vorhabensbezogene Phasenentscheidung geprüft bzw. nach Nutzerbestätigung erstellt. Das globale Screening allein ist **unzureichend**. Vorheriges Erfassen, Editieren, Validieren und optionale Entwurfsvergleiche bleiben möglich. **Nur historische Legacy-Kohorten** behalten den bisherigen Gate-Vertrag, bis sie ausdrücklich überführt werden.
- `SolutionOption` und `SolutionSelectionDecision` bleiben **pro Prozess**. Die bereits existierende „genau eine bevorzugte Option pro ProcessAnalysis“-Regel erfordert die oben festgelegte exklusive Prozesszuordnung; keine global bevorzugte Option für mehrere Vorhaben.
- `UseCase` kann 0..1 Vorhabenbezug erhalten, ein Vorhaben kann 0..n KI-Use-Cases unterstützen; `UseCaseOrigin` bleibt Quelle der prozessualen Herkunft. Ein **direkter Use Case** ohne Idee, Initiative oder Prozess bleibt **erfassbar und bearbeitbar**; historische Freigaben bleiben gültig. Für neue **positive Freigaben** ist – unabhängig vom Einstieg – eine Referenz auf **denselben fachlichen Outcome-Träger `ImprovementInitiative`** erforderlich. Falls noch keine Initiative existiert, kann die Anwendung sie **erst bei der bindenden Freigabe schlank erzeugen** und nach expliziter fachlicher Bestätigung zuordnen. **Kein zweites direktes Mini-Outcome-Objekt** und kein erzwungener Projektanlage-Dialog beim Intake. Zuordnung nicht aus Texten raten.

**Kurzpfade/Signale:** `stage_focus.persist_focus_from_existing_process` und `persist_focus_from_existing_origin` dürfen für neue vorhabensgebundene Artefakte **keine globale Freigabe erzeugen oder implizit zuordnen**. Legacy-Fälle behalten ihren bisherigen bewusst dokumentierten Kurzpfad. `save_stage_focus_decision(update_or_create)` darf nach der Umstellung nicht über eine globale Key-Kombination vorhabensspezifische Entscheidungen überschreiben.

**Klärung zu #158 (23.10.2026):** Die jüngste Fokuswahl je (Vorhaben, Value Stream) bezeichnet die aktuelle Prioritätsanzeige. Für die Gültigkeit einer Prozessentscheidung gilt dagegen die jüngste Fokusrevision ihrer eigenen (Vorhaben, Value Stream, Phase)-Kombination. Bereits legitimierte andere Phasen bleiben gültig; eine neue Revision derselben Phase löst dort erneuten Prüfbedarf aus. Die append-only Revisionszählung bleibt je (Vorhaben, Value Stream) übergreifend; historische Snapshots und globale Legacy-Entscheidungen bleiben unverändert.

### 4a. Minimale Vorhabenssteuerung, nicht bei Aufnahme erzwingen

**Angenommene fachliche Mindestzustände:** `Entwurf` → `Aktiv` → `Abgeschlossen`; `Abgebrochen` als eigener begründeter Endzustand. Dies ist **kein** weiterer KI-Delivery-/Governance-Lifecycle.

- **Entwurf:** Aufnahme, Speicherung und Untersuchung **ohne** Owner, Datum, endgültige Ziele oder Evidenz erlaubt. KI-Vorschläge bleiben Entwürfe.
- **Aktiv:** Bearbeitung/Erkundung bleibt bei offenem Owner/Review-Termin möglich und zeigt konkrete Hinweise. Spätestens bei einem **verbindlichen fachlichen Review oder einer bindenden Auswahl/Freigabe** ist eine identifizierbare berechtigte Person für diese Entscheidung erforderlich – nicht zwingend ein eingeloggter Outcome Owner. „Aktiv“ allein bewirkt keine Freigabe.
- **Abgeschlossen:** Nur nach **dokumentierter Wirkungsaussage** zur Wirkannahme: `bestätigt`, `widerlegt` oder `noch ungeklärt` **mit Begründung**. Abschluss ist nicht gleich positiver Geschäftserfolg. Keine künstlichen Messwerte.
- **Abgebrochen:** Dokumentierte Abbruchbegründung; getrennt von „Abgeschlossen“ und ohne erzwungenen Wirkungsnachweis, der bei frühem Abbruch unmöglich sein kann.
- **Nächster Review-Termin:** Für Entwurf optional, danach mit Erinnerhinweis/Offenpunkt, **kein Speichern-Blocker**. Fälligkeit soll im vorhandenen Scan/Dashboard sichtbar werden, ohne Mail-Pflicht, neue Reminder-Engine oder automatische Freigabe. Genauen Query-/Anzeige-Schnitt in #145/#147 festlegen.

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

**Outcome Owner:** Ein registrierter Benutzer ist **nicht fachlich zwingend**. Vorschlag: benannte verantwortliche Funktion/Organisation (auch ohne Login), optional referenziertes Systemkonto; bei der anfänglichen Erfassung dürfen beide Angaben **offen** bleiben. Nur aktive berechtigte Systemnutzer dürfen tatsächlich bestätigen, bewerten oder freigeben. Diese Zuordnung erteilt **keine** neuen Berechtigungen und hebt bestehende Personen-/Rollentrennung nicht auf. Eine ungeklärte verantwortliche Rolle erscheint als **Hinweis**, bei verbindlicher Entscheidung muss ein autorisierter Entscheider identifizierbar und auditierbar sein; Stellvertretung benötigt Mandat und Audit-Spur, kein implizites Rollenprivileg.

## 6. Decision Contract: Soft Guidance, Herkunft, echte Gates und Historie

**Reife, nicht Hürden:** Neue Outcome-Fragen sind im **Intake, bei der Ideensammlung, Discovery, strategischer Exploration, Prozessanalyse, Lösungsgenerierung, Entwurfsvergleichen und Speichern** immer **Hinweise**. Kein „vorher Owner/Zahl/Prozess/Ursache eintragen, sonst nicht fortfahren“. Speichern und die nächste unverbindliche Untersuchung bleiben möglich. Fehlende Evidenz darf mit `unbekannt`/`Hypothese` bezeichnet werden; vom LLM erfundene Angaben niemals automatisch als Tatsachen übernehmen.

**Binding-Gate** bei **jeder** tatsächlichen neuen bindenden Lösungswahl (auch Prozessanalyse **ohne vorherige Initiative**, auch Non-KI) im zentralen `select_preferred_solution`-/verbindlichen Diagnose-Service sowie bei der **positiven fachlichen KI-Use-Case-Freigabe** für neue direkte Use Cases. Bewertung, `zurückgestellt`, `nicht weiterverfolgt`, Draft und aktive Bearbeitung sind **keine** positive Freigabe. Bestehende Governance-, Pilot- und Go-live-Gates bleiben unverändert; keine Outcome-Prüfung bei jedem einzelnen Lifecycle-Übergang wiederholen.

### 6a. Geltung, Bestandsschutz, Doppelprüfung

- **Aktivierungsgrenze statt vagem Kalenderdatum:** Implementierung in #145/#146 legt explizit eine Einführungsversion mit Wirksamkeitszeitpunkt fest. **Kohortenzuordnung wird am Datensatz beim Anlegen oder bei ausdrücklich bestätigter Übernahme in den neuen Vertrag festgehalten**, nicht erst anhand des späteren Entscheidungsdatums abgeleitet. Der genaue Migrationsindikator ist vor Release festzulegen und regressionszuprüfen.
- **Altbestand:** Vor der Einführung entstandene, nicht ausdrücklich migrierte Use Cases/Prozessentscheidungen bleiben im Legacy-Vertrag; spätere Pilot-→Betrieb-Transitions werden **nicht** wegen eines neuen Outcome-Feldes blockiert. Vorhandene Sicherheits-, Mess- und Freigabegates bleiben selbstverständlich wirksam.
- **Neue direkte Use Cases und ungebundene Prozessanalysen:** Ohne Idee, Value Stream, Prozess oder `ImprovementInitiative` – soweit fachlich zutreffend – **aufnehmbar und bearbeitbar**. Erst zur **positiven Freigabe bzw. bindenden Lösungswahl** referenzieren sie **denselben Outcome-Träger `ImprovementInitiative`**. Fehlt er, wird auf der vorhandenen Entscheidungsoberfläche aus bestätigten Angaben ein **minimaler Vorhaben-Datensatz** erzeugt und zugeordnet. Nur der bindende Befehl prüft die Eindeutigkeit; kein zusätzlicher Pflicht-Wizard beim Intake, keine zweite Mini-Entität und kein künstlicher Prozess. Die konkrete technische Verknüpfung ist Umsetzungsdetail für #145/#146, **die gemeinsame Source of Truth ist hier verbindlich entschieden**.
- **Aus gebundener Lösungsentscheidung abgeleiteter KI-Use-Case:** Bereits bestätigten Outcome-/Snapshot-Bezug **referenzieren**, nicht vom Nutzer erneut eintippen lassen. Serverseitig Herkunft, Integrität und **aktuelle oder ausdrücklich erneut bestätigte** Outcome-Revision prüfen. Eine alte Entscheidung mit wesentlich geändertem Outcome ist **kein** Blankoscheck.
- **Keine Umgehung:** Kein alternativer direkter API-, Admin-, Batch-, View-, Copy- oder Lean-Intake-Pfad darf **positive neue Freigaben** ohne erforderlichen Outcome-Kontext auslösen. Für bloße Entwürfe gelten die Hürden gerade **nicht**.

### 6b. Zwei fachliche Discovery-Pfade ohne Ursache-Halluzination

Der **Pfad wird anhand der dokumentierten Herkunft/Problemstellung** der Discovery zugeordnet, **nicht** opportunistisch beim Entscheidungs-Click ausgewählt. Die frühe Nutzeraufnahme wird dadurch nicht blockiert: bei unklarer Herkunft zunächst `noch nicht eingeordnet` samt Hinweis; fachliche Einordnung erst **vor einer bindenden Auswahl**. Ein späterer Wechsel ist möglich, benötigt Grund, Entscheider, Zeit, Version und erneute Prüfung; nicht automatisch durch LLM. Der Snapshot weist Herkunft, Pfad, Pfadwechsel und dessen Evidenzstand aus.

| Pfad | Bindende Auswahl verlangt | Was ausdrücklich **nicht** verlangt wird |
|---|---|---|
| **Problemgetrieben** – dokumentiertes konkretes Betriebsproblem | Bestehende belegte Beobachtung/Problembeschreibung **und** fachlich bestätigte Ursache gemäß bisherigem Diagnosegate, zusätzlich Outcome-Beitrag/Wirkannahme | Frühe bestätigte Ursache beim bloßen Erfassen oder Erkunden |
| **Strategisch / top-down** – nachvollziehbare Geschäfts-/Wachstumschance ohne belegten Einzelprozessfehler | Begründetes Verbesserungspotenzial, falsifizierbare Wirkannahme **mindestens Evidenzstufe Hypothese**, explizite fachliche Bestätigung der Annahme als *zu testende Annahme*, Outcome-Bezug und Risikogrenze | Erfundene bestätigte Ursache, fingierte Engpassdaten, schon bewiesene Kausalwirkung oder Zahlenbaseline |

**In beiden Pfaden:** Mindestens zwei tatsächlich bewertete Alternativen, ein gemeinsames benanntes Geschäftsergebnis, optionenspezifisch plausibler Beitrag zum Ziel und transparentes Evidenzniveau. **Eine strategische Hypothese kann eine schwächere Evidenzstufe als eine bestätigte Prozessursache haben; sie wird nicht als gleich stark ausgegeben.** Dafür werden die Annahme, die vorgesehenen Prüfkriterien bzw. der nächste Validierungsschritt und die menschliche Verantwortlichkeit transparent. **Kein fester Review-Termin und keine zusätzliche zweite Freigaberolle als Voraussetzung der bindenden Auswahl**; fehlender Review-Termin bleibt sichtbar offen und fließt in die bestehende Fälligkeitsdarstellung ein. Bestehende `diagnosis_readiness_blockers` und `confirm_diagnosis_and_select_solution` dürfen nicht als unbedingtes Einheitsgate beibehalten werden; #146 gestaltet den serverseitigen Pfadvertrag explizit neu, ohne das alte problemgetriebene Gate heimlich zu entfernen. Die fachliche Bestätigung macht **eine Hypothese nicht zu einem Beweis**.

### 6c. Bindende Entscheidung, Snapshot und Stale

1. Ein **eindeutig identifizierter Outcome-Kontext**, Vorhabens-/Pilotbeitrag und als Hypothese/Indiz/Messwert eingeordnete Wirkannahme sind vorhanden und **fachlich angenommen**. In explorativen Entwürfen dürfen sie fehlen.
2. Bei Lösungsauswahl werden die **Beiträge der verglichenen Optionen zum gleichen Outcome** samt Evidenzstand verglichen. Ein KI-Generator/Critic darf nur vorschlagen; Mensch ist Source of Authority.
3. Keine frühe Pflicht zu numerischer Baseline, Zielwert, ROI, bestätigter Kausalwirkung, abgeschlossenem Geschäftserfolg, eingebuchtem Review-Termin oder eingeloggtem Outcome Owner, **sofern** die konkrete verbindliche Entscheidung selbst autorisiert ist.
4. Entscheidungssnapshot immutable: **einheitliche Vorhaben-ID und Outcome-Revision** (auch bei zuvor ungebundener Prozessanalyse und direktem Use Case), Geschäftsergebnis, Beitrag, Wirkannahme, Evidenzstatus, fachliche Bestätigung, Herkunft, Diagnosepfad, bei strategischem Pfad **explizit „keine bestätigte Ursache erforderlich/liegt nicht vor“**, vorgesehener Validierungsschritt/Prüfkriterien und optionenspezifische Beiträge. Keine zweite freistehende Outcome-Definition.
5. Änderungen an einer **wesentlichen** Outcome-Revision erzeugen für neue gebundene Entscheidungen *abgeleitet* „Neubewertung nötig“, ohne alte Snapshots zu ändern. **Wesentlichkeit** (Zielinhalt, Wirkmechanismus, Zielpopulation oder Erfolgskriterium) und betroffene Entscheidungen/Delegierten-Audit sind in #146 präzise zu bestimmen. Kosmetik/Schreibfehler sollen nicht unnötig sämtliche Prüfungen blockieren.
6. Historische **nicht gebundene** Fälle bleiben gültig und heißen `historisch nicht gebunden`, nicht automatisch `stale`. Ein vorab offenes, nicht bindendes Entwurfsdokument darf jederzeit weiterbearbeitet werden.

**Bedienvertrag bei fehlenden Angaben:** Statt die Arbeitsfläche zu sperren: „Als Entwurf speichern“ / „Später klären“ und konkrete Hinweise. Nur der **separate, bewusst betätigte Befehl** „Verbindlich auswählen/freigeben“ meldet serverseitig fehlende Entscheidungsgrundlagen. Der Nutzer verliert dabei **keine Eingaben** und kann im Entwurfsstatus weiterarbeiten.

## 7. Minimale gemeinsame KI-/Non-KI-Wirkungsverfolgung

Eine Non-KI-Entscheidung darf Discovery ohne künstlichen KI-Use-Case beenden; **die Frage, ob das Geschäftsergebnis eintritt, bleibt trotzdem offen**.

Für #147 vorgeschlagen: ein **kleiner, vorhabensbezogener Review-/Wirkungsnachweis** mit Interventions-/Entscheidungsbezug, benannter Verantwortung, Messdefinition, einmaligem aktuellem Messstand und Nachweisreferenz. **Getrennte Feststellungen**:
- Prozess-/Capability-Ergebnis erreicht, verfehlt oder unbekannt;
- übergeordnetes Geschäftsergebnis gemessen/noch offen;
- Plausibilität bzw. Attribution der **Wirkannahme** gesondert gekennzeichnet; Prozessziel „erreicht“ darf nicht zu „geschäftlicher Erfolg nachgewiesen“ konvertieren;
- offene Non-KI-Wirkungsfrage sichtbar, auch wenn die Discovery-Entscheidung abgeschlossen ist.

Bei KI-Vorhaben **referenziert** der vorhabensbezogene Review vorhandene `UseCase.metric_*` (konkreter Use Case, Messdefinition, Stand, Evidenz), erfasst dieselbe Prozesskennzahl **nicht erneut als zweite editierbare Zahl**. Zugleich ist eine Use-Case-Prozessmetrik **nicht automatisch** die Metrik des Geschäftsergebnisses. Eine separate Geschäftswirkungsmessung ist nur sinnvoll, wenn sie eine **inhaltlich andere Größe** misst und als solche definiert ist; Herkunft, Zuordnung und Grenzen der Aussage sichtbar machen. Auch mehrere Use Cases pro Vorhaben dürfen keine automatisch addierten Doppelzählungen erzeugen.

Die bestehenden `UseCase.metric_*`-, `Review`-, Governance-, Pilot-/Go-live- und `OUTCOME_WORKSPACE`-Mechanismen bleiben für KI führend; der zusätzliche gemeinsame Review darf kein zweiter vollständiger Use-Case-Lifecycle werden. **Keine** jetzt vorgezogene versionierte Messreihe, Trend-/Drift-Engine oder External-Delivery-Integration (Roadmap: „Later/Priorität 3“). Operative Umsetzung außerhalb des Systems bleibt erlaubt.

## 8. Abhängigkeiten, Migration und Legacy-Regeln

1. **#145 – Identität/Fokus:** neue fachliche Identität und optionale Verknüpfungen, minimale nicht-blockierende Vorhabenszustände, Outcome Owner (auch ohne Login) und Review-Termin; Varianten der Stage-Focus-Persistenz anhand realer Daten/Signals prüfen. Fälligkeiten mit bestehendem Scan/Dashboard zusammenführen, ohne SMTP oder Aufnahmeblocker. Neu-Pfade strikt initiative-scoped; Legacy-Pfade weiter gültig.
2. **#146 – Vergleich/Entscheidung:** kohortenbewusster, durch alle positiven neuen Freigabepfade durchgesetzter Outcome-/Bestätigungs-/Evidenzvertrag; Entwürfe immer speicherbar; **problemgetriebener versus strategischer Pfad mit je eigener Mindestbegründung**, Herkunft/Wechsel/fehlende bestätigte Ursache im immutable Snapshot. Alte problemgetriebene Ursache-Regel bleibt dort erhalten; Outcome-Änderungen machen **nur neue gebundene** Entscheidungen überprüfungsbedürftig.
3. **#147 – gemeinsame Wirksamkeit:** kleine Review-Projektion für Non-KI plus Trennung von Prozess- und Business-Messung; KI-`metric_*` nur referenzieren, keine doppelten editierbaren Messwerte; Abschluss mit Wirkungsaussage (bestätigt/widerlegt/offen begründet), Abbruch gesondert, kein Blocker bei früher Aufnahme. Vorhandene `UseCase`-Gates werden nicht an ein neues Vorhaben zwangsweise gekoppelt.
4. **#148 – separat:** ambitioniertes AI-first-Zielbild, kontrollierte frühe Capability-Tests, erste betriebsfähige Ausbaustufe und Learning Value. **Keinen neuen Experiment-Status oder Governance-Bypass voraussetzen.**

**Migrationsgrundsätze:** Explizite **Aktivierungsgrenze/Kohortenmarkierung** statt bloßer späterer Freigabedatumsprüfung; `NULL`/„nicht gebunden“ für Altobjekte; keine fiktiven Geschäftsergebnisse, keine Massen-Backfills aus `strategic_objective` oder `expected_benefit`, keine Umschreibung von `SolutionSelectionDecision`/Historie. Datentransfer nur explizit, nachvollziehbar und autorisiert. Alte Demo-Daten und direkte Use Cases bleiben reproduzierbar. Vor produktiver Umstellung DB-Invarianten, Sperren, Parallelität, Exporte und APIs prüfen.

## 9. Prüf- und Risiko-Inventar

Datei-/Funktionsübersicht siehe **[Issue-144-Aufruferinventar](../planning/ISSUE_144_OUTCOME_CALLER_INVENTORY.md)**. Besonders kritisch: `get_value_stream_focus`, `get_stage_focus_decision`, `stage_is_selected`, `save_stage_focus_decision`, `focus_readiness_blockers`, `DEMO_FOCUS_DEFAULTS`, `metric_*`, Signals, Templates, API/View-Pfade, CSV/Review-Export, Accelerator-Contracts/Prompts und Demo-Seeds.

**Einschränkung:** Hier wurde Quellcode über GitHub gelesen; ein lokaler repo-weiter textueller Vollscan inklusive aller Templates, Tests, Migrationen und dynamischer Aufrufe war in dieser Umgebung **nicht ausführbar**. Das Inventar trennt verifizierte Aufrufe von noch nachzuprüfenden Flächen. Der dokumentierte `rg`-Vollscan sowie ein gezielter Review der dynamischen Nutzung ist **Abnahmevoraussetzung vor ADR-Annahme**. Keine aus der Teilprüfung extrapolierten exakten Gesamtzahlen.

## 10. Akzeptanz- und Negativszenarien für Folge-Issues

Diese Szenarien vor Implementierung entsprechend angenommener Architektur konkretisieren; **Service-/API-/UI-Negativtests** prüfen, ob der Nutzer **weiterarbeiten kann**, und ob bindende Entscheidungen dennoch geschützt sind:

| Szenario | Erwartung |
|---|---|
| **Leerer Intake / neue Idee ohne Outcome, Owner, Datum, Ursache** | Speichern, Entwurf fortsetzen, Discovery/Alternativen erkunden und KI-Vorschläge erhalten **möglich**; konkrete offene Fragen nur als Hinweise |
| **Direkter neuer KI-Use-Case ohne Initiative** | Anlegen, bearbeiten, nicht bindend bewerten **möglich**; zur **positiven Freigabe** minimalen gemeinsamen Initiative-/Outcome-Träger anlegen und fachlich bestätigen, sonst Freigabe verhindert; Datensatz und Eingaben bleiben erhalten |
| **Alt-Use-Case vor Aktivierungsgrenze** | Pilot → Betrieb gemäß **bestehenden** Gates weiterhin möglich, ohne neue Outcome-Pflicht |
| **Gebundener Use Case mit gültigem Outcome-Snapshot** | Positive Freigabe benötigt **keine erneute Eingabe** derselben Angaben; veraltete wesentlich geänderte Bindung wird geprüft |
| **Neue Prozessanalyse ohne Vorhaben, mit Non-KI-Option** | Aufnahme/Untersuchung und Lösungsentwurf **möglich**; **bindende Präferenz** ohne Zuordnung zum gemeinsamen Vorhaben-Outcome **abgelehnt**; minimale Zuordnung erst bei Auswahl, nicht beim Intake |
| **Problemgetriebene Lösungswahl ohne bestätigte Ursache** | Weiteres Erkunden möglich, **bindende Auswahl** abgelehnt; keine erfundene Ursache |
| **Top-down-Fall ohne bestätigte Prozessursache, aber mit begründetem Potenzial, fachlich angenommener prüfbarer Hypothese und Outcome** | **Bindende Auswahl zulässig**, Snapshot benennt ausdrücklich Ursprung/Pfad, Evidenzstufe, den geplanten Validierungsschritt und „keine bestätigte Ursache“; **kein Pflicht-Kalendertermin** |
| **Strategischer Pfad ohne begründetes Potenzial / Wirkannahme / menschliche Annahme** | Weiteres Erkunden möglich, **bindende Auswahl** abgelehnt; frei wählbarer Pfadwechsel als Gate-Bypass unmöglich |
| **Zwei Vorhaben im selben Value Stream** | Phasen-/Fokusentscheidungen überschreiben einander nicht |
| **KI-generierte Wirkannahme ohne Fachreview** | Entwurf bleibt Hypothese, kein Anspruch „belegt“, keine bindende Entscheidung |
| **Wesentliche Outcome-Änderung** | Alte Snapshots unverändert, neue gebundene Entscheidungen/positive Freigaben verlangen Review; reine Schreibkorrektur keine unnötige Sperre |
| **Vorhaben-Review überfällig, Termin fehlt** | Fälligkeit/Hinweis im vorhandenen Dashboard/Scan; neue Aufnahme, Speicherung und Exploration bleiben möglich |
| **Vorhaben ohne Wirkungsaussage als abgeschlossen markiert** | Abschlussbefehl verlangt Aussage; `noch ungeklärt` **mit Begründung** ist zulässig, kein erfundener Erfolg |
| **Abgebrochenes Vorhaben** | Eigener Abbruchstatus mit Begründung; nicht als „Abgeschlossen“/erfolgreich gezählt |
| **Non-KI bevorzugt** | Kein künstlicher KI-Use-Case; offene Wirkung weiter sichtbar, keine erzwungene Messreihe |
| **Use-Case-Prozessmetrik erreicht, Geschäftsergebnis offen** | Geschäftserfolg **nicht** automatisch bestätigt; keine zweite editierbare Kopie derselben Prozessmetrik |
| **Governance / Rechte** | Positiver Freigabebefehl autorisiert und auditiert; Outcome-Owner-Stellvertretung nicht automatisch mit Entscheidungsrecht ausgestattet |

Synthetischer Fall B aus #133 ist Regression, **kein realer RSD-Nutzenbeleg**. Neue unbekannte Fälle einschließlich Nicht-KI und Legacy-Kohorten ergänzen. Keine UI-Checkliste als Ersatz für tatsächliche Service- und Datenbank-Vertragsprüfungen.

### Noch nicht in #144 fachlich abschließend zu entscheiden – nach #146/#147 übernehmen

- **Mehrere Vorhaben, dasselbe Geschäftsergebnis:** gemeinsames strategisches Ziel ist keine Erlaubnis für mehrfach gezählten ROI; spätere Zuordnung/Attribution und mögliche übergeordnete Zielidentität getrennt prüfen.
- **Optionenspezifischer Beitrag:** strukturierter Bezug jeder Option zum einen Outcome, mit Evidenz und plausibler Wirkannahme; genaue Felder/Validierungen erst in #146.
- **Wesentliche Änderung:** fachliche Trigger (Ziel, Empfängergruppe, Wirkmechanismus, Messkriterium) und auditierbarer Revisionsvergleich sowie Update aus LLM-/UI-Pfaden in #146 präzisieren.
- **Owner-Stellvertretung:** Mandat, wer bestätigt, tatsächliche ausführende Person, Zeitpunkt und Audit-Ereignis; in #145/#146 festlegen, ohne neue pauschale Berechtigung.
- **Gemeinsame Wirkung:** Referenzierung bestehender `UseCase.metric_*` vs. eigenständige Geschäftsergebnismetrik; Aggregation und Doppelerfassung verhindern (#147).
- **Review-Fälligkeit:** vorhandenen täglichen `scan_due_reviews` und Dashboard um vorhabenbezogene offene Fälle **erweitern**, keine neue Notification-Engine und kein Pflichtdatum beim Intake.

## 11. Fachlich angenommene Entscheidungen und verbleibende technische Vorbedingungen

**Fachliche Annahme durch den Nutzer am 22.10.2026**, nach drei Feedback-Schleifen und ausdrücklicher Entscheidung für einen **schlanken, nicht blockierenden Aufnahme- und Discovery-Arbeitsfluss**. Angenommen sind:

1. **Ein fachlich führender Outcome-Träger:** `ImprovementInitiative` (Variante B) – **kein** zweites Direkt-Use-Case-Mini-Outcome-Modell. Eintrag und Discovery bleiben ohne Initiative möglich; bei **neuer bindender Lösungswahl inklusive Non-KI** oder neuer positiver direkter Use-Case-Freigabe wird derselbe Träger bei Bedarf minimal und nach menschlicher Bestätigung gebunden.
2. **Kardinalitäten und Fokus:** Mehrere Vorhaben pro langlebigem Value Stream, mehrere eigene Prozesse pro Vorhaben, jede neue Prozessanalyse höchstens einem Vorhaben; globales Value-Stream-Screening bleibt, neue vorhabensbezogene Fokusentscheidungen sind historisch nachvollziehbar und überschreiben einander nicht.
3. **Owner und Berechtigungen:** Fachlicher Outcome Owner darf ohne eigenes Systemkonto benannt sein; seine Nennung erteilt keine Freigaberechte, wirkliche entscheidende Person und Vertretung bleiben auditiert.
4. **Wirksamkeitsnachweis:** Kleine gemeinsame KI-/Non-KI-Wirkungsverfolgung, bestehende `UseCase.metric_*` nur referenzieren, Prozessziel und Geschäftsergebnis getrennt; keine zweite Delivery-Engine und keine vorgezogene historische Messdatenplattform.
5. **Bedien- und Entscheidungsvertrag:** Ideen/Probleme, Prozessanalyse, Hypothesen, Optionen, direkte Use Cases jederzeit ohne neue Outcome-Pflichtfelder speichern und weiterbearbeiten; **nur bewusst bindende** Entscheidung trifft auf Gate. Problem- und strategischer Pfad haben verschiedene, offen sichtbare Evidenzanforderungen; **kein** zusätzlicher Pflicht-Review-Termin oder zweite Freigabe-Rolle. Alt-Kohorten bleiben geschützt.
6. **Minimale Steuerung:** `Entwurf/Aktiv/Abgeschlossen/Abgebrochen`; Abschlüsse mit Wirkungsaussage auch „ungeklärt mit Grund“, Abbruch mit Grund; fehlender Review-Termin ist Hinweis und **kein** Speicherhindernis.

**Technische Qualitätsgrenze bleibt offen, nicht als abgeschlossen ausgeben:**
- Ein vollständiger `rg`-Aufruferscan auf einem echten Checkout war über die hier angebundene GitHub-Schnittstelle/Container ohne GitHub-DNS nicht möglich. Das Inventar ist eine **geprüfte Mindestmenge, keine Vollständigkeitsbehauptung**. **#145 beginnt verpflichtend mit diesem Scan und einem dokumentierten Caller-Impact-Abgleich, bevor Modelle, Migrationen oder Services geändert werden**. Nicht gefundene dynamische/indirekte Aufrufer müssen erfasst werden. Entsteht dadurch ein materiell anderer fachlicher Trade-off, den ADR **vor Implementierung** erneut zur Entscheidung stellen.
- Die bestehende GitHub-Action `.github/workflows/ci.yml` ignoriert reine Dokumentations-Pfade (`docs/**/*.md`). Für den Dokumentations-PR ist deshalb **kein CI-Lauf ausgelöst**; es gibt keinen grünen Testnachweis. Bei #145 sind Migrationen/Regressionen/CI obligatorisch, inklusive Soft-Guidance- und Non-AI-Bypass-Negativtests.
- **#145 darf die neue Entscheidungskohorte nicht vor dem Gate aus #146 produktiv aktivieren.** Sonst entstünde während der Zwischenmigration der aktuell erkannte Non-KI-Bypass. Schema/Verknüpfungen dürfen vorbereitet werden; bindender Neupfad erst mit #146 und belegten Negativtests.
- Issue #148 bleibt ausdrücklich ein separater Priorisierungsentscheid.

**Merge dieses reinen Dokumentations-PR ist mit der fachlichen Nutzerannahme möglich.** Das ist **keine** vorzeitige Freigabe produktiver #145–#147-Änderungen, die ohne technische Abnahme unzulässig sind.
