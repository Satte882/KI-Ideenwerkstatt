# Accelerator Block 5 – Gap-Analyse

**Issue:** #121  
**Übergeordneter Plan:** #116, unverändert  
**Arbeitsplan:** `docs/accelerator/BLOCK_5_WORKPLAN.md`  
**Analysierter Stand:** `main` auf `679bbf9050d28bf2cccb411acffe369c83655fba`  
**Arbeitspaket:** AP 1 – Gap-Analyse, Feldfreigabe und bestehende Schreibpfade

## 1. Ergebnis

Block 5 kann als kleine, explizite Erweiterung des vorhandenen Accelerator-Pfads umgesetzt werden. Die wesentlichen Bausteine existieren bereits, sind aber noch nicht miteinander verbunden:

- Block 4 speichert erfolgreiche Analyseläufe und typisierte Feldvorschläge.
- `CaptureFieldSuggestion.target_object_id` ist nullable und wird im aktuellen Extraktionspfad nicht als belastbare Zielbindung befüllt.
- `CaptureSession` ist weder an einen `ValueStream` noch an einen `UseCase` gebunden.
- Es fehlen Feld-Ausgangssnapshot, Kandidatenstatus, atomare Reservierung, Adoption-Audit und mutierende Review-Aktionen.
- Die regulären Bearbeitungsrechte und Forms sind vorhanden und werden unverändert wiederverwendet.
- Die bestehende Capture-Retention löscht Analysen und Vorschläge kaskadierend; ein dauerhafter, datensparsamer Änderungsnachweis muss davon entkoppelt werden.

Es wird keine allgemeine Patch-, Audit-, Workflow- oder Feature-Flag-Plattform benötigt.

## 2. Bestehende verbindliche Bausteine

| Bereich | Bestehender Code | Folgerung für Block 5 |
|---|---|---|
| Value-Stream-Berechtigung | `ki_radar.architecture.permissions.can_edit_value_stream(user, value_stream)` | Die Adoption prüft exakt diese Funktion erneut. Keine parallele Rollenlogik. |
| Use-Case-Berechtigung | `ki_radar.use_cases.permissions.can_edit_use_case(user, use_case)` | Die Adoption prüft exakt diese Funktion erneut. Keine parallele Rollenlogik. |
| Value-Stream-Schreibpfad | `ValueStreamForm`; Update-View speichert die Form und ruft anschließend `_save_focus_actor(...)` auf | Für die grünen Block-5-Felder ist keine Fokusänderung zulässig. Der Adapter verwendet die Formvalidierung, speichert aber ausschließlich das erlaubte Modellfeld. `_save_focus_actor(...)` wird nicht ausgelöst, weil Block 5 keine Fokusfelder ändert. |
| Use-Case-Schreibpfad | `UseCaseForm(instance=..., current_user=...)` | Der Adapter bindet den vollständigen aktuellen Objektzustand plus genau ein geändertes Feld an die Form. Formvalidierung, Modell-`save()` und `django-simple-history` bleiben wirksam. |
| Value-Stream-Modell | `ValueStream` erbt `TimeStampedModel`; `status=archived` kennzeichnet inaktive Ziele | `updated_at` wird als Zusatzsnapshot gespeichert. Archivierte Value Streams sind nicht adoptierbar. |
| Use-Case-Modell | `UseCase` erbt `TimeStampedModel`; `is_archived=True` kennzeichnet inaktive Ziele; `history = HistoricalRecords(...)` | `updated_at` wird als Zusatzsnapshot gespeichert. Archivierte Use Cases sind nicht adoptierbar. Jede erfolgreiche Adoption erzeugt reguläre History. |
| Block-4-Analyse | `CaptureAnalysis` enthält Provider, Modell, Token, Kosten, Prompt- und Schemaversionen | Audit und spätere Messung referenzieren genau einen Analyselauf und kopieren dessen technische Metadaten datensparsam. |
| Block-4-Vorschlag | `CaptureFieldSuggestion` enthält Zieltyp, Zielfeld, Vorschlagswert, Quelle und Unsicherheit | Der Vorschlag bleibt unveränderliche Extraktionsausgabe. Block 5 führt einen getrennten ausführbaren Kandidaten mit Snapshot und Status ein. |
| Retention | `expire_due_capture_sessions()` und `purge_terminal_capture_sessions()` löschen Sessions nach konfigurierbarer Frist und siebentägiger Karenz | Offene Kandidaten hängen kaskadierend an der Session. Der minimale Auditdatensatz darf nicht kaskadierend mitgelöscht werden. |
| Extraktionsvertrag | Block 4 validiert Zielpfade, Feldtypen, Quelle und Unsicherheit serverseitig | Block 5 übernimmt nur die kleinere statische Grün-Registry. Ein extrahierbarer Pfad ist nicht automatisch adoptierbar. |

## 3. Berechtigungsverankerung

Die regulären Bearbeitungs-Views besitzen nur den technischen Decorator `login_required`. Die fachliche Autorisierung erfolgt anschließend über die zentralen Funktionen:

- Value Stream: `can_edit_value_stream(request.user, value_stream)`
- Use Case: `can_edit_use_case(request.user, use_case)`

Block 5 ruft dieselben Funktionen sowohl bei der Zielauswahl als auch unmittelbar vor jeder mutierenden Aktion auf. Ein im Browser angebotener Button ist kein Berechtigungsnachweis. Manipulierte direkte Requests werden serverseitig abgewiesen.

## 4. Verbindliche Feldmatrix

### 4.1 Value Stream

| Zielfeld | Block-1-Klasse | Block-4-Pfad vorhanden | Formfeld | Modelltyp | Block 5 | Begründung / Seiteneffekt |
|---|---|---:|---:|---|---:|---|
| `name` | Grün | Ja | Ja | `CharField` | Ja | Reiner beschreibender Text; reguläre Modellvalidierung und `updated_at`. |
| `description` | Grün | Ja | Ja | `TextField` | Ja | Reiner beschreibender Text. |
| `trigger` | Grün | Ja | Ja | `TextField` | Ja | Reiner beschreibender Text; Pflichtfeld bleibt durch Formvalidierung geschützt. |
| `outcome` | Grün | Ja | Ja | `TextField` | Ja | Reiner beschreibender Text; Pflichtfeld bleibt durch Formvalidierung geschützt. |
| `strategic_objective` | Grün | Ja | Ja | `TextField` | Ja | Reiner beschreibender Text. |
| `stakeholders` | Grün | Ja | Ja | `TextField` | Ja | Freitext, keine Rollenreferenz. |
| `constraints` | Grün | Ja | Ja | `TextField` | Ja | Reiner beschreibender Text. |
| `scope_in` | Gelb | Ja | Ja | `TextField` | Nein | Scope-Abgrenzung verlangt separate fachliche Bestätigung. |
| `scope_out` | Gelb | Ja | Ja | `TextField` | Nein | Scope-Abgrenzung verlangt separate fachliche Bestätigung. |
| `business_unit` | Gelb | Nein als freier Text | Ja | Referenz | Nein | Keine freie Referenzauflösung. |
| `owner` | Gelb | Nein als freier Text | Ja | Referenz | Nein | Rollen- und Berechtigungsfeld. |
| `status` | Rot | Nein | Ja | Enum | Nein | Lifecycle-Feld. |
| IDs, `demo_key`, Zeitstempel, `created_by` | System | Nein | Nein | System | Nein | Anwendung verwaltet diese Werte. |

### 4.2 Use Case

| Zielfeld | Block-1-Klasse | Block-4-Pfad vorhanden | Formfeld | Modelltyp | Block 5 | Begründung / Seiteneffekt |
|---|---|---:|---:|---|---:|---|
| `title` | Grün | Ja | Ja | `CharField` | Ja | Reiner beschreibender Text; History bleibt wirksam. |
| `summary` | Grün | Ja | Ja | `TextField` | Ja | Reiner beschreibender Text. |
| `problem_statement` | Grün | Ja | Ja | `TextField` | Ja | Pflichtfeld; Formvalidierung bleibt wirksam. |
| `affected_process` | Grün | Ja | Ja | `CharField` | Ja | Beschreibender Prozessname, keine Prozessobjekt-Referenz. |
| `target_users` | Grün | Ja | Ja | `TextField` | Ja | Formlabel „Zielgruppe“ wird aus dem gebundenen Formfeld bezogen. |
| `source_systems` | Grün | Ja | Ja | `TextField` | Ja | Beschreibender Text, keine technische Referenzauflösung. |
| `data_sources` | Grün | Ja | Ja | `TextField` | Ja | Beschreibender Text. |
| `interface_description` | Grün | Ja | Ja | `TextField` | Ja | Beschreibender Text. |
| `intended_users` | Grün | Ja | Ja | `TextField` | Ja | Beschreibender Text. |
| `intended_purpose` | Grün | Ja | Ja | `TextField` | Ja | Beschreibender Text. |
| `expected_benefit` | Grün | Ja | Ja | `TextField` | Ja | Pflichtfeld; Formvalidierung bleibt wirksam. |
| `benefit_category` | Grün | Ja | Ja | `CharField` | Ja | Freitext in Version 1, kein Enum. |
| `human_oversight` | Grün | Ja | Ja | `TextField` | Ja | Beschreibender Entwurf; setzt keine Governance-Bestätigung. |
| `support_responsibility` | Grün | Ja | Ja | `TextField` | Ja | Beschreibender Entwurf; setzt keine Rollenreferenz. |
| Provider-/Produkt-/Modellfelder | Nicht Teil der Block-5-MVP-Liste | Teilweise | Ja | Text | Nein | Bewusste kleine Registry; spätere Erweiterung nur per neuer Gap-Analyse. |
| Historische Baseline-/Zieltextfelder | Nicht Teil der Block-5-MVP-Liste | Teilweise | Ja | Text | Nein | Nähe zu Metrik- und Wirkungslogik; in Block 5 ausgeschlossen. |
| Organisation, Owner, Koordinator, technischer Owner | Gelb | Nein als freier Text | Ja | Referenzen | Nein | Keine freie Namensauflösung; Rollenfelder. |
| Priorität, Lösungs-/Hostingtyp, Bewertungsstufen | Gelb/Rot | Teilweise | Ja | Enums | Nein | Keine Enum-Übernahme in Block 5. |
| Metriken, Kosten, Termine | Gelb | Teilweise | Ja | Zahl/Datum | Nein | Block 6 beziehungsweise spätere fachliche Schritte. |
| Review-, Entscheidungs-, Status-, Gate- und Archivfelder | Rot/System | Nein | Teilweise | Steuerung | Nein | Keine Lifecycle- oder Governance-Wirkung. |

## 5. Form- und Speicherstrategie

### 5.1 Warum keine Teil-ModelForm mit nur einem Feld

`ValueStreamForm` und `UseCaseForm` enthalten zusätzliche, teilweise erforderliche Felder und fachliche `clean()`- beziehungsweise `save()`-Logik. Eine dynamisch reduzierte Form würde diese Regeln umgehen oder duplizieren.

Der kleine Adapter baut daher einen vollständigen Form-Payload aus dem aktuellen, gesperrten Objektzustand auf und ersetzt darin ausschließlich das freigegebene Zielfeld. Danach wird die reguläre Form gebunden und vollständig validiert.

### 5.2 Begrenzung der tatsächlichen Änderung

Nach erfolgreicher Formvalidierung wird geprüft, dass sich gegenüber dem gesperrten Ausgangsobjekt ausschließlich das freigegebene Fachfeld sowie dokumentierte technische Felder verändern dürfen.

- Value Stream: erlaubtes Fachfeld und `updated_at`.
- Use Case: erlaubtes Fachfeld, `updated_at` und History-Datensatz.
- Klassifikation, Referenzen, Reviews, Gates, Status, Fokus und Delivery-Daten dürfen sich nicht ändern.

Die Adapter sind explizit pro Zieltyp. Es gibt kein generisches `setattr()` über beliebige Modell- oder Request-Feldnamen.

### 5.3 View-seitige Effekte

- `_save_focus_actor(...)` aus der Value-Stream-Update-View ist an Fokusfelder gekoppelt. Block 5 verändert keine Fokusfelder; der Effekt wird nicht in den Adoption-Pfad übernommen.
- `UseCaseForm.save()` pflegt die Klassifikation über `_classification_payload`. Da der vollständige aktuelle Klassifikationszustand wieder an die Form gebunden wird, bleibt er unverändert. Der Adapter prüft dies ausdrücklich.
- `UseCase.save()` korrigiert Review-Completed-Flags nur, wenn zugehörige Required-Flags deaktiviert werden. Block 5 verändert keine dieser Felder; die bestehende Modelllogik bleibt dennoch regulär aktiv.
- `django-simple-history` wird nicht umgangen.

Es muss für AP 5 kein neuer allgemeiner Domain Service aus den Views extrahiert werden. Benötigt werden zwei kleine, Accelerator-spezifische Form-Adapter, die die vorhandenen Forms als Validierungs- und Speichergrenze verwenden.

## 6. Snapshot- und Konfliktmaßstab

Der Kandidat speichert bei Erzeugung:

- Zieltyp und Ziel-ID,
- Zielfeld,
- kanonischen Ausgangswert und SHA-256-Hash,
- Ziel-`updated_at` als Zusatzinformation,
- Analyse-, Session-, Katalog-, Prompt- und Schemaversionen,
- Erzeugungszeitpunkt.

Vor der Adoption wird das Ziel erneut gesperrt und der aktuelle Wert desselben Feldes kanonisiert. Nur eine Abweichung des Feldwerts erzeugt `field_conflict`. Ein verändertes globales `updated_at` bei identischem Zielfeld wird protokolliert, blockiert aber nicht. Dadurch können unterschiedliche Felder desselben Objekts ohne falschen Konflikt nacheinander übernommen werden.

## 7. Zielbindung und MVP-Grenze

Eine Capture Session darf höchstens genau ein bestehendes Zielobjekt besitzen:

- `capture_type=value_stream`: optional genau ein `target_value_stream`, kein `target_use_case`.
- `capture_type=use_case`: optional genau ein `target_use_case`, kein `target_value_stream`.

Ungebundene Sessions bleiben erfass- und analysierbar, bieten aber keine Adoption. Block 5 erzeugt keine unvollständigen Fachobjekte. Die Bindung an mehrere Ziele ist ausdrücklich kein stiller technischer Mangel, sondern eine dokumentierte MVP-Grenze.

## 8. Retention und Audit

- `FieldAdoptionCandidate` hängt kaskadierend an Analyse beziehungsweise Session und folgt deren konfigurierbarer Retention.
- Ein ausgeführter oder abgelehnter Versuch erzeugt ein separates minimales Audit.
- Das Audit speichert keine vollständigen Capture-Antworten, Prompts, Providerantworten oder Quellausschnitte.
- Nullable Referenzen dürfen bei späterer Session-, Analyse-, Vorschlags-, Ziel- oder Benutzerlöschung verschwinden; unveränderliche ID-, Wert-, Versions- und technische Kosten-Snapshots bleiben erhalten.
- Kosten werden später pro eindeutiger Analyse-ID aggregiert, nicht pro übernommenem Feld mehrfach summiert.

## 9. Abweichungen und Präzisierungen zum Arbeitsplan

Der Arbeitsplan bleibt fachlich gültig. AP 1 präzisiert zwei Punkte:

1. Das Label wird vorrangig aus dem gebundenen Formfeld und nur ersatzweise aus `verbose_name` bezogen. Dies ist erforderlich, weil `UseCaseForm` bewusst fachliche Labels wie „Zielgruppe“ definiert.
2. Es wird kein gemeinsamer allgemeiner Domain Service aus den regulären Update-Views extrahiert. Zwei kleine explizite Form-Adapter genügen und vermeiden eine neue universelle Schreibabstraktion.

## 10. Nicht-Ziele

- keine Änderung von Issue #116,
- keine automatische Neuanlage von Value Streams oder Use Cases,
- keine gelben, roten oder systemverwalteten Felder,
- keine Phasen, Prozessanalysen oder Lösungsoptionen,
- keine Sammelübernahme,
- keine Force-Overwrite- oder Drei-Wege-Merge-Engine,
- keine parallele Berechtigungslogik,
- keine dauerhafte Rohtextduplizierung,
- keine generische Patch-, Audit-, Retention- oder Feature-Flag-Plattform.

## 11. AP-1-Abnahme

- vollständige Grün-Feldmatrix gegen Block 1 und Block 4 dokumentiert,
- reguläre Forms und Berechtigungsfunktionen pro Zieltyp bestätigt,
- Zielaktivität, History, Seiteneffekte und Retention geprüft,
- notwendige technische Erweiterungen klar von bestehenden Bausteinen getrennt,
- keine technische Implementierung in diesem Arbeitspaket,
- Issue #116 unverändert.