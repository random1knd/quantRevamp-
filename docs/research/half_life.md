# Half-Life of Mean Reversion

**Status:** Documented

---

## What Is It?

Half-life measures how many bars it takes for a mean-reverting price series to close **half the gap** between its current value and its equilibrium mean. It is the single most practical metric for mean reversion trading: it tells you the expected hold time of a trade.

```
Half-Life = ln(2) / θ

where θ is the O-U mean reversion speed (see ornstein_uhlenbeck.md)
```

Equivalently, derived from the AR(1) regression:

```
Half-Life = -ln(2) / ln(1 + β)

where β is the OLS coefficient from:
ΔP[t] = α + β·P[t-1] + ε[t]

β must be negative for mean reversion to exist.
```

---

## Mathematical Derivation

Starting from the discrete O-U approximation:

```
P[t+1] = P[t] + α + β·P[t] + ε
       = (1 + β)·P[t] + α + ε
```

The "auto-regressive coefficient" is `λ = 1 + β`.

For mean reversion: `0 < λ < 1` (equivalently `β < 0`).

The expected gap to mean decays geometrically:
```
E[gap at time t] = λ^t · gap_at_t=0
```

At half-life H: `λ^H = 0.5`
```
H = ln(0.5) / ln(λ) = -ln(2) / ln(1 + β)
```

---

## Why It's Useful

| Use Case | How Half-Life Helps |
|----------|-------------------|
| Hold time | Expected bars to reach target = ~1–2 half-lives |
| Trade filtering | Skip trades with half-life > max_hold_bars |
| Position sizing | Shorter half-life → more aggressive sizing |
| Stop placement | Stop at 2–3× half-life if no reversion |
| Strategy design | Select bar timeframe matching typical half-life |

---

## Typical Values for NQ Futures

| Timeframe | Half-Life Range | Tradeable Range |
|-----------|----------------|-----------------|
| 1-min bars | 1–30 bars | 3–15 bars |
| 5-min bars | 1–50 bars | 5–25 bars |
| 1-hour bars | 1–20 bars | 3–10 bars |

*These vary with market regime. Estimate rolling.*

---

## Python Implementation

### Method 1: OLS Regression (Ernie Chan method)

```python
import numpy as np
from scipy.stats import linregress

def estimate_half_life(prices: np.ndarray) -> float:
    """
    Estimate half-life of mean reversion using OLS regression.
    (Ernie Chan, Algorithmic Trading, 2013)

    Args:
        prices: price series (use log prices for multiplicative dynamics)

    Returns:
        half_life in bars (np.inf if not mean-reverting)
    """
    y = np.diff(prices)          # ΔP[t]
    x = prices[:-1]              # P[t-1]

    slope, intercept, _, _, _ = linregress(x, y)
    beta = slope

    if beta >= 0:
        return np.inf  # trending or random walk

    half_life = -np.log(2) / np.log(1 + beta)
    return max(half_life, 0)


def rolling_half_life(prices: np.ndarray, window: int = 100) -> np.ndarray:
    """Rolling half-life estimate."""
    hl = np.full(len(prices), np.nan)
    for i in range(window, len(prices)):
        hl[i] = estimate_half_life(prices[i-window:i])
    return hl
```

### Method 2: From O-U theta

```python
def half_life_from_theta(theta: float) -> float:
    """Convert O-U theta to half-life in bars."""
    if theta <= 0:
        return np.inf
    return np.log(2) / theta
```

### Method 3: With ADF Confirmation

```python
from statsmodels.tsa.stattools import adfuller

def half_life_with_significance(prices: np.ndarray, window: int = 100):
    """
    Return half-life only if ADF test confirms mean reversion.
    """
    hl = estimate_half_life(prices[-window:])

    # ADF test: H0 = unit root (random walk), reject = mean reverting
    adf_result = adfuller(prices[-window:], maxlags=1)
    p_value = adf_result[1]

    return {
        "half_life": hl,
        "adf_p_value": p_value,
        "statistically_significant": p_value < 0.05,
        "tradeable": hl < 30 and p_value < 0.10
    }
```

---

## Interpretation Table

| Half-Life | Action | Max Hold |
|-----------|--------|----------|
| < 3 bars | Very fast — scalp only | 3 bars |
| 3–10 bars | Ideal for intraday | 10–20 bars |
| 10–25 bars | Good | 25–50 bars |
| 25–50 bars | Marginal | 50–100 bars |
| > 50 bars | Avoid | — |
| ∞ (β ≥ 0) | Do not trade MR | — |

---

## Connection to ADF Test

The ADF test is essentially testing whether β (from the regression above) is statistically significantly negative. If the ADF null hypothesis (unit root) is rejected:
- The series is stationary / mean-reverting
- The half-life estimate is meaningful

**Both should pass**: `half_life < threshold` AND `adf_p_value < 0.10`.

---

## As a Data Point (record per trade)

```python
# In compute_indicators():
hl = estimate_half_life(close[-100:])

# In generate_signals():
signals.append({
    ...,
    "HalfLife": hl,
    "HalfLife_Valid": hl < 30 and not np.isinf(hl),
})
```

---

## Relationship to Other Studies

- **O-U Process** (`ornstein_uhlenbeck.md`): half-life = ln(2)/θ
- **ADF Test** (`adf_test.md`): confirms β < 0 is statistically significant
- **Variance Ratio** (`variance_ratio.md`): complementary regime test

---

## References

- Chan, E. (2013) — *Algorithmic Trading*, Chapter 2: Mean Reversion of Stocks and ETFs
- Chan, E. (2009) — *Quantitative Trading*
- Avellaneda & Lee (2010) — statistical arbitrage, half-life estimation
- Lo & MacKinlay (1988) — variance ratio test (related stationarity concept)
