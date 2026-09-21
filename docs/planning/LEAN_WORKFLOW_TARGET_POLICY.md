# Lean Workflow Target Policy

Issue: #403 · Parent: #401 · Grundlage: #402  
Geprüfter Ausgangsstand: `main` @ `7458d7df5e14d7da759056ef8e6aa2f3f0387457`

## 1. Leitprinzip

Der KI-UseCase-Radar ist ein pragmatisches KMU-Werkzeug, keine GRC- oder Workflow-Engine.

> **Arbeit darf weitergehen. Nur eine konkrete verbindliche Aktion wird serverseitig blockiert, wenn sie sonst eine fachlich falsche, unzulässige oder nicht verantwortbare Zustandsaussage erzeugen würde.**

Daraus folgen drei Zieltypen:

- **Advisory**: Qualitäts-/Hinweissignal. Keine Blockierung und keine Statuswirkung.
- **Readiness**: Offener Punkt, der vor einer Aktion sinnvoll geklärt werden sollte. Er bleibt sichtbar, darf aber **für sich allein keinen `ValidationError` / `PermissionDenied` und keinen globalen Workflow-Stopp erzeugen**. Kein neues Task-System; standardmäßig genügt sichtbarer Hinweis.
- **Enforcement**: Serverseitiger Hard Guard. Nur für Rollen-/Source-State-Invarianten, verbindliche Freigabe-/Lifecycle-Aussagen oder konkret risikorelevante Voraussetzungen.

`Readiness` bedeutet ausdrücklich nicht „Hard Block mit freundlicherem Text“.

## 2. Vor-Triage: Befundart vor Zieltyp

### Logikfehler / Invarianzbruch

Diese Punkte müssen in #400 als gemeinsame Invariante aufgelöst werden und dürfen nicht lediglich zu Readiness herabgestuft werden:

1. `START_REVIEW` besitzt heute keinen Source-State-Guard; Soll ist ausschließlich `IDEA -> REVIEW`.
2. Go-live akzeptiert heute ein `metric_measured_at` vor `pilot_start`, während Outcome diese Messung anschließend als ungültig wertet.
3. `OPERATION` und `ENDED` können über direkte Status-Services ohne passendes `GO_LIVE`-/`END`-Review-Artefakt entstehen; Soll ist Statusänderung ausschließlich über den kanonischen Command.
4. `RETURN -> PILOT` kollidiert mit den Fresh-Pilot-Start-Guards. Soll ist keine rückwärtslaufende Lifecycle-Transition; Rework bleibt in der erreichten Phase.
5. Journey und Backend behandeln Governance vor negativen Entscheidungen unterschiedlich. Die Sollregel wird unten explizit festgelegt.

### Policy-/Guard-Fragen

- Welche Voraussetzungen müssen positive Approval, Pilotstart, Go-live und END tatsächlich schützen?
- Welche Rollen dürfen die wenigen bindenden Aktionen auslösen?
- Was bedeuten `DEFERRED`, `NOT_PURSUED` und `ENDED` fachlich?

### Readiness-/UX-Beobachtungen

- hohe Vollständigkeitsdichte im Intake,
- Delivery-Feld-/Artefakt-/Textsemantik-Checks,
- Pilotplanungs- und Metrikvollständigkeit,
- ML-Test-Score, Tailoring, Monitoring- und Evidenzfelder,
- Abschlussdokumentation.

Diese Punkte können wichtig sein, sind aber nicht automatisch Lifecycle-Enforcement.

### Duplikat / Implementierungsproblem

Form, View, Service, Runtime-Wrapper und Journey bilden mehrere Regeln doppelt ab, insbesondere bei Approval, END, Review-Transitionen und Scale Readiness. #400 soll eine Domain-Quelle der Wahrheit schaffen; UI/Form darf nur Bedienhilfe sein.

## 3. Zielmatrix

### Intake, Review und Assessment

| Action | Einzelbedingung | Befundart | Zieltyp | Blockiert konkret | Begründung / Delta |
|---|---|---|---|---|---|
| IDEA anlegen | Titel, Organisationseinheit, Business Owner | Policy | Enforcement | Persistenz eines neuen Use Case | Minimale Identität und Verantwortlichkeit; `IDEA` dient zugleich als schlanker Draft. |
| Intake | Problem-/Prozess-/Nutzen-/Daten-/Metrik-Vollständigkeit | Readiness/UX | Readiness | nichts | Unvollständiger IDEA-Datensatz bleibt bearbeitbar; Vollständigkeit wird sichtbar statt Speichern zu verhindern. |
| Intake Problem | kurze technologiezentrierte Beschreibung | Readiness/UX | Advisory | nichts | Qualitätshinweis statt Form-Hard-Stop. |
| Intake Metrik | Prozentwert außerhalb 0–100 bzw. widersprüchliche Richtung bei vorhandenen Werten | Datenintegrität | Enforcement | Speichern des ungültigen Feldwerts | Kein Workflow-Gate, sondern Datenvalidität. |
| START_REVIEW | Source `IDEA`, Target `REVIEW` | Logikfehler | Enforcement | `START_REVIEW` | Kanonische Lifecycle-Invariante. |
| START_REVIEW | Actor mit semantischer Koordinator-Berechtigung | Policy | Enforcement | `START_REVIEW` | Bindende Lifecycle-Aktion. |
| START_REVIEW | übrige Intake-Vollständigkeit | Readiness/UX | Readiness | nichts | Review darf gerade dazu dienen, offene Punkte zu klären. |
| Assessment | Source `REVIEW` + Koordinator-Berechtigung | bereits gehärtete Invariante #395 | Enforcement | Assessment anlegen | Strukturierte Bewertung gehört in REVIEW. |
| Assessment | Evidenz-URL ab fachlicher Einschätzung | Readiness/UX | Advisory | nichts | Ein URL-Feld beweist keine Evidenz; fehlender Link darf Bewertung nicht stoppen. |
| Neues Assessment nach `DEFERRED` | Use Case bleibt `REVIEW` | Produktentscheidung #398 | Advisory | nichts | `DEFERRED` ist bewusst reaktivierbar; Versionierung + History reichen als Audit, kein Reopen-Workflow. |
| Neues Assessment nach `NOT_PURSUED` | finale Nichtweiterverfolgung | Produktentscheidung #398 | Enforcement | neue Bewertung/Reaktivierung | `NOT_PURSUED` ist terminal; erneuter Anlauf erfolgt als neuer Use Case. |

### Governance und Approval

| Action | Einzelbedingung | Befundart | Zieltyp | Blockiert konkret | Begründung / Delta |
|---|---|---|---|---|---|
| Governance-Screening | Koordinator-Berechtigung | Policy | Enforcement | Screening speichern | Risikoklassifikation bleibt verantwortete Handlung. |
| Screening | Begründung für „nicht relevant“ | Readiness/UX | Readiness | nichts | Aussage bleibt sichtbar; keine Dokumentationspflicht als Hard Stop. |
| Formale Fachprüfung | `COMPLETED` ohne Ergebnis | Datenintegrität | Enforcement | Status `COMPLETED` | „Abgeschlossen“ ohne Ergebnis wäre objektiv falsch. |
| Formale Fachprüfung | Evidence URL / ausführliche Rationale | Readiness/UX | Readiness | nichts | Nachweisqualität sichtbar, aber kein pauschaler Form-Hard-Stop. |
| `PASSED_WITH_CONDITIONS` | konkrete Conditions vorhanden | Zustandssemantik | Enforcement | Abschluss als „mit Auflagen bestanden“ | Status wäre ohne Auflage inhaltlich falsch. |
| `FAILED` | Risiken/Maßnahmen vollständig beschrieben | Readiness/UX | Readiness | nichts | Ein negatives Prüfergebnis muss sofort dokumentierbar sein; Maßnahmen können nachgezogen werden. |
| `DEFERRED` / `NOT_PURSUED` | Governance-Screening oder Fachprüfungen | Policy #396 | Advisory | nichts | Negative Entscheidung erzeugt kein Deployment-/Pilotrisiko. Journey und Backend müssen Governance dafür bewusst optional behandeln. |
| Positive Approval | strukturiertes Assessment vorhanden | Policy | Enforcement | positive Approval | Positive Freigabe braucht eine bewertete Entscheidungsgrundlage. |
| Positive Approval | Titel, Problem, betroffener Prozess, Business Owner, erwarteter Nutzen | Policy | Enforcement | positive Approval | Ohne Problem/Nutzen/Verantwortung wäre „freigegeben“ fachlich leer. |
| Positive Approval | Governance-Screening als tatsächliches Artefakt vorhanden | Policy | Enforcement | positive Approval | Minimal notwendige Risikoklassifikation vor positivem Commitment. |
| Positive Approval | erforderliche formale Fachprüfung ist bereits explizit `FAILED` | Risiko | Enforcement | positive Approval | Gegen ein dokumentiertes negatives Fachvotum darf nicht positiv freigegeben werden. |
| Positive Approval | erforderliche formale Fachprüfung noch offen | Policy | Readiness | nichts | Delivery-Vorbereitung darf parallel laufen; Abschluss der erforderlichen Prüfung wird spätestens vor Pilotstart Enforcement. |
| Positive Approval | `governance_precheck_completed` / `governance_confirmed` als zusätzliche Checkboxen | Duplikat | Advisory | nichts | Nicht doppelt bestätigen; aus tatsächlichen Governance-Artefakten ableiten. |
| Positive Approval | Baseline / Zielwert | Readiness/UX | Readiness | nichts | Darf bis zur Pilotvorbereitung konkretisiert werden. |
| Positive Approval | Confidence LOW, Technical Feasibility LOW, Data Readiness LOW, Risk HIGH | Policy | Readiness | nichts | Entscheidungsunterstützung statt automatischer Managemententscheidung; Abweichung bleibt sichtbar. |
| Positive Approval | Assessment-Empfehlung weicht von Entscheidung ab | Policy | Advisory | nichts | Heutiges Warning-Prinzip beibehalten. |
| Positive Approval | Entscheider != Assessor und != Business Owner | Rollentrennung | Enforcement | positive Approval | Vier-Augen-/Interessenkonflikt-Schutz für positives Commitment. |
| Negative Entscheidung | Assessment vorhanden / Entscheider != Assessor | Policy | Readiness | nichts | Ein Use Case muss früh zurückstellbar oder ablehnbar sein; keine Bewertung erzwingen, nur Entscheidung/Rationale sichtbar halten. |
| `APPROVED_WITH_CONDITIONS` | Conditions + Condition Owner | Zustandssemantik | Enforcement | bedingte Approval | „Mit Auflagen“ braucht benannte Auflage und Verantwortlichkeit. |
| `APPROVED_WITH_CONDITIONS` | Fälligkeitsdatum | Readiness/UX | Readiness | nichts | Operative Planung, keine Zustandsinvariante. |
| `APPROVED_WITH_CONDITIONS` | unabhängiger Second Approver | Rollentrennung | Enforcement | Finalisierung der bedingten Approval | Vier-Augen-Regel bleibt bindend. |
| Zweitfreigabe | Assignee unabhängig/aktiv/berechtigt + Assessment unverändert | Rollentrennung/Invariante | Enforcement | Zweitfreigabe bestätigen | Verhindert Selbstfreigabe und Entscheidung auf veralteter Basis. |
| Zweitfreigabe zurückgeben | Return Reason | Readiness/UX | Readiness | nichts | Rückgabe darf nicht wegen Dokumentation scheitern; Grund bleibt empfohlen. |

### Delivery und Handover

| Action | Einzelbedingung | Befundart | Zieltyp | Blockiert konkret | Begründung / Delta |
|---|---|---|---|---|---|
| Delivery Package erzeugen | finale positive Approval vorhanden | Zustandssemantik | Enforcement | Package-Erzeugung | Delivery entsteht nur aus positiver Freigabe. |
| Delivery Package erzeugen | Actor Koordinator oder zugeordneter Business Owner | Policy/UX | Enforcement | Package-Erzeugung | Entspricht fachlicher Verantwortung und verhindert unnötigen Koordinator-Bottleneck. |
| Delivery bearbeiten | Package bereits `HANDED_OVER` | Zustandssemantik | Enforcement | Änderung des übergebenen Snapshots | Handover bleibt unveränderlicher Snapshot. |
| Delivery Readiness | Technical Owner fehlt/inaktiv | Policy | Readiness | nichts | Muss vor Handover geklärt sein, soll Bearbeitung/READY-Vorbereitung aber nicht stoppen. |
| Delivery Readiness | Section Review / Source Manifest / Bestätigung fehlt | Readiness/UX | Readiness | nichts | Sichtbarer offener Punkt, keine Dokumentationssperre. |
| Delivery Readiness | Sektion wurde ausdrücklich `BLOCKED` markiert | fachlicher Blocker | Enforcement | `READY` / Handover | Explizites negatives Fachsignal darf nicht durch Statusklick überschrieben werden. |
| Delivery Readiness | Pflichtfelder / generische Platzhalter / Architekturartefakte unvollständig | Readiness/UX | Readiness | nichts | Größter Dokumentations-Hard-Stop wird auf Readiness reduziert. |
| Delivery Readiness | Output-/Confidence-/Grounding-/Retention-/Retry-Parser finden Lücken | Readiness/UX | Readiness | nichts | Qualitätsprüfung bleibt sichtbar, darf generisches KMU-Handover nicht hart verhindern. |
| Delivery Readiness | Testpopulation/Stichprobe/Unsicherheit etc. | Readiness/UX | Advisory | nichts | Bestehende Warning-Semantik beibehalten. |
| Delivery Readiness | Approval-Auflagen nicht vollständig in Handover-Text übertragen | Duplikat/Readiness | Readiness | nichts | Originalentscheidung bleibt Source of Truth; keine Textkopierpflicht als Gate. |
| Delivery Readiness | Quelländerung nach Snapshot | Readiness/UX | Advisory | nichts | Bestehende Warning-Semantik. |
| `READY` setzen | Actor Koordinator oder zugeordneter Business Owner | Policy | Enforcement | `READY` setzen | READY ist eine verantwortete Erklärung, aber keine 100%-Dokumentationszertifizierung. |
| Handover | Source Package `READY` | Zustandssemantik | Enforcement | Handover | Klare Package-State-Invariante. |
| Handover | Actor Koordinator oder zugeordneter Business Owner | Policy | Enforcement | Handover | Verbindlicher Snapshot durch accountable Rolle. |
| Handover | Technical Owner vorhanden und aktiv | Verantwortlichkeit | Enforcement | Handover | Übergabe ohne technischen Verantwortlichen ist fachlich leer. |
| Handover | sonstige Readiness Findings offen | Readiness/UX | Readiness | nichts | Offene Punkte bleiben sichtbar und können parallel geschlossen werden. |

### START_PILOT

| Action | Einzelbedingung | Befundart | Zieltyp | Blockiert konkret | Begründung / Delta |
|---|---|---|---|---|---|
| START_PILOT | Source `REVIEW`, Target `PILOT` | Lifecycle-Invariante | Enforcement | START_PILOT | Kanonischer Übergang. |
| START_PILOT | Actor Koordinator oder zugeordneter Business Owner | Rolle | Enforcement | START_PILOT | Pilotstart ist verantwortete fachliche Handlung. |
| START_PILOT | finale positive Approval | Zustandssemantik | Enforcement | START_PILOT | Kein Pilot ohne positives Commitment. |
| START_PILOT | aktuelles Package verbindlich handed over | Zustandssemantik | Enforcement | START_PILOT | Pilot startet erst auf einem übergebenen Umsetzungsstand. |
| START_PILOT | Governance-Screening vorhanden | Risiko | Enforcement | START_PILOT | Risikoklassifikation muss vor realem Pilotbetrieb vorliegen. |
| START_PILOT | laut Screening erforderliche Privacy/Security/Legal-Prüfung abgeschlossen und nicht `FAILED` | Risiko | Enforcement | START_PILOT | Echte risikobasierte Grenze; künftig stärker als heutiger reine Screening-Existenzcheck. |
| START_PILOT | tatsächliches Startdatum vorhanden, nicht in Zukunft, nicht vor Handover | Lifecycle-Invariante | Enforcement | START_PILOT | Persistierter Pilotstart muss zeitlich wahr sein. |
| START_PILOT | Title/Problem/Prozess/Owner/Nutzen erneut vollständig | Duplikat | Readiness | nichts | Positive Approval hat den fachlichen Kern bereits verantwortet; nicht mehrfach hard gaten. |
| START_PILOT | Data Sources | Readiness/UX | Readiness | nichts | Offen sichtbar, aber kein generischer Stop; konkrete Datenrisiken gehören in Governance. |
| START_PILOT | Next Review Date / Planned Pilot End | Readiness/UX | Readiness | nichts | Planung darf nachgezogen werden. |
| START_PILOT | Metric Name/Type/Direction/Unit/Baseline/Target/Method | Readiness/UX | Readiness | nichts | Pilot darf Erkenntnis erzeugen; fehlende Metrikdetails bleiben prominent offen und werden für Go-live enger bewertet. |
| START_PILOT | Baseline == Target | Readiness/UX | Readiness | nichts | Unbrauchbare Zieldefinition sichtbar, aber kein Pilot-Stopp. |
| START_PILOT | Planned Pilot End liegt vor Start/in Vergangenheit | Readiness/UX | Readiness | nichts | Plan korrigieren, tatsächlichen Start nicht künstlich verhindern. |

### Measurement, GO_LIVE und Scale Readiness

| Action | Einzelbedingung | Befundart | Zieltyp | Blockiert konkret | Begründung / Delta |
|---|---|---|---|---|---|
| Messdaten bearbeiten | bestimmter Lifecycle-Status | Readiness/UX | Advisory | nichts | Messung darf vorbereitet/nachgetragen werden; nur ihre Verwendbarkeit für Go-live wird geprüft. |
| GO_LIVE | Source `PILOT`, Target `OPERATION` | Lifecycle-Invariante | Enforcement | GO_LIVE | Kanonischer Übergang. |
| GO_LIVE | Actor mit semantischer Koordinator-Berechtigung | Rolle | Enforcement | GO_LIVE | Produktivsetzung bleibt bindende Management-/Governance-Entscheidung. |
| GO_LIVE | passendes `GO_LIVE`-Review wird atomar mit Statuswechsel erzeugt | Logikfehler | Enforcement | Status `OPERATION` | Kein OPERATION-Status ohne Command-/Review-Artefakt. |
| GO_LIVE | primäre Metrik hat Name, Direction, Target und Actual | Entscheidungsgrundlage | Enforcement | GO_LIVE | Ohne Ziel-Ist-Vergleich kann Pilotwirkung nicht bewertet werden. |
| GO_LIVE | `metric_measured_at` vorhanden und `>= pilot_start` | Logikfehler | Enforcement | GO_LIVE | Schließt heutigen Outcome-/Backend-Widerspruch. |
| GO_LIVE | Measurement Period / Evidence URL / ausführliche Measurement Method | Readiness/UX | Readiness | nichts | Nachweisqualität sichtbar, aber keine generische Dokumentationssperre. |
| GO_LIVE | erforderliche Governance-Prüfung inzwischen offen oder `FAILED` | Risiko | Enforcement | GO_LIVE | Produktion darf keine aktuell offene/negative erforderliche Fachprüfung übergehen. |
| GO_LIVE vor `planned_pilot_end` | separate Early-Go-live-Ausnahme + drei Textfelder | Policy/Readiness | Readiness | nichts | Geplantes Enddatum ist ein Plan, kein eigenständiges Risikogate. Ausreichende aktuelle Evidenz entscheidet; separate Ausnahmebürokratie entfällt als Hard Stop. |
| GO_LIVE bei `metric_result=NOT_ACHIEVED` | ausdrückliche Ausnahme + kurze Rationale | Risikoakzeptanz | Enforcement | GO_LIVE | Bewusstes Übergehen eines verfehlten Zieles muss explizit verantwortet werden. |
| Go-live-Ausnahme | Actor | Rolleninkonsistenz | Enforcement | Ausnahmebestätigung | Einheitlich semantisches `is_coordinator`; keine abweichende Raw-Group-Sonderlogik. |
| Scale Tailoring A/B/C | Stufe/Minimum | Readiness/UX | Readiness | nichts | Methodik unterstützt, blockiert aber nicht pauschal Produktion. |
| Scale Pilot Validation Checkbox | separate Bestätigung | Duplikat | Readiness | nichts | Aus realer Pilotmessung ableiten, keine zweite Checkbox als Hard Gate. |
| ML Test Score | Dimensionen, Mindestwert, Version, Datum, Evidence URL | Readiness/UX | Readiness | nichts | Methodik-/Qualitätssignal; nicht jeder KI-Use-Case ist ein klassisches ML-Modell. |
| ML Test Score | explizit dokumentierte `failed_mandatory_checks` | Risiko | Enforcement | GO_LIVE | Bewusst fehlgeschlagene als zwingend deklarierte Prüfung darf nicht übergangen werden. |
| Scale Deployment | Production Version | Readiness/UX | Readiness | nichts | Traceability sinnvoll, aber kein generischer Stop. |
| Scale Deployment | Rollback/Deaktivierung praktisch möglich/getestet | Betriebssicherheit | Enforcement | GO_LIVE | Produktionssystem muss kontrolliert deaktivierbar sein. |
| Scale Operations | Technical Monitoring / AI Quality Monitoring | Readiness/UX | Readiness | nichts | Offen sichtbar; konkrete regulatorische Pflicht gehört in Governance. |
| Scale Operations | Incident-/Eskalationsprozess | Readiness/UX | Readiness | nichts | KMU-Readiness, kein pauschales Lifecycle-Gate. |
| Scale Responsibility | Technical Owner + Support Responsibility | Verantwortlichkeit | Enforcement | GO_LIVE | Betrieb ohne technische/operative Verantwortung ist nicht verantwortbar. |
| Scale Responsibility | Human Oversight als generisches Textfeld | Policy | Readiness | nichts | Nur dann Enforcement, wenn Governance es für den konkreten Use Case verlangt; kein globaler Textfeld-Hard-Stop. |
| Scale Evidence URL | Nachweislink | Readiness/UX | Advisory | nichts | Link ist kein Risiko-Guard. |
| Tailoring C | `scale_extended_controls_completed` Checkbox | Duplikat/Policy | Readiness | nichts | Konkrete erforderliche Fachprüfungen schützen bereits den Go-live; keine Black-box-Sammelbestätigung. |
| Scale Result `conditional` | Open Actions / Owner / Due Date | Readiness/UX | Readiness | nichts | Kein zweites generisches Task-/Remediation-System; offene Punkte sichtbar halten. |
| Downstream GO_LIVE | frühere Approval-/Handover-Guards erneut vollständig prüfen | Duplikat | Advisory | nichts | Kanonischer `PILOT`-Source-State soll frühere Transition-Invarianten garantieren; nur aktuelle Risiken erneut prüfen. |

### Operation Reviews, Lifecycle-Regress und END

| Action | Einzelbedingung | Befundart | Zieltyp | Blockiert konkret | Begründung / Delta |
|---|---|---|---|---|---|
| CONTINUE / PAUSE / REWORK | Status bleibt unverändert | Zustandssemantik | Enforcement | versteckte Lifecycle-Änderung | Diese Commands sind Review-Annotationen, keine Lifecycle-Transition. |
| CONTINUE / PAUSE / REWORK | ausführliche Rationale | Readiness/UX | Readiness | nichts | Arbeitsfortschritt nicht wegen Dokumentation blockieren. |
| Lifecycle `RETURN` in frühere Phase | beliebiges früheres Target | Logikfehler/Komplexität | Advisory | nichts | **Aus dem Soll-Lifecycle entfernen.** Erreichter Lifecycle-Meilenstein wird nicht rückwärts geschrieben; Rework bleibt in aktueller Phase. |
| Rework nach Pilot/Go-live | Lifecycle zurücksetzen | Policy | Readiness | nichts | Status bleibt `PILOT` bzw. `OPERATION`; offene Arbeit/Review wird separat angezeigt. |
| END | Source `PILOT` oder `OPERATION`, Target `ENDED` | Lifecycle-Invariante #397 | Enforcement | END | Pre-Pilot-Stopp erfolgt über Decision-Status, nicht über ENDED. |
| END | Actor Koordinator oder zugeordneter Business Owner | Policy | Enforcement | END | Stoppen muss ohne unnötigen Koordinator-Bottleneck möglich sein. |
| END | passendes END-Review wird atomar mit `ENDED` erzeugt + `actual_end_date` gesetzt | Logikfehler | Enforcement | Status `ENDED` | Kein ENDED ohne dokumentierte End-Entscheidung. |
| END | Ending Reason | Readiness/UX | Readiness | nichts | Stoppen darf nicht an Dokumentation scheitern; Grund bleibt sichtbar offen. |
| END | Data and Access Handling | Risiko-Nachlauf | Readiness | nichts | Wichtig, aber **kein Block des END-Status**. Nach `ENDED` als offener Punkt anzeigen; bestehendes Feld nutzen, kein neuer Status/Task-Typ. |
| END | Replacement Solution / Final Assessment / Lessons Learned | Readiness/UX | Advisory | nichts | Optional belassen. |
| END | vollständige Wirkungsmessung | Policy | Advisory | nichts | Ein Pilot/Betrieb muss auch bei fehlender oder negativer Evidenz gestoppt werden können. |
| END | Handover/Pilotstart erneut prüfen | Duplikat/Invariante | Advisory | nichts | Gültige Source-States müssen die vorherigen Meilensteine über den kanonischen Transition-Contract garantieren; Legacy-Inkonsistenz anzeigen, aber Stop nicht verhindern. |
| Closure | `status=ENDED` + passendes END-Review | Produktentscheidung #399 | Enforcement | Darstellung als fachlich beendet | `ENDED` bedeutet „nicht mehr aktiv“, nicht „100 % Dokumentation abgeschlossen“. |
| Closure | Data/Access Handling noch offen | Readiness/UX | Readiness | nichts | Darstellung: beendet + offener Nachlaufpunkt; nicht `blocked`/Dateninkonsistenz. |

## 4. Verbindliche Zielinvarianten für #400

1. **Monotoner Lifecycle:** `IDEA -> REVIEW -> PILOT -> OPERATION -> ENDED`; zusätzlich `PILOT -> ENDED`. Keine rückwärtslaufenden Statusänderungen. `REWORK/PAUSE/CONTINUE` verändern den Lifecycle nicht.
2. **Command erzeugt Status + Artefakt atomar:** `START_REVIEW`, `START_PILOT`, `GO_LIVE`, `END` sind die einzigen bindenden Lifecycle-Commands. `OPERATION` und `ENDED` dürfen nicht ohne passendes Review-Artefakt persistiert werden.
3. **Nur Enforcement blockiert serverseitig.** Advisory und Readiness bleiben sichtbar und priorisierbar, erzeugen aber allein keinen `ValidationError` und keine neue Workflow-/Task-Schicht.
4. **Negative Portfolioentscheidung ist leichtgewichtig:** `DEFERRED` und `NOT_PURSUED` brauchen keine Governance-/Vollständigkeitskette. `DEFERRED` ist reaktivierbar, `NOT_PURSUED` terminal.
5. **Positive Approval ist Commitment, nicht Go-live:** Screening + Kernproblem + Rollentrennung sind Enforcement; Metrikreife, Scores und noch offene erforderliche Fachreviews sind Readiness, solange kein Review explizit `FAILED` ist.
6. **Pilotstart schützt reale Exposition:** positive finale Approval, Handover, risikobasiert erforderliche Governance-Prüfungen, Rolle und wahrer Startzeitpunkt sind Enforcement; Metrik-/Planungs-/Dokumentationsvollständigkeit bleibt Readiness.
7. **Go-live schützt aktuelle Betriebsentscheidung:** aktuelle Pilotmessung (`measured_at >= pilot_start`), primärer Ziel-Ist-Vergleich, erforderliche Governance, bewusste Ausnahme bei verfehltem Ziel, Deaktivierbarkeit sowie technische/operative Verantwortung sind Enforcement. ML-Score-/Tailoring-/Dokumentationsfelder sind nicht pauschal Enforcement.
8. **ENDED = fachlich nicht mehr aktiv:** END ist aus `PILOT/OPERATION` jederzeit möglich; fehlende Abschlussdokumentation verhindert den Stop nicht. `data_and_access_handling` bleibt sichtbarer Readiness-Nachlauf ohne neuen Status.
9. **Rollen konsistent über semantische Permission-Helper:** keine Mischung aus `is_coordinator` und Raw-Group-Checks für dieselbe Capability. Bestehende Semantik von `is_coordinator` bleibt zunächst maßgeblich; eine spätere Änderung der Tech-Admin-Vererbung wäre eine eigene Rollenentscheidung.
10. **Journey ist Projektion, keine zweite State Machine:** `blocked` darf nur aus derselben Enforcement-Policy entstehen. Readiness wird als offen/noch nicht empfohlen dargestellt, ohne andere sinnvolle Arbeit zu verstecken.

## 5. Delta zu bestehenden Issues

### #395 – Assessment außerhalb REVIEW

Keine Änderung. Der Fix entspricht der Zielinvariante: Assessment gehört in `REVIEW`.

### #396 – Governance bei negativen Entscheidungen

Fachliche Entscheidung:

- `DEFERRED` und `NOT_PURSUED` dürfen **ohne Governance-Screening und ohne Fachreviews** final dokumentiert werden.
- Journey darf Approval für diese negativen Entscheidungen nicht hinter Governance blockieren.
- Positive Approval benötigt dagegen mindestens ein tatsächliches Screening-Artefakt.
- Offene erforderliche Fachreviews sind bei positiver Approval Readiness; ein bereits `FAILED` Review ist Enforcement. Spätestens vor START_PILOT müssen alle laut Screening erforderlichen Reviews erfolgreich abgeschlossen sein.

#396 wird damit zu einem kleinen Journey-/Backend-Alignment-Fix, nicht zu einem zusätzlichen Governance-Gate.

### #397 – END Source-State

Keine Änderung. `END` bleibt ausschließlich aus `PILOT` oder `OPERATION` zulässig. Vor Pilot wird über `DEFERRED`/`NOT_PURSUED` gestoppt.

### #398 – DEFERRED

Fachliche Entscheidung:

- `DEFERRED` = geparkt / später reaktivierbar.
- `NOT_PURSUED` = final nicht weiterverfolgt.
- Für `DEFERRED` kein neuer Reopen-Status und kein Reopen-Workflow. Eine neue versionierte Bewertung in `REVIEW` reaktiviert; vorhandene History genügt für Nachvollziehbarkeit.
- Journey darf `DEFERRED` daher nicht als endgültig „Journey beendet“ darstellen.

### #399 – ENDED / Closure

Fachliche Entscheidung:

- `ENDED` bedeutet: Use Case ist nach Pilot oder Betrieb **fachlich nicht mehr aktiv**.
- Es bedeutet nicht „alle Abschlussfelder vollständig“.
- `status=ENDED` muss aus einem kanonischen `END`-Command mit END-Review entstehen.
- `ending_reason` und `data_and_access_handling` dürfen den Stop nicht verhindern; letzteres bleibt als sichtbarer Nachlaufpunkt.
- Eine legitime Beendigung wird nicht wegen fehlender optionaler Historien-/Dokumentationsartefakte als Dateninkonsistenz `blocked` dargestellt.

### #400 – zentrale Transition-Policy

#400 soll diese Policy implementieren, insbesondere:

- monotone `source + command -> target`-Matrix,
- kein Lifecycle-`RETURN`,
- ein kanonischer Transition-Einstieg mit atomarem Review-Artefakt,
- Enforcement/Readiness sauber trennen,
- Runtime-Wrapper/Forms/Journey nicht als konkurrierende Guard-Quellen,
- Measurement-Go-live-Invariante schließen,
- Delivery-/Scale-Hard-Gates auf den oben definierten minimalen Enforcement-Kern reduzieren,
- Rollenprüfungen über gemeinsame Permission-Helper.

## 6. Bewusst verworfene Überkomplexität

- kein neuer `DRAFT`, `PAUSED`, `CLOSED`, `ARCHIVED` oder `REOPENED` Lifecycle-Status,
- kein generisches Override-/Waiver-System für jede Readiness-Lücke,
- kein Remediation-/Task-Subsystem für offene Punkte,
- keine separate Closure-/Archivierungsphase für `data_and_access_handling`,
- kein vollständiges ML-Test-Score-/CRISP-ML(Q)-Gate für jeden Go-live,
- keine neue BPMN-/Workflow-Engine,
- keine Statusregression als Ersatz für Rework,
- keine doppelte Governance-Bestätigung per Checkbox, wenn echte Artefakte existieren,
- keine 100-%-Delivery-Dokumentation als Voraussetzung für Arbeitsfortschritt,
- keine Pflicht-Nachweislinks allein aus Auditästhetik.

Das Ziel ist ein kleiner, deterministischer Kern: **wenige echte Transition-Gates, viele sichtbare Readiness-Hinweise und maximaler Arbeitsfortschritt.**
