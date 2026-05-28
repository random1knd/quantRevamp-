import pandas as pd
import pytest

from shared.validation.time_stability import (
    SPARSE_TRADE_FLOOR,
    time_stability_report,
)


def test_time_stability_report_buckets_and_uses_sign_safe_concentration():
    report = time_stability_report(
        [
            trade("2026-01-02 10:00", -10.0),
            trade("2026-01-03 10:00", 2.0),
            trade("2026-02-02 10:00", 3.0),
            trade("2026-02-03 10:00", 1.0),
            trade("2026-03-02 10:00", -1.0),
            trade("2026-03-03 10:00", -1.0),
            trade("2026-04-02 10:00", 0.0),
            trade("2026-04-03 10:00", 0.0),
        ],
        sparse_trade_floor=2,
    )

    assert report["report_type"] == "time_stability_report"
    assert report["coverage_only"] is True
    assert report["selection_policy"] == "no_period_selection_allowed"
    assert report["sparse_trade_floor"] == 2

    monthly = report["granularities"]["month"]
    assert monthly["bucket_mean_sign_counts"] == {
        "positive": 1,
        "zero": 1,
        "negative": 2,
        "missing": 0,
    }
    assert monthly["total_realized_r"] == pytest.approx(-6.0)
    assert monthly["total_abs_bucket_realized_r"] == pytest.approx(14.0)
    assert monthly["largest_abs_total_r_bucket"]["period_label"] == "2026-01"
    assert monthly["largest_abs_total_r_share"] == pytest.approx(8.0 / 14.0)
    assert monthly["leave_one_largest_abs_total_r_out_total_r"] == pytest.approx(2.0)

    january = monthly["buckets"][0]
    assert january["period_label"] == "2026-01"
    assert january["bucket_status"] == "sufficient"
    assert january["trade_count"] == 2
    assert january["mean_realized_r"] == pytest.approx(-4.0)
    assert january["total_realized_r"] == pytest.approx(-8.0)
    assert january["win_rate"] == pytest.approx(0.5)
    assert january["max_drawdown_r"] == pytest.approx(10.0)
    assert january["share_of_total_abs_bucket_r"] == pytest.approx(8.0 / 14.0)
    assert january["leave_one_bucket_out_total_r"] == pytest.approx(2.0)

    quarterly = report["granularities"]["quarter"]
    assert [bucket["period_label"] for bucket in quarterly["buckets"]] == [
        "2026Q1",
        "2026Q2",
    ]
    assert quarterly["bucket_mean_sign_counts"] == {
        "positive": 0,
        "zero": 1,
        "negative": 1,
        "missing": 0,
    }


def test_time_stability_report_marks_sparse_buckets():
    report = time_stability_report(
        [
            trade("2026-01-02 10:00", -1.0),
            trade("2026-01-03 10:00", 1.0),
            trade("2026-02-02 10:00", -1.0),
            trade("2026-02-03 10:00", -1.0),
        ],
        granularities=("month",),
        sparse_trade_floor=3,
    )

    monthly = report["granularities"]["month"]
    assert monthly["sparse_bucket_count"] == 2
    assert monthly["sufficient_bucket_count"] == 0
    assert monthly["bucket_mean_sign_counts"] == {
        "positive": 0,
        "zero": 0,
        "negative": 0,
        "missing": 0,
    }
    assert [bucket["bucket_status"] for bucket in monthly["buckets"]] == [
        "insufficient",
        "insufficient",
    ]


def test_time_stability_report_requires_trades():
    with pytest.raises(ValueError, match="must not be empty"):
        time_stability_report([])


def trade(entry_time: str, realized_r: float) -> dict:
    return {
        "entry_time": pd.Timestamp(entry_time, tz="America/New_York"),
        "realized_r": realized_r,
    }
