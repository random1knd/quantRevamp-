# Price Extension Indicators

Purpose:

- measure how far price is from a fair-value reference
- support VWAP and mean-reversion strategy slicing

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `SessionVWAP` | Volume-weighted average from declared session open to current bar. | `Close`, `Volume`, session definition |
| `VWAPDist` | `Close - SessionVWAP`. | `Close`, `SessionVWAP` |
| `VWAPDist_ATR` | VWAP distance normalized by ATR. | `VWAPDist`, `ATR` |
| `VWAPDist_SD` | VWAP distance normalized by rolling deviation standard deviation. | `VWAPDist`, window |
| `AnchoredVWAP` | DEFERRED: VWAP from a declared anchor event/time. | `Close`, `Volume`, anchor rule |
| `VWAPDev_SlotPctile` | DEFERRED: VWAP deviation percentile compared to same time slot history. | historical slot deviations |

Deferred items:

- `AnchoredVWAP`: anchor rule is not declared.
- `VWAPDev_SlotPctile`: requires historical session storage that does not
  exist.

## Implementation Approach

Shared math can live in:

```text
shared/indicators/vwap.py
```

Expected functions:

```text
session_vwap(frame, price_col, volume_col, session_col)
typical_price(high, low, close)
vwap_distance(close, vwap)
vwap_distance_atr_normalized(vwap_distance, atr)
```

Strategy code must pass session parameters explicitly. Any future anchored VWAP
work must pass the anchor parameters explicitly after a strategy declares the
anchor rule.

No global VWAP defaults.

## Anchor And Session Decisions

Every strategy that records or trades from VWAP features must state:

- RTH, Globex, or custom session
- session open timestamp
- session close timestamp
- timezone
- whether overnight bars are included
- anchored VWAP anchor rule, if used

Anchored VWAP must not choose an anchor using future bars. If the anchor is
based on a session high/low, document whether the value is allowed to update
causally as new highs/lows form.

## Causality

All values must be causal at bar N:

- `SessionVWAP[N]` can use bars from session open through N only
- rolling deviation statistics can use current and past deviations only
- slot percentile can use prior sessions only, not the current session's future
  slots

## Test Plan

- tiny hand-calculated VWAP example
- session reset example
- zero-volume behavior
- causality test that mutating bars after N does not change values up to N
