# Deflated Sharpe Ratio

Purpose:

- adjust Sharpe-like evidence for non-normal returns and multiple testing

## Inputs

- validation `RealizedR`
- number of searched or tested variants
- skewness
- kurtosis

## Code Shape

```text
shared/validation/deflated_sharpe.py
```

Expected function:

```text
deflated_sharpe(realized_r, n_trials)
```

## Approach

- compute observed Sharpe-like statistic from realized R
- estimate adjustment using skewness, kurtosis, sample length, and trial count

## Rule

Do not fake `n_trials=1` when the slicer searched many rules. Use the mandatory
searched rule count where applicable.

---

## Audit Note — Claude (2026-05-23, pending Codex review)

`deflated_sharpe(realized_r, n_trials)` cannot compute the DSR from a trial COUNT
alone. The Bailey/Lopez de Prado expected-maximum-Sharpe benchmark also needs the
VARIANCE of the trial Sharpe ratios, plus a defined Sharpe statistic. Suggested
build:

- Define the statistic: per-trade Sharpe = `mean(RealizedR) / std(RealizedR)`
  (trade-based, not annualized).
- Compute skewness and kurtosis from `realized_r` internally (the inputs list
  them; the signature can derive them).
- Supply the trial-Sharpe variance — e.g. the variance of the candidate Sharpes
  the slicer evaluated during its search. The signature likely needs that input,
  not just `n_trials`.

**Codex — agree / disagree / counter?** Where should the trial-Sharpe variance
come from in our pipeline? Fold in and delete this note once settled.

