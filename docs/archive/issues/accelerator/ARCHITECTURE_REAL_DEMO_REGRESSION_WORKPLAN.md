# Architecture Real-DEMO & Regression – verbindlicher Workplan

Issue: #213  
Parent: #210  
Abhängigkeiten: #211, #212, #116, #124, #125  
Stand: 2026-08-10  
Startbasis `main`: `82e20644dd3b8404faf184d11c29d012204ee58f`

## Ziel und Grenze

#213 ist der Abnahme-, Regressions-, Drift- und Real-DEMO-Block für die bereits implementierten Fähigkeiten aus #211 und #212.

Die Umsetzung soll nicht erneut Architecture Advisor oder Evaluated Solution Workflow entwickeln, sondern deren bestehende produktive Contracts reproduzierbar an kanonischen, widersprüchlichen, adversarialen, Failure-, Concurrency- und End-to-End-Fällen prüfen.

#210 bleibt unverändert. #211 und #212 werden nicht fachlich erweitert. Neue Produktionslogik ist nur zulässig, wenn ein Test eine konkrete Verletzung eines bereits beschlossenen Contracts aus #210/#211/#212 nachweist. Zeigt ein Grenzfall lediglich eine methodische Grenze der V1-Logik, wird diese als `Assessment open` bzw. bekannte Grenze dokumentiert; daraus entsteht in #213 keine neue Klassifikationsregel.

Der Critic bleibt ein semantischer Qualitätsprüfer und kein Domain-, Governance-, Auswahl- oder Lifecycle-Gate. Der Architecture Advisor bleibt deterministisch und beeinflusst den Critic-/Repair-Pfad nicht.

## Fixierter Ausgangsstand

### Architecture Advisor aus #211

Maßgeblich bleiben insbesondere:

- exakt vier menschlich beantwortete Fragen mit `Ja`, `Nein`, `Unklar`;
- deterministische Klassifikation über `architecture-advisor-v1`;
- `No LLM required`, `Controlled LLM`, `LLM Workflow`, `Bounded Agent`, `Assessment open`;
- explizite Konflikt- und Boundary-Erkennung vor positiver Klassifikation;
- symmetrische Behandlung von `Unklar` über mögliche Ja/Nein-Vervollständigungen;
- maschinenlesbare Reason Codes und deterministische Explainability;
- bestehender vollständiger 81-Kombinationen-Driftvertrag;
- keine automatische Lösungsauswahl und kein fachliches Gate.

Die 81er-Matrix wird in #213 nicht ersetzt oder dupliziert. Sie bleibt der vollständige kombinatorische Contract. #213 ergänzt eine kleinere, fachlich lesbare Referenzmenge mit konkreter Bedeutung und expliziten adversarialen Fällen.

### Evaluated Solution Workflow aus #212

Maßgeblich bleibt die Reihenfolge:

Generate -> deterministic Validate -> Critic -> optional exactly one Repair -> deterministic Validate -> final Critic -> Human Review

Zusätzlich bleiben insbesondere unverändert:

- kanonischer Effective-Preview-Contract;
- Original -> erfolgreicher Machine-Repair -> Human Edits;
- Quality-Snapshot und Whole-Preview-CAS;
- persistierte Quality-Step-Reservierung vor externem Provider-Aufruf;
- pro `SolutionGenerationRun` höchstens je ein `initial_critic`, `repair`, `final_critic`;
- ein Repair-Lauf darf mehrere exakt durch Findings freigegebene Targets atomar behandeln;
- fremde, fehlende, doppelte oder deterministisch ungültige Repair-Ziele werden vollständig verworfen;
- keine Retry-Schleife für Critic, Repair oder Final Critic;
- maximal vier Modellaufrufe inklusive Generation;
- letzter deterministisch valider Preview-Zustand bleibt bei nachgelagerten Fehlern erhalten;
- keine automatische Änderung fachlicher Bewertungs-, Auswahl-, Governance-, Delivery- oder Lifecycle-Zustände.

## Referenzdaten- und Fixture-Vertrag

#213 verwendet versionierte Daten-Artefakte statt fachlich relevanter Inline-Testdaten.

Bevorzugte Struktur:

- `tests/fixtures/architecture_real_demo_v1.json`
- `tests/fixtures/architecture_real_demo_v1.schema.json`

Die Haupt-Fixture enthält mindestens:

1. `schema_version` und `fixture_version`;
2. zwölf fachlich benannte Advisor-Fälle;
3. Critic-/Repair-Regressionsfälle mit erwarteten semantischen Contracts;
4. synthetische/anonymisierte Prozess- und Lösungsdaten für den Real-DEMO-Nachweis;
5. erwartete Invarianz-Marker für geschützte Domain-/Gate-Zustände.

Die Fixture ist ein Daten-Artefakt und darf nicht vom produktiven Code importiert werden. Tests lesen sie als Erwartungs- und Eingabebasis. Fachlich relevante Änderungen müssen als sichtbarer Fixture-Diff reviewbar sein.

Das JSON-Schema fixiert Struktur, Pflichtfelder, erlaubte Advisor-Antwortwerte, bekannte Modes/Reason Codes und die für die Regressionsfälle erforderlichen Felder. Es bildet keine zweite produktive Business-Logik nach.

## Advisor-Referenzset

Es werden zwölf explizit benannte Fälle fixiert.

### Fünf kanonische Fälle

1. `No LLM required` – stabile einfachere/deterministische Lösung reicht aus.
2. `Controlled LLM` – semantische Verarbeitung erforderlich, ein klar begrenzter KI-Schritt reicht.
3. `LLM Workflow` – semantische Verarbeitung plus mehrere bekannte KI-Schritte, Ablauf vollständig vorgegeben.
4. `Bounded Agent` – dynamische Schritt-/Toolwahl ist tatsächlich erforderlich.
5. `Assessment open` – mindestens eine entscheidungsrelevante Information fehlt.

### Sieben widersprüchliche/adversariale Fälle

6. einfachere deterministische Lösung reicht und semantisches LLM wird gleichzeitig als erforderlich angegeben;
7. mehrere feste KI-Schritte und dynamische Orchestrierung werden gleichzeitig als erforderlich angegeben;
8. einfachere Lösung reicht nicht und semantisches Reasoning ist ebenfalls nicht erforderlich;
9. dynamische Toolwahl wird behauptet, obwohl der Ablauf ansonsten als vollständig fest beschrieben wird;
10. alle vier entscheidenden Antworten sind `Unklar`;
11. fachlich sehr komplexe Aufgabe mit vollständig festem Ablauf – hohe inhaltliche Komplexität allein darf nie `Bounded Agent` erzeugen;
12. klarer dynamischer Gegenkontrollfall – `Bounded Agent` ist nur dann korrekt, wenn dynamische Orchestrierung tatsächlich erforderlich ist und kein Widerspruch vorliegt.

Jeder Fall enthält mindestens:

- stabilen Fall-Identifier und lesbaren Namen;
- die vier Advisor-Antworten;
- erwarteten Architecture Mode;
- erwartete Reason Codes;
- Erwartung für sichtbare `Warum dieses Muster?`-/`Warum kein Agent?`-/Open-Point-Semantik, soweit für den Fall relevant.

Die Erwartungen werden aus dem bereits beschlossenen #211-Contract abgeleitet. #213 führt keine neue Regelpräzedenz ein.

## `Assessment open`-Beobachtung als sichtbares Artefakt

Aus dem fixierten Referenzset wird deterministisch ein eingecheckter Bericht erzeugt:

- `docs/accelerator/ARCHITECTURE_REAL_DEMO_ASSESSMENT_OPEN_REPORT.md`

Er enthält mindestens:

- Anzahl getesteter Advisor-Fälle;
- Anzahl klassifizierter Fälle;
- Anzahl `Assessment open`;
- Reason-Code-Verteilung der offenen Fälle;
- Liste der offenen Fall-Identifier und Gründe;
- ausdrücklichen Hinweis, dass die V1-Logik expert-informed und noch nicht empirisch an einer breiten Menge realer Unternehmensfälle kalibriert ist;
- ausdrücklich keine Mindest-Klassifikationsquote und kein Erfolgsziel.

Ein Test erzeugt den Bericht deterministisch erneut und verlangt inhaltliche Identität zum committed Artefakt. Damit verschwindet die geforderte Statistik nicht in Konsolenlogs.

## Critic-/Repair-Regressionsvertrag

Die bestehende #212-Testfamilie bleibt maßgeblich. #213 erstellt eine explizite Traceability-Matrix und ergänzt nur Lücken.

Mindestens abgedeckt werden:

- nahezu identische Optionen / fehlende Distinctiveness;
- fehlender Bottleneck-Bezug;
- qualitative unbelegte Aussage;
- korrekt ausgewiesene Annahme oder offene Evidenz als positiver Kontrollfall;
- unnötige KI-/Architekturkomplexität;
- strukturierte Finding-Referenz auf Option, Feld und Evidenz;
- Critic-Ausfall bei weiterhin nutzbarer deterministisch valider Original-Preview;
- Repair-Ausfall ohne Veränderung der Original-Preview;
- Repair mit ungültigem deterministischem Contract wird vollständig verworfen;
- kollidierende Human Edits werden durch Machine-Repair nicht überschrieben;
- exakt ein zulässiger Repair-Lauf;
- kein zweiter Repair nach Final Critic;
- verbleibendes Finding nach Final Critic endet in Human Review;
- maximale LLM-Aufrufzahl wird eingehalten.

Assertions prüfen semantische Felder und Zustände wie `criterion`, Option, Feld, Source IDs, `repairable`, Step Type, Status, Snapshot-/Target-Bindung und Preview-Invarianz. Freie LLM-Prosa wird nicht als vollständiger Golden String geschützt, sofern sie nicht bereits Teil eines ausdrücklich versionierten sichtbaren Contracts ist.

## Cross-Feature-Isolation

Advisor und Evaluated Solution Workflow sind zwei getrennte Fähigkeiten und müssen auch unter #213 getrennt bleiben.

Mindestens zwei Regressionsrichtungen werden nachgewiesen:

1. eine Advisor-Klassifikation – einschließlich `Bounded Agent` oder `Assessment open` – verändert weder Input, Finding-Verhalten, Repair-Eligibility, Snapshot, Call-Zahl noch Endzustand des Critic-/Repair-Pfads;
2. Initial Critic, Repair und Final Critic verändern weder Advisor-Antworten, gespeicherten Advisor-Mode, Reason Codes noch Ruleset-/Assessment-Version.

Damit darf aus einer Architekturklassifikation keine versteckte Quality-Control-Präzedenz entstehen und umgekehrt.

## Concurrency- und One-Shot-Nachweis

Der in #212 implementierte Reservierungs- und Unique-Constraint-Schutz wird zusätzlich als echte Nebenläufigkeitsregression geprüft.

Mindestens ein Test startet zwei nahezu gleichzeitige Repair-Trigger für dieselbe Generation/Preview. Erwartung:

- genau eine persistierte Repair-Reservierung;
- höchstens ein externer Repair-Provider-Aufruf;
- kein doppelter Machine-Repair;
- kein zweiter Repair-Lauf nach terminalem Zustand;
- deterministisch valider Preview-Zustand bleibt erhalten.

Der Test soll die produktive Reservierungslogik und Datenbankrestriktion verwenden, nicht lediglich zwei sequenzielle Mock-Aufrufe als Concurrency-Ersatz.

## Gate- und Rückwärtskompatibilität

Vor und nach den relevanten Advisor-/Critic-/Repair-Läufen werden geschützte Zustände explizit gelesen und verglichen.

Architecture Advisor, Critic und Repair dürfen niemals automatisch verändern:

- `feasibility`;
- `integration_effort`;
- `evaluation_status`;
- `recommendation` bzw. bevorzugte Option;
- Process Validation;
- Solution Selection Decision;
- Use Case;
- Governance Assessment / Review;
- Delivery;
- Lifecycle.

Zusätzlich werden mindestens zwei Rückwärtskompatibilitätsfälle geprüft:

- bereits manuell angelegte `SolutionOption`-Objekte;
- bestehende normale Block-7-Previews ohne #213-spezifische Fixture-Metadaten.

Die Prüfung erfolgt über reale Persistenz-/Servicepfade. Reine Mock-Zähler sind kein ausreichender Gesamtnachweis für Gate-Invarianz.

## Reproduzierbarer Real-DEMO-Vertrag

Der zentrale E2E-Nachweis verwendet produktive Services, Contracts, Persistenz- und Validierungswege. Er baut keinen parallelen Fake-Workflow.

Externe Providergrenzen werden deterministisch ersetzt.

Der Provider-Stub muss:

- bei identischem kanonischem Input identischen Output liefern;
- ohne Zufall, Uhrzeit, UUID-/Timestamp-Rauschen oder laufabhängige Textvarianten arbeiten;
- Aufrufreihenfolge und Aufrufzahl protokollieren;
- den erwarteten Generator-, Initial-Critic-, Repair- und Final-Critic-Contract bedienen;
- unbekannte bzw. unerwartete Inputs fail-closed ablehnen, statt still irgendeinen Default-Output zurückzugeben.

Der Real-DEMO-Lauf zeigt mindestens:

1. synthetische/anonymisierte bestehende Prozess-/Lösungsdaten als Ausgangslage;
2. Architecture Advisor auf mehreren unterschiedlich gelagerten Fällen;
3. sichtbare `Warum / Warum kein Agent?`-Begründungen;
4. mindestens einen bewusst offenen oder widersprüchlichen Advisor-Fall;
5. valide Block-7-Generierung;
6. deterministische Validierung vor Initial Critic;
7. strukturierte Critic-Findings;
8. genau einen gezielten Repair-Lauf auf einem reparierbaren Finding;
9. erneute vollständige deterministische Validierung;
10. Final Critic;
11. anschließenden Human-Review-Zustand;
12. unveränderte fachliche Gates;
13. erwartete maximale Modellaufrufzahl.

Für den vollständigen Repair-Pfad gilt als maximale Providersequenz pro `SolutionGenerationRun`:

1. Generate;
2. Initial Critic;
3. Repair;
4. Final Critic.

Es wird keine Quote erhöht, um diesen Nachweis zu ermöglichen.

## Datenschutz der Real-DEMO-Daten

#213 verwendet ausschließlich synthetische oder bereits ausdrücklich anonymisierte Testdaten.

Keine echten Produktions-, Kunden-, Bewerber-, Mitarbeiter- oder sonstigen personenbezogenen Daten werden in Fixture, Snapshot, CI-Artefakt oder Dokumentation eingecheckt. Namen, IDs, Zeitwerte und Prozessdetails der Fixture müssen künstlich bzw. nicht personenbeziehbar sein.

Die Anforderung „bestehende Prozess-/Lösungsdaten als Ausgangslage“ bedeutet im CI-/Regression-Kontext vorhandene, persistierte Domain-Strukturen und nicht reale Produktionsdaten.

## CI-Zeitbudget für den Real-DEMO-E2E

Der deterministische Provider-Stub enthält keinen Netzwerkzugriff. Der gezielte #213-Real-DEMO-E2E soll deshalb in CI ein hartes maximales Step-Budget erhalten.

Vorgabe für AP6:

- eigener gezielter CI-Step für den #213-E2E;
- `timeout-minutes: 3` für diesen Step;
- danach weiterhin die vollständige normale Repository-Test-Suite;
- ein Timeout gilt als CI-Fehler und wird nach der unten fixierten CI-Regel analysiert.

Die drei Minuten sind bewusst deutlich über der erwarteten lokalen Laufzeit eines providerlosen Django-Integrationstests, begrenzen aber einen hängenden Concurrency-/DB-/State-Machine-Fall, bevor er den gesamten CI-Lauf unbegrenzt blockiert.

## Drift-Grundsätze

Drift-Schutz wird in zwei Stufen aufgebaut:

1. bereits mit der Fixture in AP2: Schema, Version, Fall-Identifier und explizite erwartete Mode-/Reason-/Quality-Contracts werden strukturell fixiert;
2. in AP7: die fachlich relevanten Decision-/Critic-/Repair-/State-Machine-Verträge und sichtbaren Abschlussartefakte werden als gesamter #213-Driftvertrag konsolidiert.

Nicht blind gehasht werden komplette freie LLM-Texte oder zufällige Persistenzmetadaten. Geschützt werden insbesondere:

- Advisor-Inputs -> Mode -> Reason Codes;
- erwartete Explainability-Kategorien;
- Critic-Kriterien und strukturierte Target-/Evidence-Referenzen;
- Repair-Target-Bindung und One-Shot-Regel;
- Quality-Step-Reihenfolge;
- maximale Provider-Aufrufzahl;
- Gate-Invarianz;
- Assessment-open-Statistik aus dem fixierten Referenzset.

## Traceability-Prinzip

Für jedes Abnahmekriterium aus #213 wird nachvollziehbar dokumentiert:

Issue-Kriterium -> Fixture-Fall oder bestehender Contract -> Testdatei/Testfall -> Ergebnis/Artefakt.

Ein bestehender #211/#212-Test darf als Nachweis wiederverwendet werden, wenn er das Kriterium bereits exakt abdeckt. #213 erzeugt keine redundanten Duplikattests nur zur Erhöhung der Testanzahl.

## Arbeitspakete

### AP1 – Scope Lock, Contract-Inventur und Traceability-Matrix

- tatsächlichen `main`-Stand sowie geschlossene Abhängigkeiten erneut verifizieren;
- #213-Abnahmekriterien vollständig gegen bestehende #211/#212-Contracts und Tests mappen;
- fehlende Nachweise von bereits erfüllten Nachweisen trennen;
- explizite Entscheidungsregel festhalten: Contract-Verletzung -> minimaler Bugfix; methodische V1-Grenze -> dokumentieren/`Assessment open`, keine spontane Scope-Erweiterung;
- erste Traceability-Matrix als Dokument anlegen;
- #210 unverändert lassen.

### AP2 – Versionierte Referenz-Fixtures, Schema und früher Drift-Vertrag

- `architecture_real_demo_v1.json` als versioniertes Daten-Artefakt anlegen;
- JSON-Schema ergänzen;
- zwölf Advisor-Fälle und die benötigten Critic-/Repair-Fälle strukturiert aufnehmen;
- ausschließlich synthetische/anonymisierte Real-DEMO-Ausgangsdaten verwenden;
- Fixture-Schema-/Version-/Identifier-Drift bereits ab diesem AP testen;
- produktiven Code von Fixture/Fixture-Generator vollständig entkoppelt halten.

### AP3 – Advisor-Adversarial-Regression und Assessment-open-Artefakt

- zwölf Advisor-Fälle über die echte produktive Klassifikationsfunktion ausführen;
- kanonische, widersprüchliche, Boundary-, `Unklar`- und Complexity-vs-Agent-Fälle explizit prüfen;
- bestehenden 81-Kombinationen-Contract nicht duplizieren, sondern als vollständigen Basisschutz weiterverwenden;
- Anzahl klassifizierter/offener Fälle und Reason-Code-Verteilung deterministisch erzeugen;
- `ARCHITECTURE_REAL_DEMO_ASSESSMENT_OPEN_REPORT.md` einchecken und gegen erneute deterministische Generierung testen;
- expert-informed-/nicht-empirisch-kalibriert-Grenze sichtbar dokumentieren.

### AP4 – Critic-/Repair-Regressionsmatrix und Cross-Feature-Isolation

- alle in #213 geforderten semantischen Critic-/Repair-Fälle auf bestehende Tests mappen und echte Lücken ergänzen;
- positive Kontrolle für korrekt ausgewiesene Annahme/offene Evidenz absichern;
- strukturierte Option-/Feld-/Evidenz-Referenzen prüfen;
- Failure Preservation für Critic und Repair prüfen;
- Cross-Feature-Isolation Advisor -> Quality Workflow und Quality Workflow -> Advisor explizit testen;
- keine freie LLM-Prosa unnötig als Golden String fixieren.

### AP5 – Gate-, Backward-Compatibility-, Concurrency- und One-Shot-Invarianz

- vollständigen Vorher-/Nachher-Vergleich der geschützten Domain-/Gate-Zustände ergänzen;
- bestehende manuelle SolutionOptions und normale Block-7-Previews als Rückwärtskompatibilität prüfen;
- zwei nahezu gleichzeitige Repair-Trigger gegen die produktive Reservierungs-/DB-Constraint-Logik testen;
- maximal einen Repair-Provider-Aufruf und genau eine Repair-Reservierung nachweisen;
- kein zweiter Repair nach terminalem/finalem Zustand;
- bei gefundenen Contract-Verletzungen nur minimalen Bugfix zulassen.

### AP6 – Reproduzierbarer Real-DEMO-E2E mit deterministischem Provider

- produktionsnahen E2E über echte Services, Validatoren, Persistenz-, Snapshot-/CAS- und Quality-Step-Pfade aufbauen;
- ausschließlich die externe Providergrenze deterministisch ersetzen;
- Provider-Stub input-deterministisch, ohne Zufall/Zeitstempel und fail-closed für unerwartete Inputs implementieren;
- Aufrufreihenfolge und maximale Aufrufzahl `Generate -> Initial Critic -> Repair -> Final Critic` prüfen;
- synthetische/anonymisierte Prozess-/Lösungsdaten verwenden;
- sichtbare Advisor-Erklärungen, mindestens einen offenen Advisor-Fall, Critic-Finding, einmaligen Repair, Revalidierung, Final Critic und Human Review nachweisen;
- fachliche Gates vor/nach dem Lauf unverändert nachweisen;
- gezielten CI-Step mit `timeout-minutes: 3` ergänzen und danach vollständige Repository-Suite weiterlaufen lassen.

### AP7 – Contract-/Fixture-Drift-Schutz und methodische Grenzen

- frühen Fixture-Driftvertrag aus AP2 mit Decision-/Critic-/Repair-/State-Machine-Semantik konsolidieren;
- Advisor Mode-/Reason-Code-Erwartungen, Quality-Kriterien, Repair-Bindung, One-Shot, Call Cap und Gate-Invarianz schützen;
- Assessment-open-Bericht als reproduzierbares Artefakt in den Driftvertrag aufnehmen;
- keine kompletten freien LLM-Texte oder laufabhängige Metadaten unnötig hashen;
- bekannte methodische Grenzen von Advisor und Critic dokumentieren;
- ausdrücklich keine objektive Architekturklassifikation oder empirische Kalibrierung behaupten.

### AP8 – Abschlussnachweis und vollständige Repository-CI

- finale Testmatrix Issue-Kriterium -> Fixture/Contract -> Test -> Ergebnis erstellen;
- zwölf Advisor-Fälle samt Resultat dokumentieren;
- Assessment-open-Häufigkeit und Reason Codes dokumentieren;
- Critic-/Repair-, Cross-Feature-, Failure-, Concurrency-, One-Shot-, Backward-Compatibility- und Gate-Nachweise zusammenführen;
- Real-DEMO-Sequenz und tatsächliche Provider-Aufrufzahl dokumentieren;
- bekannte methodische Grenzen und alle Abweichungen vom Workplan transparent aufführen;
- vollständige Repository-CI grün nachweisen;
- nach Merge und vollständig grüner CI AP8 abhaken und #213 erst dann abschließen.

## Arbeitsweise und PR-Sequenz

Dieser Workplan wird vor AP1 über einen eigenen isolierten Pull Request fixiert.

Danach gilt:

- jedes AP wird einzeln und nacheinander umgesetzt;
- jedes AP erhält einen eigenen Commit/PR;
- kein gesammelter Abschluss-PR am Ende;
- nächstes AP erst nach Merge und vollständig grüner CI des vorherigen;
- nach jedem gemergten AP wird der identische Checklistenpunkt in #213 abgehakt;
- AP-Titel im Issue müssen exakt den Überschriften dieses Dokuments entsprechen;
- der Workplan-PR wird im Issue #213 referenziert;
- #210 wird nicht verändert.

## Verbindliche CI-Regel

Bei einem fehlgeschlagenen CI-Lauf sofort einen Fix pushen und neuen Lauf anstoßen ist verboten. Immer zuerst den kompletten Lauf abwarten, alle Fehler aus allen Jobs sammeln und keine Vermutungen aufstellen, sondern die Hinweise aus dem Log verwenden, dann alle in einem Commit beheben, erst danach neuen Lauf starten. Ausnahme nur, wenn ein Fehler alle Folge-Jobs blockiert und deren Fehler verdeckt.

## Abschlussstandard

#213 gilt erst als abgeschlossen, wenn mindestens folgende Nachweise gemeinsam vorliegen:

- mindestens fünf kanonische und fünf widersprüchliche/adversariale Advisor-Fälle; Zielmenge dieses Workplans: zwölf;
- sichtbares, reproduzierbares Assessment-open-Artefakt;
- hohe Komplexität allein erzeugt keinen Agenten-Ausgang;
- vollständige Critic-/Repair-Regression einschließlich Failure Preservation und positiver Evidenzkontrolle;
- Cross-Feature-Isolation in beide Richtungen;
- echter Concurrency-Nachweis für One-Shot-Repair;
- Critic bleibt strukturiert testbar, aber kein Domain-/Governance-Gate;
- Real-DEMO nutzt produktive Kernpfade und eine deterministische Providergrenze;
- Provider liefert bei identischem Input identischen Output und fail-closed bei unerwartetem Input;
- ausschließlich synthetische/anonymisierte Referenzdaten;
- Gate-Invarianz und Rückwärtskompatibilität explizit nachgewiesen;
- fachlich relevanter Drift-Schutz vorhanden;
- bekannte methodische Grenzen dokumentiert;
- vollständige Repository-CI grün.

## Nicht-Ziele von #213

- Änderung von #210;
- neue Architecture-Advisor-Fragen, Modes, Scores oder Regeln;
- empirische Branchenstudie;
- behauptete objektive Architekturklassifikation;
- automatische Agenten-Empfehlung allein aus Komplexität;
- Multi-Agent-System;
- Performance-Benchmark von Agent-Frameworks;
- Erweiterung des Critic zu einem Domain-/Governance-Gate;
- automatisches Setzen von Bewertung, Rangfolge, Recommendation oder bevorzugter Option;
- zweiter Repair-Versuch oder Retry-Schleife;
- generische Workflow-/Rules-/Critic-Plattform;
- reale Produktions- oder personenbezogene Daten in Test-/Demo-Artefakten.
