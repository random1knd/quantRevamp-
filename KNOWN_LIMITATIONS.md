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
