import pytest

from shared.validation.cross_instrument import cross_instrument_report


def test_cross_instrument_report_compares_summaries_without_pass_fail_gate():
    report = cross_instrument_report(
        [
            summary("ES", mean=0.05, total=5.0, completed=100, kept=30, rejected=10),
            summary("NQ", mean=-0.10, total=-20.0, completed=200, kept=40, rejected=60),
        ]
    )

    assert report["report_type"] == "cross_instrument_report"
    assert report["judgment_status"] == "report_only_no_pass_fail"
    assert report["coverage_only"] is True
    assert report["blueprint_demonstration"] is True
    assert report["selection_policy"] == "no_instrument_selection_allowed"
    assert report["instrument_order"] == ["ES", "NQ"]
    assert report["instrument_mean_sign_counts"] == {
        "positive": 1,
        "zero": 0,
        "negative": 1,
        "missing": 0,
    }
    assert report["mean_realized_r_range"]["min"] == pytest.approx(-0.10)
    assert report["mean_realized_r_range"]["max"] == pytest.approx(0.05)
    assert report["completed_non_gap_trade_count_range"] == {
        "min": 100,
        "max": 200,
        "range": 100,
    }

    es = report["instruments"][0]
    assert es["instrument"] == "ES"
    assert es["adx_decision_point_count"] == 40
    assert es["adx_observed_decision_count"] == 40
    assert es["adx_kept_fraction"] == pytest.approx(0.75)
    assert es["adx_missing_fraction"] == pytest.approx(0.0)


def test_cross_instrument_report_requires_summaries():
    with pytest.raises(ValueError, match="must not be empty"):
        cross_instrument_report([])


def summary(
    instrument: str,
    *,
    mean: float,
    total: float,
    completed: int,
    kept: int,
    rejected: int,
    missing: int = 0,
) -> dict:
    return {
        "instrument": instrument,
        "input_file": f"data/bars/5min/{instrument}_all_5min.csv",
        "session_model": "same_day_rth",
        "split": "validation",
        "trade_count": completed,
        "all_completed_trade_count": completed,
        "completed_non_gap_trade_count": completed,
        "incomplete_trade_count": 0,
        "excluded_hold_crosses_gap_count": 0,
        "mean_realized_r": mean,
        "total_realized_r": total,
        "win_rate": 0.5,
        "max_drawdown_r": 10.0,
        "minimum_trade_count_tier": "normal_ge_100",
        "adx_kept_count": kept,
        "adx_rejected_count": rejected,
        "adx_missing_count": missing,
    }
