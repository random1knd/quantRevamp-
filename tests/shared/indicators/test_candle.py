import pandas as pd
import pytest

from shared.indicators.candle import body_ratio, close_position


def test_body_ratio_returns_normal_candle_ratio():
    result = body_ratio(
        pd.Series([100.0]),
        pd.Series([110.0]),
        pd.Series([90.0]),
        pd.Series([108.0]),
    )

    assert result.name == "BodyRatio"
    assert result.iloc[0] == pytest.approx(0.4)


def test_body_ratio_returns_nan_for_zero_range_candle():
    result = body_ratio(
        pd.Series([100.0]),
        pd.Series([100.0]),
        pd.Series([100.0]),
        pd.Series([100.0]),
    )

    assert pd.isna(result.iloc[0])


def test_body_ratio_returns_one_for_full_body_candle():
    result = body_ratio(
        pd.Series([100.0]),
        pd.Series([110.0]),
        pd.Series([100.0]),
        pd.Series([110.0]),
    )

    assert result.iloc[0] == 1.0


def test_close_position_returns_normal_candle_position():
    result = close_position(
        pd.Series([110.0]),
        pd.Series([90.0]),
        pd.Series([108.0]),
    )

    assert result.name == "ClosePosition"
    assert result.iloc[0] == pytest.approx(0.9)


def test_close_position_returns_zero_when_close_is_low():
    result = close_position(
        pd.Series([110.0]),
        pd.Series([90.0]),
        pd.Series([90.0]),
    )

    assert result.iloc[0] == 0.0


def test_close_position_returns_one_when_close_is_high():
    result = close_position(
        pd.Series([110.0]),
        pd.Series([90.0]),
        pd.Series([110.0]),
    )

    assert result.iloc[0] == 1.0


def test_close_position_returns_nan_for_zero_range_candle():
    result = close_position(
        pd.Series([100.0]),
        pd.Series([100.0]),
        pd.Series([100.0]),
    )

    assert pd.isna(result.iloc[0])


def test_body_ratio_is_causal_when_future_bar_changes():
    open_ = pd.Series([100.0, 101.0, 102.0, 103.0])
    high = pd.Series([110.0, 111.0, 112.0, 113.0])
    low = pd.Series([90.0, 91.0, 92.0, 93.0])
    close = pd.Series([108.0, 106.0, 110.0, 104.0])
    mutated_high = high.copy()
    mutated_low = low.copy()
    mutated_close = close.copy()
    mutated_high.iloc[3] = 10_000.0
    mutated_low.iloc[3] = 1.0
    mutated_close.iloc[3] = 9_000.0

    original = body_ratio(open_, high, low, close)
    changed = body_ratio(open_, mutated_high, mutated_low, mutated_close)

    assert original.iloc[2] == changed.iloc[2]


def test_close_position_is_causal_when_future_bar_changes():
    high = pd.Series([110.0, 111.0, 112.0, 113.0])
    low = pd.Series([90.0, 91.0, 92.0, 93.0])
    close = pd.Series([108.0, 106.0, 110.0, 104.0])
    mutated_high = high.copy()
    mutated_low = low.copy()
    mutated_close = close.copy()
    mutated_high.iloc[3] = 10_000.0
    mutated_low.iloc[3] = 1.0
    mutated_close.iloc[3] = 9_000.0

    original = close_position(high, low, close)
    changed = close_position(mutated_high, mutated_low, mutated_close)

    assert original.iloc[2] == changed.iloc[2]
