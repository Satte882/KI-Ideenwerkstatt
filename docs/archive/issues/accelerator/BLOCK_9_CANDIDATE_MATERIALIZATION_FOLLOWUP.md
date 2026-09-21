# Block 9 AP 9 Nachtrag: realer Review-Pfad für Textvorschläge

**Issue:** #125  
**Benchmarkvertrag:** `block9-v2`  
**Zeitpunkt:** vor dem ersten gewerteten interaktiven Lauf

## Befund aus den erneuten Warm-ups

PR #241 ist nicht regressiv: In einem erfolgreichen Analyse-Lauf wurden die sieben zuvor falsch
klassifizierten Enum-/Dezimalfelder korrekt normalisiert. Gleichzeitig zeigte der identische
fachliche Input echte Modellvarianz: ein Lauf war erfolgreich, ein weiterer endete mit
`invalid_extraction`.

Für den erfolgreichen Lauf wurden zusätzlich zwei Qualitätsfehler beobachtet:

- `use_case.title` verlor die öffnende eckige Klammer,
- `use_case.summary` wurde trotz zulässigem Zielpfad nicht vorgeschlagen.

Diese beiden Befunde werden **nicht** benchmark-spezifisch durch Prompt-Sonderregeln repariert.
`use_case.summary` ist im eingefrorenen Use-Case-Katalog bereits als zulässiges Ziel von
`uc_problem_context` enthalten. Die Textnormalisierung entfernt keine inneren oder führenden
Sonderzeichen außer äußerem Whitespace. Damit sind fehlende Coverage beziehungsweise die
veränderte Klammer Modell-/Vorschlagsqualität und sollen in Block 9 als solche sichtbar bleiben.

Der Capture-Aufruf verwendet bereits `temperature=0.0`. Der Nachtrag ändert daher weder Sampling
noch Prompt- oder Extraktionsschema-Version. Ein Regressionstest sichert die Temperatureinstellung
zusätzlich ab.

## Reproduzierbare Produktlücke

Unabhängig von der Modellqualität war der normale Review-Pfad unvollständig:

1. `execute_capture_analysis()` speicherte erfolgreiche `CaptureFieldSuggestion`-Datensätze.
2. Der normale Browserpfad materialisierte danach jedoch keine `FieldAdoptionCandidate`-Datensätze.
3. Die Review-UI zeigt Übernehmen-/Bearbeiten-/Verwerfen-Aktionen nur für bereits vorhandene
   Kandidaten.
4. Zusätzlich speichert die Extraktion qualifizierte Zielpfade wie `use_case.title`, während die
   bestehende Block-5-Adoption bewusst mit freigegebenen Modellfeldnamen wie `title` arbeitet.

Das erklärt die beobachteten **0 normalen Adoption-Kandidaten** trotz erfolgreicher Analyse.

## Änderung

Der bestehende Block-5-Pfad wird wiederverwendet; es entsteht keine zweite Adoption-Registry.

- Ein qualifizierter top-level Extraktionspfad wird deterministisch auf den Feldnamen reduziert,
  z. B. `use_case.title -> title`.
- Der reduzierte Feldname muss weiterhin durch `field_registry.assert_adoptable_field()` freigegeben
  sein.
- Verschachtelte oder strukturierte Pfade wie `use_case.metric.name` oder
  `use_case.classification.business_domain` werden nicht zu normalen Textkandidaten gemacht.
- Historische/plain Block-5-Zielnamen bleiben kompatibel.
- Nach erfolgreicher Extraktion werden Kandidaten automatisch erzeugt, aber nur wenn
  `ACCELERATOR_FIELD_ADOPTION_ENABLED` aktiv und ein Zielobjekt gebunden ist.
- Extraktionsspeicherung und Kandidatenmaterialisierung bilden eine gemeinsame Transaktionsgrenze.
  Scheitert die Kandidatenvorbereitung, werden die gespeicherten Suggestions zurückgerollt und der
  Lauf wird explizit als `candidate_snapshot_failed` markiert. Ein halbfertiger Review-Zustand wird
  nicht hinterlassen.

## Unverändert

- `temperature=0.0`,
- Prompt-Version `1.0`,
- Extraktionsschema-Version `1.0`,
- `block9-v2`-Fixture und Prüfsumme,
- Provider/Modell `OpenRouter / deepseek/deepseek-v4-flash`,
- Capture-Output-Cap `32.768`,
- Retry-/Recovery-Regel und Scored-Reihenfolge,
- bisherige technische AP9-Messwerte.

Die beobachteten falschen/fehlenden Vorschläge sowie weitere `invalid_extraction`-Fehler bleiben
relevante Qualitäts- und Zuverlässigkeitsbefunde und werden nicht aus der Messung herausoptimiert.

## Nächster Gate-Schritt

Nach Merge und lokalem Update wird genau ein weiterer nicht gewerteter Accelerator-Warm-up über den
vollständigen Review-Pfad durchgeführt. Der Zweck ist nun die technische Pfadvalidierung inklusive
normaler Kandidaten und Structured Review, nicht ein perfektes LLM-Ergebnis. Fachlich falsche,
fehlende oder zusätzliche Vorschläge werden im Review korrigiert beziehungsweise verworfen und als
Qualitätsbefund festgehalten.

Falls der einzelne Provideraufruf erneut ausschließlich wegen `invalid_extraction` scheitert, wird
nicht mit weiteren Prompt-Sonderregeln auf einen perfekten Warm-up optimiert. Der Fehler wird als
Zuverlässigkeitsbefund dokumentiert und der weitere Messablauf gegen den bereits eingefrorenen
Retry-/Recovery-Vertrag neu gegated. AP 9 und AP 10 bleiben bis dahin offen.
