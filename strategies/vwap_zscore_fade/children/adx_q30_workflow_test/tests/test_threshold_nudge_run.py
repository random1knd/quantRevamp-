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
    threshold_nudge_run,
)


SCRATCH_ROOT = Path(".test_artifacts/child_threshold_nudge_tests")


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


def test_threshold_nudge_runner_uses_literal_slicer_thresholds_and_writes_reports(
    scratch,
    monkeypatch,
):
    slicer_dir = scratch / "slicer"
    output_dir = scratch / "nudge"
    slicer_dir.mkdir()
    _write_json(
        slicer_dir / "filter_candidate.json",
        {
            "candidate_status": "no_candidate",
            "no_candidate_reason": "best_mean_not_positive",
        },
    )
    _write_slice_report(
        slicer_dir / "slice_report.csv",
        [
            _adx_rule(20, 16.0),
            _adx_rule(30, params.ADX_FILTER_THRESHOLD),
            _adx_rule(40, 22.0),
            {
                **_adx_rule(50, 25.0),
                "column": "SignalEfficiencyRatio",
                "rule_id": "SignalEfficiencyRatio__le__q50",
            },
        ],
    )
    validation_bars = pd.DataFrame(
        {
            "DateTime_UTC": pd.date_range(
                "2026-01-01 14:30:00",
                periods=2,
                freq="5min",
                tz="UTC",
            ),
            "SessionDate_ET": [date(2026, 1, 2), date(2026, 1, 3)],
        }
    )
    splits = {
        "discovery_end": date(2026, 1, 1),
        "validation_end": date(2026, 1, 3),
        "test_end": date(2026, 1, 4),
        "discovery_session_count": 1,
        "validation_session_count": 2,
        "test_session_count": 1,
    }
    seen_thresholds = []

    def fake_generate_trades(
        bars,
        *,
        exclude_roll_sessions,
        commission_per_round_turn,
        commission_is_smoke_test,
        adx_filter_threshold,
    ):
        seen_thresholds.append(adx_filter_threshold)
        if adx_filter_threshold == 16.0:
            return [
                trade(1.0),
                trade(-3.0, hold_crosses_gap=True),
                trade(0.0, exit_reason="end_of_data"),
            ]
        if adx_filter_threshold == params.ADX_FILTER_THRESHOLD:
            return [trade(-0.5), trade(0.25)]
        return [trade(0.5), trade(0.5), trade(-0.25)]

    monkeypatch.setattr(
        threshold_nudge_run,
        "load_validation_bars",
        lambda: (validation_bars, splits),
    )
    monkeypatch.setattr(
        threshold_nudge_run,
        "generate_child_trades",
        fake_generate_trades,
    )
    input_path = scratch / "NQ_sample.csv"
    input_path.write_text("sample", encoding="utf-8")
    monkeypatch.setattr(threshold_nudge_run, "INPUT_DATA_PATH", input_path)

    result = threshold_nudge_run.run_threshold_nudge_report(
        slicer_dir=slicer_dir,
        output_dir=output_dir,
    )

    assert result == output_dir
    assert seen_thresholds == [16.0, params.ADX_FILTER_THRESHOLD, 22.0]
    report = json.loads(
        (output_dir / threshold_nudge_run.REPORT_JSON).read_text(encoding="utf-8")
    )
    assert report["report_type"] == "child_threshold_nudge_report"
    assert report["report_label"] == "coverage_only_validation_child_nudge_no_edge_claim"
    assert report["threshold_grid_source"] == "literal_slicer_rows"
    assert report["judgment_status"] == "report_only_no_pass_fail"
    assert report["selection_policy"] == "no_threshold_selection_allowed"
    assert report["coverage_only"] is True
    assert report["final_test_status"] == "not_run"
    assert report["candidate_status_at_slicer"] == "no_candidate"
    assert [row["threshold_label"] for row in report["grid"]] == [
        "q20",
        "q30",
        "q40",
    ]

    q20, baseline, q40 = report["grid"]
    assert baseline["is_baseline"] is True
    assert q20["completed_non_gap_trade_count"] == 1
    assert q20["all_completed_trade_count"] == 2
    assert q20["incomplete_trade_count"] == 1
    assert q20["excluded_hold_crosses_gap_count"] == 1
    assert q20["delta_completed_non_gap_trade_count"] == pytest.approx(-1.0)
    assert q40["delta_total_realized_r"] == pytest.approx(1.0)

    with (output_dir / threshold_nudge_run.REPORT_CSV).open(
        newline="",
        encoding="utf-8",
    ) as file:
        rows = list(csv.DictReader(file))
    assert [row["threshold_label"] for row in rows] == ["q20", "q30", "q40"]
    assert rows[1]["is_baseline"] == "True"
    run_config = json.loads(
        (output_dir / threshold_nudge_run.RUN_CONFIG_JSON).read_text(
            encoding="utf-8"
        )
    )
    assert run_config["run_type"] == "validation_child_threshold_nudge"
    assert run_config["input_data_bytes"][
        ".test_artifacts/child_threshold_nudge_tests/"
        f"{scratch.name}/NQ_sample.csv"
    ] == 6
    assert run_config["frozen_child_parameters"]["adx_window"] == 14
    assert [row["threshold_label"] for row in run_config["threshold_grid"]] == [
        "q20",
        "q30",
        "q40",
    ]


def test_threshold_nudge_runner_requires_literal_q20_q30_q40_rows(scratch):
    slicer_dir = scratch / "slicer"
    slicer_dir.mkdir()
    _write_slice_report(
        slicer_dir / "slice_report.csv",
        [
            _adx_rule(20, 16.0),
            _adx_rule(30, params.ADX_FILTER_THRESHOLD),
        ],
    )

    with pytest.raises(ValueError, match="missing SignalADX <= slicer rows: q40"):
        threshold_nudge_run._read_adx_threshold_grid(slicer_dir / "slice_report.csv")


def _adx_rule(quantile: int, threshold: float) -> dict:
    return {
        "rule_id": f"SignalADX__le__q{quantile}",
        "rule_index": quantile,
        "rule_form": "single_column_threshold",
        "column": "SignalADX",
        "direction": "<=",
        "threshold_quantile": float(quantile),
        "threshold": threshold,
        "coincident_threshold_group": f"coincident_{quantile}",
        "coincident_threshold_count": 1,
        "non_null_count": 100,
        "kept_count": 100,
        "eligible": True,
        "mean_realized_r": 0.0,
        "median_realized_r": 0.0,
        "winsorized_mean_realized_r": 0.0,
        "win_rate": 0.0,
        "max_drawdown_r": 0.0,
        "selected_metric_rank": quantile,
        "selected": False,
        "outlier_divergence_flag": False,
    }


def _write_json(path: Path, content: dict) -> None:
    path.write_text(json.dumps(content), encoding="utf-8")


def _write_slice_report(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
