# Liquidity And Toxicity Indicators

Purpose:

- record whether flow or liquidity conditions make fading safer or more
  dangerous

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `VPIN` | NOT BUILDABLE from current time bars: volume-synchronized probability of informed trading / toxicity context. | volume buckets, signed volume method |
| `VPIN_Approx` | APPROXIMATION: rolling mean of `abs(AskVolume - BidVolume) / Volume`. Context-only. | `AskVolume`, `BidVolume`, `Volume`, window |
| `KyleLambda` | Price impact per unit order flow. | returns/price change, signed volume |
| `KyleLambda_Pctile` | Percentile rank of Kyle lambda. | Kyle lambda, window |

True VPIN was designed for volume buckets and is not buildable from the current
5-minute time bars. Only `vpin_approx = rolling mean(abs(AskVolume - BidVolume)
/ Volume)` is buildable now. This is a time-bar approximation, not volume-bar
VPIN.

Zero-denominator behavior:

- `vpin_approx`: if `Volume` is zero for a bar, that bar returns NaN.
- `kyle_lambda`: if variance of signed volume over the window is zero, returns
  NaN.

## Implementation Approach

Shared math can live in:

```text
shared/indicators/liquidity.py
```

Expected functions:

```text
vpin_approx(bars, window)
kyle_lambda(price_change, signed_volume, window)
kyle_lambda_percentile(series, window)
```

## Parameter Decisions

Each strategy must state:

- bar construction: time bars, volume bars, dollar bars, or other
- VPIN approximation window when using current time bars
- signed-volume classification method for any future true VPIN implementation
- Kyle lambda window
- price-change definition
- whether the feature is context-only or trade-driving

VPIN was designed around volume buckets. If computed from time bars, document
that it is a time-bar approximation and do not treat it as identical to a
volume-bar VPIN implementation.

## Causality

VPIN buckets must be built sequentially.

Percentiles can use prior history only.

## Test Plan

- simple bucket construction example
- zero/near-zero signed-volume behavior
- percentile behavior
- causality test by mutating future bars
