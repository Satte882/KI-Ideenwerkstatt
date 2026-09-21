# Architecture Real-DEMO & Regression – Traceability-Matrix

Issue: #213  
Parent: #210  
Workplan: `docs/accelerator/ARCHITECTURE_REAL_DEMO_REGRESSION_WORKPLAN.md`  
AP: AP1 – Scope Lock, Contract-Inventur und Traceability-Matrix  
Stand: 2026-08-10  
Startbasis `main`: `c092752e857604b718bc6a683a75f856690eca43`

## Zweck

Dieses Dokument trennt für #213 drei Dinge sauber voneinander:

1. bereits auf `main` vorhandene und autoritative Nachweise aus #211/#212;
2. vorhandene Teilabsicherung, die für die explizite #213-Abnahme noch ergänzt werden muss;
3. echte Nachweislücken, die in AP2–AP8 geschlossen werden.

#213 entwickelt Architecture Advisor oder Evaluated Solution Workflow nicht erneut. Vorhandene produktive Contracts bleiben maßgeblich und werden im Real-DEMO über ihre echten Service-, Persistenz-, Validierungs-, Snapshot-/CAS- und Gate-Pfade verwendet.

## Fixierter Scope und Entscheidungsregel

### Contract-Verletzung

Wenn ein #213-Test zeigt, dass die aktuelle Implementierung einen bereits beschlossenen Contract aus #210/#211/#212 verletzt, ist innerhalb von #213 ausschließlich ein minimaler Bugfix mit Regressionstest zulässig.

### Methodische V1-Grenze

Wenn ein Fall außerhalb der bewusst begrenzten V1-Methodik liegt oder entscheidende Information fehlt, wird das bestehende Verhalten dokumentiert. Beim Advisor ist `Assessment open` ausdrücklich ein zulässiger Ausgang. Daraus entsteht in #213 keine neue Frage, Regel, Architekturklasse, Gewichtung oder Scoring-Logik.

### Keine Scope-Erweiterung

Insbesondere nicht zulässig sind:

- Änderung von #210;
- neue Advisor-Fragen, Modes, Scores oder automatische Auswahlentscheidungen;
- Aufwertung des Critic zu einem Domain-/Governance-Gate;
- zweiter Repair-Versuch oder Retry-Schleife;
- Multi-Agent-System oder Agent-Framework-Benchmark;
- automatische Änderung von fachlicher Bewertung, Recommendation, Governance, Delivery oder Lifecycle.

## Autoritative bestehende Contracts auf `main`

### Architecture Advisor

Autoritative Implementierung: `ki_radar/architecture/architecture_advisor.py`.

Bereits fixiert sind:

- Ruleset `architecture-advisor-v1`;
- exakt vier Antworten mit `yes`, `no`, `unclear`;
- fünf Ausgänge: `no_llm_required`, `controlled_llm`, `llm_workflow`, `bounded_agent`, `assessment_open`;
- Widerspruchserkennung vor positiver Klassifikation;
- `architecture_boundary_unclear` für `simpler=no` und `semantic=no`;
- symmetrische `Unklar`-Behandlung über alle binären Vervollständigungen;
- deterministische Reason Codes und Explainability;
- vollständige 81-Kombinationen-Fixture `tests/fixtures/architecture_advisor_matrix_v1.json`.

Relevante bestehende Tests:

- `tests/test_architecture_advisor.py`;
- `tests/test_architecture_advisor_contract.py`;
- `tests/test_architecture_advisor_completion.py`;
- `tests/test_architecture_advisor_invariance.py`;
- `tests/test_architecture_advisor_persistence.py`;
- `tests/test_architecture_advisor_write_path.py`;
- `tests/test_architecture_advisor_ui.py`.

### Evaluated Solution Workflow

Autoritativ bleibt die Reihenfolge:

Generate -> deterministic Validate -> Initial Critic -> optional exactly one Repair -> deterministic Validate -> Final Critic -> Human Review

Bereits fixiert sind:

- kanonischer Effective-Preview-Contract;
- Original -> erfolgreicher Machine-Repair -> Human Edits;
- Quality-Snapshot und Whole-Preview-CAS;
- kurze persistierte Step-Reservierung vor Provider-Aufruf;
- höchstens je ein `initial_critic`, `repair`, `final_critic` pro Generation;
- Repair atomar nur auf explizit freigegebenen Targets;
- vollständiges Verwerfen ungültiger Repair-Payloads;
- Failure Preservation des letzten deterministisch validen Preview-Zustands;
- maximal vier Modellaufrufe inklusive Generation;
- keine automatische Domain-/Gate-Entscheidung.

Relevante bestehende Tests:

- `tests/test_evaluated_solution_workflow_critic_contract.py`;
- `tests/test_evaluated_solution_workflow_initial_critic.py`;
- `tests/test_evaluated_solution_workflow_targeted_repair.py`;
- `tests/test_evaluated_solution_workflow_repair_contract.py`;
- `tests/test_evaluated_solution_workflow_final_critic.py`;
- `tests/test_evaluated_solution_workflow_snapshot.py`;
- `tests/test_evaluated_solution_workflow_quality_runs.py`;
- `tests/test_evaluated_solution_workflow_security_gate_regression.py`;
- `tests/test_evaluated_solution_workflow_completion_regression.py`;
- `tests/test_evaluated_solution_workflow_preview_ui.py`.

## Bewertungsstatus der Matrix

- **Vorhanden:** Das Kriterium ist bereits direkt durch einen autoritativen Test/Contract nachgewiesen. #213 darf diesen Nachweis wiederverwenden.
- **Teilweise:** Die technische Invariante ist bereits abgesichert, aber der explizite fachlich lesbare #213-Fall oder der kombinierte Nachweis fehlt noch.
- **Offen:** Der von #213 verlangte Nachweis existiert auf `main` noch nicht in ausreichender Form.

## Traceability – Architecture Advisor

| ID | Anforderung aus #213 | Bestehender Nachweis auf `main` | Status | Geplante Schließung |
|---|---|---|---|---|
| A01 | Kanonischer Fall `No LLM required` | `test_canonical_mode_labels_are_stable`; 81er-Fixture | Teilweise | AP2 fachlich benannter Fixture-Fall, AP3 explizite Regression |
| A02 | Kanonischer Fall `Controlled LLM` | `test_canonical_mode_labels_are_stable`; Explainability-Test; 81er-Fixture | Teilweise | AP2/AP3 |
| A03 | Kanonischer Fall `LLM Workflow` | `test_canonical_mode_labels_are_stable`; Explainability-Test; 81er-Fixture | Teilweise | AP2/AP3 |
| A04 | Kanonischer Fall `Bounded Agent` | `test_canonical_mode_labels_are_stable`; Explainability-Test; 81er-Fixture | Teilweise | AP2/AP3 |
| A05 | Kanonischer Fall `Assessment open` wegen entscheidungsrelevanter Unsicherheit | `test_golden_explainability_texts_for_open_assessment`; vollständige 81er-Matrix enthält `Unklar`-Kombinationen | Teilweise | AP2/AP3 mit fachlich benanntem Fall |
| A06 | Einfachere Lösung ausreichend und semantisches LLM gleichzeitig erforderlich | produktiver Classifier erkennt `contradictory_answers`; 81er-Matrix deckt Kombination ab | Teilweise | AP2/AP3 als expliziter adversarialer Fall |
| A07 | Mehrere feste KI-Schritte und dynamische Orchestrierung gleichzeitig | produktiver Classifier erkennt `contradictory_answers`; 81er-Matrix deckt Kombination ab | Teilweise | AP2/AP3 |
| A08 | Einfachere Lösung reicht nicht und semantisches Reasoning ebenfalls nicht | produktiver Classifier liefert `architecture_boundary_unclear`; 81er-Matrix deckt Kombination ab | Teilweise | AP2/AP3 |
| A09 | Dynamische Toolwahl behauptet, obwohl Ablauf ansonsten vollständig fest ist | Widerspruchscontract `multiple_steps=yes` + `dynamic=yes` vorhanden | Teilweise | AP2/AP3 mit fachlichem Narrativ statt nur Antworttupel |
| A10 | Alle vier Antworten `Unklar` | 81er-Matrix deckt die Kombination ab; `Unklar`-Vervollständigungslogik ist produktiv getestet | Teilweise | AP2/AP3 als benannter Referenzfall |
| A11 | Hohe inhaltliche Komplexität allein darf nie `Bounded Agent` ergeben | Komplexität ist kein Advisor-Input; `Bounded Agent` verlangt produktiv dynamische Orchestrierung | Teilweise | AP2/AP3 mit explizitem komplexen, aber festen Fall |
| A12 | Dynamischer Gegenkontrollfall ergibt tatsächlich `Bounded Agent` | kanonischer Bounded-Agent-Test vorhanden | Teilweise | AP2/AP3 als fachlicher Gegenkontrollfall |
| A13 | Widersprüche dürfen nicht durch Regelreihenfolge verdeckt werden | `_classify_complete` prüft Konflikt/Boundary vor positiver Klassifikation; 81er-Vertrag | Vorhanden | AP3 referenziert bestehenden Contract zusätzlich in der Testmatrix |
| A14 | `No LLM required` niemals bei semantischem Reasoning=`yes` | `test_no_llm_required_never_occurs_when_semantic_reasoning_is_yes` | Vorhanden | keine neue Produktlogik |
| A15 | Sichtbare `Warum / Warum kein Agent?`-Begründungen | Golden-Explainability-Tests und UI-Tests aus #211 | Vorhanden | AP3 bindet relevante Erwartung an #213-Fixture |
| A16 | Anzahl getesteter, klassifizierter und offener Fälle dokumentieren | kein #213-spezifisches dauerhaftes Statistikartefakt | Offen | AP3 committed Assessment-open-Bericht |
| A17 | Reason Codes der offenen Referenzfälle sichtbar dokumentieren | Reason Codes sind technisch vorhanden, aber keine #213-Auswertung | Offen | AP3 |
| A18 | Keine künstliche Mindest-Klassifikationsquote | Workplan #213 fixiert ausdrücklich keine Quote | Vorhanden | AP3-Bericht macht dies sichtbar |
| A19 | V1 als expert-informed und nicht breit empirisch kalibriert dokumentieren | #211-Workplan beschreibt expert-informed; #213 verlangt expliziten Abschlussnachweis | Teilweise | AP3 und AP7 |

## Traceability – Critic und Repair

| ID | Anforderung aus #213 | Bestehender Nachweis auf `main` | Status | Geplante Schließung |
|---|---|---|---|---|
| C01 | Nahezu identische Optionen / fehlende Distinctiveness | Criterion `distinctiveness`; Cross-Option-Target-Contract getestet | Teilweise | AP2 Fixture-Fall, AP4 explizite semantische Regression |
| C02 | Fehlender Bottleneck-Bezug | Criterion `bottleneck_fit`; strukturierter Beispiel-Finding-Contract vorhanden | Teilweise | AP2/AP4 |
| C03 | Qualitative unbelegte Aussage | `evidence_discipline`/`grounding_consistency` vorhanden; Source-ID-Contract vorhanden | Teilweise | AP2/AP4 expliziter Fall |
| C04 | Korrekt ausgewiesene Annahme/offene Evidenz als positive Kontrolle | Preview-/Critic-Messages führen `assumptions` und `open_evidence`; kein expliziter #213-Positivfall | Offen | AP2/AP4 |
| C05 | Unnötige KI-/Architekturkomplexität | Criterion `complexity_proportionality` ist fest im V1-Contract | Teilweise | AP2/AP4 mit explizitem Fall |
| C06 | Strukturierte Finding-Referenz auf Option/Feld/Evidenz | Critic-Schema, `validate_solution_critic_payload`, Source-ID- und Cross-Option-Target-Tests | Vorhanden | AP4 Traceability konsolidieren |
| C07 | Critic-Ausfall lässt valide Original-Preview nutzbar | `test_provider_failure_preserves_valid_generation_preview_and_consumes_attempt` sowie Completion-Regression | Vorhanden | keine neue Produktlogik |
| C08 | Repair-Ausfall verändert Original-Preview nicht | `test_provider_failure_preserves_original_preview_and_consumes_one_shot` | Vorhanden | keine neue Produktlogik |
| C09 | Ungültiger deterministischer Repair-Contract wird vollständig verworfen | `test_repair_with_invalid_quantitative_claim_is_discarded_atomically` sowie Target-Contract-Tests | Vorhanden | AP4/AP5 nur referenzieren |
| C10 | Kollidierende Human Edits werden nicht automatisch repariert/überschrieben | `test_human_edit_during_provider_call_wins_and_stale_repair_is_discarded`; Human-Overlay-Priorität | Vorhanden | AP5 kombiniert mit Invarianz |
| C11 | Exakt ein zulässiger Repair-Lauf | Repair-Step-Eindeutigkeit und `repair_attempt_consumed`; ein Provider-Aufruf kann mehrere explizite Targets behandeln | Vorhanden | AP5 ergänzt echte Nebenläufigkeit |
| C12 | Kein zweiter Repair nach Final Critic | `test_remaining_final_findings_end_in_human_review_without_second_repair` | Vorhanden | AP5/Finalmatrix referenzieren |
| C13 | Verbleibendes Finding nach Final Critic -> Human Review | derselbe Final-Critic-Test; kein zweiter Repair möglich | Vorhanden | AP4/AP8 dokumentieren |
| C14 | Final Critic genau einmal | `test_final_critic_uses_same_structured_contract_once_and_preserves_repaired_preview` | Vorhanden | keine neue Produktlogik |
| C15 | Final-Critic-Ausfall bewahrt reparierte Preview | `test_final_critic_provider_failure_preserves_preview_and_consumes_attempt` | Vorhanden | keine neue Produktlogik |
| C16 | Maximal vier Modellaufrufe inklusive Generation | #212-Contract begrenzt Step Types; Einzeltests sichern One-Shot je Step, aber kein gemeinsamer #213-Aufrufzähler | Teilweise | AP6 integrierter Call-Order-/Call-Cap-Nachweis |
| C17 | Critic ist strukturiert testbar, aber kein Domain-/Governance-Gate | Critic-Schema ohne Score/Severity/Recommendation; Prompt verbietet Ranking/Preferred Solution; Gate-Regression vorhanden | Vorhanden | AP4/AP8 konsolidieren |

## Traceability – Gate-Invarianz und Rückwärtskompatibilität

| ID | Anforderung aus #213 | Bestehender Nachweis auf `main` | Status | Geplante Schließung |
|---|---|---|---|---|
| G01 | Advisor verändert `feasibility` nicht | `test_saving_advisor_has_no_selection_gate_or_downstream_side_effects` snapshotet SolutionOption-Felder | Vorhanden | AP5 Gesamtmatrix |
| G02 | Advisor verändert `integration_effort` nicht | derselbe Advisor-Invarianztest | Vorhanden | AP5 |
| G03 | Advisor verändert `evaluation_status` nicht | derselbe Advisor-Invarianztest | Vorhanden | AP5 |
| G04 | Advisor verändert `recommendation` nicht | derselbe Advisor-Invarianztest | Vorhanden | AP5 |
| G05 | Advisor erzeugt keine Process Validation / Selection / Use Case / Governance / Delivery / Lifecycle-Side-Effects | `_side_effect_counts` in `test_architecture_advisor_invariance.py` | Vorhanden | AP5 |
| G06 | Critic/Repair verändern geschützte Domain-/Gate-Zustände nicht | `test_complete_quality_path_preserves_domain_gate_and_adoption_boundaries`; Completion-Regression | Vorhanden | AP5 kombinierter Vorher-/Nachher-Nachweis |
| G07 | Adoption nach Quality Control setzt keine durch Critic erfundene Bewertung | `test_quality_result_never_blocks_adoption_or_creates_gate_state`: DRAFT, NOT_ASSESSED, CANDIDATE bleiben Defaults | Vorhanden | AP5/AP8 referenzieren |
| G08 | Bestehende manuelle SolutionOptions bleiben kompatibel | Advisor-Invarianz verwendet regulär persistierte manuelle SolutionOptions; kein expliziter kombinierter #213-Kompatibilitätstest | Teilweise | AP5 |
| G09 | Bestehende normale Block-7-Previews bleiben kompatibel | gesamte #212-Testfamilie baut reguläre Block-7-Previews ohne #213-Metadaten | Teilweise | AP5 expliziter Rückwärtskompatibilitätsfall |

## Traceability – Cross-Feature-Isolation

| ID | Anforderung | Bestehender Nachweis auf `main` | Status | Geplante Schließung |
|---|---|---|---|---|
| X01 | Advisor-Mode beeinflusst Critic-/Repair-Verhalten nicht | keine explizite Isolation zwischen beiden Fähigkeiten | Offen | AP4 |
| X02 | Critic/Repair verändern Advisor-Antworten, Mode, Reason Codes oder Version nicht | keine explizite Isolation zwischen beiden Fähigkeiten | Offen | AP4 |

## Traceability – Concurrency und One-Shot

| ID | Anforderung | Bestehender Nachweis auf `main` | Status | Geplante Schließung |
|---|---|---|---|---|
| Q01 | Wiederholter sequenzieller Repair erzeugt keinen zweiten Provider-Aufruf | `repair_attempt_consumed` und Unique-Step-Contract | Vorhanden | AP5 referenzieren |
| Q02 | Zwei nahezu gleichzeitige Repair-Trigger erzeugen höchstens einen Provider-Aufruf | Reservierungs-/Unique-Constraint-Design existiert, aber kein expliziter echter Paralleltest identifiziert | Offen | AP5 transactionale Concurrency-Regression |
| Q03 | Kein doppelter Machine-Repair bei Race | technisch durch Step-/CAS-Design intendiert, expliziter Race-Nachweis fehlt | Offen | AP5 |

## Traceability – Real-DEMO E2E

| ID | Anforderung aus #213 | Bestehender Nachweis auf `main` | Status | Geplante Schließung |
|---|---|---|---|---|
| R01 | Bestehende Prozess-/Lösungsdaten als Ausgangslage | separate Demo-/Block-7-Testdaten existieren, kein gemeinsames #213-Szenario | Offen | AP2 Fixture, AP6 E2E |
| R02 | Advisor auf mehreren unterschiedlich gelagerten Fällen | Advisor-Unit-/UI-Tests vorhanden, nicht in gemeinsamem Real-DEMO | Offen | AP6 |
| R03 | sichtbare `Warum / Warum kein Agent?`-Begründungen im Real-DEMO | separat vorhanden | Teilweise | AP6 |
| R04 | mindestens ein bewusst offener/widersprüchlicher Advisor-Fall | separat durch Matrix-Contract abgedeckt | Teilweise | AP6 |
| R05 | valide Block-7-Generierung | Block-7- und #212-Tests vorhanden | Teilweise | AP6 gemeinsamer Pfad |
| R06 | deterministische Validierung vor Critic | #212-Security-Regression weist invalid generation vor Critic zurück | Vorhanden technisch | AP6 Reihenfolge explizit protokollieren |
| R07 | strukturierte Critic-Findings | Critic-Contract/Initial-Critic-Tests vorhanden | Vorhanden technisch | AP6 gemeinsamer Pfad |
| R08 | einmaliger gezielter Repair | Targeted-Repair-Tests vorhanden | Vorhanden technisch | AP6 gemeinsamer Pfad |
| R09 | erneute deterministische Validierung nach Repair | #212 Repair-Contract prüft effektiven Payload vollständig | Vorhanden technisch | AP6 gemeinsamer Pfad |
| R10 | Final Critic und Human Review | Final-Critic-Tests vorhanden | Vorhanden technisch | AP6 gemeinsamer Pfad |
| R11 | unveränderte fachliche Gates über gesamten Real-DEMO | separate Advisor- und Quality-Invarianz vorhanden | Teilweise | AP6 vollständiger Vorher-/Nachher-Nachweis |
| R12 | deterministische Providergrenze | bestehende Tests patchen Provider deterministisch, aber kein zentraler input-stabiler #213-Stub | Offen | AP6 |
| R13 | identischer Provider-Input -> identischer Output | nicht explizit als #213-Contract getestet | Offen | AP6 |
| R14 | Provider-Stub fail-closed bei unerwartetem Input | kein zentraler #213-Stub | Offen | AP6 |
| R15 | Provider-Aufrufreihenfolge und maximale Aufrufzahl sichtbar | Einzeltests zählen Calls; gemeinsame Reihenfolge fehlt | Offen | AP6 |
| R16 | ausschließlich synthetische/anonymisierte Real-DEMO-Daten | bestehende Tests sind synthetisch; neue #213-Fixture fehlt | Teilweise | AP2 Schema/Daten, AP6 Nutzung |
| R17 | harter CI-Zeitrahmen für gezielten E2E | normale CI besitzt keinen #213-E2E-Step | Offen | AP6 `timeout-minutes: 3` |

## Traceability – Drift und Abschluss

| ID | Anforderung aus #213 | Bestehender Nachweis auf `main` | Status | Geplante Schließung |
|---|---|---|---|---|
| D01 | reproduzierbare #213-Referenzdaten / Fixture | 81er-Advisor-Fixture vorhanden, aber keine kombinierte #213-Fixture | Offen | AP2 |
| D02 | Fixture besitzt explizites Schema und Version | bestehende 81er-Fixture hat eigenen Contract, keine #213-Schema-Datei | Offen | AP2 |
| D03 | fachlich relevante Advisor-Decision-Contracts gegen Drift geschützt | 81er-Matrix + Classifier-Test bereits vorhanden | Vorhanden | AP7 in Gesamtvertrag referenzieren |
| D04 | Critic-/Repair-Contracts gegen Drift geschützt | versionierte Prompt-/Schema-Contracts und Contracttests vorhanden | Teilweise | AP7 #213-Gesamtdrift konsolidieren |
| D05 | Assessment-open-Häufigkeit dauerhaft sichtbar | kein Artefakt | Offen | AP3 |
| D06 | dokumentierte Testmatrix | dieses AP1-Dokument bildet Startmatrix, finale Ergebnisbelegung fehlt naturgemäß | Teilweise | AP8 finalisieren |
| D07 | bekannte methodische Grenzen dokumentiert | #211/#212-Workplans dokumentieren Grenzen; #213-Abschlussdokument fehlt | Teilweise | AP7/AP8 |
| D08 | keine Beschönigung von `Assessment open` | Workplan verbietet Erfolgsquote; noch kein Ergebnisbericht | Teilweise | AP3/AP7 |
| D09 | vollständige Repository-CI grün | Workplan-PR #265: PR-CI #1414 grün; Merge-main-CI #1415 grün | Vorhanden als Startbaseline | AP8 finaler CI-Nachweis |

## Ergebnis der AP1-Inventur

### Bereits stark abgesichert

Die bestehende Implementierung deckt den technischen Kern der beiden Features bereits weitgehend ab:

- vollständiger 81-Kombinationen-Advisor-Contract;
- deterministische Konflikt-/Boundary-/Unklar-Logik;
- Explainability und Advisor-Gate-Invarianz;
- strukturierter Critic-Contract mit fünf fixen Kriterien;
- Snapshot-/CAS- und One-Shot-State-Machine;
- atomarer, target-gebundener Repair;
- Failure Preservation für Critic, Repair und Final Critic;
- kein zweiter Repair nach Final Critic;
- vorhandene Quality-Workflow-Gate-Invarianz.

#213 muss diese Mechanismen deshalb überwiegend nicht neu implementieren.

### Echte #213-Nachweislücken

Die wesentlichen noch offenen Punkte sind:

1. eine versionierte, schema-validierte und fachlich lesbare #213-Fixture mit zwölf Advisor- sowie Critic-/Repair-Fällen;
2. ein dauerhaft eingechecktes Assessment-open-Statistikartefakt;
3. explizite semantische Acceptance-Fälle für Distinctiveness, Bottleneck, unbelegte Aussagen, positive Annahme/offene Evidenz und Complexity Proportionality;
4. Cross-Feature-Isolation Advisor <-> Quality Workflow in beide Richtungen;
5. echter Concurrency-Nachweis für zwei nahezu gleichzeitige Repair-Trigger;
6. ein einziger zusammenhängender Real-DEMO-E2E über Advisor und den vollständigen Quality-Pfad;
7. ein zentraler input-deterministischer, fail-closed Provider-Stub mit Call-Order-/Call-Cap-Nachweis;
8. gezieltes CI-Zeitbudget für den #213-E2E;
9. konsolidierter #213-Driftvertrag und finaler Abschlussbericht.

### Keine aktuell identifizierte Produktlücke in AP1

Auf Basis der Contract-Inventur ist in AP1 keine konkrete Verletzung von #210/#211/#212 identifiziert worden, die eine Änderung an produktiver Business-Logik rechtfertigen würde.

Die folgenden APs beginnen daher mit Test-/Fixture-/Dokumentationsarbeit. Produktionscode wird nur geändert, wenn ein nachfolgender Regressionstest eine konkrete Contract-Verletzung reproduzierbar nachweist.

## AP-Zuordnung der offenen Nachweise

- **AP2:** versionierte JSON-Fixture, JSON-Schema, synthetische/anonymisierte Real-DEMO-Daten, früher struktureller Drift-Schutz.
- **AP3:** zwölf Advisor-Fälle, Assessment-open-Auswertung und reproduzierbares Statistikartefakt.
- **AP4:** semantische Critic-/Repair-Fälle und Cross-Feature-Isolation.
- **AP5:** kombinierte Gate-/Backward-Compatibility-Invarianz und echter Repair-Concurrency-Nachweis.
- **AP6:** gemeinsamer Real-DEMO-E2E, deterministischer Provider, Call Order/Cap und gezieltes CI-Timeout.
- **AP7:** konsolidierter Contract-/Fixture-Drift und methodische Grenzen.
- **AP8:** finale Traceability-/Testmatrix, Abschlussnachweise und vollständige Repository-CI.

## CI-Baseline vor AP1

Der isolierte Workplan-PR #265 wurde erst nach vollständig grünem PR-CI-Lauf #1414 gemergt. Der anschließende `main`-CI-Lauf #1415 auf Merge-Commit `c092752e857604b718bc6a683a75f856690eca43` war ebenfalls vollständig grün.

Diese Baseline ist kein Ersatz für den finalen CI-Nachweis in AP8, sondern dokumentiert den sauberen Startzustand von #213.
