# Block 3: Capture-Vertrag und Fragenkataloge Version 1

**Issue:** #119  
**Arbeitspaket:** AP 2  
**Antwortschema:** `1.0`  
**Value-Stream-Katalog:** `1.0`  
**Use-Case-Katalog:** `1.0`

## Zweck

Der Capture-Vertrag beschreibt die persistierbare Form narrativer Antworten, bevor Block 4 daraus
strukturierte Feldvorschläge erzeugt. Er bildet keine zweite fachlich führende Quelle und keine Kopie
der regulären Zielformulare.

## Versionierungsregel

Jede Session speichert beim Anlegen:

- Capture-Art,
- Fragenkatalog-Version,
- Antwortschema-Version.

Eine laufende Session wird immer mit genau dieser gespeicherten Version fortgesetzt. Eine neuere
aktive Katalogversion ändert vorhandene Antworten weder semantisch noch technisch. Solange die alte
Version im Code registriert ist, bleibt sie nutzbar. Ist sie nicht mehr registriert, wird die Session
schreibgeschützt blockiert und mit einer verständlichen Meldung angezeigt. Stille Migrationen oder
Neuinterpretationen sind ausgeschlossen.

## Antwortdokument

Version 1 verwendet ein JSON-Objekt:

- Schlüssel: stabile Frage-ID,
- Wert: Textantwort,
- unbekannte Schlüssel: unzulässig,
- andere Werttypen: unzulässig,
- Texte werden an den Rändern bereinigt,
- die jeweilige Frage definiert eine maximale Länge,
- beim Abschluss müssen alle Pflichtfragen nicht leer beantwortet sein.

Arbeitsbezeichnung, Besitzer, Status, Revision, Zeitmessung und Retention-Metadaten gehören später
zum `CaptureSession`-Modell und nicht in das Antwortdokument.

## Fragenkataloge

Version 1 besitzt genau zwei codebasierte Kataloge:

1. `value_stream`
2. `use_case`

Jede Frage enthält:

- stabile ID,
- Abschnitt,
- sichtbare Bezeichnung,
- Hilfetext,
- Pflichtstatus,
- nativen Eingabetyp,
- maximale Länge,
- narrative Informationsdomäne,
- mögliche Blueprint-Zielpfade.

Die Zielpfade bedeuten keine bereits erfolgte Feldzuordnung. Sie begrenzen nur, welche Felder eine
spätere Extraktion aus der jeweiligen Antwort vorschlagen darf.

## Value-Stream-Katalog

Der Katalog deckt ab:

- Kontext, Beschreibung und strategisches Ziel,
- Auslöser und Ergebnis,
- Scope-In und Scope-Out als getrennte Fragen,
- Stakeholder und Leitplanken,
- Phasen, Reihenfolge, Aktivitäten und Ergebnisse,
- Rollen, Systeme, Dokumente, Probleme und Baselines je Phase,
- Fokusprozess mit Scope, Ablauf, Rollen, Regeln, Übergaben und Kennzahlen,
- mehrere unbewertete Lösungsalternativen,
- offene Fragen und Widersprüche.

Die Lösungsalternativen bleiben Kandidaten. Der Katalog erfasst keine Empfehlung, Auswahl oder
Bewertung.

## Use-Case-Katalog

Der Katalog deckt ab:

- Titel, Problem, Auswirkungen und betroffenen Prozess,
- Nutzer und zulässigen Einsatzzweck,
- Systeme, Datenquellen und Schnittstellen,
- erwarteten Nutzen,
- primäre Metrik mit Baseline, Ziel, Richtung, Einheit und Messmethode,
- bekannten Lösungs-, Produkt-, Modell- und Hosting-Rahmen,
- vorläufige Kosten- und Reifeannahmen,
- menschliche Aufsicht und Support-Verantwortung,
- offene Fragen und Widersprüche.

## Blueprint-Grenze

`ki_radar/accelerator/catalogs.py` liest den vorhandenen Vertrag
`ki_radar/core/scenario_blueprints/contract.v1.json` und erzeugt daraus die zulässige
Zielpfadmenge. Tests stellen sicher, dass kein Katalog einen unbekannten Pfad verwendet.

Bewusst ausgeschlossen sind unter anderem:

- technische Schlüssel,
- Value-Stream-Status,
- Fokusentscheidung,
- Prozessstatus und Prozessvalidierung,
- Empfehlung und Bewertungsstatus von Lösungsoptionen,
- Use-Case-Status und Entscheidungsstatus,
- Governance-, Freigabe-, Delivery- und Lifecycle-Zustände.

## Eingabegrenze

Lange Antworten sind als native `textarea` vorgesehen. Der Vertrag benötigt keine eigene
JavaScript-Eingabekomponente und bleibt damit kompatibel mit Betriebssystem-Diktat wie Windows
`WIN + H`.

## Nicht-Ziele

Version 1 ist keine:

- Survey- oder Form-Builder-Plattform,
- Datenbankverwaltung beliebiger Kataloge,
- Import- oder Workflow-DSL,
- LLM-Extraktion,
- Vorschlags- oder Übernahmepipeline,
- Fachobjektanlage,
- Entscheidungs- oder Freigabelogik.

## Technischer Einstiegspunkt

Das öffentliche Modul stellt bereit:

- `get_capture_catalog(...)`,
- `is_capture_catalog_supported(...)`,
- `validate_answer_document(...)`,
- `catalog_progress(...)`,
- `allowed_blueprint_target_paths(...)`,
- `catalog_contract_errors(...)`.

Damit können die Folgearbeitspakete den Vertrag wiederverwenden, ohne Form- oder Validierungsregeln
zu duplizieren.
