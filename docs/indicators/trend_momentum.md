# Trend And Momentum Indicators

Purpose:

- record whether a fade is fighting strong trend or momentum

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `ADX` | Trend strength. | OHLC, window |
| `ATR` | Average true range for volatility/risk context. | OHLC, window |
| `MA_Slope` | Moving-average slope. | close, window |
| `EMA_Slope` | Exponential moving-average slope. | close, span |
| `ER_Short/Mid/Long` | Efficiency ratio across horizons. | close, windows |
| `MOM_Short/Mid/Long` | Return/momentum over horizons. | close, lookbacks |
| `MOM_Composite` | Explicit weighted momentum composite. | component list |
| `TSMOM` | Time-series momentum signal/context. | returns, lookback |

## Implementation Approach

Shared math can live in:

```text
shared/indicators/trend.py
shared/indicators/momentum.py
shared/indicators/atr.py
```

Expected functions:

```text
atr(high, low, close, period)
adx(high, low, close, period)
moving_average_slope(close, window)
efficiency_ratio(close, window)
momentum(close, lookback)
```

## Parameter Decisions

Each strategy must state all windows/lookbacks explicitly.

Composite indicators should not be implemented until their component weights are
declared by a strategy README.

## Causality

All moving calculations must use past/current bars only.

Slope must compare historical values only, not a fitted line using future bars.

## Test Plan

- hand-calculated ATR example
- monotonic trend synthetic segment
- choppy synthetic segment
- causality test by mutating future bars

