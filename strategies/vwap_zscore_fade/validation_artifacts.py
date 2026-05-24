from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Sequence


TRADE_COLUMNS = (
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
    "SignalZ",
    "SignalSessionVWAP",
    "SignalVWAPDeviation",
    "Contract",
    "CommissionIsSmokeTest",
    "GapThrough",
    "HoldCrossesGap",
)


def write_validation_artifacts(
    *,
    output_dir: str | Path,
    parent_trades: Sequence[Any],
    child_trades: Sequence[Any],
    validation_report: dict[str, Any],
    run_config: dict[str, Any],
) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=False)

    _write_trades_csv(output_path / "parent_trades.csv", parent_trades)
    _write_trades_csv(output_path / "child_trades.csv", child_trades)
    _write_json(output_path / "validation_report.json", validation_report)
    _write_json(output_path / "run_config.json", run_config)


def _write_trades_csv(path: Path, trades: Sequence[Any]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRADE_COLUMNS)
        writer.writeheader()
        for trade in trades:
            writer.writerow(_trade_row(trade))


def _trade_row(trade: Any) -> dict[str, Any]:
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
        "SignalZ": trade.entry_z,
        "SignalSessionVWAP": trade.entry_session_vwap,
        "SignalVWAPDeviation": trade.entry_vwap_deviation,
        "Contract": trade.contract,
        "CommissionIsSmokeTest": trade.commission_is_smoke_test,
        "GapThrough": trade.gap_through,
        "HoldCrossesGap": trade.hold_crosses_gap,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(_json_value(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if hasattr(value, "item"):
        return _json_value(value.item())
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _serialize(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
