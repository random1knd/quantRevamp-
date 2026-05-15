# Absorption Trigger

**Status:** Documented

---

## What Is It?

The absorption trigger detects when extreme directional flow (delta or OFI) is being **absorbed without price movement**. In market microstructure, "absorption" signals that the aggressive order flow (initiating the imbalance) has exhausted supply/demand. This creates a high-probability reversal setup.

The trigger fires when:
1. Delta or OFI was at an extreme (measuring supply/demand exhaustion)
2. Price failed to move despite that volume (AbsRatio jumped)
3. Bar just closed with minimal price progress

This signals the move is reversing.

---

## Market Theory

**Assumption:** When buyers or sellers are hitting the market aggressively, their orders either:
- **Continue the trend** (trend follows flow), OR
- **Get absorbed** (price stalls despite volume, sellers/buyers willing to supply at this price)

Absorption indicates the second case: the counterparty is willing to meet the flow, which means:
- The initial aggressor's pressure is exhausted
- A reversal is imminent

**Reference:** Cont & Kukanov (2017) "Order Flow as a Currency" — order flow momentum is mean-reverting; sustained one-sided flow is unsustainable.

---

## Mathematical Foundation

### AbsRatio (Absorption Proxy)

```
AbsRatio[t] = Range[t] / |Delta[t]|
            = (High[t] - Low[t]) / |BuyVol[t] - SellVol[t]|

Range: 0 to ∞
Low AbsRatio  = much flow, little price movement = absorption
High AbsRatio = little flow, much price movement = trending
```

### Absorption Trigger Conditions

**Prior bar (i-1):**
- `|Delta_RobustZ[i-1]| > 2.0` — flow was extreme (RobustZ avoids outlier sensitivity)
- `AbsRatio[i-1] < threshold` (e.g., 0.5) — OR was low, price didn't follow

**Current bar (i):**
- `AbsRatio[i] < threshold` — absorption continues OR
- `Range[i] < Range[i-1]` — price move contracted despite flow
- `|Delta[i]| < |Delta[i-1]|` — flow declined (pressure exhausted)

**Combined signal:**
```
Absorption[i] = (|Delta_RobustZ[i-1]| > 2.0 AND AbsRatio[i-1] < 0.5)
              AND (AbsRatio[i] < 0.5 OR Range[i] < Range[i-1])
```

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def detect_absorption(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect absorption trigger: extreme flow being absorbed (price stalling).

    Args:
        bp: bootstrap dict with columns:
            - Delta_RobustZ: robust Z-score of per-bar delta
            - AbsRatio: Range / |Delta| (low = absorption)
            - Range: High - Low
        i: current bar index
        direction: "BUY_FADE" or "SELL_FADE"
        cfg: dict with optional thresholds:
            - delta_z_threshold: default 2.0
            - abs_ratio_threshold: default 0.5
            - min_bars_lookback: default 2

    Returns:
        True if absorption detected, False otherwise
    """
    if cfg is None:
        cfg = {}

    delta_z_threshold = cfg.get("delta_z_threshold", 2.0)
    abs_ratio_threshold = cfg.get("abs_ratio_threshold", 0.5)
    min_lookback = cfg.get("min_bars_lookback", 2)

    # Need at least min_lookback bars of history
    if i < min_lookback:
        return False

    # Validate columns exist and contain data
    if not all(col in bp for col in ["Delta_RobustZ", "AbsRatio", "Range"]):
        return False

    delta_z = bp["Delta_RobustZ"]
    abs_ratio = bp["AbsRatio"]
    price_range = bp["Range"]

    # Handle NaN
    if np.isnan(delta_z[i-1]) or np.isnan(abs_ratio[i-1]) or np.isnan(abs_ratio[i]):
        return False

    # Condition 1: Prior bar had extreme delta
    extreme_flow = abs(delta_z[i-1]) > delta_z_threshold

    # Condition 2: Flow not being followed by price (absorption)
    #   Either AbsRatio is low (price didn't move relative to volume)
    #   OR price range contracted while flow persisted
    absorption_prior = abs_ratio[i-1] < abs_ratio_threshold
    absorption_current = (
        abs_ratio[i] < abs_ratio_threshold or
        price_range[i] < price_range[i-1] * 0.8  # Range contracted 20%
    )

    return extreme_flow and (absorption_prior or absorption_current)


def detect_absorption_with_direction(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect absorption with directional confirmation:
    If BUY_FADE (price fell), look for buyers (positive delta) being absorbed.
    If SELL_FADE (price rose), look for sellers (negative delta) being absorbed.
    """
    if cfg is None:
        cfg = {}

    if i < 2:
        return False

    if not all(col in bp for col in ["Delta", "Delta_RobustZ", "AbsRatio", "Range"]):
        return False

    delta = bp["Delta"]
    delta_z = bp["Delta_RobustZ"]
    abs_ratio = bp["AbsRatio"]

    # Handle NaN
    if np.isnan(delta[i-1]) or np.isnan(delta_z[i-1]) or np.isnan(abs_ratio[i]):
        return False

    delta_z_threshold = cfg.get("delta_z_threshold", 2.0)
    abs_ratio_threshold = cfg.get("abs_ratio_threshold", 0.5)

    # Directional check
    if direction == "SELL_FADE":
        # Price rose (aggressor was sellers/shorts); expect negative delta to absorb
        directional_match = delta[i-1] < -delta_z_threshold * np.std(delta[max(0, i-50):i])
    elif direction == "BUY_FADE":
        # Price fell (aggressor was buyers); expect positive delta to absorb
        directional_match = delta[i-1] > delta_z_threshold * np.std(delta[max(0, i-50):i])
    else:
        return False

    # Absorption confirmation
    absorption = abs_ratio[i] < abs_ratio_threshold

    return directional_match and absorption
```

---

## Thresholds and Interpretation

| AbsRatio | Delta_RobustZ | Interpretation | Trading Signal |
|----------|---------------|----------------|----------------|
| < 0.3 | > 2.0 | Extreme absorption | High probability reversal |
| 0.3–0.5 | > 1.5 | Clear absorption | Good reversal signal |
| 0.5–1.0 | > 1.0 | Moderate absorption | Weak/uncertain |
| > 1.0 | — | Trending (not absorption) | No trigger |

### Sensitivity Tuning

```
Conservative (fewer false signals):
  - delta_z_threshold: 2.5
  - abs_ratio_threshold: 0.3

Balanced:
  - delta_z_threshold: 2.0
  - abs_ratio_threshold: 0.5

Aggressive (more signals):
  - delta_z_threshold: 1.5
  - abs_ratio_threshold: 0.7
```

---

## Layer Role

**Dimension 2: Entry Signal — Timing**

Absorption is a trigger for confirming the timing of entry within an already-detected setup (e.g., VWAP extension + OFI extreme). Used to increase entry quality by avoiding whipsaws.

---

## Column Names

Exact bootstrap columns used:
- `Delta_RobustZ` - Robust Z-score of per-bar delta (from `zscore_methods.md`)
- `AbsRatio` - Range / |Delta| (already implemented)
- `Range` - High - Low per bar (already implemented)

---

## References

- Cont, R. & Kukanov, A. (2017) — "Order Flow as a Currency"
- Easley, D., López de Prado, M. M., & O'Hara, M. (2012) — "The Volume Clock"
- Harris, L. (2003) — *Trading and Exchanges: Market Microstructure for Practitioners*
