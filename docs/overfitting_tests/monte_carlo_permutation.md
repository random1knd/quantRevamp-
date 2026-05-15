# Monte Carlo Permutation

Purpose:

- test whether observed validation returns look better than a zero-edge null

## Inputs

- validation `trades.csv`
- `RealizedR`
- `random_seed`
- iteration count

## Code Shape

```text
shared/validation/monte_carlo.py
```

Expected function:

```text
monte_carlo_permutation(realized_r, n_iter, random_seed)
```

## Approach

- center the realized-R series around zero
- resample or permute from the centered distribution
- compare actual score against simulated null scores

## Output

- actual score
- null distribution summary
- p-value
- random seed
- iteration count

## Split

Run on child validation trades, not discovery trades.

