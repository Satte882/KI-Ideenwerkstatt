# AP4 Realabnahme – Issue #107

Stand: 2026-10-01

Scored Code-Stand: `1a3f02adc5e7850dd643044598e303350bf9a1c3`

Branch: `feature/issue-107-ap4-evidence`

## Population und Methode

- Vier frische geführte Referenzpfade wurden für AP4-01 bis AP4-04 gegen exakt dieselben eingefrorenen Problemstellungen und Source Packs erfasst.
- Acht autonome scored Slots wurden jeweils genau einmal mit einem echten OpenRouter-Provider ausgeführt. Kein scored Failure wurde wiederholt oder ersetzt.
- Die Providerläufe nutzten Discovery mit `google/gemini-3.6-flash`; nachgelagerte AP2-Schritte nutzten die konfigurierte reale Providerstrecke. Mocks waren nicht aktiv.
- Die geführten Baselines und die scripted Acceptance-Operator-Aktionen sind keine unabhängige Human Review. Nicht gemessene menschliche Zeit wird im Evidence-Aggregator jetzt ausdrücklich als **offen** behandelt und nicht mehr als numerische `0` gewertet. Die Blind Human Review bleibt ausdrücklich offen.

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

\* Nur tatsächlich gemessene aktive menschliche Zeit wird gezählt. Scripted Acceptance-Operator-Aktionen werden nicht in erfundene Zeitwerte umgerechnet. Diese beiden Zeitmetriken bleiben deshalb ausdrücklich **offen** und erzeugen keinen PASS, bis echte menschliche Zeit vorliegt.

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
- Tatsächliche aktive Human Work und menschliche Nacharbeit bleiben mangels menschlicher Teilnahme offen; es wurden keine Zeiten geschätzt.

## Plan ↔ Issue Reconciliation vor Human-Time

Der führende Arbeitsplan bleibt während AP4 unverändert. Issue #107 konkretisiert ihn; dieser Abschnitt prüft nur, ob Issue, Evidence und realer Iststand deckungsgleich sind.

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
## Verbleibende offene Punkte

- Aktive Human Work und menschliche Nacharbeit sind noch nicht mit echter menschlicher Teilnahme gemessen.
- Unabhängige Blind Human Review der neutralisierten Decision Packages ist nicht erfolgt und kann nicht durch diese technische/LLM-gestützte Abnahme ersetzt werden.
- AP4-05 ist mit dem linearen Real-Provider-Nachweis `PF3` abgeschlossen; kein weiterer AP4-05-Lauf ist erforderlich.
- Der AP4-08-Produkt-/Domainpfad ist geschlossen und im Post-Hardening-Aggregat als PASS abgebildet.
- Bis Human-Time-Messung und finaler Abschlussreview erfolgt sind, bleibt Issue #107 offen und PR #108 Draft/unmerged.
