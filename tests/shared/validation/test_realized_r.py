import pytest

from shared.validation.realized_r import (
    minimum_trade_count_policy,
    summarize_realized_r,
)


def test_summarize_realized_r_reports_core_completed_trade_metrics():
    summary = summarize_realized_r(
        [1.0, -0.5, 2.0, -1.0],
        trade_count=5,
        incomplete_trade_count=1,
    )

    assert summary["trade_count"] == 5
    assert summary["completed_trade_count"] == 4
    assert summary["incomplete_trade_count"] == 1
    assert summary["mean_realized_r"] == pytest.approx(0.375)
    assert summary["median_realized_r"] == pytest.approx(0.25)
    assert summary["total_realized_r"] == pytest.approx(1.5)
    assert summary["win_rate"] == pytest.approx(0.5)
    assert summary["max_drawdown_r"] == pytest.approx(1.0)
    assert summary["r_multiple_diagnostics"]["1R_or_better"] == 2
    assert summary["r_multiple_diagnostics"]["2R_or_better"] == 1
    assert summary["r_multiple_diagnostics"]["10R_or_better"] == 0


def test_summarize_realized_r_reports_empty_completed_trade_metrics():
    summary = summarize_realized_r([], trade_count=2, incomplete_trade_count=2)

    assert summary["mean_realized_r"] is None
    assert summary["median_realized_r"] is None
    assert summary["total_realized_r"] == 0
    assert summary["win_rate"] is None
    assert summary["max_drawdown_r"] is None
    assert summary["minimum_trade_count_tier"] == "insufficient_lt_30"


@pytest.mark.parametrize(
    ("completed_trade_count", "expected"),
    [
        (29, "insufficient_lt_30"),
        (30, "low_sample_30_to_99"),
        (99, "low_sample_30_to_99"),
        (100, "normal_ge_100"),
    ],
)
def test_minimum_trade_count_policy_uses_30_100_policy(
    completed_trade_count,
    expected,
):
    assert minimum_trade_count_policy(completed_trade_count) == expected


def test_summarize_realized_r_rejects_non_finite_values():
    with pytest.raises(ValueError, match="realized R must be finite"):
        summarize_realized_r([1.0, float("nan")])
