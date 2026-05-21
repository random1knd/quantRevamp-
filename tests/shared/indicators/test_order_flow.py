import pandas as pd
import pytest

from shared.indicators.order_flow import (
    cumulative_delta,
    delta,
    delta_roc,
    ofi_approx,
)


def test_delta_uses_hand_calculated_bid_ask_difference():
    bid_volume = pd.Series([100.0, 200.0, 150.0])
    ask_volume = pd.Series([120.0, 180.0, 170.0])

    result = delta(bid_volume, ask_volume)

    expected = pd.Series([20.0, -20.0, 20.0], name="Delta")
    pd.testing.assert_series_equal(result, expected)


def test_delta_accepts_zero_bid_or_ask_volume():
    bid_volume = pd.Series([0.0, 100.0])
    ask_volume = pd.Series([50.0, 0.0])

    result = delta(bid_volume, ask_volume)

    expected = pd.Series([50.0, -100.0], name="Delta")
    pd.testing.assert_series_equal(result, expected)


def test_cumulative_delta_resets_at_session_boundary():
    delta_values = pd.Series([10.0, -5.0, 8.0, 3.0, -2.0])
    session = pd.Series(["a", "a", "a", "b", "b"])

    result = cumulative_delta(delta_values, session=session)

    expected = pd.Series([10.0, 5.0, 13.0, 3.0, 1.0], name="CumDelta")
    pd.testing.assert_series_equal(result, expected)
    assert result.iloc[3] == 3.0


def test_cumulative_delta_accumulates_single_session():
    delta_values = pd.Series([1.0, 2.0, 3.0, 4.0])
    session = pd.Series(["a", "a", "a", "a"])

    result = cumulative_delta(delta_values, session=session)

    expected = pd.Series([1.0, 3.0, 6.0, 10.0], name="CumDelta")
    pd.testing.assert_series_equal(result, expected)


def test_delta_roc_returns_known_values():
    delta_values = pd.Series([10.0, 20.0, 15.0, 25.0, 30.0])

    result = delta_roc(delta_values, lookback=2)

    assert result.name == "DeltaROC"
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == 5.0
    assert result.iloc[4] == 15.0


def test_delta_roc_rejects_non_positive_lookback():
    with pytest.raises(ValueError, match="lookback must be positive"):
        delta_roc(pd.Series([1.0, 2.0]), lookback=0)


def test_ofi_approx_uses_hand_calculated_bid_ask_changes():
    bars = pd.DataFrame(
        {
            "BidVolume": [100.0, 110.0, 95.0],
            "AskVolume": [80.0, 90.0, 100.0],
        }
    )

    result = ofi_approx(bars)

    assert result.name == "OFI_Approx"
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == 0.0
    assert result.iloc[2] == 25.0


def test_ofi_approx_returns_nan_at_bar_zero():
    bars = pd.DataFrame(
        {
            "BidVolume": [10.0, 12.0],
            "AskVolume": [11.0, 13.0],
        }
    )

    result = ofi_approx(bars)

    assert pd.isna(result.iloc[0])


def test_ofi_approx_rejects_missing_columns():
    bars = pd.DataFrame({"BidVolume": [100.0, 110.0]})

    with pytest.raises(ValueError, match="missing required columns"):
        ofi_approx(bars)


def test_cumulative_delta_is_causal_when_future_delta_changes():
    delta_values = pd.Series([10.0, -5.0, 8.0, 3.0, -2.0])
    mutated = delta_values.copy()
    mutated.iloc[4] = 10_000.0
    session = pd.Series(["a", "a", "a", "b", "b"])

    original = cumulative_delta(delta_values, session=session)
    changed = cumulative_delta(mutated, session=session)

    assert original.iloc[3] == changed.iloc[3]


def test_delta_roc_is_causal_when_future_delta_changes():
    delta_values = pd.Series([10.0, 20.0, 15.0, 25.0, 30.0])
    mutated = delta_values.copy()
    mutated.iloc[4] = 10_000.0

    original = delta_roc(delta_values, lookback=2)
    changed = delta_roc(mutated, lookback=2)

    assert original.iloc[3] == changed.iloc[3]
