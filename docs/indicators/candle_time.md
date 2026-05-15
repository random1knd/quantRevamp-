# Candle And Time Context Indicators

Purpose:

- record bar shape and time-of-day context around trades

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `CandleType` | Simple candle classification. | OHLC, rules |
| `BodyRatio` | Body size divided by full range. | OHLC |
| `ClosePosition` | Close location inside bar range. | OHLC |
| `Hour` | Timestamp hour. | `DateTime`, timezone |
| `DayOfWeek` | Timestamp weekday. | `DateTime`, timezone |
| `SessionProgress` | Fraction of declared session elapsed. | timestamp, session definition |
| `BarsSinceOpen` | Bars elapsed since declared session open. | timestamp, session definition |

## Implementation Approach

Shared math can live in:

```text
shared/indicators/candle.py
shared/indicators/time_context.py
```

Expected functions:

```text
body_ratio(open, high, low, close)
close_position(high, low, close)
candle_type(open, high, low, close, rules)
time_context(datetimes, session_open, session_close, timezone)
bars_since_open(datetimes, session_open, timezone)
```

## Parameter Decisions

Each strategy must state:

- timezone
- session open and close
- candle classification rules, if `CandleType` is used

## Causality

Current candle shape is known only after the bar closes. Strategies must state
whether signals are evaluated on closed bars and entered on the next bar.

Time context itself is deterministic and does not use future market data.

## Test Plan

- zero-range candle
- known close-position examples
- session boundary examples
- timezone conversion examples

