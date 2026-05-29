# Repo Structure

This is the intended shape for the repo. The concrete strategy currently in the
tree is `vwap_zscore_fade`; future strategies should follow this shape without
adding registries or hidden orchestration.

```text
data/
  raw/
  bars/
  results/

docs/
  README.md
  BOUNDARIES.md
  CODING_APPROACH.md
  REVIEW.md
  workflow.md
  repo_structure.md
  implementation_rules.md
  data_and_results.md
  filter_discovery.md
  simulator_spec.md
  campaigns.md
  indicators/
  overfitting_tests/
  inventories/
  research/

strategies/
  vwap_zscore_fade/
    validation_run.py
    validation_monte_carlo_run.py
    validation_equity_curves_run.py
    parent/
      README.md
      strategy.py
      indicators.py
      research_indicators.py
      params.py
      discovery_run.py
      slicer_run.py
      threshold_neighborhood_run.py
      campaigns/
      tests/
    children/
      adx_q30_workflow_test/
        README.md
        strategy.py
        indicators.py
        params.py
        evidence/
        walk_forward_run.py
        threshold_nudge_run.py
        market_permutation_run.py
        time_stability_run.py
        cross_instrument_run.py
        tests/

shared/
  data/
  indicators/
  validation/

tests/
  boundaries/
  shared/
```

## Strategy Folders

Strategies are the center of the repo.

A parent strategy folder owns:

- the trading thesis
- feature computation needed by that thesis
- signal logic
- stop and exit logic
- parameter defaults
- invariants
- tests

A child strategy folder owns:

- the explicit approved filter
- the evidence that led to the child
- validation results against the parent
- overfitting-test outputs
- tests for child-specific filter behavior

Duplication across early strategies is acceptable. Do not extract shared
abstractions until two or three strategies prove the same structure is stable.

## Shared Folders

Shared folders must be boring.

Good shared code:

- loads a bar file
- validates a schema
- computes ATR from OHLC
- computes VWAP from bars
- computes realized R from trades
- runs a Monte Carlo test on a return series

Bad shared code:

- decides what a setup is
- picks a trigger
- auto-discovers strategy configs
- applies hidden filters
- attaches dozens of columns every time
- stores workflow current state
