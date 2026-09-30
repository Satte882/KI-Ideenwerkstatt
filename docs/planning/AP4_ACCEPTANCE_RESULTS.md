# AP4 Realabnahme – Issue #107

Stand: 2026-09-30

Scored Code-Stand: `1a3f02adc5e7850dd643044598e303350bf9a1c3`

Branch: `feature/issue-107-ap4-evidence`

## Population und Methode

- Vier frische geführte Referenzpfade wurden für AP4-01 bis AP4-04 gegen exakt dieselben eingefrorenen Problemstellungen und Source Packs erfasst.
- Acht autonome scored Slots wurden jeweils genau einmal mit einem echten OpenRouter-Provider ausgeführt. Kein scored Failure wurde wiederholt oder ersetzt.
- Die Providerläufe nutzten Discovery mit `google/gemini-3.6-flash`; nachgelagerte AP2-Schritte nutzten die konfigurierte reale Providerstrecke. Mocks waren nicht aktiv.
- Die geführten Baselines und die scripted Acceptance-Operator-Aktionen sind keine unabhängige Human Review. Nicht gemessene menschliche Zeit wurde als `0`, nicht als Schätzwert, erfasst. Die Blind Human Review bleibt deshalb ausdrücklich offen.

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
| AP4-08 | `waiting_human` in Governance | FAIL – Investigation und Berechnungen korrekt, aber der Acceptance-Runner wählte entgegen seiner eigenen organisatorischen Empfehlung Analytics/ML; Cross-Domain-State dadurch inkonsistent |

Die AP4-08-Gruppenrechnung ist reproduzierbar: `parts_available=false` 12,00 h (n=4), `true` 4,75 h (n=4), Differenz 7,25 h. Der Brief behauptet daraus keine Kausalität. Der Fehler liegt in der nachfolgenden Test-Authority-Auswahl, nicht in dieser Berechnung.

## Gefundene Bugs und gezielte Fixes

1. Historische Investigation-Provenance war nach Verlassen von `DRAFT` nicht mehr lesbar, weil der Read-Pfad den Edit-Guard nutzte. Der Read-Guard prüft nun weiterhin Actor, Ownership, aktiven Quellenraum und Snapshot-Zuordnung, aber nicht den Edit-Status. Schreiboperationen bleiben gesperrt. Browser und Regressionstest bestätigen das Verhalten.
2. Planner `v18` verwechselte fehlende fertige Lösungsvorschläge mit fehlender Entscheidungsevidenz (AP4-04). Planner `v19` fordert jetzt hypothesenbasierte Optionen aus ausreichender Problem-/Scope-Evidenz und verbietet diese vermeidbare Rückfrage. Der reale Post-Fix-Run erreicht `READY` mit Regel-, Hybrid-, GenAI- und Status-quo-Optionen; die Auswahl bleibt menschlich.
3. Planner `v18` synthetisierte trotz ausdrücklich offener Entscheidungshoheit/Ausnahmeverantwortung (AP4-05). Planner `v19` bindet diese Grenze an `permission_or_scope`. Prompt-Vertragstests sind grün. Der reale Post-Fix-Versuch scheiterte bereits in Discovery mit `user_quota_exceeded`; er wurde nicht wiederholt und bleibt als Evidence erhalten.
4. Der AP4-Evidence-Vertrag konnte nach einer legitimen Prompt-Härtung keine historischen Records mehr auswerten. Post-Fix-Records binden nun die tatsächlich verwendeten aktuellen Vertragsversionen, während neue scored Records weiterhin strikt gegen den eingefrorenen Vertrag geprüft werden.

## Post-Hardening

- AP4-04: PASS im separaten echten Providerlauf; Browser zeigt den Decision Brief, vier Optionen und das unveränderte menschliche Solution-Gate.
- AP4-05: OPEN/FAIL im separaten Providerlauf wegen `user_quota_exceeded`; kein Retry, keine Ersetzung.
- AP4-08: unverändert FAIL; kein Produktfix aus einem Fehler der Test-Authority abgeleitet.

## Kennzahlen

| Kriterium | Initial scored | Post-Hardening | Ziel |
|---|---:|---:|---:|
| aktive Human Work, Median | 0 s* | 0 s* | ≤ 1.200 s |
| Reduktion manueller Feldpflege | 91,58 % | 91,58 % | ≥ 90 % |
| vermeidbare Rückfragen, Median | 0 | 0 | ≤ 3 |
| Provenance | 98,55 % | 100 % | 100 % |
| halluzinierte Fakten/Messwerte | 0 | 0 | 0 |
| Cross-Domain-Konsistenz, alle Fälle | FAIL | FAIL | alle PASS |
| erwarteter Endzustand, alle Fälle | FAIL | FAIL | alle PASS |
| menschliche Nacharbeit / Baseline | 0 %* | 0 %* | ≤ 20 % |

\* Nur tatsächlich gemessene aktive menschliche Zeit wird gezählt. Scripted Acceptance-Operator-Aktionen und die noch ausstehende Blind Human Review wurden nicht in erfundene Zeitwerte umgerechnet. Diese beiden Zeitmetriken sind deshalb technisch innerhalb des Grenzwerts, aber noch keine vollständige Human-Validierung.

## Browser- und Domain-State-Evidence

- Alle acht Discovery-Seiten, alle acht gespeicherten Investigation-Zustände und alle acht Solution-Vergleiche antworteten im echten Chrome mit HTTP 200 und ohne horizontalen Overflow.
- AP4-03 und AP4-08 zeigten zusätzlich die gespeicherten AP2-Entscheidungs-/Governance-Oberflächen.
- AP4-01s menschliches Solution-Gate wurde im Browser gespeichert und endete korrekt im organisatorischen Non-AI-Zweig.
- Nach dem Read-Guard-Fix bleiben terminale Decision Briefs lesbar; Schreibzugriffe sind per Test weiterhin untersagt.
- AP4-04 Post-Fix zeigt im Browser alle vier materialisierten Kandidaten sowie das menschliche Diagnose-/Solution-Gate.
- Strukturierte States: `artifacts/ap4/browser-state.json` und `artifacts/ap4/browser-state-post-fix.json`; Screenshots liegen unter `artifacts/ap4/browser/`.

## Verbleibende offene Punkte

- Unabhängige Blind Human Review der neutralisierten Decision Packages ist nicht erfolgt und kann nicht durch diese technische/LLM-gestützte Abnahme ersetzt werden.
- AP4-05 benötigt nach verfügbarem Providerkontingent einen linear anschließenden, nicht den Failure ersetzenden Post-Fix-Run.
- AP4-08 benötigt eine neue, ausdrücklich menschliche Authority-Entscheidung in einem separaten Folgepfad; der scored Failure bleibt unverändert.
- Wegen der offenen Qualitätskriterien ist Issue #107 nicht abnahmefähig zu schließen. PR #108 bleibt Draft und wird nicht gemergt.
