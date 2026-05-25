import csv
import json
from pathlib import Path
import shutil

import pytest

from strategies.vwap_zscore_fade.parent.threshold_neighborhood_run import (
    REPORT_CSV,
    REPORT_JSON,
    run_threshold_neighborhood_report,
)


SCRATCH_ROOT = Path(".test_artifacts/threshold_neighborhood_tests")


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


def test_threshold_neighborhood_runner_writes_train_side_reports(scratch):
    slicer_dir = scratch / "slicer"
    slicer_dir.mkdir()
    _write_json(
        slicer_dir / "slicer_plan.json",
        {
            "campaign_id": "test_campaign",
            "plan_label": "workflow_test_no_candidate_expected",
            "parent_strategy": "vwap_zscore_fade",
            "discovery_artifact": str(scratch / "discovery"),
            "quantiles": [20, 30, 40],
        },
    )
    _write_json(
        slicer_dir / "filter_candidate.json",
        {
            "campaign_id": "test_campaign",
            "plan_label": "workflow_test_no_candidate_expected",
            "parent_strategy": "vwap_zscore_fade",
            "candidate_status": "no_candidate",
            "no_candidate_reason": "best_mean_not_positive",
            "selected_rule": None,
            "best_rule": _rule("SignalADX__le__q30", 1, 30, -0.08),
        },
    )
    _write_slice_report(
        slicer_dir / "slice_report.csv",
        [
            _rule("SignalADX__le__q20", 0, 20, -0.09),
            _rule("SignalADX__le__q30", 1, 30, -0.08),
            _rule("SignalADX__le__q40", 2, 40, -0.11),
            _rule("SignalVPIN__le__q30", 3, 30, 1.0, column="SignalVPIN"),
        ],
    )

    output_dir = run_threshold_neighborhood_report(slicer_dir=slicer_dir)

    assert output_dir == slicer_dir
    report = json.loads((slicer_dir / REPORT_JSON).read_text(encoding="utf-8"))
    assert report["report_type"] == "threshold_neighborhood_report"
    assert report["report_label"] == "coverage_only_train_side_no_edge_claim"
    assert report["edge_validation_status"] == "cannot_validate_edge"
    assert report["candidate_status_at_slicer"] == "no_candidate"
    assert report["anchor_rule_role"] == "best_rule"
    assert report["spike_policy"]["policy_status"] == "not_applicable"
    assert report["same_column_direction_rule_count"] == 3
    assert [neighbor["neighbor_rule_id"] for neighbor in report["neighbors"]] == [
        "SignalADX__le__q20",
        "SignalADX__le__q40",
    ]

    with (slicer_dir / REPORT_CSV).open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert [row["neighbor_rule_id"] for row in rows] == [
        "SignalADX__le__q20",
        "SignalADX__le__q40",
    ]
    assert rows[0]["anchor_rule_id"] == "SignalADX__le__q30"


def _rule(
    rule_id: str,
    rule_index: int,
    quantile: float,
    mean_realized_r: float,
    *,
    column: str = "SignalADX",
) -> dict:
    return {
        "rule_id": rule_id,
        "rule_index": rule_index,
        "rule_form": "single_column_threshold",
        "column": column,
        "direction": "<=",
        "threshold_quantile": quantile,
        "threshold": quantile,
        "coincident_threshold_group": f"coincident_{rule_index + 1}",
        "coincident_threshold_count": 1,
        "non_null_count": 100,
        "kept_count": 100 + rule_index,
        "eligible": True,
        "mean_realized_r": mean_realized_r,
        "median_realized_r": mean_realized_r,
        "winsorized_mean_realized_r": mean_realized_r,
        "win_rate": 0.5,
        "max_drawdown_r": 2.0,
        "selected_metric_rank": rule_index + 1,
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
