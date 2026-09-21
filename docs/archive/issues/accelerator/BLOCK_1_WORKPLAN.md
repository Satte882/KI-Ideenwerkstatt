# Accelerator Block 1: Arbeitsplan

**Issue:** #117  
**Übergeordneter Plan:** #116  
**Status:** verbindlicher Umsetzungsplan  
**Gültigkeit:** Dieser Arbeitsplan wird in einem eigenen Pull Request verankert. Inhaltliche Änderungen erfolgen ausschließlich als sichtbarer Diff in einem späteren Pull Request mit Begründung.

## Ziel

Block 1 schafft die repo-spezifische fachliche und technische Grundlage für die Accelerator-Blöcke #118 bis #125. Er baut noch keine Capture Session, keine LLM-Extraktion und keine Vorschlagsübernahme. Bestehende Rollen, Gates, Validierungen, Historisierung und Auditmechanismen bleiben maßgeblich.

## Arbeitsregel

- Issue #116 wird nicht verändert.
- Vor technischen Änderungen wird der aktuelle `main`-Stand geprüft.
- Vorhandene Forms, Services, Snapshot-, Staleness- und Historisierungsmechanismen werden wiederverwendet.
- Es entsteht keine generische Provider-, Mapping-, Policy-, Billing- oder Workflow-Plattform.
- Die Datei dient als Scope- und Entscheidungsgrundlage, nicht als Fortschrittstracker. Der Fortschritt wird in Issue #117 geführt.

## Arbeitspakete

### AP 1: Gap-Analyse und bestehende Bausteine verifizieren

- `ki_radar/core/`, `ki_radar/use_cases/`, `ki_radar/architecture/`, `ki_radar/governance/` und `ki_radar/delivery/` gegen den aktuellen `main`-Stand prüfen.
- Bestehende Forms, Domain Services, Historisierung, Quellen-Snapshots, Staleness-Prüfungen, Logging- und OpenRouter-Pfade dokumentieren.
- Veraltete oder widersprüchliche Dokumente identifizieren.
- Abweichungen von den Annahmen aus #117 begründen.

**Ergebnis:** dokumentierte, repository-belegte Gap-Analyse.

### AP 2: Ziel-, Mess- und Abnahmegrenze festlegen

- Den messbaren Endzustand als strukturierten, prüfbaren Entwurf definieren.
- Start-, End-, Warte-, Navigations-, Prüf- und Korrekturzeiten trennen.
- Vergleichsbedingungen für manuelle, Blueprint- und Accelerator-Durchläufe festlegen.
- Rollen der Durchführenden und Mindestumfang der späteren Abschlussmessung definieren, ohne Ergebnisse vorwegzunehmen.
- Ein kleines protokollierbares Messereignis-Format festlegen, ohne Datenbankmodell oder Analytics-Plattform.
- Jedes Abnahmekriterium aus #117 genau einem Artefakt oder Abschnitt zuordnen.

**Ergebnis:** eindeutige Messdefinition und 1:1-Traceability zu #117.

### AP 3: Kanonisches Feld-, Quellen- und Ampelmapping definieren

- Relevante Domänenobjekte und Felder des Golden Path explizit erfassen.
- Führende Quelle, zulässige Ableitung, maßgebliche Form oder Service, Snapshot-Verhalten und Folgen späterer Änderungen dokumentieren.
- Fachfelder in Grün, Gelb und Rot klassifizieren.
- Systemverwaltete IDs, Versionen, Zeitstempel und Historienattribute separat behandeln.
- Scope-In und Scope-Out wegen ihrer fachlichen Abgrenzungswirkung mindestens als Gelb behandeln.

**Ergebnis:** repo-spezifisches, nachvollziehbares Feld- und Quellenmapping.

### AP 4: Provider-, Datenfluss-, Logging- und Retention-Regeln festlegen

- Den vorhandenen OpenRouter-Pfad als Ausgangspunkt verwenden.
- Zulässige Datenübertragung, ausdrückliche Benutzeraktion und fachliche Entscheidungsgrenzen dokumentieren.
- Vertrauliche Inhalte, Prompts und Rohantworten aus Standardlogs ausschließen.
- Zulässige technische Nutzungsmetadaten definieren.
- Retention-Regeln für flüchtige Antworten, spätere Capture Sessions, strukturierte Vorschläge, Auditdaten und technische Metadaten festlegen.
- Kein neues Nutzungs- oder Billing-Modell in Block 1 einführen.

**Ergebnis:** verbindliche Betriebs- und Datenschutzgrenzen für spätere LLM-Blöcke.

### AP 5: Gemeinsame Accelerator-LLM-Konfiguration implementieren

- Vorhandene Dateien und Namenskonventionen in `ki_radar/core/` prüfen und Doppelstrukturen vermeiden.
- Eine kleine gemeinsame Policy beziehungsweise Konfigurationsschicht an geeigneter Stelle anlegen.
- Neue Accelerator-spezifische Settings konsequent mit `ACCELERATOR_LLM_*` benennen.
- Timeout, Eingabegröße, Ausgabelimit und konservative Request-Grenzen konfigurieren.
- Settings strikt validieren; nichtnumerische, negative und widersprüchliche Werte müssen verständlich fehlschlagen.
- Keine Provider-Orchestrierung, Modellautomatik oder generische AI-Gateway-Schicht bauen.

**Ergebnis:** kleine, validierte und wiederverwendbare Konfiguration für #120, #123 und #124.

### AP 6: Bestehenden OpenRouter-Copilot kontrolliert härten

- Den bestehenden Copilot auf gemeinsame Limits und Fehlerklassen umstellen.
- Fehlenden API-Key, ungültige Konfiguration, zu große Eingabe, Rate Limit, Timeout, Provider-Ausfall, Providerfehler, ungültiges Antwortformat und leere Antwort unterscheiden.
- Genau einen Netzwerkaufruf je Benutzeraktion zulassen; keine automatische Retry-Schleife.
- Bei Fehlern keine fachlichen Änderungen erzeugen.
- Bereinigte technische Metadaten protokollieren, ohne Prompt, Rohantwort oder vollständige Fachdaten zu loggen.

**Ergebnis:** gehärteter bestehender LLM-Pfad ohne neue Endnutzerfunktion.

### AP 7: Versehentliche Doppelaufrufe im bestehenden Copilot verhindern

- Den aktuellen Copilot-Button und das zugehörige Template prüfen.
- Nach dem Absenden den Button clientseitig deaktivieren und einen eindeutigen Bearbeitungszustand anzeigen.
- Der Schutz ist nur eine UX-Leitplanke und ersetzt keine serverseitige Quota oder Idempotenz in späteren Blöcken.
- Barrierefreiheit und Verhalten bei fehlendem JavaScript erhalten.

**Ergebnis:** günstiger Doppelklick-Schutz ohne Datenmodell.

### AP 8: Accelerator-Gap-Analyse-Vorlage bereitstellen

- Unter `docs/accelerator/` eine kleine wiederverwendbare Vorlage für die verpflichtende Gap-Analyse der Blöcke 2 bis 9 anlegen.
- Mindestfragen, belegte Repository-Funde, unbestätigte Annahmen, Abweichungen, minimale Lösung, Risiken und Validierung standardisieren.
- Die Vorlage bleibt Checkliste und wird nicht zu einem Prozess- oder Dokumentgenerator ausgebaut.

**Ergebnis:** konsistentes Gap-Analyse-Format für #118 bis #125.

### AP 9: Dokumentation konsolidieren und alte Planstände einordnen

- `docs/accelerator/` als Ablageort der Accelerator-Arbeitspakete etablieren.
- Die Foundation-Dokumentation für #117 dort anlegen.
- `docs/AI_ACCELERATION_PLAN.md` als historischen, durch #116 abgelösten Planungsstand kennzeichnen, ohne ihn still umzuschreiben oder zu löschen.
- Relevante Verweise in Datenfluss-, Sicherheits- und gegebenenfalls Übersichts-Dokumenten aktualisieren.
- Issue #116 unverändert lassen.

**Ergebnis:** widerspruchsfreie, auffindbare und versionierte Dokumentation.

### AP 10: Tests, Qualitätsprüfung und Abschlussnachweis

- Tests für Settings-Parsing und Fehlkonfiguration ergänzen.
- Provider- und Netzwerkfehler, fehlenden API-Key, Eingabegrenze, Ausgabegrenze, HTTP 429, Timeout, ungültiges JSON, leere Antwort und fehlende Retries testen.
- Sicherstellen, dass keine fachlichen Änderungen und keine vertraulichen Logeinträge entstehen.
- Doppelklick-Schutz und bestehende Berechtigung des Copiloten abdecken.
- Relevante fokussierte Tests sowie die vollständige CI ausführen.
- Abnahmekriterien aus #117 gegen die Traceability-Tabelle prüfen und den Abschluss in Issue #117 dokumentieren.

**Ergebnis:** nachvollziehbar validierter Block 1 mit grünem CI-Stand.

## Nicht-Ziele

- keine Änderung von Issue #116,
- keine Capture Session,
- kein Fragenkatalog,
- kein Blueprint-Import,
- keine LLM-Extraktion,
- keine Vorschlagsübernahme,
- keine neue fachliche Objektanlage,
- keine automatische Entscheidung, Validierung, Bestätigung oder Freigabe,
- kein globaler Übernahme-Button,
- keine Änderung übergebener Delivery Packages,
- keine generische Provider-, Mapping-, Quota-, Billing- oder Observability-Plattform.

## Pull-Request-Strategie

1. Dieser Arbeitsplan wird allein in einem eigenen Pull Request verankert.
2. Die Umsetzung erfolgt anschließend auf einem separaten Branch und in einem separaten Pull Request.
3. Inhaltliche Änderungen dieses Arbeitsplans erfolgen ausschließlich in einem weiteren Pull Request mit expliziter Begründung.
4. Die Checkliste in Issue #117 verwendet exakt die Arbeitspaket-Titel aus diesem Dokument.
