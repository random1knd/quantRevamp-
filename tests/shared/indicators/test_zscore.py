import pandas as pd

from shared.indicators.zscore import gap_free_rolling_window


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
