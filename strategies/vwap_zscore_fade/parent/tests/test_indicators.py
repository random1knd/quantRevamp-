import pandas as pd
import pytest

from strategies.vwap_zscore_fade.parent.indicators import (
    INDICATOR_COLUMNS,
    add_parent_indicators,
)


def make_bars(
    *,
    closes: list[float],
    volumes: list[float] | None = None,
    session_minutes: list[int] | None = None,
    session_dates: list[str] | None = None,
    bar_gaps: list[bool] | None = None,
) -> pd.DataFrame:
    count = len(closes)
    volumes = volumes or [100.0] * count
    session_minutes = session_minutes or [index * 5 for index in range(count)]
    session_dates = session_dates or ["2026-01-02"] * count
    bar_gaps = bar_gaps or [False] * count
    date_times = [
        pd.Timestamp(f"{session_date} 09:30:00", tz="America/New_York")
        + pd.Timedelta(minutes=session_minute)
        for session_date, session_minute in zip(
            session_dates,
            session_minutes,
            strict=True,
        )
    ]

    return pd.DataFrame(
        {
            "DateTime_ET": date_times,
            "SessionDate_ET": session_dates,
            "SessionMinute_ET": session_minutes,
            "BarGapFromPrevious": bar_gaps,
            "High": [close + 1.0 for close in closes],
            "Low": [close - 1.0 for close in closes],
            "Close": closes,
            "Volume": volumes,
            "BidVolume": [volume * 0.4 for volume in volumes],
            "AskVolume": [volume * 0.6 for volume in volumes],
        }
    )


def test_parent_indicators_scope_to_rth_rows_and_reset_by_session():
    bars = make_bars(
        closes=[100.0, 10.0, 20.0, 999.0, 30.0, 50.0],
        session_minutes=[-5, 0, 5, 390, 0, 5],
        session_dates=[
            "2026-01-02",
            "2026-01-02",
            "2026-01-02",
            "2026-01-02",
            "2026-01-05",
            "2026-01-05",
        ],
    )

    result = add_parent_indicators(bars)

    assert pd.isna(result.loc[0, "SessionVWAP"])
    assert pd.isna(result.loc[3, "SessionVWAP"])
    assert result.loc[1, "TypicalPrice"] == 10.0
    assert result.loc[1, "SessionVWAP"] == 10.0
    assert result.loc[2, "SessionVWAP"] == 15.0
    assert result.loc[4, "SessionVWAP"] == 30.0
    assert result.loc[5, "SessionVWAP"] == 40.0


def test_parent_indicators_use_full_windows_for_zscores_and_atr():
    closes = [100.0 + index for index in range(21)]
    volumes = [100.0 + index * 10.0 for index in range(21)]
    bars = make_bars(closes=closes, volumes=volumes)

    result = add_parent_indicators(bars)

    expected_entry_z = (
        result["VWAPDeviation"]
        / result["VWAPDeviation"].rolling(window=20, min_periods=20).std()
    )

    assert pd.isna(result.loc[18, "EntryZ"])
    assert result.loc[19, "EntryZ"] == expected_entry_z.loc[19]
    assert result.loc[20, "EntryZ"] == expected_entry_z.loc[20]
    assert pd.isna(result.loc[12, "ATR"])
    assert result.loc[13, "ATR"] == 2.0


def test_parent_indicators_mask_entry_z_when_window_has_internal_gap():
    closes = [100.0 + index for index in range(21)]
    bar_gaps = [False] * 21
    bar_gaps[10] = True
    bars = make_bars(
        closes=closes,
        bar_gaps=bar_gaps,
    )

    result = add_parent_indicators(bars)

    assert pd.isna(result.loc[18, "EntryZ"])
    assert pd.isna(result.loc[19, "EntryZ"])
    assert pd.isna(result.loc[20, "EntryZ"])


def test_parent_indicators_mask_entry_z_when_window_edge_has_gap():
    closes = [100.0 + index for index in range(21)]
    bar_gaps = [False] * 21
    bar_gaps[19] = True
    bars = make_bars(
        closes=closes,
        bar_gaps=bar_gaps,
    )

    result = add_parent_indicators(bars)

    assert pd.isna(result.loc[18, "EntryZ"])
    assert pd.isna(result.loc[19, "EntryZ"])
    assert pd.isna(result.loc[20, "EntryZ"])


def test_parent_indicators_are_causal_when_future_rows_change():
    bars = make_bars(
        closes=[100.0 + index for index in range(25)],
        volumes=[100.0 + index * 5.0 for index in range(25)],
    )
    mutated = bars.copy()
    mutated.loc[21:, "High"] = [300.0, 310.0, 320.0, 330.0]
    mutated.loc[21:, "Low"] = [250.0, 260.0, 270.0, 280.0]
    mutated.loc[21:, "Close"] = [275.0, 285.0, 295.0, 305.0]
    mutated.loc[21:, "Volume"] = [10_000.0, 20_000.0, 30_000.0, 40_000.0]
    mutated.loc[21:, "BidVolume"] = [4_000.0, 8_000.0, 12_000.0, 16_000.0]
    mutated.loc[21:, "AskVolume"] = [6_000.0, 12_000.0, 18_000.0, 24_000.0]

    original_result = add_parent_indicators(bars)
    mutated_result = add_parent_indicators(mutated)

    pd.testing.assert_frame_equal(
        original_result.loc[:20, INDICATOR_COLUMNS],
        mutated_result.loc[:20, INDICATOR_COLUMNS],
    )


def test_parent_indicators_reject_missing_required_columns():
    bars = make_bars(closes=[100.0]).drop(columns=["DateTime_ET"])

    with pytest.raises(ValueError, match="missing required columns"):
        add_parent_indicators(bars)
