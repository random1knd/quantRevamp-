# Autocorrelation & Ljung-Box Test (Regime Detection)

**Status:** Documented

---

## What Is It?

**Autocorrelation** measures whether a time series is correlated with a lagged version of itself. In trading:
- **Negative lag-1 autocorrelation (AC₁ < 0)**: returns tend to reverse → mean-reverting regime
- **Positive lag-1 autocorrelation (AC₁ > 0)**: returns tend to continue → trending regime
- **AC₁ ≈ 0**: approximately random walk

The **Ljung-Box Q-test** formally tests whether multiple autocorrelation lags are jointly zero — a statistical gate for whether return predictability exists at all.

---

## Mathematical Basis

### Autocorrelation at Lag k

```
AC(k) = Cov(r_t, r_{t-k}) / Var(r_t)

       = [Σ(r_t - μ)(r_{t-k} - μ)] / [Σ(r_t - μ)²]

Range: -1 to +1
AC(1) < 0  → mean-reverting tendency
AC(1) > 0  → trending tendency
AC(1) = 0  → no predictability (efficient)
```

### Ljung-Box Q-Statistic

Tests H₀: all AC(1), ..., AC(h) are zero (no autocorrelation):

```
Q = n(n+2) × Σ[k=1 to h] (AC(k)² / (n-k))

Under H₀: Q ~ χ²(h)
Reject H₀ if p-value < 0.05 → returns are predictable (autocorrelated)
```

### Partial Autocorrelation (PACF)

PACF at lag k measures correlation at lag k **after removing the effect of shorter lags**. More useful than ACF for understanding the pure lag-k relationship.

---

## Why Quants Use It

| Use Case | Description |
|----------|-------------|
| Regime classification | AC₁ sign tells you MR vs trend regime instantly |
| Statistical gate | Ljung-Box must reject before trusting AC₁ |
| Strategy selection | Negative AC → MR; Positive AC → momentum |
| Timeframe selection | Find the bar frequency where AC₁ is most negative |
| Combination with VR | VR < 1 ↔ AC₁ < 0 — same thing from different angles |

---

## Python Implementation

```python
import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox

def return_autocorrelation(returns: np.ndarray,
                             max_lag: int = 10) -> dict:
    """
    Compute autocorrelations and Ljung-Box test.

    Args:
        returns: bar-by-bar log returns
        max_lag: maximum lag to compute

    Returns:
        dict with AC values, Ljung-Box results, regime classification
    """
    n = len(returns)
    if n < max_lag + 5:
        return {}

    r = pd.Series(returns)

    # ACF at each lag
    ac = {f"AC_{k}": r.autocorr(lag=k) for k in range(1, max_lag+1)}

    # Ljung-Box test (joint significance of all lags up to max_lag)
    lb = acorr_ljungbox(returns, lags=[max_lag], return_df=True)
    lb_stat = lb['lb_stat'].values[0]
    lb_pvalue = lb['lb_pvalue'].values[0]

    # Regime classification
    ac1 = ac["AC_1"]
    ac5 = ac.get("AC_5", 0)

    if lb_pvalue < 0.10:  # Returns are predictable
        if ac1 < -0.05:
            regime = "MEAN_REVERTING"
        elif ac1 > 0.05:
            regime = "TRENDING"
        else:
            regime = "MIXED"
    else:
        regime = "RANDOM_WALK"

    return {
        **ac,
        "LjungBox_Stat": lb_stat,
        "LjungBox_PValue": lb_pvalue,
        "Returns_Predictable": lb_pvalue < 0.10,
        "AC_Regime": regime,
        "AC1_MR_Score": -ac1,  # Positive = more MR-like
    }


def rolling_ac1(prices: np.ndarray, window: int = 50) -> np.ndarray:
    """
    Rolling lag-1 autocorrelation — real-time MR regime indicator.

    Negative values = mean-reverting regime.
    """
    returns = np.diff(np.log(prices))
    ac1 = np.full(len(prices), np.nan)

    for i in range(window, len(returns)):
        r = pd.Series(returns[i-window:i])
        ac1[i+1] = r.autocorr(lag=1)  # +1 to align with prices

    return ac1


def ac_regime_filter(prices: np.ndarray, window: int = 50,
                      threshold: float = -0.05) -> np.ndarray:
    """
    Returns boolean array: True when AC₁ < threshold (mean-reverting).
    Use as a gate: only trade MR when this is True.
    """
    ac1 = rolling_ac1(prices, window)
    return ac1 < threshold
```

---

## Interpretation

### AC₁ Values

| AC₁ | Regime | Mean Reversion Trade |
|-----|--------|---------------------|
| < -0.15 | Strong MR | Full size |
| -0.15 to -0.05 | Mild MR | Normal size |
| -0.05 to +0.05 | Random walk | Reduce / skip |
| +0.05 to +0.15 | Mild trend | Skip MR |
| > +0.15 | Strong trend | Momentum strategy instead |

### Ljung-Box Guidance

Before trusting AC₁:
1. Ljung-Box p-value < 0.10 → returns are predictable (trust the AC₁ sign)
2. Ljung-Box p-value > 0.10 → random walk (don't trade directionally)

---

## Multi-Lag AC Analysis

The pattern of AC values across lags reveals regime structure:

```
Mean-reverting pattern:     AC₁ < 0, AC₂ ≈ 0, AC₃ ≈ 0
Oscillating MR:             AC₁ < 0, AC₂ > 0 (alternating)
Trending pattern:           AC₁ > 0, AC₂ > 0 (decaying positive)
Noisy trending:             AC₁ > 0, AC₂ ≈ 0, AC₃ < 0
```

---

## Connection to Variance Ratio

AC₁ and Variance Ratio are mathematically related:

```
VR(2) ≈ 1 + AC₁
VR(q) ≈ 1 + 2·Σ[k=1 to q-1] (1 - k/q) · AC(k)
```

- VR(2) < 1 ↔ AC₁ < 0 — same signal
- VR and AC approach from different angles; use both for robustness

---

## As a Data Point (record per trade)

```python
returns = np.diff(np.log(close))
ac_data = return_autocorrelation(returns[max(0,i-50):i])

signals.append({
    ...,
    "AC1": ac_data.get("AC_1", 0),
    "AC5": ac_data.get("AC_5", 0),
    "LjungBox_P": ac_data.get("LjungBox_PValue", 1),
    "AC_Regime": ac_data.get("AC_Regime", "UNKNOWN"),
})
```

---

## Relationship to Other Studies

- **Variance Ratio** (`variance_ratio.md`): VR(2) = 1 + AC₁ — mathematically identical view
- **ADF Test** (`adf_test.md`): ADF tests price levels; AC tests return serial correlation
- **Hurst Exponent**: H < 0.5 ↔ AC₁ < 0 ↔ VR < 1 — same underlying phenomenon
- **HMM Regime** (`hidden_markov_models.md`): MR HMM state has negative AC₁

---

## References

- Box, G.E.P. & Pierce, D.A. (1970) — "Distribution of Residual Autocorrelations"
- Ljung, G.M. & Box, G.E.P. (1978) — "On a Measure of Lack of Fit in Time Series Models"
- Lo, A.W. & MacKinlay, A.C. (1988) — "Stock Market Prices Do Not Follow Random Walks"
- Chan, E. (2013) — *Algorithmic Trading*, autocorrelation in mean reversion
