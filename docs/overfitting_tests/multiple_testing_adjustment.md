# Multiple-Testing Adjustment

Purpose:

- report how much discovery search was performed before one filter was chosen

## Inputs

- searched rule count
- selection metric
- discovery result for selected filter
- optional p-value estimate

## Code Shape

```text
shared/validation/multiple_testing.py
```

Expected function:

```text
multiple_testing_report(raw_p_value, searched_rule_count, method)
```

## Approach

First implementation can be simple:

- searched rule count is mandatory
- report a rough Bonferroni-style adjustment when a p-value exists
- do not make it an automatic hard gate yet

Out-of-sample validation remains the main proof.

