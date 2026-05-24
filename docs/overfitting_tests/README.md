# Overfitting And Validation Test Planning

This folder defines the validation tests to rebuild from the old repo.

The tests are not a phase framework. They are small validators that consume
standard artifacts or rerun frozen strategies under controlled conditions.

## Test Groups

CSV-only tests:

- [realized_r_summary.md](realized_r_summary.md)
- [monte_carlo_permutation.md](monte_carlo_permutation.md)
- [monte_carlo_equity_curves.md](monte_carlo_equity_curves.md)
- [deflated_sharpe.md](deflated_sharpe.md)
- [minimum_backtest_length.md](minimum_backtest_length.md)
- [multiple_testing_adjustment.md](multiple_testing_adjustment.md)

Backtest-rerun tests:

- [walk_forward_reruns.md](walk_forward_reruns.md)
- [parameter_nudge_stability.md](parameter_nudge_stability.md)
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

Plain Monte Carlo permutation on validation trades is a single-hypothesis
non-parametric check of the frozen child. It does not adjust for the discovery
search unless it explicitly reruns the full search inside each permutation.

## Drawdown Definition

Max drawdown in R means max peak-to-trough decline of cumulative `RealizedR` in
chronological trade order.

Each artifact must name the population used for the drawdown. Current standard
populations are:

- `completed_non_gap`: completed trades excluding `ExitReason = end_of_data`
  and `HoldCrossesGap == true`
- `all_completed`: completed trades excluding only `ExitReason = end_of_data`
