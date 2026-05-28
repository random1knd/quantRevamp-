# Cross-Instrument Validation Blueprint

Status:

- Cycle B implemented for NQ/ES
- 6E remains blocked until Cycle C session-date support and sanity checks
- coverage-only blueprint demonstration on a rejected workflow child

Purpose:

- show how a frozen child would be tested on ES and 6E without tuning
- produce a reusable blueprint for future positive candidates
- keep cross-instrument logic explicit enough to avoid a new framework or
  hidden registry

## BLOCKER History: 6E Session Model

Do not run 6E cross-instrument validation until its session model is explicitly
implemented and sanity-checked.

Earlier blocker:

- current `prepare_bars` assumes a same-calendar-day session:
  `SessionDate_ET = DateTime_ET.dt.date`
- `SessionMinute_ET` is a minute-of-day offset from one same-day session open
- that is acceptable for NQ/ES RTH-style checks
- it breaks for 6E's near-24h overnight session

For 6E, midnight wrap, session anchoring, and the daily break are strategy
behavior, not accounting constants. Getting them wrong silently corrupts
SessionVWAP, ADX warmup, roll-session detection, and realized R.

## Code Shape

Shared code stays pure:

```text
shared/validation/cross_instrument.py
```

Expected shared function:

```text
cross_instrument_report(instrument_summaries)
```

The shared module compares already-built per-instrument summaries. It must not
import a strategy, load bars, prepare bars, rerun trades, or know about ES/6E
session rules.

The frozen-child reruns live in a child-local runner:

```text
strategies/vwap_zscore_fade/children/adx_q30_workflow_test/cross_instrument_run.py
```

The child runner owns:

- explicit NQ/ES/6E lookup
- input paths
- per-instrument data preparation
- frozen child trade generation
- per-instrument restrictiveness diagnostics
- artifact writing

## Explicit Instrument Lookup Only

Use one small child-local lookup for exactly these keys:

- `NQ`
- `ES`
- `6E`

Do not build a registry, plugin layer, universal instrument framework, or
generic multi-instrument engine. Adding another instrument later requires an
explicit review and a literal new lookup row.

Split lookup fields into two categories.

### Accounting Constants

These are pure accounting and fill-resolution fields. They may change by
instrument without counting as strategy tuning:

| Instrument | Input file | Tick size | Point value | Tick value | Slippage | Commission assumption |
| --- | --- | ---: | ---: | ---: | --- | --- |
| NQ | `data/bars/5min/NQ_all_5min.csv` | `0.25` | `20.0` | `5.00` | `1` tick per side | `5.16` round turn |
| ES | `data/bars/5min/ES_all_5min.csv` | `0.25` | `50.0` | `12.50` | `1` tick per side | `5.16` round turn |
| 6E | `data/bars/5min/6E_all_5min.csv` | `0.00005` | `125000.0` | `6.25` | `1` tick per side | `5.60` round turn |

Notes:

- NQ/ES tick sizes and point values come from CME equity-index contract specs.
- 6E uses CME FX EUR/USD futures (`6E`) contract size `125,000 EUR` and
  outright tick `0.00005`, so one tick is `6.25 USD`.
- Commission uses the same NinjaTrader monthly all-in convention as current NQ:
  NQ/ES monthly all-in `2.58` per side = `5.16` round turn; 6E monthly all-in
  `2.80` per side = `5.60` round turn. Record the source date in run config.

Sources checked on 2026-05-28:

- CME NQ contract specs:
  `https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.contractSpecs.html`
- CME ES contract specs:
  `https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.contractSpecs.html`
- CME FX product guide:
  `https://www.cmegroup.com/markets/fx/fx-product-guide.html`
- NinjaTrader futures commission PDF:
  `https://ninjatrader.com/PDF/ninjatrader_futures_commissions.pdf`

### Session Structure

These fields change how bars become strategy context. They are not simple
accounting constants and must be tested:

| Instrument | Source timezone | Session model | Session open ET | Session end ET | RTH window used for this child |
| --- | --- | --- | --- | --- | --- |
| NQ | `UTC` | same-day RTH | `09:30` | `16:00` force-flat | `09:30` through `15:55` bar open |
| ES | `UTC` | same-day RTH | `09:30` | `16:00` force-flat | `09:30` through `15:55` bar open |
| 6E | `UTC` | overnight Globex-style session anchored to next ET date | `18:00` previous ET day | `17:00` ET close; no `17:00` bar expected in normal data | full session from `18:00` through `16:55` bar open |

Behavioral thresholds do not move:

- `ENTRY_Z_THRESHOLD = 2.0`
- `Z_WINDOW = 20`
- `SIGNAL_MIN_BARS = 20`
- `ATR_WINDOW = 14`
- `ADX_WINDOW = 14`
- `ADX_FILTER_THRESHOLD = 19.26665446628932`
- `STOP_ATR_MULTIPLE = 1.5`
- `TIME_STOP_MINUTES = 60`
- `NO_ENTRY_BEFORE_SESSION_MINUTE = 60`
- `NO_ENTRY_AT_OR_AFTER_SESSION_MINUTE = 360`

For ES these timing gates remain a near-literal NQ RTH transfer. For 6E they
are intentionally frozen and therefore mean "no entries during the first hour
after the 18:00 ET session open, and no entries at/after session minute 360
(00:00 ET)." That is not tuned for FX; it is part of the blueprint stress test.

6E artifact caveat:

- the literal frozen gates make 6E trade only an arbitrary early-session window:
  roughly `19:00 ET` through `00:00 ET`, with force-flat around `00:25 ET`
- any 6E result from this workflow child primarily reflects that frozen
  literal-gate transfer, not whether the VWAP-fade thesis transfers to EUR/USD
- the 6E R number is therefore not FX-thesis evidence
- a real FX candidate must decide whether timing gates are session-relative
  before discovery; changing them after seeing 6E results would be tuning

## Data-Grounded 6E Session Decision

Method 7 data-shape scan of `data/bars/5min/6E_all_5min.csv`:

- rows: `979807`
- raw timestamp range: `2011-12-01 00:00:00` through
  `2025-12-24 18:40:00`
- raw timestamps have no timezone marker; consistent with repo practice, they
  are interpreted as `UTC`
- timestamps are monotonic and have zero duplicates
- when converted to `America/New_York`, the dominant large-gap pair is
  `16:55 -> 18:00` with `3362` occurrences across the full file
- in the validation-like span `2018-04-18` through `2023-12-01`, the same
  `16:55 -> 18:00` gap appears `1379` times
- assigning sessions as `(DateTime_ET + 6 hours).date` creates an 18:00 ET
  anchored session
- in that validation-like span, this produces `1456` proposed sessions:
  `1226` sessions have exactly `276` bars, first minute `0`, last minute
  `1375`
- sample complete sessions:
  `2018-04-19`: `2018-04-18 18:00 ET` through
  `2018-04-19 16:55 ET`
- early-close examples exist with last minute `1135` (`12:55 ET`), including
  `2018-05-28`, `2018-07-04`, and `2018-11-22`
- one observed anomalous validation-era session has `277` bars and a
  `17:00 ET` final timestamp (`2018-05-14`); the 6E runner must report this,
  not silently force it into a normal session shape

Decision for 6E:

- source timestamps are localized as `UTC` and converted to
  `America/New_York`
- `SessionDate_ET` is the ET date of the session close / trade date:
  `(DateTime_ET + 6 hours).date`
- `SessionMinute_ET = (minute_of_day_ET - 18:00) mod 1440`
- normal session starts at `18:00 ET` (`SessionMinute_ET = 0`)
- normal tradable last 5-minute bar open is `16:55 ET`
  (`SessionMinute_ET = 1375`)
- daily break is the missing interval after `16:55 ET` until `18:00 ET`
- SessionVWAP resets at `SessionMinute_ET = 0`
- ADX and ATR warmup are session-local exactly as for NQ, but over the 6E
  overnight session
- contract roll detection is by this new `SessionDate_ET`; multiple contracts
  in one 18:00-to-17:00 ET session are invalid unless explicitly handled later

## Required Data-Layer Change For 6E

Do not mutate current same-day behavior for NQ/ES.

Add a narrow data-layer option, not a framework:

- existing same-day mode remains default:
  `SessionDate_ET = DateTime_ET.dt.date`
- add an explicit session-date mode for 6E:
  `session_date_policy = "offset_after_session_open"`
- required 6E inputs:
  - `session_open = "18:00"`
  - `session_date_offset_hours = 6`
  - `last_session_bar_open_minute = 1375`
  - `daily_break_expected = "16:55 -> 18:00 ET"`

The same `prepare_bars` tests must prove:

- NQ/ES outputs are bit-identical under default mode
- 6E assigns pre-midnight and post-midnight bars to the same session
- 6E session minutes are monotonic inside each session even across midnight
- 6E `BarGapFromPrevious` marks missing bars inside a session but does not
  create a false gap across the daily break before the next session open

## Mandatory 6E Sanity Checks

A 6E run without these checks is untrusted even if tests pass:

- per-session bar-count distribution:
  - count of normal `276`-bar sessions
  - early-close buckets such as `228` bars / `12:55 ET` last bar
  - anomalous sessions, including any `277`-bar session
- session-boundary sample table:
  - first timestamp, last timestamp, first minute, last minute for at least the
    first 5, last 5, and all anomalous sessions
- VWAP reset verification:
  - first bar of every session has session VWAP equal to its own typical price
    under the chosen VWAP formula
  - no VWAP carry across the `16:55 -> 18:00 ET` break
- ADX/ATR warmup coverage:
  - per-session count of non-null ADX and ATR
  - count of sessions with no eligible post-warmup bars
- roll/session integrity:
  - no session contains multiple contracts unless explicitly allowed later
  - roll-session flag counts reported
- R-range sanity check:
  - min/max/percentiles for initial risk, gross R, net R
  - count of trades outside a predeclared extreme-R review threshold
  - no zero-risk or negative-risk trades
- restrictiveness summary:
  - ADX kept/rejected/missing counts using the literal frozen NQ threshold

## ES Path

Build ES before 6E.

ES is the behavior-neutral transfer:

- same `UTC -> America/New_York` source handling as NQ
- same RTH session model as NQ
- same behavioral thresholds and timing gates
- only accounting constants and input file change

Cycle B must also rerun NQ through the new explicit lookup and prove the NQ
child trades are bit-identical to the current validation baseline:

- trade count
- `completed_non_gap` count
- mean R
- trade CSV hash or row-for-row equality

If NQ changes, stop before running ES.

## Threshold And Restrictiveness Reporting

Scale-free thresholds transfer as literals:

- z-score threshold
- ATR stop multiple
- time stop
- warmup counts

The raw ADX threshold also stays literal:

- `ADX <= 19.26665446628932`

Every cross-instrument report must show:

- ADX decision-point count
- ADX kept count
- ADX rejected count
- ADX missing count
- ADX kept fraction
- ADX missing fraction

A failed transfer can mean the raw ADX threshold did not transfer cleanly, not
necessarily that the VWAP-fade thesis failed. Re-derived target-instrument
quantiles are diagnostics only unless a future strategy explicitly trades a
causal percentile-rank feature before discovery.

## Report Shape

The child-local runner should write:

- `cross_instrument_report.json`
- `cross_instrument_report.csv`
- `run_config.json`
- for 6E only: `session_sanity_report.json` and `.csv`

Each instrument summary should include:

- instrument
- data start/end
- session start/end
- split boundaries and session counts
- trade count
- all completed count
- completed_non_gap count
- incomplete count
- gap-excluded count
- mean R
- total R
- win rate
- max drawdown R
- minimum trade-count tier
- ADX restrictiveness summary
- accounting constants actually used
- session model actually used

Overall report labels:

- `coverage_only`
- `blueprint_demonstration`
- `rejected_child_not_edge_evidence`
- `no_instrument_selection_allowed`

Possible human-readable labels:

- `ROBUST`
- `PROMISING`
- `INSTRUMENT_SPECIFIC`
- `MIXED`
- `NEGATIVE`

These labels are reporting aids only. They cannot promote this rejected child
and must not be used to pick the best instrument.

## Implementation Sequence

Cycle B:

- completed: add explicit child-local NQ/ES/6E lookup
- completed: rerun NQ through lookup and prove bit-identical behavior
- completed: run ES
- completed: write coverage-only cross-instrument report

Cycle C:

- add narrow 6E session-date support in the data layer
- add mandatory 6E sanity checks
- run 6E only after sanity checks pass

Cycle D:

- run final 20% capstone once
- label coverage-only because this child is rejected
- predeclare partial-tail handling for `2026-03-06`

Deferred until a real positive candidate:

- block bootstrap engine
- block permutation engine
- promotion aggregator

## Cycle B Result

Artifact:

```text
data/results/vwap_zscore_fade/children/adx_q30_workflow_test/cross_instrument_es_20260528T134418Z
```

NQ lookup proof:

- bit-identical: `true`
- trade count: baseline `1820`, lookup `1820`
- completed_non_gap count: baseline `1810`, lookup `1810`
- mean R: baseline `-0.13961137318663386`, lookup
  `-0.13961137318663386`
- trade-row SHA-256:
  `d935f1a27b144054403860c53eafe12985250e49f365b83683c2949f8809d7a5`

ES same-day RTH transfer:

- trade count: `2375`
- completed_non_gap count: `2374`
- mean R: `-0.2708235375893883`
- total R: `-642.9350782372079`
- win rate: `0.37573715248525696`
- ADX kept fraction: `0.24325736464968153`

Interpretation:

- ES did not rescue the rejected workflow child
- this is still coverage-only context and cannot select an instrument or
  promote an edge
- 6E was not run
