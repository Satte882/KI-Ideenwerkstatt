# #118 historical experiment audit

Parent: #106. Experiment: #118. Harness: #120. Separate quality issue: #117.

## Experiment

- v20 variant commit: `b7c7832f6436a487b4921fad68baa7a33466ef79`.
- v19 control commit: `b37e25b6508a6e5769785c72c2fc35ac1177fae2`.
- 20 variant + 5 timely control runs; no replacement runs.
- The six external originals from `C:\Users\user\Documents\issue118-evidence` were
  copied byte-for-byte. Run IDs, record hashes, frozen plan and review remain unchanged.
- This archive adds no provider runs and does not authorize adoption.

## Result

**NOT SUFFICIENTLY PROVEN — NOT ADOPTED**

G0.3 technically passed: 8/8 affected variant runs without `no_progress_loop`,
no new technical failure category. Nevertheless, 4/5 timely controls exceeded the
frozen AP1 noise sentinel: `comparison_status = not_sufficiently_proven`.
No runtime speedup is proven. Authoritative Human Review was not performed;
`review.json` remains `UNASSESSED`. Human Quality Review and Hard-Fail acceptance
remain open. A numerical zero in the unassessed export is not confirmed absence
of quality hard fails.

## AI preannotation — non-authoritative

The C2c files contain 5× FAIL preannotations and 3× UNCLEAR; explicit mapping
was complete in 3/8 and absent in 5/8. The #117 pattern was preannotated in 5/8.
These are AI annotations, not confirmed human quality verdicts. Full tool
provenance cannot be resolved from the export; that limitation does not establish
broken provenance. The AI preannotation does not justify another provider cycle
at this point and does not replace Human Review.

## #117

#117 was already observed in the v19 baseline. Its renewed AI preannotation in
v20 does not prove a regression caused by `source_read_coverage`. This rollback
does not fix #117. Mapping completeness remains a separate open quality block.

## Product decision

The rollback restores the last product planner/runtime contract unaffected by
#118: `vs1-agent-loop-v19`. It does not establish that v19 is error-free or
technically superior, or that v20 is technically incorrect. Historical v20 runs
and their positive G0.3 evidence remain unchanged. #118 stays open until review
and merge; #113 has not started.

## Historical test source and harness

`historical/test_issue_118_planner_source_coverage.py.txt` preserves the exact
v20 test source, SHA-256
`35ce5bf2b40146f231625dba92346a54597c625d00ca4abd36bb01fa6ac99528`,
matching the frozen C1 proof. It is an audit source, not an executable v19 test.
The original executable tests and v20 coverage implementation remain available
at the variant commit. The v20-only tests were removed from current collection
because their assertions require the non-adopted projection; they were not
relabelled as v19 proof. New rollback tests instead exercise the actual v19
context and v20 incompatibility.

The #120 plan/aggregate/record validation and historical arm bindings remain.
The fixture verifier accepts these exact archived source bytes only for the
historical variant commit when the original test file is absent. Fixture replay
requires v20. Variant execution under current v19 fails closed before provider
execution, even when check-only or explicit execution is requested. Checkout,
contract and budget guards remain in place. Preparation on v19 also rejects the
variant contract; no new plan was generated. Export cannot write inside this
archive; choose external output and review paths for any future historical audit.
Nothing was reaggregated or overwritten for this rollback.

## SHA-256 of external originals and archived copies

Git attributes disable text conversion for these files, including across
Windows/Linux checkouts. Scoped whitespace attributes recognize the original
CRLF endings and preserve the review packet's original Markdown hard breaks;
evidence is not cleaned to satisfy whitespace checks. The hashes below identify
the original bytes.

| File | SHA-256 |
|---|---|
| `plan.json` | `4cb4c2312c8459361055ef476cbf889519152e81087d9a6f65580394c819c5ba` |
| `c1-state-fixtures.json` | `d0f1b09a255ac084f0c6162f1bd257d726896f48eff035289b0f5466854b66ed` |
| `experiment.json` | `c4ec46d0b74e6add0b62199e6b2ab92a99b4660fb656ffb52011c8c7983663c7` |
| `review.json` | `2b3394c1330bf204254fd3b4d1a21f924722749db1c7d1e902f9e36140dddebf` |
| `C2C_8_RUN_REVIEW_PACKET.md` | `d56fbc0312dba4c7f654514148100067891b578ccd973348ee6734ae4343319f` |
| `C2C_8_RUN_PREANNOTATION.json` | `5f8a14797710f952f3524676c377105d014db09cded3e7b2ce223cc8ac9a3b5f` |
