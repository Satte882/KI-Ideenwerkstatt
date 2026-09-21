# Issue #323 – Gap-Analyse

**Issue:** #323 – ProcessAnalysis: SIPOC als sichtbare Leitfrage für Inputs, Quellen und Empfänger ergänzen  
**Baseline:** `main` @ `2a07d3b09122025d1529bae26e5d89b0f2770b73`  
**Datum:** 22.08.2026  
**Status:** Analyse vor Implementierung

## Kurzurteil

Die Kernaussage aus #315 hält auf der aktuellen Baseline. Für SIPOC besteht keine neue Daten-, Persistenz- oder Journey-Lücke. `ProcessAnalysis` besitzt bereits die fachlichen Container für Prozessgrenzen, Trigger, Ergebnis, Rollen, Systeme, Daten/Dokumente und Übergaben.

Seit #315 wurden über #318 zusätzliche Diagnosefelder für Beobachtung, Ursachenhypothese, bestätigte Ursache und Constraint ergänzt. Diese Semantik ist orthogonal zu SIPOC und bleibt unverändert.

## Gap-Matrix

| SIPOC-Aspekt | Bestehender Mechanismus | Bewertung | Entscheidung |
|---|---|---|---|
| Supplier / Quelle | `handoffs`, `roles`, `systems`; vorgelagerter Stage-Kontext | teilweise vorhanden – reine Methodik-/Help-Text-Lücke | Quelle/Supplier als Leitfrage bei Übergaben sichtbar machen |
| Input | `data_objects`, zusätzlich `trigger`, `handoffs`, `current_flow` | teilweise vorhanden – reine Methodik-/Help-Text-Lücke | vorhandenes Feld `data_objects` als fachlichen Input-Container nutzen |
| Process | `stage`, `name`, `scope_start`, `scope_end`, `current_flow` | vorhanden | keine Änderung |
| Output | `outcome` | vorhanden | vorhandenes Ergebnisfeld nutzen |
| Customer / Empfänger | `handoffs`, `roles`; vorgelagert `stakeholders` | teilweise vorhanden – reine Methodik-/Help-Text-Lücke | Empfänger bei Übergaben ausdrücklich provozieren |
| eigenes SIPOC-Artefakt | nicht vorhanden | bewusst nicht benötigt | nicht einführen |

## Feldzuordnung

Die kleinste konsistente Abbildung lautet:

- **Input:** `data_objects` – fachliche Inputs, Daten und Dokumente,
- **Output:** `outcome` – fachliches Prozessergebnis,
- **Supplier / Customer:** `handoffs` – Herkunft relevanter Inputs und Übergabe beziehungsweise Nutzung des Ergebnisses,
- **Process:** vorhandene Prozessgrenzen und `current_flow`.

`source_snapshot` ist ausdrücklich **kein SIPOC-Supplier**. Er dokumentiert die Provenance übernommener Radar-Feldwerte und darf nicht mit der fachlichen Herkunft eines Prozessinputs vermischt werden.

## Bestehende Pflichtfelder

`outcome` und `data_objects` sind bereits reguläre Pflichtfelder der `ProcessAnalysis`; `handoffs` bleibt optional. #323 führt daher weder neue Pflichtfelder noch eine neue Requiredness ein.

## Kleinste Lösung

1. Einen kompakten, nicht-interaktiven Hinweis innerhalb der bestehenden ProcessAnalysis-Formularkarte anzeigen:
   `Supplier → Input → Process → Output → Customer`.
2. Ausdrücklich erklären, dass SIPOC nur Denk- und Scopingrahmen ist und kein separates Artefakt entsteht.
3. Feldnahe Leitfragen an den bestehenden Feldern `data_objects`, `outcome` und `handoffs` anzeigen.
4. Keine Änderungen an Models, Migrationen, Views, Persistenz, Validation, Journey oder Solution Selection.

Der SIPOC-Hinweis wird bewusst **nicht** als zusätzliche Karte neben dem vorhandenen „Quellkontext aus dem Value Stream“ angelegt, sondern innerhalb der bestehenden ProcessAnalysis-Formularkarte platziert.

## Invarianten

Unverändert bleiben insbesondere:

- #318 Diagnose-Semantik und Diagnose-Readiness,
- `ProcessValidation`, Versionierung und Stale-Verhalten,
- `PROCESS_VALIDATION_FIELDS`,
- #331 Evidenzbasis, Time-to-Value, Hybrid-/No-AI- und Solution-Selection-Semantik,
- #322 `UseCaseOrigin` und Process→Use-Case-Traceability,
- bestehende Value-Stream-/Stage-Provenance.

## Verworfene Alternativen

- SIPOC-Modul oder SIPOC-Canvas,
- Supplier-/Customer-Entitäten,
- neue Input-/Output-Modelle,
- fünf SIPOC-Pflichtfelder,
- zweites Process-`scope_in/scope_out`,
- neue Validation oder Journey-Stufe,
- separate SIPOC-Karte im Formular,
- Umdeutung von `source_snapshot` zum fachlichen Supplier.

## Schemaentscheidung

**Keine Schemaänderung. Keine Migration. Keine neue Persistenz.**
