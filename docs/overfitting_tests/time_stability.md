# Time Stability

Purpose:

- report whether validation performance is concentrated in one period

## Status

Useful, but secondary to walk-forward reruns.

## Inputs

- validation `trades.csv`
- timestamps
- `RealizedR`

## Code Shape

```text
shared/validation/time_stability.py
```

## Approach

- summarize the existing validation trades by month, quarter, or year where
  data supports it
- report whether returns are concentrated in a short period

`walk_forward_reruns` reruns the frozen child in chronological windows of the
validation bars. `time_stability` is a CSV summary of existing validation
trades and does not rerun the strategy.

## Rule

This is reporting context. It should not mine new filters on validation data.
