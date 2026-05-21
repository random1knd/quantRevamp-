import pandas as pd
import pytest

from shared.indicators.liquidity import (
    kyle_lambda,
    kyle_lambda_percentile,
    vpin_approx,
)
from shared.indicators.zscore import rolling_percentile


def test_vpin_approx_returns_hand_calculated_value():
    bars = pd.DataFrame(
        {
            "BidVolume": [0.0, 50.0, 0.0],
            "AskVolume": [100.0, 50.0, 100.0],
            "Volume": [100.0, 100.0, 100.0],
        }
    )

    result = vpin_approx(bars, window=3)

    assert result.name == "VPIN_Approx"
    assert result.iloc[2] == pytest.approx(2.0 / 3.0, abs=0.001)


def test_vpin_approx_returns_nan_before_window():
    bars = pd.DataFrame(
        {
            "BidVolume": [0.0, 50.0, 0.0],
            "AskVolume": [100.0, 50.0, 100.0],
            "Volume": [100.0, 100.0, 100.0],
        }
    )

    result = vpin_approx(bars, window=3)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])


def test_vpin_approx_returns_nan_for_zero_volume_bar():
    bars = pd.DataFrame(
        {
            "BidVolume": [100.0],
            "AskVolume": [200.0],
            "Volume": [0.0],
        }
    )

    result = vpin_approx(bars, window=1)

    assert pd.isna(result.iloc[0])


def test_vpin_approx_rejects_missing_columns():
    bars = pd.DataFrame(
        {
            "BidVolume": [100.0],
            "AskVolume": [200.0],
        }
    )

    with pytest.raises(ValueError, match="missing required columns"):
        vpin_approx(bars, window=1)


def test_kyle_lambda_returns_known_value_for_perfect_correlation():
    price_change = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    signed_volume = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])

    result = kyle_lambda(price_change, signed_volume, window=5)

    assert result.name == "KyleLambda"
    assert result.iloc[4] == pytest.approx(0.1)


def test_kyle_lambda_returns_nan_when_signed_volume_is_constant():
    price_change = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    signed_volume = pd.Series([10.0, 10.0, 10.0, 10.0, 10.0])

    result = kyle_lambda(price_change, signed_volume, window=5)

    assert result.isna().all()


def test_kyle_lambda_returns_nan_before_window():
    price_change = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    signed_volume = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])

    result = kyle_lambda(price_change, signed_volume, window=5)

    assert result.iloc[:4].isna().all()


def test_kyle_lambda_percentile_delegates_to_rolling_percentile():
    series = pd.Series([0.1, 0.2, 0.15, 0.3, 0.25])

    result = kyle_lambda_percentile(series, window=4)
    expected = rolling_percentile(series, window=4)
    expected.name = "KyleLambda_Pctile"

    pd.testing.assert_series_equal(result, expected)


def test_vpin_approx_is_causal_when_future_bar_changes():
    bars = pd.DataFrame(
        {
            "BidVolume": [0.0, 50.0, 0.0, 10.0],
            "AskVolume": [100.0, 50.0, 100.0, 20.0],
            "Volume": [100.0, 100.0, 100.0, 30.0],
        }
    )
    mutated = bars.copy()
    mutated.loc[3, ["BidVolume", "AskVolume", "Volume"]] = [10_000.0, 1.0, 1.0]

    original = vpin_approx(bars, window=3)
    changed = vpin_approx(mutated, window=3)

    assert original.iloc[2] == changed.iloc[2]


def test_kyle_lambda_is_causal_when_future_values_change():
    price_change = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    signed_volume = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    mutated_price_change = price_change.copy()
    mutated_signed_volume = signed_volume.copy()
    mutated_price_change.iloc[5] = 10_000.0
    mutated_signed_volume.iloc[5] = 1.0

    original = kyle_lambda(price_change, signed_volume, window=5)
    changed = kyle_lambda(mutated_price_change, mutated_signed_volume, window=5)

    assert original.iloc[4] == changed.iloc[4]
