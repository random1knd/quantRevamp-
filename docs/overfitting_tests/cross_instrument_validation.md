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

