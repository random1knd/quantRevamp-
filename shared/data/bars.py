from __future__ import annotations

from datetime import time
import re
from typing import Literal

import pandas as pd


REQUIRED_COLUMNS = (
    "DateTime",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "BidVolume",
    "AskVolume",
    "Contract",
)


def prepare_bars(
    bars: pd.DataFrame,
    *,
    source_timezone: str,
    strategy_timezone: str,
    session_open: str,
    expected_bar_interval_minutes: int,
    session_date_policy: Literal[
        "same_day",
        "offset_after_session_open",
    ] = "same_day",
    session_date_offset_hours: int | float | None = None,
    mixed_contract_policy: Literal["reject", "mark"] = "reject",
) -> pd.DataFrame:
    """Prepare raw bars with mechanical timestamp and contract-roll fields."""

    missing = [column for column in REQUIRED_COLUMNS if column not in bars.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    if expected_bar_interval_minutes <= 0:
        raise ValueError(
            "expected_bar_interval_minutes must be positive, got: "
            f"{expected_bar_interval_minutes}"
        )

    prepared = bars.copy()
    session_open_time = _parse_session_open(session_open)

    prepared["DateTime_UTC"] = _parse_datetime(
        prepared["DateTime"],
        source_timezone=source_timezone,
    )
    if prepared["DateTime_UTC"].duplicated().any():
        raise ValueError("duplicate DateTime_UTC values are not allowed")

    if not prepared["DateTime_UTC"].is_monotonic_increasing:
        raise ValueError("bars must be sorted by DateTime_UTC ascending")

    prepared["DateTime_ET"] = prepared["DateTime_UTC"].dt.tz_convert(
        strategy_timezone
    )
    prepared["MinuteOfDay_ET"] = (
        prepared["DateTime_ET"].dt.hour * 60 + prepared["DateTime_ET"].dt.minute
    )
    prepared["SessionDate_ET"] = _session_date(
        prepared["DateTime_ET"],
        session_date_policy=session_date_policy,
        session_date_offset_hours=session_date_offset_hours,
    )
    prepared["SessionMinute_ET"] = _session_minute(
        prepared["MinuteOfDay_ET"],
        session_open_time=session_open_time,
        session_date_policy=session_date_policy,
    )
    session_contract = _session_contract(prepared)
    mixed_contract_session = _mixed_contract_session(prepared)
    if mixed_contract_policy == "reject":
        _reject_multiple_contracts_per_session(prepared, mixed_contract_session)
    elif mixed_contract_policy == "mark":
        prepared["MixedContractSession"] = mixed_contract_session
        prepared["SessionContract"] = prepared["SessionDate_ET"].map(session_contract)
    else:
        raise ValueError(f"unknown mixed_contract_policy: {mixed_contract_policy}")

    prepared["BarGapMinutesFromPrevious"] = _bar_gap_minutes_from_previous(prepared)
    prepared["BarGapFromPrevious"] = prepared["BarGapMinutesFromPrevious"].ne(
        expected_bar_interval_minutes
    ) & prepared["BarGapMinutesFromPrevious"].notna()
    prepared["IsFirstSessionAfterContractChange"] = _mark_first_session_after_contract_change(
        prepared,
        session_contract=session_contract,
        mixed_contract_session=mixed_contract_session,
    )

    return prepared


def rth_only_raw_bars(
    raw_bars: pd.DataFrame,
    *,
    source_timezone: str,
    strategy_timezone: str,
    session_open: str,
    rth_start_session_minute: int,
    last_rth_bar_open_session_minute: int,
    session_date_policy: Literal[
        "same_day",
        "offset_after_session_open",
    ] = "same_day",
) -> pd.DataFrame:
    """Filter raw source rows to declared RTH session minutes."""

    if "DateTime" not in raw_bars.columns:
        raise ValueError("missing required column: DateTime")

    source_times = pd.to_datetime(raw_bars["DateTime"], errors="raise")
    if source_times.dt.tz is None:
        source_times = source_times.dt.tz_localize(source_timezone)
    else:
        source_times = source_times.dt.tz_convert("UTC")

    session_open_time = _parse_session_open(session_open)
    strategy_times = source_times.dt.tz_convert(strategy_timezone)
    minute_of_day = strategy_times.dt.hour * 60 + strategy_times.dt.minute
    session_minute = _session_minute(
        minute_of_day,
        session_open_time=session_open_time,
        session_date_policy=session_date_policy,
    )
    rth_mask = session_minute.between(
        rth_start_session_minute,
        last_rth_bar_open_session_minute,
    )
    return raw_bars.loc[rth_mask].copy()


def _parse_datetime(
    values: pd.Series,
    *,
    source_timezone: str,
) -> pd.Series:
    parsed = pd.to_datetime(values, errors="raise")

    if parsed.dt.tz is None:
        return parsed.dt.tz_localize(source_timezone).dt.tz_convert("UTC")

    return parsed.dt.tz_convert("UTC")


def _parse_session_open(session_open: str) -> time:
    if not re.fullmatch(r"\d{2}:\d{2}", session_open):
        raise ValueError(f"session_open must be HH:MM format, got: {session_open}")

    try:
        parsed = pd.to_datetime(session_open, format="%H:%M", errors="raise")
    except ValueError as exc:
        raise ValueError(
            f"session_open must be HH:MM format, got: {session_open}"
        ) from exc

    return parsed.time()


def _session_date(
    date_time_et: pd.Series,
    *,
    session_date_policy: str,
    session_date_offset_hours: int | float | None,
) -> pd.Series:
    if session_date_policy == "same_day":
        if session_date_offset_hours is not None:
            raise ValueError(
                "session_date_offset_hours is only valid for "
                "offset_after_session_open"
            )
        return date_time_et.dt.date

    if session_date_policy == "offset_after_session_open":
        if session_date_offset_hours is None:
            raise ValueError(
                "session_date_offset_hours is required for "
                "offset_after_session_open"
            )
        return (date_time_et + pd.Timedelta(hours=session_date_offset_hours)).dt.date

    raise ValueError(f"unknown session_date_policy: {session_date_policy}")


def _session_minute(
    minute_of_day: pd.Series,
    *,
    session_open_time: time,
    session_date_policy: str,
) -> pd.Series:
    session_open_minute = session_open_time.hour * 60 + session_open_time.minute
    raw_session_minute = minute_of_day - session_open_minute
    if session_date_policy == "same_day":
        return raw_session_minute
    if session_date_policy == "offset_after_session_open":
        return raw_session_minute.mod(24 * 60)
    raise ValueError(f"unknown session_date_policy: {session_date_policy}")


def _session_contract(bars: pd.DataFrame) -> dict:
    return bars.groupby("SessionDate_ET", sort=False)["Contract"].last().to_dict()


def _mixed_contract_session(bars: pd.DataFrame) -> pd.Series:
    contract_counts = bars.groupby("SessionDate_ET", sort=False)["Contract"].transform(
        "nunique"
    )
    return contract_counts > 1


def _reject_multiple_contracts_per_session(
    bars: pd.DataFrame,
    mixed_contract_session: pd.Series,
) -> None:
    mixed_sessions = bars.loc[
        mixed_contract_session,
        "SessionDate_ET",
    ].drop_duplicates()

    if not mixed_sessions.empty:
        sessions = [str(session) for session in mixed_sessions.tolist()]
        raise ValueError(f"multiple contracts in one session: {sessions}")


def _bar_gap_minutes_from_previous(
    bars: pd.DataFrame,
) -> pd.Series:
    previous_datetime = bars.groupby("SessionDate_ET", sort=False)["DateTime_ET"].shift(
        1
    )
    gap_minutes = (
        (bars["DateTime_ET"] - previous_datetime).dt.total_seconds() / 60.0
    )
    gap_minutes.name = "BarGapMinutesFromPrevious"
    return gap_minutes


def _mark_first_session_after_contract_change(
    bars: pd.DataFrame,
    *,
    session_contract: dict,
    mixed_contract_session: pd.Series,
) -> pd.Series:
    session_contracts = (
        bars[["SessionDate_ET"]]
        .drop_duplicates()
        .assign(
            Contract=lambda frame: frame["SessionDate_ET"].map(session_contract),
        )
    )
    session_contracts["PreviousContract"] = session_contracts["Contract"].shift(1)
    session_contracts["IsRollSession"] = (
        session_contracts["PreviousContract"].notna()
        & (session_contracts["Contract"] != session_contracts["PreviousContract"])
    )

    roll_by_session = dict(
        zip(
            session_contracts["SessionDate_ET"],
            session_contracts["IsRollSession"],
            strict=True,
        )
    )
    return (
        bars["SessionDate_ET"].map(roll_by_session).astype(bool)
        | mixed_contract_session.astype(bool)
    )
