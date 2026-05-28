# Time Stability

Purpose:

- report whether validation performance is concentrated in one calendar period

Status:

- coverage-only overfitting workflow check for the negative workflow-test child
- secondary to walk-forward reruns
- report-only, no pass/fail, no period selection

## Code Shape

Shared code stays pure:

```text
shared/validation/time_stability.py
```

Expected shared function:

```text
time_stability_report(trades, granularities, sparse_trade_floor)
```

The shared module takes already-judged trade records with entry timestamp and
RealizedR. It must not import a strategy, handle bars, or rerun anything.

The frozen-child artifact runner lives here:

```text
strategies/vwap_zscore_fade/children/adx_q30_workflow_test/time_stability_run.py
```

## Frozen Spec

- judged population: `completed_non_gap`
- source trades: one full-validation frozen-child generation, not per-period
  reruns
- grouping timestamp: trade `entry_time`
- granularities: month, quarter, year
- sparse floor: fewer than 20 completed_non_gap trades in a bucket is
  `insufficient`
- per-bucket fields: trade_count, mean R, total R, win_rate, max_drawdown_r,
  and sparse flag
- report framing: coverage-only, report-only, no pass/fail
- selection rule: no period selection, no time-of-year filters, no mining a
  good month or quarter

## Concentration Indicators

The child total R is negative, so concentration metrics must be sign-safe:

- sign counts across sufficient buckets: positive / zero / negative / missing
- largest-bucket absolute-total-R share:
  `abs(bucket_total_R) / sum(abs(each_bucket_total_R))`
- leave-one-bucket-out total R after removing the bucket with the largest
  absolute total R

Do not divide by signed total R. Signed totals can be negative or near zero, so
that ratio is not meaningful.

## Walk-Forward Difference

Walk-forward reruns the child in chronological validation windows, so indicator
state resets per window. Time stability generates the full validation trade list
once and only buckets the resulting judged trades by entry time.
