import numpy as np
import pytest

from shared.validation.block_bootstrap import (
    WIRING_STATUS,
    session_block_bootstrap_mean_report,
)
from shared.validation.monte_carlo import centered_bootstrap_mean_report


def test_session_block_bootstrap_mean_is_deterministic_under_seed():
    first = session_block_bootstrap_mean_report(
        [[1.0, -1.0], [2.0, -0.5]],
        n_iter=5,
        random_seed=7,
        include_null_values=True,
    )
    second = session_block_bootstrap_mean_report(
        [[1.0, -1.0], [2.0, -0.5]],
        n_iter=5,
        random_seed=7,
        include_null_values=True,
    )

    assert first["null_mean_realized_r"] == second["null_mean_realized_r"]
    assert first["p_value"] == second["p_value"]


def test_session_block_bootstrap_uses_plus_one_smoothing():
    report = session_block_bootstrap_mean_report(
        [[1.0, 1.0, 1.0]],
        n_iter=9,
        random_seed=0,
        include_null_values=True,
    )

    assert report["observed_mean_realized_r"] == pytest.approx(1.0)
    assert report["null_mean_realized_r"] == [0.0] * 9
    assert report["extreme_null_count"] == 0
    assert report["p_value"] == pytest.approx(1 / 10)


def test_session_block_bootstrap_single_negative_session_is_not_positive_edge():
    report = session_block_bootstrap_mean_report(
        [[-1.0, -1.0]],
        n_iter=4,
        random_seed=0,
        sidedness="one_sided_positive",
        include_null_values=True,
    )

    assert report["observed_mean_realized_r"] == pytest.approx(-1.0)
    assert report["null_mean_realized_r"] == [0.0] * 4
    assert report["extreme_null_count"] == 4
    assert report["p_value"] == pytest.approx(1.0)


def test_session_block_bootstrap_sidedness_changes_extreme_rule():
    one_sided = session_block_bootstrap_mean_report(
        [[-1.0, -1.0]],
        n_iter=4,
        random_seed=0,
        sidedness="one_sided_positive",
    )
    two_sided = session_block_bootstrap_mean_report(
        [[-1.0, -1.0]],
        n_iter=4,
        random_seed=0,
        sidedness="two_sided",
    )

    assert one_sided["p_value"] == pytest.approx(1.0)
    assert two_sided["p_value"] == pytest.approx(1 / 5)
    assert one_sided["extreme_rule"] == "null_mean >= observed_mean"
    assert two_sided["extreme_rule"] == "abs(null_mean) >= abs(observed_mean)"


def test_session_block_bootstrap_drops_empty_sessions():
    report = session_block_bootstrap_mean_report(
        [[], [1.0, 1.0]],
        n_iter=3,
        random_seed=0,
    )

    assert report["session_count"] == 1
    assert report["trade_count"] == 2


def test_session_block_bootstrap_rejects_bad_arguments():
    with pytest.raises(ValueError, match="n_iter must be positive"):
        session_block_bootstrap_mean_report([[1.0]], n_iter=0, random_seed=0)

    with pytest.raises(ValueError, match="unsupported sidedness"):
        session_block_bootstrap_mean_report(
            [[1.0]],
            n_iter=1,
            random_seed=0,
            sidedness="left_tail",
        )

    with pytest.raises(ValueError, match="realized R must be finite"):
        session_block_bootstrap_mean_report(
            [[float("nan")]],
            n_iter=1,
            random_seed=0,
        )

    with pytest.raises(ValueError, match="at least one non-empty session"):
        session_block_bootstrap_mean_report([[], []], n_iter=1, random_seed=0)


def test_session_block_bootstrap_preserves_session_dependence():
    sessions = [[1.0] * 10 for _ in range(5)] + [[-1.0] * 10 for _ in range(5)]
    flat_values = [value for session in sessions for value in session]
    block = session_block_bootstrap_mean_report(
        sessions,
        n_iter=2000,
        random_seed=11,
        include_null_values=True,
    )
    iid = centered_bootstrap_mean_report(
        flat_values,
        n_iter=2000,
        random_seed=11,
        include_null_values=True,
    )

    block_spread = _p95_p05_spread(block["null_mean_realized_r"])
    iid_spread = _p95_p05_spread(iid["null_mean_realized_r"])

    assert block_spread > iid_spread * 2.0


def test_session_block_bootstrap_marks_report_as_not_wired():
    report = session_block_bootstrap_mean_report(
        [[1.0]],
        n_iter=1,
        random_seed=0,
    )

    assert report["method"] == "session_block_bootstrap_mean"
    assert report["block_unit"] == "whole_session"
    assert report["wiring_status"] == WIRING_STATUS


def _p95_p05_spread(values):
    percentiles = np.percentile(np.array(values, dtype=float), [5, 95])
    return float(percentiles[1] - percentiles[0])
