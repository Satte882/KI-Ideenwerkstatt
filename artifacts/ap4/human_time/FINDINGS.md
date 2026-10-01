# AP4 Human-Time Findings

This ledger preserves observations from the one-time human measurement runs. It does not replace the per-case JSON records, change the frozen measurement contract, or authorize a rerun. The human stopped the round after AP4-04 because the accumulated UX defects made the remaining timing baseline unsuitable. AP4-05 through AP4-08 were not started. The findings are now the correction baseline before any new measurement campaign.

## AP4-01

### HT-F01 — Source upload has no additive staging workflow

- Surface: Autonomous Business Discovery start
- Observation: The upload control has no explicit staging list or second "add more files" action for combining files selected from different folders.
- Evidence: `AP4-01-human-time.json` → `browser_evidence`
- Status: corrected and verified locally; additive staging list, explicit "Weitere Dateien hinzufügen", per-file removal, and pre-submit filename review added

### HT-F02 — No visible processing feedback after starting Discovery

- Surface: Autonomous Business Discovery start
- Observation: After "Analyse starten", no spinner or step/status feedback explains the active Discovery work. Comparable progress feedback already exists in the Investigation/Decision Brief flow.
- Evidence: `AP4-01-human-time.json` → `browser_evidence`
- Status: corrected and verified locally; guarded submit now shows a spinner, busy label, live status, and blocks duplicate submission

### HT-F03 — Pending Investigation showed elapsed time but no actionable progress

- Surface: Investigation activity
- Observation: The page showed "Start angefordert - Ausführung ausstehend" and an increasing elapsed timer, but no worker/progress signal. The run remained unclaimed until the human aborted.
- Evidence: run `725880dd-5c21-47d7-aac7-c73532228fda`; `AP4-01-human-time.json`
- Status: corrected and covered by regression tests; an unclaimed dispatch becomes an explicit technical blocker after 30 seconds when execution capacity is available, states that no confirmed analysis is running, preserves abort as the safe action, and warns against a blind restart

## AP4-02

### HT-F04 — Selected source pack was insufficiently verified before submission

- Surface: Autonomous Business Discovery start
- Observation: AP4-02 was submitted with AP4-01 files. The system correctly detected the contradiction only after provider work and stopped at `WAITING_HUMAN`.
- Evidence: snapshot `9f780201-62a3-4801-b569-df299a1f83c4`; `AP4-02-human-time.json`
- Status: corrected and verified locally; the additive staging list exposes the complete filename set before submission

## AP4-03

### HT-F05 — Invalid solution-selection submit does not guide the human to the blocker

- Surface: Solution option comparison
- Observation: After selecting an option and entering the rationale, submit returned to the top of the same page. No prominent error summary, focus, or anchor explained that the required confirmed-cause step was still unresolved.
- Evidence: ProcessAnalysis `c5bed74d-a227-4c87-953d-a50fc639ae12`; zero persisted selection decisions after submit
- Status: corrected and covered by regression tests; invalid submits now expose a prominent, focused error summary with links to the blocking fields

### HT-F06 — Failed submit creates the impression that the ProcessAnalysis lost the decision

- Surface: ProcessAnalysis after navigating back
- Observation: The page correctly reported that no preferred option was stored, but it did not explain that the immediately preceding selection attempt had failed validation.
- Evidence: attachment `Eingefügter Text.txt`; `AP4-03-human-time.json`
- Status: corrected together with HT-F05; the preserved input and explicit "Eingabe noch nicht gespeichert" summary explain the failed submit before navigation can create a false loss impression

## AP4-04

### HT-F07 — Proposed core finding is not carried into the confirmation field

- Surface: Solution option comparison / combined diagnosis and selection
- Observation: The required "Bestätigte Ursache" field was empty although the reviewed Investigation and ProcessAnalysis already contained a proposed core finding. The human had to reconstruct context that the system already held and then received the avoidable validation message "Bitte den Kernbefund fachlich bestätigen oder korrigieren."
- Expected correction: Show the source-grounded proposed finding directly in the editable field, clearly label it as unconfirmed, and preserve explicit human confirmation or correction as the authority action.
- Evidence: Investigation `985aa95b-2e6c-4852-906d-9804dbf4882d`; ProcessAnalysis `80fff63d-42fb-45a1-b825-5f1fe221aba4`; `AP4-04-human-time.json`
- Status: corrected and covered by regression tests; fallback order now carries forward a source-grounded claim, reviewed brief hypothesis, or existing cause hypothesis without auto-confirming it

### HT-F08 — No busy state during diagnosis confirmation and AI handoff

- Surface: Solution option comparison
- Observation: After "Diagnose bestätigen und bevorzugte Option auswählen", synchronous follow-up work took noticeable time without a spinner, disabled-submit state, or status explanation.
- Expected correction: Reuse the existing guarded-submit pattern with a visible busy label, spinner, live status, and duplicate-submit protection.
- Evidence: `AP4-04-human-time.json`
- Status: corrected and covered by regression tests; both diagnosis/selection and AI continuation use the guarded-submit busy state

### HT-F09 — Competing actions obscure the next step after a successful AI selection

- Surface: Solution option comparison / selected result
- Observation: The page showed a persisted preferred AI option and created canonical use case, but both "AI-Entscheidungsgrundlage vorbereiten und fortsetzen" and another "Bevorzugte Option auswählen" action remained prominent. It was unclear whether the user should continue or repeat the selection.
- Expected correction: Make continuation the single primary next action. Present changing the existing selection as an explicitly secondary action with distinct wording.
- Evidence: selection decision `6`; Use Case `KI-0003`; `AP4-04-human-time.json`
- Status: corrected, regression-tested, and visually verified on the AP4-04 local state; continuation is the sole primary action and changing the selection is explicitly secondary

## Measurement stop

- AP4-04 ended by explicit human decision after the preferred option was persisted and before a final reviewable end state was reached.
- AP4-05, AP4-06, AP4-07, and AP4-08 were not started.
- No case is authorized for a timing rerun merely to improve a value.

## Correction verification

- Targeted solution-selection and loading-feedback suite: 15 tests passed.
- Focused regression rerun for cause fallback, validation guidance, resume flow, and submit guard: 3 tests passed.
- Discovery/source-upload regression checks and static staging contract passed.
- Ruff formatting and lint checks passed for all changed Python tests and presentation logic.
- Local visual inspection confirmed the revised Discovery upload surface and the AP4-04 post-selection action hierarchy.
- Investigation activity now distinguishes fresh assignment, legitimate queueing, confirmed execution, and unavailable background execution; the overdue unclaimed state is regression-tested.
- Investigation activity regression suite: 19 tests passed.
