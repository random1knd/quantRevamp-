# Repo Working Rules

This repo is being rebuilt from scratch because the previous version became too
dependent on bootstrap layers, broad local helpers, global defaults,
registries, manifests, and hidden invariants.

When working in this repo:

- build one explicit strategy end to end before adding broad framework code
- prefer small pure shared math over shared trading context
- keep strategy behavior inside the strategy folder
- do not create universal setup, trigger, filter, bootstrap, registry, ledger,
  or current-state orchestration layers
- do not add hidden global defaults; the only current default gate is no new
  entries during the first 60 minutes after the declared session open
- port indicators only when an active strategy or validator needs them
- keep research-context indicators separate from trade-generating code
- convert slicer discoveries into explicit child strategies before they affect
  trades
- validate frozen children out of sample before promotion
- the VWAP z-score fade on master is a worked structural reference, not a
  strategy template; strategy logic and assumptions must be restated fresh on
  each new strategy branch (see `docs/workflow.md` section 7)

If a requested change would introduce broad abstraction or hidden behavior, stop
and make that tradeoff explicit before implementing it.

## Package Policy

This repo intentionally uses namespace packages for now. Do not add
`__init__.py` files only for ceremony; add them only if a concrete tool or
runtime behavior requires regular packages.

## Test Checkpoint Policy

Commits and handoffs must be green. Intermediate local red-test failures are
allowed while implementing a slice, but do not commit or hand off that red
state. Use `importorskip` only when a red test file must exist across turns
before its implementation lands.

## Strategy Boundary Tests

Boundary tests scan all `.py` files under `strategies/` except
`research_indicators.py`. This protects future strategy-local helper files by
default while keeping research-context code separate from trade-generating code.

## Review Argument Files

Follow `ARGUMENT_REVIEW_PROTOCOL.md`.

After making a repo change, and before proposing a meaningful next change,
overwrite `codexArg` with a short explanation of what changed, why, touched
files, assumptions, and remaining risks.

Claude or another reviewer should use `claudeArg` for its response. These files
are overwritten each time and are not a ledger.

## Reviewable In Isolation

Keep files small enough to review with only:

- the touched file
- its focused test file
- `codexArg`
- the directly relevant README or spec

Apply this to new code files from this point forward. Do not create busywork by
rewriting existing files only to satisfy this rule.

For new code files:

- use one narrow responsibility
- add focused tests near the behavior
- keep shared files mechanical or pure math
- use the relevant implementation plan as the boundary spec
- avoid repeating boundary rules in module docstrings unless the function needs
  a concrete precondition note

Cross-file review is always required for:

- public function signature changes
- new or removed output columns from data preparation functions
- changed exception types or message strings that tests match
