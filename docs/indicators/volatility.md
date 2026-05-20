# Volatility Indicators

Purpose:

- record volatility regime, jumpiness, and risk context

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `RealizedVol` | Rolling realized volatility. | returns, window |
| `VolPctile` | Percentile of realized volatility. | realized vol, window |
| `VolRegime` | BLOCKED: label derived from volatility thresholds. | volatility measure, thresholds |
| `ATR_Pctile` | Percentile of ATR. | ATR, window |
| `JumpRatio` | BLOCKED: estimate of jump-driven vs smooth variance. | returns, window, method |

Blocked items:

- `VolRegime`: regime thresholds are not declared.
- `JumpRatio`: jump-variance method is not declared.

## Implementation Approach

Shared math can live in:

```text
shared/indicators/volatility.py
```

Expected functions:

```text
realized_volatility(returns, window)
vol_percentile(series, window)
atr_percentile(series, window)
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

`realized_volatility` does not reset at session boundaries by default. If
session-scoped realized volatility is needed, the caller must pass a
session-grouped series. This is intentional and must be documented by the
caller.

## Test Plan

- low-vol synthetic segment
- high-vol synthetic segment
- jump bar segment
- causality test by mutating future bars
