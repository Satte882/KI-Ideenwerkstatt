# Evaluated Solution Workflow – Abschlussnachweis #212

Stand: AP10

## Ergebnis

Der Evaluated Solution Workflow erweitert die bestehende Block-7-Preview um einen begrenzten Quality-Control-Pfad:

`Generate -> deterministic Validate -> Initial Critic -> optional exactly one Repair -> deterministic Validate -> Final Critic -> Human Review`

Der Pfad erzeugt keine automatische Bewertung, Rangfolge, Lösungsauswahl, Governance-Wirkung oder Adoption.

## Abnahmekriterien und Regression

| Abnahmekriterium | Nachweis |
|---|---|
| Deterministische Validierung vor Critic | `test_invalid_generation_is_rejected_before_initial_critic_is_scheduled` sowie bestehende Block-7-Validierungstests |
| Eigener versionierter Critic-Prompt und fünf feste Kriterien | `test_evaluated_solution_workflow_critic_contract.py` |
| Strukturierte, maschinenlesbare Findings ohne Score/Ranking | `test_evaluated_solution_workflow_critic_contract.py` |
| Initial-Critic-/Quota-/Provider-Ausfall verlustfrei | `test_evaluated_solution_workflow_initial_critic.py` |
| Genau ein expliziter Repair und CAS-/Human-Edit-Schutz | `test_evaluated_solution_workflow_repair_contract.py` |
| Atomarer Cross-Option-Patch und vollständige Revalidierung | `test_evaluated_solution_workflow_targeted_repair.py` |
| Genau ein Final Critic und zwingendes Ende | `test_evaluated_solution_workflow_final_critic.py` |
| Maximal vier Modellaufrufe inklusive Generate | `test_workflow_has_hard_maximum_of_four_model_calls_including_generation` |
| Preview-UI, Findings, Human Review und stale Verhalten | `test_evaluated_solution_workflow_preview_ui.py` |
| Repair erweitert Berechtigungen nicht | `test_repair_endpoint_rechecks_existing_value_stream_permission` |
| Quality-Pfad erzeugt keine Domain-/Gate-/Adoption-Wirkung | `test_complete_quality_path_preserves_domain_gate_and_adoption_boundaries` |
| Bestehende Block-7-Adoption bleibt explizit und neutral | `test_block7_solution_generation_adoption.py` und `test_block7_security_gate_regression.py` |

## Konsolidierte Failure-Abdeckung

Die AP1–AP9-Tests bleiben die detaillierte Fehlerabdeckung und werden in AP10 nicht dupliziert. Abgedeckt sind insbesondere:

- Initial-Critic Provider-, Quota-, Input- und Contract-Fehler;
- stale Source-/Snapshot-/Prompt-/Contract-Versionen;
- Human-Edit-Konflikt;
- ungültiger, unvollständiger oder auf nicht freigegebene Targets gerichteter Repair;
- Provider-Ausfall während Repair;
- Race mit Human Edit während Provider-Aufruf;
- Final Critic ohne erfolgreichen Repair, stale Final-Critic-Binding und Provider-Ausfall;
- One-Shot-Reservierung, parallele Reservierung und terminal verbrauchte Schritte.

## Gate- und Domain-Grenze

Der Abschlussregressionstest prüft den kompletten Quality-Pfad Initial Critic -> Repair -> Final Critic gegen die bestehende Block-7-Grenze. Unverändert bleiben:

- `ProcessAnalysis` und `ValueStream`-Felder;
- `ProcessValidation`;
- `SolutionSelectionDecision`;
- `UseCase`;
- `GovernanceAssessment` und `GovernanceReview`;
- `DeliveryPackage`;
- Lifecycle-`Review`;
- `SolutionOption` bis zu einer separaten expliziten Adoption.

Der Repair-Endpunkt verwendet dieselbe bestehende Value-Stream-Bearbeitungsberechtigung und ist für nicht berechtigte Benutzer gesperrt.

## Bekannte Grenzen

1. **Crash nach Quality-Reservierung:** Ein reservierter Quality-Step kann bei Prozessabbruch vor terminaler Speicherung in `running` verbleiben. V1 implementiert bewusst weder Recovery-Worker noch Retry-Schleife; die One-Shot-Grenze verhindert einen zweiten Provider-Aufruf.
2. **Keine semantische Merge-Logik:** Human Edits nach dem eingefrorenen Quality-Snapshot machen den Repair stale; konkurrierende Änderungen werden nicht automatisch zusammengeführt.
3. **Keine fachliche Automatisierung:** Findings sind Quality-Control-Hinweise. Es gibt keinen Quality Score, keine Rangfolge, keine bevorzugte Option und keine Governance- oder Delivery-Entscheidung.
4. **Real-DEMO/Adversarial Acceptance:** Die gemeinsame reale End-to-End-Abnahme mit #211 ist Bestandteil von #213 und wird hier nicht vorgezogen.

## Abschlussbedingung

AP10 und #212 gelten erst nach Merge des AP10-PRs und vollständig grüner Repository-CI auf dem resultierenden `main` als abgeschlossen.
