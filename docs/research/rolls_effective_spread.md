# Roll's Effective Spread Estimator

**Status:** New Study

---

## Summary

Roll's effective spread estimator is a microstructure measure that infers the **hidden bid-ask spread** from transaction prices alone, without needing direct bid-ask quotes. Proposed by Richard Roll (1984), it exploits the fact that consecutive price changes are negatively autocorrelated when trading crosses the bid-ask spread.

For mean reversion traders, Roll's spread complements the Amihud illiquidity ratio: while Amihud measures price impact per unit volume, Roll's spread measures the cost per trade. High spread = high trading costs = fewer fades should be attempted. Low spread = tight spreads = favorable environment for frequent trading.

Unlike explicit bid-ask data (which is noisy, especially in fast market conditions), Roll's estimator is computed from clean historical price data and is more robust.

---

## Mathematical Foundation

### The Intuition

When the market maker sets a bid-ask spread:
- **Market buy:** Executed at ask (higher price)
- **Market sell:** Executed at bid (lower price)

This creates **negative autocorrelation** in price changes: a market buy (positive move) is likely followed by a market sell (negative move). Roll's spread size is inferred from how strongly this pattern appears.

### Roll's Formula

```
S = 2 * sqrt(E[ΔP[t] × ΔP[t-1]])

where:
  S = effective spread (in absolute price units)
  ΔP[t] = price change at time t
  E[] = expected value (rolling average)
  × = product/covariance operator

If E[ΔP[t] × ΔP[t-1]] > 0 (positive covariance):
  → Returns are autocorrelated (trending)
  → Formula gives negative sqrt → set S = 0
```

### Adjusted Formula (for edge cases)

```
Cov = rolling_covariance(ΔP[t], ΔP[t-1], window=N)

S = max(0, 2 * sqrt(-Cov))

The negative sign is because bid-ask bouncing creates NEGATIVE covariance.
If Cov > 0 (trending prices), set S = 0.
```

### As a Percentile

```
Roll_Spread_bps = (S / Price) × 10000  (basis points)

Example:
  S = 0.10 → Price = 10,000 → Roll_bps = 0.10 bps (extremely tight)
  S = 0.50 → Price = 10,000 → Roll_bps = 0.50 bps (very tight)
  S = 2.00 → Price = 10,000 → Roll_bps = 2.0 bps (normal)
  S = 5.00 → Price = 10,000 → Roll_bps = 5.0 bps (wide)
```

---

## Why It Matters for Mean Reversion

| Challenge | Roll's Spread Role | Solution |
|-----------|-------------------|---------  |
| **Trading costs** | Estimates the true cost per trade (bid-ask bounce) | Filter out trades when spread too wide |
| **Slippage modeling** | Expected slippage ≈ Roll_Spread × position size | Adjust entry prices and targets |
| **Mean reversion validation** | Negative autocorr validates MR (if positive → trending) | Use Cov sign as regime indicator |
| **Spread shocks** | Sudden spread widening = market stress | Skip entries when spread spikes |
| **Liquidity clustering** | Spreads widen/narrow with volatility | Adapt entry frequency to spread regime |

### Key Insight

**Roll's spread is a hidden indicator of market stress:**

```
High Roll's Spread ↔ Recent volatility spike OR order imbalance
Low Roll's Spread ↔ Calm market, tight liquidity
```

Empirically: Spreads spike 100–200% when VIX jumps, news arrives, or large order flow imbalances occur. Fade trades at wide spreads have lower win rates.

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def compute_rolls_spread(prices: np.ndarray,
                         window: int = 20) -> dict:
    """
    Estimate Roll's effective spread from price series.

    Args:
        prices: array of closing prices (e.g., from bar close)
        window: lookback window for covariance

    Returns:
        dict with spread estimates and regime indicators
    """
    n = len(prices)

    # Step 1: Compute price changes
    price_changes = np.diff(prices)

    # Step 2: Compute rolling covariance(ΔP[t], ΔP[t-1])
    roll_spread = np.zeros(n)
    roll_spread_bps = np.zeros(n)
    autocorr_lag1 = np.zeros(n)

    for i in range(window, n):
        window_deltas = price_changes[i-window:i]

        # Lag-1 autocorrelation
        delta_t = window_deltas[1:]      # ΔP[t]
        delta_t_minus_1 = window_deltas[:-1]  # ΔP[t-1]

        # Covariance
        cov = np.cov(delta_t, delta_t_minus_1)[0, 1]

        # Roll's spread formula
        spread_val = 2 * np.sqrt(max(0, -cov))  # Negative because bid-ask creates negative cov
        roll_spread[i] = spread_val

        # Basis points (relative)
        mid_price = np.mean(prices[i-window:i+1])
        if mid_price > 0:
            roll_spread_bps[i] = (spread_val / mid_price) * 10000
        else:
            roll_spread_bps[i] = np.nan

        # Lag-1 autocorrelation
        if len(delta_t) > 1:
            ac1 = np.corrcoef(delta_t, delta_t_minus_1)[0, 1]
            autocorr_lag1[i] = ac1
        else:
            autocorr_lag1[i] = np.nan

    # Step 3: Rolling percentile (rank spread vs history)
    roll_pctile = pd.Series(roll_spread).rolling(window*5).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
    ).values

    return {
        'roll_spread': roll_spread,              # Absolute spread (price units)
        'roll_spread_bps': roll_spread_bps,      # Basis points
        'roll_pctile': roll_pctile,              # Percentile rank
        'autocorr_lag1': autocorr_lag1,          # Lag-1 autocorrelation
        'is_tight_spread': roll_pctile < 0.40,   # Bottom 40% = tight spreads
    }


def spread_adjusted_slippage(roll_spread: np.ndarray,
                             entry_price: np.ndarray,
                             position_size: float) -> np.ndarray:
    """
    Estimate expected slippage on market entry based on Roll's spread.

    Args:
        roll_spread: Roll's spread in price units
        entry_price: intended entry price per bar
        position_size: position size (contracts)

    Returns:
        estimated slippage per contract (price units)
    """
    # Assume market order gets the ask for buys, bid for sells
    # Slippage ≈ Roll_Spread / 2 (half the spread on average)
    slippage = roll_spread / 2.0

    # Total slippage in dollars (scale by position size)
    slippage_total = slippage * position_size

    return slippage


def spread_regime(roll_spread_bps: np.ndarray,
                  tight_threshold: float = 1.0,
                  wide_threshold: float = 5.0) -> np.ndarray:
    """
    Classify market into spread/liquidity regimes.

    Returns:
        array: 'TIGHT', 'NORMAL', 'WIDE'
    """
    regime = np.full(len(roll_spread_bps), 'NORMAL', dtype=object)
    regime[roll_spread_bps <= tight_threshold] = 'TIGHT'
    regime[roll_spread_bps >= wide_threshold] = 'WIDE'
    return regime


def rolls_spread_shock(roll_spread: np.ndarray,
                       window: int = 20,
                       zscore_threshold: float = 2.0) -> np.ndarray:
    """
    Detect sudden spread widening (market stress indicator).

    Returns:
        boolean array; True where spread spike detected
    """
    rolling_mean = pd.Series(roll_spread).rolling(window).mean().values
    rolling_std = pd.Series(roll_spread).rolling(window).std().values

    zscore = np.where(
        rolling_std > 0,
        (roll_spread - rolling_mean) / rolling_std,
        0
    )

    shock = zscore > zscore_threshold
    return shock


def rolls_vs_amihud(roll_spread_bps: np.ndarray,
                    amihud_bps: np.ndarray) -> dict:
    """
    Compare Roll's spread with Amihud illiquidity.
    Both measure trading costs but from different angles:
    - Roll's = bid-ask spread size
    - Amihud = price impact per unit volume

    Returns:
        correlation and analysis
    """
    mask = ~(np.isnan(roll_spread_bps) | np.isnan(amihud_bps))
    rolls_clean = roll_spread_bps[mask]
    amihud_clean = amihud_bps[mask]

    corr = np.corrcoef(rolls_clean, amihud_clean)[0, 1] if len(rolls_clean) > 5 else np.nan

    return {
        'correlation': corr,
        'both_high': np.sum((roll_spread_bps > np.nanpercentile(roll_spread_bps, 75)) &
                            (amihud_bps > np.nanpercentile(amihud_bps, 75))),
        'both_low': np.sum((roll_spread_bps < np.nanpercentile(roll_spread_bps, 25)) &
                           (amihud_bps < np.nanpercentile(amihud_bps, 25))),
    }
```

---

## Interpretation & Thresholds

### Roll's Spread in Basis Points

| Roll (bps) | Regime | Action | Notes |
|-----------|--------|--------|-------|
| 0–0.5 | Extremely tight | Optimal for MR | Only occurs in deep liquidity |
| 0.5–1.5 | Very tight | Ideal | NQ, ES during regular hours |
| 1.5–3.0 | Tight | Good | Normal mid-day conditions |
| 3.0–5.0 | Moderate | Fair | Acceptable; some caution needed |
| 5.0–10.0 | Wide | Caution | Reduce entry frequency or size |
| > 10.0 | Very wide | Avoid | Pre-market, flash crash conditions |

### Percentile-Based Filter

```
If Roll_Pctile > 0.75 (top 25% widest spreads):
  → Reduce position size by 30–50%
  → Require stronger entry signal
  → Widen stops by 0.5–1 ATR

If Roll_Pctile < 0.40 (bottom 40% tightest):
  → Normal entry rules
  → Standard position sizing
```

---

## Relationship to Other Metrics

| Metric | Comparison | Joint Signal |
|--------|-----------|------------|
| **Amihud Illiquidity** | Both measure trading cost; Roll's = spread, Amihud = impact | High Roll's + High Amihud = double cost warning |
| **Price Impact (Kyle's Lambda)** | Kyle's Lambda captures full impact; Roll's captures bid-ask portion | Kyle's > Roll's because Kyle's includes temporary impact |
| **Bid-Ask Spread (direct)** | Roll's estimates it from prices; direct quote is noisy in fast markets | Roll's more reliable than tick-level quotes |
| **Volatility** | Spreads widen with vol; both correlated but causation is vol → spread | High Vol + Wide Spread = avoid |
| **Volume** | Volume drops → spreads widen; negative relationship | Low Vol + Wide Spread = illiquid |

---

## Layer Role

**Dimension 4: Volatility / Sizing Context** (primary)
- Measures trading cost component
- Used for slippage estimation and position sizing
- Indicates when the environment is too costly for frequent trading

**Secondary:**
- **Dimension 1 (Regime):** Spread width indicates market stress/regime shift
- **Dimension 3 (Order Flow):** Negative autocorrelation indicates mean reversion vs trend

---

## Column Names

When recording Roll's spread metrics at each bar / trade signal:

- `Roll_Spread` - Estimated effective spread (price units)
- `Roll_SpreadBPS` - Basis points
- `Roll_Pctile` - Percentile rank vs. recent history
- `Roll_Shock` - Boolean: spread spike detected
- `Spread_Regime` - TIGHT / NORMAL / WIDE classification
- `AutoCorr_Lag1` - Lag-1 autocorrelation of returns

---

## Practical Recommendations

### For NQ Futures (1-min to 5-min bars)

| Timeframe | Typical Roll (bps) | Action |
|-----------|------|------|
| 1-min bars | 0.3–1.0 | Use tight thresholds; enter frequently |
| 5-min bars | 0.8–2.0 | Normal entry rules |
| 15-min bars | 1.5–4.0 | May need fewer entries due to wider spreads |

### Suggested Pre-Filter Rule

```python
# In entry decision:
if roll_spread_bps[i] > 5.0:
    continue  # Skip entry; spreads too wide

# In position sizing:
base_size = 1.0 contract
size = base_size * (1.0 - roll_pctile[i] * 0.3)  # Size inversely proportional to spread

# In stop placement:
base_stop_atr = 2.0
stop_atr = base_stop_atr * (1.0 + roll_pctile[i] * 0.5)  # Widen stops when spread high
```

---

## Technical Notes

### Assumptions

Roll's estimator assumes:
1. No trends (expected return = 0) — valid for intraday fades
2. Constant spread — holds over short windows (5–20 bar windows)
3. Random walk for fundamental price — reasonable for short timeframes

**Violations:** If market is trending, autocorrelation becomes positive and formula gives S = 0 (no spread detected). This is actually **useful as a regime flag**: positive autocorr = trending = not MR-friendly.

### When Roll's Gives Nonsensical Values

If autocorrelation is positive (trending market), the formula outputs S = 0 or noise. In this case:
- Check the `autocorr_lag1` value
- If AC1 > 0 → market is trending, not mean-reverting
- Use this as a regime flag to skip entries

---

## References

- Roll, R. (1984) — "A simple implicit measure of the effective bid-ask spread in an efficient market"
- Hasbrouck, J. (2009) — "Trading Costs" — comprehensive review of spread estimators
- Huang, R. D., & Stoll, H. R. (1997) — "The components of the bid-ask spread: a general approach"
- Steidelmeyer, W. F. & Kahn, K. H. (1996) — *Market Profile: Understanding Market Microstructure*
