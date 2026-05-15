# ADF Test (Augmented Dickey-Fuller)

**Status:** Documented

---

## What Is It?

The Augmented Dickey-Fuller test is a **statistical hypothesis test for stationarity** (mean reversion). It tests whether a time series has a "unit root" (random walk) or is stationary (mean-reverting).

```
H₀ (null):     series has a unit root → random walk → mean reversion does NOT apply
H₁ (alternative): series is stationary → mean-reverting → mean reversion CAN apply

Reject H₀ when: p-value < significance level (0.05 or 0.10)
```

In trading: **use ADF as a gating test before any mean reversion trade or strategy.**

---

## Mathematical Basis

The ADF test estimates this regression:

```
ΔY_t = α + β·Y[t-1] + Σ γ_i·ΔY[t-i] + ε_t

The test statistic is: t-statistic of β̂ (the coefficient on Y[t-1])
```

The **lags** (Σ γ_i terms) are the "augmented" part — they remove autocorrelation in residuals that would bias the test.

Key: if β < 0 significantly, the series is mean-reverting.

The ADF t-statistic has a **non-standard distribution** (Dickey-Fuller tables, not normal). Critical values:

| Significance | Critical Value |
|-------------|----------------|
| 1% | -3.43 |
| 5% | -2.86 |
| 10% | -2.57 |

*More negative ADF stat = stronger evidence of stationarity.*

---

## Why Quants Use It

1. **Validates mean reversion strategy applicability** — don't trade MR on a trending series
2. **Rolling regime filter** — trade MR only during stationary regimes
3. **Pairs trading** — test if spread between two assets is stationary (cointegration)
4. **Confirms half-life estimates** — half-life is only meaningful if ADF rejects H₀
5. **Industry standard** — every serious quant uses this before MR strategies

---

## Python Implementation

### Basic Usage

```python
from statsmodels.tsa.stattools import adfuller
import numpy as np

def adf_test(prices: np.ndarray, maxlags: int = None, signif: float = 0.05):
    """
    Run ADF test on a price series.

    Returns:
        dict with statistic, p_value, is_stationary
    """
    result = adfuller(prices, maxlags=maxlags, autolag='AIC')

    return {
        "adf_stat": result[0],
        "p_value": result[1],
        "lags_used": result[2],
        "n_obs": result[3],
        "critical_1pct": result[4]["1%"],
        "critical_5pct": result[4]["5%"],
        "critical_10pct": result[4]["10%"],
        "is_stationary": result[1] < signif,
    }
```

### Rolling ADF Filter (for real-time trading)

```python
def rolling_adf(prices: np.ndarray, window: int = 100, signif: float = 0.10):
    """
    Rolling ADF test — returns p-value at each bar.
    Use as a regime filter: only trade when p_value < signif.
    """
    p_values = np.full(len(prices), np.nan)
    for i in range(window, len(prices)):
        result = adfuller(prices[i-window:i], maxlags=1, autolag=None)
        p_values[i] = result[1]
    return p_values


# In strategy:
adf_p = rolling_adf(close, window=100)
is_mr_regime = adf_p < 0.10   # Only trade when series is stationary
```

### Combined with Half-Life

```python
def mean_reversion_regime_check(prices: np.ndarray, window: int = 100):
    """
    Full regime check: ADF + Half-Life combined gate.
    Both must pass for mean reversion trades to be taken.
    """
    from .half_life import estimate_half_life

    recent = prices[-window:]

    # ADF
    adf = adfuller(recent, maxlags=1, autolag=None)
    p_value = adf[1]

    # Half-life
    hl = estimate_half_life(recent)

    return {
        "adf_p_value": p_value,
        "half_life": hl,
        "mr_regime": p_value < 0.10 and hl < 50 and not np.isinf(hl),
        "confidence": "HIGH" if p_value < 0.05 and hl < 20 else
                      "MEDIUM" if p_value < 0.10 and hl < 35 else "LOW"
    }
```

---

## Interpretation Guide

| ADF p-value | ADF Stat | Interpretation | Action |
|-------------|----------|----------------|--------|
| < 0.01 | < -3.43 | Very strong stationarity | Trade aggressively |
| 0.01 – 0.05 | -3.43 to -2.86 | Strong stationarity | Trade normally |
| 0.05 – 0.10 | -2.86 to -2.57 | Marginal stationarity | Reduce size |
| 0.10 – 0.30 | -2.57 to -1.8 | Borderline | Skip or reduce |
| > 0.30 | > -1.8 | Random walk / trending | Do NOT trade MR |

---

## Important Limitations

1. **Lookback sensitivity** — short windows give noisy results. Use ≥ 50 bars minimum, 100 preferred.
2. **Non-stationary in trending markets** — NQ trending day will fail ADF, as expected.
3. **Multiple testing problem** — if you run rolling ADF, some false positives occur by chance.
4. **Unit root in levels, stationary in price changes** — most asset prices fail ADF in levels; consider testing on VWAP-deviation or spread.

**Practical tip for NQ:** Don't ADF-test raw prices. Test the VWAP deviation or the O-U residual.

---

## As a Data Point (record per trade)

```python
# Record ADF p-value on VWAP deviation series (last 100 bars)
vwap_dev = close[-100:] - vwap[-100:]
adf_result = adfuller(vwap_dev, maxlags=1, autolag=None)
signals.append({
    ...,
    "ADF_PValue": adf_result[1],
    "ADF_Stationary": adf_result[1] < 0.10,
})
```

---

## Relationship to Other Studies

- **Half-Life** (`half_life.md`): ADF test validates the β used in half-life calculation
- **Variance Ratio** (`variance_ratio.md`): complementary stationarity test (less power but more intuitive)
- **O-U Process** (`ornstein_uhlenbeck.md`): ADF is the significance test for O-U regression
- **Cointegration** (`cointegration.md`): ADF applied to a spread/residual series

---

## References

- Dickey & Fuller (1979) — "Distribution of the Estimators for Autoregressive Time Series with a Unit Root"
- MacKinnon (1994) — critical value tables
- Chan, E. (2013) — *Algorithmic Trading*, stationarity chapter
- statsmodels documentation: `statsmodels.tsa.stattools.adfuller`
