# Issue #144 – Outcome-first: Aufrufer- und Risikoinventar

**Stand:** 22.10.2026 · **Basis:** `main@f8cabbc418b4777d7bfd075e6c0dc1a3322aaa41`  
**Zweck:** Review-/Migrationslandkarte für [ADR 0009](../adr/0009-outcome-first-vorhaben-und-wirkung.md). **Keine Produktänderung.**

## Status und Methode

Die folgenden Zeilen sind **konkret aus GitHub-Dateien gelesen**. Der GitHub-Code-Suchindex meldete für den Repository-Code `incomplete_results=true`; ein lokaler kompletter `rg`-Durchlauf war mangels geklontem/ausführbarem Repo **nicht verfügbar**. Deshalb ist diese Liste eine **belegte Mindestmenge**, ausdrücklich **kein behauptetes vollständiges Trefferprotokoll**. Vor der Annahme des ADR ist der unten definierte automatische Vollscan auf dem Checkout obligatorisch; nach dem Scan sind Trefferzahlen und möglicherweise fehlende Aufrufer nachzutragen.

Auch direkte ORM-Relationen, Django-Template-Attribute und historische Datenmigrationen können Helper-Suchen umgehen. Nicht nur exakte importierte Funktionsnamen prüfen.

## A. Fokus- und Stage-Gates: verifizierte konkrete Pfade

| Symbol / Invariante | Verifizierte Aufrufer / Stellen | Relevanz |
|---|---|---|
| `get_value_stream_focus` | `architecture/focus.py` (Definition); `architecture/forms.py`; `architecture/gated_views.py`; `architecture/stage_focus_views.py`; `architecture/views.py`; `architecture/solution_selection.py` → `focus_readiness_blockers`; `use_cases/workflow.py`; `core/scenario_blueprint_diff.py`; `review_export_architecture.py` | Globales VS-Screening ist teils Gate, teils Darstellung/Export. Neuer Vorhaben-Fokus darf nicht mit globalem Screening gleichgesetzt werden. |
| `get_stage_focus_decision` | `architecture/stage_focus.py` (Definition, `stage_is_selected`, Kurzpfade); `architecture/gated_views.py`; `architecture/stage_focus_views.py`; `architecture/templatetags/architecture_focus.py`; `review_export_architecture.py` | Bislang über `value_stream.stage_focus_decision` nur ein globaler Zustand. |
| `save_stage_focus_decision` | `architecture/stage_focus.py` (Definition, `update_or_create`); `architecture/stage_focus_views.py`; `architecture/discovery_materialization.py` | Beim zweiten unabhängigen Vorhaben können bestehende Phasenwahl/Begründung überschrieben werden. |
| `stage_is_selected` | `architecture/stage_focus.py` (Definition) | Direkte weitere Produktionsaufrufer in geprüften Architektur-/Use-Case-Modulen nicht beobachtet; Tests und indirekte Nutzungen vollständig scannen. |
| `focus_readiness_blockers` | `architecture/solution_selection.py` (Definition + `select_preferred_solution`); `architecture/solution_views.py` | Entscheidet gegenwärtig nur anhand `ValueStreamFocus.is_selected`; Initiative-Stage-Wahl fehlt. |
| Direktrelationen | `templates/architecture/value_stream_detail.html` nutzt `value_stream.focus` und `value_stream.stage_focus_decision`; `templates/architecture/stage_focus_form.html` zeigt VS-zentrierte Auswahl; `templates/architecture/solution_option_compare.html` zeigt Auswahlgate; `architecture/models.py`, `architecture/focus.py`, `architecture/stage_focus.py` | Django-Templates und `select_related` können neue Kardinalitäten brechen, auch wenn keine Helper-Aufrufe vorliegen. |
| Signale | `architecture/stage_focus.py::persist_focus_from_existing_process` und `::persist_focus_from_existing_origin` (`post_save`) | Erzeugen bei bisher fehlender Globalentscheidung Legacy-Kurzpfade; nicht blind auf vorhabenbezogene Auswahl übertragen. |
| Demo/Seeds | `architecture/focus.py::DEMO_FOCUS_DEFAULTS` mit Signal/Seed; `core/demo_architecture_data.py`; `core/golden_path_demo.py`; `core/scenario_blueprint_apply.py`, `scenario_blueprint_diff.py`, `scenario_blueprint_validation.py`; `core/management/commands/seed_demo_data.py` | Existierende kanonische Demo-IDs, `UseCaseOrigin`, strategische Ziele, Blueprint-Replays/Hashes und Seeding nicht verändern. |
| Export / Read-Models | `review_export_architecture.py`; `use_cases/workflow.py`; `architecture/templatetags/architecture_focus.py` | Anzeige/Exports dürfen nicht implizit die eine VS-Fokuswahl als die Vorhabensentscheidung darstellen. |

**Modellinvariante:** `ValueStreamFocus.value_stream` und `StageFocusDecision.value_stream` sind derzeit `OneToOne`. `StageFocusDecision` ist keine append-only-Entscheidung; `SolutionSelectionDecision` dagegen schon. Das erste bleibt potenziell globales Screening; das zweite benötigt für neue Vorhaben anderen Identitäts- und Historievertrag.

## B. Idee, Discovery, Ursprung und bindende Lösung

| Verantwortlichkeit | Konkrete Anker | Risiko |
|---|---|---|
| Ideen-Inbox und Promotion | `use_cases/idea_models.py` (`IdeaCandidate.state`, `promoted_use_case`/`discovery_process_analysis` jeweils `OneToOne`, `quick_score`); `idea_discovery.py`; `idea_views.py`; `idea_forms.py`; `intake_views.py` | Idee ist nicht automatisch Vorhaben; direkte Use Cases und Non-KI können nicht in vorhandenen Promotionsstatus hineingezwungen werden. |
| Autonome Discovery | `accelerator/architect_contract.py` (`value_stream.outcome`, `strategic_objective`, `process_analysis.outcome`); `architect_service.py`; `architect_views.py`; `architecture/discovery_materialization.py` (`save_stage_focus_decision`) | Value-Stream-Ergebnis ist nicht vorhabensbezogenes Geschäftsergebnis; Prompt-, Schema- und Reparaturversionen dürfen nicht unbemerkt umgedeutet werden. |
| Option und bindende Wahl | `architecture/models.py::SolutionOption`, `::SolutionSelectionDecision`; `architecture/solution_selection.py::{focus_readiness_blockers,comparison_blockers,diagnosis_readiness_blockers,build_comparison_snapshot,build_diagnosis_snapshot,select_preferred_solution}`; `architecture/solution_views.py`; `templates/architecture/solution_option_compare.html` | Bestehende Optionen enthalten `expected_value` und Engpass-Fit, aber keine gemeinsame Outcome-Revision. Prozessversion ist nicht Outcome-Version. |
| Herkunft und Konsistenz | `architecture/models.py::UseCaseOrigin`; `architecture/provenance.py`; `architecture/views.py`; `use_cases/origin_consistency.py`; `use_cases/services.py`; `use_cases/classification.py` (`post_save`) | `UseCaseOrigin` und eingefrorene Vergleichssnapshots nicht rückwirkend verändern oder neu erraten. |
| Lösungsgenerator | `accelerator/solution_generation_sources.py`; `solution_generation_contract.py`; `solution_generation_entry.py`; `solution_generation_service.py`; Critic-/Repair-Module | Texte generieren Optionen; sie dürfen kein angenommenes Geschäftsergebnis oder eine menschliche Auswahl erfinden. |
| Direkt-Intake | `use_cases/intake.py`; `intake_views.py`; `lean_intake.py`; `use_cases/forms.py`; `use_cases/views.py` | Neue Outcome-Bindung für neue Initiative möglich, aber Bestand darf nicht blockiert werden. |
| Rollenspezifisches Geschäftsergebnis | `architecture/models.py::WorkDesignAssessment.business_outcome`; `architecture/forms.py`; `architecture/views.py`; `architecture/work_design.py` | TASKSHIFT ist optional, darf nicht zur Source of Truth für alle Initiativen werden. |

## C. `metric_*` und `UseCase` – verifizierte Nutzer und Risk Surface

**Daten und Anzeige**
- `use_cases/models.py`: `metric_name/type/direction/unit/baseline/target/actual/measurement_method/measurement_period/measurement_population/measured_at/evidence_url`, `metric_result`, `metric_result_label`; letztere beziehen „Ziel erreicht“ nur auf die Use-Case-Metrik.
- `use_cases/forms.py`, `intake.py`, `lean_intake.py`, `intake_views.py`, `views.py`, `metric_presentation.py`, `templatetags/metric_tags.py`, `copilot.py`.
- `templates/reporting/outcome_workspace.html`, `reporting/views.py`, `use_cases/outcome_workspace.py`, `use_cases/status_dimensions.py`.

**Pflichtfelder, Entscheidungen und Governance**
- `use_cases/blockers.py`, `use_cases/services.py` (PILOT-/GO_LIVE-/APPROVAL-Metriklisten), `use_cases/transition_policy.py`, `use_cases/scale_readiness.py`, `reviews/forms.py`, `reviews/lean_forms.py`.
- `use_cases/ap2_metric_pilot.py`, `use_cases/ap2_decision_governance.py`, `architecture/ap2_architecture.py`.
- `ki_radar/reviews/views.py`, `use_cases/lean_outcome.py`, `use_cases/outcome_workspace.py`.

**Delivery, Evidenz, Exporte, Demo**
- `delivery/ap3_autonomous.py`, `delivery/evidence_composer.py`, `delivery/evidence_mapping_contract.py`, `delivery/services.py`, `delivery/ai_draft.py`.
- `accelerator/structured_metric_adoption.py` (Target-Feldmap und Hashschutz).
- `review_export_use_cases.py`, `review_export_core.py`, `review_export_architecture.py`, `reporting/views.py`; `delivery/exports.py` bei CSV-/Artefaktkontext explizit überprüfen.
- `core/demo_data.py`, `demo_decision_data.py`, `golden_path_demo.py`, `scenario_blueprint_apply.py`, `scenario_blueprint_diff.py`, `scenario_blueprint_validation.py`.

**Risiko:** `metric_*` aus `UseCase` auf eine gemeinsame abstrakte Entität zu verschieben hätte hohen Blast Radius. Voraussichtlich risikoärmer: bestehende KI-Metriken belassen und zusätzlich eine schlanke, vorhabensbezogene Wirkungskontrolle nach ADR durchführen. Keine neue Messreihe ohne gesonderte Priorisierung.

## D. Test- und UI-Flächen (vor Implementierung auf Vollständigkeit prüfen)

- Fokus/Discovery: `tests/test_stage_focus_and_process_findings.py`, `tests/test_value_stream_scope.py`, `tests/test_value_stream_capture_views.py`, `tests/test_solution_selection_ux.py`, `tests/test_issue_364_process_value_stream_hardening.py`, `tests/test_idea_autonomous_discovery.py`, `tests/test_issue_422_idea_inbox.py`.
- Outcome/Metrik: `tests/test_issue_340_optional_intake_metrics.py`, `tests/test_issue_100_ap2_metric_pilot.py`, `tests/test_outcome_journey_consistency.py`, `tests/test_outcome_workspace_actions.py`, `tests/test_metric_presentation.py`, `tests/test_delivery_to_pilot.py`.
- Demo/Export: `tests/test_demo_architecture_data.py`, `tests/test_demo_data.py`, `tests/test_real_demo_blueprint.py`, weitere `review_export`-, Blueprint- und Delivery-Tests.
- UI: `templates/architecture/{value_stream_detail,value_stream_form,stage_focus_form,solution_option_compare}.html`, `templates/accelerator/{autonomous_discovery_review,solution_generation_preview}.html`, `templates/use_cases/ideas/*.html`, `templates/reporting/outcome_workspace.html`, `templates/use_cases/assessment_form.html`, `templates/reviews/*.html`.

## E. Reproduzierbarer Vollscan auf dem Repository-Checkout – noch auszuführen

Abnahme von #144 verlangt **eine vollständige Trefferliste** (Datei, Zeile, referenzierter Vertrag, geplante Änderung oder „unverändert“) für alle relevanten Treffer. Folgende Befehle erfassen auch indirekte Zugriffe und gängige dynamische Namen:

```bash
git status --short
git rev-parse HEAD
rg -n --glob '*.py' --glob '*.html' --glob '*.md'  'get_value_stream_focus|get_stage_focus_decision|stage_is_selected|save_stage_focus_decision|focus_readiness_blockers|value_stream\.focus|\.stage_focus_decision|StageFocusDecision|ValueStreamFocus|DEMO_FOCUS_DEFAULTS|is_short_path|ensure_stage_focus_for_existing_path'  ki_radar templates tests scripts docs
rg -n --glob '*.py' --glob '*.html'  '(metric_[a-z_]+|metric_result|metric_set|PILOT_METRIC_REQUIREMENTS|GO_LIVE_METRIC_REQUIREMENTS|expected_benefit|business_outcome|strategic_objective|quick_score|strategic_fit|comparison_snapshot)'  ki_radar templates tests scripts
rg -n --glob '*.py' --glob '*.html'  'post_save|UseCaseOrigin|IdeaCandidate|source_snapshot|solution_selection_decisions|csv|CSV|export|seed|blueprint'  ki_radar templates tests scripts
```

Auch `getattr`, `select_related`, `prefetch_related`, `values`, Feldnamenlisten, Django-Template-Kontextvariablen, Permissions und migrationshistorische Daten explizit prüfen. Dynamische Relationen und Tests sind **nicht** durch bloße `rg`-Trefferzahlen vollständig nachgewiesen.

**Vorläufige risikoarme Folgerung (nicht als implementierte Tatsache verstehen):**
1. Globale VS-Eignung vom vorhabensspezifischen Stage-Fokus trennen.
2. Direkte/alte Use Cases ohne Outcome-Inititiative erhalten.
3. Use-Case-Metriken nicht aus der bestehenden Lifecycle-Policy herauslösen.
4. Prüfkriterien und negative Service-/DB-/View-Tests aus #145–#147 erst nach angenommenem ADR finalisieren.

## F. Akzeptanzgrenze

Dieses Dokument ist die **in GitHub gelesene, belegte Ausgangsinventur**. Noch offen: Ergebnis des lokalen Vollscans einschließlich Trefferzahlen, Testaufrufer- und Templatekomplettheit und Review eventueller unbekannter Dynamik. Diese Lücke darf vor fachlicher ADR-Annahme weder als „vollständig inventarisiert“ noch als „alles getestet“ gekennzeichnet werden.

**Keine Tests liefen in diesem reinen Dokumentationsauftrag.** CI nach Anlage des Draft-PR separat beobachten. Der vorgeschlagene ADR bleibt bis zur ausdrücklichen Nutzerannahme nur ein Vorschlag.
