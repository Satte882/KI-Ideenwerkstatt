# Accelerator Block 7: Verbindlicher Arbeitsplan

**Issue:** #123  
**Übergeordneter Plan:** #116, unverändert  
**Ausgangsstand:** `main` auf `6bbba52432b2ab3aa8c31da0ffab93b64c9abce3` nach vollständigem Abschluss von Block 6  
**Ziel:** Aus einer bestehenden Prozessanalyse genau drei lösungsoffene, nachvollziehbare Lösungsentwürfe generieren, ohne Bewertung, Rangfolge, Auswahl oder Governance-Entscheidung zu automatisieren.

## 1. Verbindliche Blockgrenze

Block 7 setzt das LLM erstmals generativ ein. Der generative Pfad bleibt jedoch strikt vor dem bestehenden fachlichen Lösungsvergleich und dessen Entscheidungslogik.

Version 1 unterstützt genau drei serverseitig vorgegebene Lösungsrichtungen:

1. `organizational` – organisatorische Änderung,
2. `rule_automation` – regelbasierte beziehungsweise klassische Automatisierung,
3. `assistant` – KI-/Assistenzlösung.

Das LLM darf diese drei Typen weder auswählen, ersetzen, vermehren noch rangordnen. Die dritte Spur verwendet bewusst `assistant`, weil sie eine KI-/Assistenzlösung beschreibt, ohne bereits Generative AI, Machine Learning oder autonome Agentik als technische Lösung festzulegen. Eine spätere manuelle fachliche Umklassifizierung über den regulären Bearbeitungspfad bleibt möglich.

Nicht gebaut werden:

- allgemeine Ideen- oder Strategieplattform,
- autonome Recherche oder Websuche,
- Agentenschleifen,
- automatische Optimierung oder Rangfolge,
- automatische Bewertung,
- automatische Auswahl oder Entscheidungsbegründung,
- Governance-, Freigabe-, Delivery- oder Lifecycle-Aktionen,
- beliebig viele Optionstypen,
- Vektor-Datenbank,
- separates AI-Gateway,
- komplexes Prompt-Management,
- eigenes Billing-System.

Issue #116 bleibt unverändert.

## 2. Verifizierte Gap-Analyse gegen `main`

### 2.1 Bestehendes `SolutionOption`-Modell

`SolutionOption` besitzt aktuell folgende fachlich relevante Felder:

- `name`,
- `option_type`,
- `recommendation`,
- `evaluation_status`,
- `description`,
- `expected_value`,
- `bottleneck_coverage`,
- `feasibility`,
- `data_requirements`,
- `application_impact`,
- `integration_impact`,
- `integration_effort`,
- `technology_constraints`,
- `risks`,
- `architecture_fit`.

`recommendation` startet bereits neutral als `candidate`; `evaluation_status` startet als `draft`.

Ein kritischer Gap besteht bei `feasibility` und `integration_effort`: Beide Felder erhalten heute beim Anlegen automatisch den Wert `medium`. Die bestehende Vergleichsmatrix rendert diese Werte sichtbar. Eine KI-generierte Option würde dadurch trotz `evaluation_status=draft` wie bereits teilweise bewertet erscheinen. Das verletzt die Entscheidungsgrenze aus #123.

Verbindliche Folgerung:

- Block 7 führt für beide Felder einen expliziten Zustand `not_assessed` / „Noch nicht bewertet“ ein.
- Neue manuelle und generierte Optionen starten künftig neutral.
- Bestehende Datensätze behalten ihre bisherigen Werte; es gibt keine rückwirkende Umdeutung vorhandener Bewertungen.
- `evaluation_status=assessed` darf nur gespeichert werden, wenn beide Bewertungsfelder einen echten Wert aus `low`, `medium`, `high` besitzen und die übrigen bestehenden Pflichtkriterien erfüllt sind.

### 2.2 Vergleichs- und Auswahlservice

Der bestehende Lösungsvergleich sortiert Optionen lösungsoffen und blockiert eine Auswahl, solange nicht mindestens zwei Optionen vollständig bewertet sind. `select_preferred_solution()` ist transaktional, prüft Berechtigungen und Fokusentscheidung, erzeugt erst bei ausdrücklicher manueller Aktion eine `SolutionSelectionDecision` und setzt erst dort `preferred` beziehungsweise `rejected`.

Verbindliche Folgerung:

- Block 7 ruft `select_preferred_solution()` niemals auf.
- Der Auswahlservice wird nicht um LLM-Verhalten erweitert.
- Gate-Regressionen müssen beweisen, dass Generierung und Übernahme keine `SolutionSelectionDecision` erzeugen und keine Empfehlung verändern.

Die Vergleichsmatrix zeigt aktuell `technology_constraints` nicht an, obwohl das Feld im Modell und im regulären Formular existiert. Block 7 ergänzt deshalb eine Zeile „Technologieleitplanken“. Ältere manuelle Optionen mit leerem Feld müssen weiterhin korrekt mit neutralem Leerwert gerendert werden.

### 2.3 Prozessanalyse und Readiness

Eine `ProcessAnalysis` besitzt elf heute fachlich verpflichtende Textfelder:

1. `name`,
2. `scope_start`,
3. `scope_end`,
4. `trigger`,
5. `outcome`,
6. `current_flow`,
7. `roles`,
8. `systems`,
9. `data_objects`,
10. `bottlenecks`,
11. `baseline_metrics`.

Optional sind insbesondere `business_rules`, `handoffs`, `exceptions` und `target_state_principles`.

Verbindliches Readiness-Kriterium für Version 1:

- Die Prozessanalyse existiert und gehört zu einer existierenden Value-Stream-Phase.
- Alle elf oben genannten Pflichtfelder sind nach Trim nicht leer.
- Die zugehörige Prozessversion wird im Source Snapshot eingefroren.
- Eine formale `ProcessValidation` ist nicht zwingend erforderlich, weil Block 7 nur Kandidaten erzeugt und der bestehende manuelle Lösungsoptionspfad ebenfalls keine Prozessvalidierung als Gate verlangt.
- Der aktuelle Validierungszustand wird jedoch eindeutig als `current_validated`, `not_validated` oder `validation_stale` gekennzeichnet und in der Preview sichtbar gemacht.
- `review_required` oder ein älterer Validierungsnachweis darf niemals als aktuell bestätigt erscheinen.

Diese Readiness-Prüfung ist ein technisches Eingangskriterium für die Generierung, kein neues fachliches Lifecycle-Gate.

### 2.4 Verlässliche Quellen und deterministische Fakten

Die Prozessanalyse liefert bereits:

- Ist-Ablauf,
- Bottlenecks,
- Rollen,
- Systeme,
- Datenobjekte,
- Geschäftsregeln,
- Übergaben,
- Ausnahmen,
- Baseline,
- Soll-Prinzipien.

Zusätzlich können die bestehenden Value-Stream-Leitplanken und der relevante Phasenkontext verwendet werden.

Gemeinsame Fakten werden serverseitig in einen kanonischen Source Snapshot übernommen und nicht dreifach vom LLM neu formuliert. Das LLM erhält stabile Source-IDs und darf seine Aussagen nur auf diese IDs beziehen oder sie ausdrücklich als Annahme beziehungsweise offene Evidenz kennzeichnen.

Insbesondere verboten sind:

- erfundene Systeme, Rollen oder Datenquellen,
- erfundene Integrationen als bestehender Ist-Zustand,
- erfundene regulatorische Anforderungen,
- erfundene Kennzahlen oder Einsparprozente,
- erfundene Freigaben oder Validierungen,
- erfundene Bewertung von Machbarkeit oder Integrationsaufwand.

### 2.5 Wiederverwendung aus Block 4 bis 6

| Bereich | Vorhandener Baustein | Verbindliche Nutzung in Block 7 |
|---|---|---|
| LLM-Policy | zentraler Timeout sowie Input-, Output-, Context-, User- und Global-Limits | unverändert maßgeblich; keine zweite Policy |
| OpenRouter | begrenzter Transport, strukturierte JSON-Ausgabe, Fehlercodes, Token-/Kostenmetadaten | wiederverwenden; kein zweiter Providerclient |
| Block 4 | versionierter Vertrag, minimierter Payload, serverseitige Schema-/Quellenprüfung, keine Rohprompts in Standardlogs | Muster direkt übernehmen |
| Block 4 Kostenmetadaten | `provider`, `model_name`, `input_chars`, `output_chars`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost`, Laufzeit und Fehlercode | identische Feldnamen und Einheiten verwenden |
| Block 5 | Human-in-the-loop, reguläre Forms, Konfliktschutz, Idempotenzprinzip | für die explizite Übernahme wiederverwenden |
| Block 6 | Prozessanalyse als `draft`, `source_snapshot`, atomare Objektanlage und Gate-Invarianz | Herkunfts- und Schreibprinzip wiederverwenden |
| Architektur-Provenance | Source-Snapshots und Source-Differenzen | Konzept für Source-IDs und Stale-Prüfung wiederverwenden |

### 2.6 Quoten-Gap

`AcceleratorLLMQuota` besitzt bereits `context`, `user` und `global`. Der Context ist heute jedoch technisch ausschließlich an `CaptureSession` gebunden. #123 verlangt eine Begrenzung pro Prozessanalyse beziehungsweise Benutzer.

Verbindliche Folgerung:

- Die bestehende Quoteninfrastruktur wird erweitert, nicht dupliziert.
- Ein Context kann künftig entweder eine `CaptureSession` oder eine `ProcessAnalysis` sein, niemals beides.
- Bestehende Capture-Quoten bleiben rückwärtskompatibel.
- User- und Global-Quoten bleiben unverändert.
- Ein konkurrierender, serverseitig abgewiesener Zweitstart darf keine zweite Context-Quote verbrauchen.

### 2.7 Datenschutz und Datenminimierung

Block 4 besitzt keine allgemeine semantische PII-Redaktionsengine. Wiederzuverwenden sind deshalb die tatsächlich vorhandenen Schutzmechanismen und nicht eine neu erfundene zweite Datenschutzlogik:

- nur explizit benötigte und whitelisted Quelldaten an den Provider senden,
- keine kompletten Modellobjekte oder unbeteiligten Metadaten serialisieren,
- keine Nutzerprofile oder Berechtigungsdaten in den Prompt aufnehmen,
- Prompt- und Quelldaten nicht in Standardlogs schreiben,
- sensible Variablen in Fehlerpfaden schützen,
- Provider-, Modell-, Laufzeit-, Token-, Kosten- und Fehler-Metadaten separat protokollieren,
- bestehende Retention-Grundsätze für technische Accelerator-Artefakte wiederverwenden, soweit für Block 7 persistent gespeicherte Preview-Daten erforderlich sind.

Eine generische Redaktions- oder DLP-Plattform ist nicht Teil von Block 7.

## 3. Architekturentscheidungen

### 3.1 Preview vor Fachobjektanlage

Ein erfolgreicher Provideraufruf erzeugt zunächst ein serverseitig validiertes Generation-Bundle. Zu diesem Zeitpunkt wird keine `SolutionOption` angelegt.

Erst eine ausdrückliche Benutzeraktion nach sichtbarer Prüfung übernimmt das vollständige Dreier-Bundle atomar in drei reguläre `SolutionOption`-Objekte.

Gründe:

- Providerfehler verändern keine Fachobjekte.
- Schemafehler verändern keine Fachobjekte.
- Der Nutzer sieht Quellen, Annahmen, Lücken und Unsicherheit vor der Anlage.
- Eine unbrauchbare Generierung kann vollständig verworfen werden.
- Eine Teilanlage von nur einer oder zwei Optionen ist ausgeschlossen.
- Der bestehende reguläre Fachpfad bleibt maßgeblich.

### 3.2 Ein Provideraufruf für das komplette Dreier-Bundle

Genau ein OpenRouter-Aufruf erzeugt alle drei Optionsentwürfe.

Der Server gibt die drei Typen vor. Der Provider füllt ausschließlich die freigegebenen generativen Felder.

Gründe:

- gleiche Ausgangsdaten und gleiche Promptversion,
- bessere Vergleichbarkeit,
- geringere Kosten,
- genau ein Context-Aufruf,
- einfaches All-or-nothing-Schema,
- keine teilweise erfolgreiche Generierung.

### 3.3 Generierbare und manuelle Felder

Generierbar sind ausschließlich:

- `name`,
- `description`,
- `expected_value`,
- `bottleneck_coverage`,
- `data_requirements`,
- `application_impact`,
- `integration_impact`,
- `technology_constraints`,
- `risks`,
- `architecture_fit`.

Deterministisch gesetzt werden:

- `option_type` auf genau einen der drei V1-Typen,
- `recommendation=candidate`,
- `evaluation_status=draft`,
- `feasibility=not_assessed`,
- `integration_effort=not_assessed`.

Der Provider darf keine der deterministisch gesetzten oder manuell zu bewertenden Felder liefern.

`expected_value` darf qualitative Wirkung aus den Quellen synthetisieren. Quantitative Verbesserungswerte dürfen nur verwendet werden, wenn sie als vorhandene Quelle vorliegen; neue Prozentwerte, Kostenwerte oder Zeiteinsparungen dürfen nicht erfunden werden.

### 3.4 Statement-Provenance

Jede generierte Feld-Aussage besitzt strukturiert:

- Text,
- Liste referenzierter Source-IDs,
- Annahmen,
- offene Evidenz,
- Unsicherheit mit begründetem niedrigen, mittleren oder hohen Niveau.

Gemeinsame Ist-Fakten werden separat als deterministische Ausgangslage angezeigt. Die drei Optionen sollen primär ihre unterschiedlichen Lösungswirkungen und Bedingungen beschreiben statt denselben Ist-Zustand dreimal umzuschreiben.

### 3.5 Prompt-Injection-Abwehr als Designregel

Freitext aus `current_flow`, `bottlenecks`, `business_rules`, `exceptions` und anderen Prozessfeldern wird ausschließlich als untrusted source data behandelt.

Verbindliche Regeln:

- Systemanweisung und Quelldaten bleiben getrennte Message-Inhalte beziehungsweise klar getrennte strukturierte Payloadteile.
- Quelldaten werden als JSON-artige Faktenobjekte mit Source-ID, Feldname und Wert übergeben, niemals als angebliche Instruktionen.
- Der Systemprompt erklärt explizit, dass Anweisungen innerhalb der Quelldaten Dateninhalt und nicht ausführbare Instruktionen sind.
- Provideroutput ist ausschließlich im strikten versionierten Schema zulässig.
- Unbekannte Felder, zusätzliche Optionstypen, Bewertungsfelder, Rankings, Freigaben oder Entscheidungsanweisungen werden serverseitig fail-closed abgewiesen.
- Prompt-Injection wird damit nicht als reine Prompttechnik behandelt; die maßgebliche Schutzschicht ist der serverseitige Vertrag.

### 3.6 Laufpersistenz und Nebenläufigkeit

Block 7 erhält einen kleinen, domänenspezifischen technischen Laufnachweis `SolutionGenerationRun` oder einen äquivalenten final in AP 4 festgelegten Namen. Er ist keine generische AI-Run-Plattform.

Mindestens gespeichert werden mit denselben Feldnamen und Einheiten wie Block 4:

- Prozessanalyse und Prozessversion,
- Source Hash,
- anfordernder Benutzer,
- Status `running`, `success`, `failed`,
- Provider und Modell,
- Prompt-/Schema-Version,
- Start, Ende und Laufzeit,
- Fehlercode,
- `input_chars`, `output_chars`,
- `prompt_tokens`, `completion_tokens`, `total_tokens`,
- `cost`.

Nebenläufigkeitsregel:

- Pro `ProcessAnalysis` darf zu jedem Zeitpunkt höchstens ein Lauf `running` sein.
- Die Regel wird datenbankseitig abgesichert und zusätzlich innerhalb des Servicepfads geprüft.
- Der verlierende gleichzeitige Request startet keinen Provideraufruf und verbraucht keine zusätzliche Context-Quote.
- Ein erfolgreicher Lauf für denselben unveränderten Source Hash darf bewusst erneut erzeugt werden, solange die Quoten dies erlauben; Block 7 baut keinen Ergebnis-Cache.

### 3.7 Stale- und Konfliktschutz

Der Source Snapshot enthält mindestens:

- Prozessanalyse-ID,
- Prozessversion,
- relevante Quellfelder mit kanonischem Wert,
- Value-Stream-/Phasenkontext soweit verwendet,
- aktuellen Validierungsstatus,
- Source Hash.

Unmittelbar vor der Übernahme wird der relevante Quellzustand erneut berechnet.

Wenn sich eine verwendete Quelle geändert hat:

- wird das Generation-Bundle als stale behandelt,
- werden keine `SolutionOption`-Objekte angelegt,
- muss der Nutzer neu generieren.

Keine Force-Overwrite- oder automatische Merge-Funktion.

### 3.8 Atomare Übernahme

Die drei Entwürfe werden in einer gemeinsamen Transaktion über den bestehenden regulären `SolutionOptionForm`-Pfad validiert und gespeichert.

Vor dem Schreiben werden erneut geprüft:

- Berechtigung,
- Zugehörigkeit zur Prozessanalyse,
- Readiness und Source Hash,
- vollständige drei Optionstypen,
- erlaubte Felder,
- neutraler Bewertungs- und Empfehlungszustand.

Schlägt eine Option fehl, werden null Optionen angelegt.

Ein stabiler Idempotenznachweis verhindert, dass ein wiederholter POST dieselben drei Entwürfe ein zweites Mal als weitere drei Optionen anlegt.

## 4. Verbindliche Arbeitspakete

### AP 1 – Bewertungsneutralität und Vergleichskompatibilität

Umfang:

- `not_assessed` für `feasibility` und `integration_effort` einführen,
- Default neuer Optionen auf `not_assessed` setzen,
- bestehende Datensätze unverändert lassen,
- reguläre Formvalidierung für `assessed` verschärfen,
- Vergleichsmatrix um „Technologieleitplanken“ ergänzen,
- ältere manuelle Optionen mit leeren Technologiebedingungen regressiv prüfen.

Abnahme:

- neue Optionen erscheinen nicht implizit als mittel bewertet,
- bestehende Bewertungen bleiben unverändert,
- bestehende manuelle Vergleichsansicht bleibt funktionsfähig.

### AP 2 – Readiness, Source Snapshot und Datenminimierung

Umfang:

- explizite Prüfung der elf Pflichtfelder,
- aktuellen Validierungsstatus korrekt klassifizieren,
- kanonischen Source Snapshot mit stabilen Source-IDs bauen,
- Source Hash und relevante Versionen festhalten,
- nur whitelisted Prozess-/Value-Stream-Daten für Providerinput vorbereiten,
- keine Nutzerprofile, irrelevanten Modellfelder oder vollständigen Objekte serialisieren.

Abnahme:

- unvollständige Prozessanalysen starten keinen Provideraufruf,
- formale Validierung ist kein zusätzliches Gate,
- aktuelle, fehlende und stale Validierung werden unterscheidbar,
- Payload enthält ausschließlich freigegebene Quelldaten.

### AP 3 – Generierungsvertrag, Prompt-Datentrennung und Provenance

Umfang:

- versioniertes striktes JSON-Schema für genau drei Optionen definieren,
- generierbare Feldwhitelist festschreiben,
- Statement-Provenance mit Sources, Annahmen, offener Evidenz und Unsicherheit definieren,
- Systemanweisung strikt von untrusted source data trennen,
- Source-IDs statt freier Quellenbezeichnungen verwenden,
- Providerfelder für Bewertung, Rangfolge, Auswahl und Governance vollständig ausschließen.

Abnahme:

- Schema kann keine vierte Option oder unbekannte Optionstypen ausdrücken,
- Prozessfreitext kann keine Systeminstruktion ersetzen,
- jede generierte Aussage ist strukturell einer Quelle, Annahme oder Evidenzlücke zugeordnet.

### AP 4 – Laufpersistenz, Quoten und Nebenläufigkeit

Umfang:

- domänenspezifischen Generation-Run persistieren,
- exakt Block-4-kompatible Lauf-, Token- und Kostenmetadaten verwenden,
- bestehende Context-Quote rückwärtskompatibel um `ProcessAnalysis` erweitern,
- höchstens einen aktiven Lauf pro Prozessanalyse datenbankseitig absichern,
- konkurrierenden Zweitstart vor Provideraufruf und zusätzlichem Context-Verbrauch stoppen,
- Retention und metadaten-only Logging an bestehende Accelerator-Regeln anbinden.

Abnahme:

- Capture-Quoten funktionieren unverändert weiter,
- ProcessAnalysis-Context-, User- und Global-Limits greifen,
- zwei parallele Starts erzeugen höchstens einen Provideraufruf,
- Kosten-/Tokenfelder sind über Block 4 und 7 direkt vergleichbar.

### AP 5 – Einmalige strukturierte LLM-Generierung

Umfang:

- bestehenden OpenRouter-Transport wiederverwenden,
- genau einen Provideraufruf für das vollständige Dreier-Bundle ausführen,
- zentrale Timeout-, Input- und Output-Limits verwenden,
- keine automatische Retry-Schleife,
- `finish_reason=length`, Rate Limit, Provider-, Netzwerk- und Konfigurationsfehler kontrolliert behandeln,
- erfolgreiche technische Metadaten in den Generation-Run übernehmen.

Abnahme:

- ein erfolgreicher Nutzerstart erzeugt genau einen Provideraufruf,
- technische Fehler erzeugen keine `SolutionOption`,
- bestehende manuelle Optionen und Prozessdaten bleiben unverändert.

### AP 6 – Fail-closed Validierung und Halluzinationsgrenzen

Umfang:

- Providerantwort vollständig gegen Version, Schema, Optionstypen und Feldwhitelist prüfen,
- unbekannte Source-IDs ablehnen,
- fehlende Source-/Annahmen-/Evidenzstruktur ablehnen,
- Bewertungs-, Ranking-, Auswahl-, Freigabe- und Governancefelder ablehnen,
- quantitative Nutzenbehauptungen ohne entsprechende Quelle ablehnen beziehungsweise als unzulässige Erfindung behandeln,
- degenerierte oder inhaltsleere Dreier-Bundles ablehnen,
- erfolgreiche Antwort erst nach vollständiger Validierung als Preview persistieren.

Abnahme:

- eine ungültige Teiloption verwirft das gesamte Bundle,
- erfundene oder unbekannte Quellen führen zu null Fachobjektänderungen,
- der Provider kann keine Bewertungs- oder Entscheidungsfelder einschleusen.

### AP 7 – Preview- und Bearbeitungs-UI

Umfang:

- Einstieg „3 Lösungsentwürfe mit KI erstellen“ im bestehenden Lösungsvergleich ergänzen,
- regulären manuellen Einstieg „Option ergänzen“ gleichwertig erhalten,
- gemeinsame deterministische Ausgangslage einmal anzeigen,
- drei Optionen vergleichbar darstellen,
- pro Feld Quellen, Annahmen, offene Evidenz und Unsicherheit sichtbar machen,
- Kennzeichnung „KI-Entwurf – noch nicht fachlich bewertet“ anzeigen,
- Bearbeitung der generierbaren Entwurfsfelder vor Übernahme ermöglichen,
- Fehler-, Quoten-, stale- und nicht-readiness-Zustände verständlich darstellen.

Abnahme:

- Unterschiede zwischen drei Optionen sind sichtbar,
- Quellen und Unsicherheit sind nicht hinter einer Detailseite verborgen,
- keine UI-Aktion bewertet oder bevorzugt eine Option,
- Desktop und Mobile bleiben ohne unkontrollierten horizontalen Dokumentüberlauf bedienbar.

### AP 8 – Atomare Übernahme in reguläre Lösungsoptionen

Umfang:

- explizite Übernahmeaktion für das vollständige Dreier-Bundle,
- Berechtigung und Source Hash innerhalb der Transaktion erneut prüfen,
- bearbeitete Preview-Werte serverseitig erneut validieren,
- drei `SolutionOption` über bestehenden Formpfad erzeugen,
- deterministische Zustände `candidate`, `draft`, `not_assessed`, `not_assessed` erzwingen,
- vollständigen Rollback bei jedem Form-, Konflikt- oder Persistenzfehler,
- Idempotenz gegen Doppel-POST sicherstellen.

Abnahme:

- Erfolg erzeugt genau drei normale Lösungsoptionen,
- Fehler erzeugt null neue Optionen,
- Quellenänderung blockiert die Übernahme,
- wiederholter identischer POST erzeugt keine sechs Optionen,
- Optionen sind danach regulär manuell bearbeit- und bewertbar.

### AP 9 – Sicherheits-, Ausfall- und Gate-Regression

Umfang:

- fehlende Pflichtquellen,
- widersprüchliche Daten,
- unbekannte Source-IDs,
- Prompt Injection in allen relevanten Freitextquellen,
- unbekannte Felder und zusätzliche Optionstypen,
- quantitative Erfindungen,
- Rate Limit, Timeout, 401/403/5xx, Netzwerkfehler, ungültiges JSON und abgeschnittene Antworten,
- konkurrierende Generierung,
- stale Preview,
- doppelter Übernahme-POST,
- Gate-Invarianz und unveränderter Auswahlservice,
- Rückwärtskompatibilität bestehender manueller Optionen und Vergleichsansicht.

Abnahme:

- kein Fehlerpfad erzeugt Teiloptionen oder Statusänderungen,
- keine `ProcessValidation`, `SolutionSelectionDecision`, Governance-, Delivery- oder Lifecycle-Änderung,
- bestehende manuelle Optionen bleiben unverändert,
- `select_preferred_solution()` verhält sich unverändert.

### AP 10 – Real-DEMO, Drift-Schutz und Blockabschluss

Umfang:

- bestehenden Angebotsvergleich aus Block 6 als realen fachlichen Ausgangspunkt verwenden,
- genau drei Entwürfe erzeugen: organisatorisch, regelbasiert, KI-Assistenz,
- realen produktiven Source-, Validierungs-, Preview- und Übernahmepfad ausführen,
- externen Provider im CI-Nachweis deterministisch ersetzen, aber den produktiven Servicepfad verwenden,
- Golden-JSON und SHA-256-Driftschutz ergänzen,
- getrennten Ausfall-/Rollback-Nachweis ausführen,
- Desktop-/Mobile-Abnahme durchführen,
- vollständige unveränderte Repository-CI grün nachweisen,
- `BLOCK_7_COMPLETION.md` erstellen und Abnahmekriterien aus #123 einzeln belegen.

Abnahme:

- exakt drei neutral unbewertete `SolutionOption`-Objekte,
- Quellen/Annahmen/Lücken/Unsicherheit im Real-DEMO sichtbar,
- keine automatische Auswahl oder Bewertung,
- deterministischer Drift-Schutz,
- vollständige CI und UI-Verifikation grün.

## 5. Testmatrix über den Block

Mindestens abzudecken sind:

| Kategorie | Verbindlicher Nachweis |
|---|---|
| Readiness | jedes der elf Pflichtfelder einzeln leer; optionales Feld leer; Validierung aktuell/fehlend/stale |
| Quellen | gültige IDs, unbekannte IDs, geänderte Quellen, widersprüchliche Quellen |
| Prompt Injection | Instruktionen in Ablauf, Bottleneck, Regel, Ausnahme und Zielprinzipien bleiben Daten |
| Vertrag | genau drei Typen, keine vierte Option, keine unbekannten Felder, keine Bewertungsfelder |
| Erfindungen | unbekannte Systeme/Rollen/Daten, erfundene Zahlen, unbelegte Vorteile |
| Provider | 401, 403, 429, 5xx, Timeout, Netzwerk, ungültiges JSON, leere Antwort, Truncation |
| Quoten | ProcessAnalysis-Context, User, Global, Tageswechsel, konkurrierender Start |
| Atomarität | Teilfehler, Formfehler, stale Source, terminaler Fehler, vollständiger Rollback |
| Idempotenz | paralleler Start, doppelter Übernahme-POST, wiederholte terminale Antwort |
| Rückwärtskompatibilität | bestehende manuelle Optionen, ältere leere Technologiebedingungen, bestehender Auswahlservice |
| Gates | keine Validation-, Selection-, Governance-, Delivery- oder Lifecycle-Mutation |
| UI | Desktop/Mobile, lange Inhalte, Fehlerzustände, keine implizite Bewertung |

## 6. Verbindliche Abnahmematrix gegen Issue #123

| Abnahmekriterium #123 | Geplanter Nachweis |
|---|---|
| Gap-Analyse dokumentiert | dieser Workplan und Planungs-PR |
| Drei vergleichbare, lösungsoffene Entwurfsoptionen | AP 3, 5, 7, 8 und Real-DEMO |
| Quellen, Annahmen, Lücken und Unsicherheiten sichtbar | AP 2, 3, 6, 7 und UI-Nachweis |
| Gemeinsame Fakten nicht unnötig vom LLM neu erfunden | AP 2 und 7 |
| Keine Option automatisch bewertet oder bevorzugt | AP 1, 3, 8, 9 |
| Ausfall und Rate Limit ohne Teil- oder Statusänderungen | AP 4, 5, 8, 9 |
| Fehlende Quellen, Widersprüche, Erfindungen und Gate-Schutz getestet | AP 6 und 9 |
| Lösung auf bestehenden Lösungsvergleich begrenzt | gesamte Architektur und Abschlussnachweis |

## 7. Sequenz- und Merge-Regel

Die Umsetzung erfolgt streng nacheinander.

- Dieser Workplan wird als eigener erster Pull Request gegen `main` gemergt.
- Danach folgen AP 1 bis AP 10 jeweils auf aktuellem `main`.
- Jedes AP erhält eigenen Branch, eigenen Commit und eigenen Pull Request.
- Kein Folge-AP wird begonnen, solange der vorherige PR nicht mit vollständiger unveränderter Repository-CI grün und gemergt ist.
- Die Checkliste in Issue #123 verwendet exakt die oben genannten AP-Titel und wird erst nach erfolgreichem Merge des jeweiligen AP abgehakt.
- Issue #123 wird erst nach AP 10, grünem `main`, Abschlussdokumentation und vollständig erfüllten Abnahmekriterien geschlossen.
- Issue #116 wird in keinem Arbeitspaket geändert.

## 8. Definition of Done für Block 7

Block 7 ist abgeschlossen, wenn:

1. der Planungs-PR und AP 1 bis AP 10 einzeln gemergt sind,
2. die vollständige unveränderte Repository-CI nach jedem AP grün war,
3. die Real-DEMO- und UI-Abnahmen grün sind,
4. alle Checklistenpunkte in #123 belegt und abgehakt sind,
5. `BLOCK_7_COMPLETION.md` die tatsächlichen Abweichungen vom Workplan transparent dokumentiert,
6. `main` nach dem letzten Merge grün ist,
7. Issue #123 geschlossen werden kann, ohne #116 zu verändern.
