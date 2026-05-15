# Indicator Inventory

This is a porting backlog, not a universal bootstrap.

Only port an indicator when an active strategy or validator needs it. Each
ported indicator should have explicit parameters and a small test.

Detailed family plans live in `../indicators/`.

## Priority 1: Basic Execution And Risk

| Indicator | Purpose | Source |
|---|---|---|
| ATR | Stop sizing, volatility context, R normalization. | `research/advanced_data_points.md` |
| Session VWAP | Intraday fair-value anchor. | `research/zscore_methods.md` |
| VWAP distance | Mean-reversion stretch measure. | `research/zscore_methods.md` |
| Rolling z-score | Generic stretch measure. | `research/zscore_methods.md` |
| Robust z-score / MAD | Safer for noisy flow and volume series. | `research/zscore_methods.md` |

## Priority 2: First Mean-Reversion Strategies

| Indicator | Purpose | Source |
|---|---|---|
| Kalman mean and z-score | Dynamic mean estimate. | `research/kalman_filter.md` |
| O-U theta, mu, sigma, half-life, z-score | Mean-reversion speed and normalized extension. | `research/ornstein_uhlenbeck.md`, `research/half_life.md` |
| ADF p-value | Stationarity check for deviations or residuals. | `research/adf_test.md` |
| Variance ratio | Distinguish mean-reverting vs trending behavior. | `research/variance_ratio.md` |
| Autocorrelation | Quick regime context. | `research/autocorrelation_regime.md` |

## Priority 3: Order Flow And Microstructure

| Indicator | Purpose | Source |
|---|---|---|
| Delta | Basic aggressive flow. | `research/advanced_data_points.md` |
| Delta velocity | Flow acceleration / exhaustion. | `research/advanced_data_points.md`, `research/triggers/flow_exhaustion.md` |
| OFI | Order-flow imbalance. | `research/order_flow_imbalance.md` |
| Absorption ratio | Flow vs price progress. | `research/triggers/absorption.md` |
| VPIN | Flow toxicity context. | `research/vpin.md` |
| Kyle lambda | Price impact per unit flow. | `research/kyles_lambda.md` |

## Priority 4: Context And Slicing

| Indicator | Purpose | Source |
|---|---|---|
| Realized volatility | Volatility regime and sizing context. | `research/garch_volatility.md` |
| Volume z-score | Climax and participation context. | `research/advanced_data_points.md` |
| Candle body / close position | Rejection and bar structure slicing. | `research/advanced_data_points.md` |
| Session phase | Time-of-day slicing. | `research/advanced_data_points.md` |
| Anchored VWAP / composite VWAP | Multi-anchor fair-value research. | `research/advanced_data_points.md` |

## Rule

Do not build a function that computes all of these for every strategy. Build
small indicator functions and let each strategy decide what to call and record.
