# Monte Carlo Significance: Centered Bootstrap

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
centered_bootstrap_mean_report(
    realized_r,
    *,
    n_iter,
    random_seed,
    sidedness="one_sided_positive",
    include_null_values=False
)
```

## Approach

- define the score as mean `RealizedR`
- compute the actual score from the uncentered realized-R series
- build the null by centering the series on zero and bootstrapping with
  replacement for `n_iter` iterations
- this v0 implementation uses the centered bootstrap null
- do not use plain reordering of a fixed realized-R series for a mean-based
  score, because reordering does not change the mean
- default p-value is one-sided for positive edge: fraction of null means greater
  than or equal to the actual score
- if `sidedness = two_sided`, use the fraction of absolute null means greater
  than or equal to the absolute actual score

## Future Dependence-Aware Method

The current centered bootstrap assumes validation trades are i.i.d. The strategy
filter does not remove this dependence risk: it selects which trades are
included, but it does not make their outcomes time-independent.

For a future positive candidate, significance must use a predeclared
dependence-aware bootstrap before the result is trusted. The i.i.d. centered
bootstrap remains a diagnostic; it is not the promotion gate for a positive
candidate.

Frozen first block policy:

- statistic: mean `RealizedR`
- sidedness: one-sided positive
- block unit: one whole session, containing that session's ordered
  `completed_non_gap` validation trades
- resampling scheme: sample sessions with replacement until the resampled
  session count equals the observed session count
- replicate size: accept the variable total trade count produced by the drawn
  sessions
- replicate score: mean `RealizedR` over all trades in the drawn session blocks
- null: subtract the observed mean `RealizedR` from each trade before
  resampling, matching the current centered-bootstrap null family
- p-value: plus-one smoothed, `(1 + null_count_at_or_above_observed) /
  (1 + n_iter)`
- `n_iter` and `random_seed`: fixed before the run and recorded in the artifact

Minimum session-count caveat:

- a block-bootstrap p-value needs enough independent session blocks to be
  trustable
- with one non-empty session, centering produces an all-zero null and the
  p-value is only a sign check
- with only a handful of sessions, the null is coarse and highly sensitive to
  which sessions are drawn
- whoever wires the engine must enforce a predeclared session-count floor before
  reading significance, mirroring the intent of
  `minimum_trade_count_policy.md`

Fallback is allowed only if session-level trade counts make whole-session blocks
unusable. The fallback must be declared before seeing the positive candidate's
result and must specify contiguous trade-block length, circular versus
non-circular sampling, replicate sizing, sidedness, `n_iter`, and `random_seed`.

The dependence-aware method applies both to the significance p-value here and to
the equity-curve / drawdown bands in
`docs/overfitting_tests/monte_carlo_equity_curves.md`.

Do not wire or run this for the current negative workflow child. Its existing
i.i.d. reports remain coverage-only and already carry the workflow-test label.

## Output

- actual score
- null distribution summary
- p-value
- sidedness
- random seed
- iteration count

## Split

Run on child validation trades, not discovery trades.
