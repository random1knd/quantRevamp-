# Indicator Planning

This folder is the planning catalog for indicators and context features.

These docs do not define a universal bootstrap. They define reusable indicator
math and strategy-owned context recording.

## Available Bar Columns

After `prepare_bars`, every bar has:

```text
DateTime_ET, SessionDate_ET, SessionMinute_ET, BarGapFromPrevious,
IsFirstSessionAfterContractChange, Open, High, Low, Close, Volume,
BidVolume, AskVolume, Contract
```

Delta is computable as `AskVolume - BidVolume`.

No VIX, no implied volatility, no order book depth, no tick data.

## Core Rule

```text
shared math, not shared trading context
```

Shared indicator functions may exist under `shared/indicators/`.

Strategy trade decisions must call only the indicators explicitly used by that
strategy.

Post-trade research indicators are declared by the strategy in:

```text
strategies/<strategy_name>/parent/research_indicators.py
```

The context recorder reads that file only after `trades.csv` exists and writes
`context_trades.csv`.

## Planned Families

- [price_extension.md](price_extension.md)
- [zscore_family.md](zscore_family.md)
- [regime_statistical.md](regime_statistical.md)
- [ou_process.md](ou_process.md)
- [kalman.md](kalman.md)
- [trend_momentum.md](trend_momentum.md)
- [order_flow.md](order_flow.md)
- [liquidity_toxicity.md](liquidity_toxicity.md)
- [absorption_volume.md](absorption_volume.md)
- [volatility.md](volatility.md)
- [candle_time.md](candle_time.md)

## Porting Rule

Each accepted indicator must document:

- feature names
- why it is recorded
- required input columns
- explicit parameters
- causal behavior
- anchor/session behavior, if any
- bar-construction assumptions, if relevant
- whether it can be used for trading or context only
- test approach

Do not port all indicators at once. Port the smallest family needed for the
first strategy, then expand when a strategy README asks for more context.
