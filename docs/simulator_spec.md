# Simulator Specification

The simulator is dangerous shared code because every strategy result depends on
it. This spec must exist before any strategy code is trusted.

## Scope

The simulator owns mechanical trade accounting only.

It does not own:

- strategy signals
- session timing rules
- filters
- slicer logic
- validation decisions

## Bar Timing

Default assumption:

- signals are evaluated on closed bars
- entries occur on the next bar

The strategy README must state whether a signal is evaluated on bar close and
entered on the next bar. Same-bar fills are not allowed unless a strategy
explicitly documents why they are realistic.

## Entry Fill

Default fill:

- next bar open

Entry slippage is applied to the fill price.

For long entries, positive slippage worsens the entry price.

For short entries, positive slippage worsens the entry price.

## Initial Risk

Every trade must record:

- `EntryPrice`
- `InitialStopPrice`
- `InitialRisk`

`InitialRisk` is the absolute distance between entry and initial stop after
entry slippage is applied.

Invalid trades:

- `InitialRisk <= 0`
- stop on the wrong side of entry
- missing entry or stop price

Invalid trades should be rejected by the strategy or simulator and reported.
They are not normal exits and should not be written as completed rows in
`trades.csv`.

## Stop Execution

For long trades:

- stop is touched when bar low is less than or equal to stop

For short trades:

- stop is touched when bar high is greater than or equal to stop

Default stop fill:

- fill at stop price plus exit slippage when the bar trades through the stop

Gap-through behavior:

- if the next bar opens beyond the stop, fill at the worse of stop price and
  open price
- do not add fixed exit slippage on top of a gap-through open fill unless the
  run config explicitly declares a separate gap-through slippage model
- record `GapThrough = true` for the trade

This avoids assuming impossible stop fills after a gap-through.

## Target Execution

If a strategy uses fixed targets, target touch is evaluated mechanically:

- long target touched when bar high is greater than or equal to target
- short target touched when bar low is less than or equal to target

Default target fill:

- fill at target price adjusted by exit slippage

Gap-through target behavior:

- if the next bar opens beyond the target, fill at the target price
- keep `ExitReason = target`
- record `GapThrough = true`
- do not fill at the more favorable open price unless the strategy explicitly
  documents that execution model
- apply normal target-exit slippage only if the run config says target exits use
  slippage

## Stop And Target Same Bar

If both stop and target are touched in the same bar and no intrabar data exists,
use the conservative assumption:

- stop fills first

Strategies that require a different intrabar model must document the data
source and fill rule before use.

## Trailing Stops

Trailing stop state may update during the trade, but `RealizedR` remains based
on `InitialRisk`.

Optional fields:

- `FinalStopPrice`
- `StopMoved`

Trailing-stop updates must be causal. They may use only information available
through the bar where the update is made.

If a trailing stop is gapped through:

- keep `ExitReason = trailing_stop`
- record `GapThrough = true`
- use the same stop-like gap-through fill logic: worse of active trailing stop
  and open price

## Time Stops

If a max holding period is used, the strategy must define it explicitly.

The simulator can close the trade at the configured time-stop bar using the
declared fill rule, normally the next available close or open depending on the
strategy spec.

## Slippage And Costs

Every run config must state:

- slippage model
- slippage amount
- commission/cost model
- whether costs are applied to entry, exit, or both

Initial implementation should prefer fixed ticks per side.

No result should be reported without declared slippage and cost assumptions.

## Realized R

The simulator should report both gross and net R:

- `RealizedR_Gross`: slippage-adjusted fills before commission
- `RealizedR_Net`: after commission
- `RealizedR`: alias to `RealizedR_Net` for headline metrics

Gross R:

```text
RealizedR_Gross = gross_pnl_points / InitialRisk
```

For long trades:

```text
gross_pnl_points = ExitPrice - EntryPrice
```

For short trades:

```text
gross_pnl_points = EntryPrice - ExitPrice
```

Commission is usually currency, not points. Convert it before computing net R:

```text
commission_points = total_commission_currency / point_value
net_pnl_points = gross_pnl_points - commission_points
RealizedR_Net = net_pnl_points / InitialRisk
RealizedR = RealizedR_Net
```

Slippage is already reflected in `EntryPrice` and `ExitPrice`. Commission is
applied after price-based PnL is calculated.

Run config must declare `point_value` when commission is reported in currency.

## Exit Reason Vocabulary

Allowed `ExitReason` values:

- `target`
- `stop`
- `gap_stop`
- `time_stop`
- `trailing_stop`
- `session_end`
- `end_of_data`

Use `gap_stop` when a stop is filled through the gap-through rule.

Use `time_stop` for an explicit max-holding-period exit.

Use `trailing_stop` when the exit was triggered by a stop that had moved from
its initial placement.

A gapped-through trailing stop still uses `ExitReason = trailing_stop` with
`GapThrough = true`.

Use `session_end` for a forced close at the declared session boundary.

Use `end_of_data` when the data ends before the trade can be fully evaluated.

## Incomplete Trades

Trades that cannot be fully evaluated because the data ends should be marked
with `ExitReason = end_of_data`.

Incomplete trades must not silently enter headline validation metrics.

## Test Requirements

The simulator needs hand-calculated tests for:

- long win
- long stop
- short win
- short stop
- gap-through stop
- gap-through target
- trailing-stop gap-through
- stop and target touched in same bar
- trailing stop with `RealizedR` based on initial risk
- slippage and commission
- incomplete tail trade
