# Session Handoff - 2026-05-28

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
- [x] Stage D, market-data permutation: implemented as a coverage-only
      within-session market tuple shuffle with a child-local rerun.
- [ ] Time stability: next cycle. CSV-only concentration check from existing
      validation trades; no rerun, no filter mining.
- [ ] Cross-instrument: deferred; needs instrument-specific constants.
- [ ] Final 20% test: not run. Do not touch final-test data without an explicit
      labeled decision.

## Current Slice

Implemented Claude-approved market-data permutation chunk:

- `docs/overfitting_tests/market_data_permutation.md`: corrected away from the
  rejected strategy-callable shared helper shape and freezes n_iter `10`,
  random seed `0`, statistic, permutation unit, p-value, and gap handling.
- `shared/validation/market_permutation.py`: pure prepared-bar permuter and
  pure report builder. No strategy imports and no trade generation.
- `strategies/vwap_zscore_fade/children/adx_q30_workflow_test/market_permutation_run.py`:
  child-local runner that loads validation bars via `load_validation_bars()`,
  reruns the frozen child over 10 permuted validation paths, and writes
  `market_permutation_report.json`, `market_permutation_report.csv`, and
  `run_config.json`.

Permutation spec:

- statistic: mean RealizedR over `completed_non_gap`
- unit: shuffle `Open`, `High`, `Low`, `Close`, `Volume`, `BidVolume`,
  `AskVolume` as whole-row tuples within each `SessionDate_ET`
- fixed skeleton: timestamps, session anchors, contract, and roll-session flag
  stay in original sorted positions
- gap fields: `BarGapMinutesFromPrevious` and `BarGapFromPrevious` are
  recomputed from the preserved timestamp/session skeleton
- p-value: one-sided positive, plus-one smoothed
- interpretation: i.i.d.-style structure-destruction diagnostic,
  coverage-only, not a promotion gate, and not a valid null for VWAP-fade
  mean-reversion edge validation

Real market-data permutation output:

- `data/results/vwap_zscore_fade/children/adx_q30_workflow_test/market_permutation_20260528T105820Z`
- observed completed_non_gap trades: `1810`
- observed mean R: `-0.13961137318663386`
- permuted mean R summary: min `0.43475123285563155`, mean
  `0.45059695928204013`, max `0.4699887548216543`
- permuted paths >= observed: `10 / 10`
- one-sided positive p-value: `1.0`

Read the result as the headline, not a footnote: single-bar within-session
shuffling manufactures regression-to-the-mean toward the session center/VWAP and
removes real adverse momentum after extreme deviations. That is exactly the
mechanical setup a VWAP-fade wants. The +0.45R permuted result is therefore a
warning that this v0 shuffle is invalid as an edge-validating null for
mean-reversion strategies. It is kept only as honest workflow coverage for this
negative child.

## Deferred On Purpose

- time-stability report is next
- no block-bootstrap or block-permutation engine yet; a positive
  mean-reversion candidate must use a predeclared structure-preserving
  within-session block permutation before any market-permutation result can be
  treated as meaningful edge validation
- no cross-instrument build until the explicit market/session design is made
- no promotion aggregator until a real positive candidate exists
- no final-test access

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

- Focused market-permutation tests: 5 passed.
- Full suite: 336 passed.
- Real market-permutation runner completed and wrote
  `market_permutation_20260528T104235Z`.
- No final-test rows were passed to the strategy. `load_validation_bars()` reads
  the source CSV to compute/assert frozen split boundaries, then slices to
  validation before the child rerun.
- `git diff --check`: no whitespace errors; only CRLF conversion warnings.

## Standing Governance Reminders

- Single-column discovery is locked for this campaign.
- Do not retune to manufacture a candidate.
- Slicer/child/validation must not touch final-test data.
- Keep strategy behavior inside the strategy folder.
- Shared code should stay pure math or artifact comparison, not trading
  orchestration.
- Codex writes `codexArg`; Claude writes `claudeArg`.
