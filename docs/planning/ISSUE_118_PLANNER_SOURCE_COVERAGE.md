# #118 Block C1: persistent planner source-read projection

Parent: #106. Selection gate: #112. Experiment: #118.

## Code evidence and scope

Historical baseline: `b37e25b6508a6e5769785c72c2fc35ac1177fae2`.
Implementation starts from main `c0f39053276085ecb6ea5c99d49027d8d59a2f80`.
The relevant planner/loop modules are unchanged between these commits.

At the historical baseline, `_planner_context()` reads all persisted steps in
descending sequence order. `_investigation_context()` retains only the latest five.
`sources` contains metadata and immutable content hashes, but no read state.
An early successful read therefore disappears from the planner input after five
later steps. Tool deduplication returns the existing successful step, leaving
the action/state fingerprint unchanged; the repeat guard eventually fails the run.
This confirms the mechanism recorded for AP4-02 R4 and AP4-04 R5 in #112/#118.

## Projection

Only `_investigation_context()` receives the new `source_read_coverage` list.
Each entry is derived from one persisted SUCCESS `read_source` step, ordered by
sequence, and contains:

- `sequence`, `source_id`, `snapshot_id`, `revision_hash`, `result_hash`;
- normalized request `cursor`, `limit`, `columns`;
- stored result `returned_count`, `end_cursor_exclusive`, `next_cursor`.

Source IDs must belong to this run's immutable snapshot. The stored result's
source and snapshot IDs must match; mismatches are omitted. Revision hashes come
from that snapshot, never from current external files. FAILED, DISCARDED and
RUNNING steps are excluded, including any retained results on those steps.

The returned range is zero-based `[cursor, end_cursor_exclusive)` in rows or lines.
Its end uses the actual stored item count, not the requested limit; byte limits
can shorten a page. Existing source locators use one-based row/line numbers.
For CSV, nonempty `columns` restrict coverage to those columns; `columns=[]`
means all columns in the immutable source metadata. Text reads cover lines.
`next_cursor=null` denotes the end reached by this read, including an empty read
beyond EOF. It does **not** assert that earlier rows/lines or other columns were
read. There is deliberately no `fully_read` flag or semantic sufficiency judgment.
Separate pages, overlaps and column selections remain separate entries.

No source contents, full result payloads, arbitrary progress payloads, model
rationales or attempt histories are copied into this projection. It does not
select synthesis, classify source relevance or replace existing evidence gates.
`recent_steps` stays at five. Synthesizer and verifier contexts are unchanged.

## Bound and determinism

The existing frozen run budget caps normal tool calls at 40 and verifier reads
at 40. Budget overrides can only reduce these limits. Every unique successful
read consumes one of those counters; identical successful requests reuse the
same step. Thus at most 80 small read entries can exist per run, without an
additional truncation cap that could lose old coverage again.

The maximum-budget regression executes 40 normal plus 40 verifier reads and
checks that sequence 1 survives, only five recent steps remain, no evidence
payloads enter the projection and its representative serialized size is below
50 KB. That size assertion is a fixture bound, not a universal byte cap: column
names and source column counts can affect entry size. Existing model-context and
input-budget checks continue to enforce the overall prompt capacity.

Projection ordering is deterministic. Recovery changes executor generation/token
but keeps successful steps and snapshot bindings; retrying a successful read
reuses its step. No database field or migration is needed.

## Contract version and rollback

Runtime/loop: `vs1-agent-loop-v19` → `vs1-agent-loop-v20`, because planner input
semantics changed. The loop version is already frozen in each execution snapshot
and checked before reserving a model call. Planner instruction `vs1-planner-v19`
and response schema `vs1-planner-schema-v16` remain unchanged; no prompt/schema
bump is needed for an unchanged instruction and action shape.

Old v19 runs remain historically readable. The existing contract guard rejects
their continuation under v20 with `execution_version_unavailable`, before any
provider call. No historical execution snapshot or AP0/AP1 artifact is rewritten.
Current v20 runs recover/replay with the same projection. To continue v19 runs
or run baseline controls, use the original main commit in an isolated checkout
with its original contract. Do not relabel existing runs.

Rollback is a Git revert of this experiment commit (or deployment of the original
main commit), restoring both the v19 context and version. Under that rollback,
v20 runs likewise cannot silently continue as v19; their history stays intact.
Changing only a version string is not a valid rollback.

## Deterministic verification

`tests/test_issue_118_planner_source_coverage.py` covers both historical patterns
using the frozen AP4 source packs, six later successful steps, transport context
handoff, partial reads, pages and column selections, terminal suffix/empty pages,
byte-shortened reads, distinct sources, non-success statuses, mismatched result
bindings, immutable external-file snapshots, recovery/deduplication, deterministic
hashes, maximum budgets, old-contract rejection and authorization.

AP0 contract tests retain the frozen v19 baseline and explicitly assert the
selected v20 runtime difference; no acceptance gates or frozen fixtures change.
The AP4 historical-summary test explicitly asserts that frozen v19 post-fix
records cannot be loaded as current v20 evidence, then evaluates the original
human-time assertions under a test-scoped historical v19 reader. The production
evidence validator and archived record versions are unchanged.
The existing no-progress guard remains unchanged at repeat > 3.

Local targeted verification on PostgreSQL: **210 passed, 2 skipped** (Windows
symlink privileges), including all 16 new #118 cases and the existing source,
analysis, planner, runtime, policy, harness, hardening, convergence and AP0/AP1
tests. Ruff lint/format, Django checks, migration drift check and Bandit pass.
The initial SQLite run exposed an existing raw-SQL UUID tamper-test limitation;
PostgreSQL verifies that test and both concurrency tests successfully. The local
prompt file was normalized to its unchanged Git LF blob for the frozen AP0 hash
check; there is no prompt change in the commit.

REALE PROVIDER-RUNS: 0

No real variant runs or baseline controls were executed in Block C1. Tests prove
the state projection and compatibility boundaries, not future planner behavior,
runtime gains, quality acceptance or experiment adoption. The real experiment
and subsequent #106 gate remain separate work; #117 remains separately tracked.
