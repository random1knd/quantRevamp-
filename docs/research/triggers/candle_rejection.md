# Candle Rejection Trigger

**Status:** Documented

---

## What Is It?

The candle rejection trigger detects when a price bar forms a **long wick against the move direction**, indicating price is being rejected at an extreme level. This is the candlestick pattern known as a hammer (at lows) or shooting star (at highs).

In mean-reversion strategies, a rejection candle at a price extreme (e.g., 2+ SDs from VWAP) signals that buyers or sellers tried to push price further but failed — the counterparty stepped in and pushed back, creating the wick.

---

## Market Theory

**Assumption:** A long wick is a visual manifestation of competing supply/demand at price extremes. When price reaches an extreme and forms a long wick, it signals:
- The initial aggressor tried to push further
- Counterparty supplied / demanded at that level
- Price was rejected back toward equilibrium

**Application:**
- Price rose to 2+ SDs above VWAP (extended)
- Current candle has a long upper wick (rejection of the high)
- Close is below the wick high (price pulled back)
- Signal: SELL_FADE (price rejected the extreme, reversing)

**Reference:** Nison, S. (1991) *Japanese Candlestick Charting Techniques* — wick formation indicates rejection; Engulfing, Hammer, and Shooting Star patterns precede reversals.

---

## Mathematical Foundation

### Candle Components

```
High[t]      = highest price in bar
Low[t]       = lowest price in bar
Close[t]     = closing price
Open[t]      = opening price
Range[t]     = High[t] - Low[t]

Body[t]      = |Close[t] - Open[t]|
BodySize     = max(Close[t], Open[t]) - min(Close[t], Open[t])

WickHigh[t]  = High[t] - max(Close[t], Open[t])  (upper wick)
WickLow[t]   = min(Close[t], Open[t]) - Low[t]   (lower wick)
```

### Rejection Metrics

```
BodyRatio[t] = Body[t] / Range[t]
             Range: 0 to 1
             Low BodyRatio = large wicks relative to body
             High BodyRatio = small wicks (no rejection)

ClosePosition[t] = (Close[t] - Low[t]) / Range[t]
                 Range: 0 to 1
                 0.0 = closed at low (bearish hammer)
                 1.0 = closed at high (bullish hammer)
                 0.5 = closed at midpoint

UpperWickRatio[t] = WickHigh[t] / Range[t]
                  Range: 0 to 1
                  High ratio = long upper wick = rejection at highs
```

### Rejection Trigger Condition

**Shooting Star (rejection at highs, expect SELL_FADE):**
```
BodyRatio[i] < 0.4         → Small body relative to range (wick-heavy)
UpperWickRatio[i] > 0.4    → Long upper wick
ClosePosition[i] < 0.5     → Closed in lower half (rejecting the high)
```

**Hammer (rejection at lows, expect BUY_FADE):**
```
BodyRatio[i] < 0.4         → Small body relative to range
UpperWickRatio[i] < 0.4    → Short upper wick (wick is on bottom)
ClosePosition[i] > 0.5     → Closed in upper half (rejecting the low)
```

---

## Python Implementation

```python
import numpy as np
import pandas as pd

def detect_shooting_star(bp: dict, i: int, cfg: dict = None) -> bool:
    """
    Detect shooting star (rejection at highs): long upper wick, closed low.
    Signals price rejected the high.

    Args:
        bp: bootstrap dict with columns:
            - BodyRatio: Body / Range [0,1]
            - ClosePosition: (Close - Low) / Range [0,1]
            - Range: High - Low
        i: current bar index
        cfg: dict with optional thresholds:
            - max_body_ratio: default 0.4 (body must be < 40% of range)
            - min_close_position: default 0.2 (close in bottom 20%)
            - wick_factor: default 0.4 (wick > 40% of range)

    Returns:
        True if shooting star detected, False otherwise
    """
    if cfg is None:
        cfg = {}

    max_body_ratio = cfg.get("max_body_ratio", 0.4)
    min_close_position = cfg.get("min_close_position", 0.2)
    wick_factor = cfg.get("wick_factor", 0.4)

    if i < 0:
        return False

    # Validate columns
    if not all(col in bp for col in ["BodyRatio", "ClosePosition"]):
        return False

    body_ratio = bp["BodyRatio"]
    close_pos = bp["ClosePosition"]

    # Handle NaN
    if np.isnan(body_ratio[i]) or np.isnan(close_pos[i]):
        return False

    # Shooting star: small body, closed low
    small_body = body_ratio[i] < max_body_ratio
    closed_low = close_pos[i] < min_close_position

    # Upper wick is at least wick_factor of range
    upper_wick_long = (1.0 - close_pos[i]) > wick_factor

    return small_body and closed_low and upper_wick_long


def detect_hammer(bp: dict, i: int, cfg: dict = None) -> bool:
    """
    Detect hammer (rejection at lows): long lower wick, closed high.
    Signals price rejected the low.

    Args:
        bp: bootstrap dict with columns:
            - BodyRatio: Body / Range [0,1]
            - ClosePosition: (Close - Low) / Range [0,1]
        i: current bar index
        cfg: dict with optional thresholds:
            - max_body_ratio: default 0.4
            - max_close_position: default 0.8 (close in top 20%)
            - wick_factor: default 0.4

    Returns:
        True if hammer detected, False otherwise
    """
    if cfg is None:
        cfg = {}

    max_body_ratio = cfg.get("max_body_ratio", 0.4)
    max_close_position = cfg.get("max_close_position", 0.8)
    wick_factor = cfg.get("wick_factor", 0.4)

    if i < 0:
        return False

    # Validate columns
    if not all(col in bp for col in ["BodyRatio", "ClosePosition"]):
        return False

    body_ratio = bp["BodyRatio"]
    close_pos = bp["ClosePosition"]

    # Handle NaN
    if np.isnan(body_ratio[i]) or np.isnan(close_pos[i]):
        return False

    # Hammer: small body, closed high
    small_body = body_ratio[i] < max_body_ratio
    closed_high = close_pos[i] > max_close_position

    # Lower wick is at least wick_factor of range
    lower_wick_long = close_pos[i] > wick_factor

    return small_body and closed_high and lower_wick_long


def detect_candle_rejection_with_direction(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    Detect candle rejection matching trade direction.
    For SELL_FADE, expect shooting star (rejection at highs).
    For BUY_FADE, expect hammer (rejection at lows).
    """
    if cfg is None:
        cfg = {}

    if direction == "SELL_FADE":
        return detect_shooting_star(bp, i, cfg)
    elif direction == "BUY_FADE":
        return detect_hammer(bp, i, cfg)
    else:
        return False


def detect_engulfing_rejection(bp: dict, i: int, direction: str, cfg: dict = None) -> bool:
    """
    More sophisticated: detect engulfing pattern (current bar encompasses prior bar).
    Bullish engulfing: current close > prior open, body encompasses prior body.
    Bearish engulfing: current close < prior open, body encompasses prior body.

    In rejection context: prior bar was the extension, current bar reverses it.
    """
    if cfg is None:
        cfg = {}

    if i < 1:
        return False

    # Validate columns (would need OHLC)
    if not all(col in bp for col in ["Open", "Close", "High", "Low"]):
        return False

    o = bp["Open"]
    c = bp["Close"]
    h = bp["High"]
    l = bp["Low"]

    # Handle NaN
    if any(np.isnan(x[j]) for x in [o, c, h, l] for j in [i-1, i]):
        return False

    # Bullish engulfing: current close > prior open AND current open < prior close
    bullish_engulf = (c[i] > o[i-1]) and (o[i] < c[i-1])

    # Bearish engulfing: current close < prior open AND current open > prior close
    bearish_engulf = (c[i] < o[i-1]) and (o[i] > c[i-1])

    # Direction match
    if direction == "BUY_FADE":
        return bullish_engulf
    elif direction == "SELL_FADE":
        return bearish_engulf
    else:
        return False
```

---

## Thresholds and Interpretation

| BodyRatio | ClosePosition | UpperWickRatio | Pattern | Signal Strength |
|-----------|---------------|----------------|---------|-----------------|
| < 0.2 | < 0.2 | > 0.6 | Strong shooting star | Very Strong |
| 0.2–0.4 | 0.2–0.4 | 0.4–0.6 | Moderate shooting star | Strong |
| 0.4–0.6 | 0.4–0.6 | 0.2–0.4 | Weak rejection | Moderate |
| > 0.6 | — | — | No rejection (trends) | No signal |

### Sensitivity Tuning

```
Conservative (clear rejection only):
  - max_body_ratio: 0.3
  - min_close_position: 0.15 (shoot star)
  - wick_factor: 0.5

Balanced:
  - max_body_ratio: 0.4
  - min_close_position: 0.2
  - wick_factor: 0.4

Aggressive (catch any rejection candle):
  - max_body_ratio: 0.5
  - min_close_position: 0.3
  - wick_factor: 0.3
```

---

## Combining with Setup

**Example: VWAP extension + Candle rejection:**

```python
# Setup: price extended
setup = VWAPDist_SD[i] > 2.0

# Trigger: candle rejection (directional)
trigger = detect_candle_rejection_with_direction(bp, i, "SELL_FADE", cfg)

# Execute when both fire
if setup and trigger:
    return "SELL_FADE"
```

---

## Layer Role

**Dimension 2: Entry Signal — Timing**

Candle rejection is a visual/technical trigger confirming that price extremes are being rejected. Provides pattern-based confirmation.

---

## Column Names

Exact bootstrap columns used:
- `BodyRatio` - Body / Range [0,1] (already implemented)
- `ClosePosition` - (Close - Low) / Range [0,1] (already implemented)
- `Range` - High - Low (already implemented)

Optional (for engulfing):
- `Open`, `Close`, `High`, `Low` (OHLC bars)

---

## References

- Nison, S. (1991) — *Japanese Candlestick Charting Techniques: A Contemporary Guide to Ancient Investment Techniques of the Far East*
- Morris, G. L. (1995) — *Candlestick Charting Explained*
- de Prado, M. L. (2018) — *Advances in Financial Machine Learning*, Chapter 11 (pattern recognition)
