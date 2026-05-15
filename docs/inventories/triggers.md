# Trigger Inventory

Triggers are timing ideas. They should not become a global trigger registry.

If a strategy uses one of these, implement it locally first. Extract a shared
function only after repeated use proves the interface is stable.

| Trigger | What It Tries To Detect | Typical Use | Research Note | Status |
|---|---|---|---|---|
| Absorption | Aggressive flow is absorbed and price stalls. | Time entries after a stretched move fails to continue. | `research/triggers/absorption.md` | Research-only |
| Delta Reversal | Per-bar delta flips away from the prior push. | Confirm that aggressive buyers or sellers are no longer dominant. | `research/triggers/delta_reversal.md` | Research-only |
| Flow Exhaustion | Delta velocity peaked and is now decelerating. | Enter as order-flow pressure loses acceleration. | `research/triggers/flow_exhaustion.md` | Research-only |
| OFI Flip | Order-flow imbalance changes sign. | Confirm that flow supporting the extension has reversed. | `research/triggers/ofi_flip.md` | Research-only |
| Candle Rejection | A wick rejects an extreme in the fade direction. | Add price-action timing to a stretched setup. | `research/triggers/candle_rejection.md` | Research-only |
| Momentum Deceleration | Short-horizon price momentum fades from an extreme. | Avoid entering while the push is still accelerating. | `research/triggers/momentum_deceleration.md` | Research-only |
| Volume Climax | A high-volume bar is followed by contraction. | Identify capitulation or exhaustion near an extreme. | `research/triggers/volume_climax.md` | Research-only |

## Trigger Rule

A trigger can improve timing, but it does not replace the strategy thesis.
Direction, risk, and exit behavior still belong to the strategy.

