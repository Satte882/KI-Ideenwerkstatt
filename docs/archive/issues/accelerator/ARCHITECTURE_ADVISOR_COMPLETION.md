# Architecture Advisor – Abschlussnachweis #211

Stand: 2026-08-09

## Ergebnis

Der Architecture Advisor aus #211 ist als bewusst kleiner, deterministischer Zusatz zur bestehenden `SolutionOption`-Oberfläche umgesetzt. Er klassifiziert ausschließlich aus vier menschlich beantworteten Fragen und verändert weder bestehende Lösungsbewertung noch Auswahl-, Governance-, Delivery- oder Lifecycle-Gates.

Die breitere adversariale und Real-DEMO-End-to-End-Abnahme bleibt gemäß Gesamtarchitektur Aufgabe von #213.

## Abdeckung des V1-Vertrags

| Vertragsbereich | Nachweis |
| --- | --- |
| Konsistenzvertrag und 81 Kombinationen | `tests/test_architecture_advisor_contract.py` und `tests/fixtures/architecture_advisor_matrix_v1.json` |
| Produktiver Classifier gegen alle 81 Fälle | `tests/test_architecture_advisor.py` |
| Q2-Invariante für `No LLM required` | `tests/test_architecture_advisor.py` und `tests/test_architecture_advisor_contract.py` |
| Golden-Texte für Warum / Warum kein Agent / offene Punkte | `tests/test_architecture_advisor.py` |
| 1:1-Persistenz und keine automatische Re-Klassifikation | `tests/test_architecture_advisor_persistence.py` |
| Serverseitige Ableitung, Berechtigungen und Versionsfortschreibung | `tests/test_architecture_advisor_write_path.py` |
| Vier Fragen und sichtbare Explainability in der SolutionOption-UI | `tests/test_architecture_advisor_ui.py` |
| Kompakte Architecture-Mode-Zeile in der Vergleichsansicht | `tests/test_architecture_advisor_invariance.py` |
| Gate- und Side-Effect-Invarianz | `tests/test_architecture_advisor_invariance.py` |
| Querschnittlicher Ruleset-/Surface-Drift-Vertrag | `tests/test_architecture_advisor_completion.py` |

## Drift-Vertrag

V1 ist auf `architecture-advisor-v1` fixiert. Folgende Elemente müssen bewusst gemeinsam geändert werden, wenn die fachliche Regelbasis später angepasst wird:

- Contract-Generator und committed 81er-Fixture;
- produktiver Classifier;
- Persistenz-Default der Ruleset-Version;
- sichtbare Golden-Texte, sofern Reason-Code-Bedeutungen geändert werden;
- exakt vier Antwortfelder und die fünf definierten Architecture Modes.

Bestehende gespeicherte Assessments werden bei einer späteren Ruleset-Änderung nicht automatisch neu berechnet. Eine neue Klassifikation entsteht erst bei ausdrücklichem erneutem Speichern durch einen berechtigten Nutzer.

## Methodische Grenzen von V1

1. **Expert-informed statt gemessen:** Die vier Antworten sind fachliche Einschätzungen. Der Advisor misst weder Modellqualität noch Prozesswirkung noch technische Machbarkeit automatisch.
2. **Begrenzte Taxonomie:** Fälle außerhalb der definierten LLM-Architekturgrenze können als `Assessment open` enden. Insbesondere klassische Optimierung, andere nicht-generative ML-Verfahren oder weitere technische Klassen werden nicht durch zusätzliche versteckte Regeln erzwungen.
3. **Keine automatische Architekturentscheidung:** Der Advisor erzeugt keinen Score, keine automatische Lösungsauswahl, kein GO/NO-GO und keine Multi-Agent-Empfehlung.
4. **Keine neuen Gates:** Assessment und Architecture Mode sind nicht Bestandteil von `comparison_complete` und verändern keine Auswahl-, Process-Validation-, Governance-, Delivery- oder Lifecycle-Gates.
5. **Keine Concurrency-Erweiterung:** Optimistic Locking/CAS ist für V1 ausdrücklich kein Ziel. Das Assessment-Version-Feld dient der Nachvollziehbarkeit, nicht als Sperrmechanismus.
6. **Keine automatische Ruleset-Migration:** Historische Assessments behalten ihren gespeicherten Mode, ihre Reason Codes und ihre Ruleset-Version.
7. **Kein Critic-/Repair-Workflow:** Erweiterte Kritik- oder Reparaturlogik gehört zu #212 und wird durch #211 nicht vorweggenommen.
8. **Keine Real-DEMO-Endabnahme:** Adversariale Fälle und der übergreifende End-to-End-Nachweis von #211/#212 bleiben #213 vorbehalten.

## Entwicklungsnachweis

Die Umsetzung erfolgte sequenziell mit eigenständigen Pull Requests pro Arbeitspaket. Der verbindliche Workplan wurde zuerst in PR #245 fixiert; AP2 bis AP7 wurden anschließend einzeln umgesetzt. AP8 konsolidiert ausschließlich Drift-, Regressions- und Abschlussnachweise und erweitert den Produktscope nicht.

Die vollständige unveränderte Repository-CI ist das abschließende technische Abnahme-Gate dieses Arbeitspakets. #211 wird erst nach vollständig grünem AP8-Lauf geschlossen.
