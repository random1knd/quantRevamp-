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
| `OFI` | NOT BUILDABLE: true order-flow imbalance. | order book events or depth |
| `OFI_Approx` | APPROXIMATION: Chordia-style bid/ask volume change proxy. Context-only. | `BidVolume`, `AskVolume` |
| `OFI_Z` | NOT BUILDABLE for true OFI; possible only from `OFI_Approx` as context. | OFI approximation, window |
| `CumOFI` | NOT BUILDABLE for true OFI; possible only from `OFI_Approx` as context. | OFI approximation, reset rule |
| `OFI_Momentum` | NOT BUILDABLE for true OFI; possible only from `OFI_Approx` as context. | OFI approximation, lookback |

True `OFI`, `OFI_Z`, `CumOFI`, and `OFI_Momentum` require order book events
or depth data that this repo does not have. Only `OFI_Approx`, using bid/ask
volume changes on time bars, is buildable now. It must be labeled as an
approximation and used for context only.

`Delta`, `CumDelta`, and `DeltaROC` are time-bar values when computed from the
current data. They are acceptable for context use, but they are not equivalent
to tick-level signed flow.

## Implementation Approach

Shared math can live in:

```text
shared/indicators/order_flow.py
```

Expected functions:

```text
delta(bid_volume, ask_volume)
cumulative_delta(delta, session)
delta_roc(delta, lookback)
ofi_approx(bars)
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
