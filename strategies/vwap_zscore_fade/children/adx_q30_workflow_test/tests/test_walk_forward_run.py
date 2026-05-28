import csv
from datetime import date
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pandas as pd
import pytest

from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import params
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import (
    walk_forward_run,
)


SCRATCH_ROOT = Path(".test_artifacts/child_walk_forward_tests")


@pytest.fixture
def scratch(request):
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


def trade(
    realized_r: float,
    *,
    exit_reason: str = "target",
    hold_crosses_gap: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        realized_r=realized_r,
        exit_reason=exit_reason,
        hold_crosses_gap=hold_crosses_gap,
    )


def test_walk_forward_runner_uses_whole_session_windows_and_frozen_child(
    scratch,
    monkeypatch,
):
    validation_bars = _validation_bars([date(2026, 1, day) for day in range(2, 10)])
    splits = {
        "discovery_end": date(2026, 1, 1),
        "validation_end": date(2026, 1, 9),
        "test_end": date(2026, 1, 10),
        "discovery_session_count": 1,
        "validation_session_count": 8,
        "test_session_count": 1,
    }
    seen_sessions = []

    def fake_generate_trades(
        bars,
        *,
        exclude_roll_sessions,
        commission_per_round_turn,
        commission_is_smoke_test,
    ):
        seen_sessions.append(list(bars["SessionDate_ET"].drop_duplicates()))
        return [trade(-0.25)]

    monkeypatch.setattr(
        walk_forward_run,
        "load_validation_bars",
        lambda: (validation_bars, splits),
    )
    monkeypatch.setattr(
        walk_forward_run,
        "generate_child_trades",
        fake_generate_trades,
    )
    monkeypatch.setattr(
        walk_forward_run,
        "_adx_restrictiveness_summary",
        lambda bars, *, exclude_roll_sessions: {
            "adx_kept_count": 1,
            "adx_rejected_count": 1,
            "adx_missing_count": 0,
        },
    )
    input_path = scratch / "NQ_sample.csv"
    input_path.write_text("sample", encoding="utf-8")
    monkeypatch.setattr(walk_forward_run, "INPUT_DATA_PATH", input_path)

    output_dir = scratch / "walk_forward"
    result = walk_forward_run.run_walk_forward_report(output_dir=output_dir)

    assert result == output_dir
    assert seen_sessions == [[date(2026, 1, day)] for day in range(2, 10)]
    report = json.loads(
        (output_dir / walk_forward_run.REPORT_JSON).read_text(encoding="utf-8")
    )
    assert report["report_type"] == "walk_forward_report"
    assert report["report_label"] == "coverage_only_validation_child_walk_forward_no_edge_claim"
    assert report["predeclared_window_count"] == 8
    assert report["window_count"] == 8
    assert report["overall_result"] == "inconclusive"
    assert report["final_test_status"] == "not_run"
    assert report["frozen_child_thresholds"]["adx_filter_threshold"] == pytest.approx(
        params.ADX_FILTER_THRESHOLD
    )
    assert [row["window_index"] for row in report["windows"]] == list(range(1, 9))
    assert all(row["session_count"] == 1 for row in report["windows"])
    assert all(row["adx_kept_fraction"] == pytest.approx(0.5) for row in report["windows"])

    with (output_dir / walk_forward_run.REPORT_CSV).open(
        newline="",
        encoding="utf-8",
    ) as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 8
    assert rows[0]["window_index"] == "1"
    run_config = json.loads(
        (output_dir / walk_forward_run.RUN_CONFIG_JSON).read_text(encoding="utf-8")
    )
    assert run_config["run_type"] == "validation_child_walk_forward"
    assert run_config["input_data_bytes"][
        ".test_artifacts/child_walk_forward_tests/"
        f"{scratch.name}/NQ_sample.csv"
    ] == 6
    assert run_config["frozen_child_parameters"]["adx_window"] == 14


def test_session_windows_do_not_split_sessions():
    sessions = [date(2026, 1, day) for day in range(1, 11)]
    validation_bars = _validation_bars(sessions)

    windows = walk_forward_run._session_windows(validation_bars, window_count=3)

    assert [window.session_count for window in windows] == [4, 3, 3]
    assert [window.session_start for window in windows] == [
        date(2026, 1, 1),
        date(2026, 1, 5),
        date(2026, 1, 8),
    ]
    assert [window.session_end for window in windows] == [
        date(2026, 1, 4),
        date(2026, 1, 7),
        date(2026, 1, 10),
    ]
    assert all(
        len(window.bars["SessionDate_ET"].drop_duplicates()) == window.session_count
        for window in windows
    )


def test_adx_restrictiveness_counts_only_after_non_adx_gates_pass(monkeypatch):
    prepared = _prepared_gate_bars()
    monkeypatch.setattr(
        walk_forward_run,
        "add_child_indicators",
        lambda bars: prepared,
    )

    summary = walk_forward_run._adx_restrictiveness_summary(
        prepared,
        exclude_roll_sessions=True,
    )

    assert summary == {
        "adx_kept_count": 1,
        "adx_rejected_count": 1,
        "adx_missing_count": 1,
    }


def _validation_bars(sessions: list[date]) -> pd.DataFrame:
    rows = []
    timestamp = pd.Timestamp("2026-01-01 14:30:00", tz="UTC")
    for session in sessions:
        for minute in (0, 5):
            rows.append(
                {
                    "DateTime_UTC": timestamp,
                    "DateTime_ET": timestamp.tz_convert("America/New_York"),
                    "SessionDate_ET": session,
                    "SessionMinute_ET": minute,
                }
            )
            timestamp += pd.Timedelta(minutes=5)
    return pd.DataFrame(rows)


def _prepared_gate_bars() -> pd.DataFrame:
    session_date = date(2026, 1, 2)
    start = pd.Timestamp("2026-01-02 09:30:00", tz="America/New_York")
    rows = []
    for index in range(23):
        rows.append(
            {
                "DateTime_ET": start + pd.Timedelta(minutes=index * 5),
                "SessionDate_ET": session_date,
                "SessionMinute_ET": index * 5,
                "IsFirstSessionAfterContractChange": False,
                "EntryZ": None,
                "ATR": 1.0,
                "ADX": params.ADX_FILTER_THRESHOLD,
            }
        )

    rows[18]["EntryZ"] = -params.ENTRY_Z_THRESHOLD
    rows[19]["EntryZ"] = -params.ENTRY_Z_THRESHOLD
    rows[19]["ADX"] = params.ADX_FILTER_THRESHOLD - 0.01
    rows[20]["EntryZ"] = params.ENTRY_Z_THRESHOLD
    rows[20]["ADX"] = params.ADX_FILTER_THRESHOLD + 0.01
    rows[21]["EntryZ"] = -params.ENTRY_Z_THRESHOLD
    rows[21]["ADX"] = None
    return pd.DataFrame(rows)
