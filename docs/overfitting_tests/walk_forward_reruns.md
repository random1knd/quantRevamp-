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
```

Expected function:

```text
walk_forward_rerun(strategy, bars, validation_window, n_windows)
```

## Approach

- divide the 50% validation split into chronological windows
- rerun the frozen child in each window
- report realized-R and trade count by window
- for distribution-derived raw thresholds, report each window's kept-trade
  fraction or threshold percentile when useful, because distribution drift can
  change how restrictive a frozen literal level is

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
