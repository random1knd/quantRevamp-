# Order Flow Indicators

Purpose:

- record aggressive buying/selling pressure and changes in flow direction

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `Delta` | Ask volume minus bid volume, or source-provided delta. | bid/ask volume or delta |
| `CumDelta` | Cumulative delta over a declared reset scope. | delta, reset rule |
| `DeltaROC` | Delta change over N bars. | delta, lookback |
| `DeltaVel_Z` | Z-score of delta velocity. | delta velocity, window |
| `OFI` | Order-flow imbalance. | bid/ask/order-book inputs or approximation |
| `OFI_Z` | Z-score of OFI. | OFI, window |
| `CumOFI` | Cumulative OFI over reset scope. | OFI, reset rule |
| `OFI_Momentum` | Change/rate of OFI. | OFI, lookback |

## Implementation Approach

Shared math can live in:

```text
shared/indicators/order_flow.py
```

Expected functions:

```text
delta(bars)
cumulative_delta(delta, reset_rule)
delta_roc(delta, lookback)
ofi(bars, method)
rolling_flow_zscore(series, window)
```

## Parameter Decisions

Each strategy must state:

- bar construction: time bars, volume bars, dollar bars, or other
- whether delta is source-provided or computed
- reset rule for cumulative measures
- OFI method and required data
- z-score windows
- whether unavailable order-book fields make the feature skipped

Most first-pass implementations will use time bars if that is what the data
folder provides. The strategy README must state that choice. Do not silently
reuse time-bar order-flow results as if they were volume-bar features.

## Causality

All flow metrics must use current and prior bars only.

If a feature needs unavailable depth/order-book data, do not silently substitute
a different proxy without the strategy README saying so.

## Test Plan

- small hand-calculated delta/cumulative delta example
- reset behavior test
- missing input behavior
- causality test by mutating future bars
