# Variance Ratio Test

**Status:** Documented

---

## What Is It?

A statistical test (Lo & MacKinlay, 1988) that determines whether a price series is **mean-reverting, random walk, or trending** by comparing variance at different time horizons.

```
VR(q) = Var(q-period log returns) / (q × Var(1-period log returns))

VR < 1:  Mean-reverting (returns negatively autocorrelated)
VR = 1:  Random walk (efficient market)
VR > 1:  Trending (returns positively autocorrelated / momentum)
```

**Intuition:** If prices are a random walk, the variance of q-period returns should equal q times the 1-period variance. Any deviation = predictability.

---

## Mathematical Basis

Let `r_t = ln(P_t) - ln(P_{t-1})` be the 1-period log return.

```
σ²(1) = Var(r_t)          = Σ(r_t - μ)² / (n-1)

σ²(q) = Var(r_t + r_{t-1} + ... + r_{t-q+1}) = Var of q-period return

VR(q) = σ²(q) / (q · σ²(1))
```

**Under the random walk null:** `E[VR(q)] = 1`.

### Z-Statistic (for significance testing)

Lo & MacKinlay derived the asymptotic distribution:

```
Z(q) = (VR(q) - 1) / sqrt(θ(q))

where θ(q) = 2(2q-1)(q-1) / (3q·n)  [homoskedastic version]
```

Z ~ N(0,1) under H₀, so:
- |Z| > 1.96 → reject random walk at 5%
- |Z| > 1.645 → reject at 10%
- Negative Z → mean-reverting; Positive Z → trending

---

## Why Quants Use It

1. **Regime confirmation** — statistically rigorous test whether MR applies right now
2. **Multi-horizon test** — test q = 2, 4, 8, 16 bars simultaneously (different time scales)
3. **No distributional assumptions** — the heteroskedastic version is robust
4. **Complements ADF** — ADF tests levels, VR tests return serial correlation
5. **Interpretable** — VR = 0.85 means "variance grows 15% slower than random walk"

---

## Python Implementation

### Basic Variance Ratio

```python
import numpy as np
from scipy.stats import norm

def variance_ratio(prices: np.ndarray, q: int = 2):
    """
    Calculate variance ratio VR(q).

    Args:
        prices: price series (will compute log returns internally)
        q: holding period for comparison (try 2, 4, 8, 16)

    Returns:
        VR value, z-statistic, p-value
    """
    log_prices = np.log(prices)
    returns = np.diff(log_prices)
    n = len(returns)

    # 1-period variance
    mu = np.mean(returns)
    var_1 = np.sum((returns - mu)**2) / (n - 1)

    # q-period variance (overlapping)
    q_returns = np.array([
        np.sum(returns[i:i+q])
        for i in range(n - q + 1)
    ])
    m = len(q_returns)
    mu_q = np.mean(q_returns)
    var_q = np.sum((q_returns - mu_q)**2) / (m - 1)

    vr = var_q / (q * var_1) if var_1 > 0 else 1.0

    # Z-statistic (homoskedastic)
    theta = 2 * (2*q - 1) * (q - 1) / (3 * q * n)
    z_stat = (vr - 1) / np.sqrt(theta) if theta > 0 else 0
    p_value = 2 * (1 - norm.cdf(abs(z_stat)))  # two-tailed

    return {
        "vr": vr,
        "z_stat": z_stat,
        "p_value": p_value,
        "mean_reverting": vr < 1,
        "significant": p_value < 0.10,
        "q": q
    }


def multi_horizon_vr(prices: np.ndarray, q_values: list = [2, 4, 8, 16]):
    """
    Test multiple horizons simultaneously.
    Composite signal: average VR across q values.
    """
    results = {q: variance_ratio(prices, q) for q in q_values}
    avg_vr = np.mean([r["vr"] for r in results.values()])

    return {
        "results_by_q": results,
        "composite_vr": avg_vr,
        "mr_regime": avg_vr < 0.95,
        "strong_mr": avg_vr < 0.85,
    }


def rolling_vr(prices: np.ndarray, window: int = 100, q: int = 4):
    """Rolling variance ratio."""
    vr_series = np.full(len(prices), np.nan)
    for i in range(window, len(prices)):
        result = variance_ratio(prices[i-window:i], q)
        vr_series[i] = result["vr"]
    return vr_series
```

---

## Interpretation

| VR(4) | Interpretation | Trading Mode |
|-------|----------------|--------------|
| < 0.80 | Strong mean reversion | Aggressive MR entry |
| 0.80–0.92 | Mild mean reversion | Normal MR |
| 0.92–1.08 | Approximately random walk | Uncertain — reduce size |
| 1.08–1.20 | Mild trending | Avoid MR |
| > 1.20 | Strong trending (momentum) | Momentum strategy |

*q=4 is most commonly used for intraday (4 × 5-min = 20-min horizon).*

---

## Multi-Horizon Analysis

Running VR at multiple q simultaneously gives a richer picture:

```
q=2  (10-min): VR=0.88 → short-term MR strong
q=4  (20-min): VR=0.91 → medium MR present
q=8  (40-min): VR=1.05 → longer-term: near random walk
q=16 (80-min): VR=1.12 → very long-term: slight trending
```

**Signal:** If VR is MR at q=2 and q=4 but trending at q=16, use short hold times.

---

## As a Data Point (record per trade)

```python
vr_result = multi_horizon_vr(close[-100:])
signals.append({
    ...,
    "VR_q2": vr_result["results_by_q"][2]["vr"],
    "VR_q4": vr_result["results_by_q"][4]["vr"],
    "VR_q8": vr_result["results_by_q"][8]["vr"],
    "VR_Composite": vr_result["composite_vr"],
    "VR_MR_Regime": vr_result["mr_regime"],
})
```

---

## VR vs ADF vs Hurst Comparison

| Test | Tests For | Strength | Weakness |
|------|-----------|----------|---------|
| ADF | Level stationarity | High power | Sensitive to window |
| VR | Return autocorrelation | Multi-horizon | Requires overlap |
| Hurst | Long-memory MR | Intuitive | Computationally heavy |
| **VR** | **Best for short-term regime** | **Fast to compute** | **Power depends on n** |

**Use all three together for highest confidence.**

---

## Relationship to Other Studies

- **ADF Test** (`adf_test.md`): ADF tests price levels; VR tests returns — complementary
- **Hurst Exponent** (implemented in `src/indicators/hurst.py`): H < 0.5 ↔ VR < 1
- **Autocorrelation** (`autocorrelation_ljung_box.md`): VR measures the same thing from a different angle
- **O-U Process** (`ornstein_uhlenbeck.md`): O-U model implies VR < 1

---

## References

- Lo, A.W. & MacKinlay, A.C. (1988) — "Stock Market Prices Do Not Follow Random Walks"
- Lo, A.W. & MacKinlay, A.C. (1989) — "The size and power of the variance ratio test"
- Chan, E. (2013) — *Algorithmic Trading*, Chapter 2
