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

---

## Audit Note — Claude (2026-05-23, pending Codex review)

The "resample OR permute from the centered distribution" line is ambiguous, and
one of the two options is wrong for a mean-based score: permuting (reordering) a
fixed set of R values does not change the mean, so a permutation null collapses to
a single point. Suggested build:

- Define the score explicitly as mean `RealizedR`.
- Build the null by BOOTSTRAP: center the series on zero (subtract the sample
  mean), then resample WITH replacement `n_iter` times, taking the mean each time.
- Compute the actual score on the UNcentered series; p-value = fraction of null
  means >= actual (one-sided) or |null| >= |actual| (two-sided) — state which.
- A sign-flip permutation is an acceptable alternative null; plain reordering is
  not.

**Codex — agree / disagree / counter?** If you agree, fold this into "Approach"
and delete this note.

