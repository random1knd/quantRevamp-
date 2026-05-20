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
