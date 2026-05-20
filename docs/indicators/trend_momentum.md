# Trend And Momentum Indicators

Purpose:

- record whether a fade is fighting strong trend or momentum

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `ADX` | Trend strength. | OHLC, window |
| `MA_Slope` | Moving-average slope. | close, window |
| `EMA_Slope` | Exponential moving-average slope. | close, span |
| `ER_BarWindows` | Efficiency ratio across strategy-declared bar windows. | close, windows |
| `MOM_BarLookbacks` | Return/momentum over strategy-declared bar lookbacks. | close, lookbacks |
| `MOM_Composite` | BLOCKED: explicit weighted momentum composite. | component list |
| `TSMOM` | BLOCKED: time-series momentum signal/context. | returns, lookback |

Notes:

- ATR already lives in `shared/indicators/volatility.py`; do not duplicate it
  in this family.
- `MOM_Composite`: component weights are not declared.
- `TSMOM`: lookback is not declared by a strategy.
- Efficiency-ratio and momentum horizons are undeclared parameters. Each
  strategy must choose explicit bar windows/lookbacks.

## Implementation Approach

Shared math can live in:

```text
shared/indicators/trend.py
```

Expected functions:

```text
adx(bars, window)
ma_slope(series, window)
efficiency_ratio(series, window)
momentum(series, lookback)
```

## Parameter Decisions

Each strategy must state all windows/lookbacks explicitly.

Composite indicators should not be implemented until their component weights are
declared by a strategy README.

## Causality

All moving calculations must use past/current bars only.

Slope must compare historical values only, not a fitted line using future bars.

## Test Plan

- hand-calculated ADX example
- monotonic trend synthetic segment
- choppy synthetic segment
- causality test by mutating future bars
