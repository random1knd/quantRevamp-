# Coding Approach By Step

This document describes the code shape for the proposed workflow.

It is not implementation yet. It is a coding plan so the boundaries can be
reviewed before any source code exists.

## 1. Data Loading

Goal:

- load bar data for one instrument and timeframe
- expose chronological split windows
- avoid strategy-specific behavior

Likely code:

```text
shared/data/
  bars.py          # load bars, validate required columns
  splits.py        # calculate 30/50/20 chronological windows
```

Inputs:

- bar files
- instrument
- timeframe

Outputs:

- bars dataframe
- split boundaries

Must not:

- choose strategy rules
- calculate research filters
- mutate split percentages without explicit approval
- allow a non-final-test run to overlap the final-test range

## 2. Parent Strategy

Goal:

- generate trades from explicit base strategy logic

Likely code:

```text
strategies/<strategy_name>/parent/
  README.md
  strategy.py
  indicators.py
  research_indicators.py
  params.py
```

`strategy.py` owns:

- entry logic
- exit logic
- stop/risk logic
- the 60-minute post-open no-trade rule

`indicators.py` owns only the indicators needed by that strategy's actual
rules.

`research_indicators.py` lists context indicators to record after trades exist.
Every listed context indicator should be tied to a research question in the
parent README.

Must not:

- use slicer-discovered filters
- depend on a global strategy registry
- allow recorded context indicators to affect trades
- import `shared.context` or `shared.slicing`
- import `research_indicators.py` from `strategy.py`
- use centered windows, future bars, or full-sample normalization for values
  that affect trades

## 3. Shared Indicators

Goal:

- provide small reusable indicator functions

Likely code:

```text
shared/indicators/
  atr.py
  vwap.py
  zscore.py
  order_flow.py
```

These should be pure functions where possible.

Strategies may call shared indicators explicitly, but there is no universal
`compute_all_indicators()` layer for trading decisions.

The rule is shared math, not shared trading context.

Indicator family plans live under `docs/indicators/`. Those docs define the
inputs, explicit parameters, anchor/session choices, causal behavior, and tests
before code is written.

Must not:

- decide entries
- apply filters
- hide session policy
- calculate every research indicator for every strategy by default

## 4. Backtest Runner

Goal:

- run one chosen strategy over one chosen split
- write stable artifacts

Likely code:

```text
shared/execution/
  runner.py        # calls strategy on bars and writes artifacts
  simulator.py     # trade accounting
```

Inputs:

- strategy path or object
- bars
- split name
- params
- output directory

Outputs:

```text
trades.csv
summary.json
run_config.json
```

Simulator behavior is specified in `docs/simulator_spec.md`.

Must not:

- run the slicer automatically
- run validation automatically
- create child strategies
- change strategy parameters
- apply session timing rules or the post-open no-trade gate

## 5. Research Context Recorder

Goal:

- attach research indicators to already-created trades
- support slicing without influencing trade generation

Likely code:

```text
shared/context/
  recorder.py
  indicator_set.py
```

Inputs:

- bars
- `trades.csv`
- strategy-owned `research_indicators.py`

Outputs:

```text
context_trades.csv
```

Important boundary:

- this runs after the strategy has generated trades
- its outputs are for analysis only

Must not:

- change trades
- remove trades
- add trades
- affect entries, exits, stops, or timing

## 6. Discovery Slicer

Goal:

- inspect discovery `context_trades.csv`
- propose one best filter candidate

Likely code:

```text
shared/slicing/
  slicer.py
  filter_candidate.py
```

Inputs:

- discovery `context_trades.csv`
- campaign slicer plan

Outputs:

```text
filter_candidate.json
slice_report.csv
```

The candidate artifact should include:

- slicer input population
- selected filter rule
- selection metric
- searched columns
- searched rule count
- per-candidate selection-metric distribution
- multiple-testing adjustment report
- before/after trade count
- realized-R summary
- 1R through 10R diagnostics when available

Must not:

- edit strategy code
- create more than one candidate from one discovery run
- read validation or final-test data
- choose its search space after inspecting results

## 7. Child Strategy Creation

Goal:

- turn one approved filter candidate into explicit strategy code

Likely code layout:

```text
strategies/<strategy_name>/children/<child_name>/
  README.md
  strategy.py
  indicators.py
  params.py
  evidence/
```

Approach:

- copy the parent logic explicitly
- add the approved filter in readable code
- store the filter candidate artifact under `evidence/`

Must not:

- auto-generate a child without approval
- keep the filter hidden in slicer output only
- create multiple children from the same discovery run
- wrap parent strategy logic

## 8. Validation Run

Goal:

- test whether the frozen child beats the parent on the next 50%

Likely code:

```text
shared/validation/
  compare_parent_child.py
```

Inputs:

- parent strategy
- child strategy
- validation bars
- validation split boundaries

Outputs:

```text
parent_validation/trades.csv
child_validation/trades.csv
comparison_report.json
```

Report should show:

- realized R
- trade count
- win rate
- max drawdown in R
- 1R through 10R diagnostics when available
- low-sample warning if relevant

Validation is two-gated:

- the child must have credible standalone validation evidence
- the child must beat the parent on the same validation period

Must not:

- tune the child
- slice validation data to discover new filters
- change the child strategy

## 9. CSV-Only Overfitting Tests

Goal:

- test validation trade results without rerunning the strategy

Likely code:

```text
shared/validation/
  realized_r.py
  monte_carlo.py
  equity_curves.py
```

Inputs:

- child validation `trades.csv`

Outputs:

```text
csv_overfit_report.json
```

Tests:

- realized-R summary
- low-sample warning
- Monte Carlo permutation
- Monte Carlo equity curves

Detailed validation-test plans live under `docs/overfitting_tests/`.

Must not:

- use discovery trades to prove the child
- change strategy behavior

## 10. Backtest-Based Overfitting Tests

Goal:

- run controlled reruns that cannot be answered from `trades.csv`

Likely code:

```text
shared/validation/
  walk_forward.py
  threshold_nudge.py
  market_permutation.py
```

Inputs:

- frozen child strategy
- validation bars
- validation split boundaries
- explicit parameter snapshot

Outputs:

```text
walk_forward_report.json
nudge_report.json
market_permutation_report.json
```

Approach:

- walk-forward: split validation into smaller chronological windows and rerun
- threshold nudge: temporarily rerun nearby filter thresholds
- market permutation: create altered validation bar paths and rerun later

Must not:

- mutate the child strategy
- choose a new threshold
- use final-test data
- treat temporary nudge results as a new approved child

## 11. Cross-Instrument Validation

Goal:

- check whether the frozen child transfers to other instruments

Likely code:

```text
shared/validation/
  cross_instrument.py
```

Inputs:

- frozen child strategy
- target instrument bars
- matching validation split policy

Outputs:

```text
cross_instrument_report.json
```

Must not:

- discover filters on target instruments
- tune thresholds per instrument
- create new child strategies

## 12. Final Untouched Test

Goal:

- run the frozen candidate once on the final 20%

Likely code:

```text
shared/validation/
  final_test.py
```

Inputs:

- frozen child strategy
- final-test bars
- final split boundaries

Outputs:

```text
final_test/trades.csv
final_test/summary.json
final_test/final_report.json
```

Must not:

- slice
- tune
- change thresholds
- create child strategies
- rerun repeatedly to choose a better result

## 13. Result Storage

Goal:

- keep outputs understandable without a ledger or phase system

Likely layout:

```text
data/results/<strategy_name>/
  parent/
    discovery/
    validation/
  children/
    <child_name>/
      discovery_evidence/
      validation/
      overfit_tests/
      cross_instrument/
      final_test/
```

Artifacts should be immutable once used for a decision. If a strategy changes,
create a new child or versioned run folder rather than overwriting evidence.

When a child is promoted or used for a decision, store either:

- git commit/tag, when the repo is under git, or
- a source snapshot/hash under the child `evidence/` folder

If a correctness bug is found in copied base logic, affected children are
manually patched and revalidated. Old artifacts are marked superseded instead
of overwritten.

## 14. Boundary Tests

Goal:

- make silent drift visible as test failures

Likely code:

```text
tests/boundaries/
  test_strategy_imports.py
  test_final_split_protection.py
  test_filter_candidate_schema.py
```

Checks:

- `strategies/**/strategy.py` must not import `shared.context`
- `strategies/**/strategy.py` must not import `shared.slicing`
- `strategies/**/strategy.py` must not import local `research_indicators.py`
- trade-driving indicators must pass causality tests
- non-final-test runs must not overlap the final-test range
- filter candidate artifacts must include `searched_rule_count`
- filter candidate artifacts must include the selection metric
- filter candidate artifacts must include a multiple-testing adjustment report
- `strategies/**/children/**/strategy.py` must not import from parent
  `strategy.py`
- research indicators must pass causality tests
- simulator fill/risk behavior must match `docs/simulator_spec.md`
- validation trade-count status must follow the minimum backtest length policy
- walk-forward reports must mark sparse windows as insufficient/inconclusive

## 15. Indicator Test Data

Goal:

- test indicator math and integration without ad hoc toy data each time

Likely code:

```text
tests/fixtures/
  synthetic_bars.csv
tests/shared/indicators/
```

Use two test layers:

- tiny hand-calculated examples for exact indicator math
- one canonical synthetic bar dataset for indicator integration tests
- causality tests for trade-driving indicator usage

The canonical dataset should include known sections such as trend, chop,
flat volume, and volume spikes.

Causality tests should verify that future data cannot change past indicator
values. For example, compute the indicator on full bars, mutate bars after
bar N, then assert outputs up to N are unchanged.

## Main Boundary

The most important coding boundary is:

```text
trade-generating code is separate from research-context code
```

Indicators can be recorded broadly for analysis, but only parent or child
strategy code can decide trades.
