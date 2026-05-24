# Campaign Governance

This document defines what a research campaign is and how slicer searches are
bounded.

## Campaign Identity

A campaign is bound to:

- parent strategy name
- strategy version
- source instrument
- timeframe
- discovery split date range
- validation split date range
- final-test split date range
- slicer plan
- random seed

Changing any of these creates a different campaign.

Campaign id format:

```text
<strategy_slug>__<instrument>__<timeframe>__<discovery_start>_<discovery_end>
```

Use ISO dates in the date fields. If that slug would collide, append a short
explicit suffix such as `__v2`; do not silently reuse an existing campaign id.

## One Generation Rule

One split campaign can create only one child generation.

If a child passes and you want a second filter layer, you must either:

- accept the child as final for this campaign, or
- start a new campaign with fresh data or explicitly new split ranges

Do not mine the same discovery, validation, or final-test data for a second
filter layer.

## Failed Campaigns

If a child fails validation or overfitting review, the campaign must be retired
or marked failed with a written reason.

Do not rerun the slicer on the same strategy, instrument, and split range and
call it a new campaign unless the strategy thesis itself changes and that
change is documented before rerunning discovery.

## Slicer Plan

Before discovery slicing, the campaign must define a slicer plan.

The slicer plan must state:

- input population
- searchable columns
- threshold grid or candidate rules
- rule form and direction set
- missing-value handling
- selection metric
- minimum post-filter trade count
- maximum searched rule count, if a cap is used
- multiple-testing adjustment method

The slicer must not choose its search space after inspecting results.

The current default input population is `completed_non_gap`: rows where
`ExitReason != end_of_data` and `HoldCrossesGap == false`. A campaign may use a
different population only if that choice is documented before slicing.

`searched rule count` means every concrete evaluated rule. For threshold
searches, one concrete rule is the full tuple that defines a decision boundary,
such as `(column, threshold, direction, rule form)`. A five-column search with
seven thresholds and two directions is therefore `5 * 7 * 2 = 70` searched
rules. Rules that are evaluated and then fail eligibility, such as a minimum
trade-count floor, still count as searched rules.

Selection metrics must be sample-adequate central-tendency or risk-adjusted
measures. Examples include mean `RealizedR`, median `RealizedR`, Sharpe-like
statistics, or drawdown-adjusted return when predeclared. Extremum-driven
metrics are not allowed for slicer selection: do not optimize on max single
trade, best tail event, highest 10R touch, or any objective where one outlier can
choose the child.

## Filter Candidate Artifact

The selected candidate must record:

- campaign id
- slicer input population
- selected rule
- selection metric
- searched columns
- searched rule count
- per-candidate selection-metric distribution
- multiple-testing adjustment report
- pre-filter and post-filter trade count
- realized-R summary
- 1R through 10R diagnostics when available

`searched rule count` and the per-candidate selection-metric distribution are
mandatory. The distribution must include every searched rule's selection score,
not just the selected winner, so DSR and full-search permutation validation can
be reproduced.
