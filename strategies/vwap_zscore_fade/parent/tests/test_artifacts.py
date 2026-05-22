import csv
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from strategies.vwap_zscore_fade.parent import artifacts
from strategies.vwap_zscore_fade.parent.artifacts import (
    REQUIRED_TRADE_COLUMNS,
    write_parent_artifacts,
)
from strategies.vwap_zscore_fade.parent.strategy import Trade


SCRATCH_ROOT = Path(".test_artifacts/parent_artifact_tests")


@pytest.fixture
def artifact_scratch(request):
    path = SCRATCH_ROOT / request.node.name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        for parent in (SCRATCH_ROOT, SCRATCH_ROOT.parent):
            try:
                parent.rmdir()
            except OSError:
                pass


def make_trade(
    *,
    realized_r: float,
    exit_reason: str = "target",
    side: str = "long",
    hold_crosses_gap: bool = False,
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
        hold_crosses_gap=hold_crosses_gap,
    )


def write_artifacts(scratch_path: Path, trades: list[Trade]):
    input_file = scratch_path / "NQ_sample.csv"
    input_file.write_text("DateTime,Open\n2026-01-02 14:30:00,100\n")
    output_dir = scratch_path / "run"

    write_parent_artifacts(
        trades=trades,
        output_dir=output_dir,
        run_type="smoke",
        split="train",
        data_start="2026-01-02",
        data_end="2026-01-03",
        input_data_paths=[input_file],
        campaign_id="test-campaign",
        commission_source="test commission source",
        source_timezone_rationale="test timezone rationale",
        rth_filter_note="test rth filter note",
        strategy_version="test-version",
        code_version="test-code",
        random_seed=123,
        exclude_roll_sessions=True,
        commission_per_round_turn=0.0,
        commission_is_smoke_test=True,
        bar_gap_count=2,
        bar_gap_session_count=1,
    )
    return output_dir, input_file


def test_write_parent_artifacts_writes_required_trade_columns_and_run_config(
    artifact_scratch,
):
    output_dir, input_file = write_artifacts(
        artifact_scratch,
        trades=[make_trade(realized_r=1.25)],
    )

    with (output_dir / "trades.csv").open(newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows
    assert list(rows[0].keys()) == list(REQUIRED_TRADE_COLUMNS)
    assert rows[0]["EntryTime"] == "2026-01-02T11:10:00-05:00"
    assert rows[0]["Side"] == "long"
    assert rows[0]["RealizedR"] == "1.25"
    assert rows[0]["SignalZ"] == "-2.5"
    assert rows[0]["CommissionIsSmokeTest"] == "True"
    assert rows[0]["HoldCrossesGap"] == "False"

    run_config = json.loads((output_dir / "run_config.json").read_text())
    input_key = input_file.resolve().relative_to(artifacts.ROOT).as_posix()
    assert run_config["strategy_name"] == "vwap_zscore_fade"
    assert run_config["campaign_id"] == "test-campaign"
    assert run_config["run_type"] == "smoke"
    assert run_config["split"] == "train"
    assert run_config["random_seed"] == 123
    assert run_config["code_version"] == "test-code"
    assert run_config["input_data_sha256"][input_key]
    assert run_config["input_data_bytes"][input_key] == input_file.stat().st_size
    assert run_config["input_data_is_repo_relative"] is True
    assert run_config["data_quality"] == {
        "bar_gap_count": 2,
        "bar_gap_session_count": 1,
    }
    assert run_config["runner_rationale"] == {
        "commission_source": "test commission source",
        "source_timezone_rationale": "test timezone rationale",
        "rth_filter_note": "test rth filter note",
    }
    assert run_config["slippage_model"]["ticks_per_side"] == 1
    assert run_config["commission_model"]["commission_per_round_turn"] == 0.0

    summary = json.loads((output_dir / "summary.json").read_text())
    assert summary["parameter_snapshot"] == run_config["parameter_snapshot"]
    assert summary["parameter_snapshot"]["exclude_roll_sessions"] is True


def test_write_parent_artifacts_writes_summary_metrics(artifact_scratch):
    output_dir, _ = write_artifacts(
        artifact_scratch,
        trades=[
            make_trade(realized_r=1.0),
            make_trade(realized_r=-0.5, exit_reason="stop"),
            make_trade(realized_r=2.0, hold_crosses_gap=True),
            make_trade(realized_r=-10.0, exit_reason="end_of_data"),
        ],
    )

    summary = json.loads((output_dir / "summary.json").read_text())

    assert summary["strategy_name"] == "vwap_zscore_fade"
    assert summary["instrument"] == "NQ"
    assert summary["timeframe"] == "5min"
    assert summary["trade_count"] == 4
    assert summary["completed_trade_count"] == 3
    assert summary["non_gap_trade_count"] == 2
    assert summary["gap_trade_count"] == 1
    assert summary["headline_sample"] == "completed_non_gap_trades"
    assert summary["mean_realized_r"] == pytest.approx(0.25)
    assert summary["win_rate"] == pytest.approx(0.5)
    assert summary["max_drawdown_r"] == 0.5
    assert summary["all_completed_mean_realized_r"] == pytest.approx(2.5 / 3.0)
    assert summary["all_completed_win_rate"] == pytest.approx(2.0 / 3.0)
    assert summary["gap_trade_mean_r"] == 2.0
    assert summary["gap_trade_win_rate"] == 1.0
    assert summary["incomplete_trade_count"] == 1
    assert summary["r_multiple_diagnostics"]["1R_or_better"] == 1
    assert summary["r_multiple_diagnostics"]["2R_or_better"] == 0


def test_write_parent_artifacts_handles_empty_trades(artifact_scratch):
    output_dir, _ = write_artifacts(artifact_scratch, trades=[])

    with (output_dir / "trades.csv").open(newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows == []

    summary = json.loads((output_dir / "summary.json").read_text())
    assert summary["trade_count"] == 0
    assert summary["completed_trade_count"] == 0
    assert summary["non_gap_trade_count"] == 0
    assert summary["gap_trade_count"] == 0
    assert summary["headline_sample"] == "completed_non_gap_trades"
    assert summary["mean_realized_r"] is None
    assert summary["win_rate"] is None
    assert summary["max_drawdown_r"] is None
    assert summary["all_completed_mean_realized_r"] is None
    assert summary["all_completed_win_rate"] is None
    assert summary["gap_trade_mean_r"] is None
    assert summary["gap_trade_win_rate"] is None
    assert summary["incomplete_trade_count"] == 0
    assert all(value == 0 for value in summary["r_multiple_diagnostics"].values())


def test_write_parent_artifacts_raises_on_zero_commission_without_smoke_label(
    artifact_scratch,
):
    input_file = artifact_scratch / "NQ_sample.csv"
    input_file.write_text("DateTime,Open\n2026-01-02 14:30:00,100\n")
    output_dir = artifact_scratch / "run"

    with pytest.raises(ValueError, match="zero commission requires smoke-test label"):
        write_parent_artifacts(
            trades=[make_trade(realized_r=1.0)],
            output_dir=output_dir,
            run_type="discovery",
            split="train",
            data_start="2026-01-02",
            data_end="2026-01-03",
            input_data_paths=[input_file],
            campaign_id="test-campaign",
            commission_source="test commission source",
            source_timezone_rationale="test timezone rationale",
            rth_filter_note="test rth filter note",
            strategy_version="test-version",
            code_version="test-code",
            random_seed=123,
            exclude_roll_sessions=True,
            commission_per_round_turn=0.0,
            commission_is_smoke_test=False,
            bar_gap_count=0,
            bar_gap_session_count=0,
        )

    assert not output_dir.exists()


@pytest.mark.parametrize(
    ("bar_gap_count", "bar_gap_session_count", "message"),
    [
        (-1, 0, "bar_gap_count must be non-negative"),
        (0, -1, "bar_gap_session_count must be non-negative"),
    ],
)
def test_write_parent_artifacts_rejects_negative_gap_counts(
    artifact_scratch,
    bar_gap_count,
    bar_gap_session_count,
    message,
):
    input_file = artifact_scratch / "NQ_sample.csv"
    input_file.write_text("DateTime,Open\n2026-01-02 14:30:00,100\n")
    output_dir = artifact_scratch / "run"

    with pytest.raises(ValueError, match=message):
        write_parent_artifacts(
            trades=[make_trade(realized_r=1.0)],
            output_dir=output_dir,
            run_type="discovery",
            split="train",
            data_start="2026-01-02",
            data_end="2026-01-03",
            input_data_paths=[input_file],
            campaign_id="test-campaign",
            commission_source="test commission source",
            source_timezone_rationale="test timezone rationale",
            rth_filter_note="test rth filter note",
            strategy_version="test-version",
            code_version="test-code",
            random_seed=123,
            exclude_roll_sessions=True,
            commission_per_round_turn=5.16,
            commission_is_smoke_test=False,
            bar_gap_count=bar_gap_count,
            bar_gap_session_count=bar_gap_session_count,
        )

    assert not output_dir.exists()


def test_write_parent_artifacts_rejects_blank_campaign_id(artifact_scratch):
    input_file = artifact_scratch / "NQ_sample.csv"
    input_file.write_text("DateTime,Open\n2026-01-02 14:30:00,100\n")
    output_dir = artifact_scratch / "run"

    with pytest.raises(ValueError, match="campaign_id must not be blank"):
        write_parent_artifacts(
            trades=[make_trade(realized_r=1.0)],
            output_dir=output_dir,
            run_type="discovery",
            split="train",
            data_start="2026-01-02",
            data_end="2026-01-03",
            input_data_paths=[input_file],
            campaign_id=" ",
            commission_source="test commission source",
            source_timezone_rationale="test timezone rationale",
            rth_filter_note="test rth filter note",
            strategy_version="test-version",
            code_version="test-code",
            random_seed=123,
            exclude_roll_sessions=True,
            commission_per_round_turn=5.16,
            commission_is_smoke_test=False,
            bar_gap_count=0,
            bar_gap_session_count=0,
        )

    assert not output_dir.exists()


def test_write_parent_artifacts_marks_non_repo_relative_inputs(
    artifact_scratch,
    monkeypatch,
):
    fake_repo_root = artifact_scratch / "fake_repo_root"
    fake_repo_root.mkdir()
    monkeypatch.setattr(artifacts, "ROOT", fake_repo_root)

    output_dir, input_file = write_artifacts(
        artifact_scratch,
        trades=[make_trade(realized_r=1.0)],
    )

    run_config = json.loads((output_dir / "run_config.json").read_text())
    input_key = str(input_file.resolve())

    assert run_config["input_data_is_repo_relative"] is False
    assert run_config["non_reproducible_input_paths"] == [input_key]
