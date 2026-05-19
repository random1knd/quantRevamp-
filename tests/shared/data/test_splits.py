from datetime import date

import pandas as pd
import pytest

from shared.data.splits import chronological_session_splits


def make_prepared_bars(session_dates: list[date]) -> pd.DataFrame:
    return pd.DataFrame({"SessionDate_ET": session_dates})


def test_chronological_session_splits_uses_30_50_20_whole_sessions():
    sessions = [date(2026, 1, day) for day in range(1, 11)]
    bars = make_prepared_bars(
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
            sessions[9],
        ]
    )

    splits = chronological_session_splits(bars)

    assert splits == {
        "discovery_end": date(2026, 1, 3),
        "validation_end": date(2026, 1, 8),
        "test_end": date(2026, 1, 10),
        "discovery_session_count": 3,
        "validation_session_count": 5,
        "test_session_count": 2,
    }
    assert isinstance(splits["discovery_end"], date)
    assert isinstance(splits["validation_end"], date)
    assert isinstance(splits["test_end"], date)


def test_chronological_session_splits_clamps_three_sessions_to_one_each():
    bars = make_prepared_bars(
        [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
    )

    splits = chronological_session_splits(bars)

    assert splits["discovery_session_count"] == 1
    assert splits["validation_session_count"] == 1
    assert splits["test_session_count"] == 1
    assert splits["discovery_end"] == date(2026, 1, 1)
    assert splits["validation_end"] == date(2026, 1, 2)
    assert splits["test_end"] == date(2026, 1, 3)


def test_chronological_session_splits_clamps_four_sessions_to_one_two_one():
    bars = make_prepared_bars(
        [
            date(2026, 1, 1),
            date(2026, 1, 2),
            date(2026, 1, 3),
            date(2026, 1, 4),
        ]
    )

    splits = chronological_session_splits(bars)

    assert splits["discovery_session_count"] == 1
    assert splits["validation_session_count"] == 2
    assert splits["test_session_count"] == 1
    assert splits["discovery_end"] == date(2026, 1, 1)
    assert splits["validation_end"] == date(2026, 1, 3)
    assert splits["test_end"] == date(2026, 1, 4)


def test_chronological_session_splits_preserves_first_seen_session_order():
    bars = make_prepared_bars(
        [
            date(2026, 1, 2),
            date(2026, 1, 2),
            date(2026, 1, 3),
            date(2026, 1, 1),
        ]
    )

    splits = chronological_session_splits(bars)

    assert splits["discovery_end"] == date(2026, 1, 2)
    assert splits["validation_end"] == date(2026, 1, 3)
    assert splits["test_end"] == date(2026, 1, 1)


def test_chronological_session_splits_rejects_missing_session_date_column():
    bars = pd.DataFrame({"DateTime_ET": []})

    with pytest.raises(ValueError, match="missing required column: SessionDate_ET"):
        chronological_session_splits(bars)


def test_chronological_session_splits_rejects_fewer_than_three_sessions():
    bars = make_prepared_bars([date(2026, 1, 1), date(2026, 1, 2)])

    with pytest.raises(ValueError, match="at least 3 sessions"):
        chronological_session_splits(bars)
