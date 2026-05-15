# Quant Research Repo

This repo is being reset around isolated strategy research.

The previous framework tried to make every idea fit a shared setup / trigger /
filter / bootstrap engine. That created too much hidden coupling. Strategy
behavior ended up depending on generic helpers, global defaults, phase state,
manifests, registries, and a universal feature surface. The framework became
the thing being debugged instead of the trading ideas.

The new rule is simpler:

- shared math, not shared trading context
- each serious strategy is self-contained
- shared code is allowed only when it is small, mechanical, and heavily tested
- indicators are ported one at a time when a strategy or validator actually
  needs them
- validation tests can be shared, but they must stay independent of strategy
  internals
- every strategy starts with a default one-hour no-trade period after its
  declared session open
- post-trade slicing remains useful, but it must not become a universal
  bootstrap that every strategy silently depends on

## What This Repo Should Become

The research loop stays the same at a high level:

1. Write the strategy thesis in plain English.
2. Implement the strategy in its own folder.
3. Run the strategy on a source instrument and `train` split.
4. Save simple immutable artifacts: trades, run config, summary, and optional
   diagnostics.
5. Slice the resulting trades by the indicators that strategy recorded.
6. Turn any filter idea into an explicit hypothesis, not a post-hoc accident.
7. Validate the frozen strategy on same-instrument holdout data.
8. Run overfitting tests.
9. Run cross-instrument checks only after same-instrument validation.
10. Keep final `test` data untouched until the end.

## What Can Be Shared

Shared code is acceptable for:

- data schema checks
- pure indicator functions
- execution mechanics that know nothing about strategy meaning
- trade accounting and realized-R calculations
- train / validation / test split helpers
- overfitting tests
- cross-instrument comparison
- report writers that consume standard trade artifacts

Shared code is not acceptable for:

- generic strategy composition
- universal bootstrap columns
- hidden strategy defaults
- phase manifests
- ledger-driven current-state orchestration
- automatic strategy registries
- generated setup / trigger / filter combinations

## Documentation Map

- [workflow.md](workflow.md): the new research workflow.
- [repo_structure.md](repo_structure.md): intended folder layout.
- [implementation_rules.md](implementation_rules.md): what belongs inside a
  strategy and what may be shared.
- [data_and_results.md](data_and_results.md): expected input and output
  artifacts.
- [filter_discovery.md](filter_discovery.md): how recorded indicators become
  explicit child strategy filters without silent drift.
- [simulator_spec.md](simulator_spec.md): mechanical fill, risk, slippage, and
  realized-R rules.
- [campaigns.md](campaigns.md): campaign identity, slicer plans, and one-child
  governance.
- [CODING_APPROACH.md](CODING_APPROACH.md): proposed code shape for each
  workflow step before implementation starts.
- [BOUNDARIES.md](BOUNDARIES.md): import and behavior boundaries that prevent
  silent drift.
- [indicators/](indicators/): indicator family plans, parameters, anchors, and
  causal implementation notes.
- [overfitting_tests/](overfitting_tests/): validation test plans and code
  shape.
- [inventories/strategies.md](inventories/strategies.md): candidate strategy
  ideas worth preserving.
- [inventories/triggers.md](inventories/triggers.md): timing ideas worth
  preserving.
- [inventories/indicators.md](inventories/indicators.md): indicator candidates
  to port one by one.
- [inventories/validation_tests.md](inventories/validation_tests.md):
  overfitting and robustness checks to rebuild.
- [research/](research/): source research notes, formulas, caveats, and
  references.

## Current Status

This folder currently contains documentation only. The old source tree is not
present here. When the data folder is added, the next practical step is to build
one isolated strategy end to end instead of rebuilding the old framework.
