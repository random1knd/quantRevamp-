# Session Handoff — 2026-05-24

Point-in-time snapshot for resuming work. Overwrite/update each session; this is a
status snapshot, not a ledger. Active per-cycle review lives in `codexArg` / `claudeArg`.

## What this campaign is
A **workflow test**, not a profit claim. The parent strategy
(`vwap_zscore_fade`) loses money; the goal is to drive the full research pipeline
**end to end** (discover → slice → child → validate → overfitting → cross-instrument →
final test) with honest results at every stage. A losing/rejected outcome is a valid
completion.

## Pipeline progress
- [x] **Discovery** — parent run on the 30% split. Mean R ≈ −0.18 (completed_non_gap).
- [x] **Slicer** — single-column search, 42 rules. Verdict: **no_candidate** (best
      filter `SignalADX ≤ q30` still negative, −0.082R). Honest "no edge found".
- [x] **Demonstration child** — `children/adx_q30_workflow_test/`, hand-written, copies
      parent + adds ADX filter as real causal trade code. Labeled "NOT a discovered edge".
- [x] **Validation** — parent vs child on the 50% split. Child **rejected** (−0.14R,
      worse than the unfiltered parent −0.11R out-of-sample). Honest end-to-end result.
- [x] **Overfitting Stage B (CSV-based)** — realized-R summary, minimum_trade_count_policy,
      Monte Carlo significance (centered bootstrap, p=1.0 = no positive edge), equity-curve
      bootstrap (all paths drift down, P(positive)=0). All run coverage-only on the child.
- [ ] **Overfitting Stage C (rerun-based)** — parameter/threshold nudge (proposal
      reviewed, ready to implement), then walk_forward / time_stability. NEXT.
- [ ] **Stage D** — market-data permutation. Deferred.
- [ ] **Cross-instrument** — needs per-instrument constants (no NQ reuse).
- [ ] **Final 20% test** — NOT run. Decision required before touching it (see below).

## Code map (all under `shared/validation/` unless noted)
- `rule_search.py`, `multiple_testing.py` — slicer search + full-search permutation.
- `realized_r.py` — realized-R summary + `minimum_trade_count_policy` + the ONE canonical
  `max_drawdown_r` (used everywhere; no duplicates).
- `monte_carlo.py` — single-hypothesis centered bootstrap. `equity_curves.py` — i.i.d.
  equity-curve bootstrap.
- Strategy-local runners under `strategies/vwap_zscore_fade/`: `slicer_run.py`,
  `validation_run.py`, `validation_monte_carlo_run.py`, `validation_equity_curves_run.py`
  (+ `*_artifacts.py`). Specs live in `docs/overfitting_tests/`.

## State
- Tests: **306 passing**. Zero doc↔code naming drift (verified). Working tree clean.
- Latest commit `5a62917` (equity curves + drawdown consolidation), pushed to
  origin/master.
- Active next instructions for Codex: in `claudeArg` (Stage C threshold-nudge).

## What's next (resume here)
1. **Stage C — threshold nudge** (mechanism approved): add a keyword-only
   `adx_filter_threshold=None` override to the child's `generate_trades` (default = frozen
   threshold); strategy-local nudge runner over a predeclared grid (q20/q30/q40 ADX
   values); `shared/validation/threshold_nudge.py` stays PURE comparison (no strategy
   execution); report-only/judgment-only; coverage-only labels.
2. **Walk-forward / time_stability** after that.
3. Then cross-instrument, then the final-test decision.

## Standing governance reminders
- **Single-column is locked.** Combination/conjunction filters are a *future, separately
  predeclared campaign on fresh data* — never a retune of this one.
- **Do not retune to manufacture a candidate.** The slicer's no_candidate stands.
- **Final-test data is protected.** Do not burn the real 20% on the rejected demo child
  without an explicit, labeled decision; prefer exercising the final-test runner code on a
  fixture.
- **Roles:** Codex implements + writes `codexArg`; Claude reviews + writes `claudeArg`
  (both overwritten each cycle). Slicer/child/validation never touch final-test data.
- **Build discipline:** small green reviewable slices; doc↔code names matched from the
  start; reuse shared math, don't duplicate.
