# VWAP Z-Score Fade Implementation Plan

This plan exists to prevent early helper drift.

The next implementation should build one runnable parent strategy without
creating a framework around it. Shared code is allowed only when it is
mechanical or pure math.

## Current Concern

"Small helpers" can quietly become hidden policy.

This repo should not start by extracting generic session, strategy, filter,
campaign, or orchestration helpers. Those are the paths that can recreate the
previous repo's bootstrap behavior.

For the first runnable version, strategy policy belongs in this strategy folder
unless there is a clear reason to share pure math or mechanical data parsing.

## First Runnable Parent Scope

Build only:

- NQ 5-minute parent strategy
- RTH-only strategy behavior
- one bar-preparation path
- session VWAP
- VWAP deviation z-score
- ATR stop
- tracking VWAP target
- 12-bar time stop
- simple trades artifact
- simple summary artifact

Do not build:

- strategy registry
- setup / trigger / filter registry
- session-policy framework
- campaign engine
- automatic child creation
- slicer integration
- cross-instrument validation
- parameter sweep
- dashboard or CLI

## Proposed File Map

```text
shared/data/bars.py
shared/indicators/vwap.py
shared/indicators/volatility.py
strategies/vwap_zscore_fade/parent/README.md
strategies/vwap_zscore_fade/parent/IMPLEMENTATION_PLAN.md
strategies/vwap_zscore_fade/parent/indicators.py
strategies/vwap_zscore_fade/parent/params.py
strategies/vwap_zscore_fade/parent/strategy.py
shared/execution/simulator.py
shared/execution/runner.py
tests/
```

This is a planning map, not permission to implement all files in one pass.

Each file should be introduced only when the next test or runnable step needs
it.

## File Boundaries

### `shared/data/bars.py`

Already started.

Allowed:

- validate required raw bar columns
- parse source timestamps
- derive timezone-aware timestamp fields
- derive session date/minute facts
- mark contract-roll sessions

Not allowed:

- filter RTH rows automatically
- skip roll sessions automatically
- decide entry gates
- compute strategy indicators
- know about this strategy

### `shared/indicators/vwap.py`

Allowed:

- pure VWAP math from explicit price, volume, and group/session inputs
- caller must provide rows already scoped to the intended session universe
- caller must provide the session grouping key
- no strategy defaults
- no RTH filtering
- no contract-roll filtering

Not allowed:

- choose the session clock
- reset at 09:30 by itself
- decide which rows are tradable
- know about NQ or this strategy

### `shared/indicators/volatility.py`

Allowed:

- pure true range and ATR math from explicit OHLC inputs
- caller-controlled grouping/reset behavior
- caller must provide rows already scoped to the intended session universe
- caller must provide the session grouping key when reset behavior is needed

Not allowed:

- choose stop multiples
- choose RTH rows
- know about entries or exits

### `strategies/vwap_zscore_fade/parent/indicators.py`

Allowed:

- call pure shared indicator math
- apply this strategy's RTH/session-reset choices
- compute only the parent strategy's required trading indicators and declared
  research context fields

Not allowed:

- import slicer output
- apply child filters
- compute a universal indicator surface

### `strategies/vwap_zscore_fade/parent/params.py`

Allowed:

- hold explicit constants from the strategy README

Examples:

- `ENTRY_Z_THRESHOLD = 2.0`
- `Z_WINDOW = 20`
- `SIGNAL_MIN_BARS = 20`
- `ATR_WINDOW = 14`
- `STOP_ATR_MULTIPLE = 1.5`
- `MAX_BARS_HELD = 12`
- `NO_ENTRY_BEFORE_SESSION_MINUTE = 60`
- `NO_ENTRY_AT_OR_AFTER_SESSION_MINUTE = 360`
- `LAST_SESSION_BAR_MINUTE = 385`
- `SESSION_FORCE_FLAT_MINUTE = 390`

Not allowed:

- load dynamic config
- infer defaults
- read campaign state

### `strategies/vwap_zscore_fade/parent/strategy.py`

Allowed:

- own entry logic
- own stop logic
- own target logic
- own time/session exit logic
- enforce one open trade at a time
- accept `exclude_roll_sessions: bool` as an explicit named argument
- apply roll-session exclusion only when `exclude_roll_sessions` is true

Expected first interface:

```text
generate_trades(bars, params, exclude_roll_sessions) -> list[Trade]
```

Do not replace the explicit boolean with a generic config dict.

Not allowed:

- import `shared.context`
- import `shared.slicing`
- import child strategy modules
- use any slicer-discovered filter
- delegate strategy meaning to a generic framework

### `shared/execution/simulator.py`

Allowed:

- mechanical fills
- slippage
- commission
- realized-R calculation
- stop/target conflict behavior from `docs/simulator_spec.md`

Not allowed:

- decide entries
- apply session gates
- apply filters
- choose strategy parameters

### `shared/execution/runner.py`

Allowed:

- call one explicit strategy
- receive a plain strategy callable, not discover one
- call simulator
- write `trades.csv`, `summary.json`, and `run_config.json`

Expected first interface:

```text
run_strategy(strategy_callable, bars, params, output_dir, exclude_roll_sessions)
```

Not allowed:

- discover strategies
- run slicer automatically
- run validation automatically
- create child strategies
- mutate parameters

## Testing Order

Use test-first only for the next needed boundary.

Suggested order:

1. finish `shared/data/bars.py` tests and strict validation
2. write pure VWAP tests
3. write pure ATR tests
4. write parent indicator integration tests on tiny hand-made bars
5. write parent strategy behavior tests for one long and one short signal
6. write simulator tests only when strategy intent objects exist

Do not write broad boundary tests before the code surface exists.

`shared/data/splits.py` is intentionally deferred. It becomes required before
discovery, validation, or final-test runs, but it is not needed for the first
single parent smoke run.

When `shared/execution/simulator.py` is proposed, its tests must cover the
cases listed in `docs/simulator_spec.md`, including long/short wins and stops,
gap-through behavior, same-bar stop/target conflict, slippage, commission, and
incomplete tail trades.

## Review Rule

Follow the file isolation and review scope rules in `AGENTS.md`.

Before each new file is added:

1. Codex writes the intended file and reason in `codexArg`.
2. Claude reviews whether the file is necessary and scoped.
3. Only then should the file be implemented.

If a proposed file looks like a generic helper that could hide policy, pause
and keep the behavior inside the strategy until repeated stable duplication
proves sharing is worth it.
