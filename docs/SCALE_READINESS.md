# Scale Readiness

## Zweck

Scale Readiness ist die kompakte Entscheidungssicht zwischen abgeschlossener Pilot-/Wirkungsvalidierung und produktivem Betrieb.

Sie beantwortet genau eine Managementfrage:

> Ist die validierte Lösung ausreichend belastbar, kontrollierbar und verantwortet, um vom Pilot in den produktiven Regelbetrieb überführt zu werden?

Scale Readiness ist **kein neues Framework**, keine zusätzliche CRISP-ML(Q)-Phase und kein Ersatz für Delivery Readiness, Governance oder den Google ML Test Score.

Der sichtbare Ablauf lautet:

```text
Use Case → Delivery/Handover → Pilot → Wirkung validieren
→ Scale Readiness & Ergebnisentscheidung → Betrieb → Abschluss
```

Scale Readiness liegt damit bewusst **vor** dem Betrieb. Skalierung im Sinne regulärer produktiver Nutzung beginnt erst nach einer positiven, gespeicherten Ergebnisentscheidung.

## Architektur und Sources of Truth

Die bestehende Architektur bleibt führend:

| Prüfaspekt | Führende Quelle |
|---|---|
| Pilotwirkung | `UseCase.metric_*` und Messnachweis |
| Governance | `GovernanceAssessment` und `GovernanceReview` |
| Delivery/Handover | aktuelle verbindlich übergebene `DeliveryPackage`-Version |
| Lifecycle-Entscheidung | bestehendes `Review` gemäß ADR 0007 |
| ML Test Score | externe, aktuelle Erhebung des Delivery-/AI-Teams |
| Release, Rollback, Monitoring, Incident | externe Delivery-/Betriebsnachweise |
| Rollen | bestehender Business Owner und Technical Owner |

KI-Ideenwerkstatt wird damit nicht zum zweiten Delivery-, Observability-, Incident- oder GRC-System. Externe technische Evidenz wird nur in der Version beziehungsweise Referenz erfasst, die der konkreten Managemententscheidung zugrunde lag.

## Die sechs Prüffelder

1. **Pilot-Evidenz / Wirkung** – Wirkungsmessung liegt vor und Pilotumfang, Repräsentativität sowie relevante Fehler-/Ausnahmefälle wurden für den geplanten Produktivscope geprüft.
2. **Daten & Wissen** – der aktuelle ML-Test-Score `Data` bildet die technische Produktionsreife der Daten-/Wissensversorgung ab.
3. **AI-/Systemqualität** – der aktuelle ML-Test-Score `Model`, der projektspezifische Mindestwert und zwingende Einzelprüfungen werden übernommen.
4. **Deployment & technische Robustheit** – Produktivversion, `Infrastructure`-Score sowie praktisch getesteter Rollback beziehungsweise Deaktivierung sind belegt.
5. **Monitoring & Betrieb** – technisches und AI-/fachliches Qualitätsmonitoring, `Monitoring`-Score sowie je Tailoring Incident-/Eskalationsfähigkeit sind belegt.
6. **Verantwortung, Governance & Restrisiko** – bestehende Owner, Support, Human Oversight und formale Governance-Ergebnisse werden wiederverwendet.

Es wird **kein Scale-Gesamtscore** berechnet.

Der Google ML Test Score bleibt unverändert: `Data`, `Model`, `Infrastructure` und `Monitoring` werden aus der bestehenden externen Erhebung übernommen; der niedrigste Kategoriewert ist der bestehende finale ML Test Score.

## Tailoring A/B/C

Die methodischen Tailoring-Stufen aus `DELIVERY_METHODOLOGY.md` werden nicht als neue globale Reife- oder Statusdimension modelliert. Für die konkrete Scale-Entscheidung wird die verwendete Stufe im Review-Snapshot festgehalten.

- **A – kompakt:** Basisnachweise, aktueller ML Test Score, Pilotvalidierung, getesteter Rollback, Monitoring und klare Verantwortung.
- **B – Standard:** zusätzlich insbesondere belastbarer Incident-/Eskalationsprozess.
- **C – erweitert:** zusätzlich Bestätigung der je Relevanz erforderlichen unabhängigen Reviews, Recovery-/Security- und Notfall-/Abschaltnachweise.

Governance-Merkmale mit personenbezogenen, sicherheitskritischen, regulierten oder erheblich wirkenden Entscheidungen legen weiterhin eine methodische Mindeststufe nahe. Eine abweichende Tailoring-Auswahl ist jedoch **Readiness**, nicht pauschales Lifecycle-Enforcement; konkrete erforderliche Governance-Prüfungen bleiben separat serverseitig geschützt.

## Zustände und Entscheidungen

Scale Readiness berechnet ausschließlich einen Evidenzzustand:

- `ready`
- `conditional`
- `not_ready`

Dieser Zustand ist **kein neuer Lifecycle-Status und keine Go-live-Entscheidung**. Er beschreibt, wie vollständig und belastbar die zusammengeführte Readiness-Evidenz ist.

Die sichtbaren Labels lauten:

| Scale-State | Bedeutung |
|---|---|
| `ready` | **Bereit** – keine offenen Readiness-Findings |
| `conditional` | **Bedingt bereit** – dokumentierte Auflagen / Bedingungen sind offen |
| `not_ready` | **Readiness offen** – wesentliche Readiness-Nachweise fehlen oder ein Enforcement-Finding ist sichtbar |

Die verbindliche Lifecycle-Entscheidung bleibt das bestehende `Review`. Ob `GO_LIVE` zulässig ist, entscheidet ausschließlich die kanonische Transition Policy.

Damit gilt bewusst:

> **Readiness beschreibt Entscheidungsreife. Enforcement entscheidet, ob die konkrete Lifecycle-Aktion zulässig ist.**

Ein `not_ready`-Snapshot ist deshalb nicht automatisch gleichbedeutend mit einem serverseitigen `NO-GO`.

## Finding-Typen und Enforcement

Scale Readiness unterscheidet vier Finding-Typen:

| Typ | Bedeutung | Lifecycle-Wirkung |
|---|---|---|
| `enforcement` | verbindliche Voraussetzung für die konkrete Aktion | wird zusätzlich in der kanonischen Transition Policy serverseitig geschützt |
| `readiness` | relevanter offener Nachweis / Qualitätsaspekt | sichtbar, blockiert für sich allein nicht |
| `condition` | bewusste Bedingung / Restrisiko | sichtbar; kann eine verantwortete Ausnahme oder Folgemaßnahme verlangen |
| `advisory` | Hinweis / Traceability | keine Blockierung |

Aktuelle **Enforcement**-Fälle für `PILOT → OPERATION` sind insbesondere:

- erforderliche Governance-Prüfung offen oder fehlgeschlagen,
- ausdrücklich dokumentierte zwingende ML-Test-Score-Einzelprüfung fehlgeschlagen,
- Rollback / Deaktivierung nicht praktisch möglich oder getestet,
- Technical Owner fehlt,
- Support-/Betriebsverantwortung fehlt.

Weitere Scale-Aspekte wie Tailoring-Auswahl, vollständige ML-Test-Score-Dokumentation, Produktivversionsreferenz, Monitoring-Nachweise, Incident-Prozess, generisches Human-Oversight-Textfeld oder erweiterte Tailoring-C-Sammelbestätigung bleiben **Readiness** beziehungsweise **Advisory**, sofern keine konkrete Governance- oder Lifecycle-Regel daraus Enforcement macht.

Der alte Runtime-Wrapper um `use_cases.services.apply_status_transition()` ist nicht Teil des kanonischen Pfads. Lifecycle-Schreibvorgänge laufen über `reviews.services.create_review()`; die dort aufgerufene Transition Policy ist die einzige fachliche Enforcement-Quelle.

## Persistenter Decision-Snapshot

ADR 0007 bleibt unverändert gültig: `Review` ist die einzige führende Entscheidungs- und Historienquelle.

Mit #333 wurde `Review` minimal ergänzt um:

- `scale_readiness_schema_version`
- `scale_readiness_snapshot`

Schema-Version **2** trennt die Finding-Semantik explizit in `enforcement`, `readiness`, `condition` und `advisory`. Historische Snapshots bleiben unverändert erhalten.

Der Snapshot wird **serverseitig erzeugt**. Er enthält keine vollständige Kopie der fachlichen Quellen, sondern nur die entscheidungsrelevanten Referenzen und den damals verwendeten Stand:

- Scale-State und Tailoring,
- Use-Case-/Pilotreferenz und Messnachweis,
- Delivery-Package-ID/-Version und Produktivversion,
- Governance-Review-Referenzen,
- ML-Test-Score-Kategorien, finalen bestehenden ML Score, Mindestwert, Version, Datum und Nachweis,
- offene Kernprüfungen beziehungsweise fehlgeschlagene zwingende Einzelprüfungen,
- Rollback-/Monitoring-/Incident-Nachweisstatus,
- Business-/Technical-Owner-Referenzen,
- Findings zum Entscheidungszeitpunkt.

Spätere Änderungen überschreiben diesen Snapshot nicht. Ein späterer Review erzeugt einen neuen Stand.

## Platzierung und Bedienung im UI

Scale Readiness ist kein zusätzlicher globaler Lifecycle-Status und kein paralleler Workspace. Die Sicht ist in `Wirkung & Betrieb` unter `Ergebnisentscheidung` platziert – nach der Wirkungsmessung und unmittelbar vor `Betrieb`.

Am konkreten Use Case führt die lokale linke Navigation über `Wirkung & Betrieb` in diesen Teilprozess und zeigt die Einordnung `Pilot → Wirkung → Scale Readiness → Betrieb`. Der globale Workspace-Einstieg bleibt zusätzlich erhalten.

Das bestehende Lifecycle-Review zeigt:

- die sechs Prüfdimensionen in fachlicher Reihenfolge;
- eine live aktualisierte, noch nicht gespeicherte Readiness-Vorschau;
- einbezogene Pilot-, Governance-, Delivery-, Rollen- und ML-Test-Score-Evidenz;
- aktuelle Findings mit ihrer Einordnung als Enforcement, Readiness, Bedingung oder Hinweis;
- genau eine konkrete nächste Aktion.

Nach dem Speichern führt der Ablauf zurück zur Ergebnisentscheidung. Dort bleibt der serverseitig erzeugte Snapshot mit Entscheidung, sechs Dimensionen, verwendeter Evidenz und gegebenenfalls Auflagen sichtbar. Die Use-Case-Historie zeigt denselben gespeicherten Entscheidungsstand.

## Legacy und Änderungen nach Go-live

Bestehende `OPERATION`-Use-Cases werden nicht rückwirkend invalidiert und erhalten keinen erfundenen Backfill. Die kanonischen Lifecycle-Guards gelten für zukünftige `Pilot → Betrieb`-Übergänge; Readiness-Findings bleiben davon semantisch getrennt.

Ein später geänderter Quellstand setzt einen bereits produktiven Use Case nicht automatisch zurück. Die historische Entscheidung bleibt erhalten; neue Managemententscheidungen werden als neues Review mit neuem Snapshot dokumentiert.

## Systemgrenze

Die eigentliche ML-Test-Score-Erhebung, technische Detailtests, Release-/Rollback-Ausführung, Telemetrie, Incident- und Change-Steuerung verbleiben beim Delivery-/Betriebsteam.

KI-Ideenwerkstatt speichert nur den verdichteten, entscheidungsrelevanten Review-Snapshot. Dadurch bleibt die Produktgrenze aus `ROADMAP.md` erhalten.
