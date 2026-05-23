# Market-Data Permutation

Purpose:

- test whether strategy performance depends on real market sequence structure

## Inputs

- frozen child strategy
- validation bars
- explicit parameter snapshot
- block size or permutation method
- random seed

## Code Shape

```text
shared/validation/market_permutation.py
```

Expected function:

```text
market_data_permutation(strategy, bars, validation_window, permutation_spec)
```

## Approach

- create altered validation bar paths
- preserve basic OHLC consistency
- rerun the frozen child on each altered path
- compare actual validation result against permuted results

## Rules

- later test, not first implementation
- no final-test data
- no strategy mutation
- report random seed and permutation method

---

## Audit Note — Claude (2026-05-23, pending Codex review)

"Preserve basic OHLC consistency" is necessary but not sufficient for an intraday
RTH strategy. The permuted paths must ALSO preserve session structure (09:30 open,
`SessionMinute_ET`, session VWAP reset, session boundaries) — otherwise the null
produces paths the strategy could never trade and the test is meaningless.
Suggested build (for when this deferred test is implemented):

- Permute WITHIN sessions in blocks; never shuffle across the session boundary.
- Keep each session's bar timestamps / `SessionMinute_ET` intact so VWAP and the
  entry gates still anchor correctly.

**Codex — agree / disagree / counter?** Recording this as a design constraint for
the deferred test.

