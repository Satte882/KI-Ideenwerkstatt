# Accelerator Block 3: Gap-Analyse und Wiederverwendungsgrenzen

**Issue:** #119  
**Übergeordneter Plan:** #116  
**Arbeitsplan:** `docs/accelerator/BLOCK_3_WORKPLAN.md`  
**Repository-Stand:** `26e75bd7589dfc2b04bda0c98df5127152d1b731`  
**Zweck:** Verbindliche Gap-Analyse vor der technischen Umsetzung von Block 3

## 1. Ergebnis in einem Satz

Der aktuelle Repository-Stand besitzt geeignete serverseitige Wizard-, Form-, Berechtigungs-, Navigations- und Validierungsmuster, aber keine persistente, eigentümergebundene und wiederaufnehmbare Capture-Schicht. Block 3 benötigt deshalb eine kleine eigenständige Accelerator-App mit genau einem zweckgebundenen Session-Modell; die vorhandene Intake-Speicherung und deren direkte Use-Case-Anlage dürfen nicht übernommen werden.

## 2. Autoritative Quellen und Reihenfolge

Für Block 3 gelten in dieser Reihenfolge:

1. Issue #116 als unveränderter Accelerator-Gesamtplan,
2. Issue #119 als Arbeitsauftrag für Block 3,
3. `docs/accelerator/BLOCK_1_FOUNDATION.md`,
4. `docs/accelerator/BLOCK_2_BLUEPRINT_FORMAT.md` und der maschinenlesbare Blueprint-Vertrag,
5. `docs/accelerator/BLOCK_3_WORKPLAN.md`,
6. `AGENTS.md` und `DESIGN.md` für Repository- und UI-Regeln.

`docs/AI_ACCELERATION_PLAN.md` verweist ausdrücklich auf diese Accelerator-Struktur. Die ältere Produkt-Roadmap begründet keinen parallelen oder abweichenden Block-3-Scope. Issue #116 wird im Rahmen von Block 3 weder editiert noch geschlossen.

## 3. Repository-Befund

### 3.1 Bestehender Use-Case-Intake

Relevante Dateien:

- `ki_radar/use_cases/intake.py`
- `ki_radar/use_cases/intake_views.py`
- `ki_radar/use_cases/urls.py`
- `templates/use_cases/intake_wizard.html`

Der bestehende Intake besitzt bereits:

- sechs fachlich gegliederte Schritte,
- serverseitige Django-Forms,
- sichtbare Labels und Hilfetexte,
- native `Textarea`-Widgets,
- deutsche Dezimalwertverarbeitung,
- Pflichtfeld-, Enum-, Prozent- und Metrikkonsistenzprüfung,
- Fortschrittsanzeige sowie Vor-/Weiter-Navigation,
- eine Abschlussprüfung vor der Speicherung.

Nicht geeignet für Block 3 sind:

- Speicherung unter dem Browser-Session-Schlüssel `use_case_intake`,
- Bindung an die kurze Django-Session-Laufzeit,
- fehlende persistente Ownership und Retention,
- fehlende Katalog- und Schemaversion am gespeicherten Entwurf,
- direkte Erzeugung eines regulären `UseCase`,
- Setzung von `decision_status=ready` beim Abschluss,
- Kopplung an genau einen Use-Case-Pfad.

**Entscheidung:** Wiederverwendet werden Darstellungs-, Form-, Hilfetext- und Wizard-Muster. Nicht wiederverwendet werden Session-Speicherung, `_build_use_case()`, `_persist_optional_origin()` und die finale Objektanlage.

### 3.2 Architektur- und Use-Case-Listen

Relevante Dateien:

- `ki_radar/architecture/views.py`
- `ki_radar/architecture/urls.py`
- `templates/architecture/value_stream_list.html`
- `ki_radar/use_cases/views.py`
- `ki_radar/use_cases/urls.py`
- `templates/use_cases/list.html`

Beide Listen besitzen bereits:

- einen serverseitigen Listeneinstieg,
- einen im View ermittelten `can_create`-Kontext,
- reale Links und klassische POST-/GET-Abläufe,
- bestehende Design- und Navigationsmuster.

**Entscheidung:** Block 3 ergänzt dort nur eindeutige Start- und Fortsetzungsaktionen. Bestehende direkte Anlagepfade bleiben erhalten und werden nicht umgedeutet.

### 3.3 Berechtigungen

Relevante Dateien:

- `ki_radar/architecture/permissions.py`
- `ki_radar/use_cases/permissions.py`
- `ki_radar/accounts/permissions.py`

Aktueller Stand:

- `can_manage_architecture(user)` erlaubt die Anlage von Architekturinhalt für Business Owner.
- `can_create_use_case(user)` erlaubt die Use-Case-Anlage für Business Owner.
- Bestehende Views reagieren bei fehlender Berechtigung mit `PermissionDenied`.

**Entscheidung:**

- Value-Stream-Capture verwendet `can_manage_architecture`.
- Use-Case-Capture verwendet `can_create_use_case`.
- Der Zugriff auf eine konkrete Session wird zusätzlich immer über `owner=request.user` gefiltert.
- Eine erratene oder manipulierte UUID liefert keinen Zugriff auf fremde Inhalte.
- Block 3 führt keine neue Benutzergruppe, Stellvertretung oder gemeinsame Bearbeitung ein.

### 3.4 Zeitstempel, technische Jobs und Historisierung

Relevante Dateien:

- `ki_radar/core/models.py`
- `ki_radar/use_cases/models.py`
- `ki_radar/architecture/models.py`

Vorhanden sind:

- `TimeStampedModel` mit `created_at` und `updated_at`,
- `SystemJobRun` für technische Hintergrundläufe,
- `django-simple-history` am regulären `UseCase`,
- eigenständige unveränderliche fachliche Entscheidungs- und Validierungsdatensätze.

**Entscheidung:**

- `CaptureSession` erbt von `TimeStampedModel`.
- `SystemJobRun` wird nicht als Capture-, Nutzungs- oder Retention-Modell zweckentfremdet.
- Vollständige Capture-Rohantworten erhalten keine `django-simple-history`, da eine Historientabelle die spätere Löschung faktisch umgehen würde.
- Für Block 3 reichen Status, Revision, Besitzer, Katalog-/Schemaversion und Zeitstempel.
- Auditierbare Vorschläge und Übernahmen entstehen erst in den dafür vorgesehenen Folgeblöcken.

### 3.5 Blueprint-Vertrag und Feldgrenze

Relevante Dateien:

- `ki_radar/core/scenario_blueprints/contract.v1.json`
- `ki_radar/core/scenario_blueprints/real_demo.v1.json`
- `ki_radar/core/scenario_blueprint.py`
- `ki_radar/core/scenario_blueprint_validation.py`
- `docs/accelerator/BLOCK_2_BLUEPRINT_FORMAT.md`

Block 2 definiert bereits:

- erlaubte Objekte und Felder,
- Pflichtfelder und Kardinalitäten,
- zulässige Enums und Entwurfszustände,
- verbotene Entscheidungs-, Validierungs-, Governance- und Lifecycle-Objekte,
- den `[Real-DEMO]`-Referenzgraphen.

**Entscheidung:**

- Jede Capture-Frage erhält deklarierte mögliche Blueprint-Zielpfade.
- Diese Pfade werden automatisiert gegen den bestehenden Vertrag geprüft.
- Capture-Fragen bilden keine zweite Kopie aller Zielformulare.
- Narrative Antworten bleiben zunächst Fragenantworten; Block 3 leitet daraus keine Zielfeldwerte ab.
- Typ-, Enum-, Dezimal-, Referenz- und vollständige Domainvalidierung der extrahierten Werte bleibt Block 4 vorbehalten.
- Rote Zustände und systemverwaltete Felder werden nicht als Capture-Ziele angeboten.

### 3.6 Foundation-Regeln aus Block 1

`docs/accelerator/BLOCK_1_FOUNDATION.md` legt bereits fest:

- reguläre Domänenobjekte bleiben fachlich führend,
- Capture ist Arbeits- und Herkunftsschicht,
- Scope-In und Scope-Out sind getrennt zu behandeln,
- fehlende oder mehrdeutige Angaben bleiben Lücken beziehungsweise Konflikte,
- inaktive Capture Sessions sollen nach 30 Tagen ablaufen,
- Rohinhalte gehören nicht in Standardlogs,
- später übernommene Werte müssen reguläre Forms oder Domain Services verwenden.

**Entscheidung:** Block 3 implementiert nur Erfassung, Persistenz, Ownership, Lifecycle, Ablauf und kleine Messvorbereitung. Es entstehen keine Vorschläge, keine Übernahmen und keine Fachobjektänderungen.

## 4. Zu schließende funktionale Gaps

| Gap | Repository-Befund | Block-3-Lösung |
|---|---|---|
| Browserübergreifende Wiederaufnahme | Bestehender Intake nutzt Django-Session | Persistentes `CaptureSession`-Modell |
| Eigentümergebundener Zugriff | Session-Daten besitzen keinen eigenen Datensatzbesitzer | FK auf Benutzer plus owner-gefilterte Abfragen |
| Zwei Capture-Arten | Intake ist ausschließlich Use-Case-bezogen | Exakt `value_stream` und `use_case` |
| Versionierter Fragenstand | Kein persistierter Katalogstand | Katalog- und Schemaversion je Session |
| Alte laufende Entwürfe | Keine Versionswechselregel | Fortsetzung mit eingefrorener unterstützter Version; klare Sperre bei nicht mehr unterstützter Version |
| Mehrere parallele Entwürfe | Ein Session-Schlüssel überschreibt den laufenden Intake | Mehrere Sessions je Nutzer und Art ohne künstliche Eindeutigkeitsgrenze |
| Konfliktschutz | Letzte Session-Schreibung gewinnt | Revisionsprüfung ausschließlich bei POST-Schreibvorgängen |
| Lifecycle | Kein persistierter Entwurfsstatus | `draft`, `completed`, `discarded`, `expired` |
| Retention | Browser-Session endet technisch, aber ohne fachliche Regel | 30-Tage-Ablauf plus kontrollierte Bereinigung |
| Zeitmessung | Keine getrennte aktive Erfassungszeit | Wenige zweckgebundene Messfelder, keine Analytics-Plattform |
| Real-DEMO-Abdeckung | Blueprint vorhanden, Capture-Katalog noch nicht | Konkrete narrative Rückwärtsprobe in AP 10 |

## 5. Verbindliche Daten- und Lifecycle-Grenze

### 5.1 CaptureSession als einziges neues persistentes Fachhilfsobjekt

Vorgesehene Datenkategorien:

- UUID,
- Besitzer,
- Capture-Art,
- Arbeitsbezeichnung,
- Fragenkatalog- und Schemaversion,
- Antworten nach stabiler Frage-ID,
- Bearbeitungsstatus,
- Revision und Fortschritt,
- Erstellungs-, Änderungs-, Abschluss-, Verwerfungs- und Ablaufzeitpunkt,
- aktive Eingabezeit und Anzahl erfolgreicher Speicherungen.

Nicht gespeichert werden in Block 3:

- LLM-Prompts oder Providerantworten,
- extrahierte Zielfeldvorschläge,
- Zielobjekt-IDs,
- Freigaben, Validierungen oder Entscheidungen,
- Audio oder Transkripte,
- Dateien oder Connector-Inhalte,
- vollständige Änderungsverläufe jeder Rohantwort.

### 5.2 Zustandsübergänge

Zulässig:

- `draft → completed`
- `draft → discarded`
- `draft → expired`

Nicht zulässig:

- Rückkehr eines abgeschlossenen, verworfenen oder abgelaufenen Datensatzes in `draft`,
- Änderung von Antworten nach Abschluss,
- stille Migration auf einen neuen Fragenkatalog,
- automatische Anlage regulärer Fachobjekte.

### 5.3 Optimistic Locking

- Die Revision wird nur nach erfolgreicher Änderung gespeichert und erhöht.
- GET-Aufrufe, Vor-/Zurück-Navigation und erneutes Öffnen verändern keine Revision.
- Ein POST mit veralteter Revision überschreibt keinen neueren Stand.
- Ein Konflikt wird verständlich angezeigt; Block 3 baut keine Merge-Engine.

## 6. Fragenkatalog-Grenze

### 6.1 Value Stream

Narrativ abzudecken sind mindestens:

- Arbeitsbezeichnung und fachlicher Kontext,
- Beschreibung und strategisches Ziel,
- Auslöser und Ergebnis,
- Scope-In,
- Scope-Out,
- Stakeholder und Leitplanken,
- Phasen, Reihenfolge, Aktivitäten und Ergebnisse,
- Rollen, Systeme, Dokumente, Pain Points und vorhandene Kennzahlen.

### 6.2 Use Case

Narrativ abzudecken sind mindestens:

- Titel, Problem und Auswirkungen,
- betroffener Prozess und heutiger Ablauf,
- Zielnutzer und zulässiger Einsatzzweck,
- Systeme, Datenquellen und Schnittstellen,
- erwarteter Nutzen,
- Erfolgsmetrik mit Baseline, Ziel, Richtung, Einheit und Messmethode,
- bekannter Lösungsrahmen,
- menschliche Aufsicht, Risiken, Annahmen und offene Punkte.

### 6.3 Eingabeelemente

- Lange Antworten verwenden native semantische `<textarea>`-Elemente.
- Labels bleiben sichtbar; Placeholder ersetzen keine Feldbezeichnung.
- Es gibt keine Custom-JavaScript-Eingabesteuerung.
- Damit bleiben Betriebssystem-Diktatfunktionen wie Windows `WIN + H` ohne Anwendungsintegration nutzbar.

## 7. UI- und Navigationsgrenze

Nach `DESIGN.md` gelten:

- echte Links und serverseitige Navigation,
- sichtbare Fokuszustände,
- semantische Tokens statt neuer Direktfarben,
- klare Primär- und Nebenaktionen,
- responsive Darstellung,
- Tastaturbedienbarkeit und sichtbare Labels,
- kein JavaScript-Zwang.

Block 3 ergänzt:

- Startaktionen in den bestehenden Value-Stream- und Use-Case-Listen,
- Fortsetzungsaktionen für eigene Entwürfe,
- eine kleine Übersicht „Meine Erfassungen“,
- Wizard-Seiten für genau zwei Kataloge.

Block 3 verändert nicht:

- die bestehende Hauptnavigation der Journey,
- vorhandene direkte Create- und Edit-URLs,
- Status- oder Gate-Darstellungen regulärer Fachobjekte.

## 8. Retention- und Datenschutzgrenze

### 8.1 Entwürfe

- Ablauf 30 Tage nach letzter erfolgreicher fachlicher Änderung.
- Reine Navigation verlängert die Frist nicht.
- Abgelaufene Entwürfe werden gesperrt und nach dokumentierter Karenz physisch gelöscht.

### 8.2 Verworfene Sessions

- Verwerfen ist eine ausdrückliche irreversible Aktion.
- Verworfene Sessions werden nach dokumentierter Karenz physisch gelöscht.

### 8.3 Abgeschlossene Sessions

- Sie bleiben in Block 3 erhalten, weil Block 4 eine stabile Analysequelle benötigt.
- Dies ist keine dauerhafte unbegrenzte Retention-Entscheidung.
- Spätestens Block 4 muss für abgeschlossene Rohantworten eine fachlich begründete Lösch- oder Reduktionsregel definieren und testen.

### 8.4 Logging

Nicht in Standardlogs oder Fehlermeldungen:

- vollständige Antworten,
- vollständige POST-Daten,
- sensible Freitextauszüge,
- Session-Cookies oder Tokens.

Zulässig sind bereinigte technische Angaben wie Session-ID, Aktion, Status, Dauer und Fehlerklasse, soweit erforderlich.

## 9. Zeitmessungsgrenze

Für die spätere Abschlussmessung werden nur vorbereitet:

- kumulierte aktive Eingabezeit,
- Anzahl erfolgreicher Speicherungen,
- Erstellungs- und Abschlusszeitpunkt.

Nicht umgesetzt werden:

- Klickstream,
- Tasten- oder Diktatprotokollierung,
- Nutzertracking,
- BI-Dashboard,
- allgemeine Telemetrieplattform.

Kalenderdauer darf nicht als aktive Bearbeitungszeit ausgegeben werden. Eine progressive clientseitige Messhilfe ist zulässig, wenn der gesamte Ablauf ohne JavaScript funktioniert und serverseitige Plausibilitätsgrenzen gelten.

## 10. Risiken und Schutzmaßnahmen

| Risiko | Schutzmaßnahme |
|---|---|
| Capture wird zweite fachlich führende Quelle | Keine Fachobjektanlage, klare App- und Modellgrenze |
| Alte Antworten werden durch neuen Katalog umgedeutet | Eingefrorene Katalogversion je Session |
| Datenverlust durch zwei Tabs | Revisionsprüfung bei Schreibvorgängen |
| Falsche Konflikte beim Navigieren | GET und reine Navigation verändern keine Revision |
| Unbegrenzte Zahl sensibler Rohtexte | 30-Tage-Ablauf für Entwürfe, physische Bereinigung, Folgeregel für abgeschlossene Sessions |
| Versehentlicher Fremdzugriff | owner-gefilterte Abfragen zusätzlich zur Rollenberechtigung |
| Abweichende Feldnamen zu Block 2 | Zielpfadprüfung gegen Blueprint-Vertrag |
| Beschleunigungskatalog deckt Referenzfall nicht ab | `[Real-DEMO]`-Rückwärtsprobe |
| Spracherfassung wird durch UI blockiert | Native Textareas ohne Custom-JS-Eingabe |
| Bestehende Gates werden umgangen | Keine regulären Objekt- oder Statusänderungen in Block 3 |

## 11. Minimaler technischer Zuschnitt

Vorgesehen:

- kleine App `ki_radar.accelerator`,
- ein `CaptureSession`-Modell,
- zwei codebasierte Kataloge,
- ein expliziter Lifecycle-/Speicherservice,
- wenige serverseitige Views und Templates,
- ein idempotentes Retention-Management-Command,
- fokussierte Tests.

Ausgeschlossen:

- allgemeiner Form Builder,
- beliebige Katalogverwaltung in der Datenbank,
- generischer Workflow- oder Case-Management-Layer,
- Kollaborations- oder Merge-Plattform,
- LLM-, Audio-, Datei- oder Connector-Verarbeitung,
- neue Rollen- oder Identity-Logik,
- umfassendes Analytics-System.

## 12. Abnahmemapping für Issue #119

| Abnahmekriterium | Repo-Befund und geplanter Nachweis |
|---|---|
| Gap-Analyse dokumentiert | Dieses Dokument und AP-1-PR |
| Beide Session-Arten vollständig bedienbar | AP 3 bis AP 7, Regression in AP 10 |
| Fragenkataloge versioniert | AP 2 und AP 10 |
| Nur berechtigte Benutzer sehen und bearbeiten Sessions | Bestehende Berechtigungen plus Ownership in AP 4 und AP 7 |
| Keine regulären Fachobjekte verändert | Explizite Modell-/Servicegrenze und Negativtests in AP 10 |
| `WIN + H` nutzbar | Native Textareas in AP 5 und AP 6, Strukturtest in AP 10 |
| Retention und Löschung getestet | AP 8 und AP 10 |
| Lösung bleibt schlank und zweckgebunden | Ein Modell, zwei Kataloge, explizite Services; keine Plattformkomponenten |

## 13. Abschlussentscheidung für AP 1

Die technische Umsetzung kann ohne weitere fachliche Vorentscheidung mit AP 2 beginnen. Die maßgeblichen Grenzen sind durch #116, #117, #118, #119 und den festgeschriebenen Block-3-Arbeitsplan ausreichend bestimmt.
