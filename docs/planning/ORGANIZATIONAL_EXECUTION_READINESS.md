# Organizational Execution Readiness – Research Result

Stand der Verifikation: `main @ 6bb6a396c10db663adf2e38bc0e95739aba977f7`

## Verdict

**Partially.** Es ist keine neue Transformation-Readiness-Schicht erforderlich. Als generische, entscheidungsrelevante Restlücke ist nur **Funding Evidence** bestätigt.

Für Business Capacity und IT / Delivery Capacity ist dagegen **kein generisches Capacity-Gate nachgewiesen**. Die vorhandenen Artefakte belegen Verantwortung, Scope, Vorbereitung und Übergabereife, aber nicht pauschal zugesagte verfügbare Kapazität. Zusätzliche Capacity-Evidence ist deshalb nur bei einer konkret benannten Abhängigkeit des nächsten Schritts gerechtfertigt.

| Faktor | Ergebnis | Begründung |
| --- | --- | --- |
| Funding | **minimal evidence gap** | `one_time_cost` / `recurring_cost` beschreiben Kosten, aber keine Finanzierung für den konkreten Pilot- oder Produktivscope. |
| Business Capacity | **kein generisches Capacity-Gate nachgewiesen** | `DeliveryPackage.users_and_scenarios`, `measurement_plan` sowie Business-Bestätigungen für `scope_and_users`, `acceptance_and_measurement` und `delivery_control` belegen Scope und fachliche Vorbereitung. Sie belegen keine pauschal verfügbare Kapazität. |
| IT / Delivery Capacity | **kein generisches Capacity-Gate nachgewiesen** | `technical_owner`, technische Section-Confirmations, `operations_and_support`, Delivery Readiness und Handover belegen technische Verantwortung und Übergabereife. Sie belegen keine pauschal verfügbare Umsetzungskapazität. |
| Organizational Adoption / Rollout | **not generically decision-relevant** | `users_and_scenarios` und Scope-Evidence beschreiben Nutzer und Nutzung. Training, Rollout oder Prozessübernahme sind nur dann zusätzliche Voraussetzungen, wenn der konkrete Entscheidungs-Scope sie tatsächlich benötigt. |

## Existing Evidence Paths

### Business Capacity

Vorhanden sind insbesondere:

- `DeliveryPackage.users_and_scenarios`
- `DeliveryPackage.measurement_plan`
- `DeliverySectionReview` für `scope_and_users` und `acceptance_and_measurement` mit erforderlicher Business-Bestätigung
- `DeliverySectionReview.delivery_control` mit Business- und Technical-Bestätigung

Diese Contracts belegen, dass fachlicher Scope und Validierungs-/Delivery-Inhalt bestätigt wurden. Sie enthalten **keine generische Zusage verfügbarer Personentage oder Stunden**.

Konsequenz: kein neues globales Capacity-Feld. Falls ein Pilot z. B. zwingend zwei Key User für sechs Wochen benötigt, muss diese konkrete Abhängigkeit im jeweiligen Scope nachgewiesen sein.

### IT / Delivery Capacity

Vorhanden sind insbesondere:

- `DeliveryPackage.technical_owner`
- technische Bestätigungen für `solution_direction`, `architecture_and_data`, `requirements_and_governance` und `delivery_control`
- `DeliveryPackage.operations_and_support`
- Delivery Readiness
- verbindlicher Handover des Delivery Packages

Diese Contracts belegen technische Verantwortung, bestätigten Delivery-Inhalt und Übergabereife. Sie beweisen **nicht**, dass für jede später noch benötigte Umsetzung, Fehlerbehebung oder Betriebsleistung beliebig Kapazität verfügbar ist.

Konsequenz: kein generisches IT-Capacity-Gate. Eine konkrete noch ausstehende technische Leistung bleibt eine scopebezogene Dependency.

## Kontrastszenarien

| Szenario | Funding | Business Capacity | IT / Delivery Capacity | Adoption / Rollout |
| --- | --- | --- | --- | --- |
| Begrenzter Offline-Pilot | Finanzierung bestätigt oder nachvollziehbar nicht erforderlich | kein generisches Gate; konkrete benötigte Test-/Validierungsmitwirkung muss im Scope erkennbar sein | kein generisches Gate; Handover deckt die bereitgestellte Lösung ab | kein generisches Rollout-Gate |
| Pilot mit IT-/Betriebsbedarf | Finanzierung bestätigt oder nachvollziehbar nicht erforderlich | konkrete fachliche Mitwirkung nur dann zusätzliche Voraussetzung, wenn der Pilot sie benötigt | konkrete Betriebs-/Integrations-/Support-Abhängigkeit muss nachgewiesen sein | nur konkrete Nutzer-/Enablement-Abhängigkeiten |
| Produktiver Rollout | Finanzierung für Produktivscope bestätigt oder nachvollziehbar nicht erforderlich | keine pauschale Capacity-Annahme; nur konkret benötigte Mitwirkung | Technical Owner, Support und Go-live-Gates plus konkrete noch offene technische Dependencies | Rollout/Training nur wenn für diesen Scope tatsächlich erforderlich |

## Funding Contract

Funding wird **nicht** als Budgetplanung in KI-Ideenwerkstatt modelliert.

Der bestehende Lifecycle-Review speichert ausschließlich den für die Entscheidung verwendeten Nachweis:

- `unknown` / leer
- `satisfied` – erfüllt oder verbindlich zugesagt
- `open` – offen / nicht zugesagt
- `not_required` – für diesen Scope nicht erforderlich

Für `satisfied` verlangt das System einen nicht leeren Evidence-Text. Für `not_required` verlangt es eine Begründung. `unknown` und `open` blockieren nur `START_PILOT` bzw. `GO_LIVE`.

Die Anwendung prüft **nicht semantisch**, ob der Evidence-Text eine echte Budgetfreigabe darstellt. Diese fachliche Belastbarkeit verantwortet die entscheidende Person.

Die Evidence soll deshalb nachvollziehbar erkennen lassen:

- zuständige bestätigende Stelle oder externe Source of Truth,
- relevanten Pilot- oder Produktivscope,
- soweit relevant den Zeitraum beziehungsweise Gültigkeitsstand.

Der Review-Command bestimmt die Lifecycle-Phase. Reviewer und Review-Zeitpunkt dokumentieren, **wer die Lifecycle-Entscheidung getroffen hat und wann**; sie beweisen nicht automatisch Finanzierungsbefugnis.

## DDD-Light

Owner der Lifecycle-Entscheidung bleibt **Use Case Steering**. Die eigentliche Budget-/Finanzierungsquelle kann extern liegen. Das Review besitzt nur den historischen Entscheidungsnachweis.

Es entsteht:

- kein neuer Bounded Context,
- keine neue Journey-Phase,
- keine neue State Machine,
- kein generisches Capacity-/Adoption-Modell.
