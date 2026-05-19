from datetime import date

import pandas as pd

from strategies.vwap_zscore_fade.parent.discovery_run import (
    COMMISSION_IS_SMOKE_TEST,
    COMMISSION_PER_ROUND_TURN,
    discovery_split_bars,
)


def make_prepared_bars(session_dates: list[date]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SessionDate_ET": session_dates,
            "DateTime_UTC": pd.date_range(
                "2026-01-01 14:30:00",
                periods=len(session_dates),
                freq="5min",
                tz="UTC",
            ),
        }
    )


def test_discovery_split_bars_keeps_only_discovery_sessions():
    sessions = [date(2026, 1, day) for day in range(1, 11)]
    prepared = make_prepared_bars(
        [
            sessions[0],
            sessions[0],
            sessions[1],
            sessions[2],
            sessions[2],
            sessions[3],
            sessions[4],
            sessions[5],
            sessions[6],
            sessions[7],
            sessions[8],
            sessions[9],
        ]
    )

    discovery, splits = discovery_split_bars(prepared)

    assert splits["discovery_end"] == date(2026, 1, 3)
    assert splits["discovery_session_count"] == 3
    assert splits["validation_session_count"] == 5
    assert splits["test_session_count"] == 2
    assert discovery["SessionDate_ET"].tolist() == [
        date(2026, 1, 1),
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
        date(2026, 1, 3),
    ]


def test_discovery_run_uses_real_commission_not_smoke_label():
    assert COMMISSION_PER_ROUND_TURN == 5.16
    assert COMMISSION_IS_SMOKE_TEST is False
