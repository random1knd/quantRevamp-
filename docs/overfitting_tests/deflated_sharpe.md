# Deflated Sharpe Ratio

Purpose:

- adjust Sharpe-like evidence for non-normal returns and multiple testing

## Inputs

- validation `RealizedR`
- candidate Sharpe or selection-score distribution from the slicer
- number of searched or tested variants

## Code Shape

```text
shared/validation/deflated_sharpe.py
```

Expected function:

```text
deflated_sharpe(realized_r, candidate_sharpes)
```

## Approach

- define per-trade Sharpe as `mean(RealizedR) / std(RealizedR)`, not annualized
- compute skewness and kurtosis from validation `RealizedR`
- estimate the expected best trial result from the persisted candidate Sharpe
  distribution
- report the deflated Sharpe statistic and its assumptions

## Rule

Do not fake `n_trials=1` when the slicer searched many rules. Use the mandatory
candidate score distribution where applicable.

If the slicer did not persist candidate scores or an equivalent Sharpe
distribution, DSR is unavailable for that candidate rather than approximated
from rule count alone.
