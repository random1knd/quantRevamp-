# GARCH Volatility Modeling

**Status:** Documented

---

## What Is It?

GARCH (Generalized AutoRegressive Conditional Heteroskedasticity) models the **time-varying volatility** of returns. The key insight: volatility is not constant — it clusters (high-vol follows high-vol, low-vol follows low-vol). GARCH captures this clustering and produces a **one-step-ahead volatility forecast**.

Developed by Bollerslev (1986), extending Engle's ARCH (1982). Standard in risk management, option pricing, and strategy filtering.

---

## Mathematical Basis

### GARCH(1,1) Model

```
Return model:   r_t = μ + ε_t,   where ε_t = σ_t · z_t,   z_t ~ N(0,1)

Variance model: σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}

ω (omega)  = base variance (long-run variance component)
α (alpha)  = ARCH coefficient (weight on lagged squared return)
β (beta)   = GARCH coefficient (weight on lagged variance)

Stationarity constraint: α + β < 1
Long-run variance: σ²_LR = ω / (1 - α - β)
```

### Intuition

```
σ²_t = ω  +  α·(yesterday's shock)²  +  β·(yesterday's variance)
         ↑         ↑                        ↑
      base    short-term impact       long-term memory
```

- High α: vol reacts quickly to shocks (spike then decay)
- High β: vol is persistent (current regime lasts)
- α + β close to 1: integrated GARCH — shocks are permanent (trending vol)

### Typical Parameters for Equity Futures

```
ω:     1e-6 to 1e-4
α:     0.05 to 0.15
β:     0.80 to 0.94
α+β:   typically 0.95 to 0.99
```

---

## Why Quants Use It

| Use Case | Description |
|----------|-------------|
| Volatility regime filter | High forecast vol = trending; low = MR opportunity |
| Dynamic position sizing | Size = RiskTarget / GARCH_vol |
| Stop placement | ATR-like but forward-looking |
| Options pricing | GARCH vol as option vol estimate |
| Risk management | VaR calculation |

---

## Python Implementation

```python
import numpy as np
from arch import arch_model   # pip install arch

def fit_garch(returns: np.ndarray, p: int = 1, q: int = 1):
    """
    Fit GARCH(p,q) model to return series.

    Args:
        returns: daily or bar-by-bar returns (as percentages or fractions)
        p: GARCH order (usually 1)
        q: ARCH order (usually 1)

    Returns:
        model result with volatility forecast
    """
    # arch expects percentage returns (multiply by 100 if fractional)
    scale = 100 if np.std(returns) < 0.1 else 1
    r = returns * scale

    am = arch_model(r, vol='Garch', p=p, q=q, dist='Normal')
    res = am.fit(disp='off', show_warning=False)

    return res


def garch_vol_forecast(returns: np.ndarray, window: int = 500):
    """
    Rolling GARCH(1,1) one-step-ahead volatility forecast.

    Returns:
        vol_forecast: conditional volatility at each bar (in return units)
    """
    n = len(returns)
    vol = np.full(n, np.nan)

    for i in range(window, n):
        try:
            res = fit_garch(returns[i-window:i])
            # One-step-ahead forecast
            forecast = res.forecast(horizon=1, reindex=False)
            vol[i] = np.sqrt(forecast.variance.values[-1, 0])
        except Exception:
            pass

    return vol


def garch_vol_percentile(vol_forecast: np.ndarray, lookback: int = 252):
    """
    GARCH vol percentile rank vs recent history.
    Low percentile = quiet market (MR opportunity)
    High percentile = volatile market (trend/avoid MR)
    """
    pctile = np.full(len(vol_forecast), np.nan)
    for i in range(lookback, len(vol_forecast)):
        window_vol = vol_forecast[i-lookback:i]
        valid = window_vol[~np.isnan(window_vol)]
        if len(valid) > 0:
            pctile[i] = np.sum(valid <= vol_forecast[i]) / len(valid)
    return pctile


def simple_realized_vol(returns: np.ndarray, window: int = 20,
                         annualize: bool = True, bars_per_year: int = 78):
    """
    Simple realized volatility (no GARCH fitting needed).
    Use as a lighter alternative to GARCH for data point recording.

    bars_per_year for NQ 5-min: ~6.5 hours × 12 bars/hr × 252 days ≈ 19,656
    bars_per_year for NQ 1-min: ~6.5 × 60 × 252 ≈ 98,280
    """
    rv = pd.Series(returns).rolling(window).std().values
    if annualize:
        rv = rv * np.sqrt(bars_per_year)
    return rv
```

---

## Volatility Regime Classification

```python
def classify_vol_regime(vol_pctile: float) -> str:
    """
    Classify current volatility regime based on percentile rank.
    """
    if vol_pctile < 0.25:
        return "LOW"       # Quiet — MR strategies work best
    elif vol_pctile < 0.50:
        return "NORMAL"    # Average — normal conditions
    elif vol_pctile < 0.75:
        return "ELEVATED"  # Above average — reduce MR size
    else:
        return "HIGH"      # Volatile — trending, consider avoiding MR
```

---

## GARCH for Mean Reversion Strategy

### Key insight: Low volatility regimes favor mean reversion

When GARCH vol is in the bottom quartile of its history:
- Price swings are contained
- Institutions are ranging/accumulating
- Reversions happen faster

When GARCH vol is elevated:
- Directional moves are sustained
- Stop-outs are more likely for MR trades
- Trend-following works better

### As filter

```python
# Filter: only trade MR when vol regime is LOW or NORMAL
if vol_regime in ["LOW", "NORMAL"]:
    # Proceed with absorption fade / MR entry
    pass
elif vol_regime == "ELEVATED":
    # Reduce position size by 50%
    pass
else:  # HIGH
    # Skip trade entirely
    pass
```

---

## Realized Volatility (RV) — Simpler Alternative

For real-time data points without GARCH fitting:

```
RV_5min = sqrt(252 × 78) × std(5-min log returns, last 20 bars)
        = 131.9 × std(log_returns[-20:])
```

| RV Level (annualized) | NQ Interpretation |
|----------------------|-------------------|
| < 10% | Very quiet — strong MR signal |
| 10–15% | Normal — MR works well |
| 15–25% | Elevated — reduce size |
| > 25% | High vol — trending regime |

---

## As a Data Point (record per trade)

```python
returns = np.diff(np.log(close))
rv = simple_realized_vol(returns, window=20)
rv_pctile = garch_vol_percentile(rv, lookback=252 * 78)  # 1-year lookback

signals.append({
    ...,
    "RealizedVol_20": rv[i],
    "VolPctile": rv_pctile[i],
    "VolRegime": classify_vol_regime(rv_pctile[i]),
})
```

---

## Relationship to Other Studies

- **HMM Regime Detection** (`hidden_markov_models.md`): HMM state ↔ GARCH vol level
- **Variance Ratio** (`variance_ratio.md`): Low vol regime → VR more likely < 1
- **ATR**: ATR is a cruder trailing measure; GARCH forecasts forward

---

## References

- Engle, R.F. (1982) — "Autoregressive Conditional Heteroscedasticity"
- Bollerslev, T. (1986) — "Generalized Autoregressive Conditional Heteroscedasticity"
- Python `arch` library — Kevin Sheppard: https://arch.readthedocs.io
