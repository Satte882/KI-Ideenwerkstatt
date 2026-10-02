# Issue #113 – Finaler Abschluss von #106

Parent: #106  
Abschluss-Issue: #113  
Ausgewähltes Experiment: #118  
Separates Qualitätsissue: #117

## 1. Abschlussentscheidung

#106 endet mit **Resultat 3**:

> **Der Nutzen der ausgewählten Optimierung wurde innerhalb des genehmigten
> Experimentwegs nicht ausreichend belegt. Keine Optimierung wurde übernommen;
> die Baseline-Runtime v19 bleibt aktiver Produktstand.**

Dies ist ausdrücklich **keine** Aussage, dass v20 technisch falsch, nutzlos oder
qualitativ schlechter als v19 sei.

#118 wurde abgeschlossen als:

> **NOT SUFFICIENTLY PROVEN — NOT ADOPTED**

## 2. G113.0 – Anwendbarkeit des finalen Benchmarks

Der eingefrorene AP0-Vertrag sieht im finalen Re-Benchmark vor:

- fünf Golden-Set-Fälle;
- je Fall drei Läufe der **übernommenen Variante**;
- je Fall zwei zeitnahe Baseline-Kontrollen;
- zusätzlich genau zwei Discovery→Delivery-Regressionsläufe AP4-01 und AP4-04.

Nach #118 existiert keine übernommene Variante B.

### Primärer 25-Run-A/B-Benchmark

Status: **nicht anwendbar**

Begründung:

Die definierte Population setzt eine tatsächlich übernommene Variante voraus.
Ein künstlicher v19-vs-v19-Vergleich hätte keinen Entscheidungswert; ein erneuter
v20-Vergleich würde einen nicht adoptierten Experimentstand wieder in einen
Freigabepfad bringen.

Der 25-Run-Benchmark wird daher weder ausgeführt noch als bestanden markiert.

### Zwei zusätzliche Discovery→Delivery-Regressionsläufe

Status: **ausdrücklich begründet nicht durchgeführt**

AP0 §2 und §10 führen diese zwei Läufe getrennt von der primären A/B-Population
auf. Sie entfallen deshalb nicht automatisch.

Parent #106 hat für diesen Abschluss ausdrücklich entschieden, sie nicht erneut
auszuführen, weil:

- #118 nicht adoptiert wurde;
- PR #121 die aktive Produkt-Runtime real auf v19 zurückgestellt hat;
- kein neuer aktiver fachlicher Produktpfad aus #118 bestehen bleibt;
- die beiden aktiven Produktdateien exakt den historischen v19-Blobs entsprechen;
- Rollback-/Compatibility-Tests und CI erfolgreich sind;
- keine übernommene Änderung vorhanden ist, deren neue Downstream-Wirkung durch
  reale Providerläufe freigegeben werden müsste.

Diese Entscheidung bestätigt ausschließlich die technische Rückstellung. Sie
belegt weder aktuelle Providerlatenz noch neue fachliche Ergebnisqualität.

**Neue Provider-Runs in #113: 0.**

## 3. Code-/Contract-Re-Baseline

Finaler Produktstand nach PR #121:

- Merge-Commit:
  `d3bc40d6240e841a62f5423e2de29445091bf2b7`
- Loop:
  `vs1-agent-loop-v19`
- historische v19-Control-Basis:
  `b37e25b6508a6e5769785c72c2fc35ac1177fae2`

Produktdatei-Identität:

| Datei | finaler Blob | historischer v19-Blob | Status |
|---|---|---|---|
| `ki_radar/accelerator/investigation_llm.py` | `24e075d40706c643857ec0de77ff50c6be996619` | `24e075d40706c643857ec0de77ff50c6be996619` | identisch |
| `ki_radar/accelerator/investigation_runtime.py` | `f90c32a3db7fa833a22b1ae8d9a1f15a05679d3f` | `f90c32a3db7fa833a22b1ae8d9a1f15a05679d3f` | identisch |

Damit ist die **Code-/Contract-Re-Baseline** belegt.

Nicht daraus abgeleitet werden:

- aktuelle Providerperformance;
- heutige Laufzeit-Mediane;
- neue fachliche Qualitätswerte.

Weitere Rollback-Eigenschaften aus PR #121:

- `source_read_coverage` ist nicht mehr Teil des aktiven Planner-Kontexts;
- neue Runs frieren v19 ein;
- korrekt eingefrorene v19-Runs bleiben kompatibel;
- historische v20-Runs werden unter v19 vor Modellaufruf fail-closed mit
  `execution_version_unavailable`;
- historische Execution Snapshots werden nicht umetikettiert;
- keine DB-Migration.

## 4. Evidence-Kette

### AP0 – Mess-/Qualitätsvertrag

Quelle:

- `docs/planning/ISSUE_106_PERFORMANCE_CONTRACT.md`
- `tests/fixtures/issue106_performance_contract_v1.json`

AP0 bleibt historisch unverändert. G113.0 ist eine Parent-Entscheidung zum
Abschlussumfang nach Nicht-Adoption, keine rückwirkende Lockerung der
#118-Adoption-Gates.

### AP1 – Baseline / A/A

Quelle:

- `artifacts/issue106/ap1/README.md`
- `artifacts/issue106/ap1/baseline.json`
- `artifacts/issue106/ap1/review.json`

Getesteter Runtime-Commit:

`b37e25b6508a6e5769785c72c2fc35ac1177fae2`

Population:

- 25/25 reale Runs;
- 10 READY;
- 10 WAITING_HUMAN;
- 5 FAILED;
- keine Ersatzruns.

Autoritative Human Review:

- 16 Quality PASS;
- 9 Quality FAIL;
- 0 beobachtete Hard Fails im bewerteten Sample;
- kein Review-Feld UNASSESSED.

Die 0 Hard Fails sind ausschließlich ein Observed-Sample-Befund und keine
populationsweite Fehlerfreiheitsbehauptung.

Bekannter Qualitätsbefund:

Vier fachlich unvollständige READY-Runs verloren die explizite vollständige
CSV-Fallzuordnung. Dieser Befund wird separat als #117 verfolgt.

### AP2 – Bottleneck / Auswahl

Issue #112:

- analysierte AP1-Evidence;
- bestätigte den State-/Context-Projectionsmechanismus als starken Kandidaten;
- trennte Qualitätsbug #117 ausdrücklich vom Performance-/Reliability-Experiment;
- wählte genau ein Experiment aus: #118.

### #118 – Experiment

Audit:

- `artifacts/issue106/exp118/README.md`
- `artifacts/issue106/exp118/plan.json`
- `artifacts/issue106/exp118/experiment.json`
- `artifacts/issue106/exp118/review.json`

Population:

- 20 v20 Variant-Runs;
- 5 zeitnahe echte v19 Controls;
- keine Ersatzruns.

Technisches Ergebnis:

- G0.3 historisch positiv;
- AP4-02 V1–V4: 4× READY;
- AP4-04 V1–V4: 4× READY;
- `no_progress_loop_count = 0`;
- keine neue technische Failure-Kategorie.

Vergleichbarkeit:

- 4/5 zeitnahe v19-Controls außerhalb des eingefrorenen AP1-Noise-Floors;
- `comparison_status = not_sufficiently_proven`;
- kein Runtime-Speedup wird behauptet.

Qualität:

- 25/25 Human Reviews bleiben `UNASSESSED`;
- keine autoritative Hard-Fail-Abnahme für #118;
- C2c war ausschließlich eine nicht-autoritative AI-Vorannotation;
- keine Adoption.

## 5. Budgetabschluss

### AP1

- tatsächliche bestätigte Providerkosten: **0.134906 USD**
- budget-accounted: **0.184652 USD**
- uncertain attempts: **5**

### #118

- tatsächliche Providerkosten: **0.162755 USD**
- budget-accounted: **0.172800 USD**
- uncertain attempts: **1**

### Kumuliert

- bestätigte actual cost: **0.297661 USD**
- budget-accounted: **0.357452 USD**
- uncertain attempts: **6**
- kumuliertes #106 Providerbudget: **60 USD**
- budget-accounted Rest: **59.642548 USD**

Für #113 wurden **0 neue Provider-Runs** und **0 neue Providerkosten** erzeugt.

Das ungenutzte Budget ist keine Performance-Evidence und begründet keine
Qualitäts- oder Adoptionsaussage.

Für #118 wird keine Kosten-pro-Quality-PASS-Metrik berechnet, weil die Human
Reviews UNASSESSED bleiben.

## 6. Qualitätsaussage

### Belastbar gesagt werden darf

- der aktive Produktcode entspricht wieder dem v19-Produktvertrag;
- AP1 bleibt die autoritativ bewertete historische Baseline-Evidence;
- im AP1-Sample wurden 0 Hard Fails bestätigt;
- AP1 enthielt 9 normale Quality FAILs;
- #117 bleibt als bekannter Qualitätsbug offen;
- #118 besitzt keine autoritative Qualitätsfreigabe;
- der Rollback führt keinen neuen fachlichen Contract ein.

### Nicht gesagt werden darf

- v19 sei fehlerfrei;
- v20 sei technisch widerlegt;
- v20 sei qualitativ schlechter;
- #117 sei durch den Rollback behoben;
- #118 habe 0 bestätigte Hard Fails;
- aktuelle Providerperformance entspreche den AP1-Werten;
- v20 habe keinen Nutzen.

## 7. Rollout / Rollback / Compatibility

Status: **erfüllt**

Referenz:

- PR #121
- Merge-Commit `d3bc40d6240e841a62f5423e2de29445091bf2b7`
- `docs/planning/ISSUE_118_ROLLBACK.md`

Nachweise:

- Produktdateien exakt auf v19;
- keine Migration;
- v19-Recovery kompatibel;
- v20 fail-closed;
- historische v20-Evidence unverändert;
- #120-Harness als Auditstrecke erhalten;
- vollständige PR-CI erfolgreich;
- keine neuen Provider-Runs im Rollback.

## 8. Änderungsinventar seit v19

Die seit dem historischen v19-Control erhaltenen #118-bezogenen Änderungen
betreffen Audit/Harness/Evidence/Tests und Abschlussdokumentation.

Die aktiven Planner-/Runtime-Produktdateien selbst entsprechen wieder den
historischen v19-Blobs.

Daraus folgt keine Behauptung, dass jede beliebige Datei im Repository wieder dem
historischen v19-Commit entspricht. Die Re-Baseline-Aussage ist gezielt auf den
durch #118 veränderten aktiven Produktpfad und dessen Execution Contract begrenzt.

## 9. Applicability-/Exit-Matrix

| Abschlussanforderung | Status | Nachweis / Begründung |
|---|---|---|
| AP0 Vertrag vorhanden | **erfüllt** | #110 / Performance Contract |
| AP1 Baseline + A/A vorhanden | **erfüllt** | #111 / `artifacts/issue106/ap1/` |
| AP2 Kandidaten-/Gate-Entscheidung | **erfüllt** | #112 |
| ausgewähltes Experiment entschieden | **erfüllt** | #118 = NSP / not adopted |
| übernommene Variante B | **nicht anwendbar** | keine Adoption |
| 25-Run Final-A/B | **nicht anwendbar** | kein B-Arm |
| AP4-01/AP4-04 Abschlussruns | **ausdrücklich begründet nicht durchgeführt** | G113.0 Parent-Entscheidung |
| Code-/Contract-Re-Baseline | **erfüllt** | Blob-Identität + v19 Contract |
| Rollback / Recovery / Compatibility | **erfüllt** | PR #121 + Tests + CI |
| #118 Human Review | **historisch offen** | 25/25 UNASSESSED; keine Adoption |
| #118 Hard-Fail-Abnahme | **historisch offen** | keine autoritative Human Review |
| #117 | **historisch offen / separates Issue** | bereits in v19 beobachtet |
| neue Provider-Runs #113 | **ausdrücklich begründet nicht durchgeführt** | 0 Runs |
| finales #106-Ergebnis | **erfüllt** | Resultat 3 |

Nicht anwendbare oder ausdrücklich nicht durchgeführte Punkte werden nicht als
PASS umetikettiert.

## 10. Finales Ergebnis

#106 hat einen realen Reliability-/State-Mechanismus identifiziert und einen
gezielten Fix experimentell geprüft. Der Fix zeigte positive technische
Reliability-Signale, erreichte unter dem vorab definierten Nachweisvertrag jedoch
keine ausreichende Adoption-Evidence.

Daher:

> **Keine Optimierung übernommen. Aktiver Produktstand bleibt v19.
> Der Nutzen von v20 ist nicht ausreichend belegt, nicht widerlegt.**

#117 bleibt nach Abschluss von #106 als separater Qualitätsblock offen.

## 11. #113 Exit

Nach Merge dieses reinen Abschluss-PRs:

1. #113 als abgeschlossen markieren;
2. #106-Checklist für #113 markieren;
3. #106 mit **Resultat 3** schließen;
4. #117 unverändert offen lassen.

Dieser Abschluss erzeugt:

- keine Produktlogikänderung;
- keine Migration;
- keinen neuen Benchmark-Harness;
- keine neuen Provider-Runs;
- keine neue Human Review;
- keine rückwirkende Änderung historischer Evidence.
