# Imbalance Bars (Lopez de Prado)

**Status:** New Study

---

## Summary

Imbalance bars are an alternative bar formation method proposed by Marcos López de Prado in *Advances in Financial Machine Learning* (2018). Instead of creating bars at fixed time intervals (e.g., 5-minute bars), imbalance bars form when **cumulative order flow imbalance reaches a threshold**. This produces bars that cluster around high-activity periods and are sparse during quiet times, naturally emphasizing periods when traders are active and volatility is meaningful.

For mean reversion strategies, imbalance bars reveal **when absorption is occurring** — a bar forms only when the market has "digested" a large imbalance. High imbalance at bar boundaries suggests the next bar should revert. This is more meaningful than time-based bars for detecting fade opportunities.

---

## Mathematical Foundation

### Imbalance Definition

```
TickImbalance[t] = |buys[t] - sells[t]|
```

At each tick (trade), compute the absolute value of the difference between buy-initiated and sell-initiated orders.

### Cumulative Imbalance (rolling window)

```
CumImbalance[i] = Σ(TickImbalance[t]) for all ticks from start_of_lookback to tick i
```

### Bar Formation

A new bar forms when:
```
CumImbalance[i] >= Threshold
```

The threshold is dynamic: set to the **expected tick imbalance** for a target bar size.

```
ExpectedImbalance = E[|TickImbalance|] over lookback window (e.g., 100 ticks)
Threshold = ExpectedImbalance × N_bars

where N_bars is the target number of ticks per bar.
```

### Calculation of Metrics Within Each Imbalance Bar

Once a bar closes (imbalance threshold crossed), compute:
- **Open:** Close of previous bar (or first tick of new bar)
- **High/Low:** Extremes during the bar
- **Close:** Last trade price
- **Volume:** Sum of all ticks during bar
- **Imbalance:** Total TickImbalance accumulated (always ≥ threshold)

---

## Why It Matters for Mean Reversion

| Advantage | How It Helps |
|-----------|-------------|
| **Synchronized with flow** | Bars form when imbalance is digested → entry at local extremes |
| **Noise reduction** | Sparse during silence, dense during activity → cleaner signals |
| **Absorption signal** | High imbalance at bar close = strong directional pressure being absorbed |
| **Better mean reversion detection** | Price extremes cluster with high imbalance → MR fade opportunities are clearer |
| **Adaptive timeframe** | Market-driven, not clock-driven → captures true "decision points" |

### Practical Example (NQ)

**Time-based 5-min bar:** 1000–2000 ticks per bar (varies wildly by session).

**Imbalance bar (target 1500 imbalance units):** Forms when the market absorbs 1500 units of buy/sell mismatch. In quiet periods (early morning), might be every 10 minutes. In liquid hours (US open), might be every 30 seconds.

**Fade signal:** When a new imbalance bar closes with 1500+ units absorbed → market has "processed" this flow → fade the direction for next bar.

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def compute_imbalance_bars(trades_df: pd.DataFrame,
                           target_bars: int = 100,
                           lookback_ticks: int = 1000) -> pd.DataFrame:
    """
    Convert tick data to imbalance bars.

    Args:
        trades_df: DataFrame with columns:
                   - side: +1 for buy, -1 for sell
                   - price: trade price
                   - volume: trade volume (usually 1 or few)
                   - timestamp: trade timestamp
        target_bars: approximate number of bars to form from data
        lookback_ticks: window for computing expected imbalance

    Returns:
        DataFrame with imbalance bars (OHLCV + imbalance metrics)
    """
    n_ticks = len(trades_df)

    # Step 1: Compute tick imbalance (absolute value of buy/sell mismatch)
    tick_imbalance = np.abs(trades_df['side'].values)  # Assuming side is ±1

    # Step 2: Compute expected imbalance (rolling average)
    exp_imbalance = np.zeros(n_ticks)
    for i in range(lookback_ticks, n_ticks):
        exp_imbalance[i] = np.mean(tick_imbalance[i-lookback_ticks:i])

    # Set initial values
    exp_imbalance[:lookback_ticks] = np.mean(tick_imbalance[:lookback_ticks])

    # Step 3: Determine threshold to get approximately target_bars
    total_imbalance = np.sum(tick_imbalance)
    bar_threshold = total_imbalance / target_bars

    # Step 4: Form bars when cumulative imbalance >= threshold
    bars = []
    cum_imbalance = 0.0
    bar_start = 0

    for i in range(n_ticks):
        cum_imbalance += tick_imbalance[i]

        # Form bar when threshold crossed
        if cum_imbalance >= bar_threshold:
            bar_data = trades_df.iloc[bar_start:i+1]

            bars.append({
                'timestamp': bar_data['timestamp'].iloc[-1],
                'open': bar_data['price'].iloc[0],
                'high': bar_data['price'].max(),
                'low': bar_data['price'].min(),
                'close': bar_data['price'].iloc[-1],
                'volume': bar_data['volume'].sum(),
                'tick_count': len(bar_data),
                'cumulative_imbalance': cum_imbalance,
                'imbalance_direction': bar_data['side'].sum(),  # positive = more buys
                'avg_spread': 0,  # compute from tick data if available
            })

            bar_start = i + 1
            cum_imbalance = 0.0

    # Handle remaining ticks
    if bar_start < n_ticks:
        bar_data = trades_df.iloc[bar_start:]
        bars.append({
            'timestamp': bar_data['timestamp'].iloc[-1],
            'open': bar_data['price'].iloc[0],
            'high': bar_data['price'].max(),
            'low': bar_data['price'].min(),
            'close': bar_data['price'].iloc[-1],
            'volume': bar_data['volume'].sum(),
            'tick_count': len(bar_data),
            'cumulative_imbalance': cum_imbalance,
            'imbalance_direction': bar_data['side'].sum(),
            'avg_spread': 0,
        })

    return pd.DataFrame(bars)


def imbalance_bar_zscore(imbalance_bars: pd.DataFrame,
                         window: int = 20) -> np.ndarray:
    """
    Z-score of cumulative imbalance within each bar.
    High positive = extreme buying absorption.
    High negative = extreme selling absorption.

    Returns:
        array of Z-scores
    """
    imbal = imbalance_bars['cumulative_imbalance'].values
    imbal_mean = pd.Series(imbal).rolling(window).mean().values
    imbal_std = pd.Series(imbal).rolling(window).std().values

    zscore = np.where(imbal_std > 0, (imbal - imbal_mean) / imbal_std, 0.0)
    return zscore


def imbalance_bar_divergence(imbalance_bars: pd.DataFrame,
                              window: int = 10) -> np.ndarray:
    """
    Detect absorption divergence.
    Price extends but imbalance doesn't → reversal likely.

    Returns:
        +1 = bullish div (price low, imbalance low),
        -1 = bearish div (price high, imbalance low),
         0 = none
    """
    n = len(imbalance_bars)
    div = np.zeros(n)

    close = imbalance_bars['close'].values
    imbal = imbalance_bars['cumulative_imbalance'].values

    for i in range(window, n):
        close_window = close[i-window:i+1]
        imbal_window = imbal[i-window:i+1]

        # Bearish: price high but imbalance declining
        if close[i] == np.max(close_window) and imbal[i] < np.max(imbal_window):
            div[i] = -1

        # Bullish: price low but imbalance rising
        elif close[i] == np.min(close_window) and imbal[i] > np.min(imbal_window):
            div[i] = +1

    return div
```

---

## Interpretation

### Imbalance Z-Score

| Z-Score | Interpretation | Fade Signal |
|---------|----------------|-------------|
| > +2.5 | Extreme buying absorbed | Short fade likely (sellers step in next bar) |
| +1 to +2.5 | Strong buying absorbed | Weak short bias |
| -2.5 to -1 | Strong selling absorbed | Weak long bias |
| < -2.5 | Extreme selling absorbed | Long fade likely (buyers step in next bar) |
| ≈ 0 | Balanced imbalance | No directional edge |

### Imbalance Bar for Absorption Fade

**Setup:**
- Imbalance bar closes with imbalance Z-score > 2.0 (e.g., extreme buying)
- Price at or above resistance (e.g., VWAP +2 SD)
- Imbalance direction aligns with price extension (buying pressure while price rises)

**Fade:** SHORT the next imbalance bar open. Buyers are exhausted; sellers should take over.

---

## Layer Role

**Dimension 3: Order Flow Context** (primary)
- Imbalance bars are a flow-derived aggregation method
- Shows when absorption is occurring (high imbalance = directional pressure absorbed)
- Complements OFI and VPIN in measuring flow conditions

**Secondary uses:**
- **Dimension 1 (Regime):** Imbalance bar rate (bars/minute) indicates market activity regime
- **Dimension 2 (Entry):** Can use imbalance bar extremes as entry signal (rather than time-based bars)

---

## Column Names

When recording imbalance bar data at each imbalance bar close:

- `IB_CumulativeImbalance` - Total imbalance accumulated in bar (same as cumulative_imbalance)
- `IB_ImbalanceZScore` - Z-score of bar imbalance vs history
- `IB_ImbalanceDirection` - Net buys minus sells (raw count or volume-weighted)
- `IB_DivergenceSignal` - +1/−1/0 for bullish/bearish/none divergence
- `IB_TickCount` - Number of ticks in the imbalance bar (activity proxy)
- `IB_Threshold_Used` - The dynamic threshold that triggered bar close

---

## Practical Notes

### Implementation Challenges

1. **Tick data requirement:** Imbalance bars require trade-by-trade data (bid-ask classified deltas), not just OHLCV bars. May not be available for all markets.

2. **Trade classification:** Must classify each trade as buy or sell-initiated (standard: trade at bid/ask relative to previous price, or market data provider classification).

3. **Expected imbalance:** Dynamic threshold should be recomputed regularly (e.g., hourly) to adapt to market condition changes.

### Suggested Thresholds for NQ Futures (1-min -> imbalance bars)

| Session | Target Imbalance Units | Expected Bars/Min | Fade Window |
|---------|--------|------|------|
| Pre-market (9:30-12:30 ET) | 200–300 | 2–4 | 2–3 bars |
| US Session (12:30-16:00 ET) | 400–800 | 8–15 | 1–2 bars |
| Afternoon (16:00-17:30 ET) | 300–500 | 4–8 | 2–3 bars |

---

## Relationship to Other Studies

- **Order Flow Imbalance** (`order_flow_imbalance.md`): OFI is a normalized form of directional pressure; imbalance bars *aggregate* OFI
- **VPIN** (`vpin.md`): VPIN measures toxicity per imbalance bar
- **Kyle's Lambda** (`kyles_lambda.md`): Price impact per unit imbalance
- **Absorption Fade** (`advanced_data_points.md`): AbsRatio used in existing strategy; imbalance bars sharpen absorption signal

---

## References

- López de Prado, M. (2018) — *Advances in Financial Machine Learning*, Chapter 2: "Sampling"
- López de Prado, M. (2020) — *Machine Learning for Asset Managers*, extended treatment of bar formation
- Easley, D., López de Prado, M. & O'Hara, M. (2016) — "The Microstructure of the Flash Crash"
