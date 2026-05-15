# Repo Structure

This is the intended shape for the new repo once code is added.

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
  kalman_vwap_fade/
    parent/
      README.md
      strategy.py
      indicators.py
      research_indicators.py
      params.py
      tests/
    children/
      low_vpin_filter/
        README.md
        strategy.py
        indicators.py
        params.py
        evidence/
        tests/
  absorption_fade/
    parent/
    children/

shared/
  data/
  indicators/
  execution/
  context/
  slicing/
  validation/
  reporting/

tests/
  boundaries/
  fixtures/
  shared/
  validation/
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
