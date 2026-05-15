# Z-Score Family

Purpose:

- normalize price, flow, volume, or deviation series into comparable extremes

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `ZScore_SMA` | Standard rolling z-score around simple moving mean. | source series, window |
| `ZScore_EMA` | Z-score around exponential moving mean. | source series, span |
| `ZScore_EWMA` | Adaptive mean and dispersion using EWMA. | source series, span/alpha |
| `ZScore_Robust` | Median/MAD based robust z-score. | source series, window |
| `ZScore_Pctile` | Non-parametric percentile rank. | source series, window |
| `VolScaledMove` | Current move normalized by recent volatility. | return/move series, vol window |

## Implementation Approach

Shared math can live in:

```text
shared/indicators/zscore.py
```

Expected functions:

```text
rolling_zscore(series, window)
ewma_zscore(series, span)
robust_zscore(series, window)
rolling_percentile(series, window)
vol_scaled_move(series, vol_window)
```

Every strategy must state the source column and window/span. A column named
`ZScore` is not acceptable without the source and parameters.

## Causality

No centered windows. No full-sample mean/std for values used at bar N.

Rolling statistics can use bars up to N only.

For percentile ranks, the current value can be ranked against the prior window,
but the doc for the strategy must state whether bar N is included in the
reference set.

## Test Plan

- hand-calculated rolling z-score on a small series
- MAD example with an outlier
- flat series behavior
- causality test by mutating future values

