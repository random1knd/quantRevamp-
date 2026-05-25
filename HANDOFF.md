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
- [ ] Stage C, child-rerun threshold nudge: deferred to the next reviewable
      slice.
- [ ] Stage D, market-data permutation: deferred.
- [ ] Cross-instrument: deferred; needs instrument-specific constants.
- [ ] Final 20% test: not run. Do not touch final-test data without an explicit
      labeled decision.

## Current Slice

Implemented Claude-approved safe chunk:

- `shared/validation/threshold_neighborhood.py`: pure helper over already
  scored slicer rows. No strategy imports and no backtests.
- `strategies/vwap_zscore_fade/parent/threshold_neighborhood_run.py`:
  strategy-local artifact runner that reads `slice_report.csv`,
  `filter_candidate.json`, and `slicer_plan.json`, then writes
  `threshold_neighborhood_report.json` and
  `threshold_neighborhood_report.csv`.
- `strategies/vwap_zscore_fade/parent/slicer_artifacts.py`: artifact-layer
  `candidate_gate` now requires positive mean R, minimum kept count, adjusted
  p-value `<= 0.10`, and no outlier divergence before writing
  `candidate_status = candidate_selected`.

Deferred on purpose:

- no promotion aggregator until a real positive candidate exists
- no child-rerun threshold nudge until this slicer-side slice is reviewed

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

## Verification

- Focused tests for the new helper, runner, and artifact gate: 9 passed.
- Full suite: 317 passed.
- Current-campaign gate check in ignored `.tmp/slicer_gate_check_current`
  preserved the substantive slicer verdict:
  `no_candidate`, `best_mean_not_positive`, best rule
  `SignalADX__le__q30`, mean R `-0.08195238266039637`.
- `git diff --check`: no whitespace errors; only CRLF conversion warnings.

## Standing Governance Reminders

- Single-column discovery is locked for this campaign.
- Do not retune to manufacture a candidate.
- Slicer/child/validation must not touch final-test data.
- Keep strategy behavior inside the strategy folder.
- Shared code should stay pure math or artifact comparison, not trading
  orchestration.
- Codex writes `codexArg`; Claude writes `claudeArg`.
