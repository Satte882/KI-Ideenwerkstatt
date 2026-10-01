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

Nach einem Root-Cause-Fix ist nur ein eigener `post_fix`-Record mit Verweis auf den unmittelbar vorherigen Record desselben Falls/Pfads zulässig. Post-Fix-Ketten sind linear; parallele „bessere“ Zweige sind verboten.

Ein `post_fix`-Record bindet zusätzlich die tatsächlich verwendeten aktuellen
Prompt-/Schema-/Runtime-Versionen in `contract_versions`. Der eingefrorene scored Vertrag
und seine Records werden dadurch nicht umgeschrieben. Neue scored Records werden weiterhin
strikt gegen die eingefrorenen Versionen abgelehnt, sobald sich der Codevertrag geändert hat;
historische Auswertung und linear verkettete Post-Fix-Evidence bleiben dennoch lesbar.

Die Auswertung zeigt zwei getrennte Sichten:
- **Initial scored result**: ausschließlich die unveränderlichen ursprünglichen scored Runs;
- **Current post-hardening result**: je Fall der letzte linear verkettete Stand nach echten Root-Cause-Fixes.

Damit bleibt jeder ursprüngliche Fehlversuch sichtbar, während gleichzeitig der finale gehärtete Produktstand gegen die #1-Ziele bewertet werden kann.

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

Jeder Record trägt zusätzlich `human_time_measured`. Nur wenn die menschliche Zeit tatsächlich gemessen wurde, darf sie in Human-Work- oder Nacharbeits-Metriken eingehen. Fehlende bzw. scripted Operator-Zeit bleibt **offen** und darf nicht als numerische `0` automatisch PASS erzeugen.

Für die bereits eingefrorene AP4-Evidence gilt rückwärtskompatibel: manuelle Baselines sind gemessen; autonome Records ohne explizites Kennzeichen gelten als **nicht gemessen**.

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
