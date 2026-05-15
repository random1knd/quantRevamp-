# Volume Climax Trigger

**Status:** Documented

---

## What Is It?

The volume climax trigger detects when **an unusually high-volume bar is followed by a contraction in volume**. Extreme volume bars often coincide with capitulation or exhaustion: everyone who was willing to trade at this price has traded, and momentum is spent.

When volume climaxes at an extended price level (e.g., 2+ SDs from VWAP), it signals the move is exhausting. The high volume represents the final aggressive sellers or buyers, and the follow-up volume contraction confirms the move is over.

---

## Market Theory

**Assumption:** Volume peaks at turning points (capitulation, capitulation to higher prices). After the volume peak, momentum exhausts.

**Application:**
- Price extended 2+ SDs above VWAP (aggressive buyers)
- Volume spike in current or prior bar (climax of buying)
- Current volume is lower than peak (exhaustion, no more buyers)
- Signal: SELL_FADE (volume exhaustion at the high)

**Reference:** Wyckoff, R. D. (1919) *The ABC of Stock Speculation* — high volume at extremes signals exhaustion, not continuation.

---

## Mathematical Foundation

### Volume Per Bar

```
Volume[t] = total contracts traded per bar

Volume_Z[t] = (Volume[t] - rolling_mean(Volume, N)) / rolling_std(Volume, N)
            = Robust Z-score (if using MAD instead of std)
```

### Volume Ratio (Normalized)

```
VolRatio[t] = Volume[t] / rolling_mean(Volume, 20)

VolRatio > 1.5 = abnormal high volume (1.5x normal)
VolRatio > 2.0 = extreme volume climax
VolRatio < 1.0 = low volume
```

### Volume Climax Condition

```
Prior bar: Volume_RobustZ[i-1] > 2.0   → Volume was extreme
Current bar: Volume[i] < Volume[i-1]   → Volume dropped
  OR: VolRatio[i] < VolRatio[i-1] * 0.8 → Volume contracted 20%+
```

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def detect_volume_climax(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect volume climax trigger: high volume bar followed by contraction.

    Args:
        bp: bootstrap dict with columns:
            - Volume: raw volume per bar
            - Volume_RobustZ: robust Z-score of volume
            - VolRatio: volume / 20-bar rolling mean
        i: current bar index
        direction: "BUY_FADE" or "SELL_FADE"
        cfg: dict with optional thresholds:
            - volume_z_threshold: default 2.0 (how extreme prior volume was)
            - volume_decline_pct: default 0.20 (20% contraction required)
            - lookback_for_peak: default 1 or 2 (bars back to find peak)

    Returns:
        True if volume climax detected, False otherwise
    """
    if cfg is None:
        cfg = {}

    volume_z_threshold = cfg.get("volume_z_threshold", 2.0)
    volume_decline_pct = cfg.get("volume_decline_pct", 0.20)
    lookback_for_peak = cfg.get("lookback_for_peak", 1)

    # Need enough history
    if i < lookback_for_peak + 1:
        return False

    # Validate columns
    if not all(col in bp for col in ["Volume", "Volume_RobustZ"]):
        return False

    volume = bp["Volume"]
    vol_z = bp["Volume_RobustZ"]

    # Handle NaN
    peak_idx = i - lookback_for_peak
    if np.isnan(vol_z[peak_idx]) or np.isnan(volume[i]):
        return False

    # Check 1: Prior bar(s) had extreme volume
    volume_was_extreme = vol_z[peak_idx] > volume_z_threshold

    if not volume_was_extreme:
        return False

    # Check 2: Current volume declined from peak
    volume_decline = volume[i] < volume[peak_idx] * (1.0 - volume_decline_pct)

    return volume_decline


def detect_volume_climax_with_volratio(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect volume climax using VolRatio instead of raw Z-score.
    VolRatio normalizes by 20-bar rolling mean, more robust.
    """
    if cfg is None:
        cfg = {}

    if i < 2:
        return False

    # Validate columns
    if not all(col in bp for col in ["VolRatio", "Volume_RobustZ"]):
        return False

    vol_ratio = bp["VolRatio"]
    vol_z = bp["Volume_RobustZ"]

    # Handle NaN
    if np.isnan(vol_ratio[i-1]) or np.isnan(vol_ratio[i]) or np.isnan(vol_z[i-1]):
        return False

    volume_z_threshold = cfg.get("volume_z_threshold", 2.0)
    ratio_decline_pct = cfg.get("ratio_decline_pct", 0.25)

    # Prior bar had extreme volume (>1.5x normal, preferably >2x)
    prior_extreme = vol_z[i-1] > volume_z_threshold

    # Current volume ratio below prior (contraction)
    vol_declining = vol_ratio[i] < vol_ratio[i-1] * (1.0 - ratio_decline_pct)

    return prior_extreme and vol_declining


def detect_volume_spike_and_fade(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    More sophisticated: detect a volume spike (any time in lookback window)
    followed by immediate decline in current bar.
    """
    if cfg is None:
        cfg = {}

    if i < 3:
        return False

    if not all(col in bp for col in ["Volume", "Volume_RobustZ"]):
        return False

    volume = bp["Volume"]
    vol_z = bp["Volume_RobustZ"]
    lookback = cfg.get("lookback", 3)

    # Find peak volume in lookback window
    vol_z_window = vol_z[i - lookback : i]
    peak_z = np.max(vol_z_window)

    volume_z_threshold = cfg.get("volume_z_threshold", 1.5)

    # Was there a spike?
    if peak_z < volume_z_threshold:
        return False

    # Is current volume declining from any prior bar?
    current_vol_is_lower = volume[i] < np.max(volume[i - lookback : i])

    return current_vol_is_lower
```

---

## Thresholds and Interpretation

| Volume_RobustZ[i-1] | Volume[i] / Volume[i-1] | VolRatio Change | Interpretation | Signal Strength |
|---|---|---|---|---|
| > 3.0 | < 0.7 | < 0.75 | Extreme climax, clear fade | Very Strong |
| 2.0–3.0 | 0.7–0.8 | 0.75–0.85 | Clear climax, volume declining | Strong |
| 1.5–2.0 | 0.8–0.9 | 0.85–0.95 | Moderate climax, slight decline | Moderate |
| < 1.5 | — | — | No climax | No signal |

### Sensitivity Tuning

```
Conservative (only extreme climax):
  - volume_z_threshold: 2.5
  - volume_decline_pct: 0.3 (30% contraction)
  - lookback_for_peak: 1

Balanced:
  - volume_z_threshold: 2.0
  - volume_decline_pct: 0.20 (20% contraction)
  - lookback_for_peak: 1

Aggressive (catch any volume spike fade):
  - volume_z_threshold: 1.5
  - volume_decline_pct: 0.10 (10% contraction)
  - lookback_for_peak: 2
```

---

## Combining with Setup

**Example: VWAP extension + Volume climax:**

```python
# Setup: price extended
setup = VWAPDist_SD[i] > 2.0

# Trigger: volume climax and fade
trigger = detect_volume_climax(bp, i, "SELL_FADE", cfg)

# Execute when both fire
if setup and trigger:
    return "SELL_FADE"
```

---

## Use Case: Capitulation Fade

Volume climax is especially powerful when combined with absorption:
- Price extended with extreme volume (capitulation)
- Volume spiked but price didn't follow (absorption)
- Current volume declining (exhaustion)
- All three together = highest quality reversal

```python
setup = VWAPDist_SD[i] > 2.0
trigger1 = detect_volume_climax(bp, i, "SELL_FADE", cfg)
trigger2 = detect_absorption(bp, i, "SELL_FADE", cfg)

if setup and trigger1 and trigger2:
    return "SELL_FADE"  # Highest confidence
```

---

## Layer Role

**Dimension 2: Entry Signal — Timing**

Volume climax is a trigger confirming that volume supporting a move has exhausted. Provides volume-based confirmation.

---

## Column Names

Exact bootstrap columns used:
- `Volume` - Raw volume per bar (already implemented)
- `Volume_RobustZ` - Robust Z-score of volume (from `zscore_methods.md`)
- `VolRatio` - Volume / 20-bar rolling mean (already implemented)

---

## References

- Wyckoff, R. D. (1919) — *The ABC of Stock Speculation*
- Easley, D., López de Prado, M. M., & O'Hara, M. (2012) — "The Volume Clock"
- López de Prado, M. (2018) — *Advances in Financial Machine Learning*, Chapter 15 (labeling)
