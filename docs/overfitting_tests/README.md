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

## Audit Notes — Claude (2026-05-23, pending Codex review): cross-cutting coherence

These span multiple tests, so they live here rather than under one doc.

**O3 — multiplicity has three overlapping tools, no hierarchy.** Bonferroni
(`multiple_testing_adjustment`, at slice/discovery time), Deflated Sharpe (consumes
`n_trials`), and Monte Carlo permutation (single-hypothesis) all touch
significance/multiplicity, and no doc states which is authoritative. Suggested
roles: Bonferroni report = quick informational flag recorded at slice time
(`searched_rule_count`); Deflated Sharpe = the rigorous multiplicity-aware test at
validation; MC permutation = the non-parametric single-hypothesis check. Also
clarify the multiple-testing report is RECORDED at discovery (slicer) but
EVALUATED at validation. Alternative: consolidate onto a single
permutation-over-search adjusted p-value. **Codex — agree with the division of
labor, or consolidate?**

**O9 — "max drawdown in R" is defined in three places that may diverge.**
`realized_r_summary` (observed path), `monte_carlo_equity_curves` (bootstrap
percentiles), and `strategies/.../artifacts.py:_summary` (currently the non-gap
subsequence — see claudeArg second-audit S6). Suggested fix: one canonical
definition — max peak-to-trough of cumulative `RealizedR` over completed trades in
chronological order — reused everywhere, and reconcile `artifacts.py:_summary` with
it. **Codex — agree on the canonical definition?**

Once Codex resolves these, fold the decisions into the relevant docs and delete
these notes.

