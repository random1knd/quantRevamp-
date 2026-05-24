# Parameter And Filter Nudge Stability

Purpose:

- check whether the approved child filter is fragile to small threshold changes

## Inputs

- frozen child strategy
- validation bars
- approved filter thresholds
- explicit parameter snapshot
- nudge grid
- predeclared pass/fail thresholds, or a declaration that the report is
  judgment-only

## Code Shape

```text
shared/validation/threshold_nudge.py
```

Expected function:

```text
filter_threshold_nudge(strategy, bars, validation_window, nudge_spec)
```

## Approach

- temporarily rerun nearby threshold values
- compare each temporary run against the approved child
- report fragility using the predeclared criterion, if one exists
- if no threshold is declared, treat the output as human-judgment reporting with
  no automatic pass/fail

Example:

```text
approved: VPIN <= 0.35
checks:   VPIN <= 0.30, VPIN <= 0.40
```

## Rules

- do not mutate child strategy code
- do not choose a new threshold
- do not create a new child from nudge output
