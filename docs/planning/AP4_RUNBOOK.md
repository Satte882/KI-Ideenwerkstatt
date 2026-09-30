# AP4 Runbook

Issue: #107  
Frozen contract: `tests/fixtures/ap4_case_manifest_v1.json`

This runbook is intentionally small. It does not introduce a second workflow or benchmark platform.

## 1. Validate the freeze

Before any scored run:

```powershell
python manage.py ap4_evidence --show-contract
```

If this fails because source files or prompt/schema/runtime versions changed, do **not** silently update the manifest. Document the change as a pre-run contract decision.

## 2. Fresh manual E2E baseline

Run exactly the four baseline cases listed in the manifest:

- AP4-01
- AP4-02
- AP4-03
- AP4-04

For each case use the same:
- problem statement;
- source pack;
- business scope

that will later be used by the autonomous run.

Record only actual human work:
- active input;
- navigation;
- authority-decision time;
- post-draft review;
- post-draft correction;
- manually entered/changed canonical fields.

Do not use the historical VS1 baseline as the full #1 baseline.

## 3. Scored autonomous population

Run AP4-01 through AP4-08 exactly once in their frozen scored slots.

Important:
- real provider;
- current product path;
- desktop browser where the user interaction is part of the path;
- no pre-created SolutionOption, UseCase or DeliveryPackage;
- Non-AI and WAITING_HUMAN are valid outcomes when supported by the evidence.

A failure remains the scored result.

Do not rerun the same scored slot looking for a better outcome.

## 4. Record Evidence

Create one JSON object per run and append it with:

```powershell
python manage.py ap4_evidence `
  --records artifacts/ap4/evidence.jsonl `
  --append-record artifacts/ap4/records/<record>.json
```

The command rejects:
- changed source-pack hashes;
- changed frozen prompt/schema/runtime versions;
- duplicate scored records for the same case/path;
- malformed metric values.

A root-cause fix may create a separate `post_fix` record that references the earlier failed record. It does not replace the scored evidence.

## 5. Evaluate after each batch

```powershell
python manage.py ap4_evidence --records artifacts/ap4/evidence.jsonl
```

Primary scored metrics use only `phase=scored`. Post-fix runs remain visible but cannot improve the original score retroactively.

## 6. Hardening matrix

Use:

`tests/fixtures/ap4_hardening_evidence_v1.json`

First rerun the mapped regression tests on the current branch.

Do not create new provider runs for already-covered deterministic failure modes.

The only partial matrix item at freeze time is semantic handling of an irrelevant source; observe this in the frozen real-provider population.

## 7. Bug handling

For a reproducible defect:

1. keep the failed scored record;
2. identify root cause from persisted state/provider output;
3. apply the smallest fix;
4. run the affected regression tests;
5. run normal CI;
6. create a distinct post-fix run/record.

No general hardening sweep after every fix.

## 8. Blind Human Review

Reuse the redaction/anonymisation primitives from:

`ki_radar/accelerator/issue4_blind_review.py`

Compare neutralised autonomous and manual reference material outside the application if convenient.

The reviewer must not know which output is autonomous.

An LLM review is not a substitute. If no independent human reviewer is available, leave this criterion explicitly open.

## 9. Completion

AP4 is ready to close only when:
- all eight scored slots are documented;
- the four baseline pairs are documented;
- #1 metrics are evaluated;
- no open P0/P1 remains;
- full CI is green;
- Blind Human Review is documented, or its unavailability is explicitly escalated as the remaining external dependency.
