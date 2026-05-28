# Validation Test Inventory

Validation is the safest place to share code because it should consume standard
artifacts rather than strategy internals.

Detailed test plans live in `../overfitting_tests/`.

## Build Order

| Order | Test | Purpose | Input | Status |
|---|---|---|---|---|
| 1 | Realized-R summary | Establish basic expectancy, drawdown, and trade count. | `trades.csv` | To build |
| 2 | Minimum sample check | Reject tiny samples before deeper validation. | Realized R series | To build |
| 3 | Monte Carlo permutation | Test whether returns beat a zero-edge null. | Realized R series | To build |
| 4 | Monte Carlo equity curves | Estimate distribution of possible equity paths. | Realized R series | To build |
| 5 | Walk-forward reruns | Check chronological generalization. | Bars plus strategy | To build |
| 6 | Deflated Sharpe | Correct for non-normality and campaign size. | Realized R, number of tried variants | Later |
| 7 | Parameter nudge stability | Check that small parameter changes do not destroy the edge. | Strategy, bars, explicit params | Later |
| 8 | Cross-instrument validation | Check transfer to other instruments. | Strategy, bars for source and targets | Later |
| 9 | Market-data permutation | Test whether market sequence structure matters. | Strategy and bars | Later |
| 10 | BH-FDR / CSCV / White Reality Check | Correct broad campaign data-snooping. | Aligned campaign matrix | Much later |

## First Validator Contract

The first validators should consume only:

- `trades.csv`
- `summary.json`
- optional split metadata

Avoid validators that require a universal indicator surface.

## Split Assignment

Use validation trades and validation bars for overfitting tests. Discovery data
is already used for slicing, so it should not be used to prove a discovered
filter.

Trade-result tests:

- realized-R summary
- minimum trade count / low-sample warning
- Monte Carlo permutation
- Monte Carlo equity curves

Rerun-based tests:

- walk-forward inside the validation split
- filter-threshold nudge report
- market-data permutation, later
- cross-instrument validation after overfitting review

## Realized R Rule

Use mean `RealizedR` as the headline edge metric. Touch rates, target hits, and
counterfactual R levels can be useful diagnostics, but they should not override
realized trade outcomes.

Report 1R through 10R diagnostics when available. These diagnostics can reveal
rare high-upside behavior, but they are not allowed to silently replace the
declared headline metric.
