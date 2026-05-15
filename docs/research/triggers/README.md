# Trigger Research Notes

This folder stores timing ideas for mean-reversion strategies.

The notes are source material only. They are not a global trigger registry.
When a strategy uses one of these ideas, implement the timing logic inside that
strategy first. Extract a shared helper only after repeated use proves the
interface.

## Notes

- `absorption.md`: aggressive flow is absorbed and price stalls.
- `delta_reversal.md`: per-bar delta flips away from the prior push.
- `flow_exhaustion.md`: delta velocity peaks and decelerates.
- `ofi_flip.md`: order-flow imbalance changes sign.
- `candle_rejection.md`: wick rejection at a price extreme.
- `momentum_deceleration.md`: price momentum fades from an extreme.
- `volume_climax.md`: volume spike followed by contraction.

The curated trigger inventory is at `../../inventories/triggers.md`.

