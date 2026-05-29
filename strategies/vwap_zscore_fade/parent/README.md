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

On early-close market days, such as the day before Thanksgiving or Christmas
Eve, the session ends at whatever bar the source data provides. The force-flat
rule applies at the last available same-session bar. No exchange calendar is
consulted. This is intentional: early-close handling is implicit in the data,
not in strategy code.

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

`SignalVolumeZ` is context only. It does not affect parent strategy trades.

```text
SignalVolumeZ = (Volume - rolling_mean(Volume, 20)) / rolling_std(Volume, 20)
```

Rules:

- window: 20 completed RTH 5-minute bars
- minimum bars: 20
- session-reset
- the just-closed signal bar is included

## Entry Rules

Signals are evaluated only after a 5-minute signal bar has closed.

Entry fills occur on the next bar open.

After a trade closes, the exit bar is not eligible as a signal bar. The scanner
resumes at the bar following the exit bar.

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

- target is fixed at the closed signal bar's session VWAP
- long target touched when `bar_T.High >= SignalSessionVWAP`
- short target touched when `bar_T.Low <= SignalSessionVWAP`

Known behavior:

- the fixed target removes current-bar VWAP look-ahead on OHLC bars
- the 60-minute time stop is the explicit backstop when price does not revert

Time stop:

- maximum hold: 60 elapsed minutes
- if neither stop nor target is touched first, exit at the close of the first
  available bar whose close is at least 60 minutes after entry

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

Stop and target prices are rounded to the NQ tick size with a conservative
order-side policy before guard checks and fills. Long stops round up, short
stops round down, long targets round up, and short targets round down. This
keeps stops no farther from entry than the raw modeled stop and does not claim
a target before the raw signal-bar VWAP has reached a valid exchange tick.

Acknowledged side effect: because stops always round toward entry, `InitialRisk`
is rounded down by up to one tick (0.25 pt). Since `RealizedR` divides by
`InitialRisk`, this inflates the magnitude of every R (winners and losers
alike). The mean effect is small, but the tail is larger when ATR/risk is small:
measured on `completed_non_gap`, discovery mean/p95/max denominator inflation is
2.06% / 5.36% / 17.86%, and validation-parent is 0.72% / 2.32% / 8.21%.
An unrounded-denominator estimate does not rescue the edge: discovery mean R
moves from -0.17771 to -0.17363, and validation-parent from -0.11476 to
-0.11365. Any future positive edge claim should report this full distribution
rather than a flat 1-2% shorthand. The fill-realism benefit of never modeling a
stop wider than intended is judged to outweigh it for v0.

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
- `SignalZ`
- `SignalSessionVWAP`
- `SignalVWAPDeviation`
- `Contract`
- `CommissionIsSmokeTest`

`RealizedR` is based on initial risk, not a later trailing or target distance.

`ExitTime` records the fill timestamp. For `time_stop`, `session_end`, and
`end_of_data` exits, that is the close of the exit bar. For stop, target, and
gap-stop exits on OHLC bars, it is the exit bar's open timestamp because the
exact intrabar fill time is not observable.

## Research Context To Record

These fields are closed signal-bar values joined by `SignalTime` for
post-trade slicing only. They must not affect parent strategy entries, exits,
stops, or timing.

- `SignalVolumeZ`
- `SignalDelta`
- `SignalDeltaPct`
- `SignalBodyRatio`
- `SignalClosePosition`
- `SignalVWAPDist`
- `SignalVWAPDistATR`
- `SignalRealizedVol`
- `SignalVolRatio`
- `SignalVolRobustZ`
- `SignalATRPctile`
- `SignalCumDelta`
- `SignalDeltaROC`
- `SignalOFI`
- `SignalVPIN`
- `SignalKyleLambda`
- `SignalKyleLambdaPctile`
- `SignalAutoCorr`
- `SignalVarRatio`
- `SignalADX`
- `SignalEfficiencyRatio`
- `SignalBarsSinceOpen`

### Research Questions

| Signal* Column | Research Question |
| --- | --- |
| `SignalVolumeZ` | Does signal-bar volume context help explain when fades work better or worse? |
| `SignalDelta` | Does same-bar aggressive buying or selling pressure relate to fade outcomes? |
| `SignalDeltaPct` | Does normalized same-bar order-flow imbalance relate to fade outcomes independent of raw volume? |
| `SignalBodyRatio` | Does candle body size relative to range separate exhaustion from continuation behavior? |
| `SignalClosePosition` | Does the signal bar's close location inside its range identify stronger or weaker fade setups? |
| `SignalVWAPDist` | Does absolute distance from session VWAP explain realized R after entry? |
| `SignalVWAPDistATR` | Does ATR-normalized distance from session VWAP explain realized R after entry? |
| `SignalRealizedVol` | Does recent realized volatility regime relate to stop, target, or time-stop outcomes? |
| `SignalVolRatio` | Does current volume relative to recent volume identify different fade behavior? |
| `SignalVolRobustZ` | Does robust volume surprise relate to fade quality when ordinary volume z-score is noisy? |
| `SignalATRPctile` | Does the intraday ATR percentile describe regimes where this mean-reversion thesis is more or less reliable? |
| `SignalCumDelta` | Does cumulative same-session order-flow pressure help explain fade outcomes? |
| `SignalDeltaROC` | Does the recent rate of change in same-session delta relate to continuation risk after the signal? |
| `SignalOFI` | Does approximate order-flow imbalance provide useful context for fade outcomes? |
| `SignalVPIN` | Does recent volume-synchronized imbalance describe adverse-selection conditions for the fade? |
| `SignalKyleLambda` | Does estimated price impact relate to whether the stretched move reverts or continues? |
| `SignalKyleLambdaPctile` | Does the percentile of estimated price impact identify distinct liquidity regimes? |
| `SignalAutoCorr` | Does recent return autocorrelation describe trend persistence around fade signals? |
| `SignalVarRatio` | Does recent variance-ratio context distinguish mean-reverting from trending behavior? |
| `SignalADX` | Does intraday (session-scoped) trend strength relate to fade outcomes? |
| `SignalEfficiencyRatio` | Does directional efficiency of recent price movement relate to fade reliability? |
| `SignalBarsSinceOpen` | Does time elapsed since the RTH open explain differences in fade outcomes? |

Delta definitions:

```text
SignalDelta = AskVolume - BidVolume
SignalDeltaPct = SignalDelta / Volume
```

If volume is zero, `SignalDeltaPct` is missing.

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
