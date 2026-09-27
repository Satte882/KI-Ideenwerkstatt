# Issue #86: Verifier timeout recovery

## Production evidence, before implementation

Read-only inspection of PostgreSQL run `6d75f0f5-6bf7-463d-8cce-3edb12ae58ad`
on 2026-09-27, against merge `ada5d9e1d969d515a099ec752466e7367e23c352`.
The reconstructed verifier `{instruction, context}` matches its persisted
`prompt_hash` exactly; this is the actual request context, not a new probe.

| Call | Role | Result | Seconds | Input / output / reasoning tokens |
| --- | --- | --- | ---: | --- |
| 1 | planner | read_source, cursor 0, limit 100 | 4.923 | 1728 / 200 / 94 |
| 2 | planner | counterevidence search | 16.184 | 3743 / 632 / 459 |
| 3 | planner | read_source, cursor 100, limit 100 | 14.397 | 3907 / 284 / 162 |
| 4 | planner | synthesize | 9.848 | 4624 / 311 / 301 |
| 5 | synthesizer | initial, success | 235.254 | 5486 / 14259 / 7148 |
| 6 | verifier | timeout, no report | 120.012 | unknown |
| 7 | planner | synthesize | 12.752 | 4543 / 322 / 312 |
| 8 | synthesizer | refresh, running at manual abort | unknown | unknown |

Total 448.460 s; completed model calls 413.370 s (92.2%); other runtime 35.090 s.
The source reads cover different pages; no identical duplicate reads exist.
No tool result, human input or verifier finding arrived between calls 5 and 8.
There is no calculation-reference blocker; the persisted brief has `calculations=[]`.

## Actual verifier request

The context is 23,394 serialized characters / 23,525 UTF-8 bytes:

| Field | Serialized characters |
| --- | ---: |
| claim_register | 15,685 |
| brief_payload | 5,261 |
| process_context | 724 |
| tool_trace | 798 |
| source_relevance | 347 |
| bound_hashes | 310 |
| decision_question | 121 |
| analysis_replays | 2 (`[]`) |

JSON object keys and separators account for the remaining characters.
There are 25 claims, including 11 server-derived critical claims, with source
locators and revision hashes. The complete brief contains question/scope,
problem, two hypotheses, four options, recommendation, six risks/unknowns,
validation step and an empty calculations list. Nothing is silently omitted
from review. The trace contains references/hashes and parameters, not full
ToolResult contents or duplicated evidence bodies. There are no analysis
replays because the run used only reads and search. Claims plus brief account
for about 90% of the context; this is package size, not a replay explosion.

The stored independent instruction is `vs1-verifier-v5`, 1,667 characters;
the frozen strict output schema is `vs1-verifier-schema-v5`, 986 characters.
It requests `read_requests`, `findings`, `source_references_valid`, and
`checked_critical_claims`; it does not request a rewritten package.
The instruction reviews provenance, epistemic status, recommendation strength,
counterevidence, critical claims and reproducible calculations. Missing concrete
source passages may be requested independently using `read_requests`.

Effective parameters: timeout 120 s, max output 16,384 tokens, reasoning medium,
temperature 0.1, OpenRouter with DeepInfra FP8 only, no fallbacks, required schema
parameters, denied data collection and ZDR. The transport sends a normal
non-streaming JSON request with excluded reasoning text. Its bounded response
reader enforces a wall-clock deadline, including a slowly arriving response body.

This historical timeout has no response diagnostics, usage, returned model or
accepted payload. The code records a generic `timeout` for either waiting for
HTTP response or reading its body. Therefore whether headers/body had arrived,
provider queue time, generation progress, and provider-internal reasoning latency
are **unknown**. A timeout alone does not establish that 120 s is too short or
that removing review data would improve latency. No tuning is justified by this
record, and no provider pinning, review context or timeout changes are made.

## Root cause of the recovery failure

`_handle_provider_failure()` grants one role-specific transient retry and
returns RUNNING. The next `advance_investigation()` previously only recognized
a direct synthesizer retry. `_verifier_repair_due()` correctly returns false
without an `InvestigationVerifierReport`. This leaves the generic planner as
the next action source. Its new `synthesize` decision calls the synthesizer.

`_synthesis_mode()` selects `refresh` as its fallback after successful synthesis
when there is no new evidence, concrete verifier rejection or package blocker.
Unlike initial synthesis, this mode includes the existing register, brief and
source relevance. Their 21,286 characters explain the entire context increase
from 10,703 to 31,989. This is an unnecessary new package, not meaningful recovery.

## Deterministic fix

1. A fresh transient failed verifier ModelCall goes directly to the same verifier
   role for one retry. Existing per-role failure counting and budgets apply.
2. A second consecutive provider failure terminates FAILED with technical reason,
   provider error code, role and attempt count. It does not manufacture findings.
3. Initial and repeated verification share the same verification/policy handler.
   Successful review still must satisfy all existing READY gates.
4. Additionally, an unchanged complete successful synthesis with missing/stale
   verification goes directly to review before the planner. This also prevents
   unnecessary refresh after an interrupted handoff. New tool/human information
   still returns to normal planning; a current failed review retains priority
   for the existing synthesis repair path.

Only execution/loop semantics change: `vs1-agent-loop-v18` becomes v19. Prompt,
schema, policy, budget and transport contracts are unchanged. Historical runs
remain readable; frozen v18 runs cannot silently continue under v19.

Regression coverage uses the production provider-call persistence and loop path:
direct retry to success/READY, repeated identical/different transient failures,
identical review context and package hashes across retry, no planner/synthesizer
hop, and unchanged complete package review without refresh. Existing concrete
verifier-finding repair and #86/#94 tests remain required.

Initial synthesis latency remains a separate measured problem: 235.254 s,
14,259 output tokens including 7,148 reasoning tokens and 18,919 visible output
characters. This fix removes redundant synthesis; it does not claim to reduce
the latency of that initial generation. Exactly one fresh product browser run
is permitted after green full CI; no toy probes or production probe series.

## Follow-up: lossless provenance transport

The subsequent real browser run `39645c1d-2b24-4214-855c-7ab79af4e17d`
reached READY in 365.071 s. Model calls consumed 357.592 s (98%): initial
synthesis 214.611 s, independent verification 95.992 s, four planner calls
46.989 s. There was one synthesis, no repair or technical retry. The package
contains 20 claims, 10 critical claims, four solution options, hypotheses,
risks/unknowns and a validation plan. This is the latency baseline after recovery.

The accepted synthesis already omits server-derived claim fields; arbitrary
claim limits or reduced review coverage would remove information. However,
its evidence_refs occupy 5,081 serialized characters, repeatedly generating
the same source UUID and 64-character revision hash for each locator. This is
a shared transport overhead in synthesis output and verifier input.

A deterministic source_reference_catalog now binds short handles to full
source IDs and hashes from the run's immutable snapshot, ordered by source ID.
Model references use `{source_ref:"S1",locator:{line:7}}`; the locator and all
content remain intact. The synthesizer response is expanded **before** existing
domain/provenance validation and before updating domain state. ModelCall still
stores the exact accepted wire payload and its hash for audit. The verifier
receives the complete package with this same reversible reference projection
and the catalogue; its report remains bound to the canonical package hashes.
Tool-result references, analysis replays, read requests, source-relevance keys,
all critical claim IDs and the complete decision brief remain present.
Wrong explicit revision hashes remain explicit; unknown/mixed aliases fail
the structured response contract instead of inferring or repairing provenance.

Read-only replay of the real baseline package, without provider calls:

| Data | Original characters | Compact characters | Reduction |
| --- | ---: | ---: | ---: |
| Synthesis output | 16,668 | 11,912 | 28.5% |
| Verifier context, including catalogue | 21,193 | 16,651 | 21.4% |

Decoding reproduces the full original package exactly. This demonstrates
less transported/generated data, **not yet a guaranteed latency reduction**.
The catalogue/instructions add a small input cost to initial synthesis.
Prior reasoning probes in #86 found low slower and less reliable in repeated
trials; reasoning effort, provider pinning, timeouts and output ceilings stay
unchanged. No facts, claims, source passages or checks are omitted.

Only the synthesis/verifier prompt contracts change to v14/v6, with context
profiles synthesis_compact_v2/verification_compact_v1. Schemas, loop, policy,
budgets and provider transport are unchanged. Frozen prompt/instruction hashes
prevent historical runs from silently continuing under the new wire contract.
Regression tests exercise wire auditing versus canonical persistence, identical
package hashes, all review data/critical claims, multi-source counterevidence,
text/CSV locators and rejected unknown/ambiguous handles. A single fresh real
browser acceptance run follows full green CI.
