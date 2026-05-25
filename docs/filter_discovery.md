# Filter Discovery Flow

This document defines how indicator-based filters are discovered without
letting indicators silently become part of the original strategy.

## Core Separation

There are two separate jobs:

1. The strategy generates trades.
2. The research context layer records indicators around those trades.

The recorded indicators do not influence the base strategy's entries, exits,
stops, position selection, or trade timing.

## Split Model

Use chronological splits:

```text
30% discovery and slicing
50% validation and overfitting tests
20% final untouched test
```

The discovery split is contaminated after slicing. It can discover a filter,
but it cannot prove that filter works.

## Discovery Run

Run the parent strategy on the first 30%.

Write:

- `trades.csv`
- `context_trades.csv`
- `summary.json`
- `run_config.json`

`trades.csv` is the actual strategy output.

`context_trades.csv` is the same trades plus recorded indicator values for
slicing. It is research data, not strategy logic. The context writer does not
drop incomplete trades or gap-crossing holds; the slicer applies the campaign's
predeclared input population.

## Slicer Rule

The slicer must use the campaign's predeclared slicer plan.

The slicer plan must declare its input population before the search starts.
The current default population is `completed_non_gap`: rows where
`ExitReason != end_of_data` and `HoldCrossesGap == false`. A different
population is allowed only with an explicit campaign rationale.

The slicer may propose only one best filter candidate per discovery run.

The slicer must write a filter candidate artifact that states:

- parent strategy
- campaign id
- discovery split used
- slicer input population
- selected filter rule
- selection metric
- searched columns
- searched rule count
- per-candidate selection-metric distribution
- multiple-testing adjustment report
- trade count before and after the filter
- 1R through 10R diagnostics when available
- realized-R summary

The slicer must not modify strategy code.

The slicer must not choose its search space after inspecting results.

The multiple-testing report must state how the selected score was adjusted for
the full search. Preferred v0 mechanics are a full-search permutation null:
shuffle `RealizedR` against the filter columns, rerun the entire predeclared
search for each permutation, and compare the selected score to the distribution
of maximum permuted scores. A Bonferroni report can remain as an informational
secondary check when a raw p-value is available.

Initial real-candidate gate:

- selected mean `RealizedR` must be positive
- the rule must meet the campaign's predeclared minimum kept-trade count
- full-search permutation adjusted p-value must be `<= 0.10`
- the selected rule must not be flagged as outlier-divergent

This gate is enforced when the slicer artifact is written. The rule-search
helper may identify the best eligible positive rule, but the artifact can label
`candidate_status = candidate_selected` only when the artifact-layer
`candidate_gate` passes all requirements. Otherwise it must write
`candidate_status = no_candidate` with a specific `no_candidate_reason`.

If the full-search adjusted p-value is unavailable, the slicer may write a
coverage or workflow-test child only with an explicit non-edge label. It must
not label the filter as a real promoted edge candidate.

## Parent And Child Strategy Layout

Filtered versions are written as child strategies under the parent.

Use this layout:

```text
strategies/
  <strategy_name>/
    parent/
      README.md
      strategy.py
      indicators.py
      research_indicators.py
      params.py
    children/
      <child_name>/
        README.md
        strategy.py
        indicators.py
        params.py
        evidence/
```

The child strategy must explicitly contain the approved filter. A filter found
by slicing is not active until it appears in a child strategy.

## Threshold Freeze Policy

Promoted child strategies freeze literal parameter values. If a filter was
found from a quantile grid, the child records both the quantile provenance and
the literal threshold, but the child trades the literal threshold.

Out-of-sample validation, walk-forward windows, cross-instrument checks, and
final tests must not re-derive that quantile from the evaluation data. A
re-derived quantile may be reported only as a diagnostic sensitivity view, not
as the candidate's pass/fail result.

If the actual thesis is relative-regime behavior, such as "lowest 30% ADX",
then that percentile rank must be implemented as an explicit causal strategy
input before discovery. In that case the frozen child threshold is the
scale-free percentile value, not a raw level re-derived from holdout data.

## Validation

Run both parent and child on the next 50%.

The child must pass two gates before it can move forward:

1. The child must have credible standalone validation evidence.
2. The child must beat the parent on the same validation period.

The primary comparison is realized R, but the report should also show:

- trade count
- win rate
- max drawdown in R
- 1R through 10R hit or touch diagnostics, where available
- whether the child became too rare to evaluate honestly

A rare strategy is allowed if the evidence supports it. The report should not
reject a child only because it trades less often, but it must make low sample
size obvious.

Do not treat "beats parent" as sufficient when the child has too little evidence
to evaluate honestly.

Initial validation trade-count policy is defined in
`docs/overfitting_tests/minimum_trade_count_policy.md`:

- fewer than 30 validation trades: insufficient evidence
- 30 to 99 validation trades: low-sample / experimental
- 100 or more validation trades: normal interpretation allowed

Initial same-instrument validation can only advance a child to overfitting
review; it is not final promotion. The gate for that advance is:

- completed_non_gap validation trade count must be in the `normal_ge_100` tier
- child mean `RealizedR` must be positive
- child mean `RealizedR` must beat parent mean `RealizedR` by at least `0.05R`

Final real-candidate promotion after validation also requires:

- validation centered-bootstrap one-sided p-value `<= 0.10`
- no required overfitting report with a blocking failure
- cross-instrument and final-test evidence reviewed under their declared labels

These thresholds are campaign governance, not universal market truth. Changing
them requires a documented decision before discovery for that campaign. The
current ADX Q30 child is a workflow-test child and is not a real candidate.

## Overfitting Tests

Run overfitting tests after validation and before cross-instrument checks.

CSV-only tests use validation trade results:

- realized-R summary
- minimum trade count / low-sample warning
- Monte Carlo centered-bootstrap significance
- Monte Carlo equity curves

Slicer-artifact tests use discovery artifacts and are train-side only:

- threshold-neighborhood report from the scored `slice_report.csv`

The threshold-neighborhood report cannot validate an edge. It checks whether
the selected or best slicer rule was an isolated threshold spike in the already
searched same-column, same-direction grid. The advisory policy is: at least one
immediate neighbor should keep positive mean `RealizedR` and at least 50% of the
anchor rule's mean `RealizedR`; if both immediate neighbors exist and both fail,
flag `isolated_spike_flag`.

Rerun-based tests use validation bars and the frozen child strategy:

- walk-forward windows inside the validation split
- child-rerun filter-threshold nudge report
- market-data permutation later

The child-rerun filter-threshold nudge report checks implementation fragility.
It temporarily reruns nearby literal discovery-derived thresholds, but it must
not mutate the child strategy.

Walk-forward sparse-window policy:

- fewer than 20 trades in a walk-forward window: window is insufficient
- if more than half of windows are insufficient: the walk-forward test is
  inconclusive

Do not let sparse walk-forward windows silently pass as stable.

Backtest-based overfitting tests must rerun the frozen child strategy against
validation bars. They create separate test artifacts and must not edit the child
strategy or select a new threshold.

## Cross-Instrument And Final Test

Cross-instrument checks happen only after the child passes validation and
overfitting review.

The final 20% test happens after that. It is run once on the frozen candidate.
No slicing, tuning, threshold changes, or child creation happens on the final
test split.

Before any final-test run, check whether the last source session is complete
under the strategy's declared session rules. If the source file ends with a
partial session, either exclude that tail session from the final-test run or
label the artifact as partial-tail so it cannot be read as a complete final
session result.

## Anti-Drift Rules

- Do not let recorded indicators influence the parent strategy.
- Do not let the slicer edit strategy code.
- Do not create more than one child from one discovery run.
- Do not create a second child generation from the same split campaign.
- Do not create a filter candidate artifact without searched rule count.
- Do not create a filter candidate artifact without per-candidate scores.
- Do not run a slicer without a predeclared campaign slicer plan.
- Do not change split boundaries without explicit approval.
- Do not change the one-hour post-open rule without explicit approval.
- Do not add new global gates without explicit approval.
- If the intended behavior is unclear, ask before editing strategy behavior.
