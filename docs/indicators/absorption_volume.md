# Absorption And Volume Indicators

Purpose:

- record volume spikes, absorption, and participation context around trades

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `AbsRatio` | Flow pressure relative to price movement. | delta/volume, price range/change |
| `VolRatio` | Current volume relative to recent average. | volume, window |
| `Volume_RobustZ` | Robust z-score of volume. | volume, window |
| `Volume_Pctile` | Rolling percentile of volume. | volume, window |

## Implementation Approach

Shared math can live in:

```text
shared/indicators/volume.py
shared/indicators/absorption.py
```

Expected functions:

```text
volume_ratio(volume, window)
volume_robust_zscore(volume, window)
absorption_ratio(delta, price_change, range_value, method)
```

## Parameter Decisions

Each strategy must state:

- volume window
- robust z-score window
- absorption formula
- handling for zero price movement or zero range
- whether delta is required

## Causality

All volume context must use current and prior bars only.

If `AbsRatio` divides by price movement/range, zero denominators must be handled
explicitly and tested.

## Test Plan

- flat volume segment
- spike volume segment
- zero-range bar
- causality test by mutating future bars

