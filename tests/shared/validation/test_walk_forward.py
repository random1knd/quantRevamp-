import pytest

from shared.validation.walk_forward import walk_forward_report


def summary(
    *,
    window_index: int,
    completed_non_gap_count: int,
    mean: float | None,
    kept: int,
    rejected: int,
    missing: int,
) -> dict:
    total = None if mean is None else mean * completed_non_gap_count
    return {
        "window_index": window_index,
        "window_count": 4,
        "session_start": f"2026-01-{window_index:02d}",
        "session_end": f"2026-01-{window_index:02d}",
        "session_count": 1,
        "bar_count": 50,
        "trade_count": completed_non_gap_count,
        "all_completed_trade_count": completed_non_gap_count,
        "completed_non_gap_trade_count": completed_non_gap_count,
        "incomplete_trade_count": 0,
        "excluded_hold_crosses_gap_count": 0,
        "mean_realized_r": mean,
        "total_realized_r": 0.0 if total is None else total,
        "win_rate": None,
        "max_drawdown_r": None,
        "adx_kept_count": kept,
        "adx_rejected_count": rejected,
        "adx_missing_count": missing,
    }


def test_walk_forward_report_summarizes_windows_without_pass_fail_gate():
    report = walk_forward_report(
        [
            summary(
                window_index=3,
                completed_non_gap_count=30,
                mean=0.20,
                kept=4,
                rejected=1,
                missing=0,
            ),
            summary(
                window_index=1,
                completed_non_gap_count=25,
                mean=-0.10,
                kept=3,
                rejected=1,
                missing=1,
            ),
            summary(
                window_index=4,
                completed_non_gap_count=22,
                mean=0.0,
                kept=1,
                rejected=3,
                missing=0,
            ),
            summary(
                window_index=2,
                completed_non_gap_count=10,
                mean=-0.05,
                kept=1,
                rejected=1,
                missing=2,
            ),
        ],
        sparse_trade_floor=20,
    )

    assert report["report_type"] == "walk_forward_report"
    assert report["judgment_status"] == "report_only_no_pass_fail"
    assert report["selection_policy"] == "no_window_or_threshold_selection_allowed"
    assert report["coverage_only"] is True
    assert report["overall_result"] == "reported_no_pass_fail"
    assert report["sparse_window_count"] == 1
    assert report["window_mean_sign_counts"] == {
        "positive": 1,
        "zero": 1,
        "negative": 1,
        "missing": 0,
    }
    assert report["mean_realized_r_range"]["min"] == pytest.approx(-0.10)
    assert report["mean_realized_r_range"]["max"] == pytest.approx(0.20)
    assert report["restrictiveness_drift"]["min_adx_kept_fraction"] == pytest.approx(
        0.25
    )
    assert report["restrictiveness_drift"]["max_adx_kept_fraction"] == pytest.approx(
        0.8
    )
    assert [row["window_index"] for row in report["windows"]] == [1, 2, 3, 4]
    assert report["windows"][0]["adx_decision_point_count"] == 5
    assert report["windows"][0]["adx_observed_decision_count"] == 4
    assert report["windows"][0]["adx_kept_fraction"] == pytest.approx(0.75)
    assert report["windows"][0]["adx_missing_fraction"] == pytest.approx(0.20)
    assert report["windows"][1]["window_status"] == "insufficient"


def test_walk_forward_report_is_inconclusive_when_most_windows_are_sparse():
    report = walk_forward_report(
        [
            summary(
                window_index=1,
                completed_non_gap_count=3,
                mean=None,
                kept=0,
                rejected=0,
                missing=0,
            ),
            summary(
                window_index=2,
                completed_non_gap_count=5,
                mean=None,
                kept=0,
                rejected=1,
                missing=0,
            ),
            summary(
                window_index=3,
                completed_non_gap_count=25,
                mean=0.1,
                kept=2,
                rejected=0,
                missing=0,
            ),
        ],
        sparse_trade_floor=20,
    )

    assert report["overall_result"] == "inconclusive"
    assert report["sparse_window_count"] == 2
    assert report["sufficient_window_count"] == 1


def test_walk_forward_report_requires_at_least_one_window():
    with pytest.raises(ValueError, match="must not be empty"):
        walk_forward_report([])
