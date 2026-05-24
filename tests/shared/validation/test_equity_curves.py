import pytest

from shared.validation.equity_curves import monte_carlo_equity_curves


def test_monte_carlo_equity_curves_is_deterministic_under_seed():
    first = monte_carlo_equity_curves([1.0, -1.0, 2.0], 5, 7)
    second = monte_carlo_equity_curves([1.0, -1.0, 2.0], 5, 7)

    assert first["equity_curve_percentile_bands"] == second[
        "equity_curve_percentile_bands"
    ]
    assert first["final_equity_distribution"] == second[
        "final_equity_distribution"
    ]
    assert first["max_drawdown_distribution"] == second[
        "max_drawdown_distribution"
    ]


def test_monte_carlo_equity_curves_has_hand_checkable_small_fixture():
    report = monte_carlo_equity_curves([1.0, -1.0], 4, 0)

    assert report["observed"]["equity_curve"] == pytest.approx([1.0, 0.0])
    assert report["observed"]["final_equity_r"] == pytest.approx(0.0)
    assert report["observed"]["max_drawdown_r"] == pytest.approx(1.0)
    assert report["equity_curve_percentile_bands"] == [
        {"trade_number": 1, "p05": -1.0, "p50": 0.0, "p95": 1.0},
        {"trade_number": 2, "p05": -1.7, "p50": 1.0, "p95": 2.0},
    ]
    assert report["final_equity_distribution"]["p50"] == pytest.approx(1.0)
    assert report["final_equity_distribution"]["probability_positive_total_r"] == 0.5
    assert report["max_drawdown_distribution"]["p50"] == pytest.approx(0.5)


def test_monte_carlo_equity_curves_defines_single_trade_case():
    report = monte_carlo_equity_curves([-2.0], 3, 0)

    assert report["observed"]["equity_curve"] == [-2.0]
    assert report["observed"]["final_equity_r"] == -2.0
    assert report["observed"]["max_drawdown_r"] == 2.0
    assert report["equity_curve_percentile_bands"] == [
        {"trade_number": 1, "p05": -2.0, "p50": -2.0, "p95": -2.0}
    ]
    assert report["final_equity_distribution"]["probability_positive_total_r"] == 0.0


def test_monte_carlo_equity_curves_rejects_empty_input():
    with pytest.raises(ValueError, match="at least one value"):
        monte_carlo_equity_curves([], 1, 0)


def test_monte_carlo_equity_curves_rejects_bad_arguments():
    with pytest.raises(ValueError, match="n_iter must be positive"):
        monte_carlo_equity_curves([1.0], 0, 0)

    with pytest.raises(ValueError, match="realized R must be finite"):
        monte_carlo_equity_curves([float("nan")], 1, 0)
