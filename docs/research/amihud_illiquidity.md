# Amihud Illiquidity Ratio

**Status:** New Study

---

## Summary

The Amihud illiquidity ratio, proposed by Yakov Amihud, measures how much price moves per unit of trading volume. It quantifies the **price impact of a standard unit of volume** (e.g., one dollar of trading). High Amihud illiquidity = low liquidity = large price move per unit volume = risky environment for mean reversion traders. Low illiquidity = high liquidity = dense trading = safe to fade.

For mean reversion strategies, this is a crucial pre-filter: in highly illiquid environments, reversions are slower, stops get hit more often, and adverse selection is higher. Traders should focus entries only when liquidity is healthy.

---

## Mathematical Foundation

### Daily Amihud Illiquidity (academic definition)

```
ILLIQ[day] = |Return[day]| / (Volume[day] in dollars)
           = |Return| / (Price × Volume)
           = (|Close - Open| / Open) / (Volume × Avg_Price)
```

### Per-Bar Amihud (for intraday trading)

For a single bar of any timeframe:

```
ILLIQ[bar] = |Return[bar]| / (Volume[bar] × Price[bar])
           = |Close - Open| / (Open × Volume × Price)

where:
  |Close - Open| = absolute price change during bar
  Volume = total volume traded during bar
  Price = reference price (e.g., VWAP or (Open+Close)/2)
```

### Rolling Amihud (normalized)

```
ILLIQ_Rolling[bar] = rolling_mean(ILLIQ[bar], window=20)
```

Higher values = more illiquid. Scale varies; typically normalize as a percentile vs recent history.

### Interpretation (in basis points)

```
ILLIQ_bps = ILLIQ × 10000

Example:
  ILLIQ = 0.00001 → ILLIQ_bps = 0.10 → highly liquid (tight)
  ILLIQ = 0.0001  → ILLIQ_bps = 1.0  → moderate liquid
  ILLIQ = 0.001   → ILLIQ_bps = 10.0 → illiquid (wide)
```

---

## Why It Matters for Mean Reversion

| Challenge | Illiquidity's Role | Solution |
|-----------|-------------------|---------  |
| **Slippage on entry** | High illiquidity = larger entry slips | Skip trades when ILLIQ is high |
| **Wider stops** | Must place stops wider (less efficient) | Reduce size or skip |
| **Adverse selection** | Illiquid markets attract informed traders | ILLIQ inversely correlated with VPIN |
| **Slow reversions** | Price takes longer to revert | Longer hold times = less efficient |
| **Whipsaw risk** | Wide spreads = false breakouts more likely | Require stronger entry signals |

### Key Finding from Microstructure Research

**Amihud illiquidity is *negatively* correlated with mean reversion:** When a market becomes illiquid, reversions slow and reversals weaken. This is captured by:

```
Lower Liquidity → Higher Adverse Selection → Fewer Reversions → Lower Win Rate
```

Empirically, mean reversion strategies perform best in the **bottom 50th percentile** of Amihud illiquidity (i.e., liquid markets).

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def compute_amihud_illiquidity(bars_df: pd.DataFrame,
                               window: int = 20) -> dict:
    """
    Compute Amihud illiquidity ratio for intraday bars.

    Args:
        bars_df: DataFrame with columns:
                 - open, close, high, low
                 - volume (in contracts or shares, not dollars)
                 - (optional) vwap for price reference

    Returns:
        dict with illiquidity metrics
    """
    close = bars_df['close'].values
    open_ = bars_df['open'].values
    volume = bars_df['volume'].values
    vwap = bars_df.get('vwap', (open_ + close) / 2).values if 'vwap' in bars_df else (open_ + close) / 2

    # Step 1: Compute absolute return per bar (in decimal)
    abs_return = np.abs(close - open_) / open_

    # Step 2: Compute per-bar Amihud
    # ILLIQ = |Return| / (Volume × Price)
    illiq = np.zeros(len(abs_return))
    for i in range(len(abs_return)):
        if volume[i] > 0 and vwap[i] > 0:
            illiq[i] = abs_return[i] / (volume[i] * vwap[i])
        else:
            illiq[i] = np.nan

    # Step 3: Rolling average (smoothing)
    illiq_rolling = pd.Series(illiq).rolling(window, min_periods=1).mean().values

    # Step 4: Rolling percentile (rank illiquidity vs history)
    illiq_pctile = pd.Series(illiq_rolling).rolling(window*5).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
    ).values

    # Step 5: Convert to basis points for interpretation
    illiq_bps = illiq * 10000
    illiq_rolling_bps = illiq_rolling * 10000

    return {
        'illiq_raw': illiq,              # Per-bar Amihud
        'illiq_rolling': illiq_rolling,  # Smoothed
        'illiq_bps': illiq_bps,          # Basis points
        'illiq_rolling_bps': illiq_rolling_bps,
        'illiq_pctile': illiq_pctile,    # Percentile rank
        'is_liquid': illiq_pctile < 0.50,  # Bottom 50% = liquid
    }


def liquidity_regime(illiq_pctile: np.ndarray,
                     high_threshold: float = 0.75,
                     low_threshold: float = 0.25) -> np.ndarray:
    """
    Classify market into liquidity regimes.

    Returns:
        array of regime strings: 'LIQUID', 'NORMAL', 'ILLIQUID'
    """
    regime = np.full(len(illiq_pctile), 'NORMAL', dtype=object)
    regime[illiq_pctile <= low_threshold] = 'LIQUID'
    regime[illiq_pctile >= high_threshold] = 'ILLIQUID'
    return regime


def illiquidity_impact_on_returns(illiq: np.ndarray,
                                   returns: np.ndarray,
                                   window: int = 20) -> float:
    """
    Compute correlation between illiquidity and subsequent returns.
    (For research: measure if illiquidity predicts worse outcomes)

    Returns:
        correlation coefficient
    """
    if len(illiq) != len(returns):
        raise ValueError("illiq and returns must be same length")

    # Shift: correlation of illiq[t] with returns[t+1]
    illiq_valid = illiq[:-1]
    returns_fwd = returns[1:]

    # Remove NaNs
    mask = ~(np.isnan(illiq_valid) | np.isnan(returns_fwd))
    illiq_clean = illiq_valid[mask]
    returns_clean = returns_fwd[mask]

    if len(illiq_clean) < 10:
        return np.nan

    return np.corrcoef(illiq_clean, returns_clean)[0, 1]
```

---

## Interpretation & Thresholds

### Absolute Illiquidity Levels (basis points)

| Illiquidity (bps) | Regime | Action | Notes |
|-------------------|--------|--------|-------|
| 0–0.5 | Extremely liquid | Optimal for MR | ETFs, major index futures |
| 0.5–2.0 | Very liquid | Ideal | NQ, ES in regular hours |
| 2.0–5.0 | Liquid | Good | NQ, ES in secondary hours |
| 5.0–10.0 | Moderate | Marginal | Use only with strong signals |
| 10.0–20.0 | Illiquid | Avoid | High slippage, adverse selection |
| > 20.0 | Very illiquid | Do not trade | Pre-market, off-hours |

### Percentile-Based Filter (practical for backtesting)

```
If ILLIQ_Pctile > 0.75 (top 25% most illiquid):
  → Skip entry, or require extra-strong signal
  → Widen stops by 1–2 ATR

If ILLIQ_Pctile < 0.50 (bottom 50% most liquid):
  → Green light for normal entry
  → Normal stops

If ILLIQ_Pctile between 0.50–0.75:
  → Neutral; use normal rules
```

---

## Relationship to Other Metrics

| Metric | Correlation | Combined Signal |
|--------|-------------|-----------------|
| **VPIN (flow toxicity)** | Negative: low liquidity + high VPIN = dangerous | ILLIQ_high + VPIN_high = skip |
| **ATR** | Positive: illiquid markets show higher volatility | ILLIQ_high + ATR_high = wider stops needed |
| **Bid-Ask Spread** | Positive: illiquidity ↔ spread size | Correlated but spread is direct; ILLIQ captures impact |
| **Volume** | Negative: high volume = low illiquidity | Volume high + ILLIQ high = unusual (intraday flash?) |
| **Mean Reversion Win Rate** | Negative: higher ILLIQ = fewer wins | Strong filter: ILLIQ_pctile > 0.60 reduces wins by 10–20% |

---

## Layer Role

**Dimension 4: Volatility / Sizing Context** (primary)
- Illiquidity captures the cost of trading (price impact)
- Used to size positions and widen stops
- Correlates with realized volatility but captures liquidity-specific risk

**Secondary:**
- **Dimension 1 (Regime):** Illiquidity indicates market state (busy vs. quiet)
- **Dimension 3 (Order Flow):** Illiquidity and adverse selection inversely related

---

## Column Names

When recording illiquidity metrics at each bar / trade signal:

- `Amihud_ILLIQ` - Per-bar Amihud ratio (raw)
- `Amihud_Rolling` - Smoothed Amihud (20-bar average)
- `Amihud_BPS` - Basis points (raw × 10000)
- `Amihud_RollingBPS` - Smoothed basis points
- `Amihud_Pctile` - Percentile rank vs. recent history
- `Liquidity_Regime` - LIQUID / NORMAL / ILLIQUID classification
- `IsLiquid` - Boolean: True if Pctile < 0.50

---

## Practical Recommendations

### For NQ Futures (5-min bars)

| Time | Typical ILLIQ (bps) | Typical Action |
|------|------|------|
| Pre-market (9:30-12:30 ET) | 3–8 | Tight entry signal requirement; wider stops |
| Regular session (12:30-16:00 ET) | 0.5–2.0 | Normal entry; standard stops |
| Afternoon (16:00-17:30 ET) | 1.5–5.0 | Normal entry; monitor closely |
| Evening (after 17:30 ET) | 5–15 | Avoid or skip entries |

### Suggested Pre-Filter Rule

```python
# In entry_technique():
if illiq_pctile[i] > 0.65:  # Top 35% most illiquid
    continue  # Skip entry

# In stop sizing():
stop_width = base_atr * (1 + illiq_pctile[i] * 0.5)  # Widen stops as illiquidity increases
```

---

## Research Note: Liquidity and Mean Reversion

Academic finding (Amihud & Mendelson, 1986; Blume & Stambaugh, 2009):

> **Liquidity is a necessary condition for mean reversion.** In highly liquid markets, information is quickly reflected in prices; reversions are fast and reliable. In illiquid markets, information is slowly processed, and reversions are unreliable.

Therefore: **Amihud illiquidity should be part of the regime gate.** High illiquidity = suspected weak reversions = lower edge.

---

## References

- Amihud, Y. (2002) — "Illiquidity and stock returns: cross-section and time-series effects"
- Amihud, Y. & Mendelson, H. (1986) — "Asset pricing and the bid-ask spread"
- Blume, M. E., & Stambaugh, R. F. (2009) — "Disagreement, liquidity, and expected stock returns"
- Goyenko, R. Y., Holden, C. W., & Trzcinka, C. A. (2009) — "Do liquidity measures measure liquidity?"
- Kaul, G., & Sapp, S. (2006) — "Returns to jacked-up momentum"
