# Research Workflow

The workflow is still research -> execution -> slicing -> validation. The
difference is that the strategy owns its own logic and required indicators.

Use the detailed filter flow in `filter_discovery.md` when a base strategy is
being turned into a filtered child strategy.

Use `campaigns.md` to define campaign identity and the slicer plan before
running discovery slicing.

## 1. Strategy Thesis

Start each strategy with a README in its own folder.

The thesis should state:

- instrument and timeframe
- market condition being exploited
- entry logic
- timing logic, if any
- stop and exit logic
- required indicators
- session assumptions
- whether the default one-hour post-open no-trade gate is used or intentionally
  overridden
- slippage and cost assumptions
- what would invalidate the idea
- which validation tests are mandatory before trusting it

No strategy should begin as a pile of reusable framework parts. If a timing
idea matters, write it directly in the strategy first.

## 2. Implementation

Each strategy should be readable without tracing through global registries.

The strategy folder should contain:

- `README.md` for the thesis and assumptions
- `strategy.py` for signal, risk, and exit logic
- `indicators.py` for strategy-specific derived data
- `research_indicators.py` for post-trade context indicators used only by the
  recorder
- `params.py` or a small config file for explicit parameters
- tests near the strategy

Shared indicators may be imported only if they are pure functions with narrow
inputs, explicit parameters, and tests.

## 3. Execution

The runner should load bars, call the strategy, simulate trades, and write
artifacts. It should not understand strategy families, setup names, trigger
names, filter names, or research semantics.

The minimum artifacts for each run are:

- `trades.csv`
- `run_config.json`
- `summary.json`

Optional artifacts:

- `slices.csv`
- `context_trades.csv`
- `validation.json`
- charts or diagnostics

## 4. Slicing

Post-trade slicing is still valuable. The base strategy generates trades first,
then a separate context layer records indicator values around those trades.
Those recorded indicators do not influence the base strategy.

Slicing answers questions like:

- which hours worked?
- did high volatility help or hurt?
- did low VPIN improve fades?
- did a regime score separate winners from losers?
- did a timing trigger improve realized R?

The slicer may propose one best filter candidate per discovery run. Any
approved filter must become an explicit child strategy and then survive
validation. Do not keep stacking filters because train-side slicing found a
nice bucket.

## 5. Validation

Use this order:

1. Discovery and slicing on the first 30%.
2. Same-instrument validation on the next 50%.
3. Standalone child credibility check on that same validation split.
4. Parent-vs-child comparison on that same validation split.
5. Minimum sample and realized-R checks.
6. Monte Carlo permutation.
7. Monte Carlo equity curves.
8. Walk-forward reruns inside validation.
9. Filter-threshold nudge report.
10. Cross-instrument validation.
11. Final untouched test on the last 20%.

One split campaign can create only one child generation. If a child passes and
you want to add another filter layer, start a new campaign with fresh data or
accept the child as final for this campaign.

Cross-instrument checks are not a substitute for same-instrument validation.
They answer a different question: whether the edge transfers.

## 6. Promotion

Promotion should mean the strategy is now explicit, frozen, and reproducible.

Promotion does not require a ledger, manifest chain, or generated wrapper. It
requires:

- exact code version or snapshot
- exact parameters
- exact data range
- exact train / validation / test boundaries
- exact validation outputs
- known failure modes

Use the run-config mechanism in `data_and_results.md`: decision evidence must
include either a git commit/tag or a source snapshot/hash.
