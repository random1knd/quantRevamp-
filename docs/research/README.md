# Research Library

This folder preserves the useful research material from the old repo: formulas,
intuition, implementation notes, thresholds, and caveats.

These notes are not an architecture. They should inform isolated strategies,
indicator implementations, slicing reports, and validation tests.

Some preserved notes still use old names such as `bootstrap`, `bp`, `pre-filter`,
or `gate`. Treat those as historical source-language only. Do not rebuild a
universal bootstrap surface from them; translate any useful idea into explicit
strategy-owned code or a small tested shared math function.

## How To Use These Notes

1. Start from a strategy thesis.
2. Read only the notes needed by that strategy.
3. Port the required indicators as small tested functions.
4. Record only the context columns the strategy needs or intentionally wants to
   slice later.
5. Treat any discovered filter as a new hypothesis that must survive
   validation.

Do not recreate the old universal bootstrap from these notes.

## Study Index

### Entry And Stretch Measures

- `zscore_methods.md`
- `ornstein_uhlenbeck.md`
- `kalman_filter.md`
- `half_life.md`

### Regime And Stationarity

- `adf_test.md`
- `variance_ratio.md`
- `autocorrelation_regime.md`
- `hidden_markov_models.md`
- `cusum_changepoint.md`

### Order Flow And Microstructure

- `order_flow_imbalance.md`
- `vpin.md`
- `kyles_lambda.md`
- `imbalance_bars.md`
- `amihud_illiquidity.md`
- `rolls_effective_spread.md`

### Volatility And Momentum

- `garch_volatility.md`
- `tsmom_momentum.md`
- `advanced_data_points.md`

### Timing Triggers

- `triggers/absorption.md`
- `triggers/delta_reversal.md`
- `triggers/flow_exhaustion.md`
- `triggers/ofi_flip.md`
- `triggers/candle_rejection.md`
- `triggers/momentum_deceleration.md`
- `triggers/volume_climax.md`

### Validation

- `robustness_validation.md`

## Current Inventories

The curated current inventories live outside this research folder:

- `../inventories/strategies.md`
- `../inventories/triggers.md`
- `../inventories/indicators.md`
- `../inventories/validation_tests.md`
