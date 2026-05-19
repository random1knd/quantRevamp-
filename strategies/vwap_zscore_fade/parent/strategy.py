from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from strategies.vwap_zscore_fade.parent import params
from strategies.vwap_zscore_fade.parent.indicators import add_parent_indicators


Side = Literal["long", "short"]

REQUIRED_COLUMNS = (
    "DateTime_ET",
    "SessionDate_ET",
    "SessionMinute_ET",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "BidVolume",
    "AskVolume",
    "Contract",
    "IsFirstSessionAfterContractChange",
)


@dataclass(frozen=True)
class Trade:
    entry_time: Any
    exit_time: Any
    side: Side
    entry_price: float
    exit_price: float
    initial_stop_price: float
    initial_risk: float
    realized_r_gross: float
    realized_r_net: float
    realized_r: float
    exit_reason: str
    bars_held: int
    signal_time: Any
    signal_atr: float
    entry_z: float
    entry_session_vwap: float
    entry_vwap_deviation: float
    contract: str
    commission_is_smoke_test: bool
    gap_through: bool = False


@dataclass(frozen=True)
class _OpenTrade:
    side: Side
    signal_pos: int
    entry_pos: int
    entry_price: float
    initial_stop_price: float
    initial_risk: float


def generate_trades(
    bars: pd.DataFrame,
    *,
    exclude_roll_sessions: bool,
    commission_per_round_turn: float,
    commission_is_smoke_test: bool,
) -> list[Trade]:
    _validate_required_columns(bars)
    _validate_commission(
        commission_per_round_turn=commission_per_round_turn,
        commission_is_smoke_test=commission_is_smoke_test,
    )

    prepared = add_parent_indicators(bars)
    rth_bar_number = _rth_bar_number(prepared)

    trades: list[Trade] = []
    signal_pos = 0
    while signal_pos < len(prepared) - 1:
        side = _entry_side(prepared.iloc[signal_pos])
        if side is None or not _entry_allowed(
            prepared,
            rth_bar_number=rth_bar_number,
            signal_pos=signal_pos,
            exclude_roll_sessions=exclude_roll_sessions,
        ):
            signal_pos += 1
            continue

        open_trade = _open_trade(
            prepared,
            side=side,
            signal_pos=signal_pos,
            entry_pos=signal_pos + 1,
        )
        if open_trade is None:
            signal_pos += 1
            continue

        trade, exit_pos = _close_trade(
            prepared,
            open_trade=open_trade,
            commission_per_round_turn=commission_per_round_turn,
            commission_is_smoke_test=commission_is_smoke_test,
        )
        trades.append(trade)
        signal_pos = exit_pos + 1

    return trades


def _validate_required_columns(bars: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in bars.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")


def _validate_commission(
    *,
    commission_per_round_turn: float,
    commission_is_smoke_test: bool,
) -> None:
    if commission_per_round_turn < 0.0:
        raise ValueError("commission_per_round_turn must be non-negative")

    if commission_per_round_turn == 0.0 and not commission_is_smoke_test:
        raise ValueError("zero commission requires smoke-test label")


def _rth_bar_number(bars: pd.DataFrame) -> pd.Series:
    rth = bars["SessionMinute_ET"].between(
        params.RTH_START_SESSION_MINUTE,
        params.LAST_RTH_BAR_OPEN_SESSION_MINUTE,
    )
    counts = pd.Series(index=bars.index, dtype="float64")
    counts.loc[rth] = bars.loc[rth].groupby("SessionDate_ET", sort=False).cumcount() + 1
    return counts


def _entry_side(signal_bar: pd.Series) -> Side | None:
    entry_z = signal_bar["EntryZ"]
    if pd.isna(entry_z):
        return None

    if entry_z <= -params.ENTRY_Z_THRESHOLD:
        return "long"

    if entry_z >= params.ENTRY_Z_THRESHOLD:
        return "short"

    return None


def _entry_allowed(
    bars: pd.DataFrame,
    *,
    rth_bar_number: pd.Series,
    signal_pos: int,
    exclude_roll_sessions: bool,
) -> bool:
    signal_bar = bars.iloc[signal_pos]
    entry_bar = bars.iloc[signal_pos + 1]

    if signal_bar["SessionDate_ET"] != entry_bar["SessionDate_ET"]:
        return False

    if pd.isna(rth_bar_number.iloc[signal_pos]):
        return False

    if rth_bar_number.iloc[signal_pos] < params.SIGNAL_MIN_BARS:
        return False

    if pd.isna(signal_bar["ATR"]) or signal_bar["ATR"] <= 0.0:
        return False

    if not (
        params.NO_ENTRY_BEFORE_SESSION_MINUTE
        <= entry_bar["SessionMinute_ET"]
        < params.NO_ENTRY_AT_OR_AFTER_SESSION_MINUTE
    ):
        return False

    if exclude_roll_sessions and bool(signal_bar["IsFirstSessionAfterContractChange"]):
        return False

    return True


def _open_trade(
    bars: pd.DataFrame,
    *,
    side: Side,
    signal_pos: int,
    entry_pos: int,
) -> _OpenTrade | None:
    signal_bar = bars.iloc[signal_pos]
    entry_bar = bars.iloc[entry_pos]
    slippage = _slippage_points()

    if side == "long":
        entry_price = float(entry_bar["Open"]) + slippage
        initial_stop_price = entry_price - params.STOP_ATR_MULTIPLE * float(
            signal_bar["ATR"]
        )
    else:
        entry_price = float(entry_bar["Open"]) - slippage
        initial_stop_price = entry_price + params.STOP_ATR_MULTIPLE * float(
            signal_bar["ATR"]
        )

    initial_risk = abs(entry_price - initial_stop_price)
    if initial_risk <= 0.0:
        return None

    return _OpenTrade(
        side=side,
        signal_pos=signal_pos,
        entry_pos=entry_pos,
        entry_price=entry_price,
        initial_stop_price=initial_stop_price,
        initial_risk=initial_risk,
    )


def _close_trade(
    bars: pd.DataFrame,
    *,
    open_trade: _OpenTrade,
    commission_per_round_turn: float,
    commission_is_smoke_test: bool,
) -> tuple[Trade, int]:
    last_same_session_pos = _last_same_session_pos(
        bars,
        start_pos=open_trade.entry_pos,
    )

    for exit_pos in range(open_trade.entry_pos, last_same_session_pos + 1):
        exit_result = _exit_result(
            bars.iloc[exit_pos],
            open_trade=open_trade,
            bars_held=exit_pos - open_trade.entry_pos + 1,
        )
        if exit_result is not None:
            return (
                _build_trade(
                    bars,
                    open_trade=open_trade,
                    exit_pos=exit_pos,
                    exit_price=exit_result["exit_price"],
                    exit_reason=exit_result["exit_reason"],
                    gap_through=exit_result["gap_through"],
                    commission_per_round_turn=commission_per_round_turn,
                    commission_is_smoke_test=commission_is_smoke_test,
                ),
                exit_pos,
            )

    exit_pos = last_same_session_pos
    return (
        _build_trade(
            bars,
            open_trade=open_trade,
            exit_pos=exit_pos,
            exit_price=_close_exit_price(
                bars.iloc[exit_pos]["Close"],
                side=open_trade.side,
            ),
            exit_reason="end_of_data",
            gap_through=False,
            commission_per_round_turn=commission_per_round_turn,
            commission_is_smoke_test=commission_is_smoke_test,
        ),
        exit_pos,
    )


def _last_same_session_pos(
    bars: pd.DataFrame,
    *,
    start_pos: int,
) -> int:
    session_date = bars.iloc[start_pos]["SessionDate_ET"]
    last_pos = start_pos
    for pos in range(start_pos, len(bars)):
        if bars.iloc[pos]["SessionDate_ET"] != session_date:
            break
        last_pos = pos
    return last_pos


def _exit_result(
    bar: pd.Series,
    *,
    open_trade: _OpenTrade,
    bars_held: int,
) -> dict[str, float | str | bool] | None:
    stop_result = _stop_exit_result(bar, open_trade=open_trade)
    if stop_result is not None:
        return stop_result

    target_result = _target_exit_result(bar, open_trade=open_trade)
    if target_result is not None:
        return target_result

    if bars_held >= params.MAX_BARS_HELD:
        return {
            "exit_price": _close_exit_price(bar["Close"], side=open_trade.side),
            "exit_reason": "time_stop",
            "gap_through": False,
        }

    if bar["SessionMinute_ET"] >= params.LAST_RTH_BAR_OPEN_SESSION_MINUTE:
        return {
            "exit_price": _close_exit_price(bar["Close"], side=open_trade.side),
            "exit_reason": "session_end",
            "gap_through": False,
        }

    return None


def _stop_exit_result(
    bar: pd.Series,
    *,
    open_trade: _OpenTrade,
) -> dict[str, float | str | bool] | None:
    stop = open_trade.initial_stop_price
    slippage = _slippage_points()

    if open_trade.side == "long":
        if bar["Open"] < stop:
            return {
                "exit_price": float(bar["Open"]),
                "exit_reason": "gap_stop",
                "gap_through": True,
            }
        if bar["Low"] <= stop:
            return {
                "exit_price": stop - slippage,
                "exit_reason": "stop",
                "gap_through": False,
            }
    else:
        if bar["Open"] > stop:
            return {
                "exit_price": float(bar["Open"]),
                "exit_reason": "gap_stop",
                "gap_through": True,
            }
        if bar["High"] >= stop:
            return {
                "exit_price": stop + slippage,
                "exit_reason": "stop",
                "gap_through": False,
            }

    return None


def _target_exit_result(
    bar: pd.Series,
    *,
    open_trade: _OpenTrade,
) -> dict[str, float | str | bool] | None:
    target = bar["SessionVWAP"]
    if pd.isna(target):
        return None

    if open_trade.side == "long" and bar["High"] >= target:
        gap_through = bool(bar["Open"] >= target)
        return {
            "exit_price": float(target)
            if gap_through
            else float(target) - _slippage_points(),
            "exit_reason": "target",
            "gap_through": gap_through,
        }

    if open_trade.side == "short" and bar["Low"] <= target:
        gap_through = bool(bar["Open"] <= target)
        return {
            "exit_price": float(target)
            if gap_through
            else float(target) + _slippage_points(),
            "exit_reason": "target",
            "gap_through": gap_through,
        }

    return None


def _close_exit_price(price: float, *, side: Side) -> float:
    if side == "long":
        return float(price) - _slippage_points()

    return float(price) + _slippage_points()


def _build_trade(
    bars: pd.DataFrame,
    *,
    open_trade: _OpenTrade,
    exit_pos: int,
    exit_price: float,
    exit_reason: str,
    gap_through: bool,
    commission_per_round_turn: float,
    commission_is_smoke_test: bool,
) -> Trade:
    signal_bar = bars.iloc[open_trade.signal_pos]
    entry_bar = bars.iloc[open_trade.entry_pos]
    exit_bar = bars.iloc[exit_pos]
    gross_r = _gross_r(
        side=open_trade.side,
        entry_price=open_trade.entry_price,
        exit_price=exit_price,
        initial_risk=open_trade.initial_risk,
    )
    commission_points = commission_per_round_turn / params.NQ_POINT_VALUE
    net_r = (gross_r * open_trade.initial_risk - commission_points) / (
        open_trade.initial_risk
    )

    return Trade(
        entry_time=entry_bar["DateTime_ET"],
        exit_time=_exit_time(exit_bar, exit_reason=exit_reason),
        side=open_trade.side,
        entry_price=open_trade.entry_price,
        exit_price=exit_price,
        initial_stop_price=open_trade.initial_stop_price,
        initial_risk=open_trade.initial_risk,
        realized_r_gross=gross_r,
        realized_r_net=net_r,
        realized_r=net_r,
        exit_reason=exit_reason,
        bars_held=exit_pos - open_trade.entry_pos + 1,
        signal_time=signal_bar["DateTime_ET"],
        signal_atr=float(signal_bar["ATR"]),
        entry_z=float(signal_bar["EntryZ"]),
        entry_session_vwap=float(signal_bar["SessionVWAP"]),
        entry_vwap_deviation=float(signal_bar["VWAPDeviation"]),
        contract=str(signal_bar["Contract"]),
        commission_is_smoke_test=commission_is_smoke_test,
        gap_through=gap_through,
    )


def _exit_time(exit_bar: pd.Series, *, exit_reason: str) -> Any:
    if exit_reason in {"time_stop", "session_end", "end_of_data"}:
        return exit_bar["DateTime_ET"] + pd.Timedelta(
            minutes=params.BAR_INTERVAL_MINUTES
        )

    return exit_bar["DateTime_ET"]


def _gross_r(
    *,
    side: Side,
    entry_price: float,
    exit_price: float,
    initial_risk: float,
) -> float:
    if side == "long":
        return (exit_price - entry_price) / initial_risk

    return (entry_price - exit_price) / initial_risk


def _slippage_points() -> float:
    return params.SLIPPAGE_TICKS_PER_SIDE * params.NQ_TICK_SIZE
