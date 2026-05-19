import pandas as pd
import pytest

from shared.indicators.volatility import session_atr, true_range


def test_true_range_uses_previous_close_inside_each_session():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["a", "a", "a", "b"],
            "High": [12.0, 13.0, 15.0, 30.0],
            "Low": [8.0, 9.0, 14.0, 29.0],
            "Close": [10.0, 12.0, 14.5, 29.5],
        }
    )

    result = true_range(
        bars,
        high_col="High",
        low_col="Low",
        close_col="Close",
        session_col="SessionDate_ET",
    )

    expected = pd.Series([4.0, 4.0, 3.0, 1.0], name="TrueRange")
    pd.testing.assert_series_equal(result, expected)


def test_true_range_rejects_null_ohlc_values():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["a", "a"],
            "High": [12.0, None],
            "Low": [8.0, 9.0],
            "Close": [10.0, 12.0],
        }
    )

    with pytest.raises(ValueError, match="OHLC values must not be null"):
        true_range(
            bars,
            high_col="High",
            low_col="Low",
            close_col="Close",
            session_col="SessionDate_ET",
        )


def test_session_atr_uses_full_window_rolling_mean_per_session():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["a", "a", "a", "b", "b"],
            "High": [12.0, 13.0, 15.0, 30.0, 36.0],
            "Low": [8.0, 9.0, 14.0, 29.0, 35.0],
            "Close": [10.0, 12.0, 14.5, 29.5, 35.5],
        }
    )

    result = session_atr(
        bars,
        high_col="High",
        low_col="Low",
        close_col="Close",
        session_col="SessionDate_ET",
        window=2,
    )

    expected = pd.Series([None, 4.0, 3.5, None, 3.75], name="ATR")
    pd.testing.assert_series_equal(result, expected)


def test_session_atr_preserves_non_default_index_alignment():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["a", "a", "a"],
            "High": [12.0, 13.0, 15.0],
            "Low": [8.0, 9.0, 14.0],
            "Close": [10.0, 12.0, 14.5],
        },
        index=[10, 11, 20],
    )

    result = session_atr(
        bars,
        high_col="High",
        low_col="Low",
        close_col="Close",
        session_col="SessionDate_ET",
        window=2,
    )

    expected = pd.Series([None, 4.0, 3.5], index=[10, 11, 20], name="ATR")
    pd.testing.assert_series_equal(result, expected)


def test_session_atr_preserves_input_order_with_interleaved_sessions():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["b", "a", "b", "a"],
            "High": [30.0, 12.0, 36.0, 13.0],
            "Low": [29.0, 8.0, 35.0, 9.0],
            "Close": [29.5, 10.0, 35.5, 12.0],
        }
    )

    result = session_atr(
        bars,
        high_col="High",
        low_col="Low",
        close_col="Close",
        session_col="SessionDate_ET",
        window=2,
    )

    expected = pd.Series([None, None, 3.75, 4.0], name="ATR")
    pd.testing.assert_series_equal(result, expected)


def test_session_atr_is_causal_when_future_rows_change():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["a"] * 5,
            "High": [12.0, 13.0, 15.0, 16.0, 17.0],
            "Low": [8.0, 9.0, 14.0, 15.0, 16.0],
            "Close": [10.0, 12.0, 14.5, 15.5, 16.5],
        }
    )
    mutated = bars.copy()
    mutated.loc[3:, ["High", "Low", "Close"]] = [
        [100.0, 90.0, 95.0],
        [200.0, 190.0, 195.0],
    ]

    original_result = session_atr(
        bars,
        high_col="High",
        low_col="Low",
        close_col="Close",
        session_col="SessionDate_ET",
        window=2,
    )
    mutated_result = session_atr(
        mutated,
        high_col="High",
        low_col="Low",
        close_col="Close",
        session_col="SessionDate_ET",
        window=2,
    )

    pd.testing.assert_series_equal(original_result.iloc[:3], mutated_result.iloc[:3])


def test_session_atr_rejects_missing_columns():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["a"],
            "High": [12.0],
            "Low": [8.0],
        }
    )

    with pytest.raises(ValueError, match="missing required columns"):
        session_atr(
            bars,
            high_col="High",
            low_col="Low",
            close_col="Close",
            session_col="SessionDate_ET",
            window=2,
        )


def test_session_atr_rejects_null_ohlc_values():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["a", "a"],
            "High": [12.0, None],
            "Low": [8.0, 9.0],
            "Close": [10.0, 12.0],
        }
    )

    with pytest.raises(ValueError, match="OHLC values must not be null"):
        session_atr(
            bars,
            high_col="High",
            low_col="Low",
            close_col="Close",
            session_col="SessionDate_ET",
            window=2,
        )


def test_session_atr_rejects_null_session_values():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["a", None],
            "High": [12.0, 13.0],
            "Low": [8.0, 9.0],
            "Close": [10.0, 12.0],
        }
    )

    with pytest.raises(ValueError, match="session values must not be null"):
        session_atr(
            bars,
            high_col="High",
            low_col="Low",
            close_col="Close",
            session_col="SessionDate_ET",
            window=2,
        )


def test_session_atr_rejects_high_below_low():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["a"],
            "High": [8.0],
            "Low": [12.0],
            "Close": [10.0],
        }
    )

    with pytest.raises(ValueError, match="high must be greater than or equal to low"):
        session_atr(
            bars,
            high_col="High",
            low_col="Low",
            close_col="Close",
            session_col="SessionDate_ET",
            window=2,
        )


def test_session_atr_rejects_non_positive_window():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["a"],
            "High": [12.0],
            "Low": [8.0],
            "Close": [10.0],
        }
    )

    with pytest.raises(ValueError, match="window must be positive"):
        session_atr(
            bars,
            high_col="High",
            low_col="Low",
            close_col="Close",
            session_col="SessionDate_ET",
            window=0,
        )


def test_session_atr_returns_empty_named_series_for_empty_input():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": [],
            "High": [],
            "Low": [],
            "Close": [],
        }
    )

    result = session_atr(
        bars,
        high_col="High",
        low_col="Low",
        close_col="Close",
        session_col="SessionDate_ET",
        window=2,
    )

    expected = pd.Series([], dtype="float64", name="ATR")
    pd.testing.assert_series_equal(result, expected)
