# Volatility Indicators

Purpose:

- record volatility regime, jumpiness, and risk context

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `RealizedVol` | Rolling realized volatility. | returns, window |
| `VolPctile` | Percentile of realized volatility. | realized vol, window |
| `VolRegime` | Label derived from volatility thresholds. | volatility measure, thresholds |
| `ATR_Pctile` | Percentile of ATR. | ATR, window |
| `JumpRatio` | Estimate of jump-driven vs smooth variance. | returns, window, method |

## Implementation Approach

Shared math can live in:

```text
shared/indicators/volatility.py
```

Expected functions:

```text
realized_volatility(returns, window)
rolling_percentile(series, window)
vol_regime(series, thresholds)
jump_ratio(returns, window, method)
```

## Parameter Decisions

Each strategy must state:

- return definition
- volatility window
- percentile lookback
- regime thresholds, if labels are used
- jump ratio method

## Causality

Percentiles and volatility windows must use prior/current bars only.

Do not classify volatility regime with full-sample percentiles for trade-driving
values.

## Test Plan

- low-vol synthetic segment
- high-vol synthetic segment
- jump bar segment
- causality test by mutating future bars

