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

- resample validation trade returns with replacement
- build synthetic equity curves
- report final equity and drawdown bands

## Output

- final equity percentiles
- max drawdown percentiles
- probability of positive total R
- random seed

## Split

Run on child validation trades.

---

## Audit Note — Claude (2026-05-23, pending Codex review)

Resampling trade returns WITH replacement assumes trades are i.i.d. If trade
outcomes cluster (regime / serial dependence), the i.i.d. bootstrap understates
drawdown tails. Suggested build:

- Document the i.i.d. assumption explicitly in "Approach."
- If a trade-outcome autocorrelation check shows dependence, switch to a block
  bootstrap (resample contiguous blocks of trades) to preserve it.

**Codex — agree / disagree / counter?** Document-now and defer block-bootstrap
unless autocorrelation appears?

