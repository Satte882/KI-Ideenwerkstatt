# VS1/1 – Quellenraum- und Werkzeugvertrag

Issue: #2  
Tool-Version: `vs1-source-tools-v1`

## Zweck

Dieser Vertrag beschreibt ausschließlich die begrenzten, deterministischen Untersuchungswerkzeuge
für VS1/1. Er führt keinen neuen fachlichen Lifecycle ein und trifft keine Scope-, Ursachen-,
Lösungs-, Freigabe-, Pilot- oder Go-live-Entscheidung.

## Autorisierter Anker

Jeder Quellen-Snapshot ist an genau einen bestehenden, bearbeitbaren
`ProcessAnalysis`-Entwurf gebunden. Die bestehende Bearbeitungsberechtigung des zugehörigen
Value Streams bleibt maßgeblich. Ein administrativ registrierter Quellenordner gehört genau zu
diesem Fall.

## Snapshot

`create_source_snapshot(actor, SnapshotRequest)`

Eingabe:

- `process_analysis_id`: bestehender ProcessAnalysis-Draft;
- `folder_id`: opaque ID eines administrativ registrierten und aktiven Fallordners;
- `decision_question`: freigegebene Problem-/Entscheidungsfrage;
- `run_limits`: technische Run-Grenzen als versionierter Snapshot-Kontext.

Verhalten:

- prüft Berechtigung und Fallbindung;
- prüft den kanonischen Pfad;
- akzeptiert genau einen nicht rekursiven Ordner;
- akzeptiert nur UTF-8 TXT/MD/CSV;
- lehnt Limits sichtbar ab statt abzuschneiden;
- erzeugt vor einer späteren Modellnutzung vollständige, unveränderliche DB-Kopien;
- friert den ausdrücklich erlaubten ProcessAnalysis-Kontext ein;
- vergibt stabile opaque Source-IDs;
- markiert gleiche Inhalts-Hashes als Duplikate statt als unabhängige Evidenz;
- erzeugt für autorisierte Folgeaufnahmen eine neue Revision.

## Quellenwerkzeuge

### `list_sources(actor, snapshot_id)`

Liefert ausschließlich Manifest-Metadaten des autorisierten Snapshots: Source-ID, Dateiname,
Typ, Größe, SHA-256, technische Dateizeit, CSV-Zeilen/-Spalten und Duplikatreferenz.

### `search_sources(actor, snapshot_id, SearchRequest)`

Durchsucht alle Manifestdateien. Fundstellen sind:

- TXT/MD: Zeilennummer;
- CSV: Datenzeile und Spaltenname.

Ergebnisse besitzen ein festes Treffer-/Bytebudget. `next_cursor` macht jede Fortsetzung
sichtbar; es gibt kein stilles Abschneiden.

### `read_source(actor, snapshot_id, ReadRequest)`

Liest ein begrenztes Fenster über eine Source-ID, nie über einen vom Aufrufer gelieferten Pfad.

- TXT/MD: Zeilen;
- CSV: Datenzeilen und optional explizit gewählte existierende Spalten.

`next_cursor` kennzeichnet vorhandene Fortsetzung.

## Analysewerkzeuge

### `profile_csv(actor, snapshot_id, CsvProfileRequest)`

Ermittelt deterministisch:

- Spaltentypen;
- fehlende Werte;
- vollständige Dublettenzeilen.

Gemischte Typen werden als Finding ausgewiesen und nicht still konvertiert.

### `compare_groups(actor, snapshot_id, CompareGroupsRequest)`

Unterstützt ausschließlich:

- Filter auf existierenden Spalten;
- Operatoren `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`,
  `is_null`, `not_null`;
- genau eine Gruppierung;
- `count`, `sum`, `mean`, `median`, `min`, `max`;
- paarweise Differenzen der Gruppenaggregate.

Es gibt keine freien Formeln, Joins, SQL-, Python-, Shell-, Makro- oder Pfadausführung.
`null` wird nicht als 0 interpretiert. Nichtnumerische Werte, unklare oder konkurrierende
Einheiten und fehlende Spalten werden sichtbar als Ausschluss/Finding/Fehler behandelt.
Aggregationen belegen Unterschiede, nicht automatisch Kausalität.

## Persistierte Provenance

Jedes `profile_csv`-/`compare_groups`-Resultat speichert:

- Source-ID und Quellenhash;
- Werkzeugname und Werkzeugversion;
- vollständige Parameter;
- Gesamtpopulation und tatsächlich aggregierte Zeilen;
- ausgeschlossene Zeilen mit Grund;
- Gruppengrößen;
- Missing Values;
- Einheitenkontext;
- deterministisches Resultat.

Snapshot, Quellenkopien und Werkzeugresultate sind über normale ORM-Pfade unveränderlich und
nicht direkt löschbar.

## Berechtigungsentzug und Retention

Die Berechtigung wird bei jedem öffentlichen Werkzeugzugriff erneut geprüft. Ein deaktivierter
Quellenordner sperrt Reads und den Abruf gespeicherter Werkzeugresultate. Ein laufender
Snapshot bleibt technisch gespeichert, aber nicht weiter nutzbar.

Evidence-Snapshots werden **nicht** an die technische LLM-Run-Retention gekoppelt. Eine spätere
fachlich autorisierte Lösch-/Retention-Funktion muss Snapshot-Kopien und abgeleitete
Werkzeugresultate gemeinsam behandeln; direkte Einzel-Löschung ist bewusst blockiert.

## Nicht ausgeführt

Quelltext, URLs und Dokumentanweisungen sind Daten. Diese Werkzeuge führen daraus keine Links,
Prompts, Makros, Programme oder externen Aktionen aus.

## Übergabe an VS1/2

VS1/2 darf diese fünf Werkzeugfunktionen direkt aus Python/Django aufrufen. Es ist keine
allgemeine Agent-Framework- oder Tool-Plattformabstraktion erforderlich.
