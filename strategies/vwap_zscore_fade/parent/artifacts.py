from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from strategies.vwap_zscore_fade.parent import params
from strategies.vwap_zscore_fade.parent.strategy import Trade


ROOT = Path(__file__).resolve().parents[3]

REQUIRED_TRADE_COLUMNS = (
    "EntryTime",
    "ExitTime",
    "Side",
    "EntryPrice",
    "ExitPrice",
    "InitialStopPrice",
    "InitialRisk",
    "RealizedR_Gross",
    "RealizedR_Net",
    "RealizedR",
    "ExitReason",
    "BarsHeld",
    "SignalTime",
    "SignalATR",
    "EntryZ",
    "EntrySessionVWAP",
    "EntryVWAPDeviation",
    "Contract",
    "CommissionIsSmokeTest",
    "GapThrough",
)


def write_parent_artifacts(
    *,
    trades: list[Trade],
    output_dir: str | Path,
    run_type: str,
    split: str,
    data_start: str,
    data_end: str,
    input_data_paths: list[str | Path],
    strategy_version: str,
    code_version: str,
    random_seed: int,
    exclude_roll_sessions: bool,
    commission_per_round_turn: float,
    commission_is_smoke_test: bool,
) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    input_data = _input_data_metadata(input_data_paths)
    run_config = _run_config(
        run_type=run_type,
        split=split,
        data_start=data_start,
        data_end=data_end,
        input_data=input_data,
        strategy_version=strategy_version,
        code_version=code_version,
        random_seed=random_seed,
        exclude_roll_sessions=exclude_roll_sessions,
        commission_per_round_turn=commission_per_round_turn,
        commission_is_smoke_test=commission_is_smoke_test,
    )

    _write_trades_csv(output_path / "trades.csv", trades)
    _write_json(output_path / "run_config.json", run_config)
    _write_json(
        output_path / "summary.json",
        _summary(
            trades=trades,
            run_type=run_type,
            split=split,
            data_start=data_start,
            data_end=data_end,
            exclude_roll_sessions=exclude_roll_sessions,
            commission_per_round_turn=commission_per_round_turn,
            commission_is_smoke_test=commission_is_smoke_test,
        ),
    )


def _write_trades_csv(path: Path, trades: list[Trade]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=REQUIRED_TRADE_COLUMNS)
        writer.writeheader()
        for trade in trades:
            writer.writerow(_trade_row(trade))


def _trade_row(trade: Trade) -> dict[str, Any]:
    return {
        "EntryTime": _serialize(trade.entry_time),
        "ExitTime": _serialize(trade.exit_time),
        "Side": trade.side,
        "EntryPrice": trade.entry_price,
        "ExitPrice": trade.exit_price,
        "InitialStopPrice": trade.initial_stop_price,
        "InitialRisk": trade.initial_risk,
        "RealizedR_Gross": trade.realized_r_gross,
        "RealizedR_Net": trade.realized_r_net,
        "RealizedR": trade.realized_r,
        "ExitReason": trade.exit_reason,
        "BarsHeld": trade.bars_held,
        "SignalTime": _serialize(trade.signal_time),
        "SignalATR": trade.signal_atr,
        "EntryZ": trade.entry_z,
        "EntrySessionVWAP": trade.entry_session_vwap,
        "EntryVWAPDeviation": trade.entry_vwap_deviation,
        "Contract": trade.contract,
        "CommissionIsSmokeTest": trade.commission_is_smoke_test,
        "GapThrough": trade.gap_through,
    }


def _run_config(
    *,
    run_type: str,
    split: str,
    data_start: str,
    data_end: str,
    input_data: dict[str, Any],
    strategy_version: str,
    code_version: str,
    random_seed: int,
    exclude_roll_sessions: bool,
    commission_per_round_turn: float,
    commission_is_smoke_test: bool,
) -> dict[str, Any]:
    return {
        "campaign_id": None,
        "strategy_name": params.STRATEGY_NAME,
        "strategy_version": strategy_version,
        "run_type": run_type,
        "instrument": params.INSTRUMENT,
        "timeframe": params.TIMEFRAME,
        "split": split,
        "data_start": data_start,
        "data_end": data_end,
        "declared_session_open": params.SESSION_OPEN,
        "post_open_no_trade_minutes": params.NO_ENTRY_BEFORE_SESSION_MINUTE,
        "parameter_snapshot": _parameter_snapshot(
            exclude_roll_sessions=exclude_roll_sessions
        ),
        "random_seed": random_seed,
        "code_version": code_version,
        "input_data_sha256": input_data["sha256"],
        "input_data_bytes": input_data["bytes"],
        "input_data_is_repo_relative": input_data["is_repo_relative"],
        "non_reproducible_input_paths": input_data["non_reproducible_paths"],
        "slippage_model": _slippage_model(),
        "commission_model": _commission_model(
            commission_per_round_turn=commission_per_round_turn,
            commission_is_smoke_test=commission_is_smoke_test,
        ),
        "point_value": params.NQ_POINT_VALUE,
    }


def _summary(
    *,
    trades: list[Trade],
    run_type: str,
    split: str,
    data_start: str,
    data_end: str,
    exclude_roll_sessions: bool,
    commission_per_round_turn: float,
    commission_is_smoke_test: bool,
) -> dict[str, Any]:
    realized = [trade.realized_r for trade in trades]
    return {
        "strategy_name": params.STRATEGY_NAME,
        "instrument": params.INSTRUMENT,
        "timeframe": params.TIMEFRAME,
        "run_type": run_type,
        "split": split,
        "data_start": data_start,
        "data_end": data_end,
        "declared_session_open": params.SESSION_OPEN,
        "post_open_no_trade_minutes": params.NO_ENTRY_BEFORE_SESSION_MINUTE,
        "parameter_snapshot": _parameter_snapshot(
            exclude_roll_sessions=exclude_roll_sessions
        ),
        "trade_count": len(trades),
        "mean_realized_r": _mean(realized),
        "win_rate": _win_rate(realized),
        "max_drawdown_r": _max_drawdown(realized),
        "r_multiple_diagnostics": _r_multiple_diagnostics(realized),
        "incomplete_trade_count": sum(
            1 for trade in trades if trade.exit_reason == "end_of_data"
        ),
        "slippage_model": _slippage_model(),
        "commission_model": _commission_model(
            commission_per_round_turn=commission_per_round_turn,
            commission_is_smoke_test=commission_is_smoke_test,
        ),
        "standalone_child_credibility_status": None,
        "parent_comparison_status": None,
    }


def _parameter_snapshot(*, exclude_roll_sessions: bool | None = None) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "entry_z_threshold": params.ENTRY_Z_THRESHOLD,
        "z_window": params.Z_WINDOW,
        "signal_min_bars": params.SIGNAL_MIN_BARS,
        "volume_z_window": params.VOLUME_Z_WINDOW,
        "atr_window": params.ATR_WINDOW,
        "stop_atr_multiple": params.STOP_ATR_MULTIPLE,
        "max_bars_held": params.MAX_BARS_HELD,
        "no_entry_before_session_minute": params.NO_ENTRY_BEFORE_SESSION_MINUTE,
        "no_entry_at_or_after_session_minute": params.NO_ENTRY_AT_OR_AFTER_SESSION_MINUTE,
        "last_rth_bar_open_session_minute": params.LAST_RTH_BAR_OPEN_SESSION_MINUTE,
        "session_force_flat_minute": params.SESSION_FORCE_FLAT_MINUTE,
    }
    if exclude_roll_sessions is not None:
        snapshot["exclude_roll_sessions"] = exclude_roll_sessions
    return snapshot


def _slippage_model() -> dict[str, Any]:
    return {
        "model": "fixed_ticks_per_side",
        "ticks_per_side": params.SLIPPAGE_TICKS_PER_SIDE,
        "tick_size": params.NQ_TICK_SIZE,
    }


def _commission_model(
    *,
    commission_per_round_turn: float,
    commission_is_smoke_test: bool,
) -> dict[str, Any]:
    return {
        "model": "round_turn_currency",
        "commission_per_round_turn": commission_per_round_turn,
        "commission_is_smoke_test": commission_is_smoke_test,
    }


def _input_data_metadata(paths: list[str | Path]) -> dict[str, Any]:
    sha256: dict[str, str] = {}
    byte_counts: dict[str, int] = {}
    is_repo_relative = True
    non_reproducible_paths: list[str] = []

    for path_value in paths:
        path = Path(path_value).resolve()
        key, repo_relative = _input_key(path)
        is_repo_relative = is_repo_relative and repo_relative
        if not repo_relative:
            non_reproducible_paths.append(key)
        sha256[key] = _sha256(path)
        byte_counts[key] = path.stat().st_size

    return {
        "sha256": sha256,
        "bytes": byte_counts,
        "is_repo_relative": is_repo_relative,
        "non_reproducible_paths": non_reproducible_paths,
    }


def _input_key(path: Path) -> tuple[str, bool]:
    try:
        return path.relative_to(ROOT).as_posix(), True
    except ValueError:
        return str(path), False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _win_rate(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(1 for value in values if value > 0.0) / len(values)


def _max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return max_drawdown


def _r_multiple_diagnostics(values: list[float]) -> dict[str, int]:
    return {
        f"{threshold}R_or_better": sum(1 for value in values if value >= threshold)
        for threshold in range(1, 11)
    }


def _serialize(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
