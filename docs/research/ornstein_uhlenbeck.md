# Ornstein-Uhlenbeck Process

**Status:** Documented

---

## What Is It?

A continuous-time stochastic process that models mean-reverting behavior. Originally described by Uhlenbeck & Ornstein (1930) for Brownian particle velocity. Now foundational in quantitative finance for statistical arbitrage, pairs trading, and single-asset mean reversion.

```
dX_t = θ(μ - X_t)dt + σ dW_t

θ (theta)  = speed of mean reversion (rate of pull back toward μ)
μ (mu)     = long-term equilibrium mean
σ (sigma)  = volatility / diffusion coefficient
dW_t       = Wiener process increment (random noise)
```

The key insight: unlike a random walk, an O-U process is always being pulled back toward μ. The stronger θ, the faster the pull.

---

## Mathematical Basis

### Discrete Approximation (for real data)

For price series sampled at interval Δt, the O-U SDE discretizes to:

```
X[t+1] - X[t] = α + β·X[t] + ε[t]

where:
  α = θ·μ·Δt
  β = -θ·Δt        (negative β = mean-reverting)
  ε ~ N(0, σ²_ε)
```

This means: **run OLS regression of (X[t+1] - X[t]) on X[t]**.

### Parameter Recovery from Regression Coefficients

```
θ = -β / Δt            (mean reversion speed)
μ = α / (θ·Δt) = -α/β  (long-term mean)
σ = std(ε) / sqrt(Δt)  (annualized volatility)
```

### Half-Life (derived from θ)

```
half_life = ln(2) / θ
```

A half-life of 5 bars means it takes ~5 bars to close half the gap to μ.

---

## Why Quants Use It

1. **Quantifies mean reversion speed** — θ tells you not just *if* MR exists but *how fast*
2. **Optimal entry/exit timing** — enter at extreme, exit near μ within ~1 half-life
3. **Position sizing** — size position proportional to distance from μ / σ (like a Z-score)
4. **Trade filtering** — skip trades when θ is low (slow reversion, risk of trend)
5. **Works for spreads, residuals, single assets** — very versatile

---

## How Quants Use It in Practice

| θ Value (5-min bars) | Half-Life | Interpretation | Action |
|---------------------|-----------|----------------|--------|
| > 0.5 | < 1.4 bars | Extremely fast (noise) | Skip — too noisy |
| 0.1 – 0.5 | 1.4–7 bars | Very fast reversion | Strong signal |
| 0.03 – 0.1 | 7–23 bars | Moderate reversion | Good signal |
| 0.01 – 0.03 | 23–70 bars | Slow reversion | Weaker signal |
| < 0.01 | > 70 bars | Near random walk / trending | Avoid |

*Values are for NQ 5-min bars; adjust for different timeframes.*

---

## Python Implementation

```python
import numpy as np
from scipy.stats import linregress

def fit_ou_process(prices: np.ndarray, dt: float = 1.0):
    """
    Fit Ornstein-Uhlenbeck parameters to a price series.

    Args:
        prices: 1D array of prices (log prices recommended)
        dt: time step in bars (default 1)

    Returns:
        dict with theta, mu, sigma, half_life
    """
    x = prices[:-1]          # X[t]
    dx = np.diff(prices)     # X[t+1] - X[t]

    # OLS: dx = alpha + beta * x
    slope, intercept, r, p, se = linregress(x, dx)

    beta = slope       # should be negative for mean reversion
    alpha = intercept

    if beta >= 0:
        return {"theta": 0, "mu": np.mean(prices), "sigma": np.std(prices),
                "half_life": np.inf, "mean_reverting": False}

    theta = -beta / dt
    mu = -alpha / beta
    residuals = dx - (alpha + beta * x)
    sigma = np.std(residuals) / np.sqrt(dt)
    half_life = np.log(2) / theta

    return {
        "theta": theta,
        "mu": mu,
        "sigma": sigma,
        "half_life": half_life,
        "r_squared": r**2,
        "mean_reverting": beta < 0
    }


def rolling_ou(prices: np.ndarray, window: int = 100, dt: float = 1.0):
    """Rolling O-U parameter estimation."""
    results = []
    for i in range(window, len(prices)):
        window_prices = prices[i-window:i]
        params = fit_ou_process(window_prices, dt)
        results.append(params)
    return results


def ou_zscore(prices: np.ndarray, window: int = 100):
    """
    Z-score standardized by O-U equilibrium (mu) and sigma.
    Better than naive Z-score because mu is dynamically estimated.
    """
    params = fit_ou_process(prices[-window:])
    current = prices[-1]
    zscore = (current - params["mu"]) / params["sigma"] if params["sigma"] > 0 else 0
    return zscore, params
```

---

## Key Parameters for NQ 5-min Bars

| Parameter | Typical Range | Trading Threshold |
|-----------|---------------|-------------------|
| θ (theta) | 0.01 – 0.3 | θ > 0.05 = tradeable |
| half_life | 2 – 70 bars | < 20 bars preferred |
| R² of regression | 0.01 – 0.3 | R² > 0.05 = signal exists |
| Lookback window | 50 – 200 bars | 100 bars typical |

---

## Trading Application

### As Entry Filter
```python
params = fit_ou_process(recent_prices)
if params["theta"] > 0.05 and params["half_life"] < 20:
    # Mean reversion likely — proceed with entry
    zscore = (current_price - params["mu"]) / params["sigma"]
    if zscore > 2.0: signal = "SELL_FADE"
    if zscore < -2.0: signal = "BUY_FADE"
```

### As Data Point (record for every trade)
- `OU_Theta`: current θ estimate
- `OU_HalfLife`: current half-life in bars
- `OU_ZScore`: O-U normalized Z-score
- `OU_Mu`: current equilibrium estimate

---

## Relationship to Other Studies

- **Half-Life** (`half_life.md`): directly derived from θ = ln(2)/θ
- **ADF Test** (`adf_test.md`): tests whether β < 0 is statistically significant
- **Variance Ratio** (`variance_ratio.md`): complementary statistical confirmation
- **Z-Score Methods** (`zscore_methods.md`): O-U Z-score is more principled than naive Z-score

---

## References

- Uhlenbeck & Ornstein (1930) — "On the theory of the Brownian motion"
- Chan, E. (2013) — *Algorithmic Trading*, Chapter 2 (O-U pairs trading)
- Chan, E. (2009) — *Quantitative Trading*, mean reversion chapter
- Avellaneda & Lee (2010) — "Statistical Arbitrage in the US Equities Market"
