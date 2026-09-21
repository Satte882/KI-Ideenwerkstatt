# Block 9 AP 9 Nachtrag: Capture-Output-Budget

**Issue:** #125  
**Benchmarkvertrag:** `block9-v2`  
**Zeitpunkt:** vor dem ersten gewerteten interaktiven Lauf

## Anlass

Der manuelle `block9-v2`-Warm-up hat den fachlichen 21-Felder-Endzustand vollständig erreicht.
Zwei nachfolgende, nicht gewertete Accelerator-Warm-ups scheiterten dagegen jeweils beim
einzigen OpenRouter-Analyseaufruf mit `invalid_extraction`.

Beobachtet wurden dabei Completion-Werte von 3.605 beziehungsweise 4.036 Tokens bei einem
bisherigen gemeinsamen Output-Limit von 4.096 Tokens. Da die Anwendung bei
`invalid_extraction` weder den Roh-Provider-Payload noch eine feinere Validierungsursache
persistiert, ist Truncation **nicht als Ursache bewiesen**. Die zweite Messung liegt jedoch
nahe genug am bisherigen Cap, um das enge Budget vor dem ersten Scored Run als vermeidbaren
Störfaktor auszuschließen.

## Änderung

Die verbindliche Hard-Limit-Regel bleibt bestehen. Es wird kein unbegrenzter LLM-Aufruf
eingeführt.

- gemeinsame kompakte Accelerator-Aufrufe: weiterhin maximal `4.096` Output-Tokens,
- Capture-Structured-Extraction: eigener harter Cap `32.768` Output-Tokens über
  `ACCELERATOR_CAPTURE_MAX_OUTPUT_TOKENS`,
- Block-7-Lösungsgenerierung: unverändert eigener Cap `16.384` Output-Tokens.

Der Capture-Wert ist konfigurierbar, wird zentral validiert und darf `32.768` nicht
überschreiten. Die Capture-Analyse reicht genau diesen dedizierten Wert als `max_tokens` an
OpenRouter weiter.

## Benchmarkgrenze

Faktenset, Scoring-Felder, Run-Reihenfolge, Start-/Stop-Regeln, Retry-/Recovery-Regel und die
Fixture-Prüfsumme von `block9-v2` bleiben unverändert. Da noch kein Scored-v2-Run gestartet
wurde, erfolgt die Konfigurationsänderung vor Beginn der gewerteten Messserie.

Die bereits gemessenen technischen Blueprint-/Delivery-Werte aus AP 9 bleiben unverändert.
Der nächste zulässige Schritt nach Merge und lokalem Update ist ein weiterer nicht gewerteter
Accelerator-Warm-up mit der neuen Capture-Grenze. Erst nach erfolgreicher Pfadvalidierung darf
die eingefrorene Scored-Sequenz starten.

AP 10 muss weiterhin die tatsächlich verwendete Provider-/Modell- und LLM-Konfiguration der
Messserie ausweisen; LLM-bezogene Laufzeiten, Token-/Kostenwerte, Fehlerraten und
Vorschlagsqualität sind bei späteren Modell- oder Konfigurationswechseln nicht 1:1
übertragbar.
