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
| `AnchoredVWAP` | VWAP from a declared anchor event/time. | `Close`, `Volume`, anchor rule |
| `VWAPDev_SlotPctile` | VWAP deviation percentile compared to same time slot history. | historical slot deviations |

## Implementation Approach

Shared math can live in:

```text
shared/indicators/vwap.py
```

Expected functions:

```text
session_vwap(bars, session_open, session_close, timezone)
vwap_distance(close, vwap)
anchored_vwap(bars, anchor_rule)
slot_percentile(series, slot_key, lookback_sessions)
```

Strategy code must pass the session and anchor parameters explicitly.

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

