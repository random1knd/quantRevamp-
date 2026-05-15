# Liquidity And Toxicity Indicators

Purpose:

- record whether flow or liquidity conditions make fading safer or more
  dangerous

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `VPIN` | Volume-synchronized probability of informed trading / toxicity context. | volume, signed volume proxy, bucket size |
| `KyleLambda` | Price impact per unit order flow. | returns/price change, signed volume |
| `KyleLambda_Pctile` | Percentile rank of Kyle lambda. | Kyle lambda, window |

## Implementation Approach

Shared math can live in:

```text
shared/indicators/liquidity.py
shared/indicators/vpin.py
```

Expected functions:

```text
vpin(bars, bucket_volume, signed_volume_method)
kyle_lambda(price_change, signed_volume, window)
rolling_percentile(series, window)
```

## Parameter Decisions

Each strategy must state:

- bar construction: time bars, volume bars, dollar bars, or other
- VPIN bucket size
- signed-volume classification method
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
