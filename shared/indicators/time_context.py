from __future__ import annotations

import pandas as pd


SESSION_PROGRESS_NAME = "SessionProgress"
BARS_SINCE_OPEN_NAME = "BarsSinceOpen"
HOUR_NAME = "Hour"
DAY_OF_WEEK_NAME = "DayOfWeek"


def session_progress(
    datetime_series: pd.Series,
    *,
    session_open_time,
    session_close_time,
    timezone: str,
) -> pd.Series:
    local = datetime_series.dt.tz_convert(timezone)
    local_seconds = local.dt.hour * 3600 + local.dt.minute * 60 + local.dt.second
    open_seconds = (
        session_open_time.hour * 3600
        + session_open_time.minute * 60
        + session_open_time.second
    )
    close_seconds = (
        session_close_time.hour * 3600
        + session_close_time.minute * 60
        + session_close_time.second
    )
    session_duration = close_seconds - open_seconds
    in_session = (local_seconds >= open_seconds) & (local_seconds < close_seconds)
    result = ((local_seconds - open_seconds) / session_duration).where(in_session)
    result.name = SESSION_PROGRESS_NAME
    return result


def bars_since_open(
    *,
    session: pd.Series,
) -> pd.Series:
    result = session.groupby(session, sort=False).cumcount()
    result.name = BARS_SINCE_OPEN_NAME
    return result


def hour_of_day(
    datetime_series: pd.Series,
    *,
    timezone: str,
) -> pd.Series:
    result = datetime_series.dt.tz_convert(timezone).dt.hour
    result.name = HOUR_NAME
    return result


def day_of_week(
    datetime_series: pd.Series,
    *,
    timezone: str,
) -> pd.Series:
    result = datetime_series.dt.tz_convert(timezone).dt.dayofweek
    result.name = DAY_OF_WEEK_NAME
    return result
