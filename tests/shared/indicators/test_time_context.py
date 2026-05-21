import datetime

import pandas as pd
import pytest

from shared.indicators.time_context import (
    bars_since_open,
    day_of_week,
    hour_of_day,
    session_progress,
)


def test_hour_of_day_converts_utc_to_eastern():
    timestamps = pd.Series([pd.Timestamp("2024-01-15 14:30:00", tz="UTC")])

    result = hour_of_day(timestamps, timezone="America/New_York")

    assert result.name == "Hour"
    assert result.iloc[0] == 9


def test_day_of_week_returns_known_monday_after_timezone_conversion():
    timestamps = pd.Series([pd.Timestamp("2024-01-15 14:30:00", tz="UTC")])

    result = day_of_week(timestamps, timezone="America/New_York")

    assert result.name == "DayOfWeek"
    assert result.iloc[0] == 0


def test_bars_since_open_resets_at_session_boundary():
    session = pd.Series(["a", "a", "a", "b", "b"])

    result = bars_since_open(session=session)

    assert result.name == "BarsSinceOpen"
    assert result.tolist() == [0, 1, 2, 0, 1]


def test_bars_since_open_accumulates_single_session():
    session = pd.Series(["a", "a", "a", "a"])

    result = bars_since_open(session=session)

    assert result.tolist() == [0, 1, 2, 3]


def test_session_progress_returns_zero_at_session_open():
    timestamps = pd.Series([pd.Timestamp("2024-01-15 14:30:00", tz="UTC")])

    result = session_progress(
        timestamps,
        session_open_time=datetime.time(9, 30),
        session_close_time=datetime.time(16, 0),
        timezone="America/New_York",
    )

    assert result.name == "SessionProgress"
    assert result.iloc[0] == pytest.approx(0.0)


def test_session_progress_returns_half_at_midpoint():
    timestamps = pd.Series([pd.Timestamp("2024-01-15 17:45:00", tz="UTC")])

    result = session_progress(
        timestamps,
        session_open_time=datetime.time(9, 30),
        session_close_time=datetime.time(16, 0),
        timezone="America/New_York",
    )

    assert result.iloc[0] == pytest.approx(0.5)


def test_session_progress_returns_nan_before_session():
    timestamps = pd.Series([pd.Timestamp("2024-01-15 14:00:00", tz="UTC")])

    result = session_progress(
        timestamps,
        session_open_time=datetime.time(9, 30),
        session_close_time=datetime.time(16, 0),
        timezone="America/New_York",
    )

    assert pd.isna(result.iloc[0])


def test_session_progress_returns_nan_at_session_close_boundary():
    timestamps = pd.Series([pd.Timestamp("2024-01-15 21:00:00", tz="UTC")])

    result = session_progress(
        timestamps,
        session_open_time=datetime.time(9, 30),
        session_close_time=datetime.time(16, 0),
        timezone="America/New_York",
    )

    assert pd.isna(result.iloc[0])


def test_bars_since_open_is_causal_when_future_session_changes():
    session = pd.Series(["a", "a", "a", "b", "b"])
    mutated = session.copy()
    mutated.iloc[2] = "c"

    original = bars_since_open(session=session)
    changed = bars_since_open(session=mutated)

    assert original.iloc[1] == changed.iloc[1]
