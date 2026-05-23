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

    assert pd.isna(result.loc[0, "SignalDelta"])
    assert result.loc[1, "SignalDelta"] == 40.0
    assert result.loc[1, "SignalDeltaPct"] == 0.2
    assert pd.isna(result.loc[2, "SignalDelta"])


def test_research_indicators_use_full_volume_z_window_per_session():
    volumes = [100.0 + index * 10.0 for index in range(21)]
    bars = make_bars(volumes=volumes)

    result = add_research_indicators(bars)

    expected_volume_z = (
        (bars["Volume"] - bars["Volume"].rolling(window=20, min_periods=20).mean())
        / bars["Volume"].rolling(window=20, min_periods=20).std()
    )
    assert pd.isna(result.loc[18, "SignalVolumeZ"])
    assert result.loc[19, "SignalVolumeZ"] == expected_volume_z.loc[19]
    assert result.loc[20, "SignalVolumeZ"] == expected_volume_z.loc[20]


def test_research_indicators_mask_volume_z_when_window_has_gap():
    volumes = [100.0 + index * 10.0 for index in range(21)]
    bar_gaps = [False] * 21
    bar_gaps[10] = True
    bars = make_bars(volumes=volumes, bar_gaps=bar_gaps)

    result = add_research_indicators(bars)

    assert pd.isna(result.loc[19, "SignalVolumeZ"])
    assert pd.isna(result.loc[20, "SignalVolumeZ"])
    assert result.loc[19, "SignalDelta"] == 58.0
    assert result.loc[19, "SignalDeltaPct"] == 0.2


def test_research_indicators_leave_delta_pct_missing_for_zero_volume():
    bars = make_bars(volumes=[0.0])

    result = add_research_indicators(bars)

    assert result.loc[0, "SignalDelta"] == 0.0
    assert pd.isna(result.loc[0, "SignalDeltaPct"])


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

    assert result["SignalBodyRatio"].dropna().between(0, 1).all()
    assert result["SignalClosePosition"].dropna().between(0, 1).all()
    assert result["SignalBodyRatio"].iloc[0] == pytest.approx(0.25)
    assert result["SignalClosePosition"].iloc[0] == pytest.approx(0.75)


def test_batch1_vwap_distance_is_positive_for_rising_series():
    bars = make_bars(volumes=[100.0] * 25)

    result = add_research_indicators(bars)

    assert (result["SignalVWAPDist"].dropna() > 0).all()


def test_batch1_vwap_dist_atr_is_positive_and_eventually_non_nan():
    bars = make_bars(volumes=[100.0] * 40)

    result = add_research_indicators(bars)

    non_nan = result["SignalVWAPDistATR"].dropna()
    assert len(non_nan) > 0
    assert (non_nan > 0).all()


def test_batch2_vol_ratio_is_nan_before_window_and_one_for_constant_volume():
    bars = make_bars(volumes=[100.0] * 25)

    result = add_research_indicators(bars)

    assert result["SignalVolRatio"].iloc[:19].isna().all()
    assert result["SignalVolRatio"].iloc[19] == pytest.approx(1.0)


def test_batch2_realized_vol_is_non_negative():
    bars = make_bars(volumes=[100.0] * 40)

    result = add_research_indicators(bars)

    assert (result["SignalRealizedVol"].dropna() >= 0).all()


def test_batch2_atr_pctile_is_bounded_when_non_nan():
    bars = make_bars(volumes=[100.0] * 50)

    result = add_research_indicators(bars)

    non_nan = result["SignalATRPctile"].dropna()
    assert len(non_nan) > 0
    assert non_nan.between(0, 1).all()


def test_batch2_cum_delta_resets_at_session_boundary():
    bars = make_bars(
        volumes=[100.0] * 10,
        session_dates=["2026-01-02"] * 5 + ["2026-01-05"] * 5,
        session_minutes=[0, 5, 10, 15, 20, 0, 5, 10, 15, 20],
    )

    result = add_research_indicators(bars)

    assert result["SignalCumDelta"].iloc[0] == pytest.approx(20.0)
    assert result["SignalCumDelta"].iloc[5] == pytest.approx(20.0)
    assert result["SignalCumDelta"].iloc[4] == pytest.approx(100.0)


def test_price_change_research_context_resets_at_session_boundary():
    session_dates = ["2026-01-02"] * 25 + ["2026-01-05"] * 25
    session_minutes = [index * 5 for index in range(25)] * 2
    volumes = [100.0 + index * 10.0 for index in range(50)]
    bars = make_bars(
        volumes=volumes,
        session_dates=session_dates,
        session_minutes=session_minutes,
    )
    mutated = bars.copy()
    mutated.loc[:24, "Open"] = [1000.0 + index * 20.0 for index in range(25)]
    mutated.loc[:24, "High"] = mutated.loc[:24, "Open"] + 5.0
    mutated.loc[:24, "Low"] = mutated.loc[:24, "Open"] - 5.0
    mutated.loc[:24, "Close"] = mutated.loc[:24, "Open"] + 2.0

    original_result = add_research_indicators(bars)
    mutated_result = add_research_indicators(mutated)
    price_change_columns = [
        "SignalRealizedVol",
        "SignalKyleLambda",
        "SignalAutoCorr",
        "SignalVarRatio",
    ]

    assert original_result.loc[25:44, "SignalRealizedVol"].isna().all()
    assert original_result.loc[25:44, "SignalKyleLambda"].isna().all()
    pd.testing.assert_frame_equal(
        original_result.loc[25:, price_change_columns],
        mutated_result.loc[25:, price_change_columns],
    )


def test_efficiency_ratio_research_context_resets_at_session_boundary():
    # SignalEfficiencyRatio derives from Close via diff(window); like the other
    # price-change context columns it must be session-isolated. A single-session
    # test cannot catch a cross-session leak because the prior session does not
    # exist, so this uses two sessions and asserts the second session's first
    # `window` bars are NaN and are unaffected by mutating the first session.
    session_dates = ["2026-01-02"] * 25 + ["2026-01-05"] * 25
    session_minutes = [index * 5 for index in range(25)] * 2
    volumes = [100.0 + index * 10.0 for index in range(50)]
    bars = make_bars(
        volumes=volumes,
        session_dates=session_dates,
        session_minutes=session_minutes,
    )
    mutated = bars.copy()
    mutated.loc[:24, "Close"] = [1000.0 + index * 20.0 for index in range(25)]

    original_result = add_research_indicators(bars)
    mutated_result = add_research_indicators(mutated)

    assert original_result.loc[25:44, "SignalEfficiencyRatio"].isna().all()
    pd.testing.assert_series_equal(
        original_result.loc[25:, "SignalEfficiencyRatio"],
        mutated_result.loc[25:, "SignalEfficiencyRatio"],
    )


def test_adx_research_context_resets_at_session_boundary():
    # SignalADX is session-scoped intraday trend strength. ADX uses
    # high.diff()/low.shift()/close.shift() and Wilder smoothing, so an ungrouped
    # computation would carry the prior session's state (and the overnight-gap
    # true range) into this session. Like the price-change columns it needs a
    # two-session test; a single-session test cannot expose cross-session carry.
    session_dates = ["2026-01-02"] * 40 + ["2026-01-05"] * 40
    session_minutes = [index * 5 for index in range(40)] * 2
    volumes = [100.0 + index * 10.0 for index in range(80)]
    bars = make_bars(
        volumes=volumes,
        session_dates=session_dates,
        session_minutes=session_minutes,
    )
    mutated = bars.copy()
    mutated.loc[:39, "Close"] = [1000.0 + index * 20.0 for index in range(40)]
    mutated.loc[:39, "High"] = mutated.loc[:39, "Close"] + 5.0
    mutated.loc[:39, "Low"] = mutated.loc[:39, "Close"] - 5.0

    original_result = add_research_indicators(bars)
    mutated_result = add_research_indicators(mutated)

    assert pd.isna(original_result.loc[40, "SignalADX"])
    assert original_result.loc[40:, "SignalADX"].notna().any()
    pd.testing.assert_series_equal(
        original_result.loc[40:, "SignalADX"],
        mutated_result.loc[40:, "SignalADX"],
    )


def test_flow_change_research_context_resets_at_session_boundary():
    session_dates = ["2026-01-02"] * 10 + ["2026-01-05"] * 10
    session_minutes = [index * 5 for index in range(10)] * 2
    volumes = [100.0 + index * 10.0 for index in range(20)]
    bars = make_bars(
        volumes=volumes,
        session_dates=session_dates,
        session_minutes=session_minutes,
    )
    mutated = bars.copy()
    mutated.loc[:9, "BidVolume"] = [10_000.0 + index for index in range(10)]
    mutated.loc[:9, "AskVolume"] = [1.0 + index for index in range(10)]

    original_result = add_research_indicators(bars)
    mutated_result = add_research_indicators(mutated)
    flow_change_columns = ["SignalDeltaROC", "SignalOFI"]

    assert original_result.loc[10:14, "SignalDeltaROC"].isna().all()
    assert pd.isna(original_result.loc[10, "SignalOFI"])
    pd.testing.assert_frame_equal(
        original_result.loc[10:, flow_change_columns],
        mutated_result.loc[10:, flow_change_columns],
    )


def test_batch1_and_batch2_columns_are_nan_for_non_rth_rows():
    bars = make_bars(
        volumes=[100.0, 100.0, 100.0],
        session_minutes=[-5, 100, 400],
    )
    new_columns = [
        "SignalBodyRatio",
        "SignalClosePosition",
        "SignalVWAPDist",
        "SignalVWAPDistATR",
        "SignalRealizedVol",
        "SignalVolRatio",
        "SignalVolRobustZ",
        "SignalATRPctile",
        "SignalCumDelta",
    ]

    result = add_research_indicators(bars)

    for col in new_columns:
        assert pd.isna(result.loc[0, col]), f"{col} should be NaN for pre-RTH row"
        assert pd.isna(result.loc[2, col]), f"{col} should be NaN for post-RTH row"


def test_batch3_delta_roc_is_nan_before_lookback_and_zero_for_constant_delta():
    bars = make_bars(volumes=[100.0] * 10)

    result = add_research_indicators(bars)

    assert result["SignalDeltaROC"].iloc[:5].isna().all()
    assert result["SignalDeltaROC"].iloc[5] == pytest.approx(0.0)


def test_batch3_ofi_is_nan_at_bar_zero_and_zero_for_constant_volumes():
    bars = make_bars(volumes=[100.0] * 5)

    result = add_research_indicators(bars)

    assert pd.isna(result["SignalOFI"].iloc[0])
    assert result["SignalOFI"].iloc[1] == pytest.approx(0.0)
    assert result["SignalOFI"].iloc[4] == pytest.approx(0.0)


def test_batch3_vpin_is_nan_before_window_and_correct_for_constant_imbalance():
    bars = make_bars(volumes=[100.0] * 25)

    result = add_research_indicators(bars)

    assert result["SignalVPIN"].iloc[:19].isna().all()
    assert result["SignalVPIN"].iloc[19] == pytest.approx(0.2)


def test_batch3_kyle_lambda_is_nan_for_constant_signed_volume():
    bars = make_bars(volumes=[100.0] * 25)

    result = add_research_indicators(bars)

    assert result["SignalKyleLambda"].isna().all()


def test_batch3_kyle_lambda_is_non_nan_for_variable_signed_volume():
    volumes = [100.0 + index * 10.0 for index in range(25)]
    bars = make_bars(volumes=volumes)

    result = add_research_indicators(bars)

    assert result["SignalKyleLambda"].iloc[20:].notna().all()


def test_batch3_columns_are_nan_for_non_rth_rows():
    bars = make_bars(
        volumes=[100.0, 100.0, 100.0],
        session_minutes=[-5, 100, 400],
    )
    batch3_columns = [
        "SignalDeltaROC",
        "SignalOFI",
        "SignalVPIN",
        "SignalKyleLambda",
        "SignalKyleLambdaPctile",
    ]

    result = add_research_indicators(bars)

    for col in batch3_columns:
        assert pd.isna(result.loc[0, col]), f"{col} should be NaN for pre-RTH row"
        assert pd.isna(result.loc[2, col]), f"{col} should be NaN for post-RTH row"


def test_batch4_autocorr_uses_returns_not_close_levels():
    bars = make_bars(volumes=[100.0] * 25)
    close = [100.0]
    for increment in [2.0, 0.5] * 12:
        close.append(close[-1] + increment)
    bars["Close"] = close[:25]
    bars["Open"] = bars["Close"]
    bars["High"] = bars["Close"] + 1.0
    bars["Low"] = bars["Close"] - 1.0

    result = add_research_indicators(bars)

    assert result["SignalAutoCorr"].iloc[:21].isna().all()
    assert result["SignalAutoCorr"].iloc[21] < -0.9


def test_batch4_var_ratio_is_nan_for_constant_step_close():
    bars = make_bars(volumes=[100.0] * 25)

    result = add_research_indicators(bars)

    assert result["SignalVarRatio"].isna().all()


def test_batch4_adx_is_nan_early_and_non_nan_eventually():
    bars = make_bars(volumes=[100.0] * 50)

    result = add_research_indicators(bars)

    assert pd.isna(result["SignalADX"].iloc[0])
    non_nan = result["SignalADX"].dropna()
    assert len(non_nan) > 0
    assert (non_nan <= 100.0).all()


def test_batch4_efficiency_ratio_is_nan_before_window_and_one_for_trend():
    bars = make_bars(volumes=[100.0] * 25)

    result = add_research_indicators(bars)

    assert result["SignalEfficiencyRatio"].iloc[:20].isna().all()
    assert result["SignalEfficiencyRatio"].iloc[20] == pytest.approx(1.0)


def test_batch4_bars_since_open_starts_at_zero_and_resets_at_session_boundary():
    bars = make_bars(
        volumes=[100.0] * 10,
        session_dates=["2026-01-02"] * 5 + ["2026-01-05"] * 5,
        session_minutes=[0, 5, 10, 15, 20, 0, 5, 10, 15, 20],
    )

    result = add_research_indicators(bars)

    assert result["SignalBarsSinceOpen"].iloc[0] == pytest.approx(0.0)
    assert result["SignalBarsSinceOpen"].iloc[4] == pytest.approx(4.0)
    assert result["SignalBarsSinceOpen"].iloc[5] == pytest.approx(0.0)
    assert result["SignalBarsSinceOpen"].iloc[9] == pytest.approx(4.0)


def test_batch4_columns_are_nan_for_non_rth_rows():
    bars = make_bars(
        volumes=[100.0, 100.0, 100.0],
        session_minutes=[-5, 100, 400],
    )
    batch4_columns = [
        "SignalAutoCorr",
        "SignalVarRatio",
        "SignalADX",
        "SignalEfficiencyRatio",
        "SignalBarsSinceOpen",
    ]

    result = add_research_indicators(bars)

    for col in batch4_columns:
        assert pd.isna(result.loc[0, col]), f"{col} should be NaN for pre-RTH row"
        assert pd.isna(result.loc[2, col]), f"{col} should be NaN for post-RTH row"
