# Advanced Data Points for NQ Intraday Trading

**Status:** Documented
**Scope:** 20 additional data points used by professional quant funds for NQ (Nasdaq 100 E-mini futures) 1-5 minute bar trading
**Purpose:** Preserve candidate context features for strategy-specific porting and post-trade slicing. Do not bootstrap these globally.

---

## Table of Contents

1. [Implied Volatility Filter (VIX Regime)](#1-implied-volatility-filter-vix-regime)
2. [Realized Volatility (RV)](#2-realized-volatility-rv)
3. [ATR Percentile Rank](#3-atr-percentile-rank)
4. [Order Flow Imbalance (OFI)](#4-order-flow-imbalance-ofi)
5. [Trade Pressure Index (TPI)](#5-trade-pressure-index-tpi)
6. [Distance from Prior Day High/Low/Close](#6-distance-from-prior-day-highlowclose)
7. [Opening Gap](#7-opening-gap)
8. [Value Area High/Low and POC](#8-value-area-highlowpoc)
9. [Cumulative Volume Delta Divergence](#9-cumulative-volume-delta-divergence)
10. [Relative Volume by Time Bucket (RVOL)](#10-relative-volume-by-time-bucket-rvol)
11. [Tick Count per Bar](#11-tick-count-per-bar)
12. [Market Impact / Slippage Proxy](#12-market-impact--slippage-proxy)
13. [Price Action Quality (Close Position in Bar)](#13-price-action-quality-close-position-in-bar)
14. [Momentum of Delta](#14-momentum-of-delta)
15. [Autocorrelation of Returns](#15-autocorrelation-of-returns)
16. [Beta to Market (NQ vs ES)](#16-beta-to-market-nq-vs-es)
17. [Z-Score of Volume](#17-z-score-of-volume)
18. [Session Progress](#18-session-progress)
19. [Spread Between VWAP Anchors](#19-spread-between-vwap-anchors)
20. [Overnight Gap Filled (Boolean)](#20-overnight-gap-filled-boolean)

---

## 1. Implied Volatility Filter (VIX Regime)

### What It Measures
The market's expected 30-day forward volatility (VIX) and the shape of the VIX term structure (VIX9D/VIX and VIX/VIX3M ratios), which collectively define the volatility regime that intraday mean reversion strategies operate in.

### Formula
```
VIX Term Structure Ratio:
  Front_Ratio   = VIX9D / VIX        # < 1 = normal contango (calm), > 1 = backwardation (fear)
  Back_Ratio    = VIX / VIX3M        # > 1 = front-heavy fear, < 1 = back-heavy (complacency)

VIX Percentile (rolling 252-day):
  VIX_Pct = percentile_rank(VIX, window=252)
```

### Why It Is Valuable
- **Low VIX (< 15):** Tight ranges, small bar-by-bar moves, mean reversion works but targets must shrink. Whipsaw risk high.
- **Medium VIX (15-25):** Optimal zone for intraday mean reversion on NQ. Enough volatility for 1R targets, not so chaotic that signals fail.
- **High VIX (> 30):** Wide bars, gap-and-go behavior, directional momentum dominates. Mean reversion strategies get destroyed by runaway moves. Reduce or eliminate trading.
- **VIX9D > VIX (backwardation):** Short-term fear exceeds long-term; typically event-driven. Avoid or halve size.
- **VIX Percentile > 80:** Historically, the highest-volatility deciles show the worst mean-reversion win rates on NQ intraday.

### Typical Ranges
| VIX Level | Regime | MR Strategy Action |
|-----------|--------|-------------------|
| < 12 | Ultra-low vol | Trade but compress targets |
| 12-20 | Normal | Full size, normal targets |
| 20-25 | Elevated | Normal to reduced size |
| 25-30 | High | Reduced size, wider stops |
| > 30 | Crisis | Avoid or paper-trade only |
| VIX9D/VIX > 1.05 | Backwardation | Reduce size 50% |

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_vix_regime(vix_series: pd.Series,
                       vix9d_series: pd.Series = None,
                       vix3m_series: pd.Series = None,
                       window: int = 252) -> pd.DataFrame:
    """
    Compute VIX regime filters.
    vix_series: daily VIX close aligned to trading dates.
    Returns columns: VIX_Level, VIX_Pct, FrontRatio, BackRatio, VIX_Regime
    """
    out = pd.DataFrame(index=vix_series.index)
    out['VIX_Level'] = vix_series

    # Rolling percentile rank (0-100)
    out['VIX_Pct'] = vix_series.rolling(window).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100,
        raw=False
    )

    if vix9d_series is not None:
        out['VIX_FrontRatio'] = vix9d_series / vix_series  # >1 = backwardation

    if vix3m_series is not None:
        out['VIX_BackRatio'] = vix_series / vix3m_series   # >1 = front-heavy fear

    # Regime label
    def label(v):
        if v < 15:   return 'LOW'
        if v < 25:   return 'NORMAL'
        if v < 35:   return 'HIGH'
        return 'CRISIS'
    out['VIX_Regime'] = vix_series.apply(label)

    return out
```

### Filter Application
Record `VIX_Level`, `VIX_Pct`, `VIX_FrontRatio`, `VIX_Regime` on each signal bar (join by date). Post-hoc filter: find the VIX percentile range where 1R hit rate is maximized. Typically: avoid `VIX_Pct > 85` for mean reversion; avoid `VIX_FrontRatio > 1.05`.

---

## 2. Realized Volatility (RV)

### What It Measures
Actual observed volatility of NQ price returns over a recent rolling window, expressed as annualized percentage. Unlike ATR (which uses range), RV uses log returns and has strong statistical theory behind it. Yang-Zhang estimator is the most accurate OHLC-based RV estimator.

### Formula
**Close-to-Close (simplest):**
```
r_t    = ln(Close_t / Close_{t-1})
RV_CC  = sqrt(252 * N_bars_per_day) * std(r_t, window)
```

**Yang-Zhang Estimator (best for OHLC bars, accounts for overnight gap and intraday drift):**
```
Let:
  o = ln(Open / prev_Close)   # overnight return
  u = ln(High / Open)         # intraday high
  d = ln(Low / Open)          # intraday low
  c = ln(Close / Open)        # close-to-open

  sigma_overnight^2 = var(o)
  sigma_open_close^2 = var(c) + 0.5*var(u-d) - (2*ln2-1)*var(c)
  k = 0.34 / (1.34 + (N+1)/(N-1))

  YZ = sqrt(sigma_overnight^2 + k * sigma_open_close^2 + (1-k) * Rogers_Satchell)

Rogers-Satchell component:
  RS = u*(u-c) + d*(d-c)   (per bar)
  sigma_RS^2 = mean(RS, window)
```

**Practical 5-min RV for NQ:**
```
RV_5min_ann = sqrt(sum(r_t^2, last N bars) * bars_per_year)
bars_per_year = 252 * 390  # for 1-min bars
```

**RV Percentile Rank:**
```
RV_Pct = rolling_percentile_rank(RV, window=1000)  # 0-100
```

### Why It Is Valuable
- **RV < 20th percentile:** Compressed volatility — mean reversion targets must shrink; breakout risk low.
- **RV 20th-70th percentile:** Normal operating zone for NQ mean reversion. Signals tend to work with standard parameters.
- **RV > 80th percentile:** Volatile regime. Wide bars mean either large profits or large failures. Filter to only high-conviction setups.
- **RV rising sharply (acceleration):** Regime transition signal — strategies calibrated for normal RV become unreliable.
- Yang-Zhang is preferred over CC because NQ futures have significant overnight sessions; CC understates true vol by ignoring the open gap.

### Typical Ranges (NQ 1-min bars, annualized)
| RV Range | Regime |
|----------|--------|
| < 10% | Ultra-low |
| 10-20% | Low-normal |
| 20-30% | Normal |
| 30-50% | Elevated |
| > 50% | High / crisis |

### Python Implementation
```python
import numpy as np
import pandas as pd

def yang_zhang_rv(open_, high, low, close, window=20):
    """
    Yang-Zhang realized volatility estimator.
    Returns annualized RV as a decimal (0.20 = 20%).
    window: number of bars
    Assumes 1-min bars; adjust ann_factor for other timeframes.
    """
    ann_factor = np.sqrt(252 * 390)  # 1-min bars

    o = np.log(open_ / close.shift(1))   # overnight
    u = np.log(high / open_)              # intraday high
    d = np.log(low / open_)               # intraday low
    c = np.log(close / open_)             # close-to-open

    # Rogers-Satchell
    rs = u * (u - c) + d * (d - c)

    # Overnight variance
    sigma_o2 = o.rolling(window).var(ddof=1)

    # Open-to-close variance (Garman-Klass adjusted)
    sigma_c2 = c.rolling(window).var(ddof=1)

    k = 0.34 / (1.34 + (window + 1) / (window - 1))

    sigma_rs2 = rs.rolling(window).mean()

    yz_var = sigma_o2 + k * sigma_c2 + (1 - k) * sigma_rs2
    yz_vol = np.sqrt(yz_var) * ann_factor

    return yz_vol

def rv_percentile_rank(rv_series, window=1000):
    """Rolling percentile rank of RV (0-100)."""
    return rv_series.rolling(window).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100,
        raw=False
    )

# Usage in compute_indicators:
# rv_5  = yang_zhang_rv(o, h, l, c, window=5)
# rv_20 = yang_zhang_rv(o, h, l, c, window=20)
# rv_60 = yang_zhang_rv(o, h, l, c, window=60)
# rv_pct = rv_percentile_rank(rv_20, window=1000)
```

### Filter Application
Record `RV_5`, `RV_20`, `RV_60`, `RV_Pct`. Post-hoc: bin trades by `RV_Pct` decile and compute win rate / avg R. Find the RV percentile range that maximizes expectancy. Typical finding: mean reversion best when `RV_Pct` is 20th-65th.

---

## 3. ATR Percentile Rank

### What It Measures
Where the current ATR(14) sits relative to its own N-day history, expressed as a percentile (0-100). Tells you whether volatility is historically compressed or expanded at the time of the signal.

### Formula
```
ATR_14     = average_true_range(high, low, close, length=14)
ATR_Pct_N  = rolling_percentile_rank(ATR_14, window=N)

rolling_percentile_rank(x, N) = rank of x[-1] within x[-N:] * 100
```

### Why It Is Valuable
- **Low ATR percentile (< 20):** Tight range relative to history. Price is coiling. Two interpretations: (a) mean reversion works well because bars are contained, or (b) breakout risk is elevated. Use with Hurst and ER to disambiguate.
- **High ATR percentile (> 80):** Wide bars, larger-than-normal range. Mean reversion stops get hit more frequently. Widen stops or skip trades. However, high ATR + oversold RSI can be a strong capitulation signal.
- **ATR percentile rising sharply:** Expanding volatility — regime change in progress. Caution.
- Unlike raw ATR, percentile rank normalizes across all market conditions, making filters time-stable.

### Typical Ranges
| ATR Pct | Interpretation |
|---------|---------------|
| 0-20 | Historically compressed |
| 20-40 | Below average |
| 40-60 | Average |
| 60-80 | Above average |
| 80-100 | Historically expanded |

### Python Implementation
```python
import pandas_ta as ta
import pandas as pd

def atr_percentile_rank(high, low, close, atr_length=14, window=252):
    """
    ATR(14) percentile rank over rolling window.
    Returns 0-100 where 100 = highest ATR in window.
    """
    atr = ta.atr(high, low, close, length=atr_length)

    atr_pct = atr.rolling(window).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100,
        raw=False
    )
    return atr, atr_pct

# Columns to record:
# ATR14: raw ATR value
# ATR_Pct252: percentile rank over 252 bars (~1 trading day of 1-min bars... adjust window)
# For daily ATR use window=252 daily bars; for intraday 1-min use window=5000+ bars
```

### Filter Application
Record `ATR14`, `ATR_Pct_500` (500-bar window for intraday). Post-hoc: stratify win rate by ATR percentile bucket (0-20, 20-40, 40-60, 60-80, 80-100). For mean reversion, typically filter to `ATR_Pct < 70` to avoid runaway bars.

---

## 4. Order Flow Imbalance (OFI)

### What It Measures
The net directional pressure of executed trades within a bar, normalized to total volume. Positive OFI = more buying than selling; negative = more selling. A sustained imbalance reveals genuine directional intent vs. noise.

### Formula
```
Per bar:
  OFI = (BuyVol - SellVol) / TotalVol
      = Delta / Volume                    # same as normalized delta

  where: BuyVol = volume on ask (uptick/ask fills)
         SellVol = volume on bid (downtick/bid fills)
         Delta = BuyVol - SellVol         # already in your data

Cumulative OFI (window):
  CumOFI_N = sum(OFI, last N bars)       # rolling cumulative imbalance

OFI Z-Score:
  OFI_Z = (OFI - mean(OFI, window)) / std(OFI, window)
```

### Why It Is Valuable
- **OFI and price divergence:** Price rises but OFI is negative or declining = bearish divergence, mean reversion SHORT signal. Price falls but OFI is positive = bullish divergence, mean reversion LONG signal.
- **Extreme OFI (|OFI_Z| > 2):** Indicates potential capitulation or absorption. Very high sell OFI near support = buyers absorbing sellers = mean reversion LONG.
- **OFI confirming entry:** If your signal is LONG and OFI is also positive (buyers in control), higher-confidence trade.
- **Cumulative OFI trend:** 20-bar cumulative OFI trending down while price flat = distribution. Fade the distribution when price tests resistance.
- Widely used in HFT, market microstructure research (Cont, Kukanov & Stoikov 2014 paper on OFI and price impact).

### Typical Ranges
| OFI | Interpretation |
|-----|---------------|
| +0.6 to +1.0 | Heavy buying pressure |
| +0.2 to +0.6 | Moderate buying |
| -0.2 to +0.2 | Balanced / neutral |
| -0.6 to -0.2 | Moderate selling |
| -1.0 to -0.6 | Heavy selling pressure |
| OFI_Z > +2.5 | Extreme buying (capitulation or absorption) |
| OFI_Z < -2.5 | Extreme selling (capitulation or absorption) |

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_ofi(delta: pd.Series, volume: pd.Series,
                window_z: int = 20, window_cum: int = 20) -> pd.DataFrame:
    """
    Order Flow Imbalance from delta data.
    delta: BuyVol - SellVol per bar (already in your data as 'Delta')
    volume: total volume per bar
    """
    out = pd.DataFrame()

    # Normalized OFI: -1 to +1
    out['OFI'] = delta / volume.replace(0, np.nan)

    # Cumulative OFI over rolling window
    out['OFI_Cum20'] = out['OFI'].rolling(window_cum).sum()

    # OFI Z-score
    mu = out['OFI'].rolling(window_z).mean()
    sigma = out['OFI'].rolling(window_z).std()
    out['OFI_Z'] = (out['OFI'] - mu) / sigma.replace(0, np.nan)

    # Divergence: price direction vs OFI direction (last N bars)
    # Computed in strategy layer after merging with price data

    return out

# Columns to record: OFI, OFI_Cum20, OFI_Z
```

### Filter Application
Record `OFI`, `OFI_Cum20`, `OFI_Z`. Post-hoc:
- For LONG signals: does `OFI_Z > -1.0` (not extreme selling) improve win rate?
- Does `OFI_Cum20 < -0.5` (sustained selling before LONG entry) = capitulation setup improve outcome?
- Does confirming OFI (OFI directional match with trade direction) add edge?

---

## 5. Trade Pressure Index (TPI)

### What It Measures
A smoothed, normalized measure of sustained directional delta pressure, similar to RSI but applied to delta rather than price. It distinguishes persistent order flow pressure (likely informed) from random noise.

### Formula
```
Positive Delta per bar: PosDelta_t = max(Delta_t, 0)
Negative Delta per bar: NegDelta_t = abs(min(Delta_t, 0))

Smoothed over N bars:
  AvgPosDelta = EMA(PosDelta, N)
  AvgNegDelta = EMA(NegDelta, N)

TPI = 100 * AvgPosDelta / (AvgPosDelta + AvgNegDelta)

Interpretation (identical scale to RSI):
  TPI > 70: Sustained buying pressure (overbought flow)
  TPI < 30: Sustained selling pressure (oversold flow)
  TPI = 50: Balanced flow
```

**Alternative: Normalized Delta Momentum**
```
DeltaMomentum_N = Delta.rolling(N).sum() / Volume.rolling(N).sum()
# -1 to +1, positive = net buying over window
```

### Why It Is Valuable
- **TPI divergence from price:** Price makes new low but TPI rising (buying pressure increasing) = mean reversion LONG signal with order flow confirmation.
- **TPI extreme + price extreme:** TPI < 20 + price at -2SD VWAP = both price and flow oversold = high-conviction mean reversion LONG.
- **Sustained TPI > 70:** Buying pressure is persistent — likely informed. Do NOT fade this with mean reversion SHORT.
- **TPI crossing 50:** Shift in dominant order flow; transition signals.
- Captures information that raw delta misses because it smooths out per-bar noise.

### Typical Ranges
| TPI | Interpretation |
|-----|---------------|
| 80-100 | Extreme sustained buying |
| 60-80 | Buying dominant |
| 40-60 | Balanced, neutral |
| 20-40 | Selling dominant |
| 0-20 | Extreme sustained selling |

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_tpi(delta: pd.Series, volume: pd.Series,
                length: int = 14) -> pd.Series:
    """
    Trade Pressure Index: RSI-like measure of cumulative delta.
    Returns 0-100 where >70 = sustained buying, <30 = sustained selling.
    """
    pos_delta = delta.clip(lower=0)
    neg_delta = delta.clip(upper=0).abs()

    # EMA smoothing (same as RSI uses RMA/Wilder smoothing)
    alpha = 1.0 / length
    avg_pos = pos_delta.ewm(alpha=alpha, adjust=False).mean()
    avg_neg = neg_delta.ewm(alpha=alpha, adjust=False).mean()

    denom = avg_pos + avg_neg
    tpi = 100 * avg_pos / denom.replace(0, np.nan)
    return tpi

def delta_momentum(delta: pd.Series, volume: pd.Series,
                   window: int = 10) -> pd.Series:
    """
    Normalized cumulative delta over rolling window. -1 to +1.
    """
    return delta.rolling(window).sum() / volume.rolling(window).sum().replace(0, np.nan)

# Columns to record: TPI_14, DeltaMom_10
```

### Filter Application
Record `TPI_14`. Post-hoc: for mean reversion LONGs, does `TPI_14 < 35` (oversold flow) improve outcome? Does `TPI_14 < 25` (extreme oversold flow) give best results? For SHORTs, mirror analysis.

---

## 6. Distance from Prior Day High/Low/Close

### What It Measures
Price location relative to the previous calendar day's key reference levels: prior day high (PDH), prior day low (PDL), and prior day close (PDC). These are universal reference levels used by virtually all professional futures traders.

### Formula
```
# Calculated once at start of each session:
PDH  = previous_day_high
PDL  = previous_day_low
PDC  = previous_day_close
PDMid = (PDH + PDL) / 2

# At signal time (price = P):
Dist_PDH = P - PDH           # negative = below PDH
Dist_PDL = P - PDL           # positive = above PDL
Dist_PDC = P - PDC           # positive = above PDC
Dist_PDMid = P - PDMid

# Normalized by ATR (makes it regime-stable):
Dist_PDH_ATR = Dist_PDH / ATR14
Dist_PDL_ATR = Dist_PDL / ATR14
Dist_PDC_ATR = Dist_PDC / ATR14

# Location within prior day range:
PD_Range = PDH - PDL
PD_Location = (P - PDL) / PD_Range   # 0=at PDL, 1=at PDH
```

### Why It Is Valuable
- **Price near PDH or PDL:** Strong institutional reference levels. Mean reversion fades of tests of these levels are among the highest-probability setups in futures trading. The first 1-3 touches of PDH/PDL have the highest rejection probability.
- **Price inside PDR (between PDL and PDH):** Known as "inside day" setup territory. Price tends to oscillate within the prior range.
- **Price outside PDR:** Potential range expansion or breakout. Mean reversion risk is higher; momentum setups favored.
- **Dist_PDC_ATR:** Gap magnitude in ATR terms. Large positive gaps tend to fill (see #7). Useful filter.
- These levels are hardcoded into every professional trading platform (NinjaTrader, Sierra Chart, TradingView) — so they function as self-fulfilling prophecies due to mass attention.

### Typical Ranges
| Dist_PDH_ATR | Interpretation |
|--------------|---------------|
| -0.25 to 0 | Testing PDH from below |
| 0 to +0.5 | Just broken above PDH |
| < -2.0 | Far below PDH (mid-range) |

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_prior_day_levels(bars: pd.DataFrame) -> pd.DataFrame:
    """
    bars: DataFrame with DateTime, Open, High, Low, Close columns.
    Returns same DataFrame with PDH, PDL, PDC, PDMid, and distance columns added.
    Assumes bars are sorted ascending by DateTime.
    """
    bars = bars.copy()
    bars['Date'] = pd.to_datetime(bars['DateTime']).dt.date

    # Daily OHLC
    daily = bars.groupby('Date').agg(
        DayHigh=('High', 'max'),
        DayLow=('Low', 'min'),
        DayClose=('Close', 'last')
    ).reset_index()

    daily['PDH'] = daily['DayHigh'].shift(1)
    daily['PDL'] = daily['DayLow'].shift(1)
    daily['PDC'] = daily['DayClose'].shift(1)
    daily['PDMid'] = (daily['PDH'] + daily['PDL']) / 2

    bars = bars.merge(daily[['Date', 'PDH', 'PDL', 'PDC', 'PDMid']], on='Date', how='left')

    # Distances
    bars['Dist_PDH'] = bars['Close'] - bars['PDH']
    bars['Dist_PDL'] = bars['Close'] - bars['PDL']
    bars['Dist_PDC'] = bars['Close'] - bars['PDC']
    bars['Dist_PDMid'] = bars['Close'] - bars['PDMid']
    bars['PD_Location'] = (bars['Close'] - bars['PDL']) / (bars['PDH'] - bars['PDL']).replace(0, np.nan)

    # Normalize by ATR (assumes ATR14 already computed)
    if 'ATR14' in bars.columns:
        bars['Dist_PDH_ATR'] = bars['Dist_PDH'] / bars['ATR14']
        bars['Dist_PDL_ATR'] = bars['Dist_PDL'] / bars['ATR14']
        bars['Dist_PDC_ATR'] = bars['Dist_PDC'] / bars['ATR14']

    return bars

# Columns to record:
# PDH, PDL, PDC, PDMid, Dist_PDH, Dist_PDL, Dist_PDC, Dist_PDMid, PD_Location
# Dist_PDH_ATR, Dist_PDL_ATR, Dist_PDC_ATR
```

### Filter Application
Record `PD_Location`, `Dist_PDH_ATR`, `Dist_PDL_ATR`. Post-hoc: does a SHORT signal near `PD_Location > 0.85` (near PDH) have higher win rate? Does a LONG signal near `PD_Location < 0.15` (near PDL) outperform?

---

## 7. Opening Gap

### What It Measures
The price difference between the current session's opening price and the previous session's closing price, normalized by ATR. Also tracks gap direction, gap magnitude, and whether it is a "large" gap (statistically likely to fill vs. extend).

### Formula
```
GapPoints = TodayOpen - PrevClose
GapPct    = GapPoints / PrevClose * 100
GapATR    = GapPoints / ATR14                  # normalized; > 1.5 = large gap

GapDirection:
  +1 = gap up (opened above prev close)
  -1 = gap down (opened below prev close)
   0 = flat open (|GapATR| < 0.1)

GapCategory:
  FLAT:    |GapATR| < 0.25
  SMALL:   0.25 <= |GapATR| < 0.75
  MEDIUM:  0.75 <= |GapATR| < 1.5
  LARGE:   |GapATR| >= 1.5
```

**Gap Fill Probability (research-based):**
- Gaps < 0.5 ATR: ~75-80% fill same session (NQ historical)
- Gaps 0.5-1.5 ATR: ~55-65% fill same session
- Gaps > 1.5 ATR: ~35-45% fill same session; more likely continuation
- Large gap-ups on earnings/macro events: continuation > fill
- Gap fill definition: price trades back to within 1 tick of PrevClose

### Why It Is Valuable
- **Gap fill bias:** Most gaps below 1 ATR tend to fill. This creates a structural mean-reversion edge: trade in the direction of gap fill until fill occurs, then reassess.
- **Gap direction filter:** After a gap-up open, mean-reversion SHORTs that target gap fill have better stats than random SHORTs. The reverse for gap-down opens.
- **Large gap = momentum, not mean reversion:** Gaps > 1.5 ATR on significant news are continuation trades. Avoid mean reversion against large gaps.
- **Combine with VIX:** Low-VIX large gaps more likely to fill; high-VIX large gaps more likely to extend.
- Extensively researched in academic literature (Bhargava & Malhotra 2011; Andy Clenow's "Stocks on the Move").

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_gap(bars: pd.DataFrame, atr_col: str = 'ATR14') -> pd.DataFrame:
    """
    Compute opening gap metrics.
    bars: must have DateTime, Open, Close, ATR14 columns.
    """
    bars = bars.copy()
    bars['Date'] = pd.to_datetime(bars['DateTime']).dt.date

    # First bar of each session = open
    first_bars = bars.groupby('Date').first().reset_index()[['Date', 'Open']]
    first_bars.columns = ['Date', 'SessionOpen']

    # Previous day close
    daily_close = bars.groupby('Date')['Close'].last().reset_index()
    daily_close.columns = ['Date', 'DayClose']
    daily_close['PrevClose'] = daily_close['DayClose'].shift(1)

    session_info = first_bars.merge(daily_close[['Date', 'PrevClose']], on='Date', how='left')

    bars = bars.merge(session_info[['Date', 'SessionOpen', 'PrevClose']], on='Date', how='left')

    bars['GapPoints'] = bars['SessionOpen'] - bars['PrevClose']
    bars['GapPct'] = bars['GapPoints'] / bars['PrevClose'] * 100

    if atr_col in bars.columns:
        bars['GapATR'] = bars['GapPoints'] / bars[atr_col]
    else:
        bars['GapATR'] = np.nan

    bars['GapDirection'] = np.sign(bars['GapPoints']).astype(int)

    def gap_cat(g):
        ag = abs(g)
        if ag < 0.25:  return 'FLAT'
        if ag < 0.75:  return 'SMALL'
        if ag < 1.5:   return 'MEDIUM'
        return 'LARGE'
    bars['GapCategory'] = bars['GapATR'].apply(gap_cat)

    return bars

# Columns to record:
# GapPoints, GapPct, GapATR, GapDirection, GapCategory
```

### Filter Application
Record `GapATR`, `GapDirection`, `GapCategory`. Post-hoc: does `GapCategory == LARGE` AND signal direction opposing gap = poor outcome? Does `GapCategory == SMALL AND GapDirection == -1 AND signal == LONG` show high fill-rate edge?

---

## 8. Value Area High/Low and POC

### What It Measures
Volume Profile is the distribution of traded volume at each price level over a defined session or lookback. The Point of Control (POC) is the price with the highest traded volume (fairest value). Value Area (VA) contains 70% of total volume (by convention). VAH = upper bound of value area; VAL = lower bound.

### Formula
```
1. Bin all traded volume into price buckets (bucket size = 1 tick = 0.25 NQ points or larger)
2. POC = price bucket with max volume
3. Sort remaining buckets by volume (descending)
4. Expand from POC outward (alternating above/below) until 70% of session volume is enclosed
5. VAH = highest price bucket in the 70% zone
6. VAL = lowest price bucket in the 70% zone

Distance from POC:
  DistPOC      = Close - POC
  DistPOC_ATR  = DistPOC / ATR14
  DistVAH      = Close - VAH
  DistVAL      = Close - VAL
  VA_Location  = (Close - VAL) / (VAH - VAL)  # 0=at VAL, 1=at VAH
```

**Session types:**
- **Session POC:** From 22:00 UTC open to current bar (rolling intraday)
- **Previous Session POC:** Fixed from prior session — strongest reference level
- **Rolling N-bar POC:** Last N bars regardless of session boundary

### Why It Is Valuable
- **POC = mean reversion anchor:** Price gravitates toward POC (maximum volume node = accepted fair value). Trades that fade price away from POC back toward POC have structural edge.
- **VAH/VAL as mean reversion triggers:** Price above VAH or below VAL is in "unfair" territory. High-probability return to value area. Used by every prop trading firm as a primary mean-reversion setup.
- **Price inside value area:** Mean reversion between VAH and VAL is the core Market Profile trading approach (Steidlmayer, CBOT 1985).
- **POC migration:** If POC shifts toward price, the "value" has moved — reduces fade opportunity.
- **Previous session POC:** Most powerful overnight reference; price returning to prior POC is one of the cleanest setups.

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_volume_profile(bars: pd.DataFrame,
                           tick_size: float = 0.25,
                           bucket_size: float = 1.0,
                           va_pct: float = 0.70) -> pd.DataFrame:
    """
    Compute rolling intraday volume profile (POC, VAH, VAL).

    bars: DataFrame with DateTime, Close, Volume, Date columns
    tick_size: NQ = 0.25
    bucket_size: price bucket width (1.0 point = 4 ticks)
    va_pct: value area percentage (0.70 = 70%)

    Returns DataFrame with POC, VAH, VAL, DistPOC, DistVAH, DistVAL, VA_Location columns.
    """
    results = []

    for date, session in bars.groupby('Date'):
        session = session.copy().reset_index(drop=True)

        # Price buckets
        prices = session['Close'].values
        volumes = session['Volume'].values

        min_p = np.floor(prices.min() / bucket_size) * bucket_size
        max_p = np.ceil(prices.max() / bucket_size) * bucket_size
        buckets = np.arange(min_p, max_p + bucket_size, bucket_size)

        # Cumulative profile at each bar (rolling)
        poc_list, vah_list, val_list = [], [], []

        cum_profile = {}

        for i in range(len(session)):
            p = round(prices[i] / bucket_size) * bucket_size
            v = volumes[i]
            cum_profile[p] = cum_profile.get(p, 0) + v

            if len(cum_profile) < 3:
                poc_list.append(np.nan)
                vah_list.append(np.nan)
                val_list.append(np.nan)
                continue

            total_vol = sum(cum_profile.values())
            target_vol = total_vol * va_pct

            # POC
            poc = max(cum_profile, key=cum_profile.get)

            # Expand from POC to cover 70%
            sorted_prices = sorted(cum_profile.keys())
            poc_idx = sorted_prices.index(poc)

            included_vol = cum_profile[poc]
            lo_idx = poc_idx
            hi_idx = poc_idx

            while included_vol < target_vol:
                expand_up = (hi_idx + 1) < len(sorted_prices)
                expand_dn = (lo_idx - 1) >= 0
                if not expand_up and not expand_dn:
                    break
                vol_up = cum_profile[sorted_prices[hi_idx + 1]] if expand_up else 0
                vol_dn = cum_profile[sorted_prices[lo_idx - 1]] if expand_dn else 0
                if vol_up >= vol_dn and expand_up:
                    hi_idx += 1
                    included_vol += vol_up
                elif expand_dn:
                    lo_idx -= 1
                    included_vol += vol_dn
                else:
                    hi_idx += 1
                    included_vol += vol_up

            poc_list.append(poc)
            vah_list.append(sorted_prices[hi_idx])
            val_list.append(sorted_prices[lo_idx])

        session['POC'] = poc_list
        session['VAH'] = vah_list
        session['VAL'] = val_list
        results.append(session)

    out = pd.concat(results).sort_values('DateTime').reset_index(drop=True)

    out['DistPOC'] = out['Close'] - out['POC']
    out['DistPOC_ATR'] = out['DistPOC'] / out['ATR14'] if 'ATR14' in out.columns else np.nan
    out['DistVAH'] = out['Close'] - out['VAH']
    out['DistVAL'] = out['Close'] - out['VAL']
    va_range = (out['VAH'] - out['VAL']).replace(0, np.nan)
    out['VA_Location'] = (out['Close'] - out['VAL']) / va_range

    return out

# Columns to record:
# POC, VAH, VAL, DistPOC, DistPOC_ATR, DistVAH, DistVAL, VA_Location
```

### Filter Application
Record `DistPOC_ATR`, `VA_Location`. Post-hoc: trades with `|DistPOC_ATR| > 1.5` (far from POC) in the direction of POC = highest win rate for mean reversion? Trades with `VA_Location > 1.0` (above VAH) = SHORT fade setup. `VA_Location < 0.0` (below VAL) = LONG fade setup.

---

## 9. Cumulative Volume Delta Divergence

### What It Measures
A comparison between the direction of price movement and the direction of cumulative delta over the same lookback. When price makes a new extreme (high or low) but cumulative delta does not confirm, it signals that the move lacks genuine order flow support — a leading indicator of reversal.

### Formula
```
# Over a rolling window W (e.g., 10 or 20 bars):
Price_Change  = Close[-1] - Close[-W]
Delta_Change  = CumDelta[-1] - CumDelta[-W]

# Normalized divergence (sign comparison):
DeltaDiv_Sign  = sign(Price_Change) != sign(Delta_Change)  # Boolean: True = divergence

# Magnitude of divergence:
# Normalize both to 0-1 scale over rolling N bars:
Price_Rank  = rolling_percentile_rank(Price_Change, N)     # 0-100
Delta_Rank  = rolling_percentile_rank(Delta_Change, N)     # 0-100

DeltaDiv_Score = Price_Rank - Delta_Rank
# Positive = price stronger than delta (bearish divergence for longs)
# Negative = delta stronger than price (bullish divergence for shorts, i.e., buyers absorbing)

# New high/low test:
NBarHigh = Close == Close.rolling(W).max()  # price at N-bar high
DeltaAtHigh = CumDelta.rolling(W).max()
BearishDiv = NBarHigh AND (CumDelta < DeltaAtHigh)  # price high, delta not at high
```

### Why It Is Valuable
- **Classic order flow divergence:** One of the most-used concepts by professional futures traders (Footprint chart analysis). If price grinds higher on declining buy delta, sellers are quietly distributing. Fade the high.
- **Capitulation confirmation:** Price makes new session low on extreme negative delta = capitulation. Then delta starts recovering while price stays flat = absorption. LONG setup.
- **Quantifies what discretionary traders see on Footprint charts** — allows systematic testing of what was previously a judgment call.
- **Divergence persistence:** Divergence that persists over 5+ bars is more significant than 1-2 bar divergence.

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_delta_divergence(close: pd.Series,
                              cum_delta: pd.Series,
                              window: int = 10,
                              rank_window: int = 100) -> pd.DataFrame:
    """
    Compute price vs cumulative delta divergence.
    close: bar close prices
    cum_delta: cumulative delta (rolling window sum already in your data)
    window: bars to measure change over
    rank_window: bars for percentile ranking
    """
    out = pd.DataFrame()

    out['PriceChange_W'] = close.diff(window)
    out['DeltaChange_W'] = cum_delta.diff(window)

    # Sign divergence: True = divergence exists
    out['DeltaDiv_Bool'] = (
        np.sign(out['PriceChange_W']) != np.sign(out['DeltaChange_W'])
    ).astype(int)

    # Ranked divergence score (-100 to +100)
    def pct_rank(s, w):
        return s.rolling(w).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100,
            raw=False
        )

    price_rank  = pct_rank(out['PriceChange_W'], rank_window)
    delta_rank  = pct_rank(out['DeltaChange_W'], rank_window)
    out['DeltaDiv_Score'] = price_rank - delta_rank

    # New N-bar high/low flags with delta confirmation
    out['NBHighWithDiv'] = (
        (close == close.rolling(window).max()) &
        (cum_delta < cum_delta.rolling(window).max())
    ).astype(int)

    out['NBLowWithDiv'] = (
        (close == close.rolling(window).min()) &
        (cum_delta > cum_delta.rolling(window).min())
    ).astype(int)

    return out

# Columns to record:
# DeltaDiv_Bool, DeltaDiv_Score, NBHighWithDiv, NBLowWithDiv
```

### Filter Application
Record `DeltaDiv_Bool`, `DeltaDiv_Score`. Post-hoc: for LONG signals, does `DeltaDiv_Bool == 1` AND signal direction == LONG (price weak, delta strong) improve win rate? `NBLowWithDiv == 1` = bullish divergence at new low — expected to be a strong MR filter.

---

## 10. Relative Volume by Time Bucket (RVOL)

### What It Measures
How the current bar's volume compares to the average volume at the same time-of-day across recent sessions. This eliminates the well-known intraday volume pattern (U-shape: high at open, low midday, high at close) by normalizing against same-time-of-day baseline.

### Formula
```
# Build a historical average volume map:
# For each minute M of the day, compute mean volume across last N sessions:
AvgVolByMinute[M] = mean(Volume[all bars at minute M in last N sessions])

# At bar time T:
RVOL = Volume[T] / AvgVolByMinute[T]

# RVOL > 1.0: more volume than typical for this time
# RVOL < 1.0: less volume than typical for this time
# RVOL > 2.0: significantly elevated (news, catalysts, large orders)
# RVOL > 3.0: extreme (potential institutional activity)
```

### Why It Is Valuable
- **Standard VolRatio uses 20-bar lookback** which mixes different times of day (11am bars vs. 9:30am bars). This is statistically invalid for intraday volume analysis.
- **RVOL is the correct normalization:** Used by every professional equities desk and increasingly in futures. Gives true signal of "is this bar unusual for right now."
- **High RVOL at signal time:** Large volume at the exact moment of entry signal = institutional confirmation. Low RVOL = retail noise, lower-confidence signal.
- **RVOL > 2.5 at key level:** Classic footprint of institutional orders absorbing supply or demand. Strong confirmation for mean reversion entries.
- **Low RVOL at session open:** Below-average volume opening = lower liquidity, wider effective spreads, more volatile price action per unit of volume — reduce size.

### Typical Ranges
| RVOL | Interpretation |
|------|---------------|
| < 0.5 | Unusually quiet |
| 0.5-0.8 | Below average |
| 0.8-1.2 | Normal for this time |
| 1.2-2.0 | Above average |
| 2.0-3.5 | High (potential institutional) |
| > 3.5 | Extreme (news/event driven) |

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_rvol(bars: pd.DataFrame, lookback_sessions: int = 20) -> pd.Series:
    """
    Relative Volume vs. same time-of-day average.
    bars: DataFrame with DateTime (timezone-aware), Volume, Date columns.
    Returns RVOL series.
    """
    bars = bars.copy()
    bars['DateTime'] = pd.to_datetime(bars['DateTime'])
    bars['TimeOfDay'] = bars['DateTime'].dt.time
    bars['Date'] = bars['DateTime'].dt.date

    # Get unique dates in order
    dates = sorted(bars['Date'].unique())

    rvol_list = []

    for i, date in enumerate(dates):
        session_bars = bars[bars['Date'] == date].copy()

        # Use last N sessions (excluding current) for baseline
        past_dates = dates[max(0, i - lookback_sessions):i]

        if len(past_dates) == 0:
            # No history: set RVOL to 1.0
            rvol_list.append(pd.Series(1.0, index=session_bars.index))
            continue

        past_bars = bars[bars['Date'].isin(past_dates)]

        # Average volume by time-of-day
        avg_vol_by_time = past_bars.groupby('TimeOfDay')['Volume'].mean()

        # Map to current session
        session_bars['AvgVolAtTime'] = session_bars['TimeOfDay'].map(avg_vol_by_time)
        session_bars['RVOL'] = session_bars['Volume'] / session_bars['AvgVolAtTime'].replace(0, np.nan)

        rvol_list.append(session_bars['RVOL'])

    return pd.concat(rvol_list).sort_index()

# Column to record: RVOL
```

### Filter Application
Record `RVOL`. Post-hoc: does `RVOL > 1.5` at signal time improve win rate (institutional confirmation)? Does `RVOL < 0.6` hurt win rate (thin market noise)? Time of day filter: is `RVOL` more predictive during certain hours?

---

## 11. Tick Count per Bar

### What It Measures
The number of individual trades (transactions) executed within a bar's time period, regardless of their size. High tick count = many small trades (retail activity or HFT). Low tick count = few large trades (institutional block activity).

### Formula
```
TickCount = number of individual trades in bar period

# Ratios:
AvgTradeSize = Volume / TickCount          # average shares/contracts per trade
TickCountRatio = TickCount / TickCount.rolling(20).mean()  # vs recent average
TickCountZ = (TickCount - TickCount.rolling(20).mean()) / TickCount.rolling(20).std()

# For NQ futures: typical 1-min tick count = 200-800 in normal session
# During open/close: 1000-3000+
# Overnight: 50-200
```

### Why It Is Valuable
- **High tick count + high volume:** Many large trades = institutional block activity. High conviction signal if at a key level.
- **High tick count + normal volume:** Many small retail trades. Less meaningful for directional inference.
- **Low tick count + high volume:** Few very large trades. Iceberg orders or block crossing. Potential absorption.
- **AvgTradeSize:** When average trade size spikes, large players are acting. Especially significant if volume and tick count diverge.
- **Tick count divergence from volume:** Volume surges but tick count doesn't = large orders. Volume normal but tick count spikes = HFT churning.
- Used heavily in order flow analysis by CME professional data users.

### Typical Ranges (NQ 1-min bars, RTH session)
| Hour | Typical Tick Count |
|------|--------------------|
| 09:30-10:00 ET | 1000-3000 |
| 10:00-11:30 ET | 400-1000 |
| 12:00-13:30 ET | 200-500 |
| 14:00-15:30 ET | 400-900 |
| 15:30-16:00 ET | 800-2500 |

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_tick_metrics(tick_count: pd.Series,
                          volume: pd.Series,
                          window: int = 20) -> pd.DataFrame:
    """
    tick_count: number of trades per bar (from data feed / SCID)
    volume: total volume per bar
    """
    out = pd.DataFrame()
    out['TickCount'] = tick_count
    out['AvgTradeSize'] = volume / tick_count.replace(0, np.nan)

    mu = tick_count.rolling(window).mean()
    sigma = tick_count.rolling(window).std()
    out['TickCountRatio'] = tick_count / mu.replace(0, np.nan)
    out['TickCountZ'] = (tick_count - mu) / sigma.replace(0, np.nan)

    # Volume per tick ratio (high = large avg trade)
    out['VolPerTick'] = volume / tick_count.replace(0, np.nan)
    out['VolPerTickZ'] = (
        (out['VolPerTick'] - out['VolPerTick'].rolling(window).mean()) /
        out['VolPerTick'].rolling(window).std()
    )

    return out

# Columns to record: TickCount, AvgTradeSize, TickCountRatio, TickCountZ, VolPerTickZ
# NOTE: TickCount must come from your SCID data feed if available.
# If not available, skip this data point and note as "data not available".
```

### Filter Application
Record `TickCountZ`, `VolPerTickZ`. Post-hoc: does `VolPerTickZ > 1.5` (large average trade size = institutional) at entry improve outcome? Does `TickCountZ > 2` (extreme activity) correlate with higher or lower win rate?

---

## 12. Market Impact / Slippage Proxy

### What It Measures
The range-to-volume ratio of a bar, which inversely captures market liquidity and potential slippage. A high range with low volume = thin market (each contract moves price more). A low range with high volume = deep market (absorbing large orders with little price movement). This is the inverse of the Absorption Ratio already in your system.

### Formula
```
# Range-to-Volume Ratio (RVR):
RVR = (High - Low) / Volume          # price impact per unit of volume

# Normalized:
RVR_Z = (RVR - RVR.rolling(window).mean()) / RVR.rolling(window).std()

# Amihud Illiquidity Ratio (academic standard, daily):
Amihud = |Return| / DollarVolume
       = |ln(Close/prev_Close)| / (Close * Volume)

# Intrabar version:
AmihudBar = (High - Low) / Close / Volume * 1e6   # scaled for readability

# Market Depth Proxy:
MarketDepth = Volume / (High - Low)   # contracts per point of range
                                       # high = liquid, low = illiquid
MarketDepth_Z = z-score of MarketDepth over rolling 20 bars
```

### Why It Is Valuable
- **Entry quality:** High RVR_Z at signal time means the market is thin. Your entry order will have more impact and worse fills. Consider skipping or reducing size.
- **Liquidity regime:** RVR trends upward before major dislocations — market makers pulling quotes. Early warning.
- **Low MarketDepth + signal:** Poor liquidity = exits will be painful if the trade goes wrong.
- **High MarketDepth (deep market):** Price is well-supported by volume. Moves are sustained. Signals in deep markets tend to have better fill quality.
- The Amihud illiquidity ratio is the standard academic measure used in market microstructure research (Amihud 2002).

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_market_impact(high: pd.Series, low: pd.Series,
                           close: pd.Series, volume: pd.Series,
                           window: int = 20) -> pd.DataFrame:
    """
    Range-to-Volume and market depth metrics.
    """
    out = pd.DataFrame()

    bar_range = (high - low).replace(0, np.nan)

    # Range-Volume Ratio (illiquidity proxy)
    out['RVR'] = bar_range / volume.replace(0, np.nan)
    mu_rvr = out['RVR'].rolling(window).mean()
    sigma_rvr = out['RVR'].rolling(window).std()
    out['RVR_Z'] = (out['RVR'] - mu_rvr) / sigma_rvr.replace(0, np.nan)

    # Market Depth (inverse: liquidity)
    out['MarketDepth'] = volume / bar_range
    mu_md = out['MarketDepth'].rolling(window).mean()
    sigma_md = out['MarketDepth'].rolling(window).std()
    out['MarketDepth_Z'] = (out['MarketDepth'] - mu_md) / sigma_md.replace(0, np.nan)

    # Intrabar Amihud
    ret = (close / close.shift(1) - 1).abs()
    dollar_vol = close * volume
    out['AmihudBar'] = ret / dollar_vol.replace(0, np.nan) * 1e8

    return out

# Columns to record: RVR, RVR_Z, MarketDepth, MarketDepth_Z
# Note: your existing AbsRatio = Range / |Delta|; RVR = Range / Volume.
# These are complementary: AbsRatio measures price impact vs delta; RVR measures vs total volume.
```

### Filter Application
Record `RVR_Z`, `MarketDepth_Z`. Post-hoc: does `MarketDepth_Z > 0.5` (above-average liquidity) improve win rate? Does `RVR_Z > 2.0` (thin market) predict worse outcomes?

---

## 13. Price Action Quality (Close Position in Bar)

### What It Measures
Where the closing price sits within the bar's total range, expressed as a normalized score from 0 to 1. Also called "close position" or "normalized close." A close near the high (score near 1.0) indicates buyers were dominant throughout the bar. A close near the low (score near 0.0) indicates sellers dominated.

### Formula
```
ClosePosition = (Close - Low) / (High - Low)
# 0.0 = closed exactly at low (maximum bearish bar)
# 1.0 = closed exactly at high (maximum bullish bar)
# 0.5 = closed at midpoint

# Body ratio (already in your data as BodyRatio):
BodyRatio = |Close - Open| / (High - Low)
# Low BodyRatio = doji/spinning top = indecision
# High BodyRatio + ClosePosition near 1.0 = strong bullish bar

# Wick ratio:
UpperWick = (High - max(Open, Close)) / (High - Low)
LowerWick = (min(Open, Close) - Low) / (High - Low)
# Large lower wick = buyers rejected lows = bullish
# Large upper wick = sellers rejected highs = bearish

# Close Position Z-score over window:
CP_Z = (ClosePosition - ClosePosition.rolling(window).mean()) / ClosePosition.rolling(window).std()
```

### Why It Is Valuable
- **ClosePosition < 0.2:** Strong bearish bar; sellers controlled entire bar. Used as confirmation for SHORT mean reversion or entry signal for continuation.
- **ClosePosition > 0.8:** Strong bullish bar; used as LONG confirmation.
- **Consecutive ClosePosition extremes:** 3+ bars all closing near lows = strong selling pressure building. Potential capitulation OR continuation depending on context.
- **ClosePosition at key level (VWAP, VAH, PDH):** Rejection bar confirmation. Price tested level and closed far from it = strong rejection signal for mean reversion.
- **LowerWick > 0.4 (long lower wick):** Classic hammering at support. Price tested lows but buyers brought it back up within the bar. High-probability reversal bar in isolation.
- This is your `BodyRatio` extended — it provides direction information that BodyRatio lacks.

### Typical Ranges
| ClosePosition | Bar Type |
|--------------|----------|
| 0.0-0.2 | Strong bearish (closing near low) |
| 0.2-0.35 | Moderately bearish |
| 0.35-0.65 | Indecision / doji zone |
| 0.65-0.8 | Moderately bullish |
| 0.8-1.0 | Strong bullish (closing near high) |

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_price_action_quality(open_: pd.Series, high: pd.Series,
                                  low: pd.Series, close: pd.Series,
                                  window: int = 10) -> pd.DataFrame:
    """
    Bar quality metrics based on close position within range.
    """
    out = pd.DataFrame()

    bar_range = (high - low).replace(0, np.nan)

    # Close position (0 = at low, 1 = at high)
    out['ClosePos'] = (close - low) / bar_range

    # Wick analysis
    out['UpperWick'] = (high - pd.concat([open_, close], axis=1).max(axis=1)) / bar_range
    out['LowerWick'] = (pd.concat([open_, close], axis=1).min(axis=1) - low) / bar_range

    # Open position (where did we open relative to range)
    out['OpenPos'] = (open_ - low) / bar_range

    # Intrabar move: did price close above or below open?
    out['BarDirection'] = np.sign(close - open_).astype(int)

    # Consecutive closes near highs/lows (last N bars)
    out['ConsecHighClose'] = (out['ClosePos'] > 0.7).rolling(window).sum()
    out['ConsecLowClose'] = (out['ClosePos'] < 0.3).rolling(window).sum()

    return out

# Columns to record: ClosePos, UpperWick, LowerWick, OpenPos, BarDirection
# Note: BodyRatio already recorded; ClosePos adds directional context.
```

### Filter Application
Record `ClosePos`, `UpperWick`, `LowerWick`. Post-hoc: for LONG signals, does `LowerWick > 0.35` (hammer rejection at lows) improve win rate? For SHORT signals, does `UpperWick > 0.35` improve outcome? Does `ClosePos` confirm signal direction?

---

## 14. Momentum of Delta

### What It Measures
The rate of change of cumulative delta — how fast the order flow imbalance is accelerating or decelerating. Delta acceleration (delta rising faster) vs. delta deceleration (delta slowing while price continues) is a leading indicator of order flow exhaustion.

### Formula
```
# Delta per bar (already have this)
Delta_t = BuyVol_t - SellVol_t

# Cumulative delta over rolling window (already have CumDelta)

# Delta Rate of Change:
DeltaROC_N = CumDelta[-1] - CumDelta[-N]      # raw change in cumulative delta

# Delta Acceleration (second derivative):
DeltaAccel = DeltaROC_N[-1] - DeltaROC_N[-N]  # change in the rate of delta change

# Delta Momentum (EMA-smoothed):
DeltaMom_fast = EMA(Delta, 5)
DeltaMom_slow = EMA(Delta, 20)
DeltaMom_Signal = DeltaMom_fast - DeltaMom_slow  # MACD-like, applied to delta

# Delta Velocity Z-score:
DeltaVel = Delta.rolling(5).sum()              # 5-bar cumulative
DeltaVel_Z = z-score of DeltaVel over 50 bars

# Delta Divergence from Price:
PriceROC_N  = Close[-1] - Close[-N]
DeltaROC_Norm = DeltaROC_N / Volume.rolling(N).sum()  # normalize
# If PriceROC_N > 0 and DeltaROC_Norm < 0: bearish divergence
```

### Why It Is Valuable
- **Delta acceleration upward into price resistance:** Buyers are becoming increasingly aggressive at a known resistance level. Either they are about to force a breakout or they will get trapped — fade opportunity when combined with other signals.
- **Delta deceleration (slowing) while price makes new high:** Buying is exhausting. Classic pre-reversal signal. Fade setup.
- **Delta velocity spike (extreme short-term buying/selling):** Often marks the end of a panic move — capitulation point. LONG opportunity after negative delta spike at support.
- **DeltaMom_Signal crossing zero:** Delta momentum shift — potential early trend change in order flow before price reacts.
- This is what Sierra Chart's "footprint" and "cumulative delta" tools display visually — this quantifies it.

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_delta_momentum(delta: pd.Series,
                            cum_delta: pd.Series,
                            volume: pd.Series,
                            close: pd.Series,
                            roc_window: int = 5,
                            z_window: int = 50) -> pd.DataFrame:
    """
    Delta momentum, acceleration, and divergence metrics.
    """
    out = pd.DataFrame()

    # Rate of Change of cumulative delta
    out['DeltaROC5'] = cum_delta.diff(roc_window)
    out['DeltaROC20'] = cum_delta.diff(20)

    # Acceleration (change in ROC)
    out['DeltaAccel'] = out['DeltaROC5'].diff(roc_window)

    # MACD-style delta momentum
    ema_fast = delta.ewm(span=5, adjust=False).mean()
    ema_slow = delta.ewm(span=20, adjust=False).mean()
    out['DeltaMom_Signal'] = ema_fast - ema_slow

    # Delta velocity Z-score
    delta_vel = delta.rolling(roc_window).sum()
    mu = delta_vel.rolling(z_window).mean()
    sigma = delta_vel.rolling(z_window).std()
    out['DeltaVel_Z'] = (delta_vel - mu) / sigma.replace(0, np.nan)

    # Divergence from price
    price_roc = close.diff(roc_window)
    delta_roc_norm = out['DeltaROC5'] / volume.rolling(roc_window).sum().replace(0, np.nan)
    out['DeltaPriceDivScore'] = np.sign(price_roc) - np.sign(delta_roc_norm)
    # -2 = price down, delta up (bullish div); +2 = price up, delta down (bearish div); 0 = aligned

    return out

# Columns to record: DeltaROC5, DeltaAccel, DeltaMom_Signal, DeltaVel_Z, DeltaPriceDivScore
```

### Filter Application
Record `DeltaVel_Z`, `DeltaPriceDivScore`. Post-hoc: for LONG signals, does `DeltaVel_Z < -2.0` (extreme negative delta velocity = capitulation) followed by signal improve outcome? Does `DeltaPriceDivScore == -2` (bullish divergence) filter improve LONG win rate?

---

## 15. Autocorrelation of Returns

### What It Measures
The correlation of bar-by-bar returns with their own lagged values. Lag-1 autocorrelation measures whether the current bar's return predicts the next bar's return. Negative autocorrelation = mean-reverting behavior (overshoots correct themselves). Positive autocorrelation = trending/momentum behavior.

### Formula
```
r_t = Close_t / Close_{t-1} - 1    # bar return (or log return)

Lag-1 autocorrelation:
AC_1 = corr(r_t, r_{t-1})  over a rolling window

Lag-5 autocorrelation:
AC_5 = corr(r_t, r_{t-5})

Rolling implementation (window W):
AC_1_W = r.rolling(W).apply(lambda x: pd.Series(x).autocorr(lag=1))

Interpretation:
  AC_1 < -0.1 : Mean-reverting regime (favor mean reversion strategies)
  AC_1 > +0.1 : Trending/momentum regime (favor momentum strategies)
  -0.1 < AC_1 < +0.1: Random walk (no strong edge either way)
```

**Statistical note:** For N=50 bars, a 2-sigma threshold is approximately |AC| > 2/sqrt(50) ≈ 0.28. Values beyond this are statistically significant at 95%.

### Why It Is Valuable
- **Direct regime detection:** Autocorrelation is the most direct measure of whether a time series is mean-reverting or trending. More theoretically grounded than ADX or Hurst for short windows.
- **AC_1 and Hurst are related:** Hurst < 0.5 implies negative autocorrelation; they provide confirming evidence from different mathematical frameworks.
- **Rolling AC_1 changing sign:** Regime transition signal. When AC_1 shifts from negative to positive, mean reversion strategies start failing.
- **AC_5:** Tests for 5-bar cycles. Useful for detecting intraday rhythms in NQ (e.g., 5-minute cycle effects in 1-minute data).
- **Variance Ratio test is mathematically equivalent** to testing whether sum of autocorrelations across lags differs from zero.

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_return_autocorrelation(close: pd.Series,
                                    window: int = 50) -> pd.DataFrame:
    """
    Rolling lag-1 and lag-5 autocorrelation of bar returns.
    Returns: AC_1, AC_5 series.
    """
    returns = close.pct_change()  # or np.log(close/close.shift(1))

    out = pd.DataFrame()

    out['AC_1'] = returns.rolling(window).apply(
        lambda x: pd.Series(x).autocorr(lag=1),
        raw=False
    )

    out['AC_5'] = returns.rolling(window).apply(
        lambda x: pd.Series(x).autocorr(lag=5),
        raw=False
    )

    # Regime label based on AC_1
    def ac_regime(ac):
        if pd.isna(ac): return 'UNKNOWN'
        if ac < -0.15:  return 'MEAN_REV'
        if ac > +0.15:  return 'TRENDING'
        return 'RANDOM'

    out['AC_Regime'] = out['AC_1'].apply(ac_regime)

    return out

# Columns to record: AC_1, AC_5, AC_Regime
# Window of 50 bars = ~50 minutes of 1-min data; consider also window=20 and window=100
```

### Filter Application
Record `AC_1`, `AC_Regime`. Post-hoc: does `AC_Regime == MEAN_REV` significantly improve mean reversion win rate vs `AC_Regime == TRENDING`? Combine with Hurst: `Hurst < 0.5 AND AC_1 < -0.1` = high-confidence mean reversion regime filter.

---

## 16. Beta to Market (NQ vs ES)

### What It Measures
The rolling correlation and beta of NQ (Nasdaq futures) relative to ES (S&P 500 futures). Beta measures how much NQ moves per unit of ES movement. Abnormal beta or correlation divergence signals that NQ is unusually weak or strong relative to its normal relationship with the broader market — a potential mean reversion opportunity.

### Formula
```
# On aligned bars (same timestamps):
r_NQ_t = ln(NQ_Close_t / NQ_Close_{t-1})
r_ES_t = ln(ES_Close_t / ES_Close_{t-1})

Rolling Beta (window W):
  Beta_NQ_ES = cov(r_NQ, r_ES, W) / var(r_ES, W)
  # Typical range: 1.0-1.6 (NQ is usually more volatile than ES)

Rolling Correlation:
  Corr_NQ_ES = corr(r_NQ, r_ES, W)
  # Normal: 0.85-0.98 (highly correlated)
  # Low correlation < 0.7: divergence event

Relative Strength (deviation from expected):
  Expected_NQ_return = Beta_NQ_ES * r_ES_current
  RS_Divergence = r_NQ_cumulative(N) - Beta_NQ_ES * r_ES_cumulative(N)
  # Positive = NQ outperforming ES (stretched = fade with SHORT)
  # Negative = NQ underperforming ES (stretched = fade with LONG)

RS_Divergence_Z = z-score of RS_Divergence over rolling window
```

### Why It Is Valuable
- **NQ/ES divergence as mean reversion signal:** When NQ has deviated significantly from its expected path relative to ES (accounting for beta), there is a statistical tendency to converge. This is a statistical arbitrage concept applied intraday.
- **RS_Divergence_Z > 2.0:** NQ has outperformed ES by an unusual amount. Mean reversion SHORT opportunity in NQ.
- **RS_Divergence_Z < -2.0:** NQ has underperformed ES significantly. Mean reversion LONG opportunity in NQ.
- **Low correlation (< 0.75):** Market regime shift in progress. Either sector rotation (tech diverging from broad market) or NQ-specific news. Higher uncertainty — reduce size.
- **Beta spike:** NQ suddenly becoming much more volatile than ES — leverage/risk-off flows. Caution.
- Used by relative-value desks and stat arb funds as a primary signal source.

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_nq_es_relative_strength(nq_close: pd.Series,
                                     es_close: pd.Series,
                                     window: int = 20,
                                     z_window: int = 100) -> pd.DataFrame:
    """
    Rolling beta, correlation, and relative strength divergence of NQ vs ES.
    nq_close, es_close: aligned price series (same timestamps).
    """
    out = pd.DataFrame()

    r_nq = np.log(nq_close / nq_close.shift(1))
    r_es = np.log(es_close / es_close.shift(1))

    # Rolling correlation
    out['Corr_NQ_ES'] = r_nq.rolling(window).corr(r_es)

    # Rolling beta
    cov = r_nq.rolling(window).cov(r_es)
    var_es = r_es.rolling(window).var()
    out['Beta_NQ_ES'] = cov / var_es.replace(0, np.nan)

    # Relative strength divergence (cumulative over window)
    cum_nq = r_nq.rolling(window).sum()
    cum_es = r_es.rolling(window).sum()
    out['RS_Divergence'] = cum_nq - out['Beta_NQ_ES'] * cum_es

    # Z-score of divergence
    mu = out['RS_Divergence'].rolling(z_window).mean()
    sigma = out['RS_Divergence'].rolling(z_window).std()
    out['RS_Div_Z'] = (out['RS_Divergence'] - mu) / sigma.replace(0, np.nan)

    return out

# Columns to record: Corr_NQ_ES, Beta_NQ_ES, RS_Div_Z
# NOTE: Requires ES futures bars aligned to NQ bars by timestamp.
# This is a multi-instrument data point — requires ES data pipeline addition.
```

### Filter Application
Record `RS_Div_Z`, `Corr_NQ_ES`. Post-hoc: does `|RS_Div_Z| > 1.5` (NQ significantly diverged from ES) improve mean reversion win rate when trading in the direction of convergence? Does `Corr_NQ_ES < 0.75` (unusual decorrelation) hurt strategy performance?

---

## 17. Z-Score of Volume

### What It Measures
How statistically unusual the current bar's volume is relative to recent history, expressed in standard deviations. Distinguishes genuinely anomalous volume events (breakouts, institutional activity, news-driven) from normal variation. Complements the existing VolRatio (current/20-bar mean) by also accounting for the dispersion of historical volume.

### Formula
```
VolZ = (Volume - Volume.rolling(window).mean()) / Volume.rolling(window).std()

# Typically window = 20 bars
# VolZ > +2.0: Unusually high volume (> 2 standard deviations above average)
# VolZ < -1.0: Unusually low volume
# VolZ > +3.0: Extreme volume event (absorption, capitulation, news)

# Volume Z-score at specific conditions:
VolZ_atSignal = VolZ at the signal bar
VolZ_prevBar  = VolZ of bar immediately before signal

# Volume trend:
VolTrend_3 = Volume.rolling(3).mean() / Volume.rolling(10).mean()
# > 1.3 = volume building up (potential breakout or exhaustion incoming)
# < 0.7 = volume drying up (indecision or accumulation)
```

### Why It Is Valuable
- **High VolZ at key level (PDH, VWAP, VAH):** Large volume at a known level = institutional activity. Either strong breakout or strong rejection. Context determines which.
- **High VolZ + mean reversion signal:** When a mean reversion setup occurs on anomalously high volume, it often marks the capitulation point — the highest-probability reversal bar.
- **Low VolZ at signal:** Low-conviction signal. Price moved without real participation. Prone to fake-outs.
- **Volume drying up (VolTrend_3 < 0.7) near key level:** Classic technical analysis pattern — volume contraction before move. Breakout signal, not mean reversion.
- **VolZ complements RVOL:** RVOL compares to same time-of-day; VolZ compares to recent absolute levels. Use both for complete picture.

### Typical Ranges
| VolZ | Interpretation |
|------|---------------|
| < -1.5 | Unusually quiet |
| -1.5 to -0.5 | Below normal |
| -0.5 to +0.5 | Normal range |
| +0.5 to +1.5 | Slightly elevated |
| +1.5 to +2.5 | Notable (monitor) |
| +2.5 to +4.0 | High significance |
| > +4.0 | Extreme event |

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_volume_zscore(volume: pd.Series,
                           window: int = 20,
                           trend_fast: int = 3,
                           trend_slow: int = 10) -> pd.DataFrame:
    """
    Volume Z-score and volume trend ratio.
    """
    out = pd.DataFrame()

    mu = volume.rolling(window).mean()
    sigma = volume.rolling(window).std()
    out['VolZ'] = (volume - mu) / sigma.replace(0, np.nan)

    # Volume trend: recent average vs longer average
    out['VolTrend'] = volume.rolling(trend_fast).mean() / volume.rolling(trend_slow).mean().replace(0, np.nan)

    # Lagged VolZ (was there a volume spike before this bar?)
    out['VolZ_Lag1'] = out['VolZ'].shift(1)
    out['VolZ_Lag2'] = out['VolZ'].shift(2)

    # Max VolZ over last N bars
    out['VolZ_Max5'] = out['VolZ'].rolling(5).max()

    return out

# Columns to record: VolZ, VolTrend, VolZ_Lag1, VolZ_Max5
```

### Filter Application
Record `VolZ`. Post-hoc: does `VolZ > 2.0` at signal bar improve win rate for mean reversion (capitulation)? Does `VolZ < 0.5` (thin volume) hurt win rate? Combine with `OFI_Z` — high absolute `VolZ` + extreme `OFI_Z` = capitulation/absorption detection.

---

## 18. Session Progress

### What It Measures
The fraction of the trading session that has elapsed at the time of signal entry, expressed as 0.0 (session open) to 1.0 (session close). Also captures absolute time-of-day in ET. Intraday mean reversion performance varies dramatically by session phase — certain windows have structural edges.

### Formula
```
# NQ CME session: Sunday 17:00 ET to Friday 16:00 ET (nearly 24/5)
# RTH (Regular Trading Hours): 09:30-16:00 ET
# Most significant mean reversion: RTH only

# Session Progress for RTH:
SessionStart = today at 09:30 ET
SessionEnd   = today at 16:00 ET
SessionDuration = 390 minutes

Progress = (CurrentTime - SessionStart).total_seconds() / (SessionDuration * 60)
# 0.0 = 09:30 ET, 0.5 = 12:45 ET, 1.0 = 16:00 ET

# Minute of Day (integer 0-1439):
MinuteOfDay = hour * 60 + minute  (in ET)

# Session Phase buckets:
OPEN:    Progress 0.00-0.10   (09:30-10:27)   High vol, high RVOL
MORNING: Progress 0.10-0.40   (10:27-12:06)   Settles into trend or range
MIDDAY:  Progress 0.40-0.65   (12:06-13:51)   Low vol, choppy, highest MR edge
LUNCH:   Progress 0.65-0.75   (13:51-14:24)   Transitional
CLOSE:   Progress 0.75-1.00   (14:24-16:00)   Institutional rebalancing, directional
```

**Research on NQ session phases (general quant findings):**
- Open (first 30 min): highest volume, widest spreads, momentum > mean reversion
- Midday (12:00-14:00 ET): lowest volume, narrowest ranges, mean reversion > momentum
- Power Hour (14:30-16:00 ET): institutional flow dominates, directional moves
- Best mean reversion window for NQ: 10:00-12:30 ET and 13:00-14:30 ET

### Python Implementation
```python
import pandas as pd
import numpy as np
from datetime import time

def compute_session_progress(datetime_series: pd.Series,
                              session_tz: str = 'US/Eastern') -> pd.DataFrame:
    """
    Session progress and time-of-day features.
    datetime_series: bar timestamps (timezone-aware or naive UTC).
    """
    out = pd.DataFrame()

    dt = pd.to_datetime(datetime_series)
    if dt.dt.tz is None:
        dt = dt.dt.tz_localize('UTC')
    dt_et = dt.dt.tz_convert('US/Eastern')

    # RTH session: 09:30-16:00
    rth_start_min = 9 * 60 + 30   # 570 minutes
    rth_end_min   = 16 * 60        # 960 minutes
    rth_duration  = rth_end_min - rth_start_min  # 390

    minute_of_day = dt_et.dt.hour * 60 + dt_et.dt.minute
    out['MinuteOfDay_ET'] = minute_of_day

    # Session progress 0-1 (clipped to RTH)
    prog = (minute_of_day - rth_start_min) / rth_duration
    out['SessionProgress'] = prog.clip(0, 1)

    # Session phase
    def phase(p):
        if p < 0.10: return 'OPEN'
        if p < 0.40: return 'MORNING'
        if p < 0.65: return 'MIDDAY'
        if p < 0.75: return 'LUNCH'
        return 'CLOSE'
    out['SessionPhase'] = out['SessionProgress'].apply(phase)

    # Is bar in RTH?
    out['InRTH'] = ((minute_of_day >= rth_start_min) &
                    (minute_of_day < rth_end_min)).astype(int)

    return out

# Columns to record: MinuteOfDay_ET, SessionProgress, SessionPhase, InRTH
# This extends Hour (planned) with finer granularity and phase classification.
```

### Filter Application
Record `SessionProgress`, `SessionPhase`. Post-hoc: bin win rate by `SessionPhase`. Hypothesized finding: `MIDDAY` has highest mean-reversion win rate; `OPEN` has lowest (momentum dominates). Compare `OPEN` vs `MORNING` vs `MIDDAY` win rates for both BUY and SELL signals separately.

---

## 19. Spread Between VWAP Anchors

### What It Measures
The difference between two differently-anchored VWAPs — typically the standard session VWAP and an anchored VWAP from a specific significant price level (prior day's high/low, session high/low, or significant volume node). When these two VWAPs diverge, it signals that price has moved away from multiple definitions of "fair value" simultaneously.

### Formula
```
# Session VWAP (already computed, resets at session open):
VWAP_Session = cumulative(Volume * Close) / cumulative(Volume)

# Anchored VWAP from session high (so far):
VWAP_High = VWAP anchored to the bar that set the session high
           = sum(Volume * Close from session_high_bar to now) / sum(Volume from session_high_bar to now)

# Anchored VWAP from session low:
VWAP_Low = VWAP anchored to bar that set session low

# Spread:
VWAP_Spread_HL = VWAP_High - VWAP_Low   # divergence between anchors
VWAP_Spread_Z  = z-score of VWAP_Spread_HL over session

# Price location relative to both:
Dist_From_SessionVWAP = (Close - VWAP_Session) / ATR14     # already have this
Dist_From_HighVWAP    = (Close - VWAP_High) / ATR14
Dist_From_LowVWAP     = (Close - VWAP_Low) / ATR14

# Mean of anchors (composite fair value):
VWAP_Composite = (VWAP_Session + VWAP_High + VWAP_Low) / 3
Dist_From_Composite = (Close - VWAP_Composite) / ATR14
```

### Why It Is Valuable
- **Wide VWAP_Spread_HL:** Session has had a large range with significant volume on both ends. Price is "contested" — multiple fair values competing. Higher mean-reversion probability from extremes.
- **Price between VWAP anchors:** Inside the VWAP sandwich = balanced, fair value zone. Mean reversion exits target this zone.
- **Price outside all VWAP anchors:** Strong directional move; mean reversion less reliable. Consider momentum instead.
- **VWAP convergence (spread narrowing):** As session progresses and VWAPs converge, price is settling toward single fair value. End-of-session mean reversion opportunity.
- **Anchored VWAP from PDH/PDL:** Institutional players who entered near prior day's extremes use AVWAP as their breakeven. Price returning to these levels often triggers hedging flows = additional mean reversion fuel.
- Used extensively by ICT (Inner Circle Trader) methodology practitioners and institutional order flow analysts.

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_anchored_vwap(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Compute session VWAP, anchored VWAP from session high/low,
    and spread between anchors.
    bars: must have DateTime, Open, High, Low, Close, Volume, Date columns.
    """
    bars = bars.copy()
    results = []

    for date, session in bars.groupby('Date'):
        session = session.copy().reset_index(drop=True)

        prices = session['Close'].values
        highs  = session['High'].values
        lows   = session['Low'].values
        vols   = session['Volume'].values
        n      = len(session)

        session_vwap = []
        vwap_high    = []
        vwap_low     = []

        cum_pv = 0.0
        cum_v  = 0.0
        max_high_idx = 0
        min_low_idx  = 0
        cum_pv_from_high = 0.0
        cum_v_from_high  = 0.0
        cum_pv_from_low  = 0.0
        cum_v_from_low   = 0.0

        for i in range(n):
            p = prices[i]
            v = vols[i]

            # Session VWAP
            cum_pv += p * v
            cum_v  += v
            session_vwap.append(cum_pv / cum_v if cum_v > 0 else np.nan)

            # Track session high
            if highs[i] >= highs[max_high_idx]:
                max_high_idx = i
                # Reset anchored VWAP from new high
                cum_pv_from_high = p * v
                cum_v_from_high  = v
            else:
                cum_pv_from_high += p * v
                cum_v_from_high  += v
            vwap_high.append(cum_pv_from_high / cum_v_from_high if cum_v_from_high > 0 else np.nan)

            # Track session low
            if lows[i] <= lows[min_low_idx]:
                min_low_idx = i
                cum_pv_from_low = p * v
                cum_v_from_low  = v
            else:
                cum_pv_from_low += p * v
                cum_v_from_low  += v
            vwap_low.append(cum_pv_from_low / cum_v_from_low if cum_v_from_low > 0 else np.nan)

        session['VWAP_Session'] = session_vwap
        session['VWAP_HighAnchor'] = vwap_high
        session['VWAP_LowAnchor']  = vwap_low
        results.append(session)

    out = pd.concat(results).sort_values('DateTime').reset_index(drop=True)

    out['VWAP_AnchorSpread'] = out['VWAP_HighAnchor'] - out['VWAP_LowAnchor']
    out['VWAP_Composite'] = (out['VWAP_Session'] + out['VWAP_HighAnchor'] + out['VWAP_LowAnchor']) / 3

    if 'ATR14' in out.columns:
        out['Dist_HighAnchor_ATR'] = (out['Close'] - out['VWAP_HighAnchor']) / out['ATR14']
        out['Dist_LowAnchor_ATR']  = (out['Close'] - out['VWAP_LowAnchor']) / out['ATR14']
        out['Dist_Composite_ATR']  = (out['Close'] - out['VWAP_Composite']) / out['ATR14']

    return out

# Columns to record:
# VWAP_HighAnchor, VWAP_LowAnchor, VWAP_AnchorSpread,
# Dist_HighAnchor_ATR, Dist_LowAnchor_ATR, Dist_Composite_ATR
```

### Filter Application
Record `VWAP_AnchorSpread`, `Dist_Composite_ATR`. Post-hoc: does `|Dist_Composite_ATR| > 1.5` (far from all three VWAP definitions simultaneously) improve mean reversion win rate? Does wide `VWAP_AnchorSpread` (contested session) improve or hurt signal quality?

---

## 20. Overnight Gap Filled (Boolean)

### What It Measures
A binary flag indicating whether today's opening gap (from yesterday's close to today's open) has been filled at any point during the current session. Before the gap is filled, price action has a different statistical character (gap-fill drive) than after the gap is filled (no structural target remaining). This acts as a session state variable.

### Formula
```
# Gap direction and fill definition:
PrevClose = yesterday's closing price
TodayOpen = today's opening price
GapUp     = TodayOpen > PrevClose  → gap is "filled" when Low_t <= PrevClose
GapDown   = TodayOpen < PrevClose  → gap is "filled" when High_t >= PrevClose
Flat      = no gap (|GapATR| < 0.1)

# Per bar state:
GapFilled = 0  (initialized at session open)

For each bar:
  if GapUp  and Low[t]  <= PrevClose: GapFilled = 1 (remains 1 for rest of session)
  if GapDown and High[t] >= PrevClose: GapFilled = 1

# Derived features:
GapFillProgress = distance to fill as fraction:
  if GapUp:  Progress = (TodayOpen - Close[t]) / (TodayOpen - PrevClose)  # 0=just opened, 1=filled
  if GapDown: Progress = (Close[t] - TodayOpen) / (PrevClose - TodayOpen)
  Progress clipped to [0, 1]

TimeToFill = bar index when GapFilled first became 1 (filled early vs late)
```

**Gap fill statistics (NQ, empirical research basis):**
- Small gaps (< 0.5 ATR): ~78% fill within the session
- Medium gaps (0.5-1.5 ATR): ~60% fill within the session
- Large gaps (> 1.5 ATR): ~40% fill within the session
- Gaps that fill: typically fill within first 90 minutes of RTH
- Unfilled small gaps at 13:00 ET: ~50% fill in afternoon; ~50% remain unfilled

### Why It Is Valuable
- **Before fill (GapFilled = 0, gap up):** Price has a structural "gravity" toward PrevClose. Short signals that target gap fill have an additional tailwind. Long signals going away from the fill target face structural headwind.
- **After fill (GapFilled = 1):** The structural gap-fill drive is gone. Price is now driven by normal session dynamics. Signal quality reverts to baseline.
- **Regime change within session:** `GapFilled` turning from 0 to 1 is a regime change event. Mean reversion characteristics differ pre- and post-fill.
- **Gap direction + signal direction:** Gap up AND signal is SHORT AND `GapFilled == 0`: strong tailwind (both gap fill bias and mean reversion bias aligned). Highest-confidence combination.
- **GapFillProgress:** Partial fill progress quantifies where price is in the gap-fill journey — not just binary but graduated.

### Python Implementation
```python
import pandas as pd
import numpy as np

def compute_gap_fill_status(bars: pd.DataFrame,
                             gap_flat_threshold_atr: float = 0.10) -> pd.DataFrame:
    """
    Per-bar gap fill status and progress.
    bars: must have DateTime, High, Low, Close, Date, PrevClose, GapATR columns.
    PrevClose and GapATR computed by compute_gap() function (see #7 above).
    """
    bars = bars.copy()
    results = []

    for date, session in bars.groupby('Date'):
        session = session.copy().reset_index(drop=True)

        if session['PrevClose'].isna().all() or session['GapATR'].isna().all():
            session['GapFilled'] = np.nan
            session['GapFillProgress'] = np.nan
            results.append(session)
            continue

        prev_close = session['PrevClose'].iloc[0]
        gap_atr    = session['GapATR'].iloc[0]
        today_open = session['Open'].iloc[0] if 'Open' in session.columns else session['Close'].iloc[0]

        # Determine gap direction
        if abs(gap_atr) < gap_flat_threshold_atr:
            gap_dir = 0  # flat
        else:
            gap_dir = int(np.sign(gap_atr))  # +1 gap up, -1 gap down

        gap_filled = 0
        filled_col = []
        progress_col = []

        for i in range(len(session)):
            if gap_dir == 0:
                filled_col.append(np.nan)
                progress_col.append(np.nan)
                continue

            if gap_filled == 0:
                if gap_dir == 1 and session['Low'].iloc[i] <= prev_close:
                    gap_filled = 1
                elif gap_dir == -1 and session['High'].iloc[i] >= prev_close:
                    gap_filled = 1

            filled_col.append(gap_filled)

            # Fill progress (0 = at open, 1 = gap filled)
            gap_size = abs(today_open - prev_close)
            if gap_size > 0:
                if gap_dir == 1:
                    progress = (today_open - session['Close'].iloc[i]) / gap_size
                else:
                    progress = (session['Close'].iloc[i] - today_open) / gap_size
                progress_col.append(float(np.clip(progress, 0, 1)))
            else:
                progress_col.append(np.nan)

        session['GapFilled'] = filled_col
        session['GapFillProgress'] = progress_col
        results.append(session)

    out = pd.concat(results).sort_values('DateTime').reset_index(drop=True)
    return out

# Columns to record: GapFilled, GapFillProgress, GapDirection (from #7)
# GapFilled = 0: gap still open (structural fill bias active)
# GapFilled = 1: gap has been filled (baseline dynamics)
```

### Filter Application
Record `GapFilled`, `GapFillProgress`. Post-hoc:
- For SHORT signals when `GapDirection == 1` (gap up): does `GapFilled == 0` improve win rate vs `GapFilled == 1`?
- `GapFillProgress between 0.3 and 0.7` (partial fill): is the signal less reliable mid-gap?
- `GapFilled == 0 AND GapCategory == MEDIUM`: best gap-fill mean reversion setup combination?

---

## Implementation Priority

### Group A: No New Data Sources Required (implement immediately)
These need only existing OHLCV + delta data:

| # | Data Point | Columns to Add |
|---|-----------|----------------|
| 3 | ATR Percentile Rank | `ATR_Pct500` |
| 4 | Order Flow Imbalance | `OFI`, `OFI_Cum20`, `OFI_Z` |
| 5 | Trade Pressure Index | `TPI_14`, `DeltaMom_10` |
| 6 | Prior Day Levels | `PDH`, `PDL`, `PDC`, `PD_Location`, `Dist_PDH_ATR`, `Dist_PDL_ATR` |
| 7 | Opening Gap | `GapATR`, `GapDirection`, `GapCategory` |
| 9 | Delta Divergence | `DeltaDiv_Bool`, `DeltaDiv_Score` |
| 12 | Market Impact | `RVR`, `RVR_Z`, `MarketDepth_Z` |
| 13 | Price Action Quality | `ClosePos`, `UpperWick`, `LowerWick` |
| 14 | Delta Momentum | `DeltaROC5`, `DeltaVel_Z`, `DeltaPriceDivScore` |
| 15 | Autocorrelation | `AC_1`, `AC_5`, `AC_Regime` |
| 17 | Volume Z-Score | `VolZ`, `VolTrend` |
| 18 | Session Progress | `SessionProgress`, `SessionPhase` |
| 19 | VWAP Anchors | `VWAP_AnchorSpread`, `Dist_Composite_ATR` |
| 20 | Gap Fill Status | `GapFilled`, `GapFillProgress` |

### Group B: Requires Intraday Volume Profile Calculation
| # | Data Point | Columns to Add |
|---|-----------|----------------|
| 2 | Realized Volatility | `RV_5`, `RV_20`, `RV_60`, `RV_Pct` |
| 8 | Value Area / POC | `POC`, `VAH`, `VAL`, `DistPOC_ATR`, `VA_Location` |
| 10 | Relative Volume (RVOL) | `RVOL` |

### Group C: Requires External Data Sources
| # | Data Point | External Data Needed |
|---|-----------|---------------------|
| 1 | VIX Filter | VIX, VIX9D, VIX3M daily closes |
| 11 | Tick Count | Tick count per bar from SCID feed |
| 16 | NQ/ES Beta | ES futures bars aligned by timestamp |

---

## Summary Table

| # | Name | Formula Core | Range | Why Use |
|---|------|-------------|-------|---------|
| 1 | VIX Regime | VIX level + term structure | 0-100 pct | Regime filter, avoid crisis |
| 2 | Realized Vol | Yang-Zhang estimator | Annualized % | True vol for sizing |
| 3 | ATR Percentile | rank(ATR, window) | 0-100 | Normalized vol context |
| 4 | OFI | Delta / Volume | -1 to +1 | Order flow direction |
| 5 | Trade Pressure | RSI applied to delta | 0-100 | Sustained flow pressure |
| 6 | Dist PDH/PDL/PDC | (Close - Level) / ATR | ATR units | Institutional reference levels |
| 7 | Opening Gap | (Open - PrevClose) / ATR | ATR units | Gap fill bias direction |
| 8 | VAH/VAL/POC | Volume profile 70% zone | Price levels | Fair value anchor |
| 9 | Delta Divergence | sign(PriceChange) != sign(DeltaChange) | Bool + score | Leading reversal signal |
| 10 | RVOL | Volume / same-time-avg | 0-5+ | True volume significance |
| 11 | Tick Count | Trades per bar | Count / Z | Institutional vs retail |
| 12 | Market Impact | Range / Volume | Z-score | Liquidity proxy |
| 13 | ClosePosition | (Close-Low)/(High-Low) | 0-1 | Bar directional quality |
| 14 | Delta Momentum | d(CumDelta)/dt | Z-score | Delta acceleration |
| 15 | Return Autocorr | corr(r_t, r_{t-1}) | -1 to +1 | Regime detection |
| 16 | Beta NQ/ES | cov(NQ,ES)/var(ES) | 0.8-2.0 | Relative strength divergence |
| 17 | Volume Z-Score | (Vol - mean) / std | Z-score | Volume significance |
| 18 | Session Progress | Elapsed / Duration | 0-1 | Time-of-day regime |
| 19 | VWAP Spread | VWAP_High - VWAP_Low | ATR units | Multi-anchor fair value |
| 20 | Gap Fill Status | Boolean + progress | 0/1 + 0-1 | Structural bias state |

---

## References

- Cont, R., Kukanov, A., & Stoikov, S. (2014). "The Price Impact of Order Book Events." *Journal of Financial Econometrics* — foundational OFI paper.
- Yang, D., & Zhang, Q. (2000). "Drift-Independent Volatility Estimation Based on High, Low, Open, and Close Prices." *Journal of Business* — Yang-Zhang estimator.
- Amihud, Y. (2002). "Illiquidity and Stock Returns." *Journal of Financial Markets* — Amihud illiquidity ratio.
- Steidlmayer, J.P. (1985). CBOT Market Profile — volume profile / value area original concept.
- Lo, A. & MacKinlay, A.C. (1988). "Stock Market Prices Do Not Follow Random Walks." *Review of Financial Studies* — variance ratio and autocorrelation.
- Garman, M.B. & Klass, M.J. (1980). "On the Estimation of Security Price Volatilities from Historical Data." *Journal of Business* — OHLC volatility estimators.
- Harris, L. (2003). *Trading and Exchanges: Market Microstructure for Practitioners.* Oxford — comprehensive market microstructure reference.
