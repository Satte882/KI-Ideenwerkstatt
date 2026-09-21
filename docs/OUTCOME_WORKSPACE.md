# Wirkung & Betrieb

## Zielbild

`Wirkung & Betrieb` ist ein kompakter Review- und Entscheidungs-Snapshot. Der Arbeitsraum ersetzt weder das bestehende Use-Case-Formular noch Jira, Azure DevOps, GitHub oder ein anderes operatives Delivery-System.

Die Navigation umfasst:

```text
Übergabe → Pilot → Wirkung → Ergebnisentscheidung → Betrieb → Abschluss
```

Jeder Bereich zeigt vorhandene Informationen und führt ausschließlich zu einer bereits bestehenden, fachlich führenden Oberfläche. Es entsteht keine parallele Journey oder zweite Lifecycle-Statuslogik.

Die Stufe `Ergebnisentscheidung` enthält mit #333 die **Scale-Readiness-Sicht**. Sie bündelt nach abgeschlossener Wirkungsmessung die vorhandenen Pilot-, Governance- und Delivery-Nachweise mit der aktuellen externen ML-Test-Score-/Betriebsevidenz. Die verbindliche Entscheidung bleibt das bestehende Lifecycle-`Review`.

Der Arbeitsraum verwendet weiterhin dieselbe `JourneyState`-/`JourneyStep`-Logik. Es gibt keine zweite Journey-Engine und keinen zusätzlichen Lifecycle-Schritt.

## Systemgrenze

### Externes Delivery-System

Jira, Azure DevOps, GitHub oder ein vergleichbares Werkzeug bleiben führend für:

- Backlog, Epics, Stories und Tasks,
- Sprint- und Release-Planung,
- technische Detailprobleme,
- tägliche Maßnahmen und Fortschrittsmeldungen,
- Ressourcenplanung,
- ML-Test-Score-Erhebung und technische Detailnachweise,
- Release-/Rollback-Ausführung,
- Telemetrie sowie Incident-, Change- und Service-Management.

### KI-Radar

KI-Radar bleibt führend für:

- Baseline, Ziel und gemessenen Ist-Wert,
- Messzeitraum, Messmethode und Nachweislink,
- Governance-Auflagen und Verantwortlichkeiten,
- Scale-Readiness-Findings und den entscheidungsrelevanten Evidenz-Snapshot,
- Lifecycle-Reviews mit Begründung und Statuswechsel,
- Go-live- und Abschlussentscheidung,
- Management-Reviews und Lessons Learned.

Der Informationsrückfluss bleibt ein manueller Review-Snapshot. Es gibt keine Live-Synchronisation und keine doppelte Pflege operativer Maßnahmen.

## Führende Oberfläche je Bereich

| Bereich | Aktion und führende Oberfläche |
|---|---|
| Übergabe | Delivery Package prüfen, vervollständigen oder verbindlich übergeben |
| Pilot | tatsächlich hinterlegten externen Delivery-Link öffnen |
| Wirkung | direkt zum nächsten fehlenden Metrikfeld im bestehenden Use-Case-Formular springen |
| Ergebnisentscheidung | bei vollständiger Messung das bestehende Review-Formular öffnen; dort Scale Readiness prüfen und `GO_LIVE`, `CONTINUE`/`REWORK` oder `END` dokumentieren |
| Betrieb | bei fälligem Termin das bestehende Review-Formular öffnen; sonst neutralen Status anzeigen |
| Abschluss | das bestehende Review-Formular für `END` und die Abschlussangaben öffnen |

Ein CTA wird nur angezeigt, wenn Zieloberfläche und Berechtigung tatsächlich vorhanden sind.

## Pilot-Link und unveränderliche Übergaben

- Ein gestarteter Pilot mit externem Delivery-Link zeigt `Externen Pilot öffnen`.
- Ein noch bearbeitbares Delivery Package ohne Link zeigt für berechtigte Benutzer `Delivery-Link ergänzen`.
- Ein bereits übergebenes Package bleibt unveränderlich. Fehlt dort der Link, zeigt die Oberfläche bewusst einen neutralen Hinweis; sie verweist nicht auf eine unzulässige Bearbeitung.
- Die frühere Selbstverlinkung `Pilotübersicht öffnen` ist entfernt. Es wird keine interne Pilotübersicht erfunden.

## Ergebnisentscheidung, Scale Readiness und Abschluss

Die Deep Links verwenden das bestehende Lifecycle-Review:

- `Go-live entscheiden` öffnet das Review-Formular mit `GO_LIVE` und Zielstatus `Betrieb` vorbelegt.
- Für einen Pilot-Review zeigt dasselbe Formular den kompakten Scale-Readiness-Block mit sechs Prüffeldern.
- Die Entscheidungsvorschau aktualisiert `GO`, `CONDITIONAL GO` oder `NO-GO`, Findings und nächste Aktion bereits beim Bearbeiten der Nachweise; verbindlich wird der Stand erst durch das serverseitige Speichern.
- Hard Blocker verhindern `Pilot → Betrieb` serverseitig. Sie können nicht durch einen hohen anderen Wert oder eine Ausnahme kompensiert werden.
- `CONDITIONAL GO` verwendet weiterhin `GO_LIVE`, verlangt aber im bestehenden Review eine Kompensationsmaßnahme, einen Owner und eine Frist.
- `CONTINUE` beziehungsweise `REWORK` lassen den Lifecycle im Pilot.
- `Abschluss dokumentieren` öffnet dasselbe Formular mit `END` und Zielstatus `Beendet` vorbelegt.

`Review` bleibt gemäß ADR 0007 die einzige führende Entscheidungs- und Historienquelle. #333 ergänzt nur einen versionierten `scale_readiness_snapshot`; es entsteht kein separates Scale-Decision-Modell.

## Kompakter Snapshot

Der gemeinsame Use-Case-Bereich zeigt weiterhin:

- Lifecycle-Status,
- Baseline, Ziel, Ist-Wert und Ergebnis,
- Business und Technical Owner,
- nächsten Review-Termin,
- aktuelle Delivery-Package-Version und Status.

Der Scale-Readiness-Snapshot im Review referenziert zusätzlich die zum Entscheidungszeitpunkt verwendete Delivery-Version, Governance-Prüfungen, ML-Test-Score-Version/-Datum und Betriebsnachweise. Er dupliziert nicht die vollständigen fachlichen Quellobjekte.

Nach dem Speichern wird direkt wieder die Stufe `Ergebnisentscheidung` geöffnet. Dort ist die gespeicherte Entscheidung mit allen sechs Dimensionen sichtbar; die Use-Case-Historie zeigt denselben Snapshot als nachgelagerten Nachweis.

Die Darstellung ist verdichtet, damit der phasenspezifische Handlungsstatus sichtbar bleibt.

## Sidebar und Benutzer-Menü

Der globale Sidebar-Einstieg `Wirkung & Betrieb` öffnet den Arbeitsraum. Am konkreten Use Case und im Scale-Review ergänzt die lokale Initiative den Einstieg `Wirkung & Betrieb` mit der Einordnung `Pilot → Wirkung → Scale Readiness → Betrieb`. Die sechs Bereiche bleiben als kontextuelle Phasennavigation innerhalb des Arbeitsraums sichtbar und werden nicht als sechs weitere globale Navigationspunkte dupliziert.

Der Footer zeigt dauerhaft nur Avatar und Benutzername. Administration und Abmelden liegen in einem aufklappbaren Account-Menü.

## Topbar: Lifecycle-Status und geöffnete Ansicht

Die obere Leiste stellt zwei voneinander unabhängige Informationen dar:

- Farbe und Symbol zeigen den fachlich abgeleiteten Lifecycle-Status der Phase.
- Eine zusätzliche violette Kontur und Unterstreichung markieren die aktuell geöffnete Ansicht.

Ein Klick auf einen Bereich verändert deshalb nicht den fachlichen Status. Er wechselt ausschließlich die geöffnete Perspektive.

## Konsistente Lifecycle-Reihenfolge

Die Statusableitung verwendet vorhandene, verbindliche Nachweise:

- aktuelle verbindliche Delivery-Übergabe,
- dokumentierten `pilot_start`,
- vollständige Wirkungsmessung aus Ist-Wert, Messzeitraum, Messdatum und Nachweis, deren Messdatum nicht vor dem aktuellen Pilotbeginn liegt,
- persistierte Lifecycle-Reviews für `GO_LIVE` und `END`.

Dabei gelten folgende Invarianten:

- Es gibt höchstens eine Phase mit dem Zustand `current`.
- Ein gestarteter Pilot wird erst nach einer vollständigen Messung für den aktuellen Pilot oder einer dokumentierten Folgeentscheidung als abgeschlossen dargestellt.
- Eine ältere Messung vor dem aktuellen `pilot_start` bleibt sichtbar, schließt den aktuellen Pilot aber nicht ab.
- Betrieb ist nur nach vollständiger Messung, erfüllter Scale Readiness und persistiertem Go-live-Review gültig.
- Ein direkter Abschluss aus dem Pilot überspringt Betrieb bewusst als `optional`.
- Widersprechen Lifecycle-Status und Nachweise einander, werden die betroffenen Phasen als `blocked` mit dem Hinweis `Dateninkonsistenz` angezeigt. Spätere Phasen werden nicht fälschlich als abgeschlossen oder aktuell dargestellt.

## Bewusste Nicht-Ziele

Dieses Inkrement implementiert nicht:

- ein neues Pilot- oder Betriebsdatenmodell,
- eine zweite Bearbeitungsoberfläche,
- Fortschrittsprozente oder operative Maßnahmenlisten,
- Jira-, Azure-DevOps- oder GitHub-Synchronisation,
- versionierte Wirkungsmessungen,
- ein separates Scale-Readiness-Decision-Modell,
- einen neuen Scale-Gesamtscore,
- eine zweite ML-Test-Score-Engine,
- neue Lifecycle-Status oder Berechtigungsmodelle.

Die einzige neue Persistenz ist der versionierte, serverseitig erzeugte Scale-Readiness-Snapshot am bestehenden `Review`.

## Abnahmekriterien

- Die sechs Bereiche besitzen unterscheidbare Kontexte.
- CTAs führen nur zu vorhandenen und zulässigen Zieloberflächen.
- Pilot öffnet ausschließlich einen echten externen Link.
- Fehlende oder unzulässige Aktionen werden als bewusster neutraler Zustand dargestellt.
- Wirkung, Scale-/Go-live-Entscheidung und Abschluss verwenden die bestehenden Formulare.
- Scale Readiness führt keinen neuen Journey-Key oder Lifecycle-Status ein.
- Hard Blocker können `Pilot → Betrieb` nicht umgehen.
- Conditional Go verlangt Maßnahme, Owner und Frist.
- Der Account-Footer blockiert keinen dauerhaften Platz für Administration und Abmelden.
- Die obere Leiste trennt geöffneten Bereich und fachlichen Lifecycle-Status.
- Die Lifecycle-Reihenfolge zeigt keine späteren grünen oder gelben Phasen bei fehlenden zwingenden Nachweisen.
- Eine Messung vor dem aktuellen Pilotbeginn wird nicht als Abschluss des aktuellen Piloten gewertet.
- Die bestehende Systemgrenze bleibt sichtbar.
