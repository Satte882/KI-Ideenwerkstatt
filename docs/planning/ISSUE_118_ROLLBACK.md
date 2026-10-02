# Issue #118 — product rollback to v19 (C2d)

Parent #106; experiment #118; audit harness #120; separate quality bug #117.

## Anlass

#118 completed its real 20× v20 + 5× v19 experiment without replacement runs.
The frozen AP1 drift sentinel fired for 4/5 timely controls, so no adoptable
comparison exists. Human Review is not complete; the review template remains
UNASSESSED. The additional non-authoritative AI preannotation does not justify
another provider cycle at this point.

Decision: **NOT SUFFICIENTLY PROVEN — NOT ADOPTED**.

## Keine Fehlinterpretationen

- v20 has not been technically disproven.
- v19 is not error-free or proven technically superior.
- #117 is not fixed by this rollback; it predates v20.
- v20 G0.3 remains historically positive: 8/8 affected variant runs without
  `no_progress_loop`, no new technical failure category.
- The decision is `not sufficiently proven`, not `v20 is bad`.
- Human Quality Review and Hard-Fail acceptance remain open; AI preannotations
  do not establish confirmed quality failures or confirmed absence of hard fails.
- Full tool provenance is not resolvable from the export; broken provenance is
  not established by that export limitation.

## Aktiver Produktstand

After merge: `vs1-agent-loop-v19`.

`investigation_llm.py` restores the v19 planner context, limited to five recent
steps and without `source_read_coverage`; the unused v20 projection helper is
removed. `investigation_runtime.py` restores the matching v19 loop identifier.
Both product files match the historical v19 control commit. Prompts, synthesizer,
verifier, budgets and CSV mapping requirements are unchanged.

## Historische Evidence

Variant: `b7c7832f6436a487b4921fad68baa7a33466ef79`.

Control: `b37e25b6508a6e5769785c72c2fc35ac1177fae2`.

See [audit archive](../../artifacts/issue106/exp118/README.md) for byte-identical
plan, fixture proof, raw export, UNASSESSED review, C2c packet and preannotation,
plus per-file hashes and the exact historical v20 test source. Git attributes
preserve all frozen bytes. Original historical test assertions remain available
at the variant commit and in the audit source; current tests assert v19 instead.

## Rollback / compatibility

No database migration. No existing runs, execution snapshots, versions, IDs or
record hashes are modified. New investigations freeze v19. Correctly frozen v19
runs remain compatible with v19 recovery/planning. Historical v20 contracts are
rejected with `execution_version_unavailable` before a model call can be reserved;
there is no implicit contract conversion. The existing recovery fence may be
renewed, but it does not make a v20 execution contract compatible with v19.

The #120 historical harness remains available. Its original v20/v19 arm bindings
and plan hashes are unchanged. The current v19 checkout cannot execute a v20
variant or regenerate its C1 proof. The archived C1 proof remains verifiable via
the exact archived source bytes bound to the historical variant commit. Export
requires output paths outside the frozen archive. No experiment result was
reaggregated, no new plan was generated, and no provider runs were performed.

## Validation

Current contract tests cover new v19 runs, recovery/planner compatibility, both
affected source packs with the restored five-step context, historical v20
fail-closed behavior without relabelling, historical C1 proof, blocked variant
execution and archive overwrite protection. AP0 and AP4 tests reflect the restored
v19 product contract while retaining an explicit v20 evidence incompatibility
check. Actual local check and PostgreSQL suite results are reported in the PR.

## Folge — only after review and merge

1. Formally close #118.
2. Update #106 with the non-adoption decision.
3. Complete #113 without an adopted optimization.
4. Work on #117 separately afterwards.

This PR performs none of those follow-up actions and does not merge itself.
