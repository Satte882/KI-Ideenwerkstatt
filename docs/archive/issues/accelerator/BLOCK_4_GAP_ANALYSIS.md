# Accelerator Block 4: Gap-Analyse und Wiederverwendungsgrenzen

**Issue:** #120  
**Übergeordneter Plan:** #116  
**Arbeitsplan:** `docs/accelerator/BLOCK_4_WORKPLAN.md`  
**Repository-Stand:** `2481b7883d60ddca6dd8f0aea33e5ca635cce26c`  
**Zweck:** Verbindliche Gap-Analyse vor der technischen Umsetzung der strukturierten LLM-Extraktionsvorschau

## 1. Ergebnis in einem Satz

Der aktuelle `main` besitzt bereits die erforderlichen Capture-, Blueprint-, Formular-, Berechtigungs- und LLM-Betriebsgrenzen, aber noch keine persistente Analyse-, Vorschlags- oder Quotenstruktur und keinen strikt validierten strukturierten Providerpfad. Block 4 ergänzt deshalb die bestehende `accelerator`-App um genau diese technischen Schichten, ohne den Review-Copilot zur Extraktionspipeline umzubauen und ohne reguläre Fachobjekte zu verändern.

## 2. Autoritative Quellen und Reihenfolge

Für Block 4 gelten:

1. Issue #116 als unveränderter Accelerator-Gesamtplan,
2. Issue #120 als eigenständiger Arbeitsauftrag,
3. `docs/accelerator/BLOCK_1_FOUNDATION.md`,
4. Blueprint-Vertrag und Block-2-Dokumente,
5. Block-3-Capture-Vertrag, Retention und Abschlussnachweis,
6. `docs/accelerator/BLOCK_4_WORKPLAN.md`,
7. `AGENTS.md`, relevante ADRs und `DESIGN.md`.

Die ältere Produkt-Roadmap begründet keinen parallelen Block-4-Scope. Issue #116 dokumentiert die ausdrückliche Accelerator-Reihenfolge. Issue #116 wird weder editiert noch geschlossen.

## 3. Aktueller Ausgangsstand

### 3.1 Abhängigkeiten

- Block 1 / #117 ist abgeschlossen und definiert Feldampel, Datenfluss, Logging, Retention und gemeinsame LLM-Grenzen.
- Block 2 / #118 ist abgeschlossen und liefert versionierten Blueprint-Vertrag, erlaubte Felder, Enums, Referenzvalidierung und `[Real-DEMO]`.
- Block 3 / #119 ist abgeschlossen und liefert persistente, eigentümergebundene und wiederaufnehmbare Capture Sessions für `value_stream` und `use_case`.
- PR #150 ist vor Beginn von Block 4 gemergt. Die nachträgliche Desktop-/Mobile-Nachprüfung und Completion-Korrektur sind damit Bestandteil des Ausgangsstands.
- Der verbindliche Block-4-Arbeitsplan ist über PR #151 auf `main` enthalten.

### 3.2 Modularer Django-Monolith

ADR 0001 legt Django 5.2, serverseitige Templates und PostgreSQL als einzelnes deploybares System fest.

**Folgerung:**

- keine separate API- oder Frontend-Anwendung,
- keine Queue- oder Worker-Infrastruktur für Version 1,
- neue Modelle, Services, Views und Templates bleiben in der vorhandenen Django-Struktur,
- der technische Providertransport bleibt eine kleine interne Funktion.

## 4. Bestehende wiederzuverwendende Bausteine

### 4.1 Gemeinsame LLM-Policy

Relevante Dateien:

- `ki_radar/core/llm_policy.py`
- `config/settings/base.py`
- `.env.example`
- `tests/test_accelerator_llm.py`

Vorhanden sind validierte Grenzen für:

- Request-Timeout,
- maximale Eingabezeichen,
- maximale Ausgabetokens,
- maximale Aufrufe pro Kontext,
- maximale Aufrufe pro Benutzer und Tag,
- maximale globale Aufrufe pro Tag.

Die Policy prüft außerdem, dass Kontextgrenze, Nutzergrenze und globale Grenze konsistent geordnet sind.

**Wiederverwendung:**

- Timeout-, Eingabe-, Ausgabe- und Requestgrenzen werden unverändert über `get_accelerator_llm_policy()` geladen.
- Block 4 ergänzt nur die bislang ausdrücklich aufgeschobene persistente Zählung im konkreten Session-/Analysekontext.
- Es entsteht kein zweites Settings-Präfix und keine parallele Quotenlogik.

### 4.2 Bestehender OpenRouter-Copilot

Relevante Dateien:

- `ki_radar/use_cases/copilot.py`
- bestehende Copilot-View und Templates,
- `static/js/copilot-submit-guard.js`.

Vorhanden sind:

- ausdrücklicher Nutzeraufruf,
- API-Key-Prüfung,
- validierte HTTPS-URL,
- konfigurierbarer Timeout,
- Eingabegrößenprüfung,
- begrenzte Ausgabetokens,
- Fehlerklassen für fehlende Konfiguration, Autorisierung, Rate Limit, Providerfehler und Timeout,
- technische Logs mit Laufzeit, Zeichenanzahl, Token- und Kostenmetadaten,
- Doppelklickschutz als progressive UI-Ergänzung.

Nicht vorhanden beziehungsweise nicht wiederzuverwenden sind:

- strukturierter JSON-Vertrag,
- serverseitige Feldwhitelist,
- Quellfragen- und Quellausschnittprüfung,
- persistente Analyseläufe,
- Quotenreservierung,
- Vorschlagspersistenz.

**Entscheidung:**

Nur der technische HTTP-Transport und die vorhandene Fehlerklassifikation werden klein nach `ki_radar/core/` verschoben. Der fachliche Copilotprompt, seine unstrukturierte Textantwort und sein Use-Case-Reviewzweck bleiben unverändert. Der Accelerator erhält eigenen Prompt, Vertrag, Validierung, Persistenz und UI.

### 4.3 CaptureSession

Relevante Dateien:

- `ki_radar/accelerator/models.py`
- `ki_radar/accelerator/services.py`
- `ki_radar/accelerator/catalogs.py`
- `ki_radar/accelerator/forms.py`
- `ki_radar/accelerator/views.py`
- `ki_radar/accelerator/retention.py`
- `templates/accelerator/capture_*.html`.

`CaptureSession` speichert bereits:

- UUID,
- Besitzer,
- Capture-Art,
- Arbeitsbezeichnung,
- eingefrorene Katalog- und Schemaversion,
- validiertes Antwortdokument,
- Status,
- Revision,
- Fortschritt,
- aktive Eingabezeit,
- Retention- und Terminalzeitpunkte.

Der Service stellt sicher:

- serverseitige Rollenprüfung,
- strikte Ownership,
- Revisionskonfliktschutz,
- atomare Speicherung,
- vollständige Pflichtantworten beim Abschluss,
- unveränderliche Terminalzustände.

**Entscheidung:**

- Nur Sessions im Zustand `completed` sind analysierbar.
- Der Analyseservice lädt immer `get_capture_catalog(session.capture_type, session.catalog_version)`.
- Die aktive Katalogversion wird nicht als Ersatz verwendet.
- Das gespeicherte Antwortdokument wird vor jedem Aufruf erneut gegen den eingefrorenen Vertrag validiert.
- Session-ID, Revision, Katalogversion, Schemaversion und kanonischer Antwort-Hash bilden den Source Snapshot.

### 4.4 Versionierte Capture-Kataloge

`ki_radar/accelerator/catalogs.py` definiert pro Frage:

- stabile Frage-ID,
- sichtbare Bezeichnung,
- Hilfetext,
- Pflichtstatus,
- Eingabetyp,
- maximale Länge,
- narrative Informationsdomäne,
- mögliche Blueprint-Zielpfade.

Die Zielpfade werden bereits gegen `contract.v1.json` geprüft.

**Entscheidung:**

Die konkrete Quellfrage begrenzt serverseitig, welche Zielpfade ein Vorschlag adressieren darf. Das LLM darf keine freie Quelle-Ziel-Zuordnung festlegen. Für eine Session ist ausschließlich die in ihrem eingefrorenen Katalog gespeicherte Zielpfadmenge maßgeblich.

### 4.5 Blueprint-Vertrag und Forms

Relevante Dateien:

- `ki_radar/core/scenario_blueprints/contract.v1.json`
- `ki_radar/core/scenario_blueprint_validation.py`
- `ki_radar/architecture/forms.py`
- `ki_radar/use_cases/forms.py`.

Vorhanden sind:

- erlaubte Objekte und Felder,
- verbotene Entscheidungs- und Lifecycle-Objekte,
- zulässige Entwurfszustände,
- Enumlisten,
- Kardinalitäten,
- deutsche Dezimal- und Metrikvalidierung über bestehende Forms,
- Referenz- und UUID-Prüfung,
- `[Real-DEMO]` als Referenzdatensatz.

**Entscheidung:**

Block 4 verwendet eine explizite Extraktionswhitelist, die aus drei Grenzen entsteht:

1. Zielpfade der konkreten Quellfrage aus dem eingefrorenen Capture-Katalog,
2. erlaubte Felder und Enums aus dem Blueprint-Vertrag,
3. Ampelklassifikation aus Block 1.

Forms werden für passende skalare Domainwerte wiederverwendet oder ihre vorhandenen Hilfsfunktionen klein extrahiert. Die Formlogik wird nicht vollständig in einer zweiten Validatorimplementierung kopiert.

### 4.6 Logging und Datenschutz

Vorhanden sind:

- technische Standardlogs,
- Sentry mit `send_default_pii=False` und ohne Requestbody,
- `sensitive_post_parameters` an Capture-Views,
- Tests, die Rohantworten aus Fehlerberichten und Logs fernhalten.

**Entscheidung:**

Zulässige technische Metadaten:

- Zweck,
- Provider,
- Modell,
- Objektart und technische ID,
- Laufstatus und Fehlercode,
- Laufzeit,
- Eingabe-/Ausgabeumfang,
- Token- und Kostenmetadaten.

Nicht zulässig in Standardlogs und Sentry:

- vollständige Capture-Antworten,
- Prompts,
- Quellausschnitte,
- vollständige Providerantworten,
- API-Key oder Authorization-Header.

## 5. Nicht bestätigte oder korrigierte Planannahmen

### 5.1 Keine neue allgemeine Provider-Schnittstelle erforderlich

Es fehlt kein vollständiger Provider-Stack. Der bestehende OpenRouterpfad ist technisch geeignet, aber fachlich eng mit dem Copilot verbunden.

**Korrektur:** Ein kleiner gemeinsamer Transport reicht. Keine abstrakte Providerregistry, automatische Modellwahl oder austauschbare Gatewayarchitektur.

### 5.2 Die Blueprint-Validierung ist nicht direkt die Extraktionsvalidierung

Der vollständige Blueprint-Vertrag verlangt komplette Objektgraphen, Pflichtreferenzen und Zustände. Eine Extraktionsvorschau enthält dagegen einzelne Vorschläge und Findings.

**Korrektur:** Block 4 definiert einen eigenen kleinen Ausgabevertrag und verwendet Blueprint-Feldlisten sowie Enums nur als Whitelist- und Typquelle.

### 5.3 Persistente Quoten fehlen tatsächlich

Block 1 hat die Grenzen bewusst nur als Konfigurationsvertrag vorbereitet, weil Session- und Analyseobjekte noch nicht existierten.

**Korrektur:** Block 4 führt eine kleine persistente Tageszählung ein. Kein Billing- oder allgemeines Quotasystem.

### 5.4 Retention abgeschlossener Sessions ist noch offen

Block 3 erhält abgeschlossene Sessions unbegrenzt als Übergangszustand für Block 4.

**Korrektur:** Block 4 führt `ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS` mit Standard 90 und zulässigem Bereich 30 bis 365 Tagen ein. Jeder ausdrückliche Analyseversuch setzt das Ablaufdatum erneut auf dieses Fenster. Nach Ablauf folgt sieben Tage Karenz und anschließend physische Löschung zusammen mit Analysen und Vorschlägen.

### 5.5 Block-5-Anschluss muss jetzt im Schema berücksichtigt werden

`CaptureSession` besitzt keine Referenz auf ein reguläres Zielobjekt. Block 5 benötigt für vorhandene Zielobjekte Konfliktschutz, darf aber noch keine allgemeine Objektanlage vorziehen.

**Korrektur:** `CaptureFieldSuggestion` erhält bereits in Block 4:

- `target_object_type`,
- `target_field`,
- nullable `target_object_id` als UUID,
- optionalen `target_group_key`.

Das Feld bleibt zunächst leer, ermöglicht Block 5 aber eine spätere explizite Bindung ohne nachträgliche Schemaänderung auf bereits befüllten Produktionsdaten.

## 6. Verbindliches Datenmodell

### 6.1 CaptureAnalysis

Erforderliche Kategorien:

- UUID,
- Capture Session,
- anfordernder Benutzer,
- Status,
- Source Revision und Source Hash,
- Capture-, Katalog- und Antwortschemaversion,
- Provider, Modell, Promptversion und Extraktionsschemaversion,
- Start- und Abschlusszeitpunkt,
- Laufzeit,
- Fehlercode,
- Eingabe- und Ausgabeumfang,
- Token- und Kostenmetadaten,
- offene Fragen und Widersprüche als validierte kleine JSON-Strukturen.

Nicht gespeichert werden:

- vollständiger Prompt,
- vollständige Providerantwort,
- Kopie des gesamten Capture-Antwortdokuments.

### 6.2 CaptureFieldSuggestion

Erforderliche Kategorien:

- UUID,
- Analyse,
- Zielobjekttyp,
- Zielfeld,
- nullable UUID-Zielobjekt-ID,
- optionaler lokaler Gruppenschlüssel,
- Feldtyp,
- normalisierter Wert als JSON-kompatibler Wert,
- Quellfrage,
- wörtlicher Quellausschnitt,
- Unsicherheitsstufe und Begründung,
- Erstellungszeitpunkt.

Vorschläge sind in Block 4 unveränderlich und besitzen noch keinen Übernahme- oder Verwerfstatus. Diese Status entstehen erst mit den Aktionen aus Block 5.

### 6.3 Persistente Tagesquota

Eine kleine Tabelle aggregiert je Kalendertag und Scope:

- Kontext beziehungsweise Capture Session,
- Benutzer,
- global.

Reservierungen erfolgen unter Datenbanksperre und werden vor dem Provideraufruf gezählt. Providerfehler geben die verbrauchte Anfrage nicht automatisch frei, weil der externe Request bereits Kosten oder Rate-Limit verbraucht haben kann. Validierungsfehler vor dem tatsächlichen Provideraufruf verbrauchen keine Quote.

## 7. Extraktions- und Validierungsgrenze

### 7.1 Eingabe

Übertragen werden nur:

- Capture-Art,
- Katalog- und Schemaversion,
- Frage-ID,
- Fragebezeichnung,
- nichtleere Antwort,
- für diese Frage zulässige Zielpfade.

Nicht übertragen werden:

- Benutzername,
- E-Mail-Adresse,
- technische Sessionmetadaten ohne fachlichen Bedarf,
- andere Capture Sessions,
- reguläre Fachobjekte,
- vollständiger Blueprint-Vertrag.

### 7.2 Ausgabe

Jeder Einzelvorschlag benötigt:

- Zielobjekttyp,
- Zielfeld,
- optionalen Gruppenschlüssel,
- Feldtyp,
- vorgeschlagenen Wert,
- Quellfrage,
- wörtlichen Quellausschnitt,
- Unsicherheitsstufe,
- Unsicherheitsbegründung.

Der Gesamtoutput benötigt zusätzlich:

- Promptversion,
- Schemaversion,
- offene Fragen,
- Widersprüche.

### 7.3 Atomare Ablehnung

Der gesamte Lauf wird als ungültig behandelt, sobald mindestens ein Element:

- einen unbekannten Zielpfad adressiert,
- nicht zur angegebenen Quellfrage gehört,
- ein rotes oder systemverwaltetes Feld adressiert,
- einen ungültigen Typ oder Enumwert enthält,
- einen nicht im Antworttext belegbaren Quellausschnitt nennt,
- Scope-In und Scope-Out vertauscht,
- eine unbelegte Gruppe erfindet,
- nur Frage, Hilfetext, Zielfeldname oder eine Leerformel wiederholt.

Es werden keine teilweise gültigen Vorschläge gespeichert.

### 7.4 Gruppenprüfung

Für Phasen und Lösungsoptionen gilt:

- jeder Gruppenschlüssel muss innerhalb eines Laufs stabil und eindeutig sein,
- der Gruppenschlüssel darf keine Fachobjekt-ID vortäuschen,
- mindestens ein Quellausschnitt muss Name oder eindeutige Beschreibung der Gruppe belegen,
- eine zusätzliche, nicht in den Antworten vorkommende Gruppe führt zur atomaren Ablehnung.

## 8. UI-Grenze

Die bestehende Capture-Review-Seite erhält bei abgeschlossenen Sessions:

- eine eindeutige Primäraktion `Antworten analysieren`,
- eine kurze Wirkungserklärung, dass nur Vorschläge entstehen,
- keinen automatischen Aufruf.

Die neue Vorschauseite zeigt:

- Laufstatus und Metadaten,
- Vorschläge gruppiert nach Zielobjekt und Gruppe,
- Zielpfad, Typ und normalisierten Wert,
- Quellfrage und Quellausschnitt,
- Unsicherheit und Begründung,
- offene Fragen, Widersprüche und kontrollierte Fehler,
- Links zu früheren Läufen.

Nicht Teil der UI:

- Feldübernahme,
- Bearbeiten-und-Übernehmen,
- Verwerfen einzelner Vorschläge,
- Sammelaktionen,
- Objektanlage.

## 9. Tests und Abnahme

Verpflichtend sind insbesondere:

- eingefrorene Katalogversion statt aktueller Version,
- vollständig gültiger Value-Stream- und Use-Case-Lauf,
- unbekannte Zielpfade und rote Felder,
- falsche Quellfrage und erfundener Quellausschnitt,
- Scope-In-/Scope-Out-Verwechslung,
- deutsche Zahlen, Einheiten, Enums, Datum und UUID,
- degenerierte Frage-/Hilfetextwiederholung,
- erfundene Phase oder Lösungsoption,
- Prompt-Injection,
- atomare Ablehnung bei einem fehlerhaften Element,
- fehlender API-Key, Autorisierung, Rate Limit, Timeout, Provider- und Formatfehler,
- Session-, Nutzer- und globale Quoten unter Konkurrenz,
- keine Fachobjekt-, Gate-, Review- oder Lifecycle-Änderung,
- keine Rohtexte und Prompts in Logs,
- vollständige bestehende Repository-CI,
- Desktop- und Mobile-Abnahme nach `DESIGN.md`.

## 10. Zuordnung zu den Arbeitspaketen

| Gap oder Entscheidung | Arbeitspakete |
| --- | --- |
| Verbindliche Repository- und Wiederverwendungsgrenzen | AP 1 |
| Eingefrorener Extraktionsvertrag und Whitelist | AP 2 |
| Analyse-, Vorschlags-, Zielobjekt- und Quotenpersistenz | AP 3 |
| Wiederverwendeter OpenRouter-Transport | AP 4 |
| Ownership, Source Snapshot, Quoten und ausdrücklicher Aufruf | AP 5 |
| Typen, Quellen, Scope, Degeneration und Gruppen | AP 6 |
| Prüffähige serverseitige Vorschau | AP 7 |
| Logging und konfigurierbare 90-Tage-Retention | AP 8 |
| Real-DEMO und Negativabdeckung | AP 9 |
| vollständige Regression und Abschlussnachweis | AP 10 |

## 11. Explizite Nicht-Ziele

- keine Fachobjektänderung oder Objektanlage,
- keine Vorschlagsübernahme,
- keine generativen Lösungsoptionen,
- keine automatische Entscheidung, Validierung, Freigabe oder Lifecycle-Aktion,
- keine Audio-, Datei- oder Connector-Extraktion,
- keine Queue-, Worker- oder Streaming-Infrastruktur,
- keine allgemeine Provider-, Prompt-, Cache-, Vektor-, Billing-, FinOps-, Quota- oder Observability-Plattform,
- keine Änderung von Issue #116.
