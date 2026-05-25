# Session Handoff - 2026-05-25

Point-in-time snapshot for resuming work. Overwrite/update each session; this is
a status snapshot, not a ledger. Active per-cycle review lives in `codexArg` /
`claudeArg`.

## What This Campaign Is

This is a workflow test, not a profit claim. The parent strategy
`vwap_zscore_fade` loses money; the goal is to drive the research pipeline end
to end with honest results at every stage. A losing or rejected outcome is a
valid completion.

## Pipeline Progress

- [x] Discovery: parent run on the 30% split. Mean R is negative on the
      `completed_non_gap` population.
- [x] Slicer: single-column search, 42 rules. Verdict remains `no_candidate`;
      best filter is `SignalADX <= q30` with mean R
      `-0.08195238266039637`.
- [x] Demonstration child: `children/adx_q30_workflow_test/`, hand-written,
      copies parent behavior plus a causal ADX filter. It is labeled as a
      workflow-test child, not a discovered edge.
- [x] Validation: parent vs child on the 50% split. Child is rejected and
      validation can only emit an advance-to-overfitting-review decision, never
      final promotion.
- [x] Overfitting Stage B, CSV-based: realized-R summary, minimum trade count,
      centered bootstrap, and equity-curve bootstrap were run coverage-only on
      the child.
- [x] Stage C, slicer-side threshold-neighborhood report: implemented as a
      train-side, discovery-contaminated artifact check. It is coverage-only for
      the current `no_candidate` child and cannot validate an edge.
- [x] Stage C, child-rerun threshold nudge: implemented as a validation rerun
      over literal q20/q30/q40 ADX slicer thresholds. It is coverage-only and
      cannot select a new threshold.
- [x] Walk-forward rerun: implemented as eight predeclared whole-session
      validation windows. All eight windows are sufficient and all eight window
      means are negative.
- [ ] Stage D, market-data permutation: deferred.
- [ ] Time stability: deferred.
- [ ] Cross-instrument: deferred; needs instrument-specific constants.
- [ ] Final 20% test: not run. Do not touch final-test data without an explicit
      labeled decision.

## Current Slice

Implemented Claude-approved walk-forward chunk:

- `shared/validation/walk_forward.py`: pure helper that compares already-built
  window summaries. No strategy imports and no backtests.
- `strategies/vwap_zscore_fade/children/adx_q30_workflow_test/walk_forward_run.py`:
  child-local runner that loads validation bars once, cuts eight contiguous
  whole-session windows, reruns the frozen child per window, and writes
  `walk_forward_report.json` and `walk_forward_report.csv`.
- `docs/overfitting_tests/walk_forward_reruns.md`: corrected away from the old
  strategy-callable helper shape.
- `docs/overfitting_tests/cross_instrument_validation.md`: adds the 6E session
  model blocker before cross-instrument work resumes.
- `docs/overfitting_tests/monte_carlo_centered_bootstrap.md` and
  `docs/overfitting_tests/monte_carlo_equity_curves.md`: predeclare the future
  dependence-aware bootstrap requirement for positive candidates.

Real walk-forward output:

- `data/results/vwap_zscore_fade/children/adx_q30_workflow_test/walk_forward_20260525T162359Z`
- overall result: `reported_no_pass_fail`
- sparse windows: 0 of 8
- window mean signs: 8 negative, 0 positive
- mean R range: min `-0.22462478765408672`, max `-0.08342306329400517`
- ADX kept-fraction range: `0.23453070683661645` to
  `0.3016905071521456`

Deferred on purpose:

- no market-data permutation yet
- no time-stability report yet
- no cross-instrument build until the explicit market/session design is made
- no promotion aggregator until a real positive candidate exists

## Audit Fixes Already In This Working Tree

- Parent and ADX child reject unsorted bars before generating trades.
- Same-instrument validation can advance only to overfitting review; it cannot
  promote.
- Validation advance requires `normal_ge_100`, positive child mean R, and at
  least `0.05R` child-minus-parent mean edge.
- Literal threshold freeze policy is documented. Distribution-derived raw
  thresholds stay literal in holdout tests; re-derived holdout quantiles are
  diagnostics only.
- Same-session VWAP gap behavior is documented as a current workflow-test
  limitation.
- Current i.i.d. bootstrap reports remain coverage-only for this negative
  workflow child. A future positive candidate requires a predeclared
  dependence-aware bootstrap before trusting significance.

## Verification

- Focused walk-forward/child tests: 16 passed.
- Full suite: 328 passed.
- Real walk-forward runner completed and wrote
  `walk_forward_20260525T162359Z`.
- `git diff --check`: no whitespace errors; only CRLF conversion warnings.

## Standing Governance Reminders

- Single-column discovery is locked for this campaign.
- Do not retune to manufacture a candidate.
- Slicer/child/validation must not touch final-test data.
- Keep strategy behavior inside the strategy folder.
- Shared code should stay pure math or artifact comparison, not trading
  orchestration.
- Codex writes `codexArg`; Claude writes `claudeArg`.
