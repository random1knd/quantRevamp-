from datetime import date

import pandas as pd
import pytest

from shared.data.bars import prepare_bars, rth_only_raw_bars


def make_bars(datetimes_utc, contracts=None):
    contracts = contracts or ["NQH26"] * len(datetimes_utc)
    return pd.DataFrame(
        {
            "DateTime": datetimes_utc,
            "Open": [100.0 + i for i in range(len(datetimes_utc))],
            "High": [101.0 + i for i in range(len(datetimes_utc))],
            "Low": [99.0 + i for i in range(len(datetimes_utc))],
            "Close": [100.5 + i for i in range(len(datetimes_utc))],
            "Volume": [100 + i for i in range(len(datetimes_utc))],
            "BidVolume": [40 + i for i in range(len(datetimes_utc))],
            "AskVolume": [60 + i for i in range(len(datetimes_utc))],
            "Contract": contracts,
        }
    )


def prepare(raw):
    return prepare_bars(
        raw,
        source_timezone="UTC",
        strategy_timezone="America/New_York",
        session_open="09:30",
        expected_bar_interval_minutes=5,
    )


def rth_only(raw):
    return rth_only_raw_bars(
        raw,
        source_timezone="UTC",
        strategy_timezone="America/New_York",
        session_open="09:30",
        rth_start_session_minute=0,
        last_rth_bar_open_session_minute=385,
    )


def test_rth_only_raw_bars_filters_source_rows_by_declared_rth_bounds():
    raw = make_bars(
        [
            "2026-01-02 13:00:00+00:00",  # 08:00 ET
            "2026-01-02 14:30:00+00:00",  # 09:30 ET
            "2026-01-02 20:55:00+00:00",  # 15:55 ET
            "2026-01-02 21:00:00+00:00",  # 16:00 ET
        ]
    )

    result = rth_only(raw)

    assert result["DateTime"].tolist() == [
        "2026-01-02 14:30:00+00:00",
        "2026-01-02 20:55:00+00:00",
    ]


def test_rth_only_raw_bars_accepts_naive_source_timestamps():
    raw = make_bars(
        [
            "2026-07-01 13:25:00",  # 09:25 ET
            "2026-07-01 13:30:00",  # 09:30 ET
            "2026-07-01 19:55:00",  # 15:55 ET
        ]
    )

    result = rth_only(raw)

    assert result["DateTime"].tolist() == [
        "2026-07-01 13:30:00",
        "2026-07-01 19:55:00",
    ]


def test_rth_only_raw_bars_rejects_missing_datetime_column():
    raw = make_bars(["2026-01-02 14:30:00"]).drop(columns=["DateTime"])

    with pytest.raises(ValueError, match="missing required column: DateTime"):
        rth_only(raw)


def test_prepare_bars_derives_timezone_aware_session_fields():
    raw = make_bars(
        [
            "2026-01-02 09:00:00",  # 04:00 ET
            "2026-01-02 14:30:00",  # 09:30 ET
            "2026-01-02 15:30:00",  # 10:30 ET
            "2026-01-02 20:30:00",  # 15:30 ET
        ]
    )

    bars = prepare(raw)

    assert len(bars) == 4
    assert str(bars["DateTime_UTC"].dt.tz) == "UTC"
    assert str(bars["DateTime_ET"].dt.tz) == "America/New_York"
    assert bars["SessionDate_ET"].tolist() == [
        date(2026, 1, 2),
        date(2026, 1, 2),
        date(2026, 1, 2),
        date(2026, 1, 2),
    ]
    assert bars["MinuteOfDay_ET"].tolist() == [240, 570, 630, 930]
    assert bars["SessionMinute_ET"].tolist() == [-330, 0, 60, 360]
    assert bars["BarGapFromPrevious"].tolist() == [False, True, True, True]
    assert pd.isna(bars.loc[0, "BarGapMinutesFromPrevious"])
    assert bars["BarGapMinutesFromPrevious"].iloc[1:].tolist() == [
        330.0,
        60.0,
        300.0,
    ]


def test_prepare_bars_uses_dst_aware_et_conversion():
    raw = make_bars(["2026-07-01 13:30:00"])

    bars = prepare(raw)

    et_time = bars.loc[0, "DateTime_ET"]
    assert et_time.hour == 9
    assert et_time.minute == 30
    assert bars.loc[0, "MinuteOfDay_ET"] == 570
    assert bars.loc[0, "SessionMinute_ET"] == 0


def test_prepare_bars_accepts_timezone_aware_source_datetimes():
    raw = make_bars(["2026-01-02 14:30:00+00:00"])

    bars = prepare(raw)

    assert str(bars["DateTime_UTC"].dt.tz) == "UTC"
    assert bars.loc[0, "DateTime_ET"].hour == 9
    assert bars.loc[0, "DateTime_ET"].minute == 30
    assert bars.loc[0, "SessionMinute_ET"] == 0


def test_prepare_bars_marks_first_session_after_contract_change_without_dropping_rows():
    raw = make_bars(
        [
            "2026-02-27 14:30:00",
            "2026-03-02 14:30:00",
            "2026-03-02 14:35:00",
            "2026-03-03 14:30:00",
        ],
        contracts=["NQH26", "NQM26", "NQM26", "NQM26"],
    )

    bars = prepare(raw)

    assert len(bars) == 4
    assert bars["Contract"].tolist() == ["NQH26", "NQM26", "NQM26", "NQM26"]
    assert bars["IsFirstSessionAfterContractChange"].tolist() == [
        False,
        True,
        True,
        False,
    ]


def test_prepare_bars_marks_a_b_a_contract_changes_as_roll_sessions():
    raw = make_bars(
        [
            "2026-02-27 14:30:00",
            "2026-03-02 14:30:00",
            "2026-03-03 14:30:00",
        ],
        contracts=["NQH26", "NQM26", "NQH26"],
    )

    bars = prepare(raw)

    assert bars["IsFirstSessionAfterContractChange"].tolist() == [False, True, True]


def test_prepare_bars_preserves_premarket_rows_instead_of_filtering():
    raw = make_bars(
        [
            "2026-01-02 09:00:00",  # 04:00 ET
            "2026-01-02 14:30:00",  # 09:30 ET
        ]
    )

    bars = prepare(raw)

    assert len(bars) == 2
    assert bars["SessionMinute_ET"].tolist() == [-330, 0]
    assert bars["BarGapFromPrevious"].tolist() == [False, True]


def test_prepare_bars_records_same_session_bar_gap_metadata():
    raw = make_bars(
        [
            "2026-01-02 14:30:00",
            "2026-01-02 14:35:00",
            "2026-01-02 14:45:00",
            "2026-01-05 14:30:00",
            "2026-01-05 14:35:00",
        ]
    )

    bars = prepare(raw)

    assert pd.isna(bars.loc[0, "BarGapMinutesFromPrevious"])
    assert pd.isna(bars.loc[3, "BarGapMinutesFromPrevious"])
    assert bars.loc[[1, 2, 4], "BarGapMinutesFromPrevious"].tolist() == [
        5.0,
        10.0,
        5.0,
    ]
    assert bars["BarGapFromPrevious"].tolist() == [
        False,
        False,
        True,
        False,
        False,
    ]


def test_prepare_bars_offset_session_policy_groups_overnight_session():
    raw = make_bars(
        [
            "2026-01-02 23:00:00",  # 18:00 ET, session minute 0
            "2026-01-02 23:10:00",  # 18:10 ET, missing one 5m bar
            "2026-01-03 04:55:00",  # 23:55 ET
            "2026-01-03 05:00:00",  # 00:00 ET
            "2026-01-03 21:55:00",  # 16:55 ET
            "2026-01-03 23:00:00",  # next session 18:00 ET
        ],
        contracts=["6EH26"] * 6,
    )

    bars = prepare_bars(
        raw,
        source_timezone="UTC",
        strategy_timezone="America/New_York",
        session_open="18:00",
        expected_bar_interval_minutes=5,
        session_date_policy="offset_after_session_open",
        session_date_offset_hours=6,
    )

    assert bars["SessionDate_ET"].tolist() == [
        date(2026, 1, 3),
        date(2026, 1, 3),
        date(2026, 1, 3),
        date(2026, 1, 3),
        date(2026, 1, 3),
        date(2026, 1, 4),
    ]
    assert bars["SessionMinute_ET"].tolist() == [0, 10, 355, 360, 1375, 0]
    assert bars["SessionMinute_ET"].iloc[:5].is_monotonic_increasing
    assert bars["BarGapFromPrevious"].tolist() == [
        False,
        True,
        True,
        False,
        True,
        False,
    ]
    assert pd.isna(bars.loc[5, "BarGapMinutesFromPrevious"])


def test_prepare_bars_offset_policy_requires_offset():
    raw = make_bars(["2026-01-02 23:00:00"], contracts=["6EH26"])

    with pytest.raises(ValueError, match="session_date_offset_hours is required"):
        prepare_bars(
            raw,
            source_timezone="UTC",
            strategy_timezone="America/New_York",
            session_open="18:00",
            expected_bar_interval_minutes=5,
            session_date_policy="offset_after_session_open",
        )


def test_prepare_bars_marks_mixed_contract_session_when_explicitly_requested():
    raw = make_bars(
        [
            "2026-01-01 23:00:00",
            "2026-01-02 23:00:00",
            "2026-01-03 00:00:00",
            "2026-01-03 23:00:00",
        ],
        contracts=["6EH26", "6EH26", "6EM26", "6EM26"],
    )

    bars = prepare_bars(
        raw,
        source_timezone="UTC",
        strategy_timezone="America/New_York",
        session_open="18:00",
        expected_bar_interval_minutes=5,
        session_date_policy="offset_after_session_open",
        session_date_offset_hours=6,
        mixed_contract_policy="mark",
    )

    assert bars["SessionDate_ET"].tolist() == [
        date(2026, 1, 2),
        date(2026, 1, 3),
        date(2026, 1, 3),
        date(2026, 1, 4),
    ]
    assert bars["MixedContractSession"].tolist() == [False, True, True, False]
    assert bars["SessionContract"].tolist() == ["6EH26", "6EM26", "6EM26", "6EM26"]
    assert bars["IsFirstSessionAfterContractChange"].tolist() == [
        False,
        True,
        True,
        False,
    ]


def test_prepare_bars_rejects_mixed_contract_session_by_default_with_offset_policy():
    raw = make_bars(
        [
            "2026-01-02 23:00:00",
            "2026-01-03 00:00:00",
        ],
        contracts=["6EH26", "6EM26"],
    )

    with pytest.raises(ValueError, match="multiple contracts in one session"):
        prepare_bars(
            raw,
            source_timezone="UTC",
            strategy_timezone="America/New_York",
            session_open="18:00",
            expected_bar_interval_minutes=5,
            session_date_policy="offset_after_session_open",
            session_date_offset_hours=6,
        )


def test_prepare_bars_rejects_non_positive_expected_bar_interval():
    raw = make_bars(["2026-01-02 14:30:00"])

    with pytest.raises(
        ValueError,
        match="expected_bar_interval_minutes must be positive",
    ):
        prepare_bars(
            raw,
            source_timezone="UTC",
            strategy_timezone="America/New_York",
            session_open="09:30",
            expected_bar_interval_minutes=0,
        )


def test_prepare_bars_rejects_missing_required_columns():
    raw = make_bars(["2026-01-02 14:30:00"]).drop(columns=["Contract"])

    with pytest.raises(ValueError, match="missing required columns"):
        prepare(raw)


def test_prepare_bars_rejects_unsorted_datetimes():
    raw = make_bars(
        [
            "2026-01-02 14:35:00",
            "2026-01-02 14:30:00",
        ]
    )

    with pytest.raises(ValueError, match="sorted by DateTime_UTC"):
        prepare(raw)


def test_prepare_bars_rejects_duplicate_datetimes():
    raw = make_bars(
        [
            "2026-01-02 14:30:00",
            "2026-01-02 14:30:00",
        ]
    )

    with pytest.raises(ValueError, match="duplicate DateTime_UTC"):
        prepare(raw)


def test_prepare_bars_rejects_multiple_contracts_inside_one_session():
    raw = make_bars(
        [
            "2026-03-02 14:30:00",
            "2026-03-02 14:35:00",
        ],
        contracts=["NQH26", "NQM26"],
    )

    with pytest.raises(ValueError, match="multiple contracts in one session"):
        prepare(raw)


def test_prepare_bars_rejects_bad_session_open_format_with_clear_message():
    raw = make_bars(["2026-01-02 14:30:00"])

    with pytest.raises(ValueError, match="session_open must be HH:MM format"):
        prepare_bars(
            raw,
            source_timezone="UTC",
            strategy_timezone="America/New_York",
            session_open="9:30",
            expected_bar_interval_minutes=5,
        )


def test_prepare_bars_rejects_invalid_session_open_value_with_clear_message():
    raw = make_bars(["2026-01-02 14:30:00"])

    with pytest.raises(ValueError, match="session_open must be HH:MM format"):
        prepare_bars(
            raw,
            source_timezone="UTC",
            strategy_timezone="America/New_York",
            session_open="25:99",
            expected_bar_interval_minutes=5,
        )
