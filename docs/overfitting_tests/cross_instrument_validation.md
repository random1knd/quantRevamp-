# Cross-Instrument Validation

## BLOCKER: 6E Session Model Not Decided

Do not run 6E cross-instrument validation until its session model is explicitly
decided.

Current `prepare_bars` and strategy params assume a same-calendar-day session:
`SessionDate_ET = DateTime_ET.dt.date`, and `SessionMinute_ET` is a simple
minute-of-day offset from the declared `09:30` session open. That is acceptable
for NQ/ES RTH-style checks, but it breaks for 6E's near-24h/overnight session.

For 6E, midnight wrap, session anchoring, and the daily break are strategy
behavior, not accounting constants. Getting them wrong silently corrupts
SessionVWAP, ADX warmup, roll-session detection, and realized R. Cross-instrument
work may add an explicit child-local market lookup later, but 6E must remain
blocked until this session behavior is specified and tested.

Purpose:

- check whether a frozen child strategy transfers to other instruments

## Inputs

- frozen child strategy
- source validation report
- target instrument bars
- matching split policy
- target instrument constants

## Code Shape

```text
shared/validation/cross_instrument.py
```

Expected function:

```text
cross_instrument_validate(strategy, source_result, target_bars, split_policy)
```

## Approach

- run the same frozen child on target instruments
- do not tune per instrument
- adapt instrument constants through an explicit lookup
- compare realized-R, trade count, drawdown, and diagnostics

Frozen strategy parameters include entry z, ATR multiple, filter thresholds, and
other behavioral thresholds. They must not change for a target instrument.

Instrument constants include tick size, point value, tick value, and slippage
unit. Swapping these constants for the target market is required accounting, not
tuning.

Threshold caveat:

- scale-free thresholds, such as z-score levels and ATR multiples, transfer as
  literal values
- distribution-derived raw thresholds, such as an ADX level selected from an NQ
  discovery quantile, also stay frozen for the candidate result
- the report should show how restrictive that raw threshold is on each target
  instrument, because a failed transfer can mean the raw threshold did not
  transfer, not necessarily that the thesis failed
- re-derived target-instrument quantiles are diagnostics only unless a future
  strategy explicitly trades a causal percentile-rank feature before discovery

## Possible Labels

- `ROBUST`
- `PROMISING`
- `INSTRUMENT_SPECIFIC`
- `MIXED`
- `NEGATIVE`

Labels are reporting aids. Exact thresholds are not set yet.
