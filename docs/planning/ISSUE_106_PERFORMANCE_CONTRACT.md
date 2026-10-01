# Issue #106 – AP0 Performance Measurement & Quality Contract

Issue: #110  
Parent: #106  
Contract: `tests/fixtures/issue106_performance_contract_v1.json`  
Frozen pre-AP0 reference: `1f0e3c331d3cd2bef2ce9872af59fc002391f46f`

## 1. Zweck

Dieser Vertrag friert **vor der ersten #106-Performanceänderung** Messgrenze, Golden Set, Bewertungsautorität, Experimentbudget und Übernahmeregeln ein.

AP0 optimiert die Investigation **nicht**. Es entsteht keine zweite Telemetrie-, Workflow- oder Benchmarkplattform.

Die vorhandenen Investigation- und AP4-Bausteine werden wiederverwendet:

- `diagnose_investigation_run --json` für Call-/Rollen-/Token-/Runtime-Diagnose;
- `tests/fixtures/ap4_case_manifest_v1.json` als bestehende Fall- und Source-Pack-Freeze;
- `tests/fixtures/ap4_source_packs/` als unveränderte Eingaben;
- `tests/fixtures/ap4_hardening_evidence_v1.json` für bereits deterministisch abgedeckte Recovery-/Failure-Invarianten.

AP1 darf minimale Diagnose-/Exportlücken schließen, muss dafür aber keine neue Benchmarkarchitektur bauen.

## 2. Messgrenze

Primär gemessen wird die **Investigation bis zum fachlich korrekten Endzustand**:

- `ready`,
- `waiting_human`,
- oder fachlich korrektes `failed`.

Bei `waiting_human` wird aktive System-/Investigation-Laufzeit getrennt von menschlicher Wartezeit ausgewiesen. Menschliche Wartezeit ist keine Runtime-Latenz.

Zusätzlich bleibt ein begrenzter Discovery→Delivery-Regressionscheck bestehen. #106 wiederholt nicht AP4 als Vollabnahme.

Historische #86-/AP4-Läufe dürfen nur als aktuelle Baseline verwendet werden, wenn Codepfad **und** Execution Contract nachweislich vergleichbar sind. Sonst sind sie Referenz oder wiederverwendbare Eingaben.

## 3. Eingefrorener Investigation-Vertrag

Der JSON-Vertrag bindet den Ausgangsstand an:

- Planner `vs1-planner-v19` / Schema `vs1-planner-schema-v16`;
- Synthesizer `vs1-synthesis-v15` / Schema `vs1-synthesis-schema-v5`;
- Verifier `vs1-verifier-v7` / Schema `vs1-verifier-schema-v5`;
- Loop `vs1-agent-loop-v19`;
- Budget `vs1-budget-v7`;
- Transport `vs1-openrouter-deepinfra-fp8-v4`;
- Modell `deepseek/deepseek-v4.1-flash`;
- Provider `deepinfra/fp8`, keine Fallbacks;
- Default Reasoning `medium`; fokussierter Pre-Verifier-Repair `low`;
- Rollenlimits 90s/16k Planner, 270s/32k Synthesizer, 120s/16k Verifier.

Eine spätere Änderung dieser Werte ist ein Experiment und benötigt eigenen Contract-/Rollback-Nachweis.

## 4. Golden Set

Es werden fünf bestehende AP4-Source-Packs wiederverwendet. Die Schlüsselfunde werden **aus den eingefrorenen Quellen** abgeleitet, nicht aus früheren Modellantworten.

| Fall | Zweck | zulässiger Investigation-Endzustand |
|---|---|---|
| AP4-01 | einfacher Textfall / organisatorische Non-AI-Ursache | READY |
| AP4-02 | deterministische Regeln + CSV | READY |
| AP4-04 | Hybrid aus deterministischer Prüfung und begrenzter Semantik | READY |
| AP4-05 | fehlende Entscheidungshoheit | WAITING_HUMAN |
| AP4-06 | widersprüchliche freigegebene Evidenz | READY oder präzises WAITING_HUMAN |

Die exakten erwarteten Schlüsselfunde, notwendigen Gegenbelege und fallbezogenen Hard Fails stehen im JSON-Manifest.

## 5. Bewertungsautorität

Der zu optimierende Verifier darf nicht allein seine eigene Qualität bestätigen.

Referenz:

1. deterministische Checks auf **allen** Runs;
2. vorab definierte Fallkriterien aus dem Golden Set;
3. begrenzte menschliche Prüfung.

Menschliche Prüfung umfasst mindestens einen Run je Fall und verglichener Variante sowie alle Hard-Fail-Verdachtsfälle und Bewertungsdifferenzen.

Ein zusätzlicher LLM-Judge ist nur unterstützend.

### Nicht kompensierbare Hard Fails

Ein kritischer Fehler kann nicht durch bessere Durchschnittswerte ausgeglichen werden. Insbesondere:

- erfundene Fakten, Messwerte, Systeme oder Authority-Entscheidungen;
- Verlust notwendiger Gegenbelege;
- ungeprüfte kritische Claims;
- verdeckte Unknowns;
- falsche READY-/WAITING_HUMAN-Semantik;
- Umgehung menschlicher Freigabe-/Risikoautorität;
- gebrochene Provenance, Replay-, Recovery- oder Idempotenz-Invarianten.

## 6. A/A vor A/B

AP1 führt dieselbe unveränderte Baseline pro Golden-Set-Fall **fünfmal** aus.

Damit entsteht ein Noise Floor für:

- Laufzeit;
- Planner-/Synthesizer-/Verifier-Calls;
- Repairs / Retries;
- Kosten;
- Qualitätsstreuung.

Bei kleiner Population werden Rohwerte, Median, Min/Max und Fehler-/Retry-Anteil berichtet. p95 wird nur bei dafür hinreichender Population verwendet.

Provider-/Prompt-Cache-Metadaten werden erfasst, soweit der Provider sie liefert. Nicht beobachtbare Cache- oder interne Queueing-Effekte bleiben ausdrücklich unbekannt.

## 7. Experimentbudget

### AP1 Baseline

- 5 Fälle × 5 Wiederholungen = maximal **25 reale Provider-Runs**;
- Providerkosten-Cap: **20 USD**;
- menschliche Qualitätsprüfung: maximal **360 Minuten**.

### Je ausgewähltem Experiment-Gate

- maximal **25 reale Provider-Runs**;
- Providerkosten-Cap: **20 USD**;
- maximal **40 Engineering-Stunden**, bevor ein neues Gate nötig ist.

### Finaler Re-Benchmark

- erneut 5 Wiederholungen je Fall;
- Providerkosten-Cap: **20 USD**.

Ohne Änderung im Parent #106 gilt damit ein kumuliertes Providerbudget von **60 USD** für Baseline + ein ausgewähltes Experiment + finalen Re-Benchmark. Ein weiteres Experiment benötigt vor dem ersten Providerlauf eine dokumentierte Budgeterweiterung in #106.

Fehlgeschlagene, langsame und abgebrochene Runs bleiben im Datensatz. Ersatzläufe überschreiben sie nicht und benötigen Begründung + Verknüpfung.

Nach Budgetende lautet das Ergebnis: **übernehmen, verwerfen oder nicht ausreichend belegt**. Keine offene Kalibrierungsschleife.

## 8. Vorab definierte Übernahmehürden

Diese Schwellen sind **operative Entscheidungsgates**, keine Behauptung statistischer Signifikanz. Eine Verbesserung muss zusätzlich den gemessenen A/A-Noise-Floor überschreiten.

### Reversible Änderung ohne Contract-Wechsel

Mindestens eines:

- ≥ 5 % Median-Laufzeitreduktion auf betroffenen Fällen;
- oder ≥ 10 s Median-Laufzeitreduktion;
- oder mindestens ein redundanter Model Call weniger je betroffenem Run.

Providerkosten dürfen höchstens 5 % steigen.

### Contract- oder Modelländerung

Mindestens eines:

- ≥ 10 % **und** ≥ 30 s Median-Laufzeitreduktion;
- oder ≥ 20 % Providerkostenreduktion bei höchstens 5 % schlechterer Laufzeit;
- oder ≥ 25 Prozentpunkte weniger Timeout-/Retry-/Repair-Rate.

### Batching oder Concurrency

Höhere Hürde wegen zusätzlicher Recovery-/Persistenzkomplexität. Mindestens eines:

- ≥ 15 % **und** ≥ 45 s Median-Laufzeitreduktion;
- oder ≥ 25 Prozentpunkte weniger Timeout-/Retry-/Repair-Rate.

Zusätzlich:

- keine Zunahme unnötiger Evidence-Actions;
- teilweise Ausführung bleibt recoverbar und idempotent.

Alle Klassen müssen die Qualitäts-Hard-Fails bestehen.

## 9. Bestehende Messstrecke und bekannte Lücken

### Bereits ausreichend vorhanden

`diagnose_investigation_run --json` liefert heute insbesondere:

- Run- und Modellzeit;
- Rollen-/Call-Dauer;
- Prompt-/Completion-/Reasoning-Tokens;
- Context-Profil/-Größe;
- Syntheseauslöser;
- Tool-Schritte;
- Duplicate Reads;
- Policy-/Pre-Verifier-Kontext.

### AP1 darf minimal ergänzen

Noch nicht als einheitlicher Performance-Record vorhanden bzw. nicht vollständig beobachtbar:

- normalisierte Providerkosten im Investigation-Diagnoseexport;
- Experiment-ID / Variante / exakter getesteter Commit im Export;
- interne Provider-Queue vs. Inference ist nicht direkt beobachtbar;
- Cache-Metadaten nur, soweit Provider sie liefert.

AP1 darf genau diese Messlücken schließen. Das ist Instrumentierung, keine Performance-Optimierung.

## 10. Exit AP0

AP0 ist abgeschlossen, wenn:

- dieses Dokument und das JSON-Manifest versioniert sind;
- Contract-Tests Golden Set und aktuellen Investigation-Vertrag prüfen;
- #106/#110 als verbindlicher Auftrag in den Repo-Arbeitsregeln abgebildet sind;
- Fallmanifest, Rubrik, Bewertungsautorität und Experimentbudget eingefroren sind;
- bekannte Messlücken für AP1 explizit sind.

Danach beginnt #111 mit Baseline/A/A.
