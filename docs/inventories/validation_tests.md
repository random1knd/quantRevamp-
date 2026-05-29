# Validation Test Inventory

Validation is the safest place to share code because it should consume standard
artifacts rather than strategy internals.

Detailed test plans live in `../overfitting_tests/`.

## Build Order

| Order | Test | Purpose | Input | Status |
|---|---|---|---|---|
| 1 | Realized-R summary | Establish basic expectancy, drawdown, and trade count. | `trades.csv` | BUILT; coverage-only on rejected child |
| 2 | Minimum sample check | Reject tiny samples before deeper validation. | Realized R series | BUILT; coverage-only on rejected child |
| 3 | Monte Carlo centered bootstrap | Test whether returns beat a zero-edge i.i.d. diagnostic null. | Realized R series | BUILT; diagnostic only |
| 4 | Monte Carlo equity curves | Estimate i.i.d. distribution of possible equity paths. | Realized R series | BUILT; diagnostic only |
| 5 | Block bootstrap engine | Dependence-aware promotion-grade mean-R gate. | Session-grouped Realized R series | BUILT engine-only; UNWIRED |
| 6 | Full-search i.i.d. permutation | Adjust slicer search for the declared rule grid. | Discovery slicer frame | BUILT; diagnostic/current slicer path |
| 7 | Block permutation engine | Dependence-aware promotion-grade search-significance gate. | Discovery slicer frame with session key | BUILT engine-only; UNWIRED |
| 8 | Walk-forward reruns | Check chronological generalization. | Bars plus strategy | BUILT; coverage-only on rejected child |
| 9 | Deflated Sharpe | Correct for non-normality and campaign size. | Realized R, score distribution, number of tried variants | UNAVAILABLE; slicer did not persist Sharpe/score distribution |
| 10 | Parameter nudge stability | Check that small parameter changes do not destroy the edge. | Strategy, bars, explicit params | BUILT; threshold-neighborhood and child-rerun nudge are coverage-only |
| 11 | Cross-instrument validation | Check transfer to other instruments. | Strategy, bars for source and targets | BUILT; coverage-only blueprint |
| 12 | Market-data permutation | Test whether market sequence structure matters. | Strategy and bars | BUILT; single-bar shuffle is coverage-only and invalid as a mean-reversion edge null |
| 13 | BH-FDR / CSCV / White Reality Check | Correct broad campaign data-snooping. | Aligned campaign matrix | Not planned for this explicit-strategy workflow |

Built does not mean wired for promotion. The dependence-aware block bootstrap
and block permutation engines are built cold so their math can be reviewed, but
they remain unwired until a real positive candidate and reviewed promotion
design exist.

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
