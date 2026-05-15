# Kyle's Lambda (Price Impact Coefficient)

**Status:** Documented

---

## What Is It?

Kyle's Lambda (λ) is a measure of **market liquidity and price impact** — how much price moves per unit of net order flow. Introduced by Albert Kyle (1985) in his seminal market microstructure model, it represents the cost of trading and the degree to which order flow carries information.

```
ΔPrice = λ × OrderFlow + noise

λ = price impact per unit of order flow

High λ: illiquid market — small orders move price a lot
Low λ:  liquid market — large orders needed to move price
```

---

## Mathematical Basis

### Original Kyle (1985) Model

In Kyle's model, a single informed trader submits order x. The market maker sets price:
```
P = μ + λ·x
λ = σ_v / (2·σ_u)

σ_v = std of fundamental value (information quality)
σ_u = std of noise trader volume
```

### Empirical Estimation from OHLCV Data

Without order book data, estimate λ from delta (what you have):

```
Method 1 — OLS regression:
  ΔP[t] = α + λ · Delta[t] + ε[t]

  Run OLS: price change regressed on signed volume
  λ = coefficient = price change per unit delta
```

```
Method 2 — Amihud-style simplification:
  λ_t = |ΔPrice[t]| / |Volume[t]|

  (Amihud illiquidity ratio — simpler but related concept)
```

---

## Why Quants Use It

| Use Case | Description |
|----------|-------------|
| Informed trading detection | High λ = informed order flow = informed traders present |
| Liquidity regime | High λ = illiquid (thin market) = MR less reliable |
| Absorption confirmation | Low λ + high delta = true absorption (delta not impacting price) |
| Execution quality | Higher λ → expect more slippage |
| Market hours filter | λ is higher at open/close, lower mid-session |

---

## Python Implementation

```python
import numpy as np
from scipy.stats import linregress

def estimate_kyles_lambda(price_changes: np.ndarray,
                           delta: np.ndarray,
                           window: int = 50) -> dict:
    """
    Estimate Kyle's Lambda from price changes and order flow (delta).

    Args:
        price_changes: bar-by-bar price changes (close[t] - close[t-1])
        delta: bar-by-bar signed volume (buy_vol - sell_vol)
        window: rolling estimation window

    Returns:
        lambda_: price impact coefficient
        r_squared: R² of the regression
    """
    if len(price_changes) < 10:
        return {"lambda": 0, "r_squared": 0}

    # OLS: ΔP = α + λ × delta
    slope, intercept, r, p, se = linregress(delta, price_changes)

    return {
        "lambda": slope,
        "alpha": intercept,
        "r_squared": r**2,
        "p_value": p,
        "std_error": se,
    }


def rolling_kyles_lambda(price_changes: np.ndarray,
                          delta: np.ndarray,
                          window: int = 50) -> np.ndarray:
    """Rolling Kyle's Lambda estimation."""
    n = len(price_changes)
    lambdas = np.full(n, np.nan)

    for i in range(window, n):
        result = estimate_kyles_lambda(
            price_changes[i-window:i],
            delta[i-window:i]
        )
        lambdas[i] = result["lambda"]

    return lambdas


def lambda_percentile(lambdas: np.ndarray, lookback: int = 200) -> np.ndarray:
    """
    Lambda percentile rank vs recent history.
    High percentile = illiquid = high price impact.
    """
    pctile = np.full(len(lambdas), np.nan)
    for i in range(lookback, len(lambdas)):
        window = lambdas[i-lookback:i]
        valid = window[~np.isnan(window)]
        if len(valid) > 0:
            pctile[i] = np.sum(valid <= lambdas[i]) / len(valid)
    return pctile
```

---

## Interpreting Lambda for NQ Futures

Lambda is in units of **price points per contract delta**.

| Lambda Level | Interpretation | MR Strategy |
|-------------|----------------|-------------|
| Low (< 25th pctile) | Liquid — large orders barely move price | Good for MR |
| Normal (25th–75th) | Normal liquidity | Normal |
| High (> 75th pctile) | Illiquid — orders move price easily | Caution |
| Very High (> 90th) | Very illiquid / informed trading | Avoid |

---

## Lambda + Absorption Synergy

Your existing `AbsRatio = Range / |Delta|` is the **inverse** of price impact:
- Low AbsRatio = high delta relative to range = delta not moving price = **absorption** (same as low λ × delta)

Kyle's Lambda is **more rigorous** because:
1. It's estimated from a regression, accounting for baseline price drift
2. It gives a statistical significance (p-value, R²)
3. It's comparable across time periods

**Combine both:** Low AbsRatio AND low Lambda = strong absorption signal.

---

## As a Data Point (record per trade)

```python
price_changes = np.diff(close)
lambda_vals = rolling_kyles_lambda(price_changes, delta[1:], window=50)
lambda_pctile = lambda_percentile(lambda_vals)

signals.append({
    ...,
    "KyleLambda": lambda_vals[i],
    "KyleLambda_Pctile": lambda_pctile[i],
})
```

---

## Relationship to Other Studies

- **Order Flow Imbalance** (`order_flow_imbalance.md`): OFI measures directional pressure; Lambda measures its price impact
- **VPIN** (`vpin.md`): VPIN measures informed trading probability; Lambda measures its market price
- **Amihud Illiquidity** (`amihud_illiquidity.md`): Amihud is a simplified per-bar Lambda estimate

---

## References

- Kyle, A.S. (1985) — "Continuous Auctions and Insider Trading", *Econometrica*
- Glosten, L. & Harris, L. (1988) — "Estimating the Components of the Bid-Ask Spread"
- Hasbrouck, J. (2009) — "Trading Costs and Returns for U.S. Equities"
- *Advances in Financial Machine Learning* — Lopez de Prado (related microstructure)
