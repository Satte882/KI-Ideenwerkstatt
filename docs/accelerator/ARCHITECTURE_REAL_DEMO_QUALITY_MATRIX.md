# Architecture Real-DEMO - Critic-/Repair-Regressionsmatrix

Issue: #213  
AP: AP4 - Critic-/Repair-Regressionsmatrix und Cross-Feature-Isolation  
Fixture: `tests/fixtures/architecture_real_demo_v1.json`

## Zweck

Die Matrix verbindet die versionierten Quality-Fälle aus AP2 mit dem maßgeblichen Nachweis. Bereits in #212 vollständig abgedeckte Failure-/Repair-Invarianten werden nicht dupliziert. AP4 ergänzt die bisher fehlenden fachlich benannten Quality-Acceptance-Fälle und die Isolation zwischen Architecture Advisor und Evaluated Solution Workflow.

## Semantische Quality-Fälle

| Fixture-Fall | Erwarteter Contract | Maßgeblicher Nachweis |
|---|---|---|
| `quality_distinctiveness_near_identical` | `distinctiveness`, strukturierte Option/Feld/Evidenz, gezielt reparierbar | `test_fixture_quality_case_round_trips_through_productive_initial_critic` |
| `quality_missing_bottleneck_reference` | `bottleneck_fit`, Bezug auf `process.bottlenecks`, gezielt reparierbar | `test_fixture_quality_case_round_trips_through_productive_initial_critic` |
| `quality_unsubstantiated_qualitative_claim` | `evidence_discipline`, unbelegte qualitative Aussage bleibt Finding | `test_fixture_quality_case_round_trips_through_productive_initial_critic` |
| `quality_explicit_assumption_positive_control` | korrekt ausgewiesene Unsicherheit erzeugt in der positiven Kontrolle kein Finding | `test_fixture_quality_case_round_trips_through_productive_initial_critic` |
| `quality_unnecessary_architecture_complexity` | `complexity_proportionality`, unnötige KI-/Architekturkomplexität wird strukturiert referenziert | `test_fixture_quality_case_round_trips_through_productive_initial_critic` |
| `quality_structured_finding_reference` | Option, Feld und vorhandene Evidenz sind maschinenlesbar gebunden | `test_fixture_quality_case_round_trips_through_productive_initial_critic` plus bestehender Critic-Contract aus #212 |

Die Tests prüfen den strukturierten, deterministisch validierten Critic-Contract. Sie behaupten keine empirische Messung der Trefferquote eines externen LLM-Modells. Die Providergrenze ist deterministisch ersetzt; der produktive Critic-Service und dessen Contract-Validierung bleiben maßgeblich.

## Bereits vorhandene Failure-/Repair-Nachweise aus #212

| Fixture-Fall | Wiederverwendeter autoritativer Nachweis |
|---|---|
| `quality_initial_critic_provider_failure` | `test_provider_failure_preserves_valid_generation_preview_and_consumes_attempt` / Completion-Regression |
| `quality_repair_provider_failure` | `test_provider_failure_preserves_original_preview_and_consumes_one_shot` |
| `quality_invalid_repair_contract` | `test_repair_with_invalid_quantitative_claim_is_discarded_atomically` und Repair-Contract-Tests |
| `quality_human_edit_collision` | `test_human_edit_during_provider_call_wins_and_stale_repair_is_discarded` |
| `quality_exactly_one_repair` | persistierter Repair-Step, `repair_attempt_consumed` und Unique-Constraint aus #212 |
| `quality_no_second_repair_after_final` | `test_remaining_final_findings_end_in_human_review_without_second_repair` |
| `quality_remaining_final_finding_human_review` | Final-Critic-/Human-Review-Regression aus #212 |
| `quality_full_path_call_cap` | Einzel-Step-Caps aus #212; integrierter Gesamt-Call-Cap folgt in AP6 |

## Cross-Feature-Isolation

AP4 ergänzt zwei explizite Richtungen:

1. **Advisor -> Quality Workflow:** Eine gespeicherte `Bounded Agent`-Einschätzung verändert weder Quality-Snapshot noch Critic-Input. Der Snapshot-Hash und das Snapshot-Dokument bleiben identisch; Advisor-Mode, Ruleset und Antwortfelder gelangen nicht in den Provider-Aufruf.
2. **Quality Workflow -> Advisor:** Initial Critic und erfolgreicher gezielter Repair verändern weder Advisor-Antworten noch Architecture Mode, Reason Codes, Ruleset-Version, Assessment-Version oder Assessor.

Maßgebliche Tests:

- `test_advisor_assessment_does_not_change_quality_snapshot_or_critic_input`
- `test_critic_and_repair_do_not_change_persisted_advisor_assessment`

Damit bleiben die in #210 definierten Fähigkeiten fachlich und technisch getrennt. Eine Architekturklassifikation erzeugt keine versteckte Repair-Präzedenz; Critic-/Repair-Ergebnisse schreiben nicht in die Architecture-Advisor-Einschätzung zurück.
