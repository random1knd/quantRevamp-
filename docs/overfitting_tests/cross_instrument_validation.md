# Cross-Instrument Validation

Purpose:

- check whether a frozen child strategy transfers to other instruments

## Inputs

- frozen child strategy
- source validation report
- target instrument bars
- matching split policy

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
- compare realized-R, trade count, drawdown, and diagnostics

## Possible Labels

- `ROBUST`
- `PROMISING`
- `INSTRUMENT_SPECIFIC`
- `MIXED`
- `NEGATIVE`

Labels are reporting aids. Exact thresholds are not set yet.

---

## Audit Note — Claude (2026-05-23, pending Codex review)

"Do not tune per instrument" must not be read as "keep NQ constants." `params.py`
hardcodes NQ microstructure (`NQ_TICK_SIZE`, `NQ_POINT_VALUE`, `NQ_TICK_VALUE`,
slippage in NQ ticks). On ES/6E these MUST change or `RealizedR` and
commission-in-points are wrong. Instrument constants are not "tuning." Suggested
build (for when this deferred test is implemented):

- Distinguish FROZEN strategy parameters (entry z, ATR multiple, thresholds — must
  not change) from INSTRUMENT CONSTANTS (tick size, point value, tick value,
  slippage unit — must adapt per instrument).
- Introduce an instrument-constant lookup before cross-instrument runs; state in
  this doc that swapping constants is not "tuning."

**Codex — agree / disagree / counter?**

