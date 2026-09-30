# AP4 Measurement Contract

Issue: #107  
Planbasis: `2b9a2f87699cbf1f1014463d3061e3d05b77a86c`

## Zweck

Dieser Vertrag friert **vor dem ersten gewerteten AP4-Lauf** Population, Messmethodik und Success-Sampling-Regel ein. Er baut keine zweite Telemetrie- oder Workflow-Schicht.

Kanonische Fallliste:

`tests/fixtures/ap4_case_manifest_v1.json`

Die Source Packs liegen unter:

`tests/fixtures/ap4_source_packs/`

Der Validator prüft:
- exakt acht Fälle und acht geforderte Kategorien;
- stabile Run-Slots;
- unveränderte Dateimengen je Source Pack;
- Content Hash je Source Pack;
- eingefrorene Prompt-/Schema-/Runtime-Versionen gegen den aktuellen Code.

## Gewertete Runs

Jeder autonome Fall besitzt genau **einen scored Slot**.

Ein fehlgeschlagener scored Run bleibt scored Evidence. Er darf nicht gelöscht oder durch einen späteren besseren Run ersetzt werden.

Nach einem Root-Cause-Fix ist nur ein eigener `post_fix`-Record mit Verweis auf den früheren Record zulässig.

## Frische E2E-Baseline

Die historische VS1-Baseline ist keine vollständige #1-E2E-Baseline.

Für die direkten Alt-gegen-Neu-Messgrößen werden die im Manifest markierten Baseline-Fälle verwendet:

- AP4-01 – Non-AI / Organisation
- AP4-02 – Rule Automation
- AP4-03 – Controlled LLM
- AP4-04 – LLM Workflow / Hybrid

Manueller/geführter und autonomer Lauf verwenden je Vergleichsfall:
- dieselbe Problemstellung;
- dasselbe Source Pack;
- denselben fachlichen Scope.

Die Edge-Cases AP4-05 bis AP4-08 gehören zur autonomen Gesamtpopulation, erfordern aber keine zusätzliche manuelle Vergleichsrunde, sofern keine Metrik sie ausdrücklich benötigt.

## Zeitmessung

Pro Record werden getrennt erfasst:

- `active_input_seconds`
- `navigation_seconds`
- `authority_decision_seconds`
- `post_draft_review_seconds`
- `post_draft_correction_seconds`
- `system_wait_seconds`

Aktive Human Work:

```text
active_input
+ navigation
+ authority_decision
+ post_draft_review
+ post_draft_correction
```

Systemwartezeit wird nicht eingerechnet.

Authority Decisions bleiben sichtbar, sind aber keine vermeidbaren Rückfragen oder vermeidbare Nacharbeit.

## Manuelle Feldpflege

Gezählt werden tatsächlich vom Menschen neu eingegebene oder fachlich geänderte **kanonische Werte/Felder**.

Nicht gezählt:
- Navigation;
- unverändertes Öffnen/Speichern;
- reine Anzeige;
- unveränderte Bestätigung eines bereits korrekten Werts.

Primärmetrik:

```text
1 - Summe autonome manuelle Feldänderungen
    / Summe manuelle Baseline-Feldänderungen
```

über die gepaarten Baseline-Fälle.

## Rückfragen

`avoidable_questions`:
Fragen, die bei ausreichender vorhandener Evidenz nicht notwendig gewesen wären.

`authority_questions`:
echte menschliche Scope-, Lösungs-, Risiko-, Approval- oder vergleichbare Authority Decisions.

Nur `avoidable_questions` zählt gegen Median ≤ 3.

## Provenance / Halluzination

`source_derived_claims` zählt tragende Tatsachen, die als aus vorhandenen Quellen abgeleitet präsentiert werden.

`provenance_resolved_claims` zählt davon die auflösbar referenzierten Tatsachen.

Ziel: 100 %.

`hallucinated_facts` zählt als Tatsache oder Messwert präsentierte Inhalte ohne Source-/Domain-Basis.

Ziel: 0.

## Menschliche Nacharbeit

Primär:

```text
Summe autonome post_draft_review_seconds
+ Summe autonome post_draft_correction_seconds
------------------------------------------------
Summe aktive menschliche Arbeitszeit der gepaarten
manuellen E2E-Baselines
```

Ziel: ≤ 20 %.

Zusätzlich wird `post_draft_fields_changed` protokolliert, aber nicht als Ersatz für die Zeitmetrik verwendet.

## Blind Human Review

Die vorhandene Redaktionslogik aus `issue4_blind_review.py` wird wiederverwendet. Ein Review kann auf neutralisierten Markdown-Artefakten außerhalb der Anwendung stattfinden.

Ein LLM-/Technical-Review ersetzt den geforderten Blind Human Review **nicht**.

Ist kein unabhängiger Human Reviewer verfügbar, bleibt diese Abnahme transparent offen.

## Nutzung

Vertrag prüfen:

```powershell
python manage.py ap4_evidence
```

Mit vorhandenen Evidence Records auswerten:

```powershell
python manage.py ap4_evidence --records artifacts/ap4/evidence.jsonl
```

Die Records sind append-only im Sinne des AP4-Testvertrags: ein zweiter scored Record für denselben Fall/Pfad wird abgelehnt.
