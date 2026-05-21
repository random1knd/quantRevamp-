import pandas as pd
import pytest

from shared.indicators.volume import (
    absorption_ratio,
    volume_ratio,
    volume_robust_zscore,
)
from shared.indicators.zscore import robust_zscore_cross_session


def test_volume_ratio_returns_hand_calculated_normal_bar():
    volume = pd.Series([100.0, 200.0, 100.0, 200.0, 100.0])

    result = volume_ratio(volume, window=4)

    assert result.name == "VolumeRatio"
    assert result.iloc[4] == pytest.approx(0.667, abs=0.001)


def test_volume_ratio_returns_nan_when_rolling_mean_is_zero():
    volume = pd.Series([0.0, 0.0, 0.0, 0.0])

    result = volume_ratio(volume, window=3)

    assert result.isna().all()


def test_volume_ratio_returns_above_one_for_spike_bar():
    volume = pd.Series([10.0, 10.0, 10.0, 10.0, 100.0])

    result = volume_ratio(volume, window=4)

    assert result.iloc[4] > 1.0


def test_volume_ratio_returns_nan_before_window():
    volume = pd.Series([100.0, 200.0, 100.0, 200.0])

    result = volume_ratio(volume, window=4)

    assert result.iloc[:3].isna().all()


def test_volume_robust_zscore_delegates_to_cross_session_robust_zscore():
    volume = pd.Series([0.0, 80.0, 100.0, 100.0, 110.0])

    result = volume_robust_zscore(volume, window=5)
    expected = robust_zscore_cross_session(volume, window=5)
    expected.name = "VolumeRobustZ"

    pd.testing.assert_series_equal(result, expected)


def test_volume_robust_zscore_returns_nan_for_constant_series():
    volume = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0])

    result = volume_robust_zscore(volume, window=5)

    assert result.isna().all()


def test_absorption_ratio_returns_high_absorption_example():
    delta = pd.Series([500.0])
    price_change = pd.Series([2.0])

    result = absorption_ratio(delta, price_change)

    assert result.name == "AbsorptionRatio"
    assert result.iloc[0] == 250.0


def test_absorption_ratio_returns_nan_when_price_change_is_zero():
    delta = pd.Series([100.0])
    price_change = pd.Series([0.0])

    result = absorption_ratio(delta, price_change)

    assert pd.isna(result.iloc[0])


def test_absorption_ratio_returns_zero_when_delta_is_zero():
    delta = pd.Series([0.0])
    price_change = pd.Series([5.0])

    result = absorption_ratio(delta, price_change)

    assert result.iloc[0] == 0.0


def test_volume_ratio_is_causal_when_future_volume_changes():
    volume = pd.Series([100.0, 200.0, 100.0, 200.0, 100.0, 150.0])
    mutated = volume.copy()
    mutated.iloc[5] = 10_000.0

    original = volume_ratio(volume, window=4)
    changed = volume_ratio(mutated, window=4)

    assert original.iloc[4] == changed.iloc[4]


def test_absorption_ratio_is_causal_when_future_values_change():
    delta = pd.Series([500.0, 100.0, 250.0])
    price_change = pd.Series([2.0, 4.0, 5.0])
    mutated_delta = delta.copy()
    mutated_price_change = price_change.copy()
    mutated_delta.iloc[2] = 10_000.0
    mutated_price_change.iloc[2] = 0.01

    original = absorption_ratio(delta, price_change)
    changed = absorption_ratio(mutated_delta, mutated_price_change)

    assert original.iloc[1] == changed.iloc[1]
