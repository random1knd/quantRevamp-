# Walk-Forward Reruns

Purpose:

- test whether a frozen child strategy behaves consistently across validation
  time windows

## Inputs

- frozen child strategy
- validation bars
- explicit parameter snapshot
- validation split boundaries

## Code Shape

```text
shared/validation/walk_forward.py
strategies/vwap_zscore_fade/children/adx_q30_workflow_test/walk_forward_run.py
```

Expected shared helper:

```text
walk_forward_report(window_summaries, *, sparse_trade_floor)
```

The shared helper compares already-built window summaries. It must not accept a
strategy callable, import a strategy, slice bars, or run a backtest.

Strategy execution belongs in the strategy-local runner. The ADX Q30 workflow
child predeclares `WALK_FORWARD_WINDOW_COUNT = 8` before running. That count is
chosen because the validation span runs from 2018-04-18 through 2023-12-01 and
the frozen q30 child has 1810 completed_non_gap validation trades, so eight
whole-session windows should average about 226 completed_non_gap trades per
window while still showing multi-period behavior.

## Approach

- divide the 50% validation split into chronological windows
- cut windows on whole `SessionDate_ET` blocks only; never split a session
- rerun the frozen child in each window from the strategy-local runner
- report realized-R, completed_non_gap trade count, and threshold
  restrictiveness by window
- for distribution-derived raw thresholds, report each window's kept-trade
  fraction or threshold percentile when useful, because distribution drift can
  change how restrictive a frozen literal level is

For the ADX Q30 child, threshold restrictiveness counts entry-candidate signal
bars where z-side exists, same-session next-bar entry is possible, RTH/warmup
and ATR requirements pass, post-open entry timing passes, and roll-session
exclusion would not block. Only then does ADX contribute kept, rejected, or
missing counts. Do not count a signal as ADX-rejected if another non-ADX gate
would have blocked it anyway.

## Window Size Policy

Each walk-forward window should have enough trades to say anything useful.

Starting policy:

- fewer than 20 trades in a window: window is insufficient
- if more than half of windows are insufficient, the walk-forward test is
  inconclusive

Do not let sparse walk-forward windows silently pass as stable.

## Rules

- no tuning per window
- no re-derived threshold per window for the candidate result
- no new filters
- no final-test data
- no trade-split fallback in the first implementation unless explicitly added
- no "best window" interpretation; read the window set as a whole
