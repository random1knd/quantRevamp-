import csv
import json
from pathlib import Path

import pandas as pd

from strategies.vwap_zscore_fade.parent.artifacts import (
    REQUIRED_TRADE_COLUMNS,
    write_parent_artifacts,
)
from strategies.vwap_zscore_fade.parent.strategy import Trade


OUTPUT_ROOT = Path("data/results/test_artifacts")


def make_trade(
    *,
    realized_r: float,
    exit_reason: str = "target",
    side: str = "long",
) -> Trade:
    return Trade(
        entry_time=pd.Timestamp("2026-01-02 11:10:00", tz="America/New_York"),
        exit_time=pd.Timestamp("2026-01-02 11:15:00", tz="America/New_York"),
        side=side,
        entry_price=100.25,
        exit_price=102.0,
        initial_stop_price=98.0,
        initial_risk=2.25,
        realized_r_gross=realized_r,
        realized_r_net=realized_r,
        realized_r=realized_r,
        exit_reason=exit_reason,
        bars_held=1,
        signal_time=pd.Timestamp("2026-01-02 11:05:00", tz="America/New_York"),
        signal_atr=1.5,
        entry_z=-2.5,
        entry_session_vwap=101.0,
        entry_vwap_deviation=-1.0,
        contract="NQH26",
        commission_is_smoke_test=True,
        gap_through=False,
    )


def write_artifacts(*, case_name: str, trades: list[Trade]):
    case_dir = OUTPUT_ROOT / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    input_file = case_dir / "NQ_sample.csv"
    input_file.write_text("DateTime,Open\n2026-01-02 14:30:00,100\n")
    output_dir = case_dir / "run"

    write_parent_artifacts(
        trades=trades,
        output_dir=output_dir,
        run_type="smoke",
        split="train",
        data_start="2026-01-02",
        data_end="2026-01-03",
        input_data_paths=[input_file],
        strategy_version="test-version",
        code_version="test-code",
        random_seed=123,
        exclude_roll_sessions=True,
        commission_per_round_turn=0.0,
        commission_is_smoke_test=True,
    )
    return output_dir, input_file


def test_write_parent_artifacts_writes_required_trade_columns_and_run_config():
    output_dir, input_file = write_artifacts(
        case_name="required_columns",
        trades=[make_trade(realized_r=1.25)],
    )

    with (output_dir / "trades.csv").open(newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows
    assert list(rows[0].keys()) == list(REQUIRED_TRADE_COLUMNS)
    assert rows[0]["EntryTime"] == "2026-01-02T11:10:00-05:00"
    assert rows[0]["Side"] == "long"
    assert rows[0]["RealizedR"] == "1.25"
    assert rows[0]["CommissionIsSmokeTest"] == "True"

    run_config = json.loads((output_dir / "run_config.json").read_text())
    input_key = input_file.as_posix()
    assert run_config["strategy_name"] == "vwap_zscore_fade"
    assert run_config["run_type"] == "smoke"
    assert run_config["split"] == "train"
    assert run_config["random_seed"] == 123
    assert run_config["code_version"] == "test-code"
    assert run_config["input_data_sha256"][input_key]
    assert run_config["input_data_bytes"][input_key] == input_file.stat().st_size
    assert run_config["input_data_is_repo_relative"] is True
    assert run_config["slippage_model"]["ticks_per_side"] == 1
    assert run_config["commission_model"]["commission_per_round_turn"] == 0.0


def test_write_parent_artifacts_writes_summary_metrics():
    output_dir, _ = write_artifacts(
        case_name="summary_metrics",
        trades=[
            make_trade(realized_r=1.0),
            make_trade(realized_r=-0.5, exit_reason="stop"),
            make_trade(realized_r=2.0),
            make_trade(realized_r=0.0, exit_reason="end_of_data"),
        ],
    )

    summary = json.loads((output_dir / "summary.json").read_text())

    assert summary["strategy_name"] == "vwap_zscore_fade"
    assert summary["instrument"] == "NQ"
    assert summary["timeframe"] == "5min"
    assert summary["trade_count"] == 4
    assert summary["mean_realized_r"] == 0.625
    assert summary["win_rate"] == 0.5
    assert summary["max_drawdown_r"] == 0.5
    assert summary["incomplete_trade_count"] == 1
    assert summary["r_multiple_diagnostics"]["1R_or_better"] == 2
    assert summary["r_multiple_diagnostics"]["2R_or_better"] == 1
