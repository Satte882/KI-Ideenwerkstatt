# #111 AP1: Baseline und A/A-Evidence

Parent: #106. Getesteter Code-Commit:
`b37e25b6508a6e5769785c72c2fc35ac1177fae2`.
Der Commit dieses Evidence-PRs ist kein neuer getesteter Runtime-Stand.

## Messung und Population

- Modell: `deepseek/deepseek-v4.1-flash` über OpenRouter.
- Eingefrorener Provider: `deepinfra/fp8`, keine Fallbacks.
- Contract: `issue106-performance-ap0-v1`.
- 25/25 reale Runs, fünf Wiederholungen je Golden-Set-Fall, seriell ausgeführt.
- Alle Runs am gespeicherten System-Boundary; gültige einheitliche Commit-Bindung,
  keine Duplikate und keine fehlenden Slots.
- Keine Replacement-Runs, Löschungen oder nachträglichen Änderungen an Runs.
- Keine lokale Prozessunterbrechung oder Runner-Recovery erforderlich.
- `WAITING_HUMAN` schließt menschliche Wartezeit aus.

`baseline.json` enthält alle Rohwerte, Modell-/Tool-Aufrufe, Kosten,
Review-Kontexte, die normalisierte menschliche Review und die A/A-Auswertung.
`review.json` enthält die verbindlich bestätigte menschliche Bewertung.

## Runtime und A/A

Alle Zeiten in Sekunden. Raten beziehen sich auf alle fünf gestarteten Runs je Fall,
einschließlich FAILED. Die gemischten READY-/FAILED-Statistiken beschreiben die
beobachtete Population; sie sind kein Nachweis gleichwertiger fachlicher Ergebnisse.

| Fall | Statusmix | Median | MAD | 2×MAD | Min | Max | Retry | Repair | Timeout |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AP4-01 | 5 READY | 189.933 | 1.613 | 3.226 | 188.320 | 251.706 | 0% | 0% | 0% |
| AP4-02 | 2 READY, 3 FAILED | 249.280 | 81.140 | 162.280 | 168.140 | 968.821 | 80% | 20% | 80% |
| AP4-04 | 3 READY, 2 FAILED | 266.381 | 14.432 | 28.864 | 141.173 | 280.813 | 40% | 0% | 20% |
| AP4-05 | 5 WAITING_HUMAN | 35.806 | 6.885 | 13.770 | 24.103 | 47.952 | 0% | 0% | 0% |
| AP4-06 | 5 WAITING_HUMAN | 64.355 | 13.036 | 26.072 | 46.335 | 87.221 | 0% | 0% | 0% |

AP4-06: READY n=0, WAITING_HUMAN n=5. `runtime_by_terminal_state` enthält nur
WAITING_HUMAN; `comparison_runtime_mode = single_terminal_state`.
Es gibt keine gemischte READY-/WAITING_HUMAN-Population.
2×MAD ist der eingefrorene Engineering-Noise-Floor, kein Konfidenzintervall.
Keine p95- oder Signifikanzbehauptung aus fünf Wiederholungen.

## Menschliche Qualitätsbewertung

Reviewer: `Human reviewer (user-confirmed in ChatGPT)`.
Bestätigter Bewertungszeitpunkt: `2026-10-02T08:44:00+02:00`.
Die Bewertung wurde nach ausdrücklicher Bestätigung des Benutzers eingetragen;
sie ist keine automatische Modellbewertung.

| Fall | PASS | FAIL |
|---|---:|---:|
| AP4-01 | 5 | 0 |
| AP4-02 | 1 | 4 |
| AP4-04 | 0 | 5 |
| AP4-05 | 5 | 0 |
| AP4-06 | 5 | 0 |
| Gesamt | 16 | 9 |

Die neun normalen Qualitäts-Fails bestehen aus:

- Fünf technischen FAILED-Runs: AP4-02 R1/R4/R5, AP4-04 R2/R5.
  Fehlercodes: zweimal `timeout`, zweimal `no_progress_loop`, einmal
  `structured_contract_error` mit `invalid_tool_parameters`.
- Vier fachlich unvollständigen READY-Runs: AP4-02 R3 und AP4-04 R1/R3/R4.
  Die Inhalte sind fachlich richtig, aber die Zuordnung aller eingefrorenen
  CSV-Fälle E01–E06 bzw. R01–R05 ist nicht explizit vollständig.

Alle Hard-Fail-Checks der 25 Runs sind menschlich bestätigt PASS:
`observed_hard_fail_count = 0`. Normale Qualitäts-Fails werden nicht in
Hard Fails umgedeutet. Kein bewertbares Review-Feld bleibt UNASSESSED.
Das Wort `unassessed` bleibt lediglich Teil des zulässigen Dateiformats.
Die fünf technischen FAILED-Runs bleiben terminal-state-nichtkonform.

## Kosten und Pricing-Hinweis

- Bestätigte tatsächliche Providerkosten: **0.134906 USD**.
- Budget-accounted Kosten: **0.184652 USD**.
- **Fünf uncertain Provider-Versuche**: AP4-02 R1/R2/R3/R5 und AP4-04 R2.
- Vorab verwendete Benchmark-Preisbasis: Input **0.05 USD / 1M Tokens**,
  Output **0.60 USD / 1M Tokens**.
- Pricing-Version: `openrouter-deepseek-v4.1-flash-2026-10-01`.

Bestätigte `actual_cost` bleibt unveränderte Provider-Evidence.
Budget-accounted Kosten für uncertain Attempts sind eine Schätzung auf der
vorab verwendeten Benchmark-Preisbasis. Die tatsächlichen Gesamtkosten sind
wegen unklarer Abrechnung dieser Versuche nicht vollständig bekannt.
Die bereits dokumentierte Abweichung zum aktuellen Preis auf der
[OpenRouter-Modellseite](https://openrouter.ai/deepseek/deepseek-v4.1-flash)
führt weder zu nachträglicher Kostenumrechnung noch zu einer Wiederholung
der Runtime-/Qualitätsbaseline. Der AP1-Cap von 20 USD wurde nicht erreicht.

## Vollständigkeit und nächster Schritt

`export_issue106_baseline --assessments artifacts/issue106/ap1/review.json
--require-complete` wurde erfolgreich ausgeführt:
`population_complete = true`, `quality_complete = true`, 16 PASS / 9 FAIL,
0 Hard Fails. Die vollständigen Run-Rohdaten wurden gegen den vorherigen Export
auf unveränderte Inhalte geprüft.

Provider-interne Queue vs. Inference und nicht exponierte Cache-Effekte bleiben
nicht beobachtbar. Kein weiterer Provider-Run wurde für Review oder Export ausgeführt.

Dieser PR enthält ausschließlich Evidence und Dokumentation.
**#111 erst nach Merge schließen.** Keine automatische Issue-Schließung durch
diesen PR; #112 wird in diesem Arbeitsschritt nicht begonnen.
