# Market-Data Permutation

Purpose:

- test whether validation performance depends on the real market sequence
  structure

Status:

- coverage-only overfitting workflow check for the negative workflow-test child
- not a promotion gate
- cannot validate an edge

## Code Shape

Shared code stays pure:

```text
shared/validation/market_permutation.py
```

Expected shared functions:

```text
permute_market_bars(bars, random_seed, expected_bar_interval_minutes)
market_permutation_report(observed_mean_realized_r, permutation_summaries, n_iter, random_seed)
```

The shared module must not import a strategy or generate trades. The frozen
child rerun lives here:

```text
strategies/vwap_zscore_fade/children/adx_q30_workflow_test/market_permutation_run.py
```

## Frozen Spec

- statistic: mean RealizedR over the `completed_non_gap` judged population
- n_iter: 10
- random_seed: 0
- p-value: one-sided positive, plus-one smoothed:
  `(1 + count(permuted_mean_R >= observed_mean_R)) / (1 + n_iter)`
- null model: within-session, single-bar market tuple permutation
- interpretation: i.i.d.-style structure-destruction diagnostic,
  coverage-only

Mean-reversion warning:

- for VWAP-fade and related mean-reversion strategies, single-bar
  within-session shuffling manufactures regression-to-the-mean
- after an extreme bar is shuffled into a timestamp, the next bar is a random
  draw from the same session pool, so it tends to move back toward the session
  center/VWAP
- the same shuffle removes real adverse momentum that often follows extreme
  deviations and stops a fade out
- therefore this v0 single-bar shuffle is not a valid null for this strategy
  family; it is only workflow coverage for the current negative child

Permutation unit:

- shuffle whole-row market-value tuples inside each `SessionDate_ET`
- market-value columns are `Open`, `High`, `Low`, `Close`, `Volume`,
  `BidVolume`, `AskVolume`
- never move market-value tuples across sessions

Fixed skeleton:

- preserve `DateTime_ET`, `SessionDate_ET`, `SessionMinute_ET`, `Contract`,
  and `IsFirstSessionAfterContractChange` in their original sorted positions
- `DateTime_UTC` is also preserved when present
- moving whole market tuples preserves each bar's internal OHLC consistency and
  volume tuple consistency

Derived gap handling:

- recompute `BarGapMinutesFromPrevious` and `BarGapFromPrevious` from the
  preserved timestamp/session skeleton after the shuffle
- because timestamps are not permuted, the time-gap structure is unchanged, but
  the artifact records that the fields were recomputed rather than carried as
  stale derived columns

## Runner Rules

- use `load_validation_bars()` and its frozen split-boundary assert
- pass only validation bars to the child strategy
- do not access final-test rows for strategy generation
- do not mutate strategy parameters or thresholds
- do not select a permutation result, threshold, window, or path
- write `market_permutation_report.json`, `market_permutation_report.csv`, and
  `run_config.json`
- record input hash, code version, frozen child parameters, permutation spec,
  n_iter, and random seed

## Required Future Variant

A real positive mean-reversion candidate must not use this single-bar
permutation as an edge-validating market-data null. It must use a
structure-preserving method, such as within-session block permutation, that
keeps short-range path behavior intact enough to avoid manufacturing the
strategy's own mean-reversion signal.

Before any positive-candidate result is inspected, the block method must freeze:

- block length
- sampling/reassembly rule
- session-boundary handling
- statistic and p-value formula
- random seed and iteration count

Do not build that block engine for this negative workflow child.
