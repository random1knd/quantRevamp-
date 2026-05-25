import pytest

from shared.validation.threshold_nudge import child_threshold_nudge_report


def summary(
    *,
    quantile: float,
    threshold: float,
    completed_non_gap_count: int,
    mean: float,
    total: float,
    win_rate: float,
    max_drawdown: float,
) -> dict:
    return {
        "threshold_label": f"q{quantile:g}",
        "threshold_quantile": quantile,
        "adx_filter_threshold": threshold,
        "source_rule_id": f"SignalADX__le__q{quantile:g}",
        "trade_count": completed_non_gap_count + 1,
        "all_completed_trade_count": completed_non_gap_count,
        "completed_non_gap_trade_count": completed_non_gap_count,
        "incomplete_trade_count": 1,
        "excluded_hold_crosses_gap_count": 0,
        "mean_realized_r": mean,
        "total_realized_r": total,
        "win_rate": win_rate,
        "max_drawdown_r": max_drawdown,
    }


def test_child_threshold_nudge_report_compares_to_baseline_without_decision_gate():
    report = child_threshold_nudge_report(
        [
            summary(
                quantile=40,
                threshold=22.0,
                completed_non_gap_count=120,
                mean=-0.20,
                total=-24.0,
                win_rate=0.40,
                max_drawdown=30.0,
            ),
            summary(
                quantile=20,
                threshold=16.0,
                completed_non_gap_count=80,
                mean=-0.10,
                total=-8.0,
                win_rate=0.45,
                max_drawdown=10.0,
            ),
            summary(
                quantile=30,
                threshold=19.0,
                completed_non_gap_count=100,
                mean=-0.15,
                total=-15.0,
                win_rate=0.42,
                max_drawdown=20.0,
            ),
        ],
        baseline_threshold_quantile=30,
    )

    assert report["report_type"] == "child_threshold_nudge_report"
    assert report["threshold_grid_source"] == "literal_slicer_rows"
    assert report["judgment_status"] == "report_only_no_pass_fail"
    assert report["coverage_only"] is True
    assert report["selection_policy"] == "no_threshold_selection_allowed"
    assert [row["threshold_quantile"] for row in report["grid"]] == [
        20.0,
        30.0,
        40.0,
    ]

    q20, baseline, q40 = report["grid"]
    assert baseline["is_baseline"] is True
    assert baseline["delta_mean_realized_r"] == pytest.approx(0.0)
    assert q20["delta_completed_non_gap_trade_count"] == pytest.approx(-20.0)
    assert q20["delta_mean_realized_r"] == pytest.approx(0.05)
    assert q20["delta_total_realized_r"] == pytest.approx(7.0)
    assert q40["delta_max_drawdown_r"] == pytest.approx(10.0)


def test_child_threshold_nudge_report_requires_one_baseline():
    with pytest.raises(ValueError, match="exactly one baseline"):
        child_threshold_nudge_report(
            [
                summary(
                    quantile=20,
                    threshold=16.0,
                    completed_non_gap_count=80,
                    mean=-0.10,
                    total=-8.0,
                    win_rate=0.45,
                    max_drawdown=10.0,
                )
            ],
            baseline_threshold_quantile=30,
        )
