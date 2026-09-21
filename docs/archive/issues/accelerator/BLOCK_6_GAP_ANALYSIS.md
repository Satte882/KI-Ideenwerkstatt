# Accelerator Block 6: Gap-Analyse und V1-Feldfreigabe

**Issue:** #122  
**Ausgangsstand:** `main` nach Merge von #176  
**Arbeitspaket:** AP 1 – Strukturierter Vertrag, Feldfreigabe und Abhängigkeitsgraph

## Ergebnis

Der Structured-Adoption-Pfad bleibt auf drei Kandidatenarten begrenzt:

1. `metric_set` für die sieben Felder der primären Use-Case-Metrik,
2. `value_stream_stage` für katalogisierte Phasenfelder je `target_group_key`,
3. `process_analysis` für genau einen Prozessanalyse-Entwurf mit expliziter Phasenreferenz.

Die Feldfreigabe liegt als statische Matrix in
`ki_radar/accelerator/structured_contract.py`. Ein Provider-Feldtyp allein erteilt
keine Schreibberechtigung. Zielpfad und Typ müssen gemeinsam einem expliziten
Eintrag entsprechen.

## Aktive strukturierte Felder

### Use-Case-Metrik

- Name: Text
- Typ: Enum
- Optimierungsrichtung: Enum
- Einheit: Text mit späterer Aliasnormalisierung
- Baseline: Dezimalzahl
- Zielwert: Dezimalzahl
- Messmethode: Text

Nur Metriktyp und Optimierungsrichtung sind aktive Enumfelder in Block 6 V1.
Andere katalogisierte Use-Case-Enums werden nicht vorgezogen.

### Value-Stream-Phase

Die acht katalogisierten Phasenfelder werden je stabilem lokalen Gruppenschlüssel
zusammengeführt. Reihenfolge und Name sind Pflichtfelder. Die Reihenfolge ist eine
Ganzzahl; alle übrigen Felder sind beschreibender Text.

### Prozessanalyse

Die bestehenden Felder von `ProcessAnalysisForm` werden als ein Entwurfsobjekt
geführt. Die Abhängigkeit zu einer neuen Phase wird ausschließlich über einen
validierten lokalen Phasenschlüssel aus demselben Batch hergestellt. Namensmatching
oder implizite Zuordnung ist ausgeschlossen.

## Denylist und Nicht-Ziele

Der aktuelle Capture-Katalog enthält für diesen Block kein konkretes gelbes
Personen-/Rollenreferenzfeld, kein Boolean-Zielfeld und kein Datums-Zielfeld des
Erstentwurfs. `reference`, `uuid`, `boolean` und `date` sind daher keine aktiven
Structured-Adoption-Typen. Hypothetische oder unbekannte Ziele werden fail-closed
abgelehnt und ausschließlich als Sicherheitstest behandelt.

Rote Felder, Status, Entscheidungen, Validierungen, Freigaben, Governance,
Delivery und Lifecycle bleiben vollständig außerhalb des Schreibpfads.

## Abhängigkeitsgraph und Teilverwerfung

Eine Prozessanalyse kann entweder eine bestehende Phase per ID oder eine neue Phase
per lokalem Schlüssel referenzieren. Für lokale Referenzen gilt:

- `rejected`, `ambiguous`, `invalid`, `conflict`, `superseded`, `stale` oder
  `failed` an der Phase invalidiert abhängige Prozessanalyse-Items;
- die abhängigen Items erhalten später den expliziten Zustand
  `dependency_invalid`;
- nach Korrektur der Phase ist eine erneute Bestätigung der abhängigen
  Prozessanalyse erforderlich;
- das Wiederherstellen einer Phase übernimmt keine frühere Bestätigung stillschweigend.

## Wiederverwendung

- `UseCaseForm` bleibt maßgeblich für die vollständige Metrikvalidierung.
- `ValueStreamStageForm` bleibt alleiniger Schreibpfad für neue Phasen.
- `ProcessAnalysisForm` bleibt alleiniger Schreibpfad für Prozessanalysen.
- Zielbindung, Berechtigung, feldbezogener Konfliktmaßstab und Idempotenzprinzipien
  aus Block 5 werden übernommen, nicht dupliziert oder aufgeweicht.

## Abnahme

Vertrags- und Denylist-Tests belegen, dass kein Zielpfad allein aufgrund seines
Provider-Feldtyps in den Schreibpfad gelangen kann. Der V1-Scope ist statisch,
prüfbar und auf den Golden Path begrenzt.
