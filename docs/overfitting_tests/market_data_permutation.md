# Market-Data Permutation

Purpose:

- test whether strategy performance depends on real market sequence structure

## Inputs

- frozen child strategy
- validation bars
- explicit parameter snapshot
- block size or permutation method
- random seed

## Code Shape

```text
shared/validation/market_permutation.py
```

Expected function:

```text
market_data_permutation(strategy, bars, validation_window, permutation_spec)
```

## Approach

- create altered validation bar paths
- preserve basic OHLC consistency
- preserve session boundaries and declared RTH structure
- keep each session's timestamps and `SessionMinute_ET` anchors intact
- permute bars or blocks within sessions, not across sessions
- rerun the frozen child on each altered path
- compare actual validation result against permuted results

## Rules

- later test, not first implementation
- no final-test data
- no strategy mutation
- report random seed and permutation method
