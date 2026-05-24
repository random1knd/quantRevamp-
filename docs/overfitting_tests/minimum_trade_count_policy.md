# Minimum Trade-Count Policy

Purpose:

- warn when a result has too few trades to trust

This v0 document defines fixed trade-count buckets. It is not the
Bailey/Lopez de Prado Minimum Backtest Length statistic.

## Inputs

- completed validation trade count

## Code Shape

```text
shared/validation/realized_r.py
```

Expected function:

```text
minimum_trade_count_policy(completed_trade_count)
```

## Output

- actual trade count
- low-sample status
- estimated required count, if a later statistical rule is added

## Initial Policy

Use this starting policy before the first strategy run:

- fewer than 30 validation trades: insufficient evidence
- 30 to 99 validation trades: low-sample / experimental
- 100 or more validation trades: normal interpretation allowed

These thresholds can be revised only before looking at a specific candidate's
validation result. Other docs may reference these buckets, but this file owns
the thresholds.

## Rule

Low sample size must not silently pass only because a child beats the parent.
