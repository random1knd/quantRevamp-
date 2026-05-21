import pandas as pd
import pytest

from strategies.vwap_zscore_fade.parent.research_indicators import (
    RESEARCH_INDICATOR_COLUMNS,
    add_research_indicators,
)


def make_bars(
    *,
    volumes: list[float],
    session_minutes: list[int] | None = None,
    session_dates: list[str] | None = None,
    bar_gaps: list[bool] | None = None,
) -> pd.DataFrame:
    count = len(volumes)
    session_minutes = session_minutes or [index * 5 for index in range(count)]
    session_dates = session_dates or ["2026-01-02"] * count
    bar_gaps = bar_gaps or [False] * count

    return pd.DataFrame(
        {
            "SessionDate_ET": session_dates,
            "SessionMinute_ET": session_minutes,
            "BarGapFromPrevious": bar_gaps,
            "Open": [100.0 + index for index in range(count)],
            "High": [101.0 + index for index in range(count)],
            "Low": [99.0 + index for index in range(count)],
            "Close": [100.5 + index for index in range(count)],
            "Volume": volumes,
            "BidVolume": [volume * 0.4 for volume in volumes],
            "AskVolume": [volume * 0.6 for volume in volumes],
        }
    )


def test_research_indicators_scope_to_rth_rows_and_compute_delta_context():
    bars = make_bars(
        volumes=[100.0, 200.0, 300.0],
        session_minutes=[-5, 0, 390],
    )

    result = add_research_indicators(bars)

    assert pd.isna(result.loc[0, "EntryDelta"])
    assert result.loc[1, "EntryDelta"] == 40.0
    assert result.loc[1, "EntryDeltaPct"] == 0.2
    assert pd.isna(result.loc[2, "EntryDelta"])


def test_research_indicators_use_full_volume_z_window_per_session():
    volumes = [100.0 + index * 10.0 for index in range(21)]
    bars = make_bars(volumes=volumes)

    result = add_research_indicators(bars)

    expected_volume_z = (
        (bars["Volume"] - bars["Volume"].rolling(window=20, min_periods=20).mean())
        / bars["Volume"].rolling(window=20, min_periods=20).std()
    )
    assert pd.isna(result.loc[18, "EntryVolumeZ"])
    assert result.loc[19, "EntryVolumeZ"] == expected_volume_z.loc[19]
    assert result.loc[20, "EntryVolumeZ"] == expected_volume_z.loc[20]


def test_research_indicators_mask_volume_z_when_window_has_gap():
    volumes = [100.0 + index * 10.0 for index in range(21)]
    bar_gaps = [False] * 21
    bar_gaps[10] = True
    bars = make_bars(volumes=volumes, bar_gaps=bar_gaps)

    result = add_research_indicators(bars)

    assert pd.isna(result.loc[19, "EntryVolumeZ"])
    assert pd.isna(result.loc[20, "EntryVolumeZ"])
    assert result.loc[19, "EntryDelta"] == 58.0
    assert result.loc[19, "EntryDeltaPct"] == 0.2


def test_research_indicators_leave_delta_pct_missing_for_zero_volume():
    bars = make_bars(volumes=[0.0])

    result = add_research_indicators(bars)

    assert result.loc[0, "EntryDelta"] == 0.0
    assert pd.isna(result.loc[0, "EntryDeltaPct"])


def test_research_indicators_are_causal_when_future_rows_change():
    bars = make_bars(volumes=[100.0 + index * 5.0 for index in range(25)])
    mutated = bars.copy()
    mutated.loc[21:, "Volume"] = [10_000.0, 20_000.0, 30_000.0, 40_000.0]
    mutated.loc[21:, "BidVolume"] = [4_000.0, 8_000.0, 12_000.0, 16_000.0]
    mutated.loc[21:, "AskVolume"] = [6_000.0, 12_000.0, 18_000.0, 24_000.0]

    original_result = add_research_indicators(bars)
    mutated_result = add_research_indicators(mutated)

    pd.testing.assert_frame_equal(
        original_result.loc[:20, RESEARCH_INDICATOR_COLUMNS],
        mutated_result.loc[:20, RESEARCH_INDICATOR_COLUMNS],
    )


def test_research_indicators_reject_missing_required_columns():
    bars = make_bars(volumes=[100.0]).drop(columns=["BidVolume"])

    with pytest.raises(ValueError, match="missing required columns"):
        add_research_indicators(bars)


def test_batch1_body_ratio_and_close_position_are_bounded():
    bars = make_bars(volumes=[100.0] * 25)

    result = add_research_indicators(bars)

    assert result["EntryBodyRatio"].dropna().between(0, 1).all()
    assert result["EntryClosePosition"].dropna().between(0, 1).all()
    assert result["EntryBodyRatio"].iloc[0] == pytest.approx(0.25)
    assert result["EntryClosePosition"].iloc[0] == pytest.approx(0.75)


def test_batch1_vwap_distance_is_positive_for_rising_series():
    bars = make_bars(volumes=[100.0] * 25)

    result = add_research_indicators(bars)

    assert (result["EntryVWAPDist"].dropna() > 0).all()


def test_batch1_vwap_dist_atr_is_positive_and_eventually_non_nan():
    bars = make_bars(volumes=[100.0] * 40)

    result = add_research_indicators(bars)

    non_nan = result["EntryVWAPDistATR"].dropna()
    assert len(non_nan) > 0
    assert (non_nan > 0).all()


def test_batch2_vol_ratio_is_nan_before_window_and_one_for_constant_volume():
    bars = make_bars(volumes=[100.0] * 25)

    result = add_research_indicators(bars)

    assert result["EntryVolRatio"].iloc[:19].isna().all()
    assert result["EntryVolRatio"].iloc[19] == pytest.approx(1.0)


def test_batch2_realized_vol_is_non_negative():
    bars = make_bars(volumes=[100.0] * 40)

    result = add_research_indicators(bars)

    assert (result["EntryRealizedVol"].dropna() >= 0).all()


def test_batch2_atr_pctile_is_bounded_when_non_nan():
    bars = make_bars(volumes=[100.0] * 50)

    result = add_research_indicators(bars)

    non_nan = result["EntryATRPctile"].dropna()
    assert len(non_nan) > 0
    assert non_nan.between(0, 1).all()


def test_batch2_cum_delta_resets_at_session_boundary():
    bars = make_bars(
        volumes=[100.0] * 10,
        session_dates=["2026-01-02"] * 5 + ["2026-01-05"] * 5,
        session_minutes=[0, 5, 10, 15, 20, 0, 5, 10, 15, 20],
    )

    result = add_research_indicators(bars)

    assert result["EntryCumDelta"].iloc[0] == pytest.approx(20.0)
    assert result["EntryCumDelta"].iloc[5] == pytest.approx(20.0)
    assert result["EntryCumDelta"].iloc[4] == pytest.approx(100.0)


def test_batch1_and_batch2_columns_are_nan_for_non_rth_rows():
    bars = make_bars(
        volumes=[100.0, 100.0, 100.0],
        session_minutes=[-5, 100, 400],
    )
    new_columns = [
        "EntryBodyRatio",
        "EntryClosePosition",
        "EntryVWAPDist",
        "EntryVWAPDistATR",
        "EntryRealizedVol",
        "EntryVolRatio",
        "EntryVolRobustZ",
        "EntryATRPctile",
        "EntryCumDelta",
    ]

    result = add_research_indicators(bars)

    for col in new_columns:
        assert pd.isna(result.loc[0, col]), f"{col} should be NaN for pre-RTH row"
        assert pd.isna(result.loc[2, col]), f"{col} should be NaN for post-RTH row"


def test_batch3_delta_roc_is_nan_before_lookback_and_zero_for_constant_delta():
    bars = make_bars(volumes=[100.0] * 10)

    result = add_research_indicators(bars)

    assert result["EntryDeltaROC"].iloc[:5].isna().all()
    assert result["EntryDeltaROC"].iloc[5] == pytest.approx(0.0)


def test_batch3_ofi_is_nan_at_bar_zero_and_zero_for_constant_volumes():
    bars = make_bars(volumes=[100.0] * 5)

    result = add_research_indicators(bars)

    assert pd.isna(result["EntryOFI"].iloc[0])
    assert result["EntryOFI"].iloc[1] == pytest.approx(0.0)
    assert result["EntryOFI"].iloc[4] == pytest.approx(0.0)


def test_batch3_vpin_is_nan_before_window_and_correct_for_constant_imbalance():
    bars = make_bars(volumes=[100.0] * 25)

    result = add_research_indicators(bars)

    assert result["EntryVPIN"].iloc[:19].isna().all()
    assert result["EntryVPIN"].iloc[19] == pytest.approx(0.2)


def test_batch3_kyle_lambda_is_nan_for_constant_signed_volume():
    bars = make_bars(volumes=[100.0] * 25)

    result = add_research_indicators(bars)

    assert result["EntryKyleLambda"].isna().all()


def test_batch3_kyle_lambda_is_non_nan_for_variable_signed_volume():
    volumes = [100.0 + index * 10.0 for index in range(25)]
    bars = make_bars(volumes=volumes)

    result = add_research_indicators(bars)

    assert result["EntryKyleLambda"].iloc[20:].notna().all()


def test_batch3_columns_are_nan_for_non_rth_rows():
    bars = make_bars(
        volumes=[100.0, 100.0, 100.0],
        session_minutes=[-5, 100, 400],
    )
    batch3_columns = [
        "EntryDeltaROC",
        "EntryOFI",
        "EntryVPIN",
        "EntryKyleLambda",
        "EntryKyleLambdaPctile",
    ]

    result = add_research_indicators(bars)

    for col in batch3_columns:
        assert pd.isna(result.loc[0, col]), f"{col} should be NaN for pre-RTH row"
        assert pd.isna(result.loc[2, col]), f"{col} should be NaN for post-RTH row"
