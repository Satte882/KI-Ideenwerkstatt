# Issue #117 – Paket 3: Real-Provider- und Human-Review-Runbook

Issue: #117  
Fix-PR: #123  
Branch: `fix/issue-117-structured-mapping-completeness`  
Basis vor Paket 3: `16ac3c546454871beced6f488c542fc8914e003a`

## 1. Ziel

Paket 3 ist ein begrenzter Integrationsnachweis für den in #117 eingeführten Structured-Mapping-Contract.

Paket 2 hat deterministisch gezeigt:

> Ein aktivierter, explizit quellengebundener Mapping-Contract kann nicht mit fehlenden, doppelten, unerwarteten oder falsch gebundenen Assignments READY erreichen.

Paket 3 soll zusätzlich belegen:

1. dass der **normale Produktpfad** den Contract tatsächlich aktiviert;
2. dass der reale Synthesizer den Contract verarbeiten kann;
3. dass der reale Repair-Pfad einen kontrollierten Coverage-Fehler verarbeiten kann;
4. dass der reale Verifier ein strukturell vollständiges, aber fachlich falsches Mapping erkennt;
5. dass mindestens AP4-02 und AP4-04 je ein fachlich korrektes, vollständiges und menschlich bestätigtes READY-Ergebnis erreichen.

Paket 3 ist **kein Performance-, Reliability- oder Modellvergleichsexperiment**.

## 2. P3.0 – Activation Gate vor Provider-Runs

### Befund

`structured_mapping_obligations` ist im Paket-2-Contract absichtlich explizit und standardmäßig leer.

Der normale UI-Start erzeugt bisher jedoch einen `StartInvestigationRequest` ohne Obligation. Damit beweisen die Paket-2-Tests bislang den ausdrücklich aktivierten Pfad, nicht automatisch den produktiven UI-Pfad.

### Entscheidung

Vor dem ersten Providerlauf wird der Activation Contract geschlossen:

1. Bei **„Untersuchungsgrundlage festlegen“** kann der Mensch optional eine vollständige fallbezogene Mapping-Pflicht autorisieren.
2. Diese fachliche Eingabe wird zusammen mit der Quellenbasis im unveränderlichen `InvestigationSourceSnapshot.process_context` eingefroren.
3. Sie enthält nur Scope, keine fachlichen Ergebniswerte:
   - gebundene CSV-Quelle;
   - Case-Key-Spalte;
   - explizite Case-Key-Sollmenge;
   - Mapping-Dimension;
   - `exhaustive=true`.
4. Beim Run-Start materialisiert der Server daraus automatisch die bereits vorhandene `structured_mapping_obligation` mit Snapshot-, Manifest-, Source- und Revision-Bindung.
5. Ein Caller darf einen eingefrorenen Snapshot-Contract nicht mit einer abweichenden Request-Obligation überschreiben.
6. Alte Snapshots ohne Mapping-Spec bleiben unverändert und erzeugen keine Mapping-Pflicht.
7. Keine fachliche Klassifikation wird aus CSV-Zeilen, gelesenen Zeilen oder Python-Logik abgeleitet.

### Technische Leitplanken

- keine Migration: der Contract wird im bestehenden immutable `process_context` gespeichert;
- keine zweite State Machine;
- keine automatische „jede CSV-Zeile ist Pflicht“-Heuristik;
- keine Golden-Set-IDs im Produktcode;
- bestehende Runtime-Unterstützung für mehrere Obligations bleibt erhalten;
- die Produktoberfläche aktiviert zunächst genau **eine optionale Mapping-Pflicht pro autorisiertem Snapshot** (KISS);
- Runtime-/Programmatic Caller dürfen weiterhin mehrere explizite Obligations verwenden.

### Exit P3.0

Vor Providerkosten müssen deterministisch grün sein:

- Snapshot-Spec wird validiert und eingefroren;
- normaler Run-Start übernimmt sie ohne manuell gesetzte Request-Obligation;
- abweichender Override failt closed;
- ungültige Source/Spalte/Keys failen vor Snapshot-Freigabe;
- Snapshot ohne Spec bleibt unverändert;
- bestehende #117-Regressionen bleiben grün;
- vollständige CI grün.

Solange P3.0 nicht erfüllt ist: **0 Provider-Runs**.

## 3. Eingefrorener Paket-3-Vertrag

Vor dem ersten realen Lauf werden festgehalten:

- exakter getesteter Commit;
- sauberer Checkout;
- Loop / Policy / Prompt / Schema-Versionen;
- Modell, Provider, Reasoning und Transport-Policy;
- Source-Pack-Hashes;
- Snapshot-ID und Manifest-Hash;
- materialisierte Structured-Mapping-Obligation;
- erwarteter Testtyp und erwarteter Endzustand;
- persistentes EvidenceCampaign-Budget.

Die Paket-2-Versionen bleiben für diesen PR:

- Loop `vs1-agent-loop-v21`;
- Policy `vs1-stop-policy-v6`;
- Synthesizer `vs1-synthesis-v16` / Schema `vs1-synthesis-schema-v6`;
- Verifier `vs1-verifier-v8` / Schema `vs1-verifier-schema-v5`.

Da v21 noch nicht gemergt oder als Provider-Evidence verwendet wurde, ist die P3.0-Aktivierung eine Vervollständigung desselben #117-Contracts und kein separater v22-Rollout.

## 4. Provider-Budget

Das Paket bleibt klein und endlich:

- maximal **5 Investigation-Runs**;
- regulär geplant: **4 Runs**;
- Run 5 nur bei einer vorher benannten offenen Integrationsfrage;
- maximal **40 reale Provider-Calls/Attempts** über das Paket;
- Providerkosten-Cap: **5 USD**;
- keine Budgeterweiterung ohne neues Gate;
- technische Runtime-Retries innerhalb des bestehenden Contracts bleiben erlaubt und werden vollständig dokumentiert;
- ein neuer Ersatz-Run ist kein stiller Retry, zählt gegen das Run-Budget und braucht eine dokumentierte Begründung.

Keine Wiederholung bis zum gewünschten Ergebnis.

## 5. Predeclared Run-Matrix

### P3-A – AP4-02 positiver End-to-End-Run

Typ: **positive**

Zweck:

- reale Erzeugung des vollständigen E01–E06-Mappings;
- deterministischer Coverage-/Binding-Guard;
- semantische Verifier-Prüfung;
- fachlich korrektes READY.

Human-Review-Authority:

- E02 / E03 / E06: `manual_review`;
- E01 / E04 / E05: kein `manual_review`.

Erwartung:

> fachlich korrektes, vollständiges, quellengebundenes und menschlich bestätigtes READY.

### P3-B – AP4-04 positiver End-to-End-Run

Typ: **positive**

Zweck:

- reale Erzeugung des vollständigen R01–R05-Mappings im Hybridfall;
- Guard + Verifier + READY.

Human-Review-Authority:

- R02 / R03 / R05: `manual_review`;
- R01 / R04: `standard`.

Erwartung:

> fachlich korrektes, vollständiges, quellengebundenes und menschlich bestätigtes READY.

### P3-C – AP4-02 kontrollierter Missing-Assignment-/Repair-Fall

Typ: **negative coverage + real repair**

Der Fall wird als **eigene neue Test-Evidence** initialisiert. Keine historische oder positive Modellantwort wird nachträglich manipuliert.

Ausgangszustand:

- gültiger aktivierter E01–E06-Contract;
- strukturell valides Package;
- genau ein verpflichtendes Assignment fehlt;
- vorhandene Assignments bleiben korrekt gebunden.

Erwartete Kette:

1. deterministischer Guard meldet den konkreten Coverage-Blocker;
2. kein READY;
3. der reale Synthesizer erhält den dokumentierten Pre-Verifier-Repair-Kontext;
4. fehlendes Assignment wird ergänzt;
5. keine unbegründete Änderung zuvor korrekter Assignments;
6. keine erforderlichen Fälle gehen verloren;
7. jede fachliche Änderung bleibt Evidence-/Finding-gestützt;
8. frischer Verifier ist an das reparierte Package gebunden;
9. nur bei fachlich korrektem finalen Package darf READY entstehen.

Falls der reale Repair-Pfad nicht ausgeführt werden kann, wird **nicht** behauptet, dass reale Repair-Fähigkeit bewiesen sei. Der deterministische Repair-Nachweis aus Paket 2 bleibt dann bestehen und Paket 3 wird entsprechend begrenzt bewertet.

### P3-D – AP4-04 semantische Verifier-Negativkontrolle

Typ: **negative semantic verifier control**

Eigene neue Test-Evidence; keine historische oder positive Modellantwort wird still verändert.

Ausgangszustand:

- vollständige Sollmenge R01–R05;
- alle Assignments strukturell vorhanden;
- alle Source-/Revision-/Row-Bindungen korrekt;
- genau ein materieller Wert bewusst falsch klassifiziert;
- Python-Guard muss das Package strukturell passieren lassen.

Erwartung:

> Der reale Verifier erzeugt ein dem falschen Mapping zuordenbares kritisches Finding; der Run darf nicht auf Basis dieses fehlerhaften Packages freigegeben werden.

Ein sicherer FAILED-/nicht-READY-Ausgang kann diese **Negativkontrolle** bestehen. Er ersetzt keinen Positivnachweis.

Bei einem späteren READY muss das finale Mapping wieder exakt das eingefrorene Fallset
enthalten und der mutierte Zielwert dem vorab festgelegten Sollwert entsprechen. Diese
Sollwertprüfung gehört ausschließlich zum Evidence-Harness; fachliche Klassifikation bleibt
im Produkt Aufgabe des Verifiers und der menschlichen Bewertung.

Für beide Kontrollproben zählt nur der neueste Verifier-Bericht: erfolgreich, ohne kritische
Findings und an den nichtleeren Hash des finalen Briefs gebunden. Ein früherer Erfolg darf
eine spätere fehlgeschlagene Prüfung nicht überdecken. Die Zusammenfassung exportiert
`final_brief_hash` und die `context_refs` der Modellaufrufe, damit Repair- und Verifier-Bindung
zusammen mit dem Mutation-Audit nachvollziehbar bleiben.

### P3-E – optionaler unbetroffener Kontrollfall

Nur starten, wenn P3-A bis P3-D eine konkrete offene Frage hinterlassen, zum Beispiel:

- unbeabsichtigte Verschärfung eines CSV-Pfads ohne Mapping-Pflicht;
- Regression eines Textpfads.

Kein fünfter Run nur zum Ausschöpfen des Budgets.

## 6. UNKNOWN-Regel

Der Synthesizer darf technisch einen Wert wie `unknown` materialisieren.

Für Paket 3 gilt:

- ein vollständig aufgelistetes Mapping mit unbegründeten `unknown`-Werten ist **kein positiver Nachweis**;
- bei AP4-02/AP4-04 sind die hier geprüften Sollwerte aus der eingefrorenen Evidence bestimmbar;
- ein berechtigtes entscheidungskritisches Unknown kann einen korrekten Klärungszustand erfordern;
- vollständige Schlüssel allein rechtfertigen kein READY.

## 7. Evidence pro gestartetem Run

Jeder gestartete Run bleibt Evidence, auch FAILED/ABORTED/technisch fehlerhaft.

Mindestens dokumentieren:

### Freeze

- Run-ID;
- getesteter Commit;
- Runtime-/Prompt-/Schema-Versionen;
- Modell/Provider/Reasoning;
- Snapshot-ID;
- Manifest- und Source-Hashes;
- Contract Hash;
- materialisierte Obligation;
- Testtyp und erwarteter Endzustand.

### Synthese / Repair

- Synthese-Modus;
- tatsächlich gespeicherter Modellkontext bzw. dessen persistierte Bindungen;
- akzeptierter Wire-Payload;
- resultierendes `brief_payload.structured_mappings`;
- Mapping je Case-Key;
- References;
- Pre-Verifier-Blocker vor und nach Repair.

### Verifier

- tatsächlicher Verifier-Input bzw. persistierte Bindung;
- Brief-/Register-/Contract-/Manifest-Hashes;
- akzeptierter Verifier-Payload;
- Findings und Severity;
- finale Verifier-Freigabe.

`checked_critical_claims` wird **nicht** als Beweis erfunden, dass jedes Structured Mapping geprüft wurde. Für die Mapping-Negativkontrolle zählen tatsächlicher Verifier-Input und das konkrete Finding.

### Final State

- READY / WAITING_HUMAN / FAILED / ABORTED;
- Anzahl Provider-/Model-Calls;
- Repairs/Retries;
- finale Mapping-Struktur;
- Kosten, soweit durch die bestehende EvidenceCampaign belastbar erfasst.

## 8. Human Review

Alle gestarteten Paket-3-Runs werden menschlich bewertet.

Pro Run mindestens:

1. Mapping vollständig?
2. Mapping fachlich korrekt?
3. Source-/Revision-/Row-Bindung korrekt?
4. relevante Gegenbelege/Unknowns erhalten?
5. Human Authority erhalten?
6. Mapping, Claims und Empfehlung konsistent?
7. kritische neue Regression?

Für Repair zusätzlich:

- keine unbegründete Änderung zuvor korrekter Assignments;
- keine verlorenen Pflichtfälle;
- Änderung durch Evidence oder Finding begründet;
- neuer Verifier auf repariertes Package gebunden.

Human Review ist die finale semantische Autorität.

## 9. Stop- und Fehlerregeln

### Erwartete Negativkontrolle

Folgende Ergebnisse sind **kein Produktfehler**, sondern erwarteter Testausgang:

- Coverage-Blocker im Missing-Assignment-Fall;
- kritisches Verifier-Finding im semantisch falschen Mapping.

Gestoppt und neu gegatet wird bei:

- fehlender erwarteter Erkennung;
- falschem READY;
- Umgehung der Source-/Contract-Bindung;
- nicht nachvollziehbarer oder konvergierender Repair-Kette;
- Verlust zuvor korrekter Pflichtfälle;
- schwerwiegender Regression außerhalb des Mapping-Scope.

### Technische Providerfehler

Ein einzelner Timeout, Transportfehler oder ungültiger Provider-Response beweist keinen Schema-/Produktfehler.

Dann:

- der Run bleibt Evidence;
- erlaubte Runtime-Retries dürfen gemäß bestehendem Contract laufen;
- bleibt der Nachweis offen, wird nicht bis zum Wunschresultat wiederholt;
- ein Ersatzlauf benötigt dokumentierte Freigabe und zählt gegen das Gesamtbudget.

## 10. Abnahme Paket 3

Paket 3 ist nur bestanden, wenn **beide Kategorien** erfüllt sind.

### Positivnachweis

- AP4-02: mindestens ein fachlich korrektes, vollständiges, quellengebundenes und menschlich bestätigtes READY;
- AP4-04: mindestens ein entsprechendes READY;
- keine unbegründeten UNKNOWN-Werte in diesen positiven Nachweisen.

### Negativnachweis

- unvollständiges Mapping erreicht nicht READY;
- kontrollierter Repair ist korrekt nachgewiesen **oder** ausdrücklich nur als deterministisch getestet / real nicht beobachtet deklariert;
- strukturell vollständiges, fachlich falsches Mapping wird vom realen Verifier kritisch erkannt;
- ein fehlerhaftes Package darf erst nach korrigierter Fachlichkeit und frischer Prüfung READY erreichen.

Ein sicher abgebrochener oder FAILED Run kann einen Negativtest bestehen, aber niemals den Positivnachweis ersetzen.

## 11. Verifier-Governance

Der bestehende #110-Verifier-Kontrollvertrag bleibt bindend.

Die neue Mapping-Negativkontrolle ergänzt ihn; sie ersetzt nicht die Anforderung, Verifier-Contractänderungen gegen versionierte unabhängige Kontrollen und Human Calibration zu prüfen.

Der Verifier bewertet nicht allein seine eigene Qualität.

## 12. Historische Replay-Aussage

`tests/fixtures/issue117_structured_mapping_replays_v1.json` ist korrekt zu bezeichnen als:

> testseitiger Replay-Adapter aus autoritativer AP1-Review-Evidence.

Er ist **keine vollständige Wiederausführung historischer Model-Wire-Payloads**.

Sein Wert liegt im deterministischen Regressionstest der bekannten Mapping-Fehlerklasse.

## 13. Abschlussfolge

Nach bestandenem Paket 3:

1. Provider-/Human-Review-Evidence in #117 und PR #123 dokumentieren;
2. abschließendes Code-/Architecture-Review;
3. PR erst dann aus Draft nehmen;
4. Merge;
5. #117 mit Evidence schließen.

Bei einem echten Designfehler:

- PR bleibt Draft;
- #117 bleibt offen;
- Delta innerhalb #117 korrigieren;
- deterministische Regression erneut grün;
- nur den betroffenen Provider-Nachweis neu gaten.

## 14. Primäre Next Action

**P3.0 implementieren und vollständig grün bekommen.**

Vor dessen Abschluss werden keine realen Provider-Aufrufe gestartet.
