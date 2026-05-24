# Monte Carlo Permutation

Purpose:

- test whether observed validation returns look better than a zero-edge null

## Inputs

- validation `trades.csv`
- `RealizedR`
- `random_seed`
- iteration count
- sidedness (`one_sided_positive` for the default edge test, or `two_sided`)

## Code Shape

```text
shared/validation/monte_carlo.py
```

Expected function:

```text
monte_carlo_permutation(realized_r, n_iter, random_seed, sidedness)
```

## Approach

- define the score as mean `RealizedR`
- compute the actual score from the uncentered realized-R series
- build the null by centering the series on zero and bootstrapping with
  replacement for `n_iter` iterations
- a sign-flip permutation is an acceptable alternative null
- do not use plain reordering of a fixed realized-R series for a mean-based
  score, because reordering does not change the mean
- default p-value is one-sided for positive edge: fraction of null means greater
  than or equal to the actual score
- if `sidedness = two_sided`, use the fraction of absolute null means greater
  than or equal to the absolute actual score

## Output

- actual score
- null distribution summary
- p-value
- sidedness
- random seed
- iteration count

## Split

Run on child validation trades, not discovery trades.
