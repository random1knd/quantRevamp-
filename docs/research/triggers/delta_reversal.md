# Delta Reversal Trigger

**Status:** Documented

---

## What Is It?

The delta reversal trigger detects when cumulative delta (the running sum of directional flow) **reverses sign** — from positive to negative or vice versa. This signals that the dominant aggressor side has switched, and the counterparty is now pushing back.

In mean-reversion strategies, a delta reversal at an extended price level confirms that the move is exhausting: the initial directional flow that caused the extension is now reversing, and the opposite side is gaining control.

---

## Market Theory

**Assumption:** Sustained one-sided order flow (persistent positive or negative cumulative delta) drives price. When delta reverses sign, the dominant flow has exhausted and the opposite side is now dominant.

**Application:**
- Price extended 2+ SDs above VWAP (buyers were aggressive)
- CumDelta was strongly positive
- But delta just flipped negative → sellers are now pushing harder
- Trade: SELL_FADE (fade the current high, buyers exhausted)

**Reference:** Kyle (1985) "Continuous Auctions and Insider Trading" — market impact is proportional to accumulated order flow intensity.

---

## Mathematical Foundation

### Cumulative Delta

```
CumDelta[t] = Σ Delta[i] for i in rolling window (typically 30 min)
            = Σ (BuyVol[i] - SellVol[i])

Range: -∞ to +∞
Positive = net buyers controlled the window
Negative = net sellers controlled the window
```

### Delta Per Bar

```
Delta[t] = BuyVol[t] - SellVol[t]
```

### Reversal Condition

**Sign Flip:**
```
Delta[i-1] > 0 AND Delta[i] < 0  → Reversal from buyers to sellers
Delta[i-1] < 0 AND Delta[i] > 0  → Reversal from sellers to buyers
```

**Strength Check (optional):**
```
|Delta[i]| > threshold  →  Reversal is strong, not noise
|Delta[i]| > |Delta[i-1]| → New side is more aggressive
```

**CumDelta Confirmation (optional):**
```
CumDelta[i] still positive but Delta[i] turned negative
  → Buyers were leading but momentum is reversing
```

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def detect_delta_reversal(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect delta reversal trigger: per-bar delta flipped direction.

    Args:
        bp: bootstrap dict with columns:
            - Delta: BuyVol - SellVol per bar
        i: current bar index
        direction: "BUY_FADE" or "SELL_FADE"
        cfg: dict with optional thresholds:
            - min_delta_magnitude: default 0 (any flip counts)
            - require_strength: default False
            - strength_multiplier: default 1.2 (new side > old side * mult)

    Returns:
        True if delta reversal detected, False otherwise
    """
    if cfg is None:
        cfg = {}

    min_delta_magnitude = cfg.get("min_delta_magnitude", 0)
    require_strength = cfg.get("require_strength", False)
    strength_multiplier = cfg.get("strength_multiplier", 1.2)

    # Need at least 1 bar of history
    if i < 1:
        return False

    # Validate column exists
    if "Delta" not in bp:
        return False

    delta = bp["Delta"]

    # Handle NaN
    if np.isnan(delta[i-1]) or np.isnan(delta[i]):
        return False

    # Basic sign flip
    sign_flip = (delta[i-1] > 0 and delta[i] < 0) or \
                (delta[i-1] < 0 and delta[i] > 0)

    if not sign_flip:
        return False

    # Optional: minimum magnitude check (avoid micro reversals)
    if abs(delta[i]) < min_delta_magnitude:
        return False

    # Optional: strength check (new side must be >= multiplier * old side magnitude)
    if require_strength:
        if abs(delta[i]) < strength_multiplier * abs(delta[i-1]):
            return False

    return True


def detect_delta_reversal_with_direction(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect delta reversal with directional confirmation.
    For SELL_FADE, expect negative delta (sellers aggressive).
    For BUY_FADE, expect positive delta (buyers aggressive).
    """
    if cfg is None:
        cfg = {}

    if i < 1:
        return False

    if "Delta" not in bp:
        return False

    delta = bp["Delta"]

    if np.isnan(delta[i-1]) or np.isnan(delta[i]):
        return False

    # Sign flip
    if not ((delta[i-1] > 0 and delta[i] < 0) or (delta[i-1] < 0 and delta[i] > 0)):
        return False

    # Directional match
    min_magnitude = cfg.get("min_delta_magnitude", 0)

    if direction == "SELL_FADE":
        # Expect negative delta (sellers pushing down)
        return delta[i] < -min_magnitude

    elif direction == "BUY_FADE":
        # Expect positive delta (buyers pushing up)
        return delta[i] > min_magnitude

    else:
        return False


def detect_cumulative_delta_reversal(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect cumulative delta reversal: CumDelta reverses sign.
    More conservative than per-bar delta (requires sustained reversal).
    """
    if cfg is None:
        cfg = {}

    if i < 2:
        return False

    if "CumDelta" not in bp:
        return False

    cumdelta = bp["CumDelta"]

    # Handle NaN
    if np.isnan(cumdelta[i-1]) or np.isnan(cumdelta[i]):
        return False

    # Sign flip in cumulative delta
    sign_flip = (cumdelta[i-1] > 0 and cumdelta[i] < 0) or \
                (cumdelta[i-1] < 0 and cumdelta[i] > 0)

    if not sign_flip:
        return False

    # Directional check (optional)
    if direction == "SELL_FADE":
        return cumdelta[i] < 0
    elif direction == "BUY_FADE":
        return cumdelta[i] > 0
    else:
        return False
```

---

## Thresholds and Interpretation

| Condition | Delta[i] vs Delta[i-1] | CumDelta Change | Signal Strength |
|-----------|------------------------|-----------------|-----------------|
| Micro reversal | Flip, but <100 contracts | Minor | Weak |
| Small reversal | Flip, 100-500 contracts | Moderate | Moderate |
| Strong reversal | Flip, >500 contracts | Major | Strong |
| + Directional match | Flip AND sign matches setup | Clear confirmation | Strongest |

### Sensitivity Tuning

```
Conservative:
  - require_strength: true
  - strength_multiplier: 1.5
  - min_delta_magnitude: 300

Balanced:
  - require_strength: false
  - min_delta_magnitude: 0

Aggressive:
  - require_strength: false
  - min_delta_magnitude: 0 (any flip)
```

---

## Combining with Setup

**Example: VWAP extension + Delta reversal:**

```python
# Setup: price extended
setup = VWAPDist_SD[i] > 2.0

# Trigger: delta reversal (directional)
trigger = detect_delta_reversal_with_direction(bp, i, "SELL_FADE", cfg)

# Execute if both true
if setup and trigger:
    return "SELL_FADE"
```

---

## Layer Role

**Dimension 2: Entry Signal — Timing**

Delta reversal is a trigger for confirming timing within an already-detected setup. Provides mechanical confirmation that the dominant flow is reversing.

---

## Column Names

Exact bootstrap columns used:
- `Delta` - BuyVol - SellVol per bar (already implemented)
- `CumDelta` - Rolling cumulative delta (already implemented)

---

## References

- Kyle, L. A. (1985) — "Continuous Auctions and Insider Trading"
- Chordia, T., Roll, R. & Subrahmanyam, A. (2002) — "Order Imbalance, Liquidity, and Market Returns"
- Easley, D., López de Prado, M. M., & O'Hara, M. (2012) — "The Volume Clock"
