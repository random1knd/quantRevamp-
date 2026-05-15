# Z-Score Methods

## What Is It?

Z-Score measures how many standard deviations a value is from the mean. In trading, it quantifies how "extended" price is from a reference point.

```
Z = (X - μ) / σ

X = current value (price)
μ = mean (reference point)
σ = standard deviation
```

---

## Why It's Useful

- **Standardized measure**: Comparable across different instruments and timeframes
- **Statistical basis**: Z > 2 means ~2.5% probability in normal distribution
- **Mean reversion**: Extreme Z-scores suggest reversion is likely

---

## Variants

### 1. Z-Score from Simple Moving Average (SMA)
```python
mean = close.rolling(N).mean()
std = close.rolling(N).std()
zscore = (close - mean) / std
```
**Characteristics:** Smooth, equal weight to all periods

### 2. Z-Score from Exponential Moving Average (EMA)
```python
mean = close.ewm(span=N).mean()
std = close.rolling(N).std()  # or ewm std
zscore = (close - mean) / std
```
**Characteristics:** More responsive to recent prices

### 3. Z-Score from VWAP
```python
vwap = cumsum(typical_price * volume) / cumsum(volume)
std = rolling_std_of_vwap_deviation
zscore = (close - vwap) / std
```
**Characteristics:** Volume-weighted, resets per session

### 4. Z-Score from Linear Regression
```python
linreg = linear_regression(close, N)
residual = close - linreg
zscore = residual / residual.std()
```
**Characteristics:** Accounts for trend — best when price has a short-term drift

### 5. Robust Z-Score (Median + MAD)
```python
median = np.median(window)
mad = np.median(np.abs(window - median))
robust_z = (x - median) / (1.4826 * mad)
```
**Characteristics:** Resistant to outliers. The `1.4826` factor makes MAD consistent with std under a normal distribution. When a single spike (news, stop run) corrupts the rolling std, this stays clean. Best choice when your window contains occasional extreme bars.

**Why 1.4826:** `1 / Φ⁻¹(0.75) ≈ 1.4826` — rescales MAD to be a consistent estimator of σ for Gaussian data.

### 6. Percentile / Quantile Anomaly
```python
q_low  = np.percentile(window, 1)
q_high = np.percentile(window, 99)
anomaly = (x < q_low) or (x > q_high)

# Continuous version (0-1 score):
pctile_score = np.sum(window <= x) / len(window)
# 0 = most extreme low, 1 = most extreme high, 0.5 = middle
```
**Characteristics:** Makes no distributional assumption (non-parametric). Works on any distribution — price, volume, delta, OFI. Use the continuous score as a data point rather than just a binary flag.

### 7. Volatility-Scaled Move (ATR-style)
```python
atr = np.mean(np.abs(np.diff(window)))
score = abs(x - window[-1]) / atr
```
**Characteristics:** Measures the current move relative to the average recent move — not deviation from a mean, but the *size of the current bar* relative to recent bars. Useful for detecting when a single bar is abnormally large (capitulation, absorption confirmation). Different from other Z-scores — this is a momentum/volatility measure, not a mean-deviation measure.

### 8. EWMA Z-Score (Adaptive Mean and Std)
```python
mean = pd.Series(window).ewm(span=50).mean().iloc[-1]
std  = pd.Series(window).ewm(span=50).std().iloc[-1]
z_ewma = (x - mean) / std
```
**Characteristics:** Both the mean and std adapt exponentially — more weight on recent data. Reacts faster to regime shifts than SMA Z-score. Better in non-stationary environments where the mean itself is drifting. Downside: can be "fooled" by a sustained trend making recent bars the new normal.

### 9. Winsorized Z-Score (Clip Outliers First)
```python
clipped = np.clip(window, np.percentile(window, 5), np.percentile(window, 95))
mean = np.mean(clipped)
std  = np.std(clipped)
z_win = (x - mean) / std
```
**Characteristics:** Clips the most extreme 5% on each tail before computing mean/std, then scores the original unclipped `x`. This removes the influence of outliers on the reference distribution while still detecting if the current value is extreme relative to the cleaned baseline. Good middle ground between naive Z-score and full Median+MAD.

---

## Typical Thresholds

| Z-Score | Interpretation | Action |
|---------|----------------|--------|
| > +3.0 | Extremely overbought | Strong sell signal |
| > +2.0 | Overbought | Sell signal |
| +1.0 to +2.0 | Above average | Mild sell bias |
| -1.0 to +1.0 | Normal range | No signal |
| -2.0 to -1.0 | Below average | Mild buy bias |
| < -2.0 | Oversold | Buy signal |
| < -3.0 | Extremely oversold | Strong buy signal |

---

## How Quants Use It

1. **Entry signal**: Enter when |Z| > threshold (e.g., 2.0)
2. **Position sizing**: Larger position for higher |Z|
3. **Risk management**: Stop if Z goes more extreme
4. **Regime filter**: Only trade when Z indicates mean-reverting market

---

## Implementation Considerations

### Lookback Period
- Short (10-20): More signals, more noise
- Medium (20-50): Balanced
- Long (50-100): Fewer signals, more reliable

### Reference Point Choice
- SMA: Simple, widely used
- EMA: Faster reaction
- VWAP: Volume-weighted, institutional reference
- Median: Robust to outliers

### Standard Deviation Calculation
- Same lookback as mean
- Can use different lookback (e.g., shorter for faster reaction)
- Rolling vs expanding window

---

## Code Example

```python
import pandas as pd
import numpy as np

def zscore_sma(close: pd.Series, lookback: int = 20) -> pd.Series:
    """Z-Score from Simple Moving Average."""
    mean = close.rolling(lookback).mean()
    std = close.rolling(lookback).std()
    return (close - mean) / std

def zscore_ema(close: pd.Series, lookback: int = 20) -> pd.Series:
    """Z-Score from Exponential Moving Average."""
    mean = close.ewm(span=lookback).mean()
    std = close.rolling(lookback).std()
    return (close - mean) / std

def zscore_vwap(close: pd.Series, volume: pd.Series, session_ids: pd.Series) -> pd.Series:
    """Z-Score from Session VWAP."""
    tp = close  # or (high + low + close) / 3
    cum_pv = (tp * volume).groupby(session_ids).cumsum()
    cum_v = volume.groupby(session_ids).cumsum()
    vwap = cum_pv / cum_v

    # Rolling std of deviation from VWAP
    deviation = close - vwap
    std = deviation.rolling(20).std()

    return deviation / std
```

---

## Comparison: Which to Use When

| Method | Outlier Resistant | Adaptive | Distribution Assumption | Best For |
|--------|------------------|----------|------------------------|----------|
| SMA Z-Score | No | No | Normal | Stable, clean series |
| EMA Z-Score | No | Partial | Normal | Trending mean |
| VWAP Z-Score | No | Session-reset | Normal | Intraday session reference |
| Linear Reg Z-Score | No | No | Normal | Detrended residuals |
| **Robust (MAD)** | **Yes** | No | None | **Noisy data with spikes** |
| **Percentile** | **Yes** | No | **None** | **Any distribution** |
| Volatility-Scaled | N/A | No | None | Single-bar magnitude |
| **EWMA Z-Score** | No | **Yes** | Normal | **Shifting regimes** |
| **Winsorized** | **Partial** | No | Normal | **Moderate outliers** |

**Recommendation for NQ intraday:**
- Primary entry Z-score: **VWAP Z-Score** (institutional reference) or **Robust MAD** (cleaner)
- Regime filter Z-score: **EWMA** (adapts to intraday vol changes)
- Volume/delta anomaly: **Percentile** (non-parametric, works for any distribution)
- Single-bar confirmation: **Volatility-Scaled** (is this bar unusually large?)

## References

- Standard statistical measure
- Widely used in quantitative trading
- Foundation of many mean reversion strategies
- Robust statistics: Rousseeuw & Croux (1993) — "Alternatives to the Median Absolute Deviation"
- Winsorization: Dixon & Tukey (robust estimation literature)
