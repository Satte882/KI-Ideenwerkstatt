# Gap-Analyse zu Issue #311

**Basis:** `main` auf Merge-Commit `1636c62` einschließlich PR #306
**Scope:** Delivery Package, Readiness, Architekturartefakte, Evaluation, KI-spezifische Qualitätsaussagen, Latenz/Retry und Retention

## Ergebnis je Pflichtfrage

1. **AP1 und PR #306:** `evaluate_delivery_readiness()` erzeugt bei einer kollabierten fachlichen/technischen Bestätigung den Blocker `INDEPENDENT_CONFIRMATION_MISSING`. `mark_package_ready()` und `hand_over_package()` rufen dieselbe serverseitige Blockerprüfung auf. Eine unabhängige zweite Person kann die bestehende Sektionsbestätigung vervollständigen. Der reguläre Schreibpfad ist damit serverseitig vollständig geschlossen; es wird keine zweite Gate-Engine benötigt.
2. **Status, Findings und Export:** Der persistierte Status stammt aus `DeliveryPackage.status` und den Transitionsfunktionen in `delivery.services`. Die fachlichen Readiness-Findings stammen aus `delivery.readiness.evaluate_delivery_readiness()`. Vor dem Review-Hardening wurde `TECHNICAL_OWNER_INACTIVE` jedoch nur als synthetischer UI-Befund in `delivery.actions` ergänzt und war damit nicht Teil von Export, Status, Handover und Pilot-Gate. Diese Abweichung wird beseitigt. UI und Markdown-Export lasen Status und Findings außerdem getrennt; ein inkonsistenter Alt-/Manipulationsbestand konnte dadurch gleichzeitig „Übergeben“ und einen Blocker zeigen.
3. **Architekturartefakte:** Wiederverwendbar sind `system_context`, `architecture_decisions` sowie das bestehende One-to-one-Objekt `DeliveryArchitectureArtifacts` mit Systemlandschaft, Zielkomponenten/Systemverantwortung, Datenflüssen, Datenqualität/Zugriff, Integrationsverträgen, Integrationsbetrieb und optionaler `artifacts_url`. Ein neues Architektur-Repository ist nicht erforderlich.
4. **Evaluation und Qualität:** Wiederverwendbar sind `acceptance_criteria`, `test_scenarios` und `measurement_plan`; Use Cases liefern zusätzlich Zielmetrik, Baseline, Zielwert, Messmethode und Messzeitraum. Es fehlte die verbindliche gemeinsame Interpretation von Prozentwert, Testpopulation, Stichprobengröße, Unsicherheit und gezielten kritischen Fehlerklassen.
5. **Confidence:** Bestehende Bewertungs-Confidence (`DecisionAssessment`) beschreibt die Evidenz-/Entscheidungsqualität und ist kein Output-Confidence-Score. Im Delivery Package gab es nur freie Anforderungen in Akzeptanz, Human Oversight und NFR; eine Output-Typ-Semantik fehlte.
6. **Timeout, Retry und Latenz:** Die Accelerator-Runtime besitzt technische Provider-/LLM-Timeouts und einzelne Pfade verhindern Retries nach Timeout. Delivery-Inhalte werden jedoch als fachlicher Snapshot frei formuliert; eine Prüfung auf den Widerspruch „ein Versuch verbraucht das gesamte Nutzerbudget plus synchrone Retries“ fehlte.
7. **Audit und Retention:** Wiederverwendbar sind `logging_and_audit`, `security_privacy_requirements` und `operations_and_support`. Die Accelerator-Capture-Retention ist eine separate Runtime-Regel und nicht die Retention des übergebenen Zielsystems. Im Delivery-Export fehlte eine verbindliche Unterscheidung von Metadaten, Rohprompts/-inputs, Dokumenten, personenbezogenen/sensiblen Daten und technischen Logs.
8. **Änderungstypen:** AP1 benötigt eine gemeinsame abgeleitete Statussicht und Regressionstests. AP2 benötigt nur Darstellungs-/Exportklarheit auf bestehenden Architekturfeldern. AP3–AP6 benötigen Methodik, bessere Vorbelegung und gezielte semantische Readiness-Regeln auf bestehenden Textfeldern. Es sind weder Datenmodellmigrationen noch eine neue Plattform oder parallele Methodik erforderlich.

## Umsetzungsentscheidung

- Die serverseitige Readiness bleibt die einzige Gate-Quelle.
- Auch ein inaktiver Technical Owner wird in dieser kanonischen Gate-Quelle geprüft; UI-Sonderfindings entfallen.
- Ein übergebener Datensatz mit aktuellen Blockern gilt in Serverableitungen, UI und Export nicht als erfolgreich übergeben, sondern als inkonsistenter Bestand.
- Bestehende Delivery-Felder werden geschärft; neue Pflichtfelder und neue Statuswerte werden vermieden.
- Externe Architekturlinks bleiben optional, wenn die erforderlichen Sichten direkt im Package dokumentiert sind.
- Semantische Regeln blockieren konkrete fachliche Widersprüche bei Confidence, Latenz/Retry und Retention. Retention wird je Datenkategorie nur mit Zweck und konkreter Lösch-/Aufbewahrungsregel akzeptiert. Fehlender statistischer Kontext wird als sichtbare Warnung ausgewiesen, weil die angemessene Nachweistiefe von Metrik, Risiko und Population abhängt.
