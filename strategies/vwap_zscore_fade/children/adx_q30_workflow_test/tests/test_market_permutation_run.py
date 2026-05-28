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
    market_permutation_run,
)


SCRATCH_ROOT = Path(".test_artifacts/child_market_permutation_tests")


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


def test_market_permutation_runner_writes_coverage_report_and_config(
    scratch,
    monkeypatch,
):
    validation_bars = _validation_bars()
    splits = {
        "discovery_end": date(2026, 1, 1),
        "validation_end": date(2026, 1, 3),
        "test_end": date(2026, 1, 4),
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
        if len(calls) == 1:
            return [trade(-0.20), trade(0.10)]
        if len(calls) == 2:
            return [trade(-0.50)]
        return [trade(0.0)]

    monkeypatch.setattr(
        market_permutation_run,
        "load_validation_bars",
        lambda: (validation_bars, splits),
    )
    monkeypatch.setattr(
        market_permutation_run,
        "generate_child_trades",
        fake_generate_trades,
    )
    input_path = scratch / "NQ_sample.csv"
    input_path.write_text("sample", encoding="utf-8")
    monkeypatch.setattr(market_permutation_run, "INPUT_DATA_PATH", input_path)

    output_dir = scratch / "market_permutation"
    result = market_permutation_run.run_market_permutation_report(
        output_dir=output_dir,
        n_iter=2,
        random_seed=7,
    )

    assert result == output_dir
    assert calls == [
        [date(2026, 1, 2), date(2026, 1, 3)],
        [date(2026, 1, 2), date(2026, 1, 3)],
        [date(2026, 1, 2), date(2026, 1, 3)],
    ]
    report = json.loads(
        (output_dir / market_permutation_run.REPORT_JSON).read_text(
            encoding="utf-8"
        )
    )
    assert report["report_type"] == "market_data_permutation_report"
    assert report["report_label"] == (
        "coverage_only_validation_child_market_permutation_no_edge_claim"
    )
    assert report["judgment_status"] == "report_only_no_pass_fail"
    assert report["coverage_only"] is True
    assert report["coverage_flags"] == [
        "coverage_only",
        "cannot_validate_edge",
        "workflow_test_child",
    ]
    assert report["final_test_status"] == "not_run"
    assert report["observed"]["completed_non_gap_trade_count"] == 2
    assert report["observed_mean_realized_r"] == pytest.approx(-0.05)
    assert report["permuted_ge_observed_count"] == 1
    assert report["one_sided_positive_p_value"] == pytest.approx(2 / 3)
    assert report["permutation_spec"]["n_iter"] == 2
    assert report["permutation_spec"]["iteration_seeds"] == [7, 8]
    assert "manufactures regression-to-the-mean" in report["interpretation"]
    assert "not a valid edge-validating null" in report["interpretation"]
    assert "block permutation" in report["permutation_spec"][
        "positive_candidate_requirement"
    ]

    with (output_dir / market_permutation_run.REPORT_CSV).open(
        newline="",
        encoding="utf-8",
    ) as file:
        rows = list(csv.DictReader(file))
    assert [row["iteration"] for row in rows] == ["1", "2"]
    assert [row["random_seed"] for row in rows] == ["7", "8"]

    run_config = json.loads(
        (output_dir / market_permutation_run.RUN_CONFIG_JSON).read_text(
            encoding="utf-8"
        )
    )
    assert run_config["run_type"] == "validation_child_market_data_permutation"
    assert run_config["permutation_spec"]["method"] == (
        "within_session_single_bar_market_tuple_permutation"
    )
    assert run_config["input_data_bytes"][
        ".test_artifacts/child_market_permutation_tests/"
        f"{scratch.name}/NQ_sample.csv"
    ] == 6
    assert run_config["frozen_child_parameters"]["adx_window"] == 14
    assert run_config["frozen_child_parameters"]["adx_filter_threshold"] == (
        pytest.approx(params.ADX_FILTER_THRESHOLD)
    )


def _validation_bars() -> pd.DataFrame:
    rows = []
    for session in (date(2026, 1, 2), date(2026, 1, 3)):
        start = pd.Timestamp(f"{session.isoformat()} 09:30", tz="America/New_York")
        for index in range(3):
            timestamp_et = start + pd.Timedelta(minutes=index * 5)
            base = 100.0 + len(rows) * 2.0
            rows.append(
                {
                    "DateTime_UTC": timestamp_et.tz_convert("UTC"),
                    "DateTime_ET": timestamp_et,
                    "SessionDate_ET": session,
                    "SessionMinute_ET": index * 5,
                    "Contract": "NQ",
                    "IsFirstSessionAfterContractChange": False,
                    "Open": base,
                    "High": base + 1.0,
                    "Low": base - 1.0,
                    "Close": base + 0.25,
                    "Volume": 1000 + index,
                    "BidVolume": 400 + index,
                    "AskVolume": 600 + index,
                    "BarGapMinutesFromPrevious": None,
                    "BarGapFromPrevious": False,
                }
            )
    return pd.DataFrame(rows)
