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
      within-session market tuple shuffle with a child-local rerun. The result
      shows single-bar permutation is invalid as an edge-validating null for
      this VWAP-fade mean-reversion family.
- [x] Time stability: implemented as one full-validation frozen-child trade
      generation bucketed by entry calendar month, quarter, and year.
- [x] Cross-instrument blueprint: design spec written. Implementation is
      deferred until review; ES is next, then 6E session model, then final
      test capstone.
- [ ] Cross-instrument implementation: deferred.
- [ ] Final 20% test: not run. Do not touch final-test data without an explicit
      labeled decision.

## Current Slice

Implemented Claude-approved cross-instrument blueprint design only:

- `docs/overfitting_tests/cross_instrument_validation.md`: rewritten from the
  stale strategy-callable helper shape into a pure-report shared helper plus
  child-local rerun design.
- Explicit lookup is limited to `NQ`, `ES`, and `6E`; no registry, framework, or
  generic multi-instrument layer.
- Accounting constants are separated from session structure.
- Behavioral thresholds remain frozen and identical across instruments.
- ES is specified as the behavior-neutral constants-swap case to build first.
- 6E remains blocked until the new overnight session model and mandatory sanity
  checks are implemented.

6E data-grounded session findings:

- file: `data/bars/5min/6E_all_5min.csv`
- rows: `979807`
- raw timestamp range: `2011-12-01 00:00:00` through
  `2025-12-24 18:40:00`
- raw timestamps are monotonic with zero duplicates
- treating source timestamps as UTC and converting to ET, the dominant full-file
  daily break is `16:55 -> 18:00`, seen `3362` times
- in the validation-like span `2018-04-18` through `2023-12-01`, that break is
  seen `1379` times
- proposed 6E session assignment is `(DateTime_ET + 6 hours).date`, with
  `18:00 ET` open, `16:55 ET` normal last bar open, and `276` normal 5-minute
  bars
- validation-like scan found `1226 / 1456` proposed sessions with exactly
  `276` bars
- early-close examples end at `12:55 ET`; one anomalous validation-era session
  has `277` bars and must be reported, not hidden

Next sequence:

- Cycle B: implement explicit lookup, rerun NQ through it and prove
  bit-identical behavior, then run ES.
- Cycle C: implement 6E session-date support and mandatory sanity checks, then
  run 6E.
- Cycle D: run final 20% capstone once, coverage-only, with predeclared
  partial-tail handling.

## Previous Slice

Implemented Claude-approved time-stability chunk:

- `docs/overfitting_tests/time_stability.md`: freezes the report-only spec,
  judged population, granularities, sparse floor, no-period-selection rule, and
  sign-safe concentration metrics.
- `shared/validation/time_stability.py`: pure trade-result summary over
  already-judged entry timestamps and RealizedR values. No strategy imports, no
  bars, no reruns.
- `strategies/vwap_zscore_fade/children/adx_q30_workflow_test/time_stability_run.py`:
  child-local runner that generates the frozen child validation trades once,
  filters to `completed_non_gap`, writes `time_stability_report.json`,
  `time_stability_report.csv`, and `run_config.json`.

Time-stability spec:

- judged population: `completed_non_gap`
- grouping timestamp: trade `entry_time`
- granularities: month, quarter, year
- sparse bucket floor: fewer than 20 trades is `insufficient`
- sign counts are across sufficient buckets only
- concentration metrics do not divide by signed total R
- selection policy: no period selection, no time-of-year filters

Real time-stability output:

- `data/results/vwap_zscore_fade/children/adx_q30_workflow_test/time_stability_20260528T121117Z`
- completed_non_gap trades: `1810`
- total R: `-252.69658546780727`
- year sign counts: 6 negative, 0 positive, 0 zero, 0 missing
- largest year by absolute total R: `2019`, total R
  `-59.64036184588306`
- largest-year absolute share: `0.23601570134188082`
- leave-2019-out total R: `-193.0562236219242`

Read together with walk-forward: the child is negative across every sufficient
calendar year, not just in one bad year. This remains coverage-only context for
a rejected workflow child, not edge evidence.

## Prior Market-Permutation Result

- `data/results/vwap_zscore_fade/children/adx_q30_workflow_test/market_permutation_20260528T105820Z`
- observed mean R: `-0.13961137318663386`
- permuted mean R summary: min `0.43475123285563155`, mean
  `0.45059695928204013`, max `0.4699887548216543`
- one-sided positive p-value: `1.0`

Read that result as the headline: single-bar within-session shuffling
manufactures regression-to-the-mean toward VWAP and removes adverse momentum.
It is invalid as an edge-validating null for this mean-reversion strategy
family and is kept only as workflow coverage.

## Deferred On Purpose

- no block-bootstrap or block-permutation engine yet; a positive
  mean-reversion candidate must use a predeclared structure-preserving
  within-session block permutation before any market-permutation result can be
  treated as meaningful edge validation
- no cross-instrument implementation until the blueprint is reviewed
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

- Cross-instrument blueprint cycle is doc-only; no new implementation tests.
- Full suite: 340 passed.
- 6E data-shape scan completed and recorded in
  `docs/overfitting_tests/cross_instrument_validation.md`.
- `git diff --check`: no whitespace errors; only CRLF conversion warnings.

Previous time-stability verification:

- Focused time-stability tests: 4 passed.
- Real time-stability runner completed and wrote
  `time_stability_20260528T121117Z`.
- No final-test rows were passed to the strategy. `load_validation_bars()` reads
  the source CSV to compute/assert frozen split boundaries, then slices to
  validation before the child rerun.

## Standing Governance Reminders

- Single-column discovery is locked for this campaign.
- Do not retune to manufacture a candidate.
- Slicer/child/validation must not touch final-test data.
- Keep strategy behavior inside the strategy folder.
- Shared code should stay pure math or artifact comparison, not trading
  orchestration.
- Codex writes `codexArg`; Claude writes `claudeArg`.
