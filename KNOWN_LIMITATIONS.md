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
  realized R magnitudes can look marginally larger than an unrounded model would
  produce.

What it actually is:

- A sub-tick consequence of the documented conservative rounding policy (see the
  strategy README "Fill And Cost Assumptions"). Because the stop always rounds
  toward entry, `InitialRisk` is rounded down by up to one tick, and `RealizedR`
  divides by `InitialRisk`, so |R| is inflated by at most ~1-2% of risk.

Why the current behavior is accepted:

- The bias is one-directional but sub-tick and applies to both winning and losing
  tails, so its effect on headline mean R is negligible and not systematically
  favorable. The fill-realism benefit (never modeling a stop wider than intended)
  is judged to outweigh it for v0.

What would justify a different approach:

- A move to a tick-accurate execution model, or evidence that the R-denominator
  bias materially changes a slicing or validation decision.

## Some Research Columns Are Not Session-Grouped But Are Clean At Every Signal Bar

What it looks like:

- An audit can show that five research columns — `SignalVolRatio`,
  `SignalVolRobustZ`, `SignalATRPctile`, `SignalVPIN`, `SignalKyleLambdaPctile` —
  are not session-grouped, so on the first bars of a session they compute values
  whose rolling window spans the overnight boundary (e.g. `SignalVolRatio` ≈ 6.9
  on the first bar of a high-volume session, dividing today's open volume by a
  mean that is mostly yesterday's bars). This looks like the same cross-session
  contamination that was a real bug in `SignalEfficiencyRatio` (fixed under audit
  finding F1).

What it actually is:

- It is NOT the same, and it does not reach the data. Research columns are joined
  to trades by `SignalTime`, and a signal can only occur at RTH bar
  >= `SIGNAL_MIN_BARS` (the first ~20 bars of every session produce no signal).
  So the contaminated early-session values are never joined to any trade — they
  are dropped before `context_trades.csv` is written.
- The reason these specific columns are safe is the operation type. They use a
  rolling WINDOW of length <= `SIGNAL_MIN_BARS`; the window ending at the first
  eligible signal bar (cumcount 19) spans exactly that session's first 20 bars —
  fully in-session. Verified by recomputing grouped vs. ungrouped on the real
  discovery data: byte-identical at every signal-eligible bar (max |diff| = 0.0),
  with zero signal bars where ungrouped produced a value and grouped would be NaN.
- Contrast with `SignalEfficiencyRatio` (F1): it used a LOOKBACK DIFF,
  `diff(SIGNAL_MIN_BARS)`, which AT cumcount 19 reaches cumcount -1 (the prior
  session). That is why it was a genuine bug and the rolling-window columns are
  not. The rule: a rolling window of length <= `SIGNAL_MIN_BARS` is clean at the
  signal bar; a lookback/diff of length == `SIGNAL_MIN_BARS` is not.

Why the current behavior is correct:

- Every value that actually enters `context_trades.csv` (the signal-bar value) is
  in-session-clean. The contamination is confined to bars that are never evaluated
  as signals, so no slice and no research result is affected.

Related — gap-masking:

- Only `EntryZ` and `SignalVolumeZ` apply `gap_free_rolling_window`; the other
  research columns can compute across an intra-session data gap. The same join
  gate mitigates this: a valid signal already requires a gap-free 20-bar `EntryZ`
  window, which structurally protects every research column whose window <= 20 AT
  the signal bar. The only residual is `SignalADX`, whose Wilder memory exceeds 20
  bars (open decision; see the review loop / claudeArg S7).

What would justify a different approach (and the one assumption to watch):

- This safety holds ONLY while every research window is <= `SIGNAL_MIN_BARS`. If a
  research window is ever set larger than `SIGNAL_MIN_BARS`, its rolling window
  WOULD reach into the prior session at the signal bar and the column would need
  session-grouping. Re-verify this property whenever `SIGNAL_MIN_BARS` or any
  research window changes.
- A consistency/defensiveness improvement — session-group all research columns and
  add one parametrized "every research column resets at the session boundary"
  test — is proposed in the review loop (claudeArg S1). It would change zero joined
  values but make the invariant uniform and self-enforcing rather than dependent on
  the window-vs-gate coincidence above. That is an open decision, not a required
  correction.
