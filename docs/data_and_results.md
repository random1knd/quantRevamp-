# Data And Results

This doc defines the first simple data/result contract so the new repo does not
need a heavy workflow system.

Runtime data should live under the repo-root `data/` folder described in
`repo_structure.md`. Do not build loaders around `docs/` paths or absolute
local paths.

Raw market data is not versioned in git. Reproducible runs must identify the
input files by repo-relative path, byte size, and SHA-256 content hash.

If a run reads data outside the repo-root `data/` folder, mark that run as
non-reproducible. Absolute local paths are not portable decision evidence.

## Bar Data

Required bar columns for current repo loaders:

- `DateTime`
- `Open`
- `High`
- `Low`
- `Close`
- `Volume`
- `BidVolume`
- `AskVolume`
- `Contract`

This repo currently targets futures bar data where order-flow volume fields and
explicit contract labels are baseline inputs. A non-futures data source needs a
separate loader or an explicit revision to this contract.

Optional bar columns:

- `Delta`
- `NumTrades`

Required source-data decisions before building loaders:

- timestamp timezone and whether `DateTime` marks bar open or bar close
- exchange/session calendar used for RTH and ETH filters
- continuous-futures roll policy, if files combine multiple contracts
- whether prices are raw, back-adjusted, ratio-adjusted, or otherwise adjusted
- how duplicate, missing, partial, or out-of-order bars are handled

Optional session columns may be derived by a strategy or shared data helper,
but session assumptions must be explicit in the strategy README.

If `Delta` is absent but `BidVolume` and `AskVolume` are present, any computed
delta definition must be stated explicitly, normally `AskVolume - BidVolume`.

## Splits

Use chronological splits:

- `train` for discovery
- `validation` for narrowing and holdout checks
- `test` for final confirmation only

The split boundary controls which trades count for evaluation. It is not the
same thing as an intraday session filter.

The 30/50/20 split basis is chronological trading sessions, not raw bar count.
Do not split inside a trading session.

## Run Artifacts

Each run should write one directory:

```text
data/results/<strategy>/<run_id>/
  trades.csv
  context_trades.csv
  run_config.json
  summary.json
```

Optional:

```text
  slices.csv
  validation.json
  charts/
```

## Trades CSV

Minimum trade columns:

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

Optional stop-management columns:

- `FinalStopPrice`
- `StopMoved`

Optional diagnostic columns:

- `GapThrough`

`RealizedR_Gross`, `RealizedR_Net`, and `RealizedR` are calculated from
`InitialRisk`, not from a later trailing stop position. `RealizedR` is the net
headline value and should equal `RealizedR_Net`.

Allowed `ExitReason` values are defined in `simulator_spec.md`.

`GapThrough` applies to any exit where the bar opened beyond the active exit
level, including stops, trailing stops, and targets.

Recommended context columns:

- strategy-specific signal values
- strategy-specific trigger values
- chosen regime or volatility context
- hour or session phase

Do not force every strategy to record every possible indicator.

## Context Trades CSV

`context_trades.csv` is for slicing. It contains all written trades plus
recorded research indicators; do not drop `end_of_data` rows or gap-crossing
rows while writing this artifact.

These context columns must not affect the parent strategy's trade decisions.
They are used only after the run is complete.

The slicer is responsible for applying the campaign's declared input
population. The current default headline/slicer population is
`completed_non_gap`: rows where `ExitReason != end_of_data` and
`HoldCrossesGap == false`.

## Summary JSON

Minimum summary fields:

- strategy name
- instrument
- timeframe
- split
- data start and end
- declared session open
- post-open no-trade minutes
- parameter snapshot
- trade count
- mean `RealizedR`
- win rate
- max drawdown in R
- 1R through 10R diagnostics when available
- incomplete trade count
- slippage and cost assumptions
- standalone child credibility status, when validating a child
- parent comparison status, when validating a child

Headline performance fields (`mean_realized_r`, `win_rate`,
`max_drawdown_r`, and `r_multiple_diagnostics`) are computed from
`completed_non_gap` trades only: completed trades excluding
`ExitReason = end_of_data` and rows where `HoldCrossesGap == true`.
`trade_count` still counts all written trades, and `incomplete_trade_count`
reports incomplete rows.

When a summary also reports `all_completed_*` fields, those fields use all
completed trades including gap-crossing holds. `all_completed_max_drawdown_r`
uses the same drawdown definition as the headline field: max peak-to-trough of
cumulative `RealizedR` in chronological trade order.

## Run Config JSON

Minimum run config fields:

- campaign id
- strategy name
- strategy version
- run type
- instrument
- timeframe
- split
- data start and end
- declared session open
- post-open no-trade minutes
- parameter snapshot
- random seed
- code snapshot or git commit/tag, when available
- `input_data_sha256`
- `input_data_bytes`
- slippage model
- slippage amount
- commission/cost model
- point value, when commission is currency-denominated

`random seed` is required so stochastic validation reports, such as Monte Carlo
permutation or equity-curve resampling, can be reproduced.

`code snapshot or git commit/tag` is required before using a run as decision
evidence.

`input_data_sha256` is stored as:

```json
{
  "data/bars/5min/NQ_all_5min.csv": "sha256-hex-digest"
}
```

`input_data_bytes` is stored as:

```json
{
  "data/bars/5min/NQ_all_5min.csv": 54557044
}
```

The map keys are repo-relative paths. A single-file run has one entry. A
multi-file run records every input file it reads.

## Filter Candidate Artifact

When slicing discovers a filter, write a separate candidate artifact instead of
editing strategy code.

Minimum fields:

- parent strategy
- campaign id
- discovery run id
- selected filter rule
- selection metric
- slicer input population
- searched columns
- searched rule count
- per-candidate selection-metric distribution
- multiple-testing adjustment report
- before-filter and after-filter trade count
- realized-R summary
- 1R through 10R diagnostics when available
- approval status

`searched rule count` and the per-candidate selection-metric distribution are
mandatory. If the slicer cannot report them, the filter candidate artifact is
incomplete and cannot support DSR or full-search permutation validation.
