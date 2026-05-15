import pandas as pd
import pytest

pytest.importorskip(
    "shared.indicators.vwap",
    reason="shared/indicators/vwap.py not yet implemented",
)

from shared.indicators.vwap import session_vwap, typical_price


def test_typical_price_uses_high_low_close_average():
    high = pd.Series([12.0, 15.0])
    low = pd.Series([4.0, 12.0])
    close = pd.Series([9.0, 13.5])

    result = typical_price(high, low, close)

    expected = pd.Series([25.0 / 3.0, 13.5])
    pd.testing.assert_series_equal(result, expected)


def test_session_vwap_resets_by_caller_provided_session_column():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": [
                "2026-01-02",
                "2026-01-02",
                "2026-01-05",
                "2026-01-05",
            ],
            "TypicalPrice": [10.0, 12.0, 20.0, 30.0],
            "Volume": [100, 300, 50, 50],
        }
    )

    result = session_vwap(
        bars,
        price_col="TypicalPrice",
        volume_col="Volume",
        session_col="SessionDate_ET",
    )

    expected = pd.Series([10.0, 11.5, 20.0, 25.0], name="SessionVWAP")
    pd.testing.assert_series_equal(result, expected)


def test_session_vwap_preserves_input_order():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["b", "a", "b", "a"],
            "TypicalPrice": [20.0, 10.0, 40.0, 30.0],
            "Volume": [1, 1, 1, 1],
        }
    )

    result = session_vwap(
        bars,
        price_col="TypicalPrice",
        volume_col="Volume",
        session_col="SessionDate_ET",
    )

    expected = pd.Series([20.0, 10.0, 30.0, 20.0], name="SessionVWAP")
    pd.testing.assert_series_equal(result, expected)


def test_session_vwap_preserves_non_default_index_alignment():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["2026-01-02", "2026-01-02", "2026-01-05"],
            "TypicalPrice": [10.0, 12.0, 20.0],
            "Volume": [100, 300, 50],
        },
        index=[10, 11, 20],
    )

    result = session_vwap(
        bars,
        price_col="TypicalPrice",
        volume_col="Volume",
        session_col="SessionDate_ET",
    )

    expected = pd.Series([10.0, 11.5, 20.0], index=[10, 11, 20], name="SessionVWAP")
    pd.testing.assert_series_equal(result, expected)


def test_session_vwap_rejects_missing_columns():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["2026-01-02"],
            "TypicalPrice": [10.0],
        }
    )

    with pytest.raises(ValueError, match="missing required columns"):
        session_vwap(
            bars,
            price_col="TypicalPrice",
            volume_col="Volume",
            session_col="SessionDate_ET",
        )


def test_session_vwap_rejects_missing_session_column():
    bars = pd.DataFrame(
        {
            "TypicalPrice": [10.0],
            "Volume": [100],
        }
    )

    with pytest.raises(ValueError, match="missing required columns"):
        session_vwap(
            bars,
            price_col="TypicalPrice",
            volume_col="Volume",
            session_col="SessionDate_ET",
        )


def test_session_vwap_rejects_zero_or_negative_volume_rows():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["2026-01-02", "2026-01-02"],
            "TypicalPrice": [10.0, 12.0],
            "Volume": [100, 0],
        }
    )

    with pytest.raises(ValueError, match="volume must be positive"):
        session_vwap(
            bars,
            price_col="TypicalPrice",
            volume_col="Volume",
            session_col="SessionDate_ET",
        )


def test_session_vwap_rejects_negative_volume_rows():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["2026-01-02"],
            "TypicalPrice": [10.0],
            "Volume": [-1],
        }
    )

    with pytest.raises(ValueError, match="volume must be positive"):
        session_vwap(
            bars,
            price_col="TypicalPrice",
            volume_col="Volume",
            session_col="SessionDate_ET",
        )


def test_session_vwap_returns_empty_named_series_for_empty_input():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": [],
            "TypicalPrice": [],
            "Volume": [],
        }
    )

    result = session_vwap(
        bars,
        price_col="TypicalPrice",
        volume_col="Volume",
        session_col="SessionDate_ET",
    )

    expected = pd.Series([], dtype="float64", name="SessionVWAP")
    pd.testing.assert_series_equal(result, expected)


def test_session_vwap_rejects_nan_price_rows():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["2026-01-02", "2026-01-02"],
            "TypicalPrice": [10.0, None],
            "Volume": [100, 100],
        }
    )

    with pytest.raises(ValueError, match="price values must not be null"):
        session_vwap(
            bars,
            price_col="TypicalPrice",
            volume_col="Volume",
            session_col="SessionDate_ET",
        )


def test_session_vwap_rejects_null_session_values():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["2026-01-02", None],
            "TypicalPrice": [10.0, 12.0],
            "Volume": [100, 100],
        }
    )

    with pytest.raises(ValueError, match="session values must not be null"):
        session_vwap(
            bars,
            price_col="TypicalPrice",
            volume_col="Volume",
            session_col="SessionDate_ET",
        )
