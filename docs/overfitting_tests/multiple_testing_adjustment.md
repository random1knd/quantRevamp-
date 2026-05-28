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
full_search_permutation_report(frame, spec, *, n_iter, random_seed)
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

The multiple-testing report is produced by `full_search_permutation_report`.
It receives the discovery input frame and the slicer spec because each
permutation must rerun the predeclared search, not rescore a cached selected
candidate.

Preferred search-adjusted evidence is a full-search permutation p-value. For
each permutation, shuffle `RealizedR` against the filter columns, rerun the
entire predeclared search, and store the maximum score found by that search.
Compare the real selected score to the distribution of permuted maximum scores.
Use a predeclared random seed and iteration count. Report p-values with
plus-one smoothing: `(1 + null_count_at_or_above_selected) / (1 + n_iter)`.

The current full-row shuffle is an i.i.d. / exchangeability diagnostic. It
adjusts for the declared rule grid, but it does not preserve session-level or
regime-level dependence in trade outcomes.

For a future positive candidate, the selection-adjusted p-value must use a
predeclared dependence-aware version before it is trusted as a promotion gate.
First policy: permute or resample at whole-session blocks while rerunning the
same predeclared search. If whole-session blocks are unusable, a contiguous
trade-block fallback must declare block length, circular versus non-circular
sampling, replicate sizing, `n_iter`, and `random_seed` before the candidate's
result is inspected.

Out-of-sample validation remains the main proof.

## Rule Search Helper

The predeclared one-column threshold search lives in:

```text
shared/validation/rule_search.py
```

Expected functions:

```text
build_threshold_rules(frame, spec)
score_rules(frame, rules, spec)
run_rule_search(frame, spec)
```

`multiple_testing.py` imports this helper so every permutation reruns the same
rule construction and scoring path used by the slicer.

`run_rule_search(frame, spec)` remains a pure search/scoring helper. It does
not enforce the real-candidate gate. The slicer artifact writer combines the
search result and `full_search_permutation_report` into `candidate_gate`; only
that artifact-layer gate can emit a real `candidate_selected` label.
