# Order Flow Imbalance (OFI)

**Status:** Documented

---

## What Is It?

Order Flow Imbalance measures the **net directional pressure from buyers vs sellers** at a given point in time. High OFI = buying dominates; low/negative OFI = selling dominates. It is one of the most powerful short-term price direction predictors in market microstructure research.

Unlike delta (which is raw buy - sell volume), OFI is **normalized and z-scored** to be comparable across bars with different volumes.

---

## Mathematical Basis

### Raw Delta (what you already have)

```
Delta[t] = BuyVolume[t] - SellVolume[t]
```

### Order Flow Imbalance (normalized)

```
OFI[t] = (BuyVolume[t] - SellVolume[t]) / TotalVolume[t]
       = Delta[t] / Volume[t]

Range: -1 to +1
+1 = all buys (extreme buying pressure)
-1 = all sells (extreme selling pressure)
 0 = balanced
```

### Cumulative OFI (window)

```
CumOFI[t] = Σ OFI[i] for i in window
           or equivalently: CumDelta / CumVolume over window
```

### OFI Z-Score (standardized)

```
OFI_Z[t] = (OFI[t] - rolling_mean(OFI, N)) / rolling_std(OFI, N)
```

---

## Why Quants Use It

| Use Case | Description |
|----------|-------------|
| Short-term direction | OFI predicts 1–5 bar future returns (Chordia et al., 2002) |
| Absorption confirmation | High OFI + no price movement = absorption |
| Divergence signal | OFI diverging from price = potential reversal |
| Regime indicator | Persistent OFI in one direction = trend; alternating = MR |
| Stop placement | OFI flip = reason to exit |

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def compute_ofi(delta: np.ndarray, volume: np.ndarray,
                window: int = 20) -> dict:
    """
    Compute Order Flow Imbalance metrics.

    Args:
        delta: bar-by-bar delta (buy_vol - sell_vol)
        volume: bar-by-bar total volume
        window: lookback for rolling stats

    Returns:
        dict of OFI arrays
    """
    # Normalize delta by volume (handles varying bar sizes)
    ofi = np.where(volume > 0, delta / volume, 0.0)

    # Rolling cumulative OFI
    ofi_series = pd.Series(ofi)
    cum_ofi = ofi_series.rolling(window).sum().values

    # OFI Z-score (standardized)
    ofi_mean = ofi_series.rolling(window).mean().values
    ofi_std = ofi_series.rolling(window).std().values
    ofi_z = np.where(ofi_std > 0, (ofi - ofi_mean) / ofi_std, 0.0)

    # OFI momentum: rate of change of cumulative OFI
    cum_ofi_series = pd.Series(cum_ofi)
    ofi_momentum = cum_ofi_series.diff(5).values  # 5-bar change in cum OFI

    # OFI divergence: price going up but OFI declining (bearish divergence)
    # Computed separately when price series is available

    return {
        "ofi": ofi,                    # Normalized: -1 to +1
        "cum_ofi": cum_ofi,            # Running cumulative
        "ofi_z": ofi_z,                # Standardized Z-score
        "ofi_momentum": ofi_momentum,  # Acceleration of OFI
    }


def ofi_divergence(close: np.ndarray, ofi: np.ndarray,
                   lookback: int = 10) -> np.ndarray:
    """
    Detect OFI/price divergence.
    Price makes new high but OFI declining = bearish divergence (sell signal)
    Price makes new low but OFI rising = bullish divergence (buy signal)

    Returns:
        divergence array: +1 = bullish div, -1 = bearish div, 0 = none
    """
    n = len(close)
    div = np.zeros(n)

    for i in range(lookback, n):
        price_window = close[i-lookback:i+1]
        ofi_window = ofi[i-lookback:i+1]

        # Bearish: price at high but OFI not at high
        price_at_high = close[i] == np.max(price_window)
        ofi_declining = ofi[i] < ofi[i-lookback]
        if price_at_high and ofi_declining:
            div[i] = -1  # Bearish divergence

        # Bullish: price at low but OFI not at low
        price_at_low = close[i] == np.min(price_window)
        ofi_rising = ofi[i] > ofi[i-lookback]
        if price_at_low and ofi_rising:
            div[i] = +1  # Bullish divergence

    return div
```

---

## Interpretation

### OFI Z-Score

| OFI_Z | Interpretation | Signal |
|-------|----------------|--------|
| > +2.0 | Extreme buying pressure | Potential top (if price extended) |
| +1 to +2 | Strong buying | Bullish short-term |
| -1 to +1 | Balanced | No directional edge |
| -1 to -2 | Strong selling | Bearish short-term |
| < -2.0 | Extreme selling pressure | Potential bottom (if price extended) |

### OFI for Mean Reversion (Absorption Fade context)

```
Ideal SELL_FADE setup:
  - Price 2+ SDs above VWAP (extended)
  - OFI_Z > +2.0 (extreme buying pressure being "absorbed")
  - CumOFI declining from peak (momentum fading)

Ideal BUY_FADE setup:
  - Price 2+ SDs below VWAP
  - OFI_Z < -2.0 (extreme selling pressure absorbed)
  - CumOFI rising from trough
```

---

## OFI vs AbsRatio (what you already have)

Your existing `AbsRatio = Range / |Delta|` measures absorption (price impact per unit delta). OFI complements it:

| Metric | Measures | Range |
|--------|----------|-------|
| AbsRatio | Price impact per delta (low = absorption) | 0 to ∞ |
| OFI | Net directional pressure (normalized) | -1 to +1 |
| OFI_Z | Statistical extremity of pressure | Z-score |

**Best combined signal:** Low AbsRatio + extreme OFI_Z = absorption at directional extreme.

---

## As a Data Point (record per trade)

```python
ofi_data = compute_ofi(delta, volume, window=20)
signals.append({
    ...,
    "OFI": ofi_data["ofi"][i],
    "OFI_Z": ofi_data["ofi_z"][i],
    "CumOFI": ofi_data["cum_ofi"][i],
    "OFI_Momentum": ofi_data["ofi_momentum"][i],
})
```

---

## Relationship to Other Studies

- **Absorption** (`triggers/absorption.md`): AbsRatio + OFI together = stronger signal
- **Kyle's Lambda** (`kyles_lambda.md`): Kyle's lambda is another price impact measure
- **VPIN** (`vpin.md`): VPIN is a flow toxicity measure based on similar concepts

---

## References

- Chordia, T., Roll, R. & Subrahmanyam, A. (2002) — "Order imbalance, liquidity, and market returns"
- Cont, R., Kukanov, A. & Stoikov, S. (2014) — "The Price Impact of Order Book Events"
- Easley, D. et al. — *Advances in Financial Machine Learning* related sections
