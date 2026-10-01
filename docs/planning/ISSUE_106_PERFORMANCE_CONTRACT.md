# Issue #106 – AP0 Performance Measurement & Quality Contract

Issue: #110  
Parent: #106  
Contract: `tests/fixtures/issue106_performance_contract_v1.json`  
Frozen pre-AP0 reference: `1f0e3c331d3cd2bef2ce9872af59fc002391f46f`

## 1. Zweck

Dieser Vertrag friert **vor der ersten #106-Performanceänderung** Messgrenze, Golden Set,
Bewertungsautorität, Vergleichsregeln, Experimentbudget und Übernahmehürden ein.

AP0 optimiert die Investigation **nicht**. Es entsteht keine zweite Telemetrie-, Workflow-
oder Benchmarkplattform.

Wiederverwendet werden:

- `diagnose_investigation_run --json` für Call-/Rollen-/Token-/Runtime-Diagnose;
- `tests/fixtures/ap4_case_manifest_v1.json` als bestehende Fall- und Source-Pack-Freeze;
- `tests/fixtures/ap4_source_packs/` als unveränderte Eingaben;
- `tests/fixtures/ap4_hardening_evidence_v1.json` für bereits deterministisch abgedeckte
  Recovery-/Failure-Invarianten.

AP1 darf minimale Diagnose-/Exportlücken schließen. Das ist Instrumentierung, keine
Performance-Optimierung.

## 2. Messgrenze

Primär gemessen wird die **Investigation bis zum fachlich korrekten Endzustand**:

- `ready`;
- `waiting_human`;
- oder fachlich korrektes `failed`.

Bei `waiting_human` werden aktive System-/Investigation-Laufzeit und menschliche Wartezeit
getrennt ausgewiesen. Menschliche Wartezeit ist keine Runtime-Latenz.

Zusätzlich gibt es im finalen Gate genau zwei begrenzte Discovery→Delivery-Regressionsläufe:
AP4-01 und AP4-04, je ein Lauf. Sie gehören zum finalen Providerkosten-Cap, aber nicht zur
primären Investigation-A/B-Population.

Historische #86-/AP4-Läufe dürfen nur als aktuelle Baseline verwendet werden, wenn Codepfad
**und** Execution Contract nachweislich vergleichbar sind. Sonst sind sie Referenz oder
wiederverwendbare Eingaben.

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
- Default Reasoning `medium`;
- Synthesizer im `pre_verifier_repair`: `low`;
- Rollenlimits 90s/16k Planner, 270s/32k Synthesizer, 120s/16k Verifier.

Zusätzlich wird der Git-Blob des Prompt-Moduls eingefroren. Damit wird auch eine
Promptänderung ohne Versions-Bump als Contract-Drift sichtbar.

Eine spätere Änderung dieser Werte ist ein Experiment und benötigt einen eigenen
Contract-/Rollback-Nachweis.

## 4. Golden Set und Quellenbindung

Es werden fünf bestehende AP4-Source-Packs wiederverwendet:

| Fall | Zweck | zulässiger Endzustand |
|---|---|---|
| AP4-01 | einfacher Textfall / organisatorische Non-AI-Ursache | READY |
| AP4-02 | deterministische Regeln + CSV | READY |
| AP4-04 | Hybrid aus deterministischer Prüfung und begrenzter Semantik | READY |
| AP4-05 | fehlende Entscheidungshoheit | WAITING_HUMAN |
| AP4-06 | widersprüchliche freigegebene Evidenz | READY oder präzises WAITING_HUMAN |

Jeder erwartete Schlüsselfund und jeder notwendige Gegenbeleg besitzt im JSON-Manifest
mindestens einen `source_ref` aus:

- relativer Quelldatei;
- wörtlichem Locator, der in der eingefrorenen Quelle vorkommt.

Die Source-Packs werden zusätzlich über die bereits aus AP4-Evidence bekannten Content-Hashes
gebunden. Damit reicht ein unveränderter Dateiname nicht aus.

AP4-06 darf fachlich READY oder WAITING_HUMAN erreichen. Seine Laufzeit wird deshalb im
Vergleich zusätzlich nach Endzustand getrennt berichtet und nicht blind zu einer einzigen
Population vermischt.

## 5. Bewertungsvertrag

### 5.1 Deterministische Checks

Auf **jedem** Run werden mindestens geprüft:

1. Execution Contract entspricht Baseline oder explizitem Experimentvertrag;
2. Source-Pack-Hash entspricht dem eingefrorenen Fall;
3. Endzustand ist für den Fall zulässig;
4. source-derived Claims besitzen auflösbare Provenance;
5. Halluzinationszähler bleibt null;
6. bestehende Recovery-/Idempotenz-/Human-Authority-Regressions bleiben grün.

### 5.2 Semantische Rubrik

Jeder Run erhält für die nicht rein deterministischen Kriterien explizit
`PASS`, `FAIL` oder `UNASSESSED`.

Bewertet werden:

- alle erwarteten Schlüsselfunde;
- alle notwendigen Gegenbelege;
- Trennung von Facts / Hypothesen / Unknowns;
- Solution Openness;
- interne Konsistenz des Decision Brief;
- Erhalt der Human Authority.

Für eine Adoption müssen **alle Runs autoritativ bewertet** sein. Ein verbleibendes
`UNASSESSED` blockiert die Adoption und führt bei ausgeschöpftem Budget zu
`not_sufficiently_proven`.

### 5.3 Bewertungsautorität

Der zu optimierende Verifier darf nicht allein seine eigene Qualität bestätigen.

Referenz:

1. deterministische Checks;
2. eingefrorene Fallkriterien;
3. menschliche Bewertung der verbleibenden semantischen Kriterien.

Ein LLM-Judge darf nur vorannotieren oder auf mögliche Abweichungen hinweisen. Die
abschließende Bewertung nicht-deterministischer Kriterien bleibt menschlich.

Damit gibt es keine Auswahl eines „schönen“ Einzelruns für die Qualitätsfreigabe: bei
Adoption werden alle Runs der Vergleichspopulation bewertet.

### 5.4 Nicht kompensierbare Hard Fails

Ein kritischer Fehler kann nicht durch bessere Durchschnittswerte ausgeglichen werden.
Insbesondere:

- erfundene Fakten, Messwerte, Systeme oder Authority-Entscheidungen;
- Verlust notwendiger Gegenbelege;
- ungeprüfte kritische Claims;
- verdeckte Unknowns;
- falsche READY-/WAITING_HUMAN-Semantik;
- Umgehung menschlicher Freigabe-/Risikoautorität;
- gebrochene Provenance, Replay-, Recovery- oder Idempotenz-Invarianten.

Ein beobachteter und menschlich bestätigter Hard Fail stoppt weitere Variantenläufe dieses
Gates. Der Run bleibt Evidence; danach wird verworfen, repariert und neu gegatet oder als
nicht ausreichend belegt abgeschlossen. „Null Hard Fails“ ist ein **Observed-Sample-Gate**,
keine Behauptung einer populationsweiten Null-Fehlerrate.

## 6. Verifier-Kontrollvertrag

Vor einem Experiment, das Verifier-Contract oder Verifier-Modell verändert, muss ein
versionierter Kontrollsatz materialisiert sein.

Mindestens enthalten:

- bekannt korrektes Package → erwartet: Accept;
- Halluzinationsmutation → Reject oder kritisches Finding;
- fehlender Gegenbeleg → Reject oder kritisches Finding;
- Human-Authority-Bypass → Reject oder kritisches Finding;
- gebrochene Provenance → Reject oder kritisches Finding.

Der zu testende Verifier darf seine Kontrolllabels nicht selbst erzeugen. Die erwarteten
Labels werden vor dem Experiment festgelegt und menschlich kalibriert.

AP0 friert diesen Prüfvertrag ein; die konkrete Fixture wird erst angelegt, wenn #112 ein
Verifier-Experiment auswählt.

## 7. A/A-Noise-Floor und Vergleichspopulation

AP1 führt dieselbe unveränderte Baseline pro Golden-Set-Fall **fünfmal** aus.

Pro Fall werden mindestens berichtet:

- Median aktive Runtime;
- Median Absolute Deviation (MAD);
- Min/Max;
- Calls / Repairs / Retries;
- Kosten;
- Qualität.

Der operative Runtime-Noise-Floor je Fall ist:

```text
2 × MAD der fünf AP1-Baseline-Runs
```

Dies ist **kein Konfidenzintervall und kein Signifikanztest**, sondern ein vorab definierter
Engineering-Noise-Floor.

Vor dem ersten Variantenlauf muss das Experiment-Issue die fachlich betroffenen Fälle
deklarieren. Diese Auswahl darf danach nicht anhand der Resultate verändert werden.
Unabhängig davon werden **alle fünf Golden-Set-Fälle** berichtet.

Primäre Effektberechnung:

```text
case_effect_seconds
= AP1-Baseline-Median des Falls
- Varianten-Median des Falls

aggregate_effect_seconds
= Median der case_effect_seconds
  über die vorab deklarierten betroffenen Fälle

aggregate_noise_floor_seconds
= Median der fallbezogenen 2×MAD-Noise-Floors
  derselben vorab deklarierten Fälle
```

Eine Runtime-Verbesserung kann nur als belegt gelten, wenn:

1. sie die jeweilige klassenspezifische Mindesthürde erfüllt; **und**
2. `aggregate_effect_seconds > aggregate_noise_floor_seconds`.

Ist die Baseline zu verrauscht, lautet das Ergebnis `not_sufficiently_proven`.

Bei kleiner Population werden keine p95- oder Signifikanzbehauptungen abgeleitet.

## 8. Event-Raten

Timeout-, Retry- und Repair-Raten verwenden denselben Nenner:

> alle gestarteten Runs im jeweiligen Vergleichsarm, einschließlich FAILED und ABORTED.

Definitionen:

- Timeout-Rate: Anteil Runs mit mindestens einem Timeout;
- Retry-Rate: Anteil Runs mit mindestens einem Provider- oder Contract-Retry;
- Repair-Rate: Anteil Runs mit mindestens einem Pre-Verifier- oder Verifier-Repair.

Wenn die Baseline einer Rate unter 25 Prozentpunkten liegt, kann die
„−25 Prozentpunkte“-Nutzenhürde für diese Rate naturgemäß nicht als positiver Hebel verwendet
werden. Das ändert nicht die übrigen Gates.

## 9. Zeitnahe Kontrollen gegen Provider-Drift

Ein Experiment-Gate bleibt bei maximal 25 primären Investigation-Runs:

- je Fall 4 Variantenläufe;
- je Fall 1 zeitnaher Baseline-Kontrolllauf.

Die Startreihenfolge von Variante und Kontrolle wird über die Fälle alterniert.

Der Kontrolllauf ersetzt den AP1-Noise-Floor nicht. Er ist ein Drift-Sentinel. Weicht der
zeitnahe Baseline-Kontrolllauf bei **mindestens zwei der fünf Fälle** um mehr als den
fallbezogenen Noise-Floor vom AP1-Median ab, ist der Vergleich
`not_sufficiently_proven`. Ein neuer Lauf ist nur innerhalb des verbleibenden Budgets
zulässig.

Im finalen Benchmark werden je Fall 3 Läufe der übernommenen Variante und 2 zeitnahe
Baseline-Kontrollläufe verschachtelt.

## 10. Experimentbudget

### AP1 Baseline

- 5 Fälle × 5 Wiederholungen = maximal **25 reale Provider-Runs**;
- Providerkosten-Cap: **20 USD**;
- Human-Review-Cap: **480 Minuten**.

### Je ausgewähltem Experiment-Gate

- 5 Fälle × (4 Variante + 1 zeitnahe Baseline-Kontrolle) = maximal **25 Runs**;
- Providerkosten-Cap: **20 USD**;
- Human-Review-Cap: **480 Minuten**;
- maximal **40 Engineering-Stunden** vor einem neuen Gate.

### Finaler Re-Benchmark

- 5 Fälle × (3 übernommene Variante + 2 Baseline-Kontrollen) = **25 Runs**;
- zusätzlich genau 2 begrenzte Discovery→Delivery-Regressionsläufe AP4-01/AP4-04;
- maximal **27 Provider-Runs**;
- Providerkosten-Cap einschließlich der zwei Regressionen: **20 USD**;
- Human-Review-Cap: **480 Minuten**.

Ohne Änderung im Parent #106 gilt ein kumuliertes Providerbudget von **60 USD** für
Baseline + ein ausgewähltes Experiment + finalen Re-Benchmark. Ein weiteres Experiment
benötigt vor dem ersten Providerlauf eine dokumentierte Budgeterweiterung in #106.

Fehlgeschlagene, langsame und abgebrochene Runs bleiben im Datensatz. Ersatzläufe
überschreiben sie nicht, benötigen Begründung + Verknüpfung und erweitern die Caps nicht.

Reicht das Human-Review-, Provider- oder Engineering-Budget nicht für die vorgeschriebene
Bewertung, lautet das Ergebnis **nicht ausreichend belegt**. Qualitätsprüfung wird nicht
weggelassen, nur um im Budget zu bleiben.

## 11. Vorab definierte Übernahmehürden

Diese Schwellen sind operative Engineering-Gates, keine Behauptung statistischer Signifikanz.

### Für alle Änderungsklassen

- beobachtete Quality Hard Fails der Variante: **0**;
- alle Runs autoritativ bewertet; kein `UNASSESSED`;
- Human Authority, Provenance, Recovery und Idempotenz nicht schlechter;
- Effekt überschreitet den A/A-Noise-Floor;
- Kosten pro fachlich akzeptiertem Ergebnis höchstens **+5 %** gegenüber Baseline,
  außer #106 genehmigt vor Adoption explizit einen höheren Wert;
- Timeout-, Retry- und Repair-Rate jeweils höchstens **+5 Prozentpunkte** schlechter
  als Baseline.

### Reversible Änderung ohne Contract-Wechsel

Mindestens eines:

- ≥ 5 % Median-Laufzeitreduktion auf vorab deklarierten betroffenen Fällen;
- oder ≥ 10 s Median-Laufzeitreduktion;
- oder mindestens ein redundanter Model Call weniger je betroffenem Run.

### Contract- oder Modelländerung

Mindestens eines:

- ≥ 10 % **und** ≥ 30 s Median-Laufzeitreduktion;
- oder ≥ 20 % Kostenreduktion bei höchstens 5 % schlechterer Laufzeit;
- oder ≥ 25 Prozentpunkte Verbesserung **einer vorab benannten** Timeout-, Retry-
  oder Repair-Rate.

### Batching oder Concurrency

Höhere Hürde wegen zusätzlicher Recovery-/Persistenzkomplexität. Mindestens eines:

- ≥ 15 % **und** ≥ 45 s Median-Laufzeitreduktion;
- oder ≥ 25 Prozentpunkte Verbesserung einer vorab benannten Timeout-, Retry-
  oder Repair-Rate.

Zusätzlich:

- keine Zunahme unnötiger Evidence-Actions;
- teilweise Ausführung bleibt recoverbar und idempotent.

## 12. Bestehende Messstrecke und AP1-Lücken

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
- Cache-Metadaten nur, soweit Provider sie liefert;
- persistierte `PASS/FAIL/UNASSESSED`-Bewertung pro Run;
- Aggregation der in Abschnitt 7–9 eingefrorenen Vergleichsmetriken.

AP1 darf genau diese Messlücken schließen.

## 13. Exit AP0

AP0 ist abgeschlossen, wenn:

- dieses Dokument und das JSON-Manifest versioniert sind;
- Golden Set und Source-Hashes/Locators eingefroren sind;
- Contract-Tests den aktuellen Investigation-Vertrag inklusive Reasoning-Drift prüfen;
- Qualitätsrubrik, Bewertungsautorität und Verifier-Kontrollvertrag eingefroren sind;
- A/A-Noise-Floor, Population, Aggregation und Event-Raten vorab definiert sind;
- Experiment-, Human-Review- und Kostenbudgets endlich sind;
- klassenübergreifender Kosten-/Tail-Guard feststeht;
- #106 als verbindlicher Auftrag in den Repo-Arbeitsregeln abgebildet ist;
- bekannte Messlücken für AP1 explizit sind.

Danach beginnt #111 mit Baseline/A/A.
