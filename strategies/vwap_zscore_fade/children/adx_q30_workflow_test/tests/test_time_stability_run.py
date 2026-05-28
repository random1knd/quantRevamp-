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
    time_stability_run,
)


SCRATCH_ROOT = Path(".test_artifacts/child_time_stability_tests")


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
    entry_time: str,
    realized_r: float,
    *,
    exit_reason: str = "target",
    hold_crosses_gap: bool = False,
) -> SimpleNamespace:
    timestamp = pd.Timestamp(entry_time, tz="America/New_York")
    return SimpleNamespace(
        entry_time=timestamp,
        exit_time=timestamp + pd.Timedelta(minutes=5),
        realized_r=realized_r,
        exit_reason=exit_reason,
        hold_crosses_gap=hold_crosses_gap,
    )


def test_time_stability_runner_generates_once_and_writes_reports(
    scratch,
    monkeypatch,
):
    validation_bars = _validation_bars()
    splits = {
        "discovery_end": date(2026, 1, 1),
        "validation_end": date(2026, 2, 3),
        "test_end": date(2026, 2, 4),
        "discovery_session_count": 1,
        "validation_session_count": 2,
        "test_session_count": 1,
    }
    calls = []

    def fake_generate_trades(
        bars,
        *,
        exclude_roll_sessions,
        commission_per_round_turn,
        commission_is_smoke_test,
    ):
        calls.append(list(bars["SessionDate_ET"].drop_duplicates()))
        return [
            trade("2026-01-02 10:00", -1.0),
            trade("2026-01-03 10:00", 0.5, hold_crosses_gap=True),
            trade("2026-02-02 10:00", 2.0, exit_reason="end_of_data"),
            trade("2026-02-03 10:00", -3.0),
        ]

    monkeypatch.setattr(
        time_stability_run,
        "load_validation_bars",
        lambda: (validation_bars, splits),
    )
    monkeypatch.setattr(
        time_stability_run,
        "generate_child_trades",
        fake_generate_trades,
    )
    input_path = scratch / "NQ_sample.csv"
    input_path.write_text("sample", encoding="utf-8")
    monkeypatch.setattr(time_stability_run, "INPUT_DATA_PATH", input_path)

    output_dir = scratch / "time_stability"
    result = time_stability_run.run_time_stability_report(
        output_dir=output_dir,
        sparse_trade_floor=1,
    )

    assert result == output_dir
    assert calls == [[date(2026, 1, 2), date(2026, 2, 3)]]
    report = json.loads(
        (output_dir / time_stability_run.REPORT_JSON).read_text(
            encoding="utf-8"
        )
    )
    assert report["report_type"] == "time_stability_report"
    assert report["report_label"] == (
        "coverage_only_validation_child_time_stability_no_edge_claim"
    )
    assert report["selection_policy"] == "no_period_selection_allowed"
    assert report["judgment_status"] == "report_only_no_pass_fail"
    assert report["coverage_only"] is True
    assert report["final_test_status"] == "not_run"
    assert report["trade_population"] == {
        "trade_count": 4,
        "all_completed_trade_count": 3,
        "completed_non_gap_trade_count": 2,
        "incomplete_trade_count": 1,
        "excluded_hold_crosses_gap_count": 1,
    }
    monthly = report["granularities"]["month"]
    assert monthly["bucket_mean_sign_counts"] == {
        "positive": 0,
        "zero": 0,
        "negative": 2,
        "missing": 0,
    }
    assert monthly["largest_abs_total_r_bucket"]["period_label"] == "2026-02"
    assert monthly["largest_abs_total_r_share"] == pytest.approx(0.75)
    assert monthly["leave_one_largest_abs_total_r_out_total_r"] == pytest.approx(
        -1.0
    )

    with (output_dir / time_stability_run.REPORT_CSV).open(
        newline="",
        encoding="utf-8",
    ) as file:
        rows = list(csv.DictReader(file))
    assert [row["granularity"] for row in rows] == [
        "month",
        "month",
        "quarter",
        "year",
    ]
    assert rows[0]["period_label"] == "2026-01"

    run_config = json.loads(
        (output_dir / time_stability_run.RUN_CONFIG_JSON).read_text(
            encoding="utf-8"
        )
    )
    assert run_config["run_type"] == "validation_child_time_stability"
    assert run_config["time_stability_spec"]["source_trades"].startswith(
        "single full-validation"
    )
    assert run_config["time_stability_spec"]["selection_policy"] == (
        "no_period_selection_allowed"
    )
    assert run_config["input_data_bytes"][
        ".test_artifacts/child_time_stability_tests/"
        f"{scratch.name}/NQ_sample.csv"
    ] == 6
    assert run_config["frozen_child_parameters"]["adx_window"] == 14
    assert run_config["frozen_child_parameters"]["adx_filter_threshold"] == (
        pytest.approx(params.ADX_FILTER_THRESHOLD)
    )


def _validation_bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "DateTime_UTC": pd.to_datetime(
                [
                    "2026-01-02T15:00:00Z",
                    "2026-02-03T15:00:00Z",
                ]
            ),
            "SessionDate_ET": [date(2026, 1, 2), date(2026, 2, 3)],
        }
    )
