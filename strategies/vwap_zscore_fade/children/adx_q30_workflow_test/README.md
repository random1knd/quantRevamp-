# VWAP Z-Score Fade ADX Q30 Workflow Test Child

This child is a workflow test / demonstration child, negative expectancy, NOT a
discovered edge.

It exists to exercise the downstream pipeline after the parent slicer correctly
returned `no_candidate`. The slicer artifact's best eligible rule was still a
loser, so this child must not be treated as a promoted trading edge.

## Filter

The child copies the parent VWAP z-score fade logic explicitly and adds one
trade-driving filter:

```text
SignalADX <= 19.26665446628932
```

The threshold is frozen from:

```text
data/results/vwap_zscore_fade/parent/discovery_20260524T050004Z/slicer_20260524T061833Z/filter_candidate.json
```

The copied evidence lives under `evidence/`.

## ADX Semantics

ADX is computed in the child trade path, not imported from parent research
context. It is session-scoped, causal, and uses the same shared ADX math as the
research context.

If ADX is missing at the signal bar, the child opens no trade.

## Governance

- This child does not import or wrap the parent strategy.
- This child does not import `research_indicators.py`.
- This child keeps the parent session, post-open, stop, target, time-stop,
  slippage, and commission semantics copied into the child folder.
- Any validation output for this child must be labeled workflow-test coverage,
  not edge evidence.
