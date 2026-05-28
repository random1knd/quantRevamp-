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
- for a future positive candidate, use the dependence-aware block-bootstrap
  policy predeclared in
  `docs/overfitting_tests/monte_carlo_centered_bootstrap.md` before trusting
  equity-curve or drawdown bands
- the same frozen block policy applies here: whole-session blocks first,
  centered null for significance, and block-resampled equity/drawdown paths
  before any positive candidate's result is trusted
- the strategy filter does not remove trade-outcome dependence; it only selects
  which trades are included

## Output

- `observed.equity_curve`
- `observed.final_equity_r`
- `observed.max_drawdown_r`
- `equity_curve_percentile_bands`
- `final_equity_distribution`
- `final_equity_distribution.probability_positive_total_r`
- `max_drawdown_distribution`
- `random_seed`
- `n_iter`

## Split

Run on child validation trades.
