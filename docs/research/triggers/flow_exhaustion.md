# Flow Exhaustion Trigger

**Status:** Documented

---

## What Is It?

The flow exhaustion trigger detects when **delta velocity** (the acceleration/deceleration of order flow) peaked and is now declining. Velocity is the derivative of delta: the rate at which flow imbalance is growing or shrinking.

When velocity is extreme (accelerating flow), it signals aggressive buying or selling pressure. When velocity reverses (decelerating), it signals the pressure is exhausting — the aggressor's orders are running out of steam.

This is a second-derivative signal: delta is momentum, delta velocity is momentum of momentum.

---

## Market Theory

**Assumption:** Order flow pressure builds (positive velocity) and then exhausts (velocity declines). The peak velocity represents maximum aggression; the reversal represents exhaustion.

**Application:**
- Price rose sharply (buyers were accelerating)
- DeltaVel_Z (delta acceleration) was extreme positive (e.g., +3.0)
- Current DeltaVel_Z is lower than prior bar (velocity declining)
- This signals the buy pressure is exhausting → SELL_FADE setup

**Reference:** Chordia & Subrahmanyam (2004) "Order Imbalance and Individual Stock Returns" — flow velocity predicts reversals.

---

## Mathematical Foundation

### Delta Velocity (ROC of Delta)

```
Delta[t] = BuyVol[t] - SellVol[t]

DeltaVel[t] = Delta[t] - Delta[t-n]   (n-bar change, typically n=5)
            = Rate of change of buy/sell imbalance

DeltaROC5[t] = Delta[t] - Delta[t-5]  (example)
```

### Delta Velocity Z-Score

```
DeltaVel_Z[t] = (DeltaVel[t] - rolling_mean(DeltaVel, 50)) / rolling_std(DeltaVel, 50)

High DeltaVel_Z = flow accelerating (pressure building)
Low DeltaVel_Z = flow decelerating (pressure exhausting)
```

### Exhaustion Trigger Condition

```
DeltaVel_Z[i-2] > threshold (e.g., 1.5)   → Velocity was extreme
DeltaVel_Z[i-1] < DeltaVel_Z[i-2]        → Started declining
DeltaVel_Z[i] < DeltaVel_Z[i-1]          → Still declining (momentum fading)

Combined: Velocity peaked at i-2, now declining → exhaustion confirmed
```

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def detect_flow_exhaustion(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect flow exhaustion trigger: delta velocity peaked and is declining.

    Args:
        bp: bootstrap dict with columns:
            - DeltaVel_Z: robust Z-score of delta velocity (ROC5)
        i: current bar index
        direction: "BUY_FADE" or "SELL_FADE"
        cfg: dict with optional thresholds:
            - peak_threshold: default 1.5 (how extreme the prior velocity was)
            - min_bars_declining: default 2 (bars of velocity decline)
            - lookback_for_peak: default 2 (bars back to find peak)

    Returns:
        True if flow exhaustion detected, False otherwise
    """
    if cfg is None:
        cfg = {}

    peak_threshold = cfg.get("peak_threshold", 1.5)
    min_bars_declining = cfg.get("min_bars_declining", 2)
    lookback_for_peak = cfg.get("lookback_for_peak", 2)

    # Need enough history
    if i < lookback_for_peak + min_bars_declining:
        return False

    # Validate column
    if "DeltaVel_Z" not in bp:
        return False

    vel_z = bp["DeltaVel_Z"]

    # Handle NaN
    if any(np.isnan(vel_z[j]) for j in range(i - lookback_for_peak, i + 1)):
        return False

    # Check 1: Prior bar(s) had extreme velocity
    peak_idx = i - lookback_for_peak
    peak_was_extreme = abs(vel_z[peak_idx]) > peak_threshold

    if not peak_was_extreme:
        return False

    # Check 2: Velocity is declining from peak
    velocity_declining = all(
        vel_z[j] < vel_z[j-1] for j in range(peak_idx + 1, i + 1)
    )

    return velocity_declining


def detect_flow_exhaustion_with_direction(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect flow exhaustion with directional confirmation.
    For SELL_FADE, expect positive velocity (buyers were accelerating, now exhausting).
    For BUY_FADE, expect negative velocity (sellers were accelerating, now exhausting).
    """
    if cfg is None:
        cfg = {}

    if i < 3:
        return False

    if "DeltaVel_Z" not in bp or "DeltaROC5" not in bp:
        return False

    vel_z = bp["DeltaVel_Z"]
    vel = bp["DeltaROC5"]

    # Handle NaN
    if any(np.isnan(vel_z[j]) for j in range(i - 2, i + 1)) or \
       any(np.isnan(vel[j]) for j in range(i - 2, i + 1)):
        return False

    peak_threshold = cfg.get("peak_threshold", 1.5)

    # Check for peak
    peak_was_extreme = abs(vel_z[i-2]) > peak_threshold

    if not peak_was_extreme:
        return False

    # Check for decline
    velocity_declining = vel_z[i-1] < vel_z[i-2] and vel_z[i] < vel_z[i-1]

    if not velocity_declining:
        return False

    # Directional confirmation
    if direction == "SELL_FADE":
        # Expect prior positive velocity (buyers accelerating, now exhausting)
        return vel_z[i-2] > peak_threshold
    elif direction == "BUY_FADE":
        # Expect prior negative velocity (sellers accelerating, now exhausting)
        return vel_z[i-2] < -peak_threshold
    else:
        return False


def detect_velocity_peak_and_trough(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    More sophisticated: detect local max/min in velocity (peak), then reversal.
    Uses a rolling window to find where velocity peaked, not fixed lookback.
    """
    if cfg is None:
        cfg = {}

    if i < 5:
        return False

    if "DeltaVel_Z" not in bp:
        return False

    vel_z = bp["DeltaVel_Z"]
    lookback = cfg.get("lookback", 5)

    # Handle NaN
    if any(np.isnan(vel_z[j]) for j in range(i - lookback, i + 1)):
        return False

    # Find peak in lookback window
    window = vel_z[i - lookback : i]
    peak_value = np.max(np.abs(window))

    # Is current velocity lower than peak? (exhaustion)
    current_is_lower = abs(vel_z[i]) < peak_value

    # Is current velocity changing sign? (reversal)
    changing_sign = (vel_z[i-1] > 0 and vel_z[i] < 0) or \
                    (vel_z[i-1] < 0 and vel_z[i] > 0)

    # Trigger fires on exhaustion or sign change
    return current_is_lower or changing_sign
```

---

## Thresholds and Interpretation

| DeltaVel_Z[i-2] | DeltaVel_Z[i-1] | DeltaVel_Z[i] | Interpretation | Signal Strength |
|-----------------|-----------------|---------------|----------------|-----------------|
| > 2.0 | < 1.5 | < 1.0 | Strong peak, clear exhaustion | Very Strong |
| > 1.5 | < 1.2 | < 0.9 | Moderate peak, clear decline | Strong |
| > 1.0 | ~1.0 | < 1.0 | Weak peak, weak exhaustion | Moderate |
| > 0.5 | > 0.5 | > 0.5 | No exhaustion | No signal |

### Sensitivity Tuning

```
Conservative (wait for very strong exhaustion):
  - peak_threshold: 2.0
  - min_bars_declining: 3
  - lookback_for_peak: 3

Balanced:
  - peak_threshold: 1.5
  - min_bars_declining: 2
  - lookback_for_peak: 2

Aggressive (catch exhaustion early):
  - peak_threshold: 1.0
  - min_bars_declining: 1
  - lookback_for_peak: 1
```

---

## Combining with Setup

**Example: OFI extreme + Flow exhaustion:**

```python
# Setup: OFI at extreme
setup = OFI_Z[i] > 2.0

# Trigger: flow exhaustion (positive velocity fading)
trigger = detect_flow_exhaustion_with_direction(bp, i, "SELL_FADE", cfg)

# Execute when both fire
if setup and trigger:
    return "SELL_FADE"
```

---

## Layer Role

**Dimension 2: Entry Signal — Timing**

Flow exhaustion is a second-derivative trigger: it captures momentum-of-momentum reversals, providing early confirmation that a strong setup is about to reverse.

---

## Column Names

Exact bootstrap columns used:
- `DeltaVel_Z` - Robust Z-score of delta velocity (5-bar ROC) (already implemented)
- `DeltaROC5` - Delta velocity, raw form: Delta[t] - Delta[t-5] (already implemented)

---

## References

- Chordia, T. & Subrahmanyam, A. (2004) — "Order Imbalance and Individual Stock Returns"
- Chordia, T., Roll, R. & Subrahmanyam, A. (2002) — "Order Imbalance, Liquidity, and Market Returns"
- Harris, L. (2003) — *Trading and Exchanges: Market Microstructure for Practitioners*
