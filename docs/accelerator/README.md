# Accelerator – aktive Dokumentation

Dieser Ordner enthält nur Accelerator-Dokumente, die trotz abgeschlossener Umsetzungs-Issues weiterhin als **aktueller Vertrag, Referenz, Playbook oder Regressionsevidenz** relevant sind.

Historische Workplans, Gap-Analysen, Completion Reports und abgelöste Zwischenstände liegen unter [`../archive/issues/accelerator/`](../archive/issues/accelerator/).

## Foundation und Verträge

- [`BLOCK_1_FOUNDATION.md`](BLOCK_1_FOUNDATION.md) – gemeinsame Feld-, Herkunfts-, LLM- und Entwurfsgrenzen;
- [`BLOCK_2_BLUEPRINT_FORMAT.md`](BLOCK_2_BLUEPRINT_FORMAT.md) – versionierter Scenario-Blueprint-Vertrag;
- [`BLOCK_2_REAL_DEMO_REFERENCE.md`](BLOCK_2_REAL_DEMO_REFERENCE.md) – deterministische Real-DEMO-Referenz;
- [`BLOCK_3_CAPTURE_CONTRACT.md`](BLOCK_3_CAPTURE_CONTRACT.md) – versionierter Capture-Vertrag und Fragenkataloge;
- [`BLOCK_3_MEASUREMENT_PRIVACY.md`](BLOCK_3_MEASUREMENT_PRIVACY.md) – Mess- und Datenschutzgrenzen der Capture-Funktion;
- [`BLOCK_3_RETENTION.md`](BLOCK_3_RETENTION.md) – Retention für Capture Sessions;
- [`BLOCK_6_RETENTION.md`](BLOCK_6_RETENTION.md) – Retention und Datenminimierung der Structured Adoption.

## Architecture Advisor und Solution Quality

- [`ARCHITECTURE_ADVISOR_UI_PLAYBOOK.md`](ARCHITECTURE_ADVISOR_UI_PLAYBOOK.md) – manueller Prüfdurchlauf des Architecture Advisor;
- [`ARCHITECTURE_REAL_DEMO_DRIFT_CONTRACT.md`](ARCHITECTURE_REAL_DEMO_DRIFT_CONTRACT.md) – geschützter Regression-/Driftvertrag;
- [`ARCHITECTURE_REAL_DEMO_ASSESSMENT_OPEN_REPORT.md`](ARCHITECTURE_REAL_DEMO_ASSESSMENT_OPEN_REPORT.md) – deterministisches Referenzartefakt des Driftvertrags;
- [`EVALUATED_SOLUTION_WORKFLOW_UI_PLAYBOOK.md`](EVALUATED_SOLUTION_WORKFLOW_UI_PLAYBOOK.md) – manueller Prüfdurchlauf des Evaluated Solution Workflow.

## Benchmark und Messung

- [`BLOCK_9_BENCHMARK_FREEZE_V2.md`](BLOCK_9_BENCHMARK_FREEZE_V2.md) – aktuell führender eingefrorener Benchmarkvertrag;
- [`BLOCK_9_MEASUREMENT_HELPER.md`](BLOCK_9_MEASUREMENT_HELPER.md) – Messhilfe;
- [`BLOCK_9_ROLE_DEFAULT_MATRIX.md`](BLOCK_9_ROLE_DEFAULT_MATRIX.md) – Referenzmatrix der Rollen-Defaults.

`BLOCK_9_BENCHMARK_FREEZE.md` (v1) wurde durch v2 für die interaktiven AP-9-Läufe ersetzt und liegt deshalb im Archiv.

## Arbeitsvorlage

- [`GAP_ANALYSIS_TEMPLATE.md`](GAP_ANALYSIS_TEMPLATE.md) – wiederverwendbare Vorlage für künftige Gap-Analysen.

## Pflegeprinzip

Ein Dokument bleibt hier nur dann aktiv, wenn mindestens eines gilt:

1. produktive Logik oder Regressionen referenzieren seine Semantik;
2. es definiert einen weiterhin gültigen versionierten Vertrag;
3. es ist die aktuelle Referenz für einen reproduzierbaren Demo-/Benchmarkfall;
4. es ist ein weiterhin verwendetes Playbook oder eine Arbeitsvorlage.

Reine Umsetzungshistorie gehört ins Archiv.
