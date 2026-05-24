# Boundaries

This document states the boundaries that should become tests once code exists.

The purpose is to prevent silent drift.

## One-Line Rule

```text
shared math, not shared trading context
```

Shared code may compute math. Shared code must not decide what a strategy means.

Trade-driving and research-context indicator values must be causal. Future bars
must not be able to change values used for earlier trade decisions or slicing.

## Strategy Boundaries

`strategy.py` may import:

- local `indicators.py`
- local `params.py`
- pure shared indicator functions
- inert shared type definitions, if needed

`strategy.py` must not import:

- `shared.context`
- `shared.slicing`
- local `research_indicators.py`
- child strategy modules
- parent strategy modules from a child

The 60-minute post-open rule lives in each strategy's own code, not in the
runner.

Allowed shared type definitions mean passive schemas or enums only, such as a
trade side enum or trade-intent dataclass. They must not contain runner,
simulator, context-recorder, slicer, validation, or session-timing behavior.

## Context Recorder Boundary

The context recorder runs only after `trades.csv` exists.

Allowed order:

```text
runner -> strategy -> trades.csv -> context recorder -> context_trades.csv
```

Not allowed:

```text
strategy -> context recorder -> trade decision
```

The recorder consumes strategy-owned `research_indicators.py`. That file is for
post-trade research context only.

Every item listed in `research_indicators.py` should be tied to a research
question in the strategy README.

## Slicer Boundary

The slicer consumes only discovery `context_trades.csv`.

The slicer must:

- use the campaign's predeclared slicer plan
- apply the campaign's predeclared input population at the slicer
- propose at most one filter candidate per discovery run
- write searched rule count
- write searched columns
- write the selection metric
- write every searched candidate's selection score
- write a multiple-testing adjustment report
- write realized-R and 1R through 10R diagnostics when available

The slicer must not:

- edit strategy code
- read validation data
- read final-test data
- create child strategies
- create a second filter layer from the same split campaign
- choose its search space after inspecting results

## Child Strategy Boundary

Child strategies copy parent logic at first. They do not wrap parent modules.

This is deliberate duplication. It prevents parent edits from silently changing
child behavior.

Extraction can be reconsidered later only after repeated stable duplication is
obvious.

One split campaign can create only one child generation. A passing child is not
mined again on the same discovery, validation, or final-test data.

If a correctness bug is found in parent/base logic, each affected child must be
updated manually and reviewed. Do not switch to wrapping parent logic to avoid
the manual update.

Artifacts produced with the buggy logic must be marked superseded before new
decision evidence is accepted.

## Validation Boundary

A child must pass two validation gates:

1. It must have credible standalone validation evidence.
2. It must beat the parent on the same validation period.

Initial validation trade-count policy is owned by
`docs/overfitting_tests/minimum_trade_count_policy.md`:

- fewer than 30 validation trades: insufficient evidence
- 30 to 99 validation trades: low-sample / experimental
- 100 or more validation trades: normal interpretation allowed

Low-sample results must not silently pass only because they beat the parent.

## Split Boundary

The final 20% split is protected.

Code should refuse a non-final-test run if its requested data range overlaps
the final-test range.

Final-test runs must be explicitly labeled as final-test runs.

Splits are chronological by trading session. Do not split inside a session.

## Trades Schema Boundary

Realized R is calculated from initial risk.

Required fields:

- `InitialStopPrice`
- `InitialRisk`
- `RealizedR_Gross`
- `RealizedR_Net`
- `RealizedR`

Optional stop-management fields:

- `FinalStopPrice`
- `StopMoved`

Trailing-stop state must not redefine the initial R denominator.

## Test Data Boundary

Shared indicator tests use two layers:

- tiny hand-calculated examples for exact math
- one canonical synthetic bar dataset for integration behavior
- causality tests for trade-driving indicator usage

Do not let every indicator author invent unrelated toy data for the same class
of tests.

Causality tests should verify that mutating future bars does not change earlier
indicator outputs used for trade decisions.

The same causality rule applies to research-context indicators because they
feed the slicer and child-filter discovery.
