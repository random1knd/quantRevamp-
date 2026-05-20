# Indicator Inventory

This is a porting backlog, not a universal bootstrap.

Only port an indicator when an active strategy or validator needs it. Each
ported indicator should have explicit parameters and a small test.

Detailed family plans live in `../indicators/`.

**Porting rule:** This is a backlog ordered by general utility, not a
pre-slicing checklist. Do not port indicators speculatively. The right time to
add an indicator is after a slice reveals the existing ones are insufficient.
Port the smallest set the current evidence demands.

## Priority 1: Basic Execution And Risk

| Indicator | Purpose | Feasibility | Source |
|---|---|---|---|
| ATR | Stop sizing, volatility context, R normalization. | buildable | `research/advanced_data_points.md` |
| Session VWAP | Intraday fair-value anchor. | buildable | `research/zscore_methods.md` |
| VWAP distance | Mean-reversion stretch measure. | buildable | `research/zscore_methods.md` |
| Rolling z-score | Generic stretch measure. | buildable | `research/zscore_methods.md` |
| Robust z-score / MAD | Safer for noisy flow and volume series. | buildable | `research/zscore_methods.md` |

## Priority 2: First Mean-Reversion Strategies

| Indicator | Purpose | Feasibility | Source |
|---|---|---|---|
| Kalman mean and z-score | Dynamic mean estimate. | deferred | `research/kalman_filter.md` |
| O-U theta, mu, sigma, half-life, z-score | Mean-reversion speed and normalized extension. | deferred | `research/ornstein_uhlenbeck.md`, `research/half_life.md` |
| ADF p-value | Stationarity check for deviations or residuals. | buildable (context-only, slow) | `research/adf_test.md` |
| Variance ratio | Distinguish mean-reverting vs trending behavior. | buildable | `research/variance_ratio.md` |
| Autocorrelation | Quick regime context. | buildable | `research/autocorrelation_regime.md` |

## Priority 3: Order Flow And Microstructure

| Indicator | Purpose | Feasibility | Source |
|---|---|---|---|
| Delta | Basic aggressive flow. | buildable | `research/advanced_data_points.md` |
| Delta velocity | Flow acceleration / exhaustion. | buildable | `research/advanced_data_points.md`, `research/triggers/flow_exhaustion.md` |
| OFI | Order-flow imbalance. Time-bar approximation - not equivalent to volume-bar or tick-level estimates. | approximation (context-only) | `research/order_flow_imbalance.md` |
| Absorption ratio | Flow vs price progress. Time-bar approximation - not equivalent to volume-bar or tick-level estimates. | approximation (context-only) | `research/triggers/absorption.md` |
| VPIN | Flow toxicity context. Time-bar approximation - not equivalent to volume-bar or tick-level estimates. | approximation (context-only) | `research/vpin.md` |
| Kyle lambda | Price impact per unit flow. Time-bar approximation - not equivalent to volume-bar or tick-level estimates. | buildable (proxy) | `research/kyles_lambda.md` |

## Priority 4: Context And Slicing

| Indicator | Purpose | Feasibility | Source |
|---|---|---|---|
| Realized volatility | Volatility regime and sizing context. | buildable | `research/garch_volatility.md` |
| Volume z-score | Climax and participation context. | buildable | `research/advanced_data_points.md` |
| Candle body / close position | Rejection and bar structure slicing. | buildable | `research/advanced_data_points.md` |
| Session phase | Time-of-day slicing. | buildable | `research/advanced_data_points.md` |
| Anchored VWAP / composite VWAP | DEFERRED: multi-anchor fair-value research; anchor rule not declared. | deferred | `research/advanced_data_points.md` |

## Rule

Do not build a function that computes all of these for every strategy. Build
small indicator functions and let each strategy decide what to call and record.
