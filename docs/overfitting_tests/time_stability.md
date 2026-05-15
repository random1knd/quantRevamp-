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

- summarize by month/quarter/year where data supports it
- report whether returns are concentrated in a short period

## Rule

This is reporting context. It should not mine new filters on validation data.

