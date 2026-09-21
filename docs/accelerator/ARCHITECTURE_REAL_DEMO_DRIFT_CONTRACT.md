# Architecture Real-DEMO - Drift-Vertrag

Issue: #213  
Arbeitspaket: AP7  
Referenz-Fixture: `tests/fixtures/architecture_real_demo_v1.json`

## Zweck

Dieser Vertrag konsolidiert die in AP2 bis AP6 aufgebauten Regressionen. Er schützt die
strukturierte fachliche Semantik des Architecture Advisor und des Evaluated Solution Workflow
gegen stillen Drift. Er ersetzt keine der bestehenden funktionalen Regressionen und erweitert
die in #211 und #212 freigegebene Methodik nicht.

## Geschützte Verträge

| Vertrag | Verbindlicher Nachweis |
| --- | --- |
| Advisor: alle 81 Antwortkombinationen, Modes und Reason Codes | `tests/test_architecture_advisor_contract.py` und `tests/fixtures/architecture_advisor_matrix_v1.json` |
| Real-DEMO-Fixture: Schema, Versionen, Checksum, 12 Advisor- und 14 Quality-Fälle | `tests/test_architecture_real_demo_fixture_contract.py` |
| Advisor: 12 benannte Referenzfälle und Why/Why-no-Agent-Semantik | `tests/test_architecture_real_demo_advisor_regression.py` |
| Assessment-open-Häufigkeit und Reason-Code-Verteilung | `tests/test_architecture_real_demo_advisor_regression.py` und `docs/accelerator/ARCHITECTURE_REAL_DEMO_ASSESSMENT_OPEN_REPORT.md` |
| Critic: fünf Kriterien und strukturierte Option-/Feld-/Source-Bindung | `tests/test_architecture_real_demo_quality_acceptance.py` und `tests/test_architecture_real_demo_ap7_drift_contract.py` |
| Repair: explizite Target-Bindung, Human-Edit-Schutz und genau ein Repair | `tests/test_evaluated_solution_workflow_repair_contract.py` und `tests/test_architecture_real_demo_ap5_invariance.py` |
| Quality-State-Machine: Initial Critic -> Repair -> Final Critic | `tests/test_architecture_real_demo_ap6_e2e.py` und `tests/test_architecture_real_demo_ap7_drift_contract.py` |
| Provider-Call-Cap: maximal vier Calls inklusive Generation | `tests/test_architecture_real_demo_ap6_e2e.py` und Fixture-Fall `quality_full_path_call_cap` |
| Finales Finding: Human Review statt zweiter Repair-Schleife | `tests/test_architecture_real_demo_ap6_e2e.py` und Fixture-Fall `quality_remaining_final_finding_human_review` |
| Gate- und Backward-Compatibility-Invarianz | `tests/test_architecture_real_demo_ap5_invariance.py` und `tests/test_architecture_real_demo_ap6_e2e.py` |
| Cross-Feature-Isolation Advisor <-> Critic/Repair | `tests/test_architecture_real_demo_quality_acceptance.py` |

## Drift-Regeln

Eine beabsichtigte Änderung an einem der geschützten Contracts muss sichtbar versioniert und
zusammenhängend angepasst werden. Je nach betroffenem Vertrag umfasst dies produktive
Konstanten bzw. Versionen, Fixture/Schema/Checksum, die zugehörigen Regressionen und die
sichtbaren Nachweisartefakte. Ein stilles Ändern von Mode-/Reason-Code-Semantik,
Critic-Kriterien, Repair-Zielen, One-Shot-Verhalten, Quality-Step-Reihenfolge, Call Cap oder
Gate-Invarianz ist nicht zulässig.

Der AP2-Checksum schützt die versionierte Referenz-Fixture. Zusätzlich prüfen produktive Tests
die darin kodierte Semantik. Der Assessment-open-Bericht wird weiterhin deterministisch aus
der Fixture und dem produktiven Advisor erzeugt und byte-genau geprüft; AP7 nimmt ihn als
verbindliches Closure-Artefakt in den Driftvertrag auf.

Freie LLM-Texte werden nicht als Ganzes gehasht. Ebenso werden keine Zeitstempel, zufälligen
Persistenz-IDs, Laufzeiten oder sonstige laufabhängige Metadaten in einen Drift-Hash aufgenommen.
Geschützt werden die strukturierten Verträge, Versionen, Referenzen, Zustandsübergänge und
fachlichen Invarianten.

## Methodische Grenzen

Der Architecture Advisor V1 ist **expert-informed** und bewusst klein sowie deterministisch.
Er ist **nicht empirisch kalibriert** an einer breiten Menge realer Unternehmensfälle und
behauptet **keine objektive Architekturwahrheit**. Die Referenzfälle sind Regressionen für den
freigegebenen Contract, keine statistische Aussage über reale Architekturverteilungen.

`Assessment open` ist ein beabsichtigter Sicherheitsausgang bei fehlenden, widersprüchlichen
oder außerhalb der V1-Taxonomie liegenden Informationen. Eine hohe fachliche Komplexität allein
ist kein Nachweis für Agentik. Die V1 liefert außerdem **kein Framework-Benchmark** und ist
**kein Multi-Agent-System**.

Der Critic prüft die freigegebenen semantischen Qualitätskriterien strukturiert. Er ist **kein
Domain-, Governance-, Selection- oder Lifecycle-Gate** und trifft keine fachliche
Freigabeentscheidung. Ein Repair ist auf explizite Targets begrenzt und darf höchstens einmal
erfolgen; verbleibende Findings gehen nach dem Final Critic in Human Review.

Provider-generierte Formulierungen sind nicht als objektive Wahrheit zu interpretieren. Die
Robustheit entsteht durch deterministische Validierung, strukturierte Findings, Target-Bindung,
One-Shot-Repair, erneute Validierung und die abschließende menschliche Prüfung.
