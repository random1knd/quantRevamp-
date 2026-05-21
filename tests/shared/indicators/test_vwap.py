import pandas as pd
import pytest

from shared.indicators.vwap import (
    session_vwap,
    typical_price,
    vwap_distance,
    vwap_distance_atr_normalized,
)


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


def test_session_vwap_is_causal_when_future_rows_change():
    bars = pd.DataFrame(
        {
            "SessionDate_ET": ["2026-01-02"] * 5,
            "TypicalPrice": [10.0, 12.0, 14.0, 16.0, 18.0],
            "Volume": [100, 200, 300, 400, 500],
        }
    )
    mutated = bars.copy()
    mutated.loc[3:, "TypicalPrice"] = [1000.0, 2000.0]
    mutated.loc[3:, "Volume"] = [10_000, 20_000]

    original_result = session_vwap(
        bars,
        price_col="TypicalPrice",
        volume_col="Volume",
        session_col="SessionDate_ET",
    )
    mutated_result = session_vwap(
        mutated,
        price_col="TypicalPrice",
        volume_col="Volume",
        session_col="SessionDate_ET",
    )

    pd.testing.assert_series_equal(original_result.iloc[:3], mutated_result.iloc[:3])


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


def test_vwap_distance_returns_positive_when_close_above_vwap():
    result = vwap_distance(pd.Series([102.0]), pd.Series([100.0]))

    assert result.name == "VWAPDist"
    assert result.iloc[0] == 2.0


def test_vwap_distance_returns_negative_when_close_below_vwap():
    result = vwap_distance(pd.Series([98.0]), pd.Series([100.0]))

    assert result.iloc[0] == -2.0


def test_vwap_distance_returns_nan_where_vwap_is_nan():
    result = vwap_distance(pd.Series([102.0]), pd.Series([float("nan")]))

    assert pd.isna(result.iloc[0])


def test_vwap_distance_atr_normalized_returns_known_value():
    result = vwap_distance_atr_normalized(pd.Series([4.0]), pd.Series([2.0]))

    assert result.name == "VWAPDist_ATR"
    assert result.iloc[0] == 2.0


def test_vwap_distance_atr_normalized_returns_nan_where_atr_is_zero():
    result = vwap_distance_atr_normalized(pd.Series([4.0]), pd.Series([0.0]))

    assert pd.isna(result.iloc[0])


def test_vwap_distance_atr_normalized_returns_nan_where_atr_is_nan():
    result = vwap_distance_atr_normalized(
        pd.Series([4.0]),
        pd.Series([float("nan")]),
    )

    assert pd.isna(result.iloc[0])


def test_vwap_distance_is_causal_when_future_values_change():
    close = pd.Series([100.0, 101.0, 102.0, 103.0])
    vwap = pd.Series([99.0, 100.0, 101.0, 102.0])
    mutated_close = close.copy()
    mutated_vwap = vwap.copy()
    mutated_close.iloc[3] = 10_000.0
    mutated_vwap.iloc[3] = 1.0

    original = vwap_distance(close, vwap)
    changed = vwap_distance(mutated_close, mutated_vwap)

    assert original.iloc[2] == changed.iloc[2]


def test_vwap_distance_atr_normalized_is_causal_when_future_values_change():
    distance = pd.Series([1.0, 2.0, 3.0, 4.0])
    atr = pd.Series([1.0, 2.0, 1.5, 2.0])
    mutated_distance = distance.copy()
    mutated_atr = atr.copy()
    mutated_distance.iloc[3] = 10_000.0
    mutated_atr.iloc[3] = 0.01

    original = vwap_distance_atr_normalized(distance, atr)
    changed = vwap_distance_atr_normalized(mutated_distance, mutated_atr)

    assert original.iloc[2] == changed.iloc[2]
