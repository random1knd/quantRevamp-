# Implementation Rules

These rules are meant to prevent the old failure mode: broad abstractions that
look clean but change strategy behavior from a distance.

## Strategy Rules

Each strategy must:

- state its thesis before implementation
- declare the session it trades and the session-open timestamp it uses
- block new entries for the first 60 minutes after that declared session open,
  unless the strategy README explicitly justifies an early-session variant
- compute only the indicators it uses or intentionally records
- make every research assumption explicit
- define its entry, stop, exit, and invalidation rules locally
- write reproducible artifacts
- use only causal trade-driving indicators

Each strategy must not:

- depend on a global setup / trigger / filter registry
- inherit hidden defaults from a shared framework
- require a universal bootstrap to run
- rely on post-hoc slices as if they were pre-approved filters
- import `shared.context`
- import `shared.slicing`
- import local `research_indicators.py` from `strategy.py`
- import parent strategy modules from a child strategy
- use centered windows, future bars, or full-sample normalization for values
  that affect trades

## Default Trade Gates

There is only one global default trade gate right now:

- no new entries during the first 60 minutes after the declared session open

The one-hour rule is a stability rule, not a claim that every market needs
exactly one hour. It is the default starting point so early-session VWAP,
volume, and flow-derived features have time to become usable.

Do not add more global gates without an explicit decision. Any additional gate
belongs inside a specific strategy thesis first.

## Indicator Rules

An indicator can be shared only if:

- it is a pure function
- inputs and outputs are explicit
- lookback behavior is documented
- trade-driving usage is causal
- research-context usage is causal
- no strategy-specific policy is hidden inside it
- it has a small golden-value test

Indicators should be ported in the order demanded by active strategies, not in
one large bootstrap migration.

## Execution Rules

Execution code should:

- load bars
- call one strategy
- simulate trades
- calculate realized outcomes
- write artifacts
- follow `docs/simulator_spec.md` for fill, risk, slippage, and `RealizedR`

Execution code should not:

- infer strategy type
- mutate strategy parameters
- auto-run validation
- select winners
- know about setup / trigger vocabularies
- apply session timing rules or the post-open no-trade gate

## Validation Rules

Validation can be shared because it consumes standard artifacts.

Validators should accept simple inputs:

- trades with timestamps and realized R
- optional bars for rerun-based tests
- declared train / validation / test boundaries
- declared campaign size when multiple-testing corrections are used

Validators should not depend on strategy internals.

## Slicing Rules

Slicing is allowed after execution.

Slicing should:

- consume trade artifacts
- compare winner and loser contexts
- report candidate filters
- label train-only discoveries clearly

Slicing should not:

- silently rewrite the strategy
- promote a train-side bucket as truth
- search hundreds of filters without recording multiple-testing risk
