# Block 9 AP 9 Nachtrag: deterministische Extraktionstypen

**Issue:** #125  
**Benchmarkvertrag:** `block9-v2`  
**Zeitpunkt:** vor dem ersten gewerteten interaktiven Lauf

## Diagnose

Der lokale Diagnose-Warm-up mit `deepseek/deepseek-v4-flash` endete regulär mit
`finish_reason=stop` und syntaktisch gültigem JSON. Die serverseitige Extraktionsprüfung
meldete sieben Fehler, weil der Provider jeweils `field_type="text"` lieferte, obwohl der
Zielpfad einen anderen Typ festlegt:

- fünf Enum-Ziele: Fachdomäne, Metriktyp, Optimierungsrichtung, Lösungstyp, Hosting,
- zwei Dezimal-Ziele: Baseline und Zielwert.

Der Diagnosepayload zeigte zugleich Enumwerte in der Form `code / Bezeichnung`, zum Beispiel
`duration / Dauer` und `assistant / Assistenzsystem`.

## Entscheidung

`target_field` ist die autoritative Quelle für den fachlichen Datentyp. Der vom LLM gelieferte
`field_type` bleibt aus Kompatibilitätsgründen Bestandteil des Providervertrags, entscheidet
aber nicht mehr über den serverseitigen Zieltyp.

Die Normalisierung bleibt fail-closed:

- Der Rohwert muss zum aus `target_field` bestimmten Typ passen.
- Die konkret diagnostizierte generische Unterklassifizierung `text -> enum|decimal|integer`
  darf anhand des autoritativen Zielpfads korrigiert werden; andere Typkonflikte bleiben Fehler.
- Textziele akzeptieren weiterhin nur echte Strings und weiterhin nur `field_type="text"`;
  Boolean-, Listen-, UUID-, Date- oder Reference-Deklarationen werden nicht still zu Text.
- Enums werden gegen die bereits bestehende `allowed_enums`-Quelle aus dem
  Scenario-Blueprint-Vertrag validiert.
- Neben einem exakten kanonischen Enumcode wird ausschließlich die eindeutige Form
  `code / Bezeichnung` akzeptiert und auf `code` reduziert.
- Label-only-, unbekannte oder fuzzy Enumwerte bleiben ungültig.
- Dezimalwerte verwenden unverändert die bestehende lokalisierte Dezimalnormalisierung.

Damit entsteht keine zweite Typ- oder Enum-Registry und keine modellabhängige Heuristik.

## Unverändert

- Prompt-Version `1.0` und Extraktionsschema-Version `1.0`,
- `block9-v2`-Fixture und deren Prüfsumme,
- Provider-/Modellwahl,
- Capture-Output-Cap `32.768`,
- Retry-/Recovery-Regel und Run-Reihenfolge,
- bereits vorhandene technische AP9-Messwerte.

Der lokale Diagnosepayload wird nicht in das Repository übernommen.

## Nächster Gate-Schritt

Nach Merge und lokalem Update ist genau ein weiterer nicht gewerteter Accelerator-Warm-up
zulässig. Erst wenn dieser den fachlichen `block9-v2`-Endzustand erreicht, darf die eingefrorene
Scored-Sequenz beginnen. AP9 und AP10 werden durch diesen Nachtrag nicht abgeschlossen.
