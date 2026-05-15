# OFI Flip Trigger

**Status:** Documented

---

## What Is It?

The OFI flip trigger detects when **Order Flow Imbalance changes sign** — from positive to negative or vice versa. This signals that the dominant directional pressure has reversed: buyers are now dominant where sellers were, or vice versa.

When OFI flips at an extended price level (e.g., price 2+ SDs above VWAP), it's a high-probability reversal signal: the flow that drove the extension has reversed direction.

---

## Market Theory

**Assumption:** OFI captures per-bar directional flow normalized by volume. When OFI is positive and strong, buyers are dominant. When OFI flips negative, sellers are now dominant.

**Application:**
- Price rose sharply (extended above VWAP)
- OFI was positive and strong (buyers were aggressive)
- OFI just flipped negative (sellers now dominant)
- Signal: SELL_FADE (price rejects the high as sellers take control)

**Reference:** Cont, Kukanov & Stoikov (2014) "The Price Impact of Order Book Events" — order flow sign change is a key predictor of price reversals.

---

## Mathematical Foundation

### Order Flow Imbalance (Per Bar)

```
OFI[t] = (BuyVol[t] - SellVol[t]) / TotalVolume[t]
       = Delta[t] / Volume[t]

Range: -1 to +1
Positive = net buyers initiated volume
Negative = net sellers initiated volume
```

### OFI Z-Score (Standardized)

```
OFI_Z[t] = (OFI[t] - rolling_mean(OFI, N)) / rolling_std(OFI, N)

High Z (> +2) = statistically extreme buying pressure
Low Z (< -2) = statistically extreme selling pressure
```

### OFI Flip Condition

**Simple sign flip:**
```
OFI[i-1] > 0 AND OFI[i] < 0  → Flip from buying to selling
OFI[i-1] < 0 AND OFI[i] > 0  → Flip from selling to buying
```

**Strength variant:**
```
|OFI_Z[i]| > threshold  →  Flip is statistically significant
```

**Reversal confirmation:**
```
CumOFI[i-1] was positive but OFI[i] negative
  → Cumulative buying pressure but current bar is selling
```

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def detect_ofi_flip(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect OFI flip trigger: Order Flow Imbalance changed sign.

    Args:
        bp: bootstrap dict with columns:
            - OFI: normalized order flow imbalance (-1 to +1)
            - OFI_Z: Z-score of OFI
        i: current bar index
        direction: "BUY_FADE" or "SELL_FADE"
        cfg: dict with optional thresholds:
            - require_z_extreme: default False (OFI_Z must be extreme)
            - z_threshold: default 1.5
            - use_cumofi_confirmation: default False

    Returns:
        True if OFI flip detected, False otherwise
    """
    if cfg is None:
        cfg = {}

    require_z_extreme = cfg.get("require_z_extreme", False)
    z_threshold = cfg.get("z_threshold", 1.5)
    use_cumofi = cfg.get("use_cumofi_confirmation", False)

    # Need at least 1 bar of history
    if i < 1:
        return False

    # Validate columns
    if "OFI" not in bp:
        return False

    ofi = bp["OFI"]

    # Handle NaN
    if np.isnan(ofi[i-1]) or np.isnan(ofi[i]):
        return False

    # Check for sign flip
    sign_flip = (ofi[i-1] > 0 and ofi[i] < 0) or \
                (ofi[i-1] < 0 and ofi[i] > 0)

    if not sign_flip:
        return False

    # Optional: require current OFI_Z to be statistically extreme
    if require_z_extreme:
        if "OFI_Z" not in bp:
            return False
        ofi_z = bp["OFI_Z"]
        if np.isnan(ofi_z[i]):
            return False
        if abs(ofi_z[i]) < z_threshold:
            return False

    # Optional: confirm with cumulative OFI
    if use_cumofi:
        if "CumOFI" not in bp:
            return False
        cumofi = bp["CumOFI"]
        if np.isnan(cumofi[i-1]):
            return False
        # CumOFI still agrees with old direction, but current OFI flipped
        # This is stronger evidence of reversal
        momentum_fading = (cumofi[i-1] > 0 and ofi[i] < 0) or \
                          (cumofi[i-1] < 0 and ofi[i] > 0)
        return momentum_fading

    return True


def detect_ofi_flip_with_direction(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect OFI flip with directional confirmation.
    For SELL_FADE, expect OFI to flip negative (sellers now dominant).
    For BUY_FADE, expect OFI to flip positive (buyers now dominant).
    """
    if cfg is None:
        cfg = {}

    if i < 1:
        return False

    if "OFI" not in bp:
        return False

    ofi = bp["OFI"]

    # Handle NaN
    if np.isnan(ofi[i-1]) or np.isnan(ofi[i]):
        return False

    # Sign flip
    if not ((ofi[i-1] > 0 and ofi[i] < 0) or (ofi[i-1] < 0 and ofi[i] > 0)):
        return False

    # Directional match
    if direction == "SELL_FADE":
        # Expect OFI to flip negative (sellers taking control)
        return ofi[i] < 0
    elif direction == "BUY_FADE":
        # Expect OFI to flip positive (buyers taking control)
        return ofi[i] > 0
    else:
        return False


def detect_ofi_divergence_from_cumofi(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    More sophisticated: current OFI diverging from cumulative OFI direction.
    This indicates the sustained flow direction is reversing.

    Example:
    - CumOFI is strongly positive (buyers were dominant)
    - Current OFI is negative (but sellers are not yet dominant cumulatively)
    - This is the START of the reversal
    """
    if cfg is None:
        cfg = {}

    if i < 1:
        return False

    if not all(col in bp for col in ["OFI", "CumOFI"]):
        return False

    ofi = bp["OFI"]
    cumofi = bp["CumOFI"]

    # Handle NaN
    if np.isnan(ofi[i]) or np.isnan(cumofi[i-1]):
        return False

    # Divergence: CumOFI and current OFI opposite directions
    divergence = (cumofi[i-1] > 0 and ofi[i] < 0) or \
                 (cumofi[i-1] < 0 and ofi[i] > 0)

    return divergence
```

---

## Thresholds and Interpretation

| OFI[i-1] | OFI[i] | OFI_Z[i] | Interpretation | Signal Strength |
|----------|--------|----------|----------------|-----------------|
| +0.3 | -0.2 | < -1.5 | Strong flip, extreme selling | Very Strong |
| +0.2 | -0.1 | -1.0 to -1.5 | Clear flip, moderate selling | Strong |
| +0.1 | -0.05 | -0.5 to -1.0 | Micro flip, weak signal | Weak |
| ±0.5 | ~-0.0 | Near 0 | Ambiguous flip | No signal |

### Sensitivity Tuning

```
Conservative (wait for strong flip):
  - require_z_extreme: true
  - z_threshold: 2.0
  - use_cumofi_confirmation: true

Balanced:
  - require_z_extreme: false
  - use_cumofi_confirmation: false

Aggressive (catch any flip):
  - require_z_extreme: false
  - use_cumofi_confirmation: false
```

---

## Combining with Setup

**Example: VWAP extension + OFI flip:**

```python
# Setup: price extended
setup = VWAPDist_SD[i] > 2.0 and OFI_Z[i-1] > 2.0

# Trigger: OFI flip (from positive to negative)
trigger = detect_ofi_flip_with_direction(bp, i, "SELL_FADE", cfg)

# Execute when both fire
if setup and trigger:
    return "SELL_FADE"
```

---

## Layer Role

**Dimension 2: Entry Signal — Timing**

OFI flip is a trigger confirming that the flow direction supporting a setup is reversing. Provides directional confirmation that the trade is correctly timed.

---

## Column Names

Exact bootstrap columns used:
- `OFI` - Order Flow Imbalance (Delta / Volume) (see `order_flow_imbalance.md`)
- `OFI_Z` - Z-score of OFI (see `order_flow_imbalance.md`)
- `CumOFI` - Cumulative OFI over rolling window (see `order_flow_imbalance.md`)

---

## References

- Cont, R., Kukanov, A. & Stoikov, S. (2014) — "The Price Impact of Order Book Events"
- Chordia, T., Roll, R. & Subrahmanyam, A. (2002) — "Order Imbalance, Liquidity, and Market Returns"
- Easley, D., López de Prado, M. M., & O'Hara, M. (2012) — "The Volume Clock"
