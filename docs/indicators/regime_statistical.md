# Statistical Regime Indicators

Purpose:

- record whether the market looks mean-reverting, trending, or unstable around
  a trade

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `Hurst` | Rough persistence / mean-reversion estimate. | price or deviation series, window |
| `ADF_PValue` | Stationarity test p-value. | price/deviation series, window |
| `ADF_Stationary` | Boolean interpretation of ADF threshold. | `ADF_PValue`, threshold |
| `VR_q4` | Variance ratio at lag/q. | return series, q, window |
| `AC1` | Lag-1 autocorrelation. | return/deviation series, window |
| `RegimeScore` | Composite score from selected regime features. | explicit component list |

## Implementation Approach

Shared math can live in:

```text
shared/indicators/regime.py
```

Expected functions:

```text
rolling_autocorr(series, window, lag)
rolling_variance_ratio(series, window, q)
rolling_adf_pvalue(series, window)
hurst_estimate(series, window)
```

`RegimeScore` should not be implemented until the component formula is
strategy-approved. It is easy for a composite score to hide policy.

## Parameter Decisions

Each strategy must state:

- input series: raw close, VWAP deviation, spread, returns, or residuals
- window length
- lag/q values
- ADF threshold if converting to boolean
- whether the indicator is context-only or trade-driving

## Causality

All rolling estimates must use past/current bars only. No full-sample fit.

ADF and Hurst are computationally heavier and should initially be context-only
unless a strategy explicitly depends on them.

## Test Plan

- known trending synthetic segment
- known mean-reverting synthetic segment
- causality test by mutating future bars
- compare output shape and missing-value behavior on short windows

