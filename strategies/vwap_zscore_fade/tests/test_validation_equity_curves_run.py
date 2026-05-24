from datetime import date
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pandas as pd
import pytest

from shared.data.splits import chronological_session_splits
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import params
from strategies.vwap_zscore_fade.validation_equity_curves_run import (
    IID_ASSUMPTION,
    build_equity_curves_report,
    write_equity_curve_artifacts,
)
from strategies.vwap_zscore_fade.validation_run import (
    COVERAGE_LABEL,
    validation_split_bars,
)


SCRATCH_ROOT = Path(".test_artifacts/validation_equity_curves_tests")


@pytest.fixture
def equity_curves_scratch(request):
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


def test_equity_curves_report_uses_validation_judgment_population():
    prepared = make_prepared_bars([date(2026, 1, day) for day in range(1, 11)])
    splits = chronological_session_splits(prepared)
    validation = validation_split_bars(prepared, splits=splits)
    child_trades = [
        trade(1.0),
        trade(-1.0),
        trade(10.0, hold_crosses_gap=True),
        trade(-5.0, exit_reason="end_of_data"),
    ]

    report = build_equity_curves_report(
        child_trades=child_trades,
        validation_bars=validation,
        splits=splits,
        n_iter=4,
        random_seed=0,
    )

    assert report["coverage_label"] == COVERAGE_LABEL
    assert report["child_workflow_label"] == params.WORKFLOW_TEST_LABEL
    assert report["final_test_status"] == "not_run"
    assert report["population"]["name"] == "completed_non_gap"
    assert report["population"]["trade_count"] == 4
    assert report["population"]["all_completed_trade_count"] == 3
    assert report["population"]["completed_non_gap_trade_count"] == 2
    assert report["population"]["excluded_hold_crosses_gap_count"] == 1
    assert report["equity_curves"]["observed"]["equity_curve"] == pytest.approx(
        [1.0, 0.0]
    )
    assert report["equity_curves"]["sample_count"] == 2
    assert report["equity_curves"]["final_equity_distribution"][
        "probability_positive_total_r"
    ] == 0.5
    assert report["iid_assumption"] == IID_ASSUMPTION
    assert report["block_bootstrap_status"] == "deferred"


def test_equity_curve_artifacts_write_labeled_report_and_config(
    equity_curves_scratch,
):
    output_dir = equity_curves_scratch / "run"
    report = {
        "coverage_label": COVERAGE_LABEL,
        "child_workflow_label": params.WORKFLOW_TEST_LABEL,
    }
    run_config = {
        "coverage_label": COVERAGE_LABEL,
        "child_workflow_label": params.WORKFLOW_TEST_LABEL,
    }

    write_equity_curve_artifacts(
        output_dir=output_dir,
        equity_curves_report=report,
        run_config=run_config,
    )

    written_report = json.loads(
        (output_dir / "equity_curves_report.json").read_text(encoding="utf-8")
    )
    written_config = json.loads(
        (output_dir / "run_config.json").read_text(encoding="utf-8")
    )

    assert written_report["coverage_label"] == COVERAGE_LABEL
    assert written_config["child_workflow_label"] == params.WORKFLOW_TEST_LABEL
