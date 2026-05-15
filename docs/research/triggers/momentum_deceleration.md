# Momentum Deceleration Trigger

**Status:** Documented

---

## What Is It?

The momentum deceleration trigger detects when **price momentum (rate of price change) was strong but is now declining**. This signals that the fuel driving the move is running out, and a reversal is imminent.

In mean-reversion strategies, momentum deceleration at an extended price level is high-probability confirmation that the move is exhausting. The price extended, momentum peaked, and now momentum is fading — the ideal entry point.

---

## Market Theory

**Assumption:** Price moves are driven by momentum (persistent directional buying/selling). When momentum decelerates at an extreme, it signals the move is losing steam.

**Application:**
- Price extended 2+ SDs above VWAP (buyers were aggressive)
- Momentum was strong (price rose steadily)
- Momentum is now declining (each bar gains less than the prior bar)
- Signal: SELL_FADE (momentum is fading, reversal coming)

**Reference:** Moskowitz, Ooi & Pedersen (2012) "Time Series Momentum" — momentum is mean-reverting; momentum of momentum predicts reversals.

---

## Mathematical Foundation

### Momentum (Price Rate of Change)

```
MOM_Short[t] = (Close[t] - Close[t-5]) / Close[t-5]
             Typical lookback: 5 bars (~1.5 hours on 5-min bars)

Positive = price risen over lookback (uptrend)
Negative = price fallen over lookback (downtrend)
Zero = flat
```

### Momentum Deceleration

```
MOM_Decel[t] = MOM_Short[t] - MOM_Short[t-1]

Positive decel = momentum increasing (accelerating)
Negative decel = momentum decreasing (decelerating)
```

### Momentum Z-Score (Standardized)

```
MOM_Z[t] = (MOM_Short[t] - rolling_mean(MOM_Short, 50)) / rolling_std(MOM_Short, 50)

Extreme MOM_Z = unusual momentum level
MOM_Z near 0 = neutral momentum
```

### Deceleration Trigger Condition

```
MOM_Short[i-2] > threshold (e.g., +0.01)  → Momentum was positive (up move)
MOM_Short[i-1] < MOM_Short[i-2]           → Started declining
MOM_Short[i] < MOM_Short[i-1]             → Still declining (losing steam)

Combined: Momentum peaked at i-2, now decelerating → exhaustion confirmed
```

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def detect_momentum_deceleration(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect momentum deceleration trigger: price momentum was strong, now declining.

    Args:
        bp: bootstrap dict with columns:
            - MOM_Short: TSMOM ~5 bars / 1.5 hours
        i: current bar index
        direction: "BUY_FADE" or "SELL_FADE"
        cfg: dict with optional thresholds:
            - momentum_threshold: default 0.005 (0.5% = minimum prior momentum)
            - min_bars_declining: default 2 (bars of momentum decline)
            - lookback_for_peak: default 2 (bars back to find peak)

    Returns:
        True if momentum deceleration detected, False otherwise
    """
    if cfg is None:
        cfg = {}

    momentum_threshold = cfg.get("momentum_threshold", 0.005)
    min_bars_declining = cfg.get("min_bars_declining", 2)
    lookback_for_peak = cfg.get("lookback_for_peak", 2)

    # Need enough history
    if i < lookback_for_peak + min_bars_declining:
        return False

    # Validate column
    if "MOM_Short" not in bp:
        return False

    mom = bp["MOM_Short"]

    # Handle NaN
    if any(np.isnan(mom[j]) for j in range(i - lookback_for_peak, i + 1)):
        return False

    # Check 1: Prior bar(s) had strong momentum
    peak_idx = i - lookback_for_peak
    peak_was_strong = abs(mom[peak_idx]) > momentum_threshold

    if not peak_was_strong:
        return False

    # Check 2: Momentum is declining from peak
    # (approaching zero, even if still in same direction)
    momentum_declining = all(
        abs(mom[j]) < abs(mom[j-1]) for j in range(peak_idx + 1, i + 1)
    )

    return momentum_declining


def detect_momentum_deceleration_with_direction(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect momentum deceleration with directional confirmation.
    For SELL_FADE, expect positive momentum that is now declining.
    For BUY_FADE, expect negative momentum that is now declining (becoming less negative).
    """
    if cfg is None:
        cfg = {}

    if i < 3:
        return False

    if "MOM_Short" not in bp:
        return False

    mom = bp["MOM_Short"]

    # Handle NaN
    if any(np.isnan(mom[j]) for j in range(i - 2, i + 1)):
        return False

    momentum_threshold = cfg.get("momentum_threshold", 0.005)

    # Check for strong prior momentum
    peak_was_strong = abs(mom[i-2]) > momentum_threshold

    if not peak_was_strong:
        return False

    # Check for momentum declining
    momentum_declining = abs(mom[i-1]) < abs(mom[i-2]) and abs(mom[i]) < abs(mom[i-1])

    if not momentum_declining:
        return False

    # Directional confirmation
    if direction == "SELL_FADE":
        # Expect positive momentum declining (uptrend exhausting)
        return mom[i-2] > momentum_threshold
    elif direction == "BUY_FADE":
        # Expect negative momentum declining toward zero (downtrend exhausting)
        return mom[i-2] < -momentum_threshold
    else:
        return False


def detect_momentum_reversal(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    More sophisticated: detect when momentum changes sign (strong reversal).
    Example: momentum was positive (uptrend), now negative (downtrend).
    """
    if cfg is None:
        cfg = {}

    if i < 1:
        return False

    if "MOM_Short" not in bp:
        return False

    mom = bp["MOM_Short"]

    # Handle NaN
    if np.isnan(mom[i-1]) or np.isnan(mom[i]):
        return False

    # Sign flip
    sign_flip = (mom[i-1] > 0 and mom[i] < 0) or \
                (mom[i-1] < 0 and mom[i] > 0)

    if not sign_flip:
        return False

    # Directional check
    if direction == "SELL_FADE":
        # Momentum flipped from positive to negative
        return mom[i-1] > 0 and mom[i] < 0
    elif direction == "BUY_FADE":
        # Momentum flipped from negative to positive
        return mom[i-1] < 0 and mom[i] > 0
    else:
        return False
```

---

## Thresholds and Interpretation

| MOM_Short[i-2] | MOM_Short[i-1] | MOM_Short[i] | Interpretation | Signal Strength |
|---|---|---|---|---|
| > +0.01 | +0.008 | +0.005 | Strong uptrend, now fading | Very Strong |
| > +0.005 | +0.003 | +0.001 | Moderate uptrend, declining | Strong |
| +0.003 | +0.002 | +0.001 | Weak uptrend, still declining | Moderate |
| 0 to +0.002 | — | — | No significant momentum | No signal |

### Sensitivity Tuning

```
Conservative (wait for very strong momentum decay):
  - momentum_threshold: 0.01 (1%)
  - min_bars_declining: 3
  - lookback_for_peak: 3

Balanced:
  - momentum_threshold: 0.005 (0.5%)
  - min_bars_declining: 2
  - lookback_for_peak: 2

Aggressive (catch momentum fading early):
  - momentum_threshold: 0.002 (0.2%)
  - min_bars_declining: 1
  - lookback_for_peak: 1
```

---

## Combining with Setup

**Example: VWAP extension + Momentum deceleration:**

```python
# Setup: price extended
setup = VWAPDist_SD[i] > 2.0

# Trigger: momentum deceleration (directional)
trigger = detect_momentum_deceleration_with_direction(bp, i, "SELL_FADE", cfg)

# Execute when both fire
if setup and trigger:
    return "SELL_FADE"
```

---

## Difference: Momentum vs Flow Exhaustion

Both detect "pressure running out," but at different levels:

| Aspect | Momentum Deceleration | Flow Exhaustion |
|--------|----------------------|-----------------|
| Measures | Price rate of change | Delta velocity (order flow acceleration) |
| Lag | Later (price already moved) | Earlier (flow leads price) |
| Sensitivity | Higher | Lower but earlier |
| Best Used | Confirm at reversal points | Catch exhaustion before price reverses |

Combining both: momentum deceleration + flow exhaustion = highest-quality confirmation.

---

## Layer Role

**Dimension 2: Entry Signal — Timing**

Momentum deceleration is a trigger confirming that price momentum supporting a setup is exhausting. Provides price-action confirmation.

---

## Column Names

Exact bootstrap columns used:
- `MOM_Short` - Time-Series Momentum ~5 bars / 1.5 hours (see `tsmom_momentum.md`)

---

## References

- Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012) — "Time Series Momentum"
- Asness, C. S., Moskowitz, T. J., & Pedersen, L. H. (2013) — "Value and Momentum Everywhere"
- Jegadeesh, N. & Titman, S. (1993) — "Returns to Buying Winners and Selling Losers"
