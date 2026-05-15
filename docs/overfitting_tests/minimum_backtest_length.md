# Minimum Backtest Length

Purpose:

- warn when a result has too few trades to trust

## Inputs

- validation `RealizedR`
- trade count
- observed mean and variance
- optional skew/kurtosis

## Code Shape

```text
shared/validation/minimum_backtest_length.py
```

Expected function:

```text
minimum_backtest_length(realized_r)
```

## Output

- actual trade count
- estimated required count, if available
- low-sample status

## Initial Policy

Use this starting policy before the first strategy run:

- fewer than 30 validation trades: insufficient evidence
- 30 to 99 validation trades: low-sample / experimental
- 100 or more validation trades: normal interpretation allowed

These thresholds can be revised only before looking at a specific candidate's
validation result.

## Rule

Low sample size must not silently pass only because a child beats the parent.
