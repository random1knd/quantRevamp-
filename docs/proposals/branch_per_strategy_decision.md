# Branch-Per-Strategy Decision Record (2026-05-30)

This file records the design conversation between the user, Claude, and Codex
about how to scale this repo to multiple strategy campaigns. Come back to this
when starting a new strategy branch.

## Context

- Full deep audit completed 2026-05-30: no bugs, no red flags, 366 tests green.
- The VWAP z-score fade pipeline is complete for everything buildable without a
  positive edge. The strategy itself is rejected (negative mean R).
- The deferred items (block engine wiring, promotion aggregator, Cycle D final
  test) require a real positive candidate before they can meaningfully run.
- The user wants to scale to multiple strategies while keeping the repo lean.

## Decision: branch-per-strategy

Each new strategy campaign lives on its own branch off `master`.

### Branch naming

Descriptive, outcome-neutral:

    strategy/mean-reversion-vwap-fade
    strategy/momentum-breakout-nq
    strategy/microstructure-imbalance-es

Do not rename branches after outcomes. Use annotated git tags for verdicts:

    vwap-zscore-fade/rejected-2026-05-29
    momentum-breakout-nq/advanced-final-2026-07-15
    momentum-breakout-nq/promoted-2026-08-02

### One strategy family per branch

Each branch carries exactly one strategy family (parent + child if applicable).
No mixing of unrelated strategies on the same branch.

### What master holds

- shared/data (bars, splits, provenance)
- shared/indicators (add new ones as needed)
- shared/validation (all engines, including unwired block engines)
- tests/boundaries
- the VWAP z-score fade as a completed structural reference
- docs, review protocol, campaign index

### The template vs reference distinction (key decision)

This was the main point of debate. Resolution:

**The VWAP fade is a structural reference, not a strategy template.**

What to reference (pipeline patterns):
- file organization and child-folder layout
- runner patterns (data loading, split enforcement, artifact writing)
- test structure (causality tests, boundary tests)
- artifact format (provenance, hashes, frozen config)
- the codexArg/claudeArg review loop

What NOT to copy forward (strategy-specific):
- thesis, params, indicator choices, entry/exit rules
- session gates, cost/slippage assumptions
- validation thresholds, timing labels, threshold types
- instrument transfer assumptions, research columns
- any VWAP-fade-specific logic

Codex's key warning: "Pipeline structure is not assumption-free." Things like
`NO_ENTRY_BEFORE_SESSION_MINUTE = 60` or `COMMISSION_PER_ROUND_TURN = 5.16`
look like pipeline but are actually strategy-specific. A new branch must
explicitly adopt or change these in its own README and params before discovery.

### Starting a new strategy branch

1. Branch from current master.
2. Write a fresh thesis README (instrument, timeframe, entry/exit logic,
   session assumptions, cost assumptions, invalidation criteria).
3. Write fresh params.py from scratch.
4. Predeclare the slicer plan and campaign identity before discovery.
5. Reference the VWAP fade's runner/test patterns for wiring.
6. Merge or rebase master before any verdict run.

### When a positive candidate appears

That branch is where you:
- wire the block bootstrap engine to the strategy runner
- build the promotion aggregator
- run the Cycle D final 20% test
- complete the remaining deferred items

Pure shared improvements (engine fixes, new validators) get merged back to
master. Strategy-local wiring stays on the branch.

### Campaign index

`CAMPAIGN_INDEX.md` at repo root tracks every strategy branch: thesis,
instrument, verdict, verdict tag, date. Human-maintained only.

### Merge policy

- Shared infrastructure improvements merge back to master.
- Strategy-specific code never merges to master.
- Before-verdict sync: merge or rebase master before any verdict run so shared
  code does not diverge.

## Risks to watch

1. Shared-code divergence across long-lived branches.
2. Mechanical copy-forward of VWAP assumptions disguised as pipeline patterns.
3. Treating the campaign index as machine state instead of a human directory.

## Who agreed

- User: proposed the branch-per-strategy model.
- Claude: refined with tagging convention, merge policy, campaign index.
- Codex: accepted with the template/reference distinction and before-verdict
  sync requirement.

All three aligned as of 2026-05-30.
