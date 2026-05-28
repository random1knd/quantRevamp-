# Parameter And Filter Nudge Stability

Purpose:

- check whether a discovered filter threshold is an isolated discovery spike
- later check whether the live child implementation is fragile to nearby
  literal threshold values

This test is split into two reports. Both current reports are implemented for
the ADX Q30 workflow child, and both are report-only. Neither report can select
a new threshold or validate an edge.

## Report 1: Threshold-Neighborhood Report

Code:

```text
shared/validation/threshold_neighborhood.py
strategies/vwap_zscore_fade/parent/threshold_neighborhood_run.py
```

Artifacts:

```text
threshold_neighborhood_report.json
threshold_neighborhood_report.csv
```

Inputs:

- `slice_report.csv`
- `filter_candidate.json`
- `slicer_plan.json`

The helper compares already-scored slicer rows. It does not import any
strategy, rerun a backtest, or create a new candidate.

The report is train-side and discovery-contaminated. It cannot validate an
edge. It only flags whether the slicer result was an isolated threshold spike
inside the original search grid. For the current ADX Q30 workflow child, the
slicer verdict is `no_candidate`, so the report is coverage-only and makes no
edge claim.

Policy:

- inspect same-column, same-direction immediate quantile neighbors
- at least one immediate neighbor should keep positive mean `RealizedR` and at
  least 50% of the anchor rule's mean `RealizedR`
- if both immediate neighbors exist and both fail, set `isolated_spike_flag`
- if the anchor rule mean is not positive, the policy is not applicable

The current grid is coarse (`q20/q30/q40` style 10-point steps), so this policy
only catches obvious threshold spikes.

## Report 2: Child-Rerun Threshold Nudge

Code:

```text
shared/validation/threshold_nudge.py
strategies/vwap_zscore_fade/children/adx_q30_workflow_test/threshold_nudge_run.py
```

Artifacts:

```text
threshold_nudge_report.json
threshold_nudge_report.csv
```

The child-rerun nudge reruns the frozen child strategy on validation bars using
literal discovery-derived threshold values from the slicer rows. It tests
implementation fidelity: causal indicator recomputation, warmup, fills, costs,
roll exclusion, and validation population.

For distribution-derived raw thresholds, the primary nudge grid must use
literal discovery-derived values. Re-derived validation quantiles may be
reported only as diagnostics and must not reset the approved child threshold.

For the current ADX Q30 workflow child, the implemented grid uses literal q20,
q30, and q40 `SignalADX <=` slicer-row thresholds. The q30 row remains the
baseline frozen child; q20 and q40 are diagnostics only.

## Rules

- do not mutate child strategy code
- do not choose a new threshold
- do not create a new child from either report
- do not let validation data reset the approved filter threshold
- do not treat the threshold-neighborhood report as out-of-sample validation
