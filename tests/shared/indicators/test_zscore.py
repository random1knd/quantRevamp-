import pandas as pd
import pytest

from shared.indicators.zscore import (
    ewma_zscore,
    gap_free_rolling_window,
    robust_zscore,
    robust_zscore_cross_session,
    rolling_percentile,
    rolling_zscore,
    rolling_zscore_cross_session,
)


def test_gap_free_rolling_window_returns_true_for_clean_windows():
    result = gap_free_rolling_window(
        pd.Series([False, False, False]),
        session=pd.Series(["a", "a", "a"]),
        window=2,
    )

    expected = pd.Series([True, True, True])
    pd.testing.assert_series_equal(result, expected)


def test_gap_free_rolling_window_masks_internal_gap_until_it_leaves_window():
    result = gap_free_rolling_window(
        pd.Series([False, True, False, False]),
        session=pd.Series(["a", "a", "a", "a"]),
        window=3,
    )

    expected = pd.Series([True, False, False, False])
    pd.testing.assert_series_equal(result, expected)


def test_gap_free_rolling_window_masks_gap_at_window_edge():
    result = gap_free_rolling_window(
        pd.Series([False, False, True, False]),
        session=pd.Series(["a", "a", "a", "a"]),
        window=2,
    )

    expected = pd.Series([True, True, False, False])
    pd.testing.assert_series_equal(result, expected)


def test_gap_free_rolling_window_resets_by_session():
    result = gap_free_rolling_window(
        pd.Series([False, True, False, False]),
        session=pd.Series(["a", "a", "b", "b"]),
        window=3,
    )

    expected = pd.Series([True, False, True, True])
    pd.testing.assert_series_equal(result, expected)


def test_gap_free_rolling_window_treats_null_gap_flags_as_clean():
    result = gap_free_rolling_window(
        pd.Series([None, False, True]),
        session=pd.Series(["a", "a", "a"]),
        window=2,
    )

    expected = pd.Series([True, True, False])
    pd.testing.assert_series_equal(result, expected)


def test_rolling_zscore_uses_hand_calculated_session_window():
    series = pd.Series([1.0, 2.0, 3.0, 5.0, 8.0, 13.0])
    session = pd.Series(["a"] * 6)

    result = rolling_zscore(series, session=session, window=3)

    expected = pd.Series(
        [
            None,
            None,
            1.0,
            pytest.approx(1.0911, abs=0.0001),
            pytest.approx(1.0596, abs=0.0001),
            pytest.approx(1.0722, abs=0.0001),
        ],
        name="ZScore",
    )
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == expected.iloc[2]
    assert result.iloc[3] == expected.iloc[3]
    assert result.iloc[4] == expected.iloc[4]
    assert result.iloc[5] == expected.iloc[5]


def test_rolling_zscore_resets_at_session_boundary():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0, 101.0, 102.0, 103.0])
    session = pd.Series(["a", "a", "a", "a", "b", "b", "b", "b"])

    result = rolling_zscore(series, session=session, window=3)

    assert pd.isna(result.iloc[4])
    assert pd.isna(result.iloc[5])
    assert result.iloc[6] == 1.0


def test_rolling_zscore_cross_session_does_not_reset_at_session_boundary():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0, 101.0, 102.0, 103.0])

    result = rolling_zscore_cross_session(series, window=3)

    assert result.iloc[4] == pytest.approx(1.1547, abs=0.0001)


def test_rolling_zscore_returns_nan_for_flat_series():
    series = pd.Series([5.0, 5.0, 5.0, 5.0])
    session = pd.Series(["a"] * 4)

    result = rolling_zscore(series, session=session, window=3)

    assert result.isna().all()


def test_ewma_zscore_uses_ewm_mean_and_std_without_session_reset():
    series = pd.Series([1.0, 2.0, 4.0, 8.0])

    result = ewma_zscore(series, span=2)
    ewm_mean = series.ewm(span=2).mean()
    ewm_std = series.ewm(span=2).std()
    expected = ((series - ewm_mean) / ewm_std).rename("ZScore")

    pd.testing.assert_series_equal(result, expected)


def test_robust_zscore_resists_outlier_with_hand_calculated_mad():
    series = pd.Series([0.0, 80.0, 100.0, 100.0, 110.0])
    session = pd.Series(["a"] * 5)

    robust = robust_zscore(series, session=session, window=5)
    standard = rolling_zscore(series, session=session, window=5)

    assert robust.iloc[4] == pytest.approx(10.0 / (1.4826 * 10.0))
    assert abs(robust.iloc[4]) < abs(standard.iloc[4])


def test_robust_zscore_returns_nan_when_mad_is_zero():
    series = pd.Series([7.0, 7.0, 7.0, 7.0])
    session = pd.Series(["a"] * 4)

    result = robust_zscore(series, session=session, window=3)

    assert result.isna().all()


def test_robust_zscore_resets_at_session_boundary():
    series = pd.Series([1.0, 2.0, 3.0, 10.0, 11.0, 12.0])
    session = pd.Series(["a", "a", "a", "b", "b", "b"])

    result = robust_zscore(series, session=session, window=3)

    assert pd.isna(result.iloc[3])
    assert not pd.isna(result.iloc[5])


def test_robust_zscore_cross_session_returns_value_after_window_is_met():
    series = pd.Series([0.0, 80.0, 100.0, 100.0, 110.0])

    result = robust_zscore_cross_session(series, window=5)

    assert result.name == "ZScore"
    assert result.iloc[4] == pytest.approx(10.0 / (1.4826 * 10.0))


def test_robust_zscore_cross_session_returns_nan_when_mad_is_zero():
    series = pd.Series([7.0, 7.0, 7.0, 7.0])

    result = robust_zscore_cross_session(series, window=3)

    assert result.isna().all()


def test_rolling_percentile_excludes_current_bar_from_reference_window():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])

    window_four = rolling_percentile(series, window=4)
    window_three = rolling_percentile(series, window=3)

    assert window_four.iloc[4] == 1.0
    assert window_three.iloc[3] == 1.0


def test_rolling_percentile_returns_nan_before_prior_window_is_complete():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])

    result = rolling_percentile(series, window=4)

    assert result.iloc[:4].isna().all()
    assert result.iloc[4] == 1.0


def test_rolling_zscore_is_causal_when_future_value_changes():
    series = pd.Series([1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0])
    session = pd.Series(["a"] * 7)
    mutated = series.copy()
    mutated.iloc[6] = 10_000.0

    original = rolling_zscore(series, session=session, window=3)
    changed = rolling_zscore(mutated, session=session, window=3)

    assert original.iloc[5] == changed.iloc[5]


def test_rolling_percentile_is_causal_when_future_value_changes():
    series = pd.Series([1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0])
    mutated = series.copy()
    mutated.iloc[6] = 10_000.0

    original = rolling_percentile(series, window=3)
    changed = rolling_percentile(mutated, window=3)

    assert original.iloc[5] == changed.iloc[5]
