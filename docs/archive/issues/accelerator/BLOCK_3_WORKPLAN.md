# Accelerator Block 3: Geführte Erfassung ohne LLM – Arbeitsplan

**Issue:** #119  
**Übergeordneter Plan:** #116  
**Abhängigkeiten:** Block 1 / #117 und Block 2 / #118  
**Ausgangspunkt:** `main` auf `058e26139edf1c149b618e80a4e4daf70b29a218`  
**Zielzustand:** Berechtigte Nutzer können persistente, wiederaufnehmbare Value-Stream- und Use-Case-Erfassungen anlegen, speichern, fortsetzen, abschließen und verwerfen, ohne reguläre Fachobjekte zu verändern.

## Verbindliche Umsetzungsregeln

- Dieser Workplan wird vor der technischen Umsetzung über einen eigenen Pull Request nach `main` übernommen.
- Danach wird in Issue #119 eine Checkliste mit exakt den unten stehenden AP-Titeln angelegt.
- Jedes Arbeitspaket wird auf einem eigenen Branch mit eigenem Commit und eigenem Pull Request umgesetzt und erst nach erfolgreicher vollständiger CI gemergt.
- Die Reihenfolge der Arbeitspakete ist verbindlich.
- Jeder AP-Branch startet vom jeweils aktuellen `main` und wird unmittelbar nach dem Merge remote gelöscht. Vor dem nächsten AP wird geprüft, dass keine erledigten Block-3-Branches offen bleiben.
- Issue #116 wird nicht verändert.
- Capture Sessions sind ausschließlich temporäre Arbeits- und Herkunftsschichten. Sie sind keine fachlich führende Quelle und verändern keine regulären Value-Stream-, Prozess-, Lösungsoptions-, Use-Case-, Governance-, Delivery- oder Lifecycle-Objekte.
- Version 1 unterstützt genau zwei Capture-Arten: `value_stream` und `use_case`. Es entsteht kein allgemeiner Form Builder, Survey-Baukasten oder Case-Management-System.
- Fragenkataloge und Antwortschemas sind codebasiert und versioniert. Eine laufende Session bleibt unveränderlich an die beim Anlegen gespeicherte Katalog- und Schemaversion gebunden. Alte, weiterhin im Code unterstützte Versionen werden mit ihrem eingefrorenen Katalog fortgesetzt; nicht mehr unterstützte Versionen werden schreibgeschützt blockiert und mit einer klaren Meldung angezeigt. Eine stille Migration oder Neuinterpretation vorhandener Antworten ist ausgeschlossen.
- Ein Nutzer darf mehrere parallele offene Sessions je Capture-Art besitzen. Die Übersicht macht Art, Titel beziehungsweise Arbeitsbezeichnung, Fortschritt, letzte Änderung und Ablauf sichtbar. Es gibt keine künstliche Ein-Entwurf-pro-Art-Grenze.
- Optimistic Locking schützt nur Schreibvorgänge. Reine Vor-/Zurück-Navigation und GET-Aufrufe verändern keine Revision und erzeugen keinen Konflikt. Ein Konflikt entsteht nur, wenn ein POST mit veralteter Revision speichern oder abschließen will.
- Große Eingabefelder bleiben native semantische HTML-`textarea`-Elemente ohne Custom-JavaScript-Eingabesteuerung. Damit bleiben Betriebssystem-Diktatfunktionen wie Windows `WIN + H` ohne Zusatzintegration nutzbar.
- Inaktive Entwürfe laufen nach 30 Tagen ohne gültige Änderung ab. Abgeschlossene Sessions werden in Block 3 als notwendige Quelle für Block 4 erhalten. Diese Aufbewahrung ist ausdrücklich ein Zwischenzustand; spätestens mit der Vorschlagspersistenz aus Block 4 wird eine fachlich begründete Löschregel für abgeschlossene Rohantworten festgelegt und getestet.
- Zeitmessung trennt aktive Eingabe von bloßer Kalenderdauer und bleibt auf wenige zweckgebundene Messfelder begrenzt. Es entsteht kein Produkt-Analytics- oder Telemetriesystem.

## Architekturentscheidungen

### Eigener begrenzter Accelerator-Kontext

Die Capture-Funktion wird in einer kleinen Django-App `ki_radar.accelerator` umgesetzt. Sie betrifft sowohl Architektur- als auch Use-Case-Erfassung und darf weder `core` noch eines der führenden Domänenmodule zu einem Sammelbecken für temporäre Arbeitsdaten machen.

### Ein gemeinsames Capture-Modell

Ein `CaptureSession`-Modell speichert Besitzer, Capture-Art, Katalog- und Schemaversion, Antworten, Status, Revision, Fortschritt, Zeitmessung und Retention-Metadaten. Antworten werden als validiertes JSON-Dokument mit stabilen Frage-IDs gespeichert. Eine generische Antworttabelle ist für die zwei festen Kataloge nicht erforderlich.

### Unveränderlicher Abschluss

Zulässige Zustandsübergänge sind:

- `draft → completed`
- `draft → discarded`
- `draft → expired`

Abgeschlossene, verworfene und abgelaufene Sessions sind nicht mehr bearbeitbar. Block 4 kann dadurch eindeutig auf den analysierten Antwortstand verweisen.

### Berechtigungsgrenze

- Value-Stream-Capture verwendet die bestehende Berechtigung zur Anlage von Architekturinhalt.
- Use-Case-Capture verwendet die bestehende Berechtigung zur Anlage von Use Cases.
- Zusätzlich ist jede Session strikt eigentümergebunden; erratene oder manipulierte UUIDs gewähren keinen Zugriff.

### Katalog- und Blueprint-Kompatibilität

Jede Frage besitzt stabile ID, Abschnitt, Pflichtstatus, Eingabetyp, Längengrenze und deklarierte mögliche Blueprint-Zielpfade. Automatisierte Tests prüfen die Zielpfade gegen den Blueprint-Vertrag aus Block 2. Ein konkreter `[Real-DEMO]`-Rückwärtstest belegt zusätzlich, dass beide Kataloge die für das Referenzszenario benötigten narrativen Informationen abdecken können. Block 3 nimmt noch keine Extraktion oder vollständige Domainvalidierung vor.

## AP 1: Gap-Analyse und verbindliche Wiederverwendungsgrenzen dokumentieren

- Aktuellen `main` einschließlich Intake-Wizard, Forms, Berechtigungen, URLs, Templates, Retention-Muster, Management Commands, Logging und Tests prüfen.
- Wiederverwendbare UI-, Form- und Navigationsmuster von nicht wiederverwendbarer Session- und Objektanlage trennen.
- Autoritative Regeln aus #117, #118, `AGENTS.md`, `DESIGN.md` und dem Blueprint-Vertrag mit Repository-Evidenz zuordnen.
- Rohdaten-, Historisierungs-, Berechtigungs- und Retention-Risiken dokumentieren.
- Minimalen Block-3-Zuschnitt und Abnahmemapping festhalten.

**Ergebnis:** `docs/accelerator/BLOCK_3_GAP_ANALYSIS.md`.

## AP 2: Versionierten Capture-Vertrag und beide Fragenkataloge festlegen

- Antwortschema Version 1 und codebasiertes Katalogregister einführen.
- Getrennte Kataloge Version 1 für Value Stream und Use Case definieren.
- Stabile Frage-IDs, Abschnitte, Pflichtstatus, native Eingabetypen, Längengrenzen und Blueprint-Zielpfade festlegen.
- Scope-In und Scope-Out als getrennte Fragen führen.
- Regel für eingefrorene alte Katalogversionen und kontrollierte Blockierung nicht mehr unterstützter Versionen implementieren.
- Katalogpfade automatisiert gegen den bestehenden Blueprint-Vertrag prüfen.

**Ergebnis:** Kleiner versionierter Capture-Vertrag ohne Datenbankänderung und ohne dynamischen Form Builder.

## AP 3: Persistentes CaptureSession-Modell und Migration einführen

- Kleine App `ki_radar.accelerator` registrieren.
- `CaptureSession` mit UUID, Besitzer, Capture-Art, Arbeitsbezeichnung, Katalog- und Schemaversion, validierten Antworten, Status, Revision, Fortschritt, Zeitmessung und Retention-Zeitpunkten implementieren.
- Mehrere parallele offene Sessions je Nutzer und Capture-Art ausdrücklich zulassen.
- Geeignete Indizes für Besitzer, Status, Art, letzte Änderung und Ablauf ergänzen.
- Keine Historientabelle für vollständige Rohantworten einführen.

**Ergebnis:** Persistente, zweckgebundene Arbeits- und Herkunftsschicht ohne Änderung bestehender Fachmodelle.

## AP 4: Lifecycle-, Speicher-, Konflikt- und Berechtigungsservice implementieren

- Explizite Services für Anlegen, Speichern, Abschließen, Verwerfen und Ablauf bereitstellen.
- Besitzer ausschließlich serverseitig aus dem angemeldeten Benutzer setzen.
- Bestehende Architektur- und Use-Case-Berechtigungen wiederverwenden und Session-Ownership zusätzlich prüfen.
- Antwortdokument gegen gespeicherten Katalog und Schema validieren; unbekannte Fragen abweisen.
- Revision nur bei erfolgreichem Schreibvorgang erhöhen.
- Veraltete POST-Revisionen verständlich als Konflikt ablehnen; GET-, Vor- und Zurück-Navigation bleiben konfliktfrei.
- Abschluss atomar nur bei vollständigen Pflichtantworten erlauben.

**Ergebnis:** Kleiner expliziter Domain-Service ohne generischen CRUD- oder Merge-Layer.

## AP 5: Geführte Value-Stream-Erfassung bereitstellen

- Serverseitigen mehrseitigen Wizard aus dem Value-Stream-Katalog erzeugen.
- Zwischenspeichern, Zurück, Weiter, Fortschritt, Abschlussprüfung und verständliche Fehleranzeige umsetzen.
- Native semantische `textarea`-Elemente mit sichtbaren Labels und ohne Custom-JS-Eingabesteuerung verwenden.
- Scope-In und Scope-Out getrennt anzeigen und speichern.
- Reine Navigation darf keine Revision verändern; veraltete Schreibvorgänge werden getestet.
- Abschluss erzeugt ausschließlich eine abgeschlossene Capture Session.

**Ergebnis:** Persistente, wiederaufnehmbare und `WIN + H`-kompatible Value-Stream-Erfassung.

## AP 6: Geführte Use-Case-Erfassung bereitstellen

- Serverseitigen mehrseitigen Wizard aus dem Use-Case-Katalog erzeugen.
- Problem, Prozess, Nutzung, Daten, Nutzen, Metrik, Risiken und offene Punkte narrativ erfassen.
- Geeignete bestehende Hilfetexte und fachliche Eingabehinweise wiederverwenden, ohne den aktuellen Intake-Schreibpfad zu kopieren.
- Native semantische `textarea`-Elemente mit sichtbaren Labels und ohne Custom-JS-Eingabesteuerung verwenden.
- Reine Navigation darf keine Revision verändern; veraltete Schreibvorgänge werden getestet.
- Abschluss erzeugt ausschließlich eine abgeschlossene Capture Session.

**Ergebnis:** Persistente, wiederaufnehmbare und `WIN + H`-kompatible Use-Case-Erfassung.

## AP 7: Einstiegspunkte und Übersicht „Meine Erfassungen“ integrieren

- Value-Stream- und Use-Case-Listen um eindeutige Startaktionen ergänzen.
- Eigene offene Sessions mit passenden Fortsetzungsaktionen sichtbar machen.
- Kleine Übersicht für alle eigenen Sessions bereitstellen.
- Mehrere parallele Entwürfe derselben Art eindeutig unterscheidbar darstellen.
- Art, Arbeitsbezeichnung, Status, Fortschritt, letzte Änderung, Ablauf und nächste Aktion anzeigen.
- Keine fremden Sessions auflisten oder über direkte URLs zugänglich machen.
- UI vollständig nach `DESIGN.md`, responsiv, tastaturbedienbar und ohne JavaScript-Zwang umsetzen.

**Ergebnis:** Klarer Einstieg und belastbare Wiederaufnahme ohne neue globale Workflow-Navigation.

## AP 8: Retention, Ablauf und physische Bereinigung umsetzen

- Ablaufdatum bei Anlage und jeder gültigen Entwurfsänderung auf 30 Tage nach letzter Aktivität setzen.
- Abgelaufene Sessions kontrolliert in den Zustand `expired` überführen und sperren.
- Verwerfen als explizite irreversible Nutzeraktion umsetzen.
- Idempotentes Management Command zur physischen Bereinigung abgelaufener und verworfener Sessions nach dokumentierter Karenz bereitstellen.
- Abgeschlossene Sessions in Block 3 erhalten, aber die verpflichtende Folgeregel für ihre Rohantwort-Retention in Block 4 dokumentieren.
- Keine allgemeine unternehmensweite Retention-Engine oder neue Jobplattform bauen.

**Ergebnis:** Getestetes, schlankes Retention- und Löschverhalten entsprechend #117.

## AP 9: Aktive Erfassungszeit und Datenschutz-Härtung vorbereiten

- Aktive Eingabezeit, Anzahl erfolgreicher Speicherungen und Abschlusszeitpunkt zweckgebunden erfassen.
- Kalenderdauer und aktive Eingabezeit getrennt halten.
- Progressive clientseitige Zeitmessung nur als Ergänzung verwenden; der gesamte Wizard bleibt ohne JavaScript funktionsfähig.
- Eingabezeit serverseitig plausibilisieren und pro Request begrenzen.
- Capture-Antworten, Prompts und vollständige Formdaten aus Standardlogs und Fehlermeldungen fernhalten.
- Keine Klickpfade, Tastatureingaben oder detaillierte Nutzertelemetrie speichern.

**Ergebnis:** Kleine Messgrundlage für Block 9 ohne Analytics-Infrastruktur.

## AP 10: Regression, Real-DEMO-Rückwärtsprobe und Abschlussnachweis absichern

Mindestens testen:

- beide Capture-Arten und mehrere parallele Entwürfe je Nutzer,
- Teil- und Zwischenspeicherung sowie Wiederaufnahme in neuer Anmeldung beziehungsweise anderem Browser,
- eingefrorene Fortsetzung einer weiterhin unterstützten alten Katalogversion,
- kontrollierte Blockierung einer nicht mehr unterstützten Katalogversion,
- Pflichtfeldprüfung und unveränderlicher Abschluss,
- Eigentümer-, Rollen- und direkte UUID-Zugriffsprüfung,
- unbekannte Frage- und Schemaversionen,
- veralteter POST als Revisionskonflikt,
- konfliktfreie reine Vor-/Zurück-Navigation,
- native semantische Textfelder ohne Custom-JS-Eingabesteuerung als `WIN + H`-Voraussetzung,
- Verwerfen, Ablauf und physische Bereinigung,
- keine reguläre Fachobjektanlage und unverändertes Verhalten des bestehenden Intake,
- keine Änderung von Gates, Rollen, Reviews oder Lifecycle-Zuständen,
- keine Rohantworten in Standardlogs,
- Katalog-Zielpfade gegen den Blueprint-Vertrag,
- konkrete `[Real-DEMO]`-Rückwärtsprobe: Die Value-Stream- und Use-Case-Kataloge decken alle für das Referenz-Blueprint benötigten narrativen Informationsbereiche ab, ohne rote Zustände oder systemverwaltete Felder zu erfassen,
- vollständige bestehende repo-weite CI,
- manuelle Browserabnahme auf Desktop und Mobile.

**Ergebnis:** `docs/accelerator/BLOCK_3_COMPLETION.md` mit Nachweis zu sämtlichen Abnahmekriterien aus Issue #119.

## Zuordnung zu den Abnahmekriterien aus Issue #119

| Abnahmekriterium | Arbeitspakete |
|---|---|
| Gap-Analyse dokumentiert | AP 1 |
| Value-Stream- und Use-Case-Sessions vollständig bedienbar | AP 3 bis AP 7, AP 10 |
| Fragenkataloge versioniert | AP 2, AP 10 |
| Nur berechtigte Benutzer sehen und bearbeiten Sessions | AP 4, AP 7, AP 10 |
| Keine regulären Fachobjekte verändert | AP 3 bis AP 6, AP 10 |
| `WIN + H` über Standard-Textfelder nutzbar | AP 5, AP 6, AP 10 |
| Retention und Löschung getestet | AP 8, AP 10 |
| Lösung bleibt schlank und zweckgebunden | alle APs |
