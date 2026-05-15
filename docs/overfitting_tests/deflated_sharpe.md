# Deflated Sharpe Ratio

Purpose:

- adjust Sharpe-like evidence for non-normal returns and multiple testing

## Inputs

- validation `RealizedR`
- number of searched or tested variants
- skewness
- kurtosis

## Code Shape

```text
shared/validation/deflated_sharpe.py
```

Expected function:

```text
deflated_sharpe(realized_r, n_trials)
```

## Approach

- compute observed Sharpe-like statistic from realized R
- estimate adjustment using skewness, kurtosis, sample length, and trial count

## Rule

Do not fake `n_trials=1` when the slicer searched many rules. Use the mandatory
searched rule count where applicable.

