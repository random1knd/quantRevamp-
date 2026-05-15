# VPIN — Volume-Synchronized Probability of Informed Trading

**Status:** Documented

---

## What Is It?

VPIN (Volume-Synchronized Probability of Informed Trading) is a real-time measure of **order flow toxicity** — how much of the current trading volume is likely from informed (directional) traders vs uninformed (noise) traders.

Developed by Easley, Lopez de Prado & O'Hara (2012). High VPIN = informed traders dominate = expect directional move or market stress. Low VPIN = mostly noise trading = better for mean reversion.

**Key insight for MR traders:** Trade mean reversion when VPIN is LOW. Avoid when VPIN is HIGH (informed traders are driving price — don't fade them).

---

## Mathematical Basis

### Volume Bucketing

Instead of time bars, divide the price series into **equal-volume buckets** of size V:

```
V = total_volume / n_buckets  (typically 50 buckets per day)
```

### Buy/Sell Classification

For each volume bucket, classify volume as buy or sell using the **bulk volume classification (BVC)**:

```
P(buy | bucket) = Φ(ΔP / σ_ΔP)   [Φ = standard normal CDF]

BuyVolume  = V × P(buy | bucket)
SellVolume = V × (1 - P(buy | bucket))
|OI|        = |BuyVolume - SellVolume|  (order imbalance)
```

### VPIN Formula

```
VPIN = (Σ|OI_bucket| for last n buckets) / (n × V)

where n = sample length (typically 50 buckets)

VPIN ∈ [0, 1]
VPIN → 0: mostly balanced flow (noise traders)
VPIN → 1: mostly one-sided flow (informed traders)
```

---

## Why Quants Use It

| Use Case | Description |
|----------|-------------|
| Toxicity filter | High VPIN = toxic flow = don't fade |
| Flash crash warning | VPIN spiked before 2010 Flash Crash |
| Liquidity assessment | High VPIN = market makers widen spreads |
| MR confirmation | Low VPIN → safe to fade (noise trading dominant) |
| News/event detection | VPIN spike often precedes major moves |

---

## Python Implementation

```python
import numpy as np
from scipy.stats import norm

def compute_vpin(close: np.ndarray, volume: np.ndarray,
                  n_buckets: int = 50, sample_length: int = 50) -> dict:
    """
    Compute VPIN using bulk volume classification.

    Args:
        close: close prices
        volume: bar volumes
        n_buckets: number of volume buckets per day (~50)
        sample_length: number of buckets in the VPIN rolling window

    Returns:
        vpin: VPIN series aligned with close prices
    """
    n = len(close)
    bucket_size = np.sum(volume) / (n_buckets * (n / 78))  # 78 bars/day for 5-min

    # Bulk volume classification
    price_changes = np.diff(close, prepend=close[0])
    sigma_dp = np.std(price_changes[price_changes != 0])
    if sigma_dp == 0:
        sigma_dp = 0.25  # NQ tick size fallback

    # P(buy) using normal CDF of price change
    p_buy = norm.cdf(price_changes / sigma_dp)
    buy_vol = volume * p_buy
    sell_vol = volume * (1 - p_buy)
    order_imbalance = np.abs(buy_vol - sell_vol)

    # Accumulate into volume buckets
    vpin_at_bar = np.full(n, np.nan)
    cum_vol = 0
    current_bucket_oi = []
    buckets = []

    for i in range(n):
        cum_vol += volume[i]
        current_bucket_oi.append(order_imbalance[i])

        if cum_vol >= bucket_size:
            bucket_oi = np.sum(current_bucket_oi)
            buckets.append(bucket_oi)
            current_bucket_oi = []
            cum_vol = 0

            # Compute VPIN over rolling sample_length buckets
            if len(buckets) >= sample_length:
                recent_buckets = buckets[-sample_length:]
                vpin = np.sum(recent_buckets) / (sample_length * bucket_size)
                vpin_at_bar[i] = min(vpin, 1.0)

    # Forward-fill VPIN to all bars
    vpin_series = np.full(n, np.nan)
    last_vpin = np.nan
    for i in range(n):
        if not np.isnan(vpin_at_bar[i]):
            last_vpin = vpin_at_bar[i]
        vpin_series[i] = last_vpin

    return {
        "vpin": vpin_series,
        "high_toxicity": vpin_series > 0.5,
        "low_toxicity": vpin_series < 0.25,
    }


def vpin_percentile(vpin: np.ndarray, lookback: int = 500) -> np.ndarray:
    """VPIN percentile vs recent history."""
    pctile = np.full(len(vpin), np.nan)
    for i in range(lookback, len(vpin)):
        window = vpin[i-lookback:i]
        valid = window[~np.isnan(window)]
        if len(valid) > 0:
            pctile[i] = np.sum(valid <= vpin[i]) / len(valid)
    return pctile
```

---

## VPIN Interpretation

| VPIN | Interpretation | MR Strategy Action |
|------|----------------|-------------------|
| < 0.20 | Very low toxicity — mostly noise | Trade aggressively |
| 0.20–0.35 | Low toxicity — safe | Trade normally |
| 0.35–0.50 | Moderate — some informed flow | Reduce size |
| 0.50–0.65 | High toxicity — informed traders active | Skip new entries |
| > 0.65 | Very high toxicity / pre-event | Do not trade MR |

---

## VPIN vs OFI vs Delta

All three measure order flow — different aspects:

| Metric | What It Measures | Timescale |
|--------|-----------------|-----------|
| Delta | Raw directional imbalance | Per bar |
| OFI | Normalized directional imbalance | Per bar |
| **VPIN** | **Proportion of informed flow** | **Volume-synchronized** |

VPIN is the most sophisticated because it normalizes by **volume buckets** (not time), making it robust to intraday volume patterns.

---

## As a Data Point (record per trade)

```python
vpin_data = compute_vpin(close, volume, n_buckets=50)
signals.append({
    ...,
    "VPIN": vpin_data["vpin"][i],
    "VPIN_LowToxicity": vpin_data["low_toxicity"][i],
})
```

---

## Historical Note

VPIN gained prominence when Easley, Lopez de Prado & O'Hara showed it was elevated **hours before the 2010 Flash Crash**. High VPIN preceded the extreme directional move. This validated it as a market stress indicator.

---

## Relationship to Other Studies

- **Kyle's Lambda** (`kyles_lambda.md`): Lambda measures price impact; VPIN measures informed flow proportion
- **Order Flow Imbalance** (`order_flow_imbalance.md`): OFI = per-bar version; VPIN = volume-bucket version
- **Absorption Fade**: Low VPIN = noise trading = fade signals are more reliable

---

## References

- Easley, D., Lopez de Prado, M. & O'Hara, M. (2012) — "Flow Toxicity and Liquidity in a High Frequency World"
- Easley, D. et al. (2011) — "The Microstructure of the 'Flash Crash'"
- Lopez de Prado, M. (2018) — *Advances in Financial Machine Learning*, Chapter 2
