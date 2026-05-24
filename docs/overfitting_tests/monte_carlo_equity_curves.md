# Monte Carlo Equity Curves

Purpose:

- estimate the range of possible equity paths from observed validation trades

## Inputs

- validation `trades.csv`
- `RealizedR`
- `random_seed`
- iteration count

## Code Shape

```text
shared/validation/equity_curves.py
```

Expected function:

```text
monte_carlo_equity_curves(realized_r, n_iter, random_seed)
```

## Approach

- assume validation trade returns are i.i.d. for the first implementation
- resample validation trade returns with replacement
- build synthetic equity curves
- report final equity and drawdown bands
- if trade-outcome autocorrelation or regime clustering appears material, use a
  block bootstrap that resamples contiguous trade blocks

## Output

- final equity percentiles
- max drawdown percentiles
- probability of positive total R
- random seed

## Split

Run on child validation trades.
