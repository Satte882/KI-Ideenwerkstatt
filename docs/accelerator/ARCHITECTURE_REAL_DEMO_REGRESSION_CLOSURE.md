# Architecture Real-DEMO & Regression - Abschlussnachweis

Issue: #213  
Parent: #210  
Workplan: `docs/accelerator/ARCHITECTURE_REAL_DEMO_REGRESSION_WORKPLAN.md`  
Referenz-Fixture: `tests/fixtures/architecture_real_demo_v1.json`

## Abschlussurteil

Die in #213 geforderten Architecture-Advisor- und Evaluated-Solution-Workflow-Nachweise sind
über AP1 bis AP7 implementiert und reproduzierbar abgesichert. AP8 führt die vorhandenen
Nachweise zusammen; es erweitert weder die Methodik aus #211/#212 noch Produktlogik oder
fachliche Gates.

Die Referenzdaten sind ausschließlich synthetisch/anonymisiert. Der produktive Advisor sowie
die produktiven Generation-, Validator-, Critic-, Repair-, Persistenz- und Snapshot-Pfade
bleiben maßgeblich; nur externe Providergrenzen werden im Real-DEMO deterministisch ersetzt.

## Abnahmekriterien

| Issue-Kriterium | Fixture / Contract | Maßgeblicher Nachweis | Ergebnis |
| --- | --- | --- | --- |
| Mindestens 5 kanonische und 5 adversariale Advisor-Fälle | 12 `advisor_cases` | `test_architecture_real_demo_advisor_regression.py` | PASS |
| Assessment-open-Häufigkeit und Reason Codes sichtbar | Advisor-Referenzset | `ARCHITECTURE_REAL_DEMO_ASSESSMENT_OPEN_REPORT.md` | PASS |
| Hohe Komplexität allein erzeugt keinen Agenten | `advisor_adversarial_high_complexity_fixed_workflow` | Advisor-Regression | PASS |
| Semantische Critic-Qualität strukturiert testbar | 6 semantische Quality-Fälle | `test_architecture_real_demo_quality_acceptance.py` | PASS |
| Failure Preservation | Failure-/Repair-Fälle | bestehende #212-Regressionen + Quality-Matrix | PASS |
| One-Shot und Human-Edit-Schutz | Repair-Contract | #212-Regressionen + AP5 | PASS |
| Cross-Feature-Isolation in beide Richtungen | Advisor / Quality Workflow | AP4 Quality-Acceptance | PASS |
| Echter Repair-Concurrency-Nachweis | One-Shot-Repair | `test_architecture_real_demo_ap5_invariance.py` | PASS |
| Backward Compatibility manueller Optionen/Block-7-Previews | bestehende Option + Plain Preview | AP5 Invariance | PASS |
| Gate-Invarianz | Domain-/Governance-/Delivery-/Lifecycle-Gates | AP5 + AP6 | PASS |
| Produktiver Real-DEMO-Kernpfad | synthetischer Beschaffungsfall | `test_architecture_real_demo_ap6_e2e.py` | PASS |
| Deterministische, fail-closed Providergrenze | AP6 Provider-Stub | AP6 E2E | PASS |
| Maximal vier Provider-Aufrufe | Full-Path-Call-Cap | AP6 E2E | PASS |
| Finales Finding endet in Human Review | Final-Critic-Contract | AP6 E2E | PASS |
| Fachlich relevanter Drift-Schutz | Fixture, Advisor, Critic, Repair, State Machine | AP2 + AP7 | PASS |
| Methodische Grenzen dokumentiert | V1-Non-Claims | `ARCHITECTURE_REAL_DEMO_DRIFT_CONTRACT.md` | PASS |
| Vollständige Repository-CI grün | CI-Workflow | letzte grüne AP7-`main`-Basis #1451; AP8-PR und post-merge `main` sind Abschluss-Gates | PASS vor AP8-Änderung |

## Advisor-Referenzset - 12 Fälle

| Fall | Kategorie | Erwartetes Resultat | Reason Code | Ergebnis |
| --- | --- | --- | --- | --- |
| `advisor_canonical_no_llm` | canonical | `no_llm_required` | `simpler_solution_sufficient` | PASS |
| `advisor_canonical_controlled_llm` | canonical | `controlled_llm` | `controlled_llm_sufficient` | PASS |
| `advisor_canonical_llm_workflow` | canonical | `llm_workflow` | `fixed_llm_workflow_sufficient` | PASS |
| `advisor_canonical_bounded_agent` | canonical | `bounded_agent` | `dynamic_orchestration_required` | PASS |
| `advisor_canonical_assessment_open` | canonical | `assessment_open` | `insufficient_information` | PASS |
| `advisor_adversarial_simpler_and_semantic` | adversarial | `assessment_open` | `contradictory_answers` | PASS |
| `advisor_adversarial_fixed_steps_and_dynamic` | adversarial | `assessment_open` | `contradictory_answers` | PASS |
| `advisor_adversarial_taxonomy_boundary` | adversarial | `assessment_open` | `architecture_boundary_unclear` | PASS |
| `advisor_adversarial_dynamic_claim_fixed_flow` | adversarial | `assessment_open` | `contradictory_answers` | PASS |
| `advisor_adversarial_all_unclear` | adversarial | `assessment_open` | `insufficient_information` | PASS |
| `advisor_adversarial_high_complexity_fixed_workflow` | adversarial | `llm_workflow` | `fixed_llm_workflow_sufficient` | PASS |
| `advisor_adversarial_dynamic_countercontrol` | adversarial | `bounded_agent` | `dynamic_orchestration_required` | PASS |

### Assessment open

- getestete Advisor-Fälle: **12**
- klassifiziert, nicht offen: **6**
- `Assessment open`: **6**
- `contradictory_answers`: **3**
- `insufficient_information`: **2**
- `architecture_boundary_unclear`: **1**

Die Gegenkontrolle bleibt explizit: hohe Fachkomplexität bei vollständig festem Workflow ergibt
`llm_workflow`; ein fachlich niedrig komplexer Fall mit tatsächlich dynamischer Schrittwahl
ergibt `bounded_agent`. Komplexität ist damit kein Agenten-Trigger.

## Critic-/Repair-Referenzset - 14 Fälle

| Fall | Schwerpunkt | Autoritativer Nachweis | Ergebnis |
| --- | --- | --- | --- |
| `quality_distinctiveness_near_identical` | Distinctiveness | AP4 Quality-Acceptance | PASS |
| `quality_missing_bottleneck_reference` | Bottleneck Fit | AP4 Quality-Acceptance | PASS |
| `quality_unsubstantiated_qualitative_claim` | Evidence Discipline | AP4 Quality-Acceptance | PASS |
| `quality_explicit_assumption_positive_control` | positive Evidenzkontrolle | AP4 Quality-Acceptance | PASS |
| `quality_unnecessary_architecture_complexity` | Complexity Proportionality | AP4 Quality-Acceptance | PASS |
| `quality_structured_finding_reference` | strukturierte Option-/Feld-/Source-Bindung | AP4 Quality-Acceptance | PASS |
| `quality_initial_critic_provider_failure` | Initial-Critic Failure Preservation | #212 Regression | PASS |
| `quality_repair_provider_failure` | Repair Failure Preservation | #212 Regression | PASS |
| `quality_invalid_repair_contract` | deterministisch ungültiger Repair | #212 Regression | PASS |
| `quality_human_edit_collision` | Human Edit gewinnt | #212 Regression | PASS |
| `quality_exactly_one_repair` | One-Shot Repair | #212 + AP5 | PASS |
| `quality_no_second_repair_after_final` | kein zweiter Repair | #212 + AP6 | PASS |
| `quality_remaining_final_finding_human_review` | Human Review | #212 + AP6 | PASS |
| `quality_full_path_call_cap` | maximal vier Provider-Calls | AP6 E2E | PASS |

## Cross-Feature-, Concurrency-, Backward-Compatibility- und Gate-Nachweise

**Cross-Feature-Isolation:** AP4 weist beide Richtungen nach. Eine Advisor-Einschätzung verändert
weder Quality-Snapshot noch Critic-Input; Initial Critic und Repair verändern keine persistierte
Advisor-Einschätzung.

**Concurrency / One-Shot:** AP5 startet zwei parallele Repair-Trigger gegen denselben
Generation-Run. Genau einer ist erfolgreich, der zweite endet mit `repair_attempt_consumed`,
der Provider wird genau einmal aufgerufen und es existiert genau ein persistierter Repair-Step.
Ein weiterer Repair nach Final Critic erreicht den Provider nicht.

**Backward Compatibility:** Eine bestehende manuelle `SolutionOption` und ein gewöhnlicher
Block-7-Preview ohne #213-spezifische Fixture-Metadaten bleiben nutzbar. Geschützte Felder
`feasibility`, `integration_effort`, `evaluation_status` und `recommendation` bleiben
unverändert.

**Gate-Invarianz:** Process Validation, Solution Selection Decision, Use Case, Governance
Assessment/Review, DeliveryPackage und Lifecycle Review werden durch Advisor, Critic und Repair
nicht automatisch erzeugt oder verändert. AP5 und AP6 vergleichen den Zustand vor und nach den
produktiven Pfaden.

## Real-DEMO-Sequenz

Der AP6-E2E nutzt den synthetischen Prozess `Synthetischer Angebotsvergleich` und durchläuft:

1. drei unterschiedlich gelagerte Advisor-Fälle inklusive sichtbarer Why-/Why-no-Agent-Aussage;
2. einen bewusst widersprüchlichen `assessment_open`-Fall;
3. produktive Block-7-Generierung;
4. deterministische Validierung der Roh-Preview;
5. produktiven Initial Critic mit strukturiertem `bottleneck_fit`-Finding;
6. genau einen gezielten Repair auf `assistant.bottleneck_coverage`;
7. erneute deterministische Validierung von Roh- und Effective-Payload;
8. produktiven Final Critic mit verbleibendem, nicht reparierbarem Finding;
9. Human Review als notwendige Fortsetzung statt zweitem Repair;
10. unveränderte fachliche Gates und geschützte manuelle Optionsfelder.

Tatsächliche Provider-Aufrufreihenfolge und -anzahl im E2E:

`generation -> initial_critic -> repair -> final_critic` = **4 Calls**.

Der Provider-Stub bildet ausschließlich die externe Grenze ab. Er kanonisiert den Input,
verifiziert identischen Output für identischen Input und lehnt unerwartete Inputs fail-closed ab.
Der dedizierte Real-DEMO-CI-Step besitzt `timeout-minutes: 3`; anschließend läuft weiterhin die
vollständige Repository-Suite.

## Drift-Schutz

AP7 konsolidiert den AP2-Fixture-/Checksum-Vertrag mit den fachlich relevanten Semantiken:

- Advisor: 81-Kombinationen-Matrix, Modes und Reason Codes;
- 12 benannte Real-DEMO-Advisor-Fälle;
- fünf Critic-Kriterien und strukturierte Target-Bindung;
- Quality-State-Machine `initial_critic -> repair -> final_critic`;
- DB-One-Shot und maximal ein Repair;
- Full-Path-Call-Cap von vier Provider-Aufrufen;
- Human Review bei verbleibendem finalem Finding;
- Gate- und Backward-Compatibility-Evidence-Pfade.

Freie LLM-Texte, Zeitstempel, zufällige Persistenz-IDs und andere laufabhängige Metadaten werden
bewusst nicht als Ganzes gehasht.

## Methodische Grenzen / Non-Claims

- Advisor V1 ist **expert-informed** und **nicht empirisch an einer breiten Menge realer Unternehmensfälle kalibriert**.
- Die Architekturklassifikation behauptet **keine objektive Architekturwahrheit**.
- `Assessment open` ist ein beabsichtigter transparenter Sicherheitsausgang und kein Fehler, der für eine höhere Quote unterdrückt werden soll.
- Hohe Komplexität allein begründet keine Agentik.
- Es gibt **keinen Framework-Benchmark** und **kein Multi-Agent-System**.
- Der Critic ist **kein Domain-, Governance-, Selection- oder Lifecycle-Gate** und trifft keine fachliche Freigabeentscheidung.
- Advisor und Quality Workflow setzen keine Bewertung, Rangfolge, Recommendation oder bevorzugte Option automatisch.
- Es gibt keinen zweiten Repair-Versuch und keine Retry-Schleife nach dem einmaligen Repair.
- Die Referenzdaten sind synthetisch/anonymisiert und enthalten keine realen Produktions- oder personenbezogenen Daten.

## Abweichungen vom Workplan

Es besteht **keine fachliche Abweichung** vom fixierten AP1-AP8-Scope. Während AP5-AP7 waren
rein testtechnische Anpassungen erforderlich, nachdem vollständige CI-Läufe konkrete Fehler
belegt hatten: Isolation automatischer Critic-Signale im Concurrency-Test, Ruff-Formatierung und
Markdown-normalisierte Dokumentassertion. Diese Änderungen erweitern weder Produktvertrag noch
Methodik.

Die finale AP8-PR-CI sowie die post-merge `main`-CI sind operative Abschluss-Gates. Ihre
konkreten Run-IDs entstehen erst nach diesem statischen Bericht und werden beim formalen
Abschluss von #213 dokumentiert; #213 wird vorher nicht geschlossen.

## CI-Ausgangsbasis für AP8

- `main` vor AP8: `1e90309f32d50bb13582ace327a9bfe5f9edf431`
- vollständiger `main`-CI-Lauf: **#1451 – success**
- enthalten: Ruff, Django-/Migration-Gates, Real-DEMO-E2E, vollständige Testsuite, Bandit,
  Dependency Audit, alle Compose-Validierungen sowie Production- und Development-Image-Build.

AP8 gilt erst als abgeschlossen, wenn der AP8-PR vollständig grün gemergt ist und der dadurch
ausgelöste `main`-CI ebenfalls vollständig grün abgeschlossen wurde.
