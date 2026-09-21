# Issue #333 – Gap-Analyse

**Issue:** #333 – Kompaktes KMU-Go-live-Gate zwischen Pilot/Wirkung und Betrieb  
**Baseline:** `main` @ `83f59e5cd255c594edb6ad0125fbff99d8de61c5`  
**Datum:** 23.08.2026  
**Status:** historischer Analyse-Nachweis; umgesetzt über PR #346 und vervollständigt über PR #348

## Ziel der Analyse

Vor der Implementierung wurde geprüft, ob Scale Readiness ein neues Framework, ein separates Entscheidungsmodell oder eine zusätzliche Journey benötigt. Leitlinie war, vorhandene Pilot-, Wirkungs-, Governance-, Delivery-, Rollen- und Go-live-Mechanismen wiederzuverwenden und nur die echte Entscheidungslücke zwischen validierter Pilotwirkung und produktivem Betrieb zu schließen.

## Gap-Matrix

| Capability | Bestehender Mechanismus | Nachgewiesene Restlücke | Entscheidung |
|---|---|---|---|
| Lifecycle | `UseCase.Status.PILOT/OPERATION`, `Review`, serverseitige Übergangsregeln | Ein erfolgreicher Pilot konnte fachlich als Go-live-Grundlage gelesen werden, ohne eine zusammenhängende Produktionsreife-Sicht | **EXTEND** bestehendes Go-live-Gate; kein neuer Lifecycle-Status |
| Pilotwirkung | `UseCase.metric_*`, Ziel-/Ist-Vergleich, Messzeitraum, Messdatum und Evidenzlink | Wirkung war sichtbar, Repräsentativität für den geplanten Produktivscope aber nicht explizit bestätigt | **REUSE + minimale Bestätigung** |
| Delivery/Handover | versioniertes, verbindlich übergebenes `DeliveryPackage`, Readiness und Provenance | Delivery-Nachweise waren vorhanden, aber in der Ergebnisentscheidung nicht gemeinsam mit Pilotwirkung und Betriebsevidenz verdichtet | **REUSE/REFERENZIEREN**, keine zweite Delivery Readiness |
| Governance | `GovernanceAssessment`, `GovernanceReview`, bestehende Hard Gates | Ergebnisse waren verteilt sichtbar; formale Blocker mussten Bestandteil der Go-live-Aggregation werden | **REUSE**, keine zweite Governance-Engine |
| Rollen | bestehender Business Owner und Technical Owner | kein neues Rollenmodell nötig; fehlende Verantwortungsfunktion musste den Go-live blockieren | **REUSE** |
| ML Test Score | externe Erhebung mit `Data`, `Model`, `Infrastructure`, `Monitoring`, Mindestwert und zwingenden Einzelprüfungen | die für die Entscheidung verwendete Version, Werte und Evidenzreferenz wurden im Radar nicht als Review-Snapshot festgehalten | **REFERENZIEREN + SNAPSHOT**, keine Score-Neuberechnung |
| Release/Betrieb | externe Release-, Rollback-, Monitoring- und Incident-Nachweise | entscheidungsrelevante Version/Referenz und Pflichtbestätigungen fehlten im bestehenden Review | **MINIMAL EXTEND**, Detailsteuerung bleibt extern |
| Entscheidung | bestehendes historisches `Review` gemäß ADR 0007 | kein unveränderbarer Scale-Readiness-Stand zum Entscheidungszeitpunkt | **EXTEND Review-Snapshot**, kein `ScaleReadinessDecision`-Modell |
| Readiness-Logik | vorhandene Gate-/Finding-Konventionen | keine gemeinsame deterministische Auswertung der sechs Scale-Dimensionen mit Hard Blockern und Auflagen | **NEW deterministische Projektion**, keine Ampelmittelung |
| Conditional Go | `Review.open_actions`, `action_owner`, `action_due_date` | die drei Angaben wurden nicht als untrennbare Voraussetzung einer Scale-Auflage geprüft | **REUSE + serverseitige Pflichtregel** |
| Outcome-Workspace | `Wirkung & Betrieb` mit `Übergabe → Pilot → Wirkung → Ergebnisentscheidung → Betrieb → Abschluss` | Scale Readiness und ihre dominante nächste Aktion waren in der Ergebnisentscheidung nicht explizit sichtbar | **EXTEND** vorhandene Ergebnisentscheidung; keine zweite Journey |
| Historie | Review- und Use-Case-Historie | die sechs Dimensionen und verwendeten Scale-Nachweise waren nach der Entscheidung nicht kompakt sichtbar | **EXTEND Darstellung** des gespeicherten Snapshots |
| Legacy | vorhandene Use Cases im Betrieb | rückwirkende Neubewertung hätte historische Zustände verfälscht | **PRESERVE**, kein Backfill und keine automatische Invalidierung |

## Kleinste belastbare Lösung

1. Scale Readiness als deterministische Projektion mit genau sechs Dimensionen implementieren.
2. Pilot-, Governance-, Delivery- und Rollendaten aus ihren bestehenden Sources of Truth lesen.
3. ML-Test-Score- und Betriebsnachweise nur in der für die Entscheidung verwendeten Version beziehungsweise Referenz erfassen.
4. Hard Blocker getrennt von kompensierbaren Auflagen behandeln; keine Mittelung und kein eigener Scale-Gesamtscore.
5. `GO`, `CONDITIONAL GO` und `NO-GO` als verständliche Entscheidungsvorschläge auf das bestehende Lifecycle-Review abbilden.
6. Für ein Conditional Go vorhandene Maßnahmenfelder verpflichtend gemeinsam prüfen.
7. Den serverseitig erzeugten, unveränderlichen Scale-Readiness-Snapshot am bestehenden `Review` speichern.
8. Den direkten `Pilot → Betrieb`-Übergang auch auf Service-Ebene schützen.
9. Scale Readiness im bestehenden Workspace `Wirkung & Betrieb` unter `Ergebnisentscheidung` platzieren.

## Verworfene Alternativen

- eigenes `ScaleReadinessDecision`-Modell → **verworfen**, weil `Review` bereits die kanonische Entscheidungs- und Historienquelle ist;
- neuer Lifecycle-Status `Scale` → **verworfen**, weil Scale Readiness ein Gate vor `Betrieb` und keine eigenständige Betriebsphase ist;
- zweiter Delivery-/Go-live-Workspace → **verworfen**, weil `Wirkung & Betrieb` die fachlich passende Ergebnisentscheidung bereits besitzt;
- eigener Scale-Gesamtscore → **verworfen**, weil gute Teilwerte Hard Blocker nicht kompensieren dürfen;
- erneute Implementierung des Google ML Test Score → **verworfen**, weil die externe Erhebung führend bleibt;
- Duplikation vollständiger Pilot-, Governance- oder Delivery-Daten im Snapshot → **verworfen**, weil Referenzen und entscheidungsrelevante Zustände genügen;
- rückwirkender Backfill für Bestandsfälle im Betrieb → **verworfen**, weil historische Go-live-Entscheidungen nicht nachträglich erfunden werden dürfen.

## Schemaentscheidung

Eine kleine additive Schemaänderung am bestehenden `Review` war erforderlich: `scale_readiness_schema_version` und `scale_readiness_snapshot`. Es entstand keine neue Entscheidungstabelle und kein paralleles Domainmodell.

## Ergebnis

Die Analyse bestätigte eine Darstellungs-, Aggregations- und Snapshot-Lücke – keine neue Lifecycle-, Delivery-, Governance- oder Score-Methodik. Die reuse-first Lösung wurde mit PR #346 umgesetzt. Die in der Abnahme noch fehlende dominante nächste Aktion wurde anschließend minimal mit PR #348 ergänzt.
