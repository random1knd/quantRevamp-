# Candle And Time Context Indicators

Purpose:

- record bar shape and time-of-day context around trades

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `CandleType` | BLOCKED: simple candle classification. | OHLC, rules |
| `BodyRatio` | Body size divided by full range. | OHLC |
| `ClosePosition` | Close location inside bar range. | OHLC |
| `Hour` | Timestamp hour. | `DateTime`, timezone |
| `DayOfWeek` | Timestamp weekday. | `DateTime`, timezone |
| `SessionProgress` | Fraction of declared session elapsed. | timestamp, session definition |
| `BarsSinceOpen` | Bars elapsed since declared session open. | timestamp, session definition |

Blocked items:

- `CandleType`: candle classification rules are not declared by any strategy.

`SessionProgress` returns NaN for bars outside the declared session window.

`BarsSinceOpen` uses the session column count, not elapsed-time inference, so
it is robust to bar gaps.

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
session_progress(datetime_series, session_open_time, session_close_time, timezone)
bars_since_open(datetime_series, session)
hour_of_day(datetime_series, timezone)
day_of_week(datetime_series, timezone)
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
