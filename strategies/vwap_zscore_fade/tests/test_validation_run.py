import csv
from datetime import date
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pandas as pd
import pytest

from shared.data.splits import chronological_session_splits
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import params
from strategies.vwap_zscore_fade.validation_artifacts import (
    write_validation_artifacts,
)
from strategies.vwap_zscore_fade.validation_run import (
    COVERAGE_LABEL,
    build_validation_report,
    validation_split_bars,
    _validate_validation_does_not_overlap_final_test,
)


SCRATCH_ROOT = Path(".test_artifacts/validation_run_tests")


@pytest.fixture
def validation_scratch(request):
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


def make_prepared_bars(session_dates: list[date]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SessionDate_ET": session_dates,
            "DateTime_UTC": pd.date_range(
                "2026-01-01 14:30:00",
                periods=len(session_dates),
                freq="5min",
                tz="UTC",
            ),
        }
    )


def report_trade(
    realized_r: float,
    exit_reason: str = "target",
    hold_crosses_gap: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        realized_r=realized_r,
        exit_reason=exit_reason,
        hold_crosses_gap=hold_crosses_gap,
    )


def artifact_trade(realized_r: float) -> SimpleNamespace:
    return SimpleNamespace(
        entry_time=pd.Timestamp("2026-01-02 10:00:00", tz="America/New_York"),
        exit_time=pd.Timestamp("2026-01-02 10:30:00", tz="America/New_York"),
        side="long",
        entry_price=100.0,
        exit_price=101.0,
        initial_stop_price=99.0,
        initial_risk=1.0,
        realized_r_gross=realized_r,
        realized_r_net=realized_r,
        realized_r=realized_r,
        exit_reason="target",
        bars_held=6,
        signal_time=pd.Timestamp("2026-01-02 09:55:00", tz="America/New_York"),
        signal_atr=2.0,
        entry_z=2.5,
        entry_session_vwap=100.5,
        entry_vwap_deviation=1.0,
        contract="NQH26",
        commission_is_smoke_test=False,
        gap_through=False,
        hold_crosses_gap=False,
    )


def test_validation_split_keeps_only_whole_validation_sessions():
    sessions = [date(2026, 1, day) for day in range(1, 11)]
    prepared = make_prepared_bars(
        [
            sessions[0],
            sessions[0],
            sessions[1],
            sessions[2],
            sessions[2],
            sessions[3],
            sessions[4],
            sessions[5],
            sessions[6],
            sessions[7],
            sessions[8],
            sessions[9],
        ]
    )

    splits = chronological_session_splits(prepared)
    validation = validation_split_bars(prepared, splits=splits)

    assert splits["discovery_end"] == date(2026, 1, 3)
    assert splits["validation_end"] == date(2026, 1, 8)
    assert validation["SessionDate_ET"].tolist() == [
        date(2026, 1, 4),
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 7),
        date(2026, 1, 8),
    ]


def test_validation_overlap_guard_rejects_final_test_rows():
    sessions = [date(2026, 1, day) for day in range(1, 11)]
    prepared = make_prepared_bars(sessions)
    splits = chronological_session_splits(prepared)
    validation_with_final_overlap = prepared.loc[
        (prepared["SessionDate_ET"] > splits["discovery_end"])
        & (prepared["SessionDate_ET"] <= date(2026, 1, 9))
    ].copy()

    with pytest.raises(RuntimeError, match="validation slice overlaps final-test"):
        _validate_validation_does_not_overlap_final_test(
            validation_with_final_overlap,
            splits=splits,
        )


def test_validation_report_rejects_negative_demo_child_and_marks_dsr_unavailable():
    prepared = make_prepared_bars([date(2026, 1, day) for day in range(1, 11)])
    splits = chronological_session_splits(prepared)
    validation = validation_split_bars(prepared, splits=splits)
    parent_trades = [report_trade(-0.2) for _ in range(100)]
    child_trades = [report_trade(-0.1) for _ in range(100)]

    report = build_validation_report(
        parent_trades=parent_trades,
        child_trades=child_trades,
        validation_bars=validation,
        splits=splits,
    )

    assert report["coverage_label"] == COVERAGE_LABEL
    assert report["child_workflow_label"] == params.WORKFLOW_TEST_LABEL
    assert report["final_test_status"] == "not_run"
    assert report["child"]["minimum_trade_count_tier"] == "normal_ge_100"
    assert report["comparison"]["child_beats_parent"] is True
    assert report["verdict"]["decision"] == "reject"
    assert report["verdict"]["standalone_child_credibility_status"] == "fail"
    assert "child_mean_realized_r_not_positive" in report["verdict"]["reasons"]
    assert report["deflated_sharpe_ratio"]["status"] == "unavailable"
    assert "per-rule Sharpe/std distribution" in report["deflated_sharpe_ratio"]["reason"]
    assert "post-hoc discovery-subset" in report["post_hoc_vs_live_note"]


def test_validation_report_uses_completed_non_gap_judgment_population():
    prepared = make_prepared_bars([date(2026, 1, day) for day in range(1, 11)])
    splits = chronological_session_splits(prepared)
    validation = validation_split_bars(prepared, splits=splits)

    report = build_validation_report(
        parent_trades=[report_trade(0.0)],
        child_trades=[
            report_trade(1.0),
            report_trade(10.0, hold_crosses_gap=True),
            report_trade(-5.0, exit_reason="end_of_data"),
        ],
        validation_bars=validation,
        splits=splits,
    )

    child = report["child"]
    assert child["judgment_population"] == "completed_non_gap"
    assert child["trade_count"] == 3
    assert child["completed_trade_count"] == 1
    assert child["all_completed_trade_count"] == 2
    assert child["incomplete_trade_count"] == 1
    assert child["excluded_hold_crosses_gap_count"] == 1
    assert child["mean_realized_r"] == pytest.approx(1.0)


def test_validation_artifacts_write_labeled_report_and_trade_files(validation_scratch):
    output_dir = validation_scratch / "validation"
    report = {
        "coverage_label": COVERAGE_LABEL,
        "child_workflow_label": params.WORKFLOW_TEST_LABEL,
    }
    run_config = {
        "coverage_label": COVERAGE_LABEL,
        "child_workflow_label": params.WORKFLOW_TEST_LABEL,
    }

    write_validation_artifacts(
        output_dir=output_dir,
        parent_trades=[artifact_trade(1.0)],
        child_trades=[artifact_trade(-0.5)],
        validation_report=report,
        run_config=run_config,
    )

    with (output_dir / "child_trades.csv").open(newline="", encoding="utf-8") as file:
        child_rows = list(csv.DictReader(file))
    validation_report = json.loads(
        (output_dir / "validation_report.json").read_text(encoding="utf-8")
    )
    validation_config = json.loads(
        (output_dir / "run_config.json").read_text(encoding="utf-8")
    )

    assert child_rows[0]["RealizedR"] == "-0.5"
    assert validation_report["coverage_label"] == COVERAGE_LABEL
    assert validation_config["child_workflow_label"] == params.WORKFLOW_TEST_LABEL
