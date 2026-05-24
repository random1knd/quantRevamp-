import pytest

from shared.validation.monte_carlo import centered_bootstrap_mean_report


def test_centered_bootstrap_mean_is_deterministic_under_seed():
    first = centered_bootstrap_mean_report(
        [1.0, -1.0, 2.0, -0.5],
        n_iter=5,
        random_seed=7,
        include_null_values=True,
    )
    second = centered_bootstrap_mean_report(
        [1.0, -1.0, 2.0, -0.5],
        n_iter=5,
        random_seed=7,
        include_null_values=True,
    )

    assert first["null_mean_realized_r"] == second["null_mean_realized_r"]
    assert first["p_value"] == second["p_value"]


def test_centered_bootstrap_mean_uses_plus_one_smoothing():
    report = centered_bootstrap_mean_report(
        [1.0, 1.0, 1.0],
        n_iter=9,
        random_seed=0,
        include_null_values=True,
    )

    assert report["observed_mean_realized_r"] == pytest.approx(1.0)
    assert report["null_mean_realized_r"] == [0.0] * 9
    assert report["extreme_null_count"] == 0
    assert report["p_value"] == pytest.approx(1 / 10)


def test_centered_bootstrap_mean_has_hand_checkable_small_fixture_p_value():
    report = centered_bootstrap_mean_report(
        [1.0, -1.0],
        n_iter=4,
        random_seed=0,
        include_null_values=True,
    )

    assert report["observed_mean_realized_r"] == pytest.approx(0.0)
    assert report["null_mean_realized_r"] == pytest.approx(
        [-1.0, 0.0, 1.0, 1.0]
    )
    assert report["extreme_null_count"] == 3
    assert report["p_value"] == pytest.approx(4 / 5)


def test_centered_bootstrap_mean_sidedness_changes_extreme_rule():
    one_sided = centered_bootstrap_mean_report(
        [-1.0, -1.0],
        n_iter=4,
        random_seed=0,
        sidedness="one_sided_positive",
    )
    two_sided = centered_bootstrap_mean_report(
        [-1.0, -1.0],
        n_iter=4,
        random_seed=0,
        sidedness="two_sided",
    )

    assert one_sided["p_value"] == pytest.approx(1.0)
    assert two_sided["p_value"] == pytest.approx(1 / 5)
    assert one_sided["extreme_rule"] == "null_mean >= observed_mean"
    assert two_sided["extreme_rule"] == "abs(null_mean) >= abs(observed_mean)"


def test_centered_bootstrap_mean_rejects_empty_input():
    with pytest.raises(ValueError, match="at least one value"):
        centered_bootstrap_mean_report([], n_iter=1, random_seed=0)


def test_centered_bootstrap_mean_rejects_bad_arguments():
    with pytest.raises(ValueError, match="n_iter must be positive"):
        centered_bootstrap_mean_report([1.0], n_iter=0, random_seed=0)

    with pytest.raises(ValueError, match="unsupported sidedness"):
        centered_bootstrap_mean_report(
            [1.0],
            n_iter=1,
            random_seed=0,
            sidedness="left_tail",
        )

    with pytest.raises(ValueError, match="realized R must be finite"):
        centered_bootstrap_mean_report([float("nan")], n_iter=1, random_seed=0)
