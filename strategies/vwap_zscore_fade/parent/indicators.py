from __future__ import annotations

import pandas as pd

from shared.indicators.volatility import session_atr
from shared.indicators.vwap import session_vwap, typical_price
from strategies.vwap_zscore_fade.parent import params


REQUIRED_COLUMNS = (
    "DateTime_ET",
    "SessionDate_ET",
    "SessionMinute_ET",
    "High",
    "Low",
    "Close",
    "Volume",
)

INDICATOR_COLUMNS = (
    "TypicalPrice",
    "SessionVWAP",
    "VWAPDeviation",
    "EntryZ",
    "ATR",
)


def add_parent_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    """Add v0 parent trade-driving indicators."""

    _validate_required_columns(bars)

    result = bars.copy()
    for column in INDICATOR_COLUMNS:
        result[column] = pd.Series(index=result.index, dtype="float64")

    rth_mask = _rth_rows(result)
    if not rth_mask.any():
        return result

    rth = result.loc[rth_mask].copy()
    rth["TypicalPrice"] = typical_price(
        high=rth["High"],
        low=rth["Low"],
        close=rth["Close"],
    )
    rth["SessionVWAP"] = session_vwap(
        rth,
        price_col="TypicalPrice",
        volume_col="Volume",
        session_col="SessionDate_ET",
    )
    rth["VWAPDeviation"] = rth["Close"] - rth["SessionVWAP"]
    rth["EntryZ"] = _session_deviation_zscore(
        rth["VWAPDeviation"],
        session=rth["SessionDate_ET"],
        timestamps=rth["DateTime_ET"],
        window=params.Z_WINDOW,
        bar_interval_minutes=params.BAR_INTERVAL_MINUTES,
    )
    rth["ATR"] = session_atr(
        rth,
        high_col="High",
        low_col="Low",
        close_col="Close",
        session_col="SessionDate_ET",
        window=params.ATR_WINDOW,
    )

    result.loc[rth.index, INDICATOR_COLUMNS] = rth.loc[:, INDICATOR_COLUMNS]
    return result


def _validate_required_columns(bars: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in bars.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")


def _rth_rows(bars: pd.DataFrame) -> pd.Series:
    return bars["SessionMinute_ET"].between(
        params.RTH_START_SESSION_MINUTE,
        params.LAST_RTH_BAR_OPEN_SESSION_MINUTE,
    )


def _session_deviation_zscore(
    values: pd.Series,
    *,
    session: pd.Series,
    timestamps: pd.Series,
    window: int,
    bar_interval_minutes: int,
) -> pd.Series:
    rolling_std = _session_rolling_std(values, session=session, window=window)
    zscore = values / rolling_std.mask(rolling_std == 0.0)
    valid_span = _valid_rolling_window_span(
        timestamps,
        session=session,
        window=window,
        bar_interval_minutes=bar_interval_minutes,
    )
    return zscore.mask(~valid_span)


def _session_rolling_std(
    values: pd.Series,
    *,
    session: pd.Series,
    window: int,
) -> pd.Series:
    return values.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).std()
    )


def _valid_rolling_window_span(
    timestamps: pd.Series,
    *,
    session: pd.Series,
    window: int,
    bar_interval_minutes: int,
) -> pd.Series:
    window_start = timestamps.groupby(session, sort=False).transform(
        lambda group: group.shift(window - 1)
    )
    span = timestamps - window_start
    max_span = pd.Timedelta(
        minutes=(window - 1) * bar_interval_minutes + bar_interval_minutes / 2
    )
    return span.notna() & span.le(max_span)
