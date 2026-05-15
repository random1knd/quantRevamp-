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

