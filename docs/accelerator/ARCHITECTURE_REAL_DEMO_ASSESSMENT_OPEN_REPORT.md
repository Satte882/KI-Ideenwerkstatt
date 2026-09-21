# Architecture Real-DEMO - Assessment-open-Bericht

Issue: #213  
Fixture: `tests/fixtures/architecture_real_demo_v1.json`  
Ruleset: `architecture-advisor-v1`

## Ergebnis des fixierten Referenzsets

- Getestete Advisor-Fälle: **12**
- Klassifizierte Fälle: **6**
- `Assessment open`: **6**

### Mode-Verteilung

- `no_llm_required` (No LLM required): **1**
- `controlled_llm` (Controlled LLM): **1**
- `llm_workflow` (LLM Workflow): **2**
- `bounded_agent` (Bounded Agent): **2**
- `assessment_open` (Assessment open): **6**

### Reason Codes der offenen Fälle

- `contradictory_answers`: **3**
- `insufficient_information`: **2**
- `architecture_boundary_unclear`: **1**

### Offene Fälle

- `advisor_canonical_assessment_open` - Unklare Zahl benötigter KI-Schritte: `insufficient_information`
- `advisor_adversarial_simpler_and_semantic` - Deterministisch ausreichend und LLM zugleich erforderlich: `contradictory_answers`
- `advisor_adversarial_fixed_steps_and_dynamic` - Fester Mehrschritt und dynamische Orchestrierung zugleich: `contradictory_answers`
- `advisor_adversarial_taxonomy_boundary` - Keine einfachere Lösung und kein semantisches Reasoning: `architecture_boundary_unclear`
- `advisor_adversarial_dynamic_claim_fixed_flow` - Dynamische Toolwahl bei vollständig festem Ablauf behauptet: `contradictory_answers`
- `advisor_adversarial_all_unclear` - Alle entscheidenden Antworten unklar: `insufficient_information`

## Kontrollnachweise

- Hohe inhaltliche Komplexität allein erzeugt keinen Agenten-Ausgang: `advisor_adversarial_high_complexity_fixed_workflow` ist als `high` markiert und ergibt `llm_workflow`.
- Die dynamische Gegenkontrolle zeigt die eigentliche Agentenbedingung: `advisor_adversarial_dynamic_countercontrol` ist als `low` markiert und ergibt `bounded_agent`.
- Widersprüchliche Anforderungen werden als `Assessment open` ausgewiesen; sie werden nicht durch eine spätere positive Regel verdeckt.

## Methodische Einordnung

Die V1-Logik ist **expert-informed** und bewusst als kleine, nachvollziehbare Entscheidungslogik ausgelegt. Sie ist **noch nicht empirisch an einer breiten Menge realer Unternehmensfälle kalibriert**.

Für dieses Referenzset gibt es **keine Mindest-Klassifikationsquote und kein Erfolgsziel**. `Assessment open` ist ein beabsichtigter transparenter Ausgang, wenn Informationen fehlen, Anforderungen widersprüchlich sind oder der Fall außerhalb der V1-Taxonomie liegt.

Die dokumentierten Häufigkeiten beschreiben ausschließlich das fixierte #213-Referenzset. Sie sind keine empirische Aussage über die Verteilung von Architekturklassen in realen Unternehmen.
