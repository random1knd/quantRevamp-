# Overfitting And Validation Test Planning

This folder defines the validation tests to rebuild from the old repo.

The tests are not a phase framework. They are small validators that consume
standard artifacts or rerun frozen strategies under controlled conditions.

## Test Groups

Trade-result tests:

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
  [parameter_nudge_stability.md](parameter_nudge_stability.md)
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

The current i.i.d. Monte Carlo centered bootstrap on validation trades is a
single-hypothesis non-parametric diagnostic of the frozen child. It does not
adjust for the discovery search, and it does not preserve trade-outcome
dependence. For a future positive candidate, the promotion gate must use the
predeclared dependence-aware block-bootstrap policy in
`monte_carlo_centered_bootstrap.md`.

## Deferred Until A Real Positive Candidate

Bucket A engine status:

- Block bootstrap is built as pure engine-only code. It is not wired to a
  strategy runner, artifact writer, or promotion decision. Spec:
  [monte_carlo_centered_bootstrap.md](monte_carlo_centered_bootstrap.md).
- Block permutation is built as pure engine-only code. It is not wired to the
  slicer, artifact writer, or promotion decision. Spec:
  [multiple_testing_adjustment.md](multiple_testing_adjustment.md).

Deferred items:

- **Block-permutation real-data use.** The engine exists, but the current real
  discovery `context_trades.csv` has no session key such as `SessionDate_ET`.
  It is deferred because running the engine without a real session key would
  either derive hidden sessions or use the wrong block unit. It is unblocked by a
  reviewed artifact-schema change that persists the session key, followed by a
  separate wiring step. Frozen spec:
  [multiple_testing_adjustment.md](multiple_testing_adjustment.md).
- **Structure-preserving within-session block market-data permutation.** The
  current single-bar shuffle is invalid as an edge-validating null for this
  mean-reversion family because it manufactures regression-to-the-mean. It is
  deferred until a real positive mean-reversion candidate needs market-sequence
  evidence. It is unblocked by freezing the within-session block policy before
  inspecting that candidate's result. Frozen spec:
  [market_data_permutation.md](market_data_permutation.md).
- **Promotion aggregator and typed `test_role` guard.** New reports should carry
  `test_role` when they are created, but old artifacts are not retrofitted. The
  guard is deferred because it belongs with the aggregator; building it alone
  would create framework surface without a promotion design. It is unblocked by
  a real positive candidate that needs one combined promote/reject decision.
  Stacking several `p <= 0.10` checks is not itself a real 0.10 error bar.
  Relevant specs:
  [monte_carlo_centered_bootstrap.md](monte_carlo_centered_bootstrap.md) and
  [multiple_testing_adjustment.md](multiple_testing_adjustment.md).
- **6E session-relative timing gates.** Current 6E checks use frozen literal NQ
  timing gates as a transfer stress test, not as an FX timing thesis. They are
  deferred until a real EUR/USD candidate exists. They are unblocked by a
  pre-discovery decision on whether timing gates are session-relative for that
  candidate. Spec:
  [cross_instrument_validation.md](cross_instrument_validation.md).
- **Final 20% test (Cycle D).** This one-shot capstone touches the final-test
  split and is unauthorized. It is deferred until the user explicitly approves a
  frozen candidate for final-test access. Frozen partial-tail handling for
  `2026-03-06` is documented in
  [cross_instrument_validation.md](cross_instrument_validation.md).

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
