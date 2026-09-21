# Block 9 AP 9 Nachtrag: deterministische Textlisten-Normalisierung

**Issue:** #125
**Benchmarkvertrag:** `block9-v2`
**Zeitpunkt:** vor dem ersten gewerteten interaktiven Lauf

## Diagnose

Nach dem Wechsel auf `openai/gpt-5.6-luna` erreichte der Capture-Aufruf den Provider erst,
nachdem der für dieses Modell nicht unterstützte optionale Parameter `temperature` weggelassen
wurde. Die danach syntaktisch gültige und mit `finish_reason=stop` abgeschlossene Antwort
scheiterte an vier semantisch mehrwertigen, technisch aber als Text gespeicherten Zielen:

- `use_case.target_users`,
- `use_case.intended_users`,
- `use_case.source_systems`,
- `use_case.data_sources`.

Luna deklarierte diese Ziele als `text_list` und lieferte Listen aus Strings. Der bestehende
Validator erwartete für die freigegebenen Use-Case-Modellfelder ausschließlich `text`.

## Änderung

Der autoritative Zielpfad bestimmt weiterhin den gespeicherten Typ. `text_list` wird nur für die
fünf tatsächlich beobachteten Use-Case-Ziele `benefit_category`, `data_sources`,
`intended_users`, `source_systems` und `target_users` deterministisch auf Text normalisiert, wenn
der Rohwert eine nicht-leere Liste ausschließlich nicht-leerer Strings ist. Die Einträge werden
mit `, ` verbunden.

Leere Listen, leere Elemente, Nicht-String-Elemente sowie `text_list` für strukturierte oder
nicht-textuelle Ziele bleiben fail-closed. Inhaltliche Abweichungen der verbundenen Darstellung
werden im vorhandenen Review/Edit-Pfad korrigiert und als Qualitätsbefund gezählt.

## Unverändert

- Strict JSON Schema und `provider.require_parameters=true`,
- Prompt- und Extraktionsschema-Version,
- Enum-, Dezimal- und Integer-Normalisierung,
- `block9-v2`-Faktenset und Scoring,
- Retry-/Recovery-Regel,
- Capture-Output-Cap von 32.768 Tokens.

## Nachgelagerte Feldübernahme

Der erfolgreiche Luna-Lauf erzeugte 13 normale `FieldAdoptionCandidate`s. Zwei bestehende
Pfadannahmen verhinderten zunächst deren reale Nutzung: Die Detailseite suchte Kandidaten mit
dem vollständigen Extraktionspfad, während der Kandidat den aufgelösten Modellfeldnamen
speichert; dieselbe veraltete Gleichheitsprüfung existierte in der serverseitigen
Integritätskontrolle.

Anzeige und Integritätskontrolle verwenden jetzt dieselbe autoritative Pfadauflösung wie die
Kandidatenerzeugung. Ein Regressionstest deckt den vollständigen Weg für einen präfixierten
Extraktionspfad ab: sichtbare Review-Aktion, POST und tatsächlich gespeicherter Modellwert.

Bei einem noch vollständig leeren Use-Case-Draft bleibt die reguläre Use-Case-Validierung
maßgeblich. Deshalb wurde der Warm-up über den bereits im Benchmarkvertrag erlaubten normalen
Use-Case-Edit initialisiert, bevor die einzelnen Textkandidaten bestätigt wurden. Die
strukturierte Metrikgruppe wurde anschließend weiterhin einzeln geprüft und atomar übernommen.

## Lokaler Warm-up-Nachweis

- Modell: `openai/gpt-5.6-luna`
- Analyse: `a45e7637-b0bf-4554-96e9-900a138a641e`
- Providerstatus: erfolgreich, `finish_reason=stop`
- Vorschläge: 23
- Nutzung: 1.753 Prompt-, 2.696 Completion-, 4.449 Gesamttokens
- Providerdauer: 16.658 ms
- Kostenwert: 0,0016354
- Normale Feldprüfung: 13 Kandidaten abgeschlossen, davon 9 direkt und 4 bearbeitet
- Strukturierte Prüfung: 7 Metrikitems vollständig atomar übernommen
- Endzustand: alle 21 Benchmark-Felder entsprechen exakt `block9-v2`; Domäne
  `procurement`, Capability `Source-to-Pay` und Hosting `unknown` sind ebenfalls gesetzt;
  `support_responsibility` bleibt erwartungsgemäß leer.

Qualitätsbefunde des Modells bleiben sichtbar: `summary` wiederholte zunächst die
Problemstellung und drei aus `text_list` normalisierte Werte verwendeten Kommas statt der
Benchmarkformulierung mit „und“. Diese vier Werte wurden im vorgesehenen Review/Edit-Pfad
korrigiert. Der Lauf bleibt ungewertet; es wurden noch keine Scored Runs gestartet.
