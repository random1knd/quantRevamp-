# Strategy Inventory

This is an idea inventory, not an implementation registry.

Nothing listed here should be treated as implemented until it has its own
self-contained strategy folder.

## Candidate Strategies

| Strategy | Core Thesis | Likely Inputs | Research Sources | Status |
|---|---|---|---|---|
| VWAP Z-Score Fade | Price stretched far from session VWAP often reverts toward fair value. | Session VWAP, VWAP distance, ATR, session maturity | `research/zscore_methods.md`, `research/advanced_data_points.md` | Research-only |
| Kalman VWAP Fade | A dynamic mean can adapt better than fixed VWAP or SMA during changing sessions. | Kalman mean, Kalman z-score, ATR, trend context | `research/kalman_filter.md`, `research/zscore_methods.md` | Research-only |
| O-U Z-Score Fade | Trades only when the observed process has measurable mean-reversion speed. | O-U theta, half-life, O-U z-score, ADF p-value | `research/ornstein_uhlenbeck.md`, `research/half_life.md`, `research/adf_test.md` | Research-only |
| Classic Absorption Fade | Strong directional flow with limited price progress can signal absorption and reversal. | VWAP distance, delta, absorption ratio, ATR | `research/order_flow_imbalance.md`, `research/triggers/absorption.md` | Research-only |
| Statistical Absorption Fade | Price extension plus extreme flow plus low toxicity should produce cleaner fades. | VWAP or O-U z-score, robust delta z-score, OFI, VPIN, AbsRatio | `research/vpin.md`, `research/order_flow_imbalance.md`, `research/zscore_methods.md` | Research-only |
| Half-Life Timed Fade | Mean-reversion trades should use expected reversion speed to size holding time and exits. | Half-life, O-U parameters, ATR, percentile extreme | `research/half_life.md`, `research/ornstein_uhlenbeck.md` | Research-only |
| Percentile Extreme Fade | Non-parametric extremes may be more stable than normal-distribution z-scores. | Rolling percentile, ATR, volatility context | `research/zscore_methods.md` | Research-only |
| Multi-Anchor VWAP Fade | Price far from several fair-value anchors is more stretched than distance from one anchor. | Session VWAP, anchored VWAPs, composite VWAP distance, ATR | `research/advanced_data_points.md` | Research-only |
| Value Area Fade | Price outside value area may revert toward accepted volume. | POC, VAH, VAL, distance from value area, volume profile | `research/advanced_data_points.md` | Research-only |
| Relative Strength Divergence Fade | NQ diverging from ES can mean temporary dislocation that later converges. | NQ/ES spread or relative-strength z-score, rolling correlation | `research/advanced_data_points.md` | Research-only |

## First Strategy Recommendation

Start with one strategy that is simple enough to debug end to end:

`VWAP Z-Score Fade` or `Classic Absorption Fade`.

Do not start with a combined framework. Build the chosen strategy directly,
record only the fields it needs, and add validation after the first run
artifacts are stable.

