# Review: What This Repo Is Trying To Do

This repo is being reset into a clean quant research workflow built around
self-contained strategies.

The old direction failed because too much behavior lived in shared helpers,
global defaults, phase state, and broad bootstrap logic. The new direction is
to keep strategy decisions explicit while still allowing reusable indicators,
validation tests, and result analysis.

The one-line rule is:

```text
shared math, not shared trading context
```

## Core Idea

Each strategy should trade from its own explicit rules.

Indicators can be recorded broadly for research, but recorded indicators do not
influence the parent strategy's trades unless a new approved child strategy is
created.

The main separation is:

```text
strategy generates trades
research context records indicators
slicer studies context
approved filter becomes explicit child strategy
child is validated out of sample
```

## Strategy Structure

Use a parent/child layout:

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

The parent is the base strategy.

A child is a filtered version created only after slicing finds one approved
filter candidate.

## One Global Trade Rule

There is only one global default trade gate right now:

- no new entries during the first 60 minutes after the declared session open

No other global gates should be added without explicit approval.

## Split Model

Use chronological splits:

```text
30% discovery and slicing
50% validation and overfitting tests
20% final untouched test
```

The discovery split is used to find ideas.

The validation split is used to prove whether a frozen child strategy actually
beats the parent.

The final test split is touched only once, after the candidate is frozen.

## Discovery Phase

Run the parent strategy on the first 30%.

Write:

- `trades.csv`
- `context_trades.csv`
- `summary.json`
- `run_config.json`

`trades.csv` is the actual strategy output.

`context_trades.csv` is the same trades plus recorded indicator values. These
indicator values are for slicing only.

## Slicing Phase

The slicer reads only discovery `context_trades.csv`.

The slicer may propose only one best filter candidate per discovery run.

The slicer must not edit strategy code.

The filter candidate should state:

- parent strategy
- discovery split used
- selected filter rule
- selection metric
- searched columns
- searched rule count
- multiple-testing adjustment report
- trade count before and after filter
- realized-R summary
- 1R through 10R diagnostics when available

## Child Strategy Phase

If the filter is approved, create a child strategy.

The child must contain the filter explicitly. Nothing discovered by slicing is
active until it is written into the child strategy.

## Validation Phase

Run both parent and child on the next 50%.

The child must pass two validation gates before moving forward:

1. The child must have credible standalone validation evidence.
2. The child must beat the parent on the same validation period.

The validation report should include:

- realized R
- trade count
- win rate
- max drawdown in R
- 1R through 10R diagnostics when available
- whether the child became too rare to evaluate honestly

Rare strategies are allowed, but low sample size must be obvious.

Do not silently convert low-sample results into an approval just because the
child beats the parent.

Initial validation trade-count policy:

- fewer than 30 validation trades: insufficient evidence
- 30 to 99 validation trades: low-sample / experimental
- 100 or more validation trades: normal interpretation allowed

## Overfitting Tests

Overfitting tests happen after validation and before cross-instrument checks.

CSV-only tests use validation trade results:

- realized-R summary
- low-sample warning
- Monte Carlo permutation
- Monte Carlo equity curves

Rerun-based tests use validation bars and the frozen child strategy:

- walk-forward windows inside validation
- filter-threshold nudge report
- market-data permutation later

The filter-threshold nudge report checks fragility. It may rerun nearby
thresholds temporarily, but it must not mutate the child strategy.

## Backtest-Based Overfitting Tests

Some overfitting tests cannot be run from `trades.csv` alone. They require new
backtests.

These tests must use:

- the frozen child strategy
- the same explicit parameter snapshot
- the validation bars
- the declared validation split boundaries
- a separate output folder for the test

They must not edit the child strategy.

### Walk-Forward Reruns

Walk-forward splits the 50% validation block into smaller chronological
windows.

Each window reruns the frozen child strategy and reports whether results are
consistent across time.

This is not a tuning step.

### Filter-Threshold Nudge Reruns

Nudge tests temporarily rerun nearby filter thresholds to check fragility.

Example:

```text
approved filter: VPIN <= 0.35
temporary checks: VPIN <= 0.30, VPIN <= 0.40
```

The temporary runs are evidence only. They do not replace the approved child
filter.

### Market-Data Permutation Reruns

Market-data permutation creates altered validation bar paths and reruns the
same frozen child strategy against them.

The purpose is to check whether the strategy depends on real market sequence
structure.

This is a later test, not part of the first implementation.

## Cross-Instrument Phase

Cross-instrument checks happen only after validation and overfitting review.

The same frozen child strategy is run on other instruments. The purpose is to
check transfer, not to discover new filters.

## Final Test Phase

The last 20% is the final untouched test.

Run the frozen candidate once.

No slicing, tuning, threshold changes, or child creation happens on this split.

## Anti-Drift Rules

- Recorded indicators do not influence parent strategy trades.
- The slicer does not edit strategy code.
- One discovery run can create at most one child candidate.
- One split campaign can create only one child generation. Do not mine the same
  discovery, validation, or final-test data for a second filter layer.
- Child strategies copy parent logic at first; they do not wrap parent logic.
- Split boundaries do not change without explicit approval.
- The one-hour post-open rule does not change without explicit approval.
- No new global trade gates are added without explicit approval.
- If behavior is unclear, ask before changing strategy behavior.

## Current Approach In One Line

Use broad indicator recording for research visibility, but require explicit
child strategy code before any discovered filter can affect trades.

For the proposed code shape behind each step, see `CODING_APPROACH.md`.
