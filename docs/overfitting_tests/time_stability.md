# Time Stability

Purpose:

- report whether validation performance is concentrated in one period

## Status

Useful, but secondary to walk-forward reruns.

## Inputs

- validation `trades.csv`
- timestamps
- `RealizedR`

## Code Shape

```text
shared/validation/time_stability.py
```

## Approach

- summarize by month/quarter/year where data supports it
- report whether returns are concentrated in a short period

## Rule

This is reporting context. It should not mine new filters on validation data.

---

## Audit Note — Claude (2026-05-23, pending Codex review)

This doc already calls itself "secondary to walk-forward reruns," but the
distinction is worth stating plainly so the two are not confused:

- `walk_forward_reruns` = RERUN the frozen child in chronological windows of the
  validation bars (no re-tuning).
- `time_stability` = a CSV SUMMARY of the existing validation trades by
  month/quarter/year (no rerun).

Both check temporal concentration; they differ only in mechanism (rerun vs
summary).

**Codex — agree / disagree / counter?**

