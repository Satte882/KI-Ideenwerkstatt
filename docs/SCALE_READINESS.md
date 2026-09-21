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

KI-Radar wird damit nicht zum zweiten Delivery-, Observability-, Incident- oder GRC-System. Externe technische Evidenz wird nur in der Version beziehungsweise Referenz erfasst, die der konkreten Managemententscheidung zugrunde lag.

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

Governance-Merkmale mit personenbezogenen, sicherheitskritischen, regulierten oder erheblich wirkenden Entscheidungen erzwingen mindestens Tailoring C. Eine niedrigere Auswahl ist dann serverseitig blockiert.

## Zustände und Entscheidungen

Scale Readiness berechnet ausschließlich einen Evidenzzustand:

- `ready`
- `conditional`
- `not_ready`

Dieser Zustand ist **kein neuer Lifecycle-Status**.

Die verbindliche Entscheidung bleibt das bestehende `Review`:

| Managemententscheidung | Bestehende Review-/Lifecycle-Semantik |
|---|---|
| Go | `GO_LIVE`, Snapshot `ready`, `Pilot → Betrieb` |
| Conditional Go | `GO_LIVE`, Snapshot `conditional`, `Pilot → Betrieb` |
| Pilot verlängern / nacharbeiten | `CONTINUE` beziehungsweise `REWORK`, Status bleibt `Pilot` |
| Stop | `END`, Zielstatus `Beendet` |

Ein Conditional Go ist nur zulässig, wenn **kein Hard Blocker** besteht und mindestens Kompensationsmaßnahme, Owner und Frist im bestehenden Review dokumentiert sind.

Im UI werden diese Zustände ausdrücklich als `GO · Bereit`, `CONDITIONAL GO · Bereit mit Auflagen` und `NO-GO · Nicht bereit` bezeichnet.

## Nicht überstimmbare Hard Blocker

Unter anderem blockieren:

- fehlende oder unzureichende aktuelle ML-Test-Score-Erhebung,
- finaler ML Test Score unter dem projektspezifischen Mindestwert,
- nicht erfüllte zwingende ML-Test-Score-Einzelprüfungen,
- fehlende eindeutig identifizierte Produktivversion,
- nicht praktisch getesteter Rollback beziehungsweise keine Deaktivierung,
- fehlendes technisches oder AI-/fachliches Qualitätsmonitoring,
- erforderlicher, aber fehlender Incident-/Eskalationsprozess,
- offene beziehungsweise fehlgeschlagene formale Governance-Prüfungen,
- fehlende bestehende Owner-/Betriebsverantwortung,
- für Tailoring C fehlende erweiterte Kontrollen.

Diese Blocker können weder durch einen hohen Score in einer anderen Kategorie noch durch eine freie Begründung, eine Early-Go-live-Ausnahme oder eine direkte Service-Nutzung kompensiert werden.

## Persistenter Decision-Snapshot

ADR 0007 bleibt unverändert gültig: `Review` ist die einzige führende Entscheidungs- und Historienquelle.

Mit #333 wurde `Review` minimal ergänzt um:

- `scale_readiness_schema_version`
- `scale_readiness_snapshot`

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
- eine live aktualisierte, noch nicht gespeicherte Entscheidungsvorschau;
- einbezogene Pilot-, Governance-, Delivery-, Rollen- und ML-Test-Score-Evidenz;
- aktuelle Findings und genau eine konkrete nächste Aktion;
- bei `CONDITIONAL GO` die Pflichtangaben Maßnahme, Owner und Frist.

Nach dem Speichern führt der Ablauf zurück zur Ergebnisentscheidung. Dort bleibt der serverseitig erzeugte Snapshot mit Entscheidung, sechs Dimensionen, verwendeter Evidenz und gegebenenfalls Auflagen sichtbar. Die Use-Case-Historie zeigt denselben gespeicherten Entscheidungsstand.

## Legacy und Änderungen nach Go-live

Bestehende `OPERATION`-Use-Cases werden nicht rückwirkend invalidiert und erhalten keinen erfundenen Backfill. Die neuen Gates gelten für zukünftige `Pilot → Betrieb`-Übergänge.

Ein später geänderter Quellstand setzt einen bereits produktiven Use Case nicht automatisch zurück. Die historische Entscheidung bleibt erhalten; neue Managemententscheidungen werden als neues Review mit neuem Snapshot dokumentiert.

## Systemgrenze

Die eigentliche ML-Test-Score-Erhebung, technische Detailtests, Release-/Rollback-Ausführung, Telemetrie, Incident- und Change-Steuerung verbleiben beim Delivery-/Betriebsteam.

KI-Radar speichert nur den verdichteten, entscheidungsrelevanten Review-Snapshot. Dadurch bleibt die Produktgrenze aus `ROADMAP.md` erhalten.
