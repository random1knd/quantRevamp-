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

- trade count
- mean `RealizedR`
- median `RealizedR`
- win rate
- total R
- max drawdown in R
- streaks
- incomplete trade count

## Rules

`RealizedR` is the headline metric. Touch-rate diagnostics do not replace it.

