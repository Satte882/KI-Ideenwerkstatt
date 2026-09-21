# Accelerator Block 4: Strukturierte LLM-Extraktionsvorschau – Arbeitsplan

**Issue:** #120  
**Übergeordneter Plan:** #116  
**Abhängigkeiten:** Block 1 / #117, Block 2 / #118 und Block 3 / #119  
**Ausgangspunkt:** `main` nach Merge von PR #150  
**Zielzustand:** Ein berechtigter Nutzer kann eine unveränderlich abgeschlossene Capture Session ausdrücklich analysieren lassen und ausschließlich serverseitig validierte, quellennachweisbare Feldvorschläge prüfen. Reguläre Fachobjekte bleiben unverändert.

## Verbindliche Umsetzungsregeln

- Dieser Workplan wird vor der technischen Umsetzung über einen eigenen Pull Request nach `main` übernommen.
- Danach wird in Issue #120 eine Checkliste mit exakt den unten stehenden AP-Titeln angelegt.
- Jedes Arbeitspaket wird auf einem eigenen Branch mit eigenem Commit und eigenem Pull Request umgesetzt und erst nach erfolgreicher vollständiger Repository-CI gemergt.
- Jeder AP-Branch startet vom jeweils aktuellen `main`. Nach dem Merge wird der erledigte Remote-Branch gelöscht; vor dem nächsten AP wird geprüft, dass keine abgeschlossenen Block-4-Branches offen bleiben.
- Issue #116 wird nicht verändert.
- Block 4 erzeugt ausschließlich technische Analyseläufe und prüfbare Vorschläge. Es erzeugt oder verändert keine regulären Value-Stream-, Phasen-, Prozessanalyse-, Lösungsoptions-, Use-Case-, Governance-, Delivery- oder Lifecycle-Objekte.
- Eine Analyse wird ausschließlich durch eine ausdrückliche POST-Aktion des angemeldeten Nutzers gestartet. Es gibt keine automatische Analyse beim Speichern, Abschließen, Öffnen oder Navigieren.
- Analysiert werden ausschließlich Sessions im Zustand `completed`. Entwürfe, verworfene und abgelaufene Sessions sind nicht analysierbar.
- Eine Session wird immer gegen die bei ihr gespeicherte `catalog_version` und `schema_version` analysiert. Die aktuell aktive Katalogversion darf eine ältere Session weder still neu interpretieren noch neue Zielpfade eröffnen.
- Pro Analyse wird ein unveränderlicher Source Snapshot aus Session-ID, Revision, Katalogversion, Schemaversion und kanonischem SHA-256-Hash des Antwortdokuments gespeichert.
- Eine neue Analyse erzeugt einen neuen Lauf. Erfolgreiche frühere Vorschauen werden nicht überschrieben und bleiben bei späteren Providerfehlern verfügbar.
- Providerantworten werden vollständig und atomar geprüft. Ein unbekannter Zielpfad, eine unzulässige Quellfrage, ein ungültiger Typ oder ein nicht belegbarer Quellausschnitt verwirft den gesamten Vorschlagssatz dieses Laufs. Es entstehen keine teilweise vertrauenswürdig wirkenden Vorschläge.
- Die bestehenden `ACCELERATOR_LLM_*`-Grenzen aus Block 1 werden wiederverwendet. Persistente Zählung für Session-, Nutzer- und globale Tagesgrenzen wird in Block 4 klein und konkurenzsicher ergänzt.
- Es gibt genau einen konfigurierten Providerpfad über OpenRouter. Keine Provider-Orchestrierung, automatische Modellwahl, Streaming-, Cache-, Prompt-Editor-, Vektor- oder Billing-Plattform.
- Vollständige Prompts, vollständige Providerantworten und Capture-Rohtexte werden nicht in Standardlogs, Sentry oder separaten Telemetriedatensätzen gespeichert.
- Provider, tatsächlich verwendetes Modell, Promptversion, Ausgabeschemaversion, Zeitpunkt, Laufzeit, Fehlercode sowie verfügbare Token- und Kostenmetadaten werden technisch nachvollziehbar gespeichert.
- Die Vorschau bietet keine Übernahme-, Bearbeiten-und-Übernehmen-, Verwerfen- oder Sammelaktion. Diese Funktionen gehören zu Block 5.

## Architekturentscheidungen

### 1. Analyse gegen die eingefrorene Session-Version

`CaptureSession.catalog_version` und `CaptureSession.schema_version` sind für jeden Lauf verbindlich. Der Orchestrierungsservice lädt ausdrücklich den gespeicherten Katalog über `get_capture_catalog(session.capture_type, session.catalog_version)` und validiert das gespeicherte Antwortdokument erneut gegen genau diesen Vertrag. Eine nicht mehr unterstützte Katalogversion bleibt schreibgeschützt und wird auch für neue Analysen kontrolliert abgelehnt; vorhandene erfolgreiche Analysen bleiben lesbar.

Damit wird verhindert, dass alte Antworten nach einer späteren Katalogänderung mit neuen Fragen, Zielpfaden oder Bedeutungen interpretiert werden.

### 2. Getrennte technische Analyseläufe und Feldvorschläge

Block 4 ergänzt zwei zweckgebundene Modelle:

- `CaptureAnalysis`: unveränderlicher technischer Lauf mit Source Snapshot, Status, Provider-/Modell-/Versionsmetadaten, Limits, Laufzeit, Fehlercode, Findings sowie Token-/Kostenmetadaten.
- `CaptureFieldSuggestion`: serverseitig validierter Einzelvorschlag mit Zielobjekttyp, Zielfeld, optionaler Zielobjekt-ID, optionalem lokalem Gruppenschlüssel, Feldtyp, normalisiertem Wert, Quellfrage, Quellausschnitt, Unsicherheitsstufe und Unsicherheitsbegründung.

Die optionale Zielobjekt-ID wird bereits in Version 1 als nullable UUID-Feld festgelegt. Sämtliche aktuell relevanten Architektur- und Use-Case-Zielobjekte verwenden UUID-Primärschlüssel. Block 4 befüllt das Feld noch nicht automatisch. Dadurch kann Block 5 vorhandene Zielobjekte konfliktgeschützt binden, ohne das Produktionsschema später nachziehen zu müssen.

Für wiederholbare Entwurfsgruppen wie Phasen und Lösungsoptionen wird zusätzlich ein stabiler lokaler Gruppenschlüssel gespeichert. Er muss aus einem tatsächlich in der Quellantwort benannten Element abgeleitet und serverseitig gegen die Quelle plausibilisiert werden. Er ist keine Fachobjekt-ID und löst keine Objektanlage aus.

### 3. Expliziter Extraktionsvertrag statt vollständigem Blueprint

Die Providerantwort bildet keinen vollständigen Scenario Blueprint. Sie enthält nur Vorschläge und Findings. Version 1 definiert explizit:

- erlaubte Zielobjekttypen,
- erlaubte Zielpfade aus dem zur Session gehörenden Capture-Katalog,
- Feldtypen,
- Unsicherheitsstufen `low`, `medium`, `high`,
- Quellfrage und wörtlichen Quellausschnitt,
- offene Fragen,
- Widersprüche,
- Prompt- und Schemaversion.

Die Blueprint-Whitelists und Enums aus Block 2 werden wiederverwendet, aber nicht als Providervertrauen behandelt. Die finale Zulässigkeit entsteht aus der Schnittmenge von eingefrorenem Capture-Katalog, Blueprint-Vertrag und Block-1-Ampelgrenze.

### 4. Kleine gemeinsame OpenRouter-Transportfunktion

Der bestehende Use-Case-Copilot bleibt fachlich unverändert. Nur der technische HTTP-Transport, URL-/API-Key-Prüfung, Timeout, begrenztes Einlesen der Antwort, Providerfehlerklassen und Nutzungsmetadaten werden in eine kleine Funktion unter `ki_radar/core/` verschoben und von Copilot sowie Accelerator verwendet.

Promptaufbau, Antwortschema, Extraktionsvalidierung, Persistenz und UI bleiben im Modul `ki_radar.accelerator`. Es entsteht kein generisches AI Gateway.

### 5. Vollständige atomare Ergebnisprüfung

Der Ablauf lautet:

1. Session, Status, Ownership und Berechtigung prüfen.
2. Eingefrorenen Katalog und Antwortschema laden.
3. Antwortdokument erneut validieren und kanonisch hashen.
4. Session-, Nutzer- und globale Tagesgrenze konkurenzsicher reservieren.
5. Nur nichtleere, für den gespeicherten Katalog bekannte Antworten übertragen.
6. Provider genau einmal aufrufen; keine automatische Retry-Schleife.
7. Providerantwort als JSON einlesen und vollständig gegen Extraktionsvertrag prüfen.
8. Zielpfad gegen die konkrete Quellfrage des eingefrorenen Katalogs prüfen.
9. Quellausschnitt gegen den tatsächlichen Antworttext prüfen.
10. Typen, Enums, Datumswerte, UUIDs, Referenzen, deutsche Zahlen und Einheiten deterministisch prüfen.
11. Degenerierte Inhalte und erfundene Gruppen ablehnen.
12. Analyse und vollständigen validierten Vorschlagssatz in einer Transaktion speichern.

Ein fehlgeschlagener Lauf speichert nur technische Laufmetadaten und einen kontrollierten Fehlercode. Er verändert weder Capture-Antworten noch frühere Vorschläge oder Fachobjekte.

### 6. Degenerierte und erfundene Inhalte

Strukturelle Gültigkeit reicht nicht. Ein Vorschlag wird zusätzlich abgelehnt, wenn sein normalisierter Inhalt im Wesentlichen nur:

- die sichtbare Frage,
- den Hilfetext,
- den Zielfeldnamen,
- eine generische Leerformel ohne Information aus der Antwort

wiederholt.

Für Phasen und Lösungsoptionen muss der Provider pro Gruppe mindestens einen belegbaren Quellausschnitt liefern, der den Gruppennamen oder eine eindeutige Beschreibung enthält. Zusätzliche Gruppen, die in keiner zugeordneten Antwort vorkommen, führen zur atomaren Ablehnung des Laufs.

Diese Prüfung ist bewusst konservativ. Sie soll offensichtliche wertlose oder erfundene Ergebnisse erkennen, nicht semantische Qualität allgemein bewerten.

### 7. Retention während der Block-4-/Block-5-Übergangsphase

Die in Block 3 noch unbegrenzt aufbewahrten abgeschlossenen Rohantworten erhalten eine konfigurierbare Retention:

- `ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS`, Standard 90 Tage, zulässiger Bereich 30 bis 365 Tage,
- sieben Tage Karenz nach Ablauf vor physischer Löschung,
- erfolgreiche und fehlgeschlagene Analysen sowie Vorschläge werden gemeinsam mit ihrer Capture Session gelöscht,
- jede ausdrücklich gestartete Analyse setzt das Ablaufdatum der abgeschlossenen Session erneut auf das konfigurierte Fenster,
- keine getrennte Rohdatenarchivierung.

90 Tage sind für die Übergangsphase zu Block 5 ausreichend konservativ, ohne unbegrenzte Speicherung zum Zielzustand zu erklären. Der Wert bleibt betrieblich konfigurierbar, falls der Rollout-Abstand größer ist. Nach Produktivsetzung von Block 5 wird die Angemessenheit erneut geprüft; eine automatische Verlängerung über 365 Tage ist ausgeschlossen.

### 8. Serverseitige Vorschau im modularen Django-Monolithen

Die bestehende Capture-Review-Seite erhält bei abgeschlossenen Sessions die Primäraktion `Antworten analysieren`. Der POST leitet nach Abschluss auf eine getrennte Vorschauseite weiter.

Die Vorschauseite zeigt:

- Laufstatus, Zeitpunkt, Provider, Modell und Versionen,
- Anzahl gültiger Vorschläge, offene Fragen, Widersprüche und Validierungsfehler,
- Vorschläge gruppiert nach Zielobjekt und lokalem Gruppenschlüssel,
- Zielfeld, Feldtyp, normalisierten Wert, Quellfrage und Quellausschnitt,
- Unsicherheit als Kategorie mit Begründung,
- echte Links zu früheren Läufen.

Die Seite verwendet serverseitige Templates, bestehende semantische Designtokens, sichtbaren Tastaturfokus und bleibt ohne JavaScript navigierbar. Doppelklickschutz darf progressive Ergänzung sein, die serverseitige Idempotenz- und Quotenprüfung bleibt maßgeblich.

## AP 1: Gap-Analyse und verbindliche Wiederverwendungsgrenzen dokumentieren

- Aktuellen `main` einschließlich Merge von PR #150 prüfen.
- Issue #116, #120, Block-1-Foundation, Block-2-Vertrag, Block-3-Capture-Vertrag, Retention, Completion, Roadmap, ADRs, `AGENTS.md` und `DESIGN.md` abgleichen.
- Vorhandenen OpenRouter-Copilot, LLM-Policy, Capture-Modelle, Services, Kataloge, Views, Templates, Formularvalidierungen, Blueprint-Vertrag und Regressionstests mit konkreten Dateipfaden dokumentieren.
- Bestätigen, welche Planannahmen im Code nicht gelten oder angepasst werden müssen.
- Eingefrorene Katalogversion, Zielobjekt-ID, Gruppenschlüssel, Quoten, Datenschutz und Retention als verbindliche Block-4-Grenzen festhalten.
- Abnahmekriterien aus #120 vollständig den APs zuordnen.

**Ergebnis:** `docs/accelerator/BLOCK_4_GAP_ANALYSIS.md`.

## AP 2: Versionierten Extraktionsvertrag und Whitelists festlegen

- Extraktionsschema Version 1 als kleiner codebasierter Vertrag definieren.
- Erlaubte Zielobjekte, Zielpfade, Feldtypen, Unsicherheitsstufen und Finding-Typen festlegen.
- Zielpfade immer aus dem eingefrorenen Katalog der Session ableiten und gegen den Blueprint-Vertrag begrenzen.
- Scope-In und Scope-Out als getrennte Quellen-/Zielkombinationen erzwingen.
- Rot- und Systemfelder grundsätzlich ausschließen.
- Quellfrage, Quellausschnitt, Promptversion und Schemaversion verpflichtend machen.
- Normalisierte interne Dataclasses beziehungsweise unveränderliche Vertragsobjekte bereitstellen.

**Ergebnis:** Testbarer Extraktionsvertrag ohne Datenbankänderung und ohne Provideraufruf.

## AP 3: Analyse-, Vorschlags- und Quotenmodelle einführen

- `CaptureAnalysis` mit unveränderlichem Source Snapshot, Status, Provider-/Modell-/Versionsmetadaten, Zeitpunkten, Fehlercode, Laufzeit sowie Token-/Kostenmetadaten implementieren.
- `CaptureFieldSuggestion` mit Zielobjekttyp, Zielfeld, nullable UUID-Zielobjekt-ID, lokalem Gruppenschlüssel, Feldtyp, normalisiertem Wert, Quellfrage, Quellausschnitt und Unsicherheit implementieren.
- Kleine persistente Quotenstruktur für Session-, Nutzer- und globalen Kalendertag einführen; konkurenzsichere Reservierung ermöglichen.
- Geeignete Constraints und Indizes ergänzen.
- Keine vollständigen Prompts, Providerantworten oder Capture-Antwortkopien speichern.

**Ergebnis:** Kleine auditierbare Vorschlags- und Aufrufschicht mit bewusst festgelegter Block-5-Anschlussstruktur.

## AP 4: Gemeinsamen begrenzten OpenRouter-Transport bereitstellen

- Technischen Transport aus `use_cases/copilot.py` in eine kleine Core-Funktion extrahieren.
- Bestehende API-Key-, HTTPS-, Timeout- und Providerfehlerbehandlung erhalten.
- Antwortgröße beim Einlesen hart begrenzen; ungültige Kodierung und JSON kontrolliert behandeln.
- Token- und Kostenmetadaten soweit verfügbar zurückgeben.
- Fachlichen Copilotprompt und dessen bestehendes Verhalten unverändert halten.
- Keine Providerabstraktion über den konkret konfigurierten OpenRouterpfad hinaus bauen.

**Ergebnis:** Ein wiederverwendeter technischer Providerpfad ohne zweiten HTTP-Stack und ohne Copilot-Regression.

## AP 5: Kontrollierte Analyse-Orchestrierung implementieren

- Ausdrücklichen Service für eine abgeschlossene, eigene und berechtigte Capture Session bereitstellen.
- Gespeicherte Katalog- und Schemaversion laden; nie automatisch auf die aktive Version wechseln.
- Antwortdokument erneut validieren, kanonisch hashen und als Source Snapshot referenzieren.
- Nur bekannte, nichtleere Antworten des konkreten Katalogs in minimierter Form übertragen.
- Session-, Nutzer- und globale Tagesgrenze atomar reservieren.
- Parallele Doppelstarts für denselben Source Snapshot kontrolliert verhindern.
- Prompt Version 1 mit klarer Extraktions-, Nicht-Erfindungs- und JSON-Grenze einführen.
- Fehlende Konfiguration, Rate Limit, Timeout und Providerfehler als kontrollierte Laufstatus behandeln.

**Ergebnis:** Genau einmal ausdrücklich gestarteter, quota-geschützter Analysepfad ohne Fachobjektänderung.

## AP 6: Deterministische Ergebnisvalidierung und Normalisierung implementieren

- Provider-JSON vollständig gegen Extraktionsschema prüfen.
- Zielpfad gegen die konkrete Quellfrage des eingefrorenen Katalogs prüfen.
- Quellausschnitt normalisiert, aber inhaltstreu gegen den Antworttext verifizieren.
- Text, Listen, Enums, Ganzzahlen, Datumswerte, UUIDs/Referenzen, deutsche Dezimalzahlen, Tausendertrennzeichen, Prozentwerte und Einheiten deterministisch prüfen.
- Unsicherheit und Begründung validieren.
- Scope-In-/Scope-Out-Verwechslungen ablehnen.
- Degenerierte Vorschläge erkennen, die nur Frage, Hilfetext, Zielfeld oder Leerformeln wiederholen.
- Lokale Gruppen nur akzeptieren, wenn sie in der zugeordneten Antwort belegbar sind; erfundene Phasen oder Lösungsoptionen atomar ablehnen.
- Erst nach vollständigem Erfolg Analyse und Vorschläge gemeinsam speichern.

**Ergebnis:** Keine unbekannten, typwidrigen, unbelegten oder offensichtlich wertlosen Providerinhalte in der Vorschau.

## AP 7: Serverseitige Analyse- und Vorschauoberfläche integrieren

- Auf der Capture-Review-Seite die Aktion `Antworten analysieren` ausschließlich für abgeschlossene, analysierbare Sessions anzeigen.
- POST-View mit CSRF-, Ownership-, Rollen-, Status-, Quoten- und Doppelstartprüfung implementieren.
- Getrennte Vorschauseite mit Laufmetadaten, Vorschlägen, Quellen, Unsicherheit, offenen Fragen, Widersprüchen und Fehlerzuständen bereitstellen.
- Frühere Läufe als echte Links erreichbar machen.
- Bei neuem Fehler den letzten erfolgreichen Lauf nicht überschreiben oder verstecken.
- Keine Übernahme- oder Verwerfaktion für einzelne Vorschläge anbieten.
- UI nach `DESIGN.md` responsiv, tastaturbedienbar und ohne JavaScript-Zwang umsetzen.

**Ergebnis:** Prüffähiger Block-4-Zwischenstand für Value-Stream- und Use-Case-Captures.

## AP 8: Logging, Datenschutz und Retention abschließen

- Standardlogs auf technische Metadaten ohne Prompt, Antworttext, Quellausschnitt oder vollständige Providerantwort begrenzen.
- Fehler- und Sentry-Pfade mit `sensitive_post_parameters` und kontrollierten Exceptions absichern.
- `ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS` mit Standard 90 und zulässigem Bereich 30 bis 365 Tagen einführen.
- Analyseversuch verlängert die Retention der abgeschlossenen Session auf das konfigurierte Fenster.
- Abgeschlossene Sessions nach Ablauf in `expired` überführen und nach sieben Tagen zusammen mit Analysen/Vorschlägen physisch löschen.
- Management Command und bestehende Retentionlogik klein erweitern; keine allgemeine Archivierungsplattform bauen.

**Ergebnis:** Getestete, konfigurierbare und Block-5-taugliche Rohdatenhaltung ohne unbegrenzte Speicherung.

## AP 9: Real-DEMO-Golden-Dataset und Negativtests absichern

Mindestens testen:

- deterministische Extraktionsantworten für Value Stream und Use Case auf Basis `[Real-DEMO]`,
- eingefrorene ältere Katalogversion trotz abweichender aktueller Version,
- unbekannte oder nicht mehr unterstützte Katalog-/Schemaversion,
- unbekannte Zielobjekte, Zielpfade und rote/Systemfelder,
- falsche Quellfrage und nicht im Antworttext vorhandener Quellausschnitt,
- Scope-In-/Scope-Out-Verwechslung,
- ungültige Enums, Zahlen, Einheiten, Datumswerte, UUIDs und Referenzen,
- degenerierte Antwort, die Frage oder Hilfetext als Vorschlag wiederholt,
- zusätzliche erfundene Phase oder Lösungsoption ohne Quellbeleg,
- Prompt-Injection in Capture-Antworten,
- teilweise gültige Providerantwort mit einem ungültigen Element führt zu vollständiger Ablehnung,
- fehlender API-Key, 401/403, 429, Timeout, 5xx, Netzwerkfehler, leere und übergroße Antwort,
- Session-, Nutzer- und globale Quoten einschließlich paralleler Reservierung,
- keine Änderung regulärer Fachobjekte, Gates, Reviews oder Lifecycle-Zustände,
- keine Rohtexte und Prompts in Standardlogs.

**Ergebnis:** Reproduzierbarer Golden-Path-Nachweis und explizite Abdeckung strukturell gültiger, aber fachlich wertloser oder erfundener Ergebnisse.

## AP 10: Vollständige Regression, UI-Abnahme und Abschlussnachweis erstellen

- Vollständige bestehende Repository-Test-Suite ausführen.
- Repo-weites Ruff-Linting und `ruff format --check .`, Django-Systemcheck, Migrationsprüfung, Bandit, Dependency Audit, drei Compose-Validierungen sowie Produktions- und Entwicklungsimage-Build unverändert grün nachweisen.
- Desktop- und Mobile-Abnahme der Capture-Review-, Analyse- und Vorschauseiten reproduzierbar durchführen.
- Erfolgs-, Fehler-, leere-, lange- und gruppierte Vorschau visuell prüfen.
- Sicherstellen, dass bestehender Review-Copilot, Block-3-Capture, direkter Intake und Blueprint-Pfad unverändert funktionieren.
- `docs/accelerator/BLOCK_4_COMPLETION.md` mit Abnahmematrix, CI-Lauf, Migrationen, Testumfang, Retentionregel und bestätigten Nicht-Zielen erstellen.
- Issue #120 erst schließen, wenn alle zehn APs gemergt und sämtliche Abnahmekriterien erfüllt sind.

**Ergebnis:** Vollständig nachgewiesener Abschluss von Block 4 ohne Änderung von Issue #116.

## Zuordnung zu den Abnahmekriterien aus Issue #120

| Abnahmekriterium | Arbeitspakete |
| --- | --- |
| Gap-Analyse dokumentiert | AP 1 |
| Analyse nur nach ausdrücklicher Benutzeraktion | AP 5, AP 7, AP 9 |
| Ausgabe gegen versioniertes Schema validiert | AP 2, AP 6, AP 9 |
| Unbekannte Felder und ungültige Typen abgewiesen | AP 2, AP 6, AP 9 |
| Quelle, Unsicherheit und offene Fragen sichtbar | AP 2, AP 3, AP 7, AP 9 |
| Rate Limit, Timeout und Provider-Ausfall ohne Datenverlust | AP 3 bis AP 5, AP 7, AP 9 |
| Reguläre Fachobjekte bleiben unverändert | AP 3, AP 5 bis AP 7, AP 9, AP 10 |
| Keine Rohtexte oder Prompts in Standardlogs | AP 4, AP 5, AP 8, AP 9 |
| Schlanke Lösung mit einem Providerpfad | AP 2 bis AP 5, AP 10 |

## Explizite Nicht-Ziele

- keine Feldübernahme oder Fachobjektanlage,
- keine Sammelaktion,
- keine automatische Generierung neuer fachlicher Inhalte,
- keine automatische Fokusentscheidung, Prozessvalidierung, Lösungswahl, Governance-Prüfung, Freigabe oder Lifecycle-Änderung,
- keine native Sprach-, Audio-, Datei- oder Connector-Verarbeitung,
- keine asynchrone Job-, Queue- oder Streaming-Infrastruktur,
- keine allgemeine AI-Gateway-, Prompt-Management-, Cache-, Vektor-, Quota-, Billing-, FinOps- oder Observability-Plattform,
- keine Änderung bereits übergebener Delivery Packages,
- keine Änderung des autoritativen Gesamtplans #116.
