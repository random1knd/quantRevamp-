# Known Limitations

These items have been investigated and closed as intentional architecture
decisions. Do not reopen them as bugs unless the assumptions below change.

## Time Stop Exits Up To 5 Minutes Late On Gapped Data

What it looks like:

- Smoke or discovery artifacts can show time stops recorded at 65 elapsed
  minutes instead of exactly 60 minutes.

What it actually is:

- This is a bar-resolution artifact, not a bug. The strategy exits at the close
  of the first bar where `_bar_close_time(bar) - entry_time >= 60 minutes`.
  When the historical file is missing the bar that would close exactly at 60
  minutes, the next available bar closes one interval later.

Why the current behavior is correct:

- This is a bar-based backtest, so the strategy can only exit on bars that
  exist. Time-stop exits use bar-close fills. The overshoot is bounded by one
  declared bar interval. In live trading, bars should not be missing, so this is
  a historical-data artifact.

What would justify a different approach:

- A tick-level model, or an explicit decision to use open fills for time stops
  only. That fill-model change is not warranted for the current discovery
  phase.

## Runners Pre-Filter To RTH Before `prepare_bars()`

What it looks like:

- `smoke_run.py` and `discovery_run.py` filter raw bars to RTH rows before
  calling `prepare_bars()`, which can look like a workaround for the loader.

What it actually is:

- This is intentional input scoping for an RTH-only strategy. The full source
  file is ETH-shaped and can contain old and new contract labels on the same
  calendar date around roll dates. `prepare_bars()` correctly rejects
  multi-contract sessions as a data integrity violation.

Why the current behavior is correct:

- `prepare_bars()` is a strict validator. The runners are responsible for
  handing it the session universe appropriate for the strategy. For this parent
  strategy, that universe is RTH-only, single-contract-per-session data.

What would justify a different approach:

- An ETH strategy, or another strategy that explicitly needs to handle
  contract changes inside a session, would need a separate loader or an explicit
  contract-roll policy before validation.

## `BarGapFromPrevious` Flags Any Non-Expected Interval

What it looks like:

- `BarGapFromPrevious` is true when a same-session bar interval differs from
  `expected_bar_interval_minutes`, including intervals shorter than expected.

What it actually is:

- This is intentional. The flag means the interval from the previous bar does
  not match the declared bar interval. Longer intervals imply missing bars;
  shorter intervals imply sub-expected-resolution data.

Why the current behavior is correct:

- The invariant is that same-session intervals must equal the declared
  `expected_bar_interval_minutes`. Duplicate timestamps are already rejected, so
  sub-expected intervals should not occur in normal input, but the symmetric
  definition keeps the invariant explicit.

What would justify a different approach:

- A strategy that intentionally mixes bar resolutions inside a session would
  need a direction-aware or strategy-specific gap classification.

## Percentile Research Columns Are Sparse Early In Each Session

What it looks like:

- `SignalATRPctile` and `SignalKyleLambdaPctile` are missing (NaN) for a large
  share of trades in `context_trades.csv` (about 27% and 39% respectively in the
  discovery artifact). Trades that signal early in the session almost always have
  a blank value for these two columns.

What it actually is:

- This is intentional and correct, not a missing computation. `rolling_percentile`
  ranks a bar against its trailing `window` peers, so it needs `window + 1`
  observations. It is stacked on top of the underlying indicator's own warmup
  (ATR needs 14 session bars before producing a value; Kyle lambda needs a full
  20-bar covariance window). The two warmups compound, so the first valid
  percentile lands well into the session.

Why the current behavior is correct:

- A percentile with too few reference observations would be meaningless. NaN is
  the honest output, consistent with every other research column that returns NaN
  before its window is satisfied. No value is fabricated.

What would justify a different approach:

- Nothing for slicing correctness. The practical consequence is a coverage one:
  any slice predicated on `SignalATRPctile` or `SignalKyleLambdaPctile` is
  effectively restricted to later-session trades. The slicer plan should treat
  these two columns as lower-coverage candidates rather than expect them to span
  the whole trade population.

## Conservative Stop Rounding Slightly Inflates R Magnitude

What it looks like:

- Stops are rounded toward entry (long stops up, short stops down), so the
  realized R magnitudes can look larger than an unrounded model would produce.

What it actually is:

- A sub-tick consequence of the documented conservative rounding policy (see the
  strategy README "Fill And Cost Assumptions"). Because the stop always rounds
  toward entry, `InitialRisk` is rounded down by up to one tick, and `RealizedR`
  divides by `InitialRisk`, so |R| magnitude is inflated. The mean effect is
  small, but the tail is materially larger than a flat 1-2% because the
  percentage impact is largest when ATR/risk is small.

Measured on the judged `completed_non_gap` population:

- discovery: mean 2.06%, p95 5.36%, max 17.86%
- validation-parent: mean 0.72%, p95 2.32%, max 8.21%

Using an unrounded denominator estimate does not rescue the edge: discovery
mean R moves from -0.17771 to -0.17363, and validation-parent mean R moves from
-0.11476 to -0.11365.

Why the current behavior is accepted:

- The bias is one-directional but sub-tick and applies to both winning and
  losing tails, so its effect on headline mean R is small and not systematically
  favorable. The fill-realism benefit (never modeling a stop wider than
  intended) is judged to outweigh it for v0.

What would justify a different approach:

- A move to a tick-accurate execution model, or evidence that the R-denominator
  bias materially changes a slicing or validation decision.
- Any future positive edge claim should report the full measured rounding-impact
  distribution, not a flat 1-2% shorthand.

## Same-Session Gaps Leave Session VWAP Based On Observed Bars

What it looks like:

- A trade can signal after an earlier same-session data gap. Its `EntryZ` window
  is gap-free, but its cumulative `SessionVWAP` and fixed target are still based
  on all observed bars since the session open, excluding any missing bars.

What it actually is:

- `SessionVWAP` is an expanding cumulative calculation over the rows that exist
  in the source data. The current v0 strategy does not reconstruct missing bars,
  split sessions at a gap, or reject every later same-session signal after a
  data hole.

Why the current behavior is accepted:

- The current VWAP z-score campaign is a negative workflow-test campaign, not an
  edge claim. Read-only audit counts found a small but nonzero exposure: 19
  discovery headline trades and 24 validation-parent headline trades signaled
  after an earlier same-session gap. This can help or hurt individual trades; it
  is not assumed to be a directional edge inflator.

What would justify a different approach:

- Any future positive edge claim should report this exposure before promotion.
  If the affected trades are material to the conclusion, the campaign should
  either exclude post-gap same-session signals or define an explicit session
  split/reset policy before accepting the result.

## Research Columns Are Session-Grouped And Clean At Every Signal Bar

What it looks like:

- Older audit notes described five research columns - `SignalVolRatio`,
  `SignalVolRobustZ`, `SignalATRPctile`, `SignalVPIN`, and
  `SignalKyleLambdaPctile` - as having early-session cross-boundary
  rolling-window contamination.

What it actually is:

- The S1 consistency improvement is implemented. These columns are now
  session-grouped in `research_indicators.py`, so the old first-bar
  cross-boundary example is obsolete; the first bar of each session is now NaN
  for these rolling columns.
- Research columns are still joined to trades by `SignalTime`, and a signal can
  only occur at RTH bar >= `SIGNAL_MIN_BARS` (the first ~20 bars of every
  session produce no signal). The previous signal-row safety property still
  holds, but it is now enforced structurally by session grouping rather than by
  a window-vs-entry-gate coincidence.
- Recomputing grouped vs. ungrouped values on the real discovery data confirmed
  that joined signal-row values are identical to floating-point precision:
  `SignalVolRatio`, `SignalVolRobustZ`, `SignalATRPctile`, and
  `SignalKyleLambdaPctile` had max |diff| = 0.0; `SignalVPIN` differed only by
  floating noise around 1e-16.
- Contrast with `SignalEfficiencyRatio` (F1): it used a LOOKBACK DIFF,
  `diff(SIGNAL_MIN_BARS)`, which at cumcount 19 reaches cumcount -1 (the prior
  session). That is why it was a genuine bug and the rolling-window columns are
  not. The rule: a rolling window of length <= `SIGNAL_MIN_BARS` is clean at the
  signal bar; a lookback/diff of length == `SIGNAL_MIN_BARS` is not.

Why the current behavior is correct:

- Every value that actually enters `context_trades.csv` (the signal-bar value) is
  in-session-clean. Current code also keeps these rolling research columns
  session-scoped before the join, so no slice and no research result is affected.

Related - gap-masking:

- Only `EntryZ` and `SignalVolumeZ` apply `gap_free_rolling_window`; the other
  research columns can compute across an intra-session data gap. The same join
  gate mitigates this: a valid signal already requires a gap-free 20-bar `EntryZ`
  window, which structurally protects every research column whose window <= 20
  at the signal bar. The only residual is `SignalADX`, whose Wilder memory
  exceeds 20 bars (open decision; see the review loop / claudeArg S7).

What would justify a different approach:

- The session-grouping invariant should stay covered if `SIGNAL_MIN_BARS` or any
  research window changes. A future research column with longer memory should
  declare whether it is session-scoped or intentionally cross-session before it
  enters slicer context.
