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

- searchable columns
- threshold grid or candidate rules
- selection metric
- minimum post-filter trade count
- maximum searched rule count, if a cap is used
- multiple-testing adjustment method

The slicer must not choose its search space after inspecting results.

## Filter Candidate Artifact

The selected candidate must record:

- campaign id
- selected rule
- selection metric
- searched columns
- searched rule count
- multiple-testing adjustment report
- pre-filter and post-filter trade count
- realized-R summary
- 1R through 10R diagnostics when available

`searched rule count` is mandatory.
