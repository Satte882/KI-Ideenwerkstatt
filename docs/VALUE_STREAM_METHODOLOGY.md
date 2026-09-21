# Value-Stream-Methodik

**Version:** 1.2  
**Stand:** 22.08.2026  
**Gültig für:** Value-Stream-Erfassung und Fokus-/Prozessanalyse im KI-Radar  
**Zweck:** kompakte fachliche Leitplanke; keine zusätzliche Business-Architecture-Schicht

## 1. Begriffe sauber trennen

### Capability

Eine Capability beschreibt, **was ein Unternehmen können muss**. Sie ist eine relativ stabile Fähigkeit und noch kein konkreter Ablauf.

Beispiel: `Rechnungen prüfen und freigeben können`.

### Value Stream

Ein Value Stream beschreibt, **wie für einen Stakeholder ein relevantes Ergebnis oder ein Wert entsteht**. Er verbindet einen klaren Trigger mit einem fachlich relevanten Outcome.

Beispiel: `Rechnungseingang bis freigegebene Zahlung`.

### Process

Ein Process beschreibt, **wie ein konkreter Ablauf heute oder künftig ausgeführt wird**: Schritte, Rollen, Systeme, Regeln, Übergaben und Ausnahmen.

Beispiel: der operative Prüf- und Freigabeprozess innerhalb einer ausgewählten Value-Stream-Phase.

> Merksatz: **Capability = Was können? · Value Stream = Wie entsteht Wert? · Process = Wie läuft es konkret ab?**

## 2. Einen Value Stream sinnvoll schneiden

Ein guter Value Stream besitzt einen erkennbaren Anfang und ein fachlich relevantes Ende.

- **Trigger:** Welches Ereignis startet die Wertentstehung?
- **Stakeholder / Empfänger:** Für wen entsteht das relevante Ergebnis?
- **Outcome:** Welcher Zustand oder welches Ergebnis liegt am Ende vor?
- **Scope-In:** Was gehört ausdrücklich zum betrachteten Value Stream?
- **Scope-Out:** Was gehört ausdrücklich nicht dazu?
- **Strategischer Kontext / Ziel:** Warum ist dieser Value Stream für das Unternehmen relevant?

### Kurzbeispiel

**Value Stream:** Beschaffungsbedarf bis Bestellung  
**Trigger:** Ein bestätigter Beschaffungsbedarf liegt vor.  
**Stakeholder:** Bedarfsträger und Einkauf.  
**Outcome:** Eine fachlich und kaufmännisch freigegebene Bestellung wurde ausgelöst.  
**Scope-In:** Bedarf konkretisieren, Anbieter/Angebote prüfen, Entscheidung und Bestellung.  
**Scope-Out:** Wareneingang, Rechnungsprüfung und Zahlung.

## 3. Granularität konsistent halten

Value Streams, die miteinander verglichen werden, sollten auf einer ähnlichen Abstraktionsebene liegen.

Vermeiden:

- einen End-to-End-Value-Stream mit einem einzelnen Teilprozess zu vergleichen,
- einzelne Tätigkeiten als eigene Value Streams zu behandeln,
- organisatorische Zuständigkeiten mit Wertentstehung gleichzusetzen.

Prüffrage:

> Beschreiben die betrachteten Value Streams jeweils einen vergleichbaren Weg von einem Trigger zu einem für einen Stakeholder relevanten Outcome?

## 4. Phasen als Wertfortschritt beschreiben

Eine Value-Stream-Phase ist mehr als eine Tätigkeitsüberschrift. Sie sollte einen **erkennbaren fachlichen Wertfortschritt** beschreiben.

Für jede Phase helfen drei Fragen:

1. **Was liegt vorher vor?**
2. **Was verändert sich fachlich?**
3. **Welcher relevante Zustand oder welches Ergebnis liegt danach vor?**

Als Denkmodell kann verwendet werden:

`Entrance → Transformation → Value Item / Wertfortschritt → Exit`

Dieses Denkmodell dient nur zum besseren Schneiden und Beschreiben der Phase. Es wird **nicht** in vier zusätzliche Pflichtfelder übersetzt.

### Beispiel

Schwach: `Angebote bearbeiten`

Stärker: `Angebote vergleichbar machen` – aus eingegangenen, unterschiedlich strukturierten Angeboten entsteht eine fachlich vergleichbare Entscheidungsgrundlage.

## 5. Mehrere mögliche Value Streams pragmatisch priorisieren

Wenn mehrere Value Streams als Startpunkt infrage kommen, kann eine einfache Heuristik verwendet werden:

`Business Importance × Transformation Need`

### Business Importance

Wie wichtig ist der Value Stream für das Unternehmen oder relevante Stakeholder?

Mögliche Indikatoren:

- Einfluss auf strategische Ziele,
- Kunden-/Stakeholder-Wert,
- wirtschaftliche Relevanz,
- regulatorische oder operative Kritikalität.

### Transformation Need

Wie groß ist der konkrete Veränderungsbedarf?

Mögliche Indikatoren:

- bekannte Probleme und Engpässe,
- hohe manuelle Aufwände,
- Medienbrüche,
- Qualitätsprobleme,
- hoher Änderungsdruck,
- relevantes Automatisierungs- oder Digitalisierungspotenzial.

### Einfache Orientierung

| Business Importance | Transformation Need | Orientierung |
|---|---|---|
| hoch | hoch | bevorzugt vertiefen |
| hoch | niedrig | beobachten / gezielt prüfen |
| niedrig | hoch | Nutzen und Scope kritisch prüfen |
| niedrig | niedrig | nachrangig |

Diese Heuristik ist **kein neues Portfolio-Modul und kein verpflichtendes Scoring**. Sie hilft lediglich, einen sinnvollen Startpunkt zu wählen.

## 6. Fokusphase innerhalb eines Value Streams auswählen

Nach Auswahl eines Value Streams wird entschieden, **welche Phase tatsächlich vertieft werden soll**. Diese Entscheidung darf früh und hypothesenbasiert erfolgen, muss aber nachvollziehbar bleiben.

Die Fokusphase wird anhand folgender Perspektiven verglichen:

- **Business Impact** – Relevanz für Geschäftsziele, Stakeholder oder kritischen Betrieb;
- **Problemintensität** – Ausmaß von Wartezeit, Nacharbeit, Fehlern, Aufwand oder Engpässen;
- **Verbesserungspotenzial** – welche relevante Verbesserung gegenüber dem Ist-Zustand realistisch erreichbar erscheint;
- **Datenzugang / Validierbarkeit** – wie realistisch Hypothesen und spätere Wirkung geprüft werden können;
- **Veränderungsaufwand** – organisatorischer, prozessualer und technischer Änderungsaufwand;
- **Time-to-Value** – wie schnell eine sinnvolle Wirkung realistischerweise erreichbar ist.

### Verbesserungspotenzial ist nicht Veränderungsaufwand

Die beiden Kriterien beantworten unterschiedliche Fragen:

- `Verbesserungspotenzial`: **Wie viel sinnvolle Verbesserung kann erreicht werden?**
- `Veränderungsaufwand`: **Wie aufwendig ist die Veränderung?**

Eine Phase kann gleichzeitig hohes Verbesserungspotenzial **und** hohen Veränderungsaufwand besitzen. Das ist kein Widerspruch und darf nicht in einem einzelnen Kriterium verschmolzen werden.

### Time-to-Value als Trade-off

Time-to-Value wird qualitativ als `unbekannt`, `kurz`, `mittel` oder `lang` eingeordnet.

Es gilt ausdrücklich nicht:

> kürzer = automatisch besser

Ein schneller KI-Pilot kann im Einzelfall sinnvoller sein als eine langwierige Harmonisierung. Umgekehrt kann eine langsamere Standardisierung langfristig robuster und wirtschaftlicher sein. Die Abwägung muss sichtbar begründet werden; es gibt keinen automatischen TTV-Score.

### Evidenzbasis sichtbar halten

Je Phase wird außerdem kenntlich gemacht, worauf die Bewertung aktuell beruht:

- **Hypothese / unbestätigt**,
- **Indiz / qualitativ belegt**,
- **gemessen / nachgewiesen**.

Eine Hypothese ist in früher Discovery zulässig. Sie darf nur nicht so dargestellt werden, als läge bereits validierte Evidenz vor. Fehlende quantitative Baselines werden nicht erfunden.

Bestehende `ProcessValidation`, Provenance sowie Versions-/Stale-Mechanismen bleiben die kanonischen Nachweise für fachliche Validierung und Herkunft im späteren Prozess-Deep-Dive.

## 7. Von Value Stream zu Prozess und Lösung

### SIPOC als kompakter Scopingrahmen

Beim Einstieg in die konkrete Prozessanalyse dient SIPOC als sichtbare Denkstütze:

`Supplier → Input → Process → Output → Customer`

Dafür werden **keine zusätzlichen SIPOC-Felder oder ein separates Artefakt** gepflegt. Die vorhandene `ProcessAnalysis` bleibt kanonisch:

- fachliche Inputs, Daten und Dokumente werden unter **Datenobjekte und Dokumente** erfasst,
- das konkrete Prozessergebnis unter **Ergebnis**,
- Quellen relevanter Inputs und Empfänger des Ergebnisses werden bei **Übergaben und Schnittstellen** konkretisiert,
- Prozessgrenzen und Ablauf bleiben über Prozessstart, Prozessende und Ist-Ablauf beschrieben.

Der Quellkontext beziehungsweise `source_snapshot` dokumentiert dagegen die Herkunft übernommener Radar-Inhalte und ist **nicht** mit einem fachlichen SIPOC-Supplier gleichzusetzen.

Der KI-Radar folgt bewusst dieser Logik:

1. Value Stream erfassen und sauber abgrenzen.
2. Phasen vergleichen.
3. Fokusphase anhand der Kriterien und der aktuellen Evidenzbasis nachvollziehbar auswählen.
4. Den relevanten Prozess detaillierter analysieren.
5. Problem, Ursachen, Engpässe, Baselines und Rahmenbedingungen verstehen.
6. Mehrere Lösungsoptionen entwickeln und vergleichen.
7. Die fachlich beste ausreichende Option auswählen.
8. Nur wenn die bevorzugte Lösung tatsächlich eine KI-Komponente enthält, gegebenenfalls einen KI-Use-Case anlegen.

Dabei gilt:

> **Problem / Prozess → Lösungsraum → mehrere Alternativen → KI kann eine Option sein.**

Nicht:

> **Problem → KI-Eignung → KI erzwingen.**

Organisatorische, regelbasierte oder klassische technische Lösungen können gegenüber einer KI-Lösung die bessere Option sein. Ebenso kann eine hybride Lösung aus Standardisierung, deterministischer Automation und gezielter KI-Komponente die beste ausreichende Variante sein.

Ein fachlich sauberer Endzustand ist ausdrücklich auch:

```text
Problem analysiert
→ Standardisierung / klassische Automation ausreichend
→ kein KI-Use-Case erforderlich
```

## 8. Bestehende qualitative Bewertungsskalen

Die bestehende Value-Stream-/Fokus-Journey verwendet für mehrere Kriterien die drei Stufen:

`Niedrig · Mittel · Hoch`

Die konkrete Bedeutung hängt vom Kriterium ab. Deshalb gilt nicht pauschal „hoch = gut“.

- **Strategischer Impact / Impact:** Reichweite und Relevanz der Wirkung.
- **Wirtschaftliches Potenzial:** Größe des plausiblen wirtschaftlichen Hebels.
- **Problemintensität:** Stärke, Häufigkeit und Konsequenz des Problems.
- **Verbesserungspotenzial:** Größe der plausibel erreichbaren Verbesserung gegenüber dem Ist-Zustand.
- **Datenzugänglichkeit / Datenlage:** reale Verfügbarkeit, Zugänglichkeit und Nutzbarkeit relevanter Daten beziehungsweise Validierbarkeit.
- **Veränderungsaufwand:** notwendiger organisatorischer, prozessualer und technischer Veränderungsaufwand.

Time-to-Value verwendet bewusst eine eigene Skala (`unbekannt · kurz · mittel · lang`) und die Evidenzbasis eine eigene Semantik (`Hypothese · Indiz · Messwert`). Beide werden nicht in die Niedrig-/Mittel-/Hoch-Skala gezwungen.

Die Skalenanker in der Anwendung erläutern diese Semantik; sie erzeugen keinen gewichteten Gesamtscore.

## 9. Methodische Leitplanke

Die Value-Stream-Erfassung soll Orientierung schaffen, nicht zusätzliche Bürokratie erzeugen.

Daher:

- vorhandene Felder und bestehende Validation-/Provenance-Mechanismen zuerst nutzen,
- keine zusätzliche Capability- oder Portfolio-Engine,
- keine zweite allgemeine Evidence-/Validation-Engine,
- keine parallele Fokus- oder Prozessanalyse,
- kein vorgeschaltetes AI-Suitability-Gate,
- keine automatische Rangfolge aus Fokus- oder Lösungskriterien,
- keine erfundenen Baselines oder TTV-Werte,
- Detailtiefe erst dort erhöhen, wo eine Fokusentscheidung dies rechtfertigt.
