# Kalman Filter for Dynamic Mean Estimation

**Status:** Documented

---

## What Is It?

The Kalman Filter is a **recursive Bayesian estimator** that optimally tracks a hidden state from noisy observations. In trading, it is used as a **dynamic, adaptive moving average** — one that automatically adjusts its speed based on the signal-to-noise ratio.

Unlike SMA or EMA (fixed lookback), the Kalman Filter:
- Adapts its smoothing speed based on observed noise
- Provides a **measurement of uncertainty** (variance) around its estimate
- Is theoretically optimal under linear-Gaussian assumptions

---

## Mathematical Basis

The filter has two steps per bar: **Predict** and **Update**.

### State Space Model

```
State equation:    x[t] = x[t-1] + w[t],   w ~ N(0, Q)     (random walk prior)
Observation eq.:   y[t] = x[t] + v[t],     v ~ N(0, R)     (noisy price)

x[t] = hidden true mean (what we estimate)
y[t] = observed price
Q    = process noise variance (how fast true mean changes)
R    = observation noise variance (how noisy prices are)
```

### Predict Step

```
x̂[t|t-1] = x̂[t-1|t-1]                    (predicted state)
P[t|t-1]  = P[t-1|t-1] + Q                 (predicted variance)
```

### Update Step

```
K[t]     = P[t|t-1] / (P[t|t-1] + R)       (Kalman gain, 0 to 1)
x̂[t|t]  = x̂[t|t-1] + K[t]·(y[t] - x̂[t|t-1])  (updated estimate)
P[t|t]   = (1 - K[t]) · P[t|t-1]           (updated variance)
```

### Intuition

- `K[t]` is like a dynamic EMA alpha: when `R` is large (noisy prices), `K` is small → more smoothing
- When `Q` is large (fast-moving mean), `K` is large → follows price more closely
- **Q/R ratio** is the key tuning parameter: high Q/R = responsive, low Q/R = smooth

---

## Why Quants Use It

| Advantage | Description |
|-----------|-------------|
| Adaptive speed | Reacts faster during volatile regimes, slower when stable |
| Uncertainty bands | P[t] gives real-time confidence interval around estimate |
| No lookback choice | No need to choose SMA/EMA period — self-calibrating |
| Pairs trading | Track dynamic hedge ratio between two assets |
| Noise filtering | Better than any fixed MA at separating signal from noise |

---

## Python Implementation

### Simple Price Kalman Filter

```python
import numpy as np

def kalman_filter_mean(prices: np.ndarray, Q: float = 1e-5, R: float = 1e-2):
    """
    Kalman filter for dynamic mean estimation.

    Args:
        prices: observed price series
        Q: process noise (how fast the true mean moves). Try 1e-5 to 1e-3.
        R: observation noise (how noisy prices are). Try 1e-3 to 1e-1.

    Returns:
        means: filtered mean estimate at each bar
        variances: uncertainty (variance) at each bar
        gains: Kalman gain at each bar
    """
    n = len(prices)
    x = np.zeros(n)       # filtered mean
    P = np.zeros(n)       # variance
    K = np.zeros(n)       # Kalman gain

    # Initialize
    x[0] = prices[0]
    P[0] = 1.0

    for t in range(1, n):
        # Predict
        x_pred = x[t-1]
        P_pred = P[t-1] + Q

        # Update
        K[t] = P_pred / (P_pred + R)
        x[t] = x_pred + K[t] * (prices[t] - x_pred)
        P[t] = (1 - K[t]) * P_pred

    return x, P, K


def kalman_zscore(prices: np.ndarray, Q: float = 1e-5, R: float = 1e-2):
    """
    Z-score relative to Kalman-filtered mean.
    More adaptive than SMA/EMA Z-score.
    """
    means, variances, gains = kalman_filter_mean(prices, Q, R)
    std = np.sqrt(variances + R)  # total uncertainty: state + observation noise
    zscore = (prices - means) / np.where(std > 0, std, 1)
    return zscore, means, variances
```

### Auto-tuned Q/R via EM (advanced)

```python
def em_tune_kalman(prices: np.ndarray, n_iter: int = 10):
    """
    Expectation-Maximization to estimate Q and R from data.
    More principled than hand-tuning.
    """
    # Initial guess
    Q = np.var(np.diff(prices)) * 0.1
    R = np.var(prices) * 0.1

    for _ in range(n_iter):
        means, variances, gains = kalman_filter_mean(prices, Q, R)

        # M-step: update Q and R
        innovations = prices[1:] - means[:-1]
        R = np.mean(innovations**2) - np.mean(variances[:-1])
        R = max(R, 1e-8)

        state_changes = np.diff(means)
        Q = np.mean(state_changes**2) - np.mean(variances[:-1] * gains[1:]**2)
        Q = max(Q, 1e-10)

    return Q, R
```

---

## Parameter Tuning Guide

| Q/R Ratio | Behavior | Use Case |
|-----------|----------|----------|
| High (> 0.1) | Tracks price closely (like short EMA) | Fast markets |
| Medium (0.01–0.1) | Balanced adaptive | Most cases |
| Low (< 0.01) | Heavy smoothing (like long SMA) | Slow-moving mean |

**For NQ 5-min bars, start with:**
- `Q = 1e-4` to `1e-3`
- `R = 1e-2` to `5e-2`

---

## Trading Application

### As adaptive mean reference

```python
# Better than VWAP for non-session mean estimation
means, variances, gains = kalman_filter_mean(close, Q=1e-4, R=0.01)
kalman_std = np.sqrt(variances + 0.01)

# Entry signal: Kalman Z-score
k_zscore = (close - means) / kalman_std
if k_zscore[-1] > 2.0:   signal = "SELL_FADE"
if k_zscore[-1] < -2.0:  signal = "BUY_FADE"
```

### Kalman Gain as regime indicator

The Kalman gain `K[t]` itself is informative:
- **K near 0**: Filter is confident in its mean → slow-moving, stable
- **K near 1**: Filter is very uncertain → fast-moving or volatile regime

```python
# High K = volatile/trending → bad for mean reversion
if gains[-1] > 0.3:
    # Trending regime — skip MR trades
    pass
```

### As data point

```python
signals.append({
    ...,
    "Kalman_Mean": means[-1],
    "Kalman_ZScore": k_zscore[-1],
    "Kalman_Gain": gains[-1],          # regime indicator
    "Kalman_Variance": variances[-1],  # uncertainty
})
```

---

## Kalman Filter vs Other Means

| Method | Adaptivity | Uncertainty | Lag | Best For |
|--------|-----------|-------------|-----|----------|
| SMA | None | None | High | Stable trends |
| EMA | Fixed alpha | None | Medium | General |
| VWAP | Volume-weighted | None | Low | Session reference |
| **Kalman** | **Dynamic** | **Yes** | **Minimal** | **Adaptive regime** |

---

## Relationship to Other Studies

- **Z-Score Methods** (`zscore_methods.md`): Kalman provides a better dynamic mean for Z-score
- **O-U Process** (`ornstein_uhlenbeck.md`): Kalman can track O-U equilibrium μ dynamically
- **Regime Detection** (`hidden_markov_models.md`): Kalman gain indicates regime

---

## References

- Kalman, R.E. (1960) — "A New Approach to Linear Filtering and Prediction Problems"
- Welch & Bishop (2006) — "An Introduction to the Kalman Filter" (accessible tutorial)
- Ritter, J.A. (2010) — "Kalman Filter for Pairs Trading" (finance application)
- Chan, E. (2013) — *Algorithmic Trading*, Kalman filter pairs trading
