# VWAP Z-Score Fade Parent Strategy

Status: thesis locked for v0 implementation.

This is the first parent strategy for the repo. It is intentionally narrow:
NQ, 5-minute bars, regular US equity-index trading hours, and one explicit
mean-reversion thesis.

The strategy must be implemented directly in this folder. It must not depend on
a strategy registry, universal bootstrap layer, or slicer-discovered filter.

## Thesis

NQ often mean-reverts toward intraday fair value after becoming stretched away
from regular-session VWAP. The parent strategy fades statistically large
deviations from session VWAP after the opening period has passed.

The parent strategy does not use any post-trade slicing result as a filter.
Slicing may later create one explicit child strategy, but that child must be
separate code.

## Primary Backtest Scope

- instrument: NQ
- timeframe: 5-minute bars
- primary session: regular trading hours for US equity-index futures
- strategy timezone: America/New_York
- source timestamp timezone: UTC
- source bar timestamp convention: bar open
- first implementation instrument only: NQ
- ES and 6E are not part of the v0 primary backtest

## Data Assumptions

Required source columns:

- `DateTime`
- `Open`
- `High`
- `Low`
- `Close`
- `Volume`
- `BidVolume`
- `AskVolume`
- `Contract`

Derived data fields expected before strategy logic:

- `DateTime_UTC`
- `DateTime_ET`
- `SessionDate_ET`
- `MinuteOfDay_ET`
- `SessionMinute_ET`
- `Contract`
- `IsFirstSessionAfterContractChange`

`DateTime_ET` must be timezone-aware. Do not use naive ET timestamps.

`SessionMinute_ET` is minutes since the declared RTH open. It is 0 at 09:30 ET.

The raw CSVs combine quarterly contract labels and are not assumed to be
back-adjusted. The v0 backtest excludes the first ET session after `Contract`
changes from the previous trading day.

The loader may mark roll sessions, but it must not silently drop them. The run
configuration must explicitly state whether roll sessions are excluded.

## Session Rules

- RTH open: 09:30 ET
- no-entry gate: 09:30 ET through 10:30 ET
- no partial z-score warmup
- 20 full RTH 5-minute bars are required before any signal
- first possible entry: 11:10 ET bar open
- no new entry fills at or after 15:30 ET
- force flat at the 16:00 ET RTH close

For 5-minute bar-open timestamps, the 15:55 ET bar represents 15:55-16:00 ET.
Forced session exit occurs at the close of that bar.

## Indicator Definitions

### Session VWAP

Session VWAP resets at 09:30 ET.

Because the data is candle data rather than tick-level trade data, v0 uses this
bar approximation:

```text
TypicalPrice = (High + Low + Close) / 3
SessionVWAP = cumulative(TypicalPrice * Volume) / cumulative(Volume)
```

VWAP is computed only from current-session RTH bars.

### VWAP Deviation Z-Score

```text
VWAPDeviation = Close - SessionVWAP
EntryZ = VWAPDeviation / rolling_std(VWAPDeviation, 20)
```

Rules:

- window: 20 completed RTH 5-minute bars
- minimum bars: 20
- no partial-window z-score
- session-reset
- the just-closed signal bar is included in the rolling standard deviation
- no additional rolling mean subtraction; VWAP is the zero reference
- if rolling standard deviation is zero or missing, no signal is allowed

### ATR

ATR uses a 14-bar rolling average of true range on RTH bars.

```text
TrueRange = max(
  High - Low,
  abs(High - previous Close),
  abs(Low - previous Close)
)
```

Rules:

- window: 14 completed RTH 5-minute bars
- session-reset
- for the first RTH bar of a session, true range is `High - Low`
- the stop uses ATR from the closed signal bar

### Volume Z-Score

`EntryVolumeZ` is context only. It does not affect parent strategy trades.

```text
EntryVolumeZ = (Volume - rolling_mean(Volume, 20)) / rolling_std(Volume, 20)
```

Rules:

- window: 20 completed RTH 5-minute bars
- minimum bars: 20
- session-reset
- the just-closed signal bar is included

## Entry Rules

Signals are evaluated only after a 5-minute signal bar has closed.

Entry fills occur on the next bar open.

Long entry:

```text
EntryZ <= -2.0
```

Short entry:

```text
EntryZ >= 2.0
```

Additional entry requirements:

- signal bar must be an RTH bar
- 20-bar z-score warmup must be complete
- entry fill time must be at least 10:30 ET
- entry fill time must be before 15:30 ET
- signal session must not be the first ET session after a contract change when
  the run config excludes roll sessions
- only one open trade at a time

## Stop, Target, And Exit Rules

Initial stop:

```text
LongStop = EntryPrice - 1.5 * SignalATR
ShortStop = EntryPrice + 1.5 * SignalATR
```

`SignalATR` is the ATR value from the closed signal bar.

Target:

- target is live/tracking session VWAP, not VWAP frozen at entry
- for exit evaluation on bar T, `SessionVWAP_T` includes bar T
- long target touched when `bar_T.High >= SessionVWAP_T`
- short target touched when `bar_T.Low <= SessionVWAP_T`

Known behavior:

- tracking VWAP can drift away from price after entry during a trend
- the 12-bar time stop is the explicit backstop for this behavior

Time stop:

- maximum hold: 12 bars / 60 minutes
- if neither stop nor target is touched first, exit at the close of the 12th
  held bar

Session exit:

- any open trade is forced flat at the 16:00 ET RTH close
- with 5-minute bar-open timestamps, this means the close of the 15:55 ET bar

Same-bar conflict rule:

- if stop and target are both touched in the same bar, stop fills first
- this conservative rule also applies to the entry bar

## Fill And Cost Assumptions

Default entry fill:

- next bar open

Default slippage:

- 1 tick per side

Current v0 implementation note:

- `strategy.py` temporarily performs mechanical fills, slippage, and
  realized-R calculation until `shared/execution/simulator.py` is extracted
  behind focused simulator-spec tests. At that point, the slippage model must
  move from parent params into explicit run configuration.

NQ contract values:

- tick size: 0.25
- point value: 20 USD per point
- tick value: 5 USD per tick

Commission:

- commission may be 0 only for smoke-test runs
- any run with commission set to 0 must be labeled as a smoke test in
  `run_config.json`
- real comparison runs must declare a nonzero commission assumption

## Required Trade Artifacts

Every completed trade should record at least:

- `EntryTime`
- `ExitTime`
- `Side`
- `EntryPrice`
- `ExitPrice`
- `InitialStopPrice`
- `InitialRisk`
- `RealizedR_Gross`
- `RealizedR_Net`
- `RealizedR`
- `ExitReason`
- `BarsHeld`
- `SignalTime`
- `SignalATR`
- `EntryZ`
- `EntrySessionVWAP`
- `EntryVWAPDeviation`
- `Contract`
- `CommissionIsSmokeTest`

`RealizedR` is based on initial risk, not a later trailing or target distance.

## Research Context To Record

These fields are for post-trade slicing only. They must not affect parent
strategy entries, exits, stops, or timing.

- `EntryHour_ET`
- `SessionMinute_ET`
- `EntryZ`
- `EntryATR`
- `EntrySessionVWAP`
- `EntryVWAPDeviation`
- `EntryVolume`
- `EntryVolumeZ`
- `EntryDelta`
- `EntryDeltaPct`

Delta definitions:

```text
EntryDelta = AskVolume - BidVolume
EntryDeltaPct = EntryDelta / Volume
```

If volume is zero, `EntryDeltaPct` is missing.

## Explicit Non-Goals For Parent v0

- no ES primary backtest
- no 6E primary backtest
- no cross-instrument validation in the first runnable version
- no slicer-discovered filter in parent logic
- no global setup / trigger / filter registry
- no universal indicator bootstrap
- no automatic child strategy creation
- no parameter sweep before the parent run is stable

## First Child Strategy Rule

If slicing proposes a filter, only one candidate may be approved from the first
discovery run. The approved filter must become explicit child strategy code
under:

```text
strategies/vwap_zscore_fade/children/<child_name>/
```

The parent strategy must remain unchanged by slicing.
