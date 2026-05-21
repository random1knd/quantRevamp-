import pandas as pd
import pytest

from shared.indicators.trend import (
    adx,
    efficiency_ratio,
    ma_slope,
    momentum,
)


def test_adx_rejects_missing_columns():
    bars = pd.DataFrame(
        {
            "High": [10.0],
            "Close": [9.5],
        }
    )

    with pytest.raises(ValueError, match="missing required columns"):
        adx(bars, window=5)


def test_adx_detects_monotonic_uptrend():
    bars = _monotonic_uptrend_bars(length=15)

    result = adx(bars, window=5)

    assert result["PlusDI"].iloc[-1] > result["MinusDI"].iloc[-1]
    assert 20.0 < result["ADX"].iloc[-1] <= 100.0


def test_adx_returns_nan_for_first_bars():
    bars = _monotonic_uptrend_bars(length=15)

    result = adx(bars, window=5)

    assert pd.isna(result["ADX"].iloc[0])
    assert pd.isna(result["ADX"].iloc[7])


def test_adx_directional_indicators_are_non_negative():
    bars = pd.DataFrame(
        {
            "High": [10.0, 11.0, 10.5, 12.0, 11.5, 13.0, 12.0, 14.0],
            "Low": [9.0, 9.5, 9.0, 10.0, 10.0, 11.0, 10.5, 12.0],
            "Close": [9.5, 10.5, 10.0, 11.5, 11.0, 12.5, 11.5, 13.5],
        }
    )

    result = adx(bars, window=3)

    assert (result["PlusDI"].dropna() >= 0.0).all()
    assert (result["MinusDI"].dropna() >= 0.0).all()


def test_adx_is_causal_when_future_bar_changes():
    bars = _monotonic_uptrend_bars(length=15)
    mutated = bars.copy()
    mutated.loc[13, ["High", "Low", "Close"]] = [500.0, 1.0, 250.0]

    original = adx(bars, window=5)
    changed = adx(mutated, window=5)

    assert original["ADX"].iloc[12] == changed["ADX"].iloc[12]


def test_ma_slope_returns_positive_slope_on_rising_series():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])

    result = ma_slope(series, window=2)

    assert result.name == "MA_Slope"
    assert result.iloc[2] == 1.0


def test_ma_slope_returns_nan_before_window():
    series = pd.Series([1.0, 2.0, 3.0])

    result = ma_slope(series, window=2)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])


def test_efficiency_ratio_returns_one_for_trending_series():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])

    result = efficiency_ratio(series, window=4)

    assert result.name == "EfficiencyRatio"
    assert result.iloc[4] == 1.0


def test_efficiency_ratio_returns_nan_for_flat_series():
    series = pd.Series([5.0, 5.0, 5.0, 5.0, 5.0])

    result = efficiency_ratio(series, window=4)

    assert pd.isna(result.iloc[4])


def test_efficiency_ratio_returns_zero_for_choppy_series():
    series = pd.Series([1.0, 2.0, 1.0, 2.0, 1.0])

    result = efficiency_ratio(series, window=4)

    assert result.iloc[4] == 0.0


def test_momentum_returns_known_percent_change():
    series = pd.Series([100.0, 105.0, 102.0, 110.0])

    result = momentum(series, lookback=2)

    assert result.name == "Momentum"
    assert result.iloc[2] == pytest.approx(0.02)
    assert result.iloc[3] == pytest.approx(0.04762, abs=0.00001)


def test_momentum_returns_nan_before_lookback():
    series = pd.Series([100.0, 105.0, 102.0])

    result = momentum(series, lookback=2)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])


def test_momentum_returns_nan_for_zero_denominator():
    series = pd.Series([0.0, 5.0, 10.0])

    result = momentum(series, lookback=2)

    assert pd.isna(result.iloc[2])


def test_efficiency_ratio_is_causal_when_future_value_changes():
    series = pd.Series([1.0, 2.0, 3.0, 5.0, 8.0, 13.0])
    mutated = series.copy()
    mutated.iloc[5] = 10_000.0

    original = efficiency_ratio(series, window=4)
    changed = efficiency_ratio(mutated, window=4)

    assert original.iloc[4] == changed.iloc[4]


def test_ma_slope_is_causal_when_future_value_changes():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    mutated = series.copy()
    mutated.iloc[5] = 10_000.0

    original = ma_slope(series, window=2)
    changed = ma_slope(mutated, window=2)

    assert original.iloc[4] == changed.iloc[4]


def test_momentum_is_causal_when_future_value_changes():
    series = pd.Series([100.0, 105.0, 102.0, 110.0, 108.0, 115.0])
    mutated = series.copy()
    mutated.iloc[5] = 10_000.0

    original = momentum(series, lookback=2)
    changed = momentum(mutated, lookback=2)

    assert original.iloc[4] == changed.iloc[4]


def _monotonic_uptrend_bars(*, length: int) -> pd.DataFrame:
    close = pd.Series(range(100, 100 + length), dtype="float64")
    return pd.DataFrame(
        {
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
        }
    )
