# Sweep-Based Parameter Stability

Purpose:

- check whether performance is a plateau or a narrow spike when a true sweep
  exists

## Status

Later.

Do not build this until the new repo has intentional sweep campaigns.

## Inputs

- aligned sweep results
- selected candidate
- declared sweep dimensions

## Code Shape

```text
shared/validation/sweep_stability.py
```

## Rule

Do not recreate the old broad config sweep system just to enable this test.

