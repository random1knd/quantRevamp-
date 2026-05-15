# Time-Series Momentum (TSMOM)

**Status:** Documented

---

## What Is It?

Time-Series Momentum (TSMOM) is a strategy that goes **long if an asset's past return is positive, short if negative** — trading on the persistence of trends. Unlike cross-sectional momentum (ranking assets against each other), TSMOM is a single-asset strategy: trade each instrument based solely on its own past returns.

Documented rigorously by Moskowitz, Ooi & Pedersen (2012), who found TSMOM delivers positive risk-adjusted returns across 58 liquid futures contracts over 25+ years.

**Relevance to NQ:** TSMOM is the **opposite of mean reversion**. Understanding when it works vs when MR works is essential for regime-aware trading. TSMOM is your competition — when momentum is strong, don't fade it.

---

## Mathematical Basis

### Signal Construction (Moskowitz et al.)

```
r_{t-12,t-1} = cumulative return over past 12 months (excluding last month)

Signal: long if r > 0, short if r < 0

Position size (volatility-scaled):
  w = signal × (target_vol / σ_t)

where σ_t = annualized realized volatility over past 1 month
```

### For Intraday NQ (adapted)

```
r_{t-N, t} = cumulative log return over last N bars

Fast TSMOM (N = 12 bars = 1 hour at 5-min):
  if r_1h > 0: trend is up, avoid SELL_FADE
  if r_1h < 0: trend is down, avoid BUY_FADE

Slow TSMOM (N = 78 bars = 1 day):
  if r_1d > 0: daily trend up
  if r_1d < 0: daily trend down
```

### Momentum Score (continuous version)

```
MOM_score = r_t / σ_t

Positive = uptrend; Negative = downtrend
Magnitude = strength of trend relative to volatility
```

---

## Why Quants Use It

| Use Case | Description |
|----------|-------------|
| Strategy selection | Strong momentum → use trend-following, not MR |
| MR filter | Trade MR only when momentum score is low/zero |
| Direction bias | Use trend direction for MR directional preference |
| Regime detection | High |MOM_score| = trending; low ≈ 0 = ranging |

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def tsmom_signal(close: np.ndarray, lookback: int = 78,
                  vol_window: int = 20) -> dict:
    """
    Time-Series Momentum signal for NQ.

    Args:
        close: price series
        lookback: bars to look back for return (78 = 1 day at 5-min)
        vol_window: bars for volatility estimation

    Returns:
        signal: +1 (long trend), -1 (short trend)
        score: continuous momentum score (r/vol)
    """
    log_returns = np.diff(np.log(close))
    n = len(close)

    signals = np.zeros(n)
    scores = np.full(n, np.nan)

    for i in range(lookback + vol_window, n):
        # Cumulative return over lookback
        r = np.sum(log_returns[i-lookback:i])

        # Realized vol (annualized for 5-min bars)
        vol = np.std(log_returns[i-vol_window:i]) * np.sqrt(252 * 78)
        if vol == 0:
            continue

        score = r / vol
        scores[i] = score
        signals[i] = np.sign(r)

    return {
        "signal": signals,
        "score": scores,
        "is_trending": np.abs(scores) > 0.5,
    }


def multi_horizon_momentum(close: np.ndarray,
                             horizons: dict = None) -> dict:
    """
    Compute momentum at multiple time horizons.
    Different horizons tell you about different trend structures.

    Default horizons for NQ 5-min:
      'ultra_short': 6 bars = 30 min
      'short':       18 bars = 1.5 hours
      'medium':      78 bars = 1 day
      'long':        390 bars = 1 week
    """
    if horizons is None:
        horizons = {
            'ultra_short': 6,
            'short': 18,
            'medium': 78,
            'long': 390,
        }

    results = {}
    for name, h in horizons.items():
        if len(close) > h + 20:
            result = tsmom_signal(close, lookback=h)
            results[name] = result

    # Composite: agree across horizons?
    if results:
        signals_arr = np.array([r["signal"] for r in results.values()])
        results["composite_signal"] = np.mean(signals_arr, axis=0)
        results["agreement"] = np.abs(results["composite_signal"])

    return results


def momentum_mr_compatibility(mom_score: float,
                                mr_direction: str) -> dict:
    """
    Check if momentum is compatible with a mean reversion trade.

    Args:
        mom_score: TSMOM score (positive = uptrend, negative = downtrend)
        mr_direction: 'BUY_FADE' or 'SELL_FADE'

    Returns:
        compatible: True if momentum does NOT oppose the MR trade
        quality: 'IDEAL', 'NEUTRAL', 'AGAINST'
    """
    if mr_direction == "SELL_FADE":
        # Selling into strength — ideal when trend is DOWN (mom < 0)
        if mom_score < -0.3:
            return {"compatible": True, "quality": "IDEAL"}
        elif -0.3 <= mom_score <= 0.3:
            return {"compatible": True, "quality": "NEUTRAL"}
        else:
            return {"compatible": False, "quality": "AGAINST"}  # Don't fade uptrend

    elif mr_direction == "BUY_FADE":
        if mom_score > 0.3:
            return {"compatible": True, "quality": "IDEAL"}
        elif -0.3 <= mom_score <= 0.3:
            return {"compatible": True, "quality": "NEUTRAL"}
        else:
            return {"compatible": False, "quality": "AGAINST"}  # Don't fade downtrend

    return {"compatible": True, "quality": "UNKNOWN"}
```

---

## TSMOM as a Mean Reversion Filter

The practical value for your system: **use TSMOM to reject MR trades that fight the trend.**

```
Good MR SELL setup:
  - Price extended above VWAP (as usual)
  - TSMOM score NEGATIVE (market is tired/already rolled over)
  - Score close to zero at multiple horizons

Bad MR SELL setup (avoid):
  - Price extended above VWAP
  - TSMOM score STRONGLY POSITIVE (momentum is driving price up)
  - This is an uptrending market making new highs → don't fade it
```

---

## Momentum Score Thresholds

| |MOM Score| | Regime | MR Trade Quality |
|------------|--------|-----------------|
| 0.0 – 0.3 | Range-bound | Excellent for MR |
| 0.3 – 0.7 | Mild trend | Acceptable for MR |
| 0.7 – 1.5 | Moderate trend | Reduce size |
| > 1.5 | Strong trend | Skip MR entirely |

---

## As a Data Point (record per trade)

```python
mom_data = multi_horizon_momentum(close[:i+1])
signals.append({
    ...,
    "MOM_Short": mom_data["short"]["score"][i] if "short" in mom_data else 0,
    "MOM_Medium": mom_data["medium"]["score"][i] if "medium" in mom_data else 0,
    "MOM_Composite": mom_data.get("composite_signal", np.zeros(i+1))[i],
    "MOM_IsTrending": mom_data.get("agreement", np.zeros(i+1))[i] > 0.5,
})
```

---

## TSMOM vs Mean Reversion — Coexistence

These two strategies are not enemies — they occupy different regimes:

| Condition | TSMOM Works | MR Works |
|-----------|-------------|----------|
| Low volatility | Weak | Strong |
| High volatility | Strong | Weak |
| Trending market | Yes | No |
| Ranging market | No | Yes |
| Post-news / event | Often | Rarely |

**System design:** Use the same data points (MOM score, VR, AC₁, HMM) to switch between TSMOM and MR strategies. Never trade both simultaneously on the same instrument.

---

## Relationship to Other Studies

- **Variance Ratio** (`variance_ratio.md`): VR > 1 = trending = TSMOM regime
- **Autocorrelation** (`autocorrelation_regime.md`): AC₁ > 0 = momentum regime
- **HMM** (`hidden_markov_models.md`): High-vol HMM state = trending = TSMOM
- **GARCH** (`garch_volatility.md`): High vol = trend following works

---

## References

- Moskowitz, T., Ooi, Y.H. & Pedersen, L. (2012) — "Time Series Momentum", *Journal of Financial Economics*
- Hurst, B., Ooi, Y.H. & Pedersen, L. (2017) — "A Century of Evidence on Trend-Following Investing"
- AQR Capital — time series momentum research library
