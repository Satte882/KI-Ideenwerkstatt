# Discovery & Architecture in KI-Radar

## Ziel

Der Bereich ergänzt den direkten Use-Case-Intake um einen optionalen, priorisierten Business-Architecture-Pfad:

```text
Fachdomäne und Business Capability
→ End-to-End-Value-Stream
→ Fokus-Screening und Auswahl
→ Fokusphase mit Kriterien- und Evidenzsnapshot
→ ausgewählter Prozess-Deep-Dive
→ Problem / Ursache / Verbesserungspotenzial
→ organisatorische, klassische, KI- oder hybride Lösungsoptionen
→ begründete bevorzugte Lösung
→ gegebenenfalls geführter Use-Case-Intake
→ Bewertung
→ Freigabe
→ Delivery Package
→ externes Delivery-System
```

Ein Use Case muss nicht aus einem Value Stream entstehen. Der direkte Intake bleibt ein gleichwertiger Einstieg und behält alle Plausibilitäts- und Hard-Gate-Prüfungen. Systematische Discovery verlangt dagegen eine dokumentierte Fokusentscheidung, bevor Prozessanalysen vertieft oder Use Cases abgeleitet werden.

## Methodische Trennung

KI-Radar behandelt fünf unterschiedliche Ebenen getrennt:

1. **Value-Stream-Analyse:** End-to-End-Wertschöpfung, Empfänger, Phasen, Stakeholder und Ergebnis.
2. **Fokus & Priorisierung:** Auswahl der zu vertiefenden Value Streams und Phasen anhand transparenter Kriterien und sichtbarer Evidenzbasis ohne künstlichen Gesamtscore.
3. **Prozessanalyse und Lösungsoptionen:** detaillierter Ist-Ablauf, Systeme, Daten, Regeln, Bottlenecks, Ursachen und technologieoffene Lösungswege.
4. **Use-Case- und Decision-Governance:** fachliche Kategorisierung, evidenzbasierte Bewertung und verbindliche Freigabe tatsächlich angelegter Use Cases.
5. **Delivery-Handover:** umsetzbarer Scope, Architekturartefakte, Anforderungen, Akzeptanzkriterien, Risiken, Abhängigkeiten und initiales Backlog.

Die Ebenen sind miteinander verknüpft, aber nicht austauschbar. Ein Value Stream ist kein Detailprozess, ein Fokus-Screening ist keine Use-Case-Bewertung, eine Prozessanalyse ist keine Lösungsarchitektur und ein Delivery Package ist kein Projektplan.

## Dauerhafte Prozesslandkarte

Die Oberfläche zeigt auf allen angemeldeten Seiten dieselbe Gesamtstrecke:

```text
Discovery → Fokus & Priorisierung → Use Cases → Bewertung → Freigabe → Delivery
```

Auf Übersichtsseiten markiert sie die fachliche Position des Arbeitsbereichs. Auf Detailseiten übernimmt sie die tatsächlichen Zustände der ausgewählten Initiative:

- `✓` abgeschlossen
- `●` aktuell
- `!` blockiert
- `○` noch offen
- `–` optional oder bewusst übersprungen

Die linke Navigation zeigt zusätzlich nur für den aktiven Bereich die lokale Tiefe, beispielsweise Value Stream, Fokusentscheidung, Prozessanalyse und Lösungsoption oder Use Case, Bewertung, Freigabe und Delivery.

## Fachdomäne und Capability

Organisationseinheit und fachliche Einordnung werden bewusst getrennt. Jeder systematisch abgeleitete oder direkt erfasste Use Case erhält:

- eine kontrollierte Fachdomäne, beispielsweise Einkauf, Marketing, Produktion, Finanzen oder Personal,
- eine Business Capability,
- einen Prozessbereich.

Damit kann ein fachlich dem Einkauf zugeordneter Use Case weiterhin von Shared Services oder einer anderen Organisationseinheit verantwortet werden. Die Zuordnung wird im Register, in der Portfolio-Sicht und im CSV-Export verwendet.

## Fokus & Priorisierung

Die grobe Value-Stream-Aufnahme darf abgeschlossen werden, ohne sofort einen Deep Dive auszulösen.

### Value-Stream-Screening

Auf der vorgelagerten Value-Stream-Ebene bleiben die vorhandenen Screening-Perspektiven maßgeblich, unter anderem:

- Fachdomäne,
- Business Capability,
- strategischer Impact,
- wirtschaftliches Potenzial,
- Problem- und Schmerzintensität,
- Datenzugänglichkeit,
- Veränderungsaufwand,
- begründete Auswahlentscheidung.

Mögliche Entscheidungen sind:

- noch nicht bewertet,
- Kandidat für Vertiefung,
- für Deep Dive ausgewählt,
- zurückgestellt,
- nicht ausgewählt.

### Fokusphase innerhalb des Value Streams

Für den eigentlichen Stage-/Phasenvergleich werden die entscheidungsrelevanten Kriterien explizit und getrennt gespeichert:

- **Business Impact**,
- **Problemintensität**,
- **Verbesserungspotenzial**,
- **Datenzugang / Validierbarkeit**,
- **Veränderungsaufwand**,
- **Time-to-Value**.

`Verbesserungspotenzial` beantwortet, welche relevante Verbesserung gegenüber dem Ist-Zustand realistisch erreichbar erscheint. `Veränderungsaufwand` beschreibt dagegen den notwendigen organisatorischen, prozessualen und technischen Änderungsaufwand. Beide Kriterien dürfen nicht zusammengezogen werden.

Zusätzlich wird je Phase die **Evidenzbasis** sichtbar eingeordnet:

- Hypothese / unbestätigt,
- Indiz / qualitativ belegt,
- gemessen / nachgewiesen.

Eine frühe Fokuswahl darf ausdrücklich auf Hypothesenbasis erfolgen. Fehlende Messwerte blockieren die Discovery nicht. Die Einordnung muss aber sichtbar bleiben; Hypothesen werden nicht als validierte Erkenntnisse dargestellt und es werden keine künstlichen Baselines erzeugt.

Time-to-Value bleibt ein qualitativer Trade-off (`unbekannt`, `kurz`, `mittel`, `lang`) und erzeugt keine automatische Rangfolge. Die Kriterien bleiben einzeln sichtbar; KI-Radar berechnet bewusst keinen scheinpräzisen Gesamtscore.

Nur ein ausreichend dokumentierter und ausgewählter Fokus darf neue Prozessanalysen oder daraus abgeleitete Lösungsentscheidungen starten. Bestehende serverseitige Fokus- und Journey-Regeln bleiben maßgeblich.

## TOGAF-light

KI-Radar ist kein Enterprise-Architecture-Repository und implementiert nicht das vollständige TOGAF-Metamodell. Die ADM-Bezüge sind nur dort sichtbar, wo konkrete Artefakte erfasst werden:

| ADM-Phase | KI-Radar-Artefakt |
|---|---|
| A – Architecture Vision | Scope, strategisches Ziel, Stakeholder, Leitplanken, Auslöser und Ergebnis |
| B – Business Architecture | Fachdomäne, Capability, Value Stream, Phasen, Rollen, Ist-Prozess, Regeln, Bottlenecks und Kennzahlen |
| C – Information Systems | Anwendungen, Datenobjekte, Informationsflüsse und Integrationen |
| D – Technology Architecture | Technologie-, Hosting- und Plattformleitplanken innerhalb der Lösungsoption und des Delivery Packages |
| E – Opportunities & Solutions | Fokusentscheidung sowie organisatorische, klassische, KI- und hybride Lösungsoptionen mit begründeter Präferenz |
| F – Migration Planning | MVP-Scope, Akzeptanzkriterien, Tests, Abhängigkeiten, Backlog und Delivery Package |
| G/H | Freigaben, Package-Versionen und Änderungen werden dokumentiert; kein vollständiges Architecture-Governance-Modul |

## Optionalität und Traceability

Der bestehende Use-Case-Intake bleibt ein vollwertiger Einstieg. Ein Use Case benötigt weiterhin **keinen** Value-Stream- oder Prozessbezug.

Wenn der Use Case jedoch aus einem bekannten Prozess entsteht, verwendet KI-Radar seit #322 die bereits vorhandene `UseCaseOrigin`-Relation als kanonische Herkunft:

```text
Use Case
→ UseCaseOrigin
→ Prozessanalyse
→ Value-Stream-Phase
→ Value Stream
→ strategisches Ziel / Fokuskontext
```

Im direkten Intake kann optional eine vorhandene Prozessanalyse als Ursprungsprozess gewählt werden. Der Prozess wird auf die gewählte Organisationseinheit eingeschränkt; Phase, Value Stream und strategischer Kontext werden daraus abgeleitet und **nicht** als parallele Use-Case-Felder gespeichert. Ohne Auswahl bleibt die direkte Erfassung mit einem beschreibenden Prozessbereich unverändert möglich.

Im systematischen Discovery-Pfad wird ein bereits bekannter Prozess automatisch übernommen. Ein aus einer bevorzugten KI-Lösungsoption gestarteter Intake darf diesen Ursprung nicht auf einen anderen Prozess umbiegen. Die bestehende Discovery-Kette bleibt damit vollständig rückverfolgbar.

Eine bevorzugte Non-AI-Lösung kann die Discovery weiterhin regulär beenden, ohne einen künstlichen Use Case zu erzeugen. Bestehende Use Cases ohne Ursprung bleiben unverändert gültig; es gibt keine heuristische oder LLM-basierte Rückzuordnung.

### Messreife im geführten Use-Case-Intake

Die hypothesenfähige Discovery setzt sich seit #340 konsistent im Guided Intake fort. Ein Use Case darf bis zur strukturierten Bewertung aufgenommen werden, obwohl noch keine belastbare numerische Baseline oder kein belastbarer Zielwert vorliegt.

Für die Aufnahme bleiben fachlich erforderlich:

- Nutzenhypothese,
- Name und Typ der Erfolgsmetrik,
- Optimierungsrichtung und Einheit,
- konkrete Messmethode,
- Datenrahmen.

`metric_baseline` und `metric_target` dürfen in dieser frühen Reifestufe dagegen unbekannt bleiben und werden als `NULL` gespeichert. Es werden keine Platzhalterwerte wie `0` erzeugt. Das gilt für direkte Use Cases ebenso wie für Use Cases, die aus einer Discovery-Lösungsoption entstehen.

Sobald Name, Typ, Richtung, Einheit und Messmethode vorliegen, zeigt die Oberfläche die Erfolgsmetrik als **definiert**. Fehlende Baseline oder fehlender Zielwert werden davon getrennt und ausdrücklich als noch offen dargestellt; sie dürfen nicht den falschen Eindruck erzeugen, es sei überhaupt keine Metrik definiert.

Die Entscheidungsgrenze wird dadurch nicht aufgeweicht: Eine positive Freigabe bleibt ohne Baseline oder Zielwert serverseitig blockiert; Pilot- und Go-live-Metrikgates bleiben zusätzlich unverändert. Negative Entscheidungen wie `Zurückgestellt` oder `Nicht weiterverfolgt` können dagegen auch dann fachlich sinnvoll sein, wenn die Messreife für eine positive Freigabe noch nicht erreicht ist.

## Prozessanalyse

Eine Prozessanalyse erfasst genau die Informationen, die zur Beurteilung des Problems und zur Formulierung eines Zielbilds benötigt werden:

- Prozessstart und Prozessende
- Auslöser und Ergebnis
- Ist-Ablauf
- Rollen und Verantwortlichkeiten
- Anwendungen und Arbeitsmittel
- Datenobjekte und Dokumente
- Geschäftsregeln
- Übergaben und Schnittstellen
- Bottlenecks und Ursachen
- Ausnahmen und Fehlerfälle
- Baseline und Prozesskennzahlen
- Prinzipien für den Soll-Prozess

Beim Anlegen aus einer Fokusphase bleibt deren Value-Stream-Kontext sichtbar, wird aber nicht als vermeintlich präziser Prozessinhalt vorausgefüllt. Insbesondere sind der Value-Stream-Auslöser nicht automatisch der Prozessauslöser und die Phasenbeschreibung nicht automatisch das Prozessergebnis. Prozessspezifische Grenzen werden bewusst eingegeben oder als noch offen benannt; unbekannte Fakten und Zahlen werden nicht erfunden.

Beobachtung beziehungsweise Problem, Ursachenhypothese und bestätigte Ursache werden semantisch getrennt. `ProcessValidation`, Provenance und Versions-/Stale-Mechanismen bleiben die kanonischen Nachweise für fachliche Validierung und Herkunft.

KI-Radar erzeugt kein BPMN-Modell. Vorhandene Prozessmodelle können weiterhin in spezialisierten Werkzeugen gepflegt werden.

## Lösungsoptionen

Nach einer positiven Fokusentscheidung können unterschiedliche Lösungsarten verglichen werden:

- organisatorische Änderung
- regelbasierte Automatisierung
- Standardsoftware
- individuelle Software
- Analytics oder Machine Learning
- generative KI
- Assistenzsystem
- hybride Lösung
- keine technische Lösung
- sonstige Option

Für jede bewertete Option werden die vorhandenen Vergleichsdimensionen um **Evidenzbasis** und **Time-to-Value** ergänzt. Time-to-Value ist ein Trade-off und keine automatische Priorisierung. Bei Hybrid-, Custom- oder sonstigen Lösungen wird ein KI-Anteil explizit dokumentiert; er wird nicht automatisch aus dem Lösungstyp abgeleitet.

Maximal eine Option kann je Prozessanalyse als bevorzugt markiert werden. Die Auswahl bleibt eine menschliche Entscheidung und wird mit Vergleichs-, Diagnose- und Evidenzsnapshot historisiert. LLM-Unterstützung darf Alternativen entwerfen, aber keine bindende Präferenz erzeugen.

Nur eine bevorzugte Lösung mit tatsächlicher KI-Komponente führt regulär in den KI-Use-Case-Pfad. Eine organisatorische, regelbasierte, Standardsoftware- oder andere Non-AI-Lösung kann die Discovery bewusst erfolgreich ohne KI-Use-Case abschließen. Analyse, Entscheidung und Begründung bleiben dabei auditierbar.

Beim Übergang aus einer bevorzugten KI-Lösungsoption beschreibt die Kurzbeschreibung des neuen Use Cases das konkrete Vorhaben. Der vollständige heutige Prozessablauf bleibt im kanonisch verknüpften Prozesskontext und wird nicht als scheinbare Use-Case-Lösungsbeschreibung dupliziert.

## Portfolio als Querschnitt

Portfolio ist kein einmaliger linearer Prozessschritt. Die Portfolio-Sicht vergleicht Vorhaben über mehrere Phasen hinweg, insbesondere Use Cases, Bewertung, Freigabe und Delivery. Sie zeigt unter anderem:

- Fachdomänen und Capabilities,
- Organisationseinheiten,
- Nutzen und technische Machbarkeit,
- Confidence und Entscheidungsstatus,
- Lifecycle und Lösungstyp,
- nicht einordenbare oder blockierte Vorhaben.

## Delivery-Handover

Ein Delivery Package kann nur aus einer final positiven Freigabe entstehen. Es konsolidiert Informationen aus Discovery, Fokusentscheidung, Prozessanalyse, Lösungsoption, Use Case, Bewertung und Freigabe.

Enthalten sind insbesondere:

- Problem- und Geschäftskontext
- Ziel, Nutzer und Nutzungsszenarien
- In-Scope und Out-of-Scope
- Lösungs-, System-, Daten- und Integrationskontext
- Ist-/Ziel-Systemlandschaft
- Daten- und Informationsflüsse
- Integrationsverträge und technische Verantwortlichkeiten
- Link zu Architekturdiagrammen oder weiteren Architekturartefakten
- funktionale und nichtfunktionale Anforderungen
- Security-, Datenschutz- und Rechtsanforderungen
- menschliche Aufsicht, Logging, Betrieb und Support
- MVP-Scope
- Akzeptanzkriterien und Testfälle
- Erfolgsmessung
- Risiken, Annahmen und Abhängigkeiten
- Architekturentscheidungen und Leitplanken
- initiales Backlog
- Link zum externen Delivery-System

Delivery Readiness 2.0 ordnet diese Inhalte sieben prüfbaren Sektionen zu. Jede Sektion besitzt eine sichtbare Herkunft, einen Prüfstatus und die erforderliche fachliche beziehungsweise technische Bestätigung. Automatisch übernommene Inhalte gelten als Entwurf und müssen bestätigt werden. Änderungen setzen die betroffene Sektion erneut auf **Prüfung erforderlich**.

Der System-, Daten- und Integrationskontext umfasst zusätzlich System of Record, Systemverantwortung und Zielkomponenten, Datenqualität und Zugriffsweg sowie Integrationsbetrieb und Fehlerbehandlung. Die Readiness-Prüfung liefert konkrete Blocker statt einer reinen Leerfeldliste und wird unmittelbar vor der Übergabe erneut serverseitig ausgeführt.

Für den Status **Bereit zur Übergabe** müssen Architektur- und Übergabepunkte entweder konkret beschrieben oder ausdrücklich als nicht relevant dokumentiert sein. Nichtanwendbarkeit benötigt eine Begründung. Leere, generische oder unbestätigte Angaben gelten nicht als ausreichend.

Packages sind versioniert. Der Status verläuft über:

```text
Entwurf → Bereit zur Übergabe → Übergeben
```

Übergebene Versionen sind unveränderlich. Änderungen werden in einer neuen Version dokumentiert. Der Inhalt kann als Markdown exportiert und in Jira, Azure DevOps, GitHub, Confluence oder vergleichbare Systeme übernommen werden.

Die methodische Herkunft der Struktur ist vollständig in [Delivery Methodology](DELIVERY_METHODOLOGY.md) dokumentiert. Die In-App-Ansicht und der Download verwenden dieselbe versionierte Markdown-Datei; daraus entsteht kein zusätzlicher Workflow und keine automatische Score-Berechnung.

## Bewusste Systemgrenze

KI-Radar verwaltet keine:

- Sprints oder Arbeitspakete während der Umsetzung
- Ressourcen oder Kapazitäten
- Zeiterfassung
- Delivery-Fortschrittsberichte
- frei konfigurierbaren Workflows
- vollständigen Enterprise-Architecture-Katalog

Die Systemlandschaft im Delivery Package ist eine umsetzungsbezogene Ist-/Ziel-Sicht, kein vollständiges Applikationsportfolio. KI-Radar sorgt dafür, dass ein fachlich begründetes und freigegebenes Vorhaben mit belastbarem Scope und den relevanten Architekturartefakten an Delivery übergeben wird. Die operative Umsetzung bleibt im spezialisierten Delivery-System.

## Umgesetzte Inkremente

1. Value Streams und optionale Herkunft eines Use Cases
2. Fokus-Screening und serverseitige Deep-Dive-Freigabe
3. Prozessanalyse und explizite Lösungsoptionen
4. Strukturierte Fachdomäne, Capability und Prozessbereich
5. Versioniertes Delivery Package mit Systemlandschaft und exportierbarem Handover
6. Delivery Readiness 2.0 mit Quellenmanifest, Sektionsbestätigungen und strukturierten Blockern
7. Vollständige methodische Referenz mit In-App-Ansicht und identischem Markdown-Download
8. Evidenzbewusste Fokusphase und technologieoffene Lösungsentscheidung mit Time-to-Value, Hybrid- und No-AI-Ausgang (#331)
9. Optionaler kanonischer Ursprungsprozess für direkte und geführte Use Cases mit abgeleitetem strategischem Value-Stream-Kontext (#322)
10. SIPOC als sichtbarer Scopingrahmen innerhalb der bestehenden ProcessAnalysis ohne separates Artefakt oder neue Pflichtfelder (#323)
11. Hypothesenfähiger Guided Intake mit unbekannter Baseline beziehungsweise unbekanntem Zielwert bis zur strukturierten Bewertung bei unveränderten positiven Freigabe- und Lifecycle-Gates (#340)

Der direkte Intake und der systematische Architecture-Pfad bleiben unabhängig nutzbar. Der Architecture-Pfad verlangt jedoch eine nachvollziehbare Auswahlentscheidung, bevor vertiefende Artefakte erzeugt werden.
