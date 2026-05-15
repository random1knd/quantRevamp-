# CUSUM Change Point Detection

**Status:** New Study

---

## Summary

CUSUM (Cumulative Sum Control Chart) is a real-time algorithm for detecting **sudden shifts in a time series**. Originally developed for quality control manufacturing, it's applied in quantitative finance to detect **regime changes** — when a market abruptly transitions from mean-reverting to trending (or vice versa).

Unlike static regime tests (ADF, Hurst) which measure a series over a fixed lookback window, CUSUM **continuously monitors** for abnormal deviations. When the cumulative sum exceeds a threshold, a regime change is flagged. This is ideal for adaptive mean reversion strategies: detect when the market transitions to trending mode and **kill entries immediately**.

---

## Mathematical Foundation

### CUSUM Algorithm (univariate)

Given a time series of returns or deviations:

```
r[t] = log(Price[t] / Price[t-1])  (or any stationary measure)

CUSUM[t] = max(0, CUSUM[t-1] + (r[t] - μ) - λ)

where:
  μ = mean of r (rolling estimate)
  λ = threshold (tuning parameter, e.g., 0.5 × σ)

Reset: CUSUM[t] = 0 if it drops below zero or goes negative
```

### Interpretation

- **CUSUM = 0:** Normal regime, no deviation accumulating
- **CUSUM > threshold:** Regime change detected, trending likely
- **High CUSUM:** Strong departure from mean, continue monitoring for reversion back to 0

### Practical Form (for regime switching)

```
Deviation[t] = Price[t] - EMA_mean[t]
               (or VWAP_deviation, or O-U residual)

CUSUM[t] = max(0, CUSUM[t-1] + Deviation[t] - threshold)

Regime_Switch = True when CUSUM[t] > UpperBound (e.g., 2σ of Deviation)
                 Reset to 0 when CUSUM crosses back below LowerBound (e.g., 0 or -1σ)
```

---

## Why It Matters for Mean Reversion

| Advantage | How It Helps |
|-----------|-------------|
| **Real-time detection** | Catches regime changes within 1–5 bars, not waiting for 50–100 bar window |
| **Adaptive regime gate** | Dynamically flag when market becomes trending → kill entries |
| **No false positives** | Threshold-based → needs sustained deviation, not one spike |
| **Complements static tests** | ADF/Hurst = historical view; CUSUM = forward-looking alert |
| **Useful for stop logic** | High CUSUM = strong trend forming → exit position early |

### Example: NQ Intraday (5-min bars)

**Normal regime (CUSUM low):**
```
CUSUM oscillates 0–1: price whipsawing around mean
→ Optimal for fade entries
```

**Trending regime (CUSUM high):**
```
CUSUM climbs to 5+: price consistently above/below EMA
→ Trend forming; skip fade entries
→ Consider exiting existing trades
```

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def compute_cusum(prices: np.ndarray,
                  mean_window: int = 50,
                  threshold: float = 0.5,
                  lookback_sigma: int = 20) -> dict:
    """
    Compute CUSUM for regime change detection.

    Args:
        prices: array of closing prices
        mean_window: window for rolling mean (reference level)
        threshold: CUSUM drift parameter (in units of std dev)
        lookback_sigma: window for computing rolling std dev

    Returns:
        dict with CUSUM metrics
    """
    n = len(prices)

    # Step 1: Compute deviations from rolling mean
    price_series = pd.Series(prices)
    rolling_mean = price_series.rolling(mean_window, min_periods=1).mean().values
    deviation = prices - rolling_mean

    # Step 2: Compute rolling standard deviation
    rolling_std = price_series.rolling(lookback_sigma, min_periods=1).std().values
    rolling_std[rolling_std == 0] = 1.0  # Avoid division by zero

    # Step 3: Normalize deviation by std
    normalized_dev = deviation / rolling_std

    # Step 4: Compute CUSUM
    cusum = np.zeros(n)
    cusum_h = np.zeros(n)  # Upper CUSUM (for positive deviations)
    cusum_l = np.zeros(n)  # Lower CUSUM (for negative deviations)

    for t in range(1, n):
        # Both-sided CUSUM
        cusum_h[t] = max(0, cusum_h[t-1] + normalized_dev[t] - threshold)
        cusum_l[t] = min(0, cusum_l[t-1] + normalized_dev[t] + threshold)

        cusum[t] = max(abs(cusum_h[t]), abs(cusum_l[t]))

    # Step 5: Detect regime change (when CUSUM exceeds bound)
    upper_bound = 4.0  # Threshold for change point (tuned parameter)
    regime_change = (cusum > upper_bound).astype(int)

    # Step 6: Regime state (0 = normal, 1 = uptrending, -1 = downtrending)
    regime_state = np.zeros(n, dtype=int)
    for t in range(1, n):
        if cusum_h[t] > upper_bound:
            regime_state[t] = 1  # Uptrending
        elif cusum_l[t] < -upper_bound:
            regime_state[t] = -1  # Downtrending
        else:
            regime_state[t] = regime_state[t-1]  # Carry forward

    return {
        'cusum': cusum,                  # Combined magnitude
        'cusum_positive': cusum_h,       # Upper CUSUM
        'cusum_negative': cusum_l,       # Lower CUSUM
        'regime_change_detected': regime_change,
        'regime_state': regime_state,    # 1=up, -1=down, 0=normal
        'normalized_deviation': normalized_dev,
    }


def adaptive_cusum_threshold(returns: np.ndarray,
                             window: int = 100) -> float:
    """
    Adaptively set CUSUM threshold based on rolling volatility.
    Higher vol → higher threshold needed to avoid false positives.

    Returns:
        adaptive threshold (in units of std dev)
    """
    rolling_vol = pd.Series(returns).rolling(window).std().values[-1]
    if rolling_vol > 0:
        # Threshold = 0.5 × recent vol (empirically tuned)
        return max(0.3, min(1.0, 0.5 * rolling_vol))
    return 0.5


def cusum_regime_score(regime_state: np.ndarray,
                       window: int = 10) -> np.ndarray:
    """
    Compute rolling regime confidence.
    Score from -1 (down) to +1 (up).

    Returns:
        array of scores indicating regime conviction
    """
    regime_series = pd.Series(regime_state)
    rolling_mean = regime_series.rolling(window).mean().values
    return np.clip(rolling_mean, -1, 1)


def cusum_vs_static_regime(cusum: np.ndarray,
                           adf_pvalue: np.ndarray,
                           threshold_cusum: float = 3.0,
                           threshold_adf: float = 0.10) -> dict:
    """
    Compare CUSUM (forward-looking) vs ADF (backward-looking) regime detection.
    Useful for understanding when each signals a regime change.

    Returns:
        metrics on agreement/divergence
    """
    cusum_regime = (cusum > threshold_cusum).astype(int)  # 1 = trending
    adf_regime = (adf_pvalue > threshold_adf).astype(int)   # 1 = trending

    agreement = (cusum_regime == adf_regime).sum() / len(cusum_regime)
    cusum_leads = np.sum((cusum_regime[:-1] == 1) & (adf_regime[1:] == 1))

    return {
        'agreement_pct': agreement,
        'cusum_leads_adf': cusum_leads,  # How often CUSUM detected before ADF
    }
```

---

## Interpretation & Thresholds

### CUSUM Magnitude

| CUSUM Value | Interpretation | Action |
|-------------|----------------|--------|
| 0–1.0 | Normal MR regime | Optimal for entries |
| 1.0–2.0 | Slight drift developing | Normal entries, monitor |
| 2.0–3.5 | Moderate trend | Weaker entries, wider stops |
| 3.5–5.0 | Strong trend | Skip entries, consider exits |
| > 5.0 | Very strong trend / flash crash | Do not enter; exit immediately |

### Change Point Detection

**Trigger:** CUSUM crosses upper bound (e.g., 4.0) = regime change detected.

**Recovery:** CUSUM returns to < 2.0 = regime change ended, return to MR mode.

---

## Layer Role

**Dimension 1: Regime Context** (primary)
- Real-time detection of regime switching
- Complements ADF, Hurst, VR with forward-looking signal
- Useful as a kill switch: when CUSUM high → suspend entries

---

## Column Names

When recording CUSUM metrics at each trade signal:

- `CUSUM` - Current CUSUM magnitude
- `CUSUM_Positive` - Upper CUSUM (uptrend detection)
- `CUSUM_Negative` - Lower CUSUM (downtrend detection)
- `CUSUM_RegimeState` - 1 (uptrending) / 0 (normal) / -1 (downtrending)
- `CUSUM_ChangeDetected` - Boolean: change point detected this bar
- `CUSUM_Confidence` - Regime conviction score [-1, 1]

---

## Practical Recommendations

### For NQ Futures (5-min bars)

```python
# Baseline parameters
mean_window = 50       # 250 minutes / 5-min bar = ~50 bars
threshold = 0.5       # CUSUM drift
upper_bound = 4.0     # Change point threshold

# Entry logic
if cusum[i] < 2.0 and adf_pvalue[i] < 0.10:
    # Normal MR regime: both tests agree
    entry_ok = True
elif cusum[i] < 1.0:
    # Very stable MR: enter even if ADF weak
    entry_ok = True
else:
    # Trending or uncertain: skip
    entry_ok = False
```

### Tuning Guidelines

| Parameter | Conservative | Aggressive | Notes |
|-----------|--------------|------------|-------|
| `threshold` | 0.3 | 0.7 | Lower = more sensitive |
| `upper_bound` | 5.0 | 3.0 | Lower = earlier detection |
| `mean_window` | 75 | 30 | Longer = slower adaptation |

---

## Relationship to Other Studies

| Metric | Comparison | Combined Signal |
|--------|-----------|-----------------|
| **ADF Test** | Both test stationarity; CUSUM is real-time, ADF is lookback | CUSUM for kill switch, ADF for regime confirmation |
| **Hurst Exponent** | Hurst = smoothed regime; CUSUM = sharp change detector | High Hurst + High CUSUM = strong trend |
| **Half-Life** | Half-life assumes MR; CUSUM detects when assumption breaks | If CUSUM_high, half-life estimate invalid |
| **ADX** | ADX measures trend strength; CUSUM detects transition | Both useful; CUSUM reacts faster |

---

## Advanced: Multi-Series CUSUM

For joint regime detection (price + flow):

```python
def multivariate_cusum(price_dev: np.ndarray,
                       flow_dev: np.ndarray,
                       weights: tuple = (0.6, 0.4),
                       threshold: float = 0.5) -> np.ndarray:
    """
    Combined CUSUM using both price and order flow deviations.
    Weights: importance of each series.
    """
    combined_dev = weights[0] * price_dev + weights[1] * flow_dev
    # Repeat CUSUM computation on combined series
    return compute_cusum_univariate(combined_dev, threshold=threshold)
```

---

## References

- Page, E. S. (1954) — "Continuous inspection schemes" (original CUSUM paper)
- Hawkins, D. M. (1993) — "Regression Adjustment for Reporting Delays in Disease Surveillance Data"
- Pólya, G. (1920) — "Über die Möglichkeit, daß ein zufällig wanderndes Punktnis beschranktes Gebiet"
- Moustakides, G. V. (1986) — "Optimal stopping times for detecting changes in distributions"
- Applied to finance: López de Prado, M. (2018) — *Advances in Financial Machine Learning*, Chapter 15
