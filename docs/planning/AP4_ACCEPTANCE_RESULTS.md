# AP4 Realabnahme – Issue #107

Stand: 2026-10-01

Scored Code-Stand: `1a3f02adc5e7850dd643044598e303350bf9a1c3`

Branch: `feature/issue-107-ap4-evidence`

## Population und Methode

- Vier frische geführte Referenzpfade wurden für AP4-01 bis AP4-04 gegen exakt dieselben eingefrorenen Problemstellungen und Source Packs erfasst.
- Acht autonome scored Slots wurden jeweils genau einmal mit einem echten OpenRouter-Provider ausgeführt. Kein scored Failure wurde wiederholt oder ersetzt.
- Die Providerläufe nutzten Discovery mit `google/gemini-3.6-flash`; nachgelagerte AP2-Schritte nutzten die konfigurierte reale Providerstrecke. Mocks waren nicht aktiv.
- Die geführten Baselines und die scripted Acceptance-Operator-Aktionen sind keine unabhängige Human Review. Nicht gemessene menschliche Zeit wird im Evidence-Aggregator jetzt ausdrücklich als **offen** behandelt und nicht mehr als numerische `0` gewertet. Der Blind Human Review wurde nicht durchgeführt; er ist für den aktuellen technischen Abschlussweg bewusst ausgeschlossen und bleibt als Qualitätsnachweis unerfüllt.

## Frische Baselines

| Fall | Referenz-Endzweig | aktive Eingabe | manuelle Werte | Ergebnis |
|---|---|---:|---:|---|
| AP4-01 | organisatorisch / Non-AI | 43 s | 23 | PASS |
| AP4-02 | Rule Automation / Non-AI | 41 s | 21 | PASS |
| AP4-03 | Controlled LLM, danach Governance-Gate | 45 s | 25 | PASS |
| AP4-04 | Hybrid-Kandidat, danach Solution-/Governance-Gates | 51 s | 26 | PASS |

Die Baseline-Artefakte nennen keine erfundenen Baselines, Zielwerte, Kosten oder Fristen. Entscheidungen und Pilotvorschläge sind von belegten Tatsachen getrennt.

## Initial scored result

| Fall | gespeicherter Endzustand | fachliche Bewertung |
|---|---|---|
| AP4-01 | `non_ai_selected` | PASS – organisatorischer Engpass, Non-AI-Endzweig, keine künstliche KI-Materialisierung |
| AP4-02 | `non_ai_selected` | PASS – deterministische Regeln und CSV-Evidenz, Rule Automation statt KI |
| AP4-03 | `waiting_human` in Governance | PASS – Controlled LLM mit menschlicher Versandentscheidung; unbekannte Governance-Fakten blockieren korrekt |
| AP4-04 | `waiting_human` in Investigation | FAIL – vermeidbare Anfrage nach bereits formulierten Lösungsmaßnahmen statt hypothesenbasierter Optionen |
| AP4-05 | Investigation fachlich `READY`, Runner danach fail-closed | FAIL – offene Entscheidungshoheit und Ausnahmeverantwortung hätten eine präzise menschliche Rückfrage erzwingen müssen |
| AP4-06 | Investigation fachlich `READY`, Runner vor Auswahl gestoppt | PASS – beide widersprüchlichen Quellen sichtbar; keine Quelle still bevorzugt; offene Authority-Entscheidung bleibt sichtbar |
| AP4-07 | `waiting_human` an Solution Selection | PASS – keine Ursache erfunden; Cloud-/AI-Richtung bleibt von Privacy-, Security- und Legal-Review abhängig |
| AP4-08 | `waiting_human` in Governance | FAIL der ursprünglichen Acceptance-Wertung – Investigation und Berechnungen korrekt; der scripted Acceptance-Operator wählte Analytics/ML entgegen der Empfehlung. Der scored Failure bleibt unverändert erhalten. |

Die AP4-08-Gruppenrechnung ist reproduzierbar: `parts_available=false` 12,00 h (n=4), `true` 4,75 h (n=4), Differenz 7,25 h. Der Brief behauptet daraus keine Kausalität.

Die Produktlogik bindet nachgelagerte AP2-Schritte an die **tatsächlich menschlich ausgewählte** `SolutionSelectionDecision.selected_option`: `require_current_selected_use_case()` lehnt Use Cases ab, deren `UseCaseOrigin.solution_option` nicht der aktuellen menschlichen Lösungswahl entspricht. Eine menschliche Auswahl entgegen der Empfehlung ist daher nicht selbst ein Cross-Domain-Produktfehler. Der explizite AP4-08-Folgenachweis bestätigt diesen Pfad; der ursprüngliche scored Failure wird nicht umgeschrieben.

## Gefundene Bugs und gezielte Fixes

1. Historische Investigation-Provenance war nach Verlassen von `DRAFT` nicht mehr lesbar, weil der Read-Pfad den Edit-Guard nutzte. Der Read-Guard prüft nun weiterhin Actor, Ownership, aktiven Quellenraum und Snapshot-Zuordnung, aber nicht den Edit-Status. Schreiboperationen bleiben gesperrt. Browser und Regressionstest bestätigen das Verhalten.
2. Planner `v18` verwechselte fehlende fertige Lösungsvorschläge mit fehlender Entscheidungsevidenz (AP4-04). Planner `v19` fordert jetzt hypothesenbasierte Optionen aus ausreichender Problem-/Scope-Evidenz und verbietet diese vermeidbare Rückfrage. Der reale Post-Fix-Run erreicht `READY` mit Regel-, Hybrid-, GenAI- und Status-quo-Optionen; die Auswahl bleibt menschlich.
3. Planner `v18` synthetisierte trotz ausdrücklich offener Entscheidungshoheit/Ausnahmeverantwortung (AP4-05). Planner `v19` bindet diese Grenze an `permission_or_scope`. Nach zwei unverändert erhaltenen Provider-Quota-Failures bestätigt der lineare Real-Provider-Lauf `PF3` den Fix: Planner v19 wurde nachweislich ausgeführt und stoppte mit einer präzisen menschlichen Zuständigkeitsfrage.
4. Der AP4-Evidence-Vertrag konnte nach einer legitimen Prompt-Härtung keine historischen Records mehr auswerten. Post-Fix-Records binden nun die tatsächlich verwendeten aktuellen Vertragsversionen, während neue scored Records weiterhin strikt gegen den eingefrorenen Vertrag geprüft werden.

Bei der gezielten Folgeabnahme am 2026-10-01 trat kein weiterer reproduzierbarer Produktdefekt auf; entsprechend wurde kein Produktcode geändert.

## Post-Hardening

- AP4-04: PASS im separaten echten Providerlauf; Browser zeigt den Decision Brief, vier Optionen und das unveränderte menschliche Solution-Gate.
- AP4-05: PASS im genau einmal ausgeführten linearen Real-Provider-Lauf `AP4-05-PF3`. Discovery war erfolgreich; der persistierte Execution Snapshot weist Planner `vs1-planner-v19`/Schema `v16` aus. Investigation stoppte korrekt mit `waiting_human`/`permission_or_scope` und fragte nach verbindlicher Entscheidungshoheit sowie Ausnahmeverantwortung. Es wurden keine Authority-Entscheidung, SolutionOption oder SelectionDecision erfunden. Scored Failure, `PF1` und `PF2` bleiben unverändert erhalten.
- AP4-08: PASS für den Human-Authority-/Domainpfad. Im echten Browser wurde bewusst die organisatorische Non-AI-Option „Ersatzteilverfügbarkeit verbessern“ ausgewählt. Die neue bindende Entscheidung bleibt neben der früheren ML-Entscheidung historisiert. Der alte AI-Use-Case wird vor UseCase-, Architecture- und Governance-Fortsetzung als nicht mehr aktuell blockiert; Delivery bleibt ohne finale positive Freigabe ineligible und hat kein Paket erzeugt. Der ursprüngliche scored Failure bleibt erhalten; **kein Produktfix** war angezeigt. Der separate Authority-Folgenachweis ist als linearer Evidence-Record `AP4-08-auto-post-fix-1` abgebildet, damit das Post-Hardening-Aggregat den bestätigten Endzustand ausweist.

## Kennzahlen

| Kriterium | Initial scored | Post-Hardening | Ziel |
|---|---:|---:|---:|
| aktive Human Work, Median | offen / nicht gemessen* | offen / nicht gemessen* | ≤ 1.200 s |
| Reduktion manueller Feldpflege | 91,58 % | 91,58 % | ≥ 90 % |
| vermeidbare Rückfragen, Median | 0 | 0 | ≤ 3 |
| Provenance | 98,55 % | 100 % | 100 % |
| halluzinierte Fakten/Messwerte | 0 | 0 | 0 |
| Cross-Domain-Konsistenz, alle Fälle | FAIL | **PASS** | alle PASS |
| erwarteter Endzustand, alle Fälle | FAIL | **PASS** | alle PASS |
| menschliche Nacharbeit / Baseline | offen / nicht gemessen* | offen / nicht gemessen* | ≤ 20 % |

\* Nur tatsächlich gemessene aktive menschliche Zeit wird gezählt. Scripted Acceptance-Operator-Aktionen werden nicht in erfundene Zeitwerte umgerechnet. Diese beiden Zeitmetriken bleiben **quantitativ nicht nachgewiesen** und erzeugen keinen PASS. Die gestoppte erste Human-Time-Kampagne erlaubt keinen belastbaren Median und keine Nacharbeitsquote; für diesen Abschlussweg wird keine zweite Kampagne gestartet.

## Browser- und Domain-State-Evidence

- Alle acht Discovery-Seiten, alle acht gespeicherten Investigation-Zustände und alle acht Solution-Vergleiche antworteten im echten Chrome mit HTTP 200 und ohne horizontalen Overflow.
- AP4-03 und AP4-08 zeigten zusätzlich die gespeicherten AP2-Entscheidungs-/Governance-Oberflächen.
- AP4-01s menschliches Solution-Gate wurde im Browser gespeichert und endete korrekt im organisatorischen Non-AI-Zweig.
- Nach dem Read-Guard-Fix bleiben terminale Decision Briefs lesbar; Schreibzugriffe sind per Test weiterhin untersagt.
- AP4-04 Post-Fix zeigt im Browser alle vier materialisierten Kandidaten sowie das menschliche Diagnose-/Solution-Gate.
- AP4-08 zeigt die neue organisatorische Auswahl mit Bestätigungsbanner und vollständiger Entscheidungshistorie. Der gespeicherte Domain-State bestätigt dieselbe bindende Auswahl und die Downstream-Sperren.
- AP4-05 PF3 zeigt im echten Chrome „Klärung erforderlich“ mit derselben Authority-/Ausnahmefrage wie der persistierte Domain-State. Der Run enthält keine SolutionOptions oder SelectionDecisions.
- Strukturierte States: `artifacts/ap4/browser-state.json`, `artifacts/ap4/browser-state-post-fix.json`, `artifacts/ap4/browser-state-ap4-05-pf3.json` und `artifacts/ap4/human_authority/AP4-08.json`; Screenshots liegen unter `artifacts/ap4/browser/`.

## Gemessene Zeit im Authority-Folgenachweis

- AP4-08 Browser-Operator-Laufzeit: 102,581 s, real gemessen von Öffnen des Solution-Vergleichs bis zur erfolgreichen Speicherung.
- Diese Zeit stammt aus der CLI-gestützten Abnahme und umfasst Navigation sowie Werkzeuglauf. Sie ist deshalb ausdrücklich **keine menschliche Arbeitszeit** (`human_time_measured=false`) und wird nicht in die AP4-Human-Work- oder Nacharbeitsmetriken eingerechnet.
- Dieser Authority-Folgenachweis misst keine menschliche Arbeitszeit. Auch die spätere, gestoppte erste Human-Time-Kampagne belegt die beiden Zeitmetriken nicht; es wurden keine Zeiten geschätzt.

## Historischer Plan-/Issue-Abgleich vor Human-Time

Der führende Arbeitsplan bleibt während AP4 unverändert. Die folgende Tabelle bewahrt den historischen Stand vor der ersten Human-Time-Kampagne; der aktuelle technische Abschlussweg steht darunter. Sie ist keine Änderung des Plans oder Messvertrags.

| Plan | Issue-/Evidence-Stand | Status vor Human-Time |
|---|---|---|
| §32 Ziel: keine neue Funktionalität, belastbarer E2E-Nachweis | 8 reale Fälle, Browser-/Provider-/Domain-Evidence, keine offene Produktlücke | **ERFÜLLT technisch; Gesamtnachweis noch offen** |
| §33 Testpopulation | 8 eingefrorene unterschiedliche Fälle, Non-AI und WAITING_HUMAN zulässig | **ERFÜLLT** |
| §34 kein Success Sampling | 8 scored Slots unverändert; 5 lineare Post-Fix-Records; ursprüngliche Failures erhalten | **ERFÜLLT** |
| §35 #1-Metriken | Feldpflege 91,58 %, Rückfragen Median 0, Provenance post-hardening 100 %, Halluzinationen 0, Cross-Domain PASS, erwartete Endzustände PASS | **TEILWEISE** – Human Work, menschliche Nacharbeit und Blind Human Review offen |
| §36 technische Härtung | alle Szenarien durch aktuelle Regressionen/Realbefunde abgedeckt; `irrelevant_source` durch die vorhandenen semantischen Relevanz-/Clarification-Tests abgedeckt | **ERFÜLLT** |
| §37 Abschlusslogik | CI grün, keine offene P0/P1; externer Blind Review zulässig, aber #1-Human-Time-Metriken noch nicht gemessen | **NOCH NICHT ABSCHLIESSEN** |

### Finales technisches Post-Hardening-Aggregat vor Human-Time

- Records: **17** insgesamt
- Scored autonome Fälle: **8/8**
- Frische manuelle Baselines: **4/4**
- Lineare Post-Fix-Runs: **5**
- Post-Hardening-Fälle: **AP4-04, AP4-05, AP4-08**
- Manuelle Feldpflege: **91,58 % Reduktion – PASS**
- Vermeidbare Rückfragen: **Median 0 – PASS**
- Provenance: **100 % – PASS**
- Halluzinationen: **0 – PASS**
- Cross-Domain-Konsistenz: **alle 8 aktuellen Fallstände PASS**
- Fachlich erwarteter Endzustand: **alle 8 aktuellen Fallstände PASS**
- Aktive Human Work: **offen / nicht gemessen**
- Menschliche Nacharbeit: **offen / nicht gemessen**
- Blind Human Review: **offen / externe Abhängigkeit**

Damit sind vor der Human-Time-Messung **keine bekannte Produktlücke, kein technischer Hardening-Gap und kein Plan↔Issue-Widerspruch** mehr offen. Nicht erfüllt sind ausschließlich die bewusst menschlichen #1-Nachweise.
## Technische Post-Fix-Abnahme — 2026-10-01

Prüfbasis: `d48401148d67d242b668ae21ea6af4a0f440410b`, Fix-Commits `64541bd` und `d484011`, CI #665 / `36848836450` nachweislich vollständig grün. Zwei reproduzierbare Restfehler wurden im Rahmen dieser Abnahme korrigiert; für den neuen Code-Head ist erneut vollständige CI erforderlich.

| Finding | Produktionsfix / Regression | Ergebnis |
|---|---|---|
| HT-F01, HT-F04 | `source-upload-staging.js`: additive FileList, sichtbare Dateinamen, Entfernen; `test_source_upload_staging.py`, `test_issue_80_source_upload.py`, Discovery-Tests und isolierter Edge-Browservertrag | PASS |
| HT-F02 | Discovery nutzt `data-submit-guard`, Spinner, Live-Status und Mehrfachsubmit-Sperre; Discovery-/Loading-Regressionen | PASS |
| HT-F03 | `pending_execution_state()` und `build_activity()`; verbleibende irreführende Überschriften korrigiert; `test_issue_75_activity.py`, einschließlich Assignment-/Lease-Grenzen und Generation | PASS |
| HT-F05, HT-F06 | fokussierte Fehlerzusammenfassung, Feldlinks, gebundene Eingaben und kein Decision-Write bei ungültigem Submit; `test_solution_selection_ux.py` | PASS |
| HT-F07 | Claim → reviewed Brief-Hypothese → bestehende Ursachenhypothese; Vorschlag bleibt unbestätigt, menschlicher Submit erforderlich; Solution-UX-Regressionen | PASS |
| HT-F08 | Busy-State bewahrt jetzt den geklickten Aktionswert vor Disabled/native Submit; `test_submit_guard_runtime.py`, Edge Vorher-/Nachher-Reproduktion | PASS |
| HT-F09 | nach AI-Auswahl Fortsetzung als einzige Primary Action, Auswahländerung sekundär; Solution-UX-Regressionen | PASS |

### HT-F03 Ausführungsvertrag

- `pending`: neues Assignment bis einschließlich 30 Sekunden (`LEASE_SECONDS=30`); keine Überschrift behauptet laufende Analyse.
- `queued`: älteres unclaimed Assignment, während mindestens `MAX_EXECUTIONS=2` aktuelle produktive Runs mit passender Generation und nicht abgelaufener Lease die Kapazität belegen; UI nennt das Warten auf einen freien Platz.
- `confirmed`: nur RUNNING mit passender Execution-/Executor-Generation, Worker-ID und Lease strikt nach `now`; nur hier „Untersuchung läuft“ / „läuft im Hintergrund“.
- `unavailable`: Assignment älter als 30 Sekunden und weniger als zwei bestätigte aktive Produkt-Runs; UI erklärt die nicht übernommene Ausführung, technischen Dienst prüfen/starten, Abbruch und keinen Blind-Restart. Sie behauptet nicht, dass definitiv kein Worker-Prozess existiert.
- Abgelaufene oder fremde Generation bestätigt keine Analyse. Bereits beanspruchte Runs mit abgelaufener Lease werden `unconfirmed`, bis die bestehende Worker-Cleanup-Logik greift. Keine neue Statusmaschine, Queue oder Architektur.

### Gezielte E2E-Konsistenz

115 relevante Django-/statische Regressionen bestanden (Activity, Solution UX, Loading Feedback, Source Upload/Staging, Discovery, AP4 Evidence und Solution Comparison); zusätzlich 1 ausführbarer JS-Submit-Guard-Test bestanden. Die Tests prüfen Start/Dispatch, menschliche Confirmation, valide/invalid gespeicherte Auswahl, AI-Fortsetzung sowie Bindung des Handoffs an die unveränderte menschliche Auswahl.

Der isolierte Edge-Browser prüfte die tatsächliche Formserialisierung: ursprünglicher Guard verlor die Fortsetzungsaktion, korrigierter Guard überträgt genau `continue_ai_handoff=1` trotz deaktiviertem Button und unvollständigen Feldern der optionalen Auswahländerung. Additives Staging, Dateinamen und Entfernen ebenfalls PASS. Keine neue fachliche Bewertung der acht Fälle und kein neuer Providerlauf. Bestehende AP4-05-PF3-/AP4-08-Authority-Evidence und Downstream-Guards bleiben die Grundlage; vollständige CI prüft zusätzlich die bestehende Härtungsmatrix.

### Historische Human-Time und Abschlussentscheidung

- AP4-01 bis AP4-03: technische Fehlversuche.
- AP4-04: vom Menschen wegen UX-Findings gestoppt, kein finaler reviewfähiger Messabschluss.
- AP4-05 bis AP4-08: nicht gestartet.
- Die vier `AP4-0[1-4]-human-time.json` bleiben byte-identisch. Null-Werte bleiben unbekannt; fehlende Segmente werden weder geschätzt noch zu Null erklärt.
- Human-Time ≤15–20 Minuten und Human-Rework ≤20 %: **nicht quantitativ nachgewiesen / Validation Gap**, niemals PASS. Die technische Zielerreichung ersetzt keinen Produktivitätsnachweis.
- Blind Human Review: **nicht durchgeführt und für diesen Abschlussweg bewusst ausgeschlossen**, kein PASS und kein Ersatz durch LLM-/Technical-Review.
- Separates vollständiges Produkt-Playthrough: späterer eigener Arbeitsschritt, hier nicht durchgeführt und kein Voraussetzungstest dieser technischen Abnahme.

**#107 technisch closure-ready: YES, sofern die vollständige CI auf dem neuen Fix-Head grün ist und die beiden Zeitmetriken als akzeptierte Validation Gap sowie Blind Review als bewusst ausgeschlossener Nachweis im Abschluss dokumentiert werden.** Das ist kein vollständiger quantitativer #1-Nachweis.

Issue #107 enthält weiterhin die historischen operativen Formulierungen unter „Aktueller Reconciliation-Stand vor Human-Time“ (Blind Review/Gesamtergebnis offen), „AP4.8 – Blind Review“, Arbeitsreihenfolge Schritt 7 und die nicht abgehakten Kriterien „Blind Review mindestens gleichwertig“ / „Blind-Review-Evidence dokumentiert“. PR #108 beschreibt im Draft-Text ebenfalls noch Blind Review als Abschlussvoraussetzung. Für den vereinbarten Abschlussweg lautet die sachliche Reconciliation: „Nicht durchgeführt; bewusst ausgeschlossen für diesen technischen Abschluss; Qualitätsnachweis bleibt unerfüllt.“ Checkboxen werden nicht als PASS erfunden. Die historischen Anforderungen bleiben nachvollziehbar; dieser Bericht dokumentiert die bewusst gewählte Abweichung.

## Finaler AP4-Abschlussstand nach Merge

- PR #108 wurde mit finalem Head `5e4bc7a32d254de028d819b121702a1a56ed2a0e` gemergt.
- Merge-Commit auf `main`: `55b3fba41e6bd60e95a78400e701cdef627a4ed6`.
- Issue #107 ist als `completed` geschlossen.
- CI #666 / `36859490252` auf dem finalen PR-Head ist vollständig grün (1.888 Tests plus übrige Checks).
- AP4 ist **technisch abgeschlossen mit transparent akzeptierten Validation Gaps**.
- Active Human Work ≤ 15–20 Minuten und Human Rework ≤ 20 % bleiben **nicht quantitativ nachgewiesen**.
- Blind Human Review wurde **nicht durchgeführt und für diesen Abschlussweg bewusst ausgeschlossen**; kein PASS.
- Damit liegt ausdrücklich **kein vollständiger quantitativer #1-Nachweis** vor.
- Das separate vollständige Produkt-Playthrough bleibt ein späterer eigener Qualitätsschritt und ist kein rückwirkender AP4-Blocker.

Arbeitsplan und eingefrorener Messvertrag wurden während AP4 nicht verändert; die Post-AP4-Planaktualisierung erfolgt erst nach dem Merge auf Basis dieses realen Abschlussstands.
