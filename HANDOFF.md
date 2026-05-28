# Session Handoff - 2026-05-28

Point-in-time snapshot for resuming work. Overwrite/update each session; this is
a status snapshot, not a ledger. Active per-cycle review lives in `codexArg` /
`claudeArg`.

## What This Campaign Is

This is a workflow test, not a profit claim. The parent strategy
`vwap_zscore_fade` loses money; the goal is to drive the research pipeline end
to end with honest results at every stage. A losing or rejected outcome is a
valid completion.

## Session End (2026-05-28)

- All work committed and pushed: `origin/master` at `033f64b`. Working tree clean.
- The codex/claude review loop is paused for now (Codex budget exhausted). The
  code does not depend on the loop being live; resume by reading this file.
- Overfitting suite is COMPLETE and the cross-instrument blueprint (ES + 6E) is
  COMPLETE, all coverage-only on a rejected child.
- Only remaining pipeline step: the **final 20% test (Cycle D)**. It is NOT yet
  authorized — it touches the final-test split, so it needs an explicit go-ahead
  before running. Until then, the blueprint stands complete without it.
- What is deferred (and where its spec lives) is recorded in the "Deferred On
  Purpose" section below.

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
- [x] Cross-instrument blueprint: design spec written and Cycle B implemented
      for NQ/ES.
- [x] Cross-instrument Cycle B: explicit child-local NQ/ES/6E lookup, NQ
      lookup regression proof, and ES same-day RTH transfer report.
- [x] Cross-instrument Cycle C: 6E session-date model and mandatory sanity
      checks.
- [ ] Final 20% test: not run. Do not touch final-test data without an explicit
      labeled decision.

## Current Slice

Implemented Claude-approved cross-instrument Cycle C:

- `shared/data/bars.py`: default same-day behavior remains unchanged; added a
  narrow explicit `offset_after_session_open` policy for overnight sessions and
  an explicit mixed-contract mark mode for quarantine.
- `strategies/vwap_zscore_fade/children/adx_q30_workflow_test/strategy.py`
  and `indicators.py`: child-local session bounds can now be passed explicitly,
  preserving NQ/ES defaults and allowing 6E to use the full `18:00 -> 16:55 ET`
  session.
- `strategies/vwap_zscore_fade/children/adx_q30_workflow_test/cross_instrument_run.py`:
  now gates NQ bit-identity, ES Cycle B unchanged numbers, 6E session sanity,
  and hard no-tradeable-mixed-contract assertion before writing the 6E result.
- Mixed-contract 6E sessions are quarantined as untradeable roll sessions; no
  contract stitching was added.
- The 6E report carries the literal-gate caveat alongside the numbers.

Real Cycle B artifact:

- `data/results/vwap_zscore_fade/children/adx_q30_workflow_test/cross_instrument_es_20260528T134418Z`

NQ lookup proof:

- bit-identical: `true`
- trade count: baseline `1820`, lookup `1820`
- completed_non_gap count: baseline `1810`, lookup `1810`
- mean R: baseline `-0.13961137318663386`, lookup
  `-0.13961137318663386`
- trade-row SHA-256:
  `d935f1a27b144054403860c53eafe12985250e49f365b83683c2949f8809d7a5`

ES same-day RTH transfer result:

- trade count: `2375`
- completed_non_gap count: `2374`
- mean R: `-0.2708235375893883`
- total R: `-642.9350782372079`
- win rate: `0.37573715248525696`
- ADX kept fraction: `0.24325736464968153`
- interpretation: ES does not rescue the rejected workflow child; this remains
  coverage-only context and cannot select an instrument or promote an edge.

Real Cycle C artifact:

- `data/results/vwap_zscore_fade/children/adx_q30_workflow_test/cross_instrument_6e_20260528T144737Z`

Cycle C regression gates:

- NQ lookup bit-identical: `true`
- NQ trade-row SHA-256:
  `d935f1a27b144054403860c53eafe12985250e49f365b83683c2949f8809d7a5`
- ES Cycle B unchanged: `true`
- ES mean R remains `-0.2708235375893883`

6E sanity result:

- status: `pass`
- validation sessions: `1841`
- bar-count highlights: `276` bars = `1529`, `228` bars = `30`,
  `277` bars = `11`
- `2018-05-14` is a `277`-bar anomaly:
  `2018-05-13 18:00 ET -> 2018-05-14 17:00 ET`
- mixed-contract sessions quarantined: `22`
- mixed-contract excluded fraction: `0.011950027159152634`
- tradeable mixed-contract sessions: `0`
- VWAP reset canary: `1841` sessions checked, `0` failures
- zero/negative initial-risk trades: `0`

6E frozen-gate transfer result:

- trade count: `1915`
- completed_non_gap count: `1907`
- mean R: `-0.5415719496803157`
- total R: `-1032.777708040362`
- win rate: `0.3434714210802307`
- ADX kept fraction: `0.18258426966292135`
- interpretation: 6E does not rescue the rejected workflow child. The number
  reflects the arbitrary literal frozen-gate transfer, not EUR/USD thesis
  evidence.

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

## Deferred On Purpose (specs frozen, code intentionally not built)

Principle: everything here is edge-PROVING machinery. This child loses money, so
there is nothing to prove. Building these now would be premature and would invite
tuning them to a result. Each item below has a frozen written spec already in the
repo; the code is built only when a real positive candidate exists, against that
frozen spec. (Diagnostics that already run today cannot promote anything; the
deferred versions are the gates that can.)

- **Block-bootstrap engine** — dependence-aware significance gate (resamples whole
  sessions, not single trades). Spec frozen in
  `docs/overfitting_tests/monte_carlo_centered_bootstrap.md`. The i.i.d. centered
  bootstrap is a diagnostic only.
- **Block-permutation engine** — dependence-aware version of the slicer
  search-significance test. Spec frozen in
  `docs/overfitting_tests/multiple_testing_adjustment.md`. The full-shuffle
  permutation is a diagnostic only.
- **Structure-preserving (within-session block) market-data permutation** —
  required for a real mean-reversion candidate; single-bar shuffle is an invalid
  null (it manufactures mean-reversion). Spec frozen in
  `docs/overfitting_tests/market_data_permutation.md`.
- **Promotion aggregator** — would combine the separate test verdicts into one
  promote/reject decision. Not built and no dedicated design doc yet; stacking
  several `p<=0.10` gates is NOT a real 0.10 bar (correlated, lenient). Design it
  when a real candidate forces it.
- **6E session-relative timing gates** — the NQ timing gates were frozen literally
  as a stress test; a real EUR/USD candidate needs them reclassified for a ~24h
  session, decided pre-discovery. Noted in
  `docs/overfitting_tests/cross_instrument_validation.md`.
- **Final 20% test (Cycle D)** — not run. Runs once, on a frozen candidate, with
  partial-tail handling for `2026-03-06`. No final-test access until then.

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

- Focused cross-instrument tests:
  `python -m pytest tests\shared\validation\test_cross_instrument.py strategies\vwap_zscore_fade\children\adx_q30_workflow_test\tests\test_child_strategy.py strategies\vwap_zscore_fade\children\adx_q30_workflow_test\tests\test_cross_instrument_run.py`
  -> included in focused Cycle C checks.
- Focused Cycle C tests:
  `python -m pytest tests\shared\data\test_bars.py tests\shared\validation\test_cross_instrument.py strategies\vwap_zscore_fade\children\adx_q30_workflow_test\tests\test_child_strategy.py strategies\vwap_zscore_fade\children\adx_q30_workflow_test\tests\test_cross_instrument_run.py`
  -> 34 passed.
- Real Cycle C runner completed and wrote
  `cross_instrument_6e_20260528T144737Z`.
- Full suite: `python -m pytest` -> 349 passed.
- `git diff --check`: no whitespace errors; CRLF warnings only.
- No final-test rows were passed to the strategy. Cross-instrument Cycle C uses
  validation splits only.

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
