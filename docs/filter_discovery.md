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
`docs/overfitting_tests/minimum_backtest_length.md`:

- fewer than 30 validation trades: insufficient evidence
- 30 to 99 validation trades: low-sample / experimental
- 100 or more validation trades: normal interpretation allowed

## Overfitting Tests

Run overfitting tests after validation and before cross-instrument checks.

CSV-only tests use validation trade results:

- realized-R summary
- minimum trade count / low-sample warning
- Monte Carlo permutation
- Monte Carlo equity curves

Rerun-based tests use validation bars and the frozen child strategy:

- walk-forward windows inside the validation split
- filter-threshold nudge report
- market-data permutation later

The filter-threshold nudge report checks fragility. It temporarily reruns nearby
thresholds, but it must not mutate the child strategy.

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
