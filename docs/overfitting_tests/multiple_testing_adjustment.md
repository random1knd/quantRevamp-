# Multiple-Testing Adjustment

Purpose:

- report how much discovery search was performed before one filter was chosen

## Inputs

- searched rule count
- searched columns
- slicer input population
- selection metric
- per-candidate selection-metric distribution
- discovery result for selected filter
- optional raw p-value estimate

## Code Shape

```text
shared/validation/multiple_testing.py
```

Expected function:

```text
multiple_testing_report(candidate_scores, selected_rule, method)
```

## Approach

First implementation requirements:

- searched rule count is mandatory
- the per-candidate score distribution is mandatory
- searched rule count uses concrete-rule granularity:
  `(column, threshold, direction, rule form)` is one searched rule
- evaluated rules that fail eligibility still count and should appear with
  their ineligible status
- report the selected rule's score and rank
- report a rough Bonferroni-style adjustment when a raw p-value exists
- do not make Bonferroni an automatic hard gate yet

Preferred search-adjusted evidence is a full-search permutation p-value. For
each permutation, shuffle `RealizedR` against the filter columns, rerun the
entire predeclared search, and store the maximum score found by that search.
Compare the real selected score to the distribution of permuted maximum scores.
Use a predeclared random seed and iteration count. Report p-values with
plus-one smoothing: `(1 + null_count_at_or_above_selected) / (1 + n_iter)`.

Out-of-sample validation remains the main proof.
