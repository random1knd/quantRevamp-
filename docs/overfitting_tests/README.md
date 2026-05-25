# Overfitting And Validation Test Planning

This folder defines the validation tests to rebuild from the old repo.

The tests are not a phase framework. They are small validators that consume
standard artifacts or rerun frozen strategies under controlled conditions.

## Test Groups

CSV-only tests:

- [realized_r_summary.md](realized_r_summary.md)
- [monte_carlo_centered_bootstrap.md](monte_carlo_centered_bootstrap.md)
- [monte_carlo_equity_curves.md](monte_carlo_equity_curves.md)
- [deflated_sharpe.md](deflated_sharpe.md)
- [minimum_trade_count_policy.md](minimum_trade_count_policy.md)
- [multiple_testing_adjustment.md](multiple_testing_adjustment.md)
- threshold-neighborhood report from
  [parameter_nudge_stability.md](parameter_nudge_stability.md)

Backtest-rerun tests:

- [walk_forward_reruns.md](walk_forward_reruns.md)
- child-rerun threshold nudge from
  [parameter_nudge_stability.md](parameter_nudge_stability.md) (deferred)
- [market_data_permutation.md](market_data_permutation.md)
- [cross_instrument_validation.md](cross_instrument_validation.md)

Later / optional:

- [sweep_parameter_stability.md](sweep_parameter_stability.md)
- [time_stability.md](time_stability.md)

## Split Rule

Discovery finds filters. Validation proves filters. Final test confirms once.

Most overfitting tests run on the 50% validation split after a child strategy is
created.

Final-test data must not be used for overfitting tests.

## Multiplicity Hierarchy

The primary search-adjusted evidence is a full-search permutation report when
candidate scores and the source discovery context are available. The report is
recorded with the slicer output because it describes the search that selected
the candidate.

Bonferroni-style adjustment is a secondary informational report when a raw
p-value exists. It does not replace out-of-sample validation.

Deflated Sharpe is a secondary validation statistic. It is available only when
the slicer persisted the candidate Sharpe or score distribution needed to
estimate the expected best trial result.

Monte Carlo centered bootstrap on validation trades is a single-hypothesis
non-parametric check of the frozen child. It does not adjust for the discovery
search.

## Threshold-Type Policy

Rerun tests must distinguish threshold types:

- scale-free thresholds, such as z-score levels or ATR multiples, remain frozen
  as literal values across validation, walk-forward, and cross-instrument tests
- distribution-derived raw thresholds, such as an ADX level selected from a
  discovery quantile, also remain frozen as literal child parameters for the
  candidate result
- re-derived quantiles on validation, walk-forward, cross-instrument, or final
  data are diagnostics only; they do not replace the frozen-child result

If a strategy wants a transferable relative-regime rule, it should trade a
causal percentile-rank or normalized feature from the start. Then the frozen
threshold is the scale-free rank value, not a raw threshold recalculated on
holdout data.

## Drawdown Definition

Max drawdown in R means max peak-to-trough decline of cumulative `RealizedR` in
chronological trade order.

Each artifact must name the population used for the drawdown. Current standard
populations are:

- `completed_non_gap`: completed trades excluding `ExitReason = end_of_data`
  and `HoldCrossesGap == true`
- `all_completed`: completed trades excluding only `ExitReason = end_of_data`
