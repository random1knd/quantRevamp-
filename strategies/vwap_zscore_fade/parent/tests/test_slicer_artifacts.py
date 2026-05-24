import csv
import json
from pathlib import Path
import shutil

import pandas as pd
import pytest

from strategies.vwap_zscore_fade.parent.slicer_run import (
    completed_non_gap_population,
    run_slicer,
)


RULE_FIELDS = [
    "rule_id",
    "rule_index",
    "rule_form",
    "column",
    "direction",
    "threshold_quantile",
    "threshold",
    "coincident_threshold_group",
    "coincident_threshold_count",
    "non_null_count",
    "kept_count",
    "eligible",
    "mean_realized_r",
    "median_realized_r",
    "winsorized_mean_realized_r",
    "win_rate",
    "max_drawdown_r",
    "selected_metric_rank",
    "selected",
    "outlier_divergence_flag",
]
SCRATCH_ROOT = Path(".test_artifacts/slicer_artifacts_tests")


@pytest.fixture
def slicer_scratch(request):
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


def make_tiny_plan(*, context_path: Path, discovery_artifact: Path) -> dict:
    return {
        "campaign_id": "test_campaign",
        "plan_label": "workflow_test_no_candidate_expected",
        "parent_strategy": "test_strategy",
        "discovery_artifact": str(discovery_artifact),
        "context_trades_path": str(context_path),
        "input_population": {
            "name": "completed_non_gap",
            "exit_reason_column": "ExitReason",
            "excluded_exit_reason": "end_of_data",
            "hold_crosses_gap_column": "HoldCrossesGap",
            "hold_crosses_gap_value": False,
        },
        "columns": [{"name": "SignalADX", "directions": ["<="]}],
        "quantiles": [100],
        "rule_form": "single_column_threshold",
        "expected_searched_rule_count": 1,
        "realized_r_column": "RealizedR",
        "selection_metric": "mean_realized_r",
        "min_kept_count": 1,
        "winsorize_fraction": 0.05,
        "nan_policy": {"filter_value_nan": "excluded_from_kept_subset"},
        "multiple_testing": {
            "method": "full_search_permutation_max_stat",
            "sidedness": "one_sided_positive",
            "random_seed": 0,
            "n_iter": 2,
            "p_value_smoothing": "plus_one",
            "bonferroni": "informational_only",
        },
        "required_rule_diagnostics": RULE_FIELDS,
    }


def test_completed_non_gap_population_filters_at_slicer():
    frame = pd.DataFrame(
        {
            "ExitReason": ["target", "end_of_data", "stop", "target"],
            "HoldCrossesGap": ["False", "False", "True", "0"],
            "RealizedR": [1.0, 2.0, 3.0, 4.0],
        }
    )
    plan = make_tiny_plan(
        context_path=Path("unused.csv"),
        discovery_artifact=Path("unused"),
    )

    population = completed_non_gap_population(frame, plan=plan)

    assert population["RealizedR"].tolist() == [1.0, 4.0]


def test_slicer_run_writes_honest_no_candidate_artifacts(slicer_scratch):
    discovery_artifact = slicer_scratch / "discovery"
    discovery_artifact.mkdir()
    context_path = discovery_artifact / "context_trades.csv"
    pd.DataFrame(
        {
            "ExitReason": ["target", "stop", "end_of_data", "target"],
            "HoldCrossesGap": [False, False, False, True],
            "SignalADX": [1.0, 2.0, 3.0, 4.0],
            "RealizedR": [-1.0, -2.0, 10.0, 10.0],
        }
    ).to_csv(context_path, index=False)
    plan = make_tiny_plan(
        context_path=context_path,
        discovery_artifact=discovery_artifact,
    )
    plan_path = slicer_scratch / "slicer_plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    output_dir = slicer_scratch / "slicer_out"

    result_path = run_slicer(plan_path=plan_path, output_dir=output_dir)

    assert result_path == output_dir
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "filter_candidate.json",
        "permutation_null.csv",
        "slice_report.csv",
        "slicer_plan.json",
    ]

    candidate = json.loads(
        (output_dir / "filter_candidate.json").read_text(encoding="utf-8")
    )
    assert candidate["candidate_status"] == "no_candidate"
    assert candidate["promotion_decision"] == "no_filter_candidate_promoted"
    assert candidate["no_candidate_reason"] == "best_mean_not_positive"
    assert candidate["population_summary"]["input_rows"] == 4
    assert candidate["population_summary"]["population_rows"] == 2
    assert candidate["best_rule"]["mean_realized_r"] == -1.5
    assert candidate["workflow_test_label"] == "pipeline_test_only_not_a_profit_claim"

    with (output_dir / "slice_report.csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    assert rows[0]["rule_id"] == "SignalADX__le__q100"
    assert rows[0]["kept_count"] == "2"
    assert rows[0]["eligible"] == "True"

    with (output_dir / "permutation_null.csv").open(newline="", encoding="utf-8") as file:
        permutation_rows = list(csv.DictReader(file))
    assert permutation_rows == []
