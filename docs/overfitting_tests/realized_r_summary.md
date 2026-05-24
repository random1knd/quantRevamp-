# Realized-R Summary

Purpose:

- establish baseline trade outcome semantics before deeper tests

## Inputs

- validation `trades.csv`

Required fields:

- `InitialRisk`
- `RealizedR`
- `EntryTime`
- `ExitTime`

## Code Shape

```text
shared/validation/realized_r.py
```

Expected outputs:

- `trade_count`
- `completed_trade_count`
- `incomplete_trade_count`
- `mean_realized_r`
- `median_realized_r`
- `total_realized_r`
- `win_rate`
- `max_drawdown_r`
- `r_multiple_diagnostics`
- `minimum_trade_count_tier`
- `minimum_trade_count_policy`

## Rules

`RealizedR` is the headline metric. Touch-rate diagnostics do not replace it.

Max drawdown in R is max peak-to-trough decline of cumulative `RealizedR` in
chronological trade order. Reports must name whether they use
`completed_non_gap`, `all_completed`, or another explicit population.

Streak diagnostics are deferred and are not part of the current
`summarize_realized_r` output.
