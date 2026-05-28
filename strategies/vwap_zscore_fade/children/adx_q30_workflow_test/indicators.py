from __future__ import annotations

import pandas as pd

from shared.indicators.trend import adx
from shared.indicators.volatility import session_atr
from shared.indicators.vwap import session_vwap, typical_price
from shared.indicators.zscore import gap_free_rolling_window
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import params


REQUIRED_COLUMNS = (
    "DateTime_ET",
    "SessionDate_ET",
    "SessionMinute_ET",
    "BarGapFromPrevious",
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
    "ADX",
)


def add_child_indicators(
    bars: pd.DataFrame,
    *,
    rth_start_session_minute: int | None = None,
    last_rth_bar_open_session_minute: int | None = None,
) -> pd.DataFrame:
    """Add demonstration-child trade-driving indicators."""

    _validate_required_columns(bars)

    result = bars.copy()
    for column in INDICATOR_COLUMNS:
        result[column] = pd.Series(index=result.index, dtype="float64")

    rth_start = (
        params.RTH_START_SESSION_MINUTE
        if rth_start_session_minute is None
        else int(rth_start_session_minute)
    )
    last_rth_bar_open = (
        params.LAST_RTH_BAR_OPEN_SESSION_MINUTE
        if last_rth_bar_open_session_minute is None
        else int(last_rth_bar_open_session_minute)
    )
    _validate_session_bounds(
        rth_start_session_minute=rth_start,
        last_rth_bar_open_session_minute=last_rth_bar_open,
    )

    rth_mask = _rth_rows(
        result,
        rth_start_session_minute=rth_start,
        last_rth_bar_open_session_minute=last_rth_bar_open,
    )
    if not rth_mask.any():
        return result

    rth = result.loc[rth_mask].copy()
    rth["TypicalPrice"] = typical_price(
        high=rth["High"],
        low=rth["Low"],
        close=rth["Close"],
    )
    rth["SessionVWAP"] = pd.Series(index=rth.index, dtype="float64")
    positive_volume = rth["Volume"] > 0.0
    if positive_volume.any():
        rth.loc[positive_volume, "SessionVWAP"] = session_vwap(
            rth.loc[positive_volume].copy(),
            price_col="TypicalPrice",
            volume_col="Volume",
            session_col="SessionDate_ET",
        )
    rth["VWAPDeviation"] = rth["Close"] - rth["SessionVWAP"]
    rth["EntryZ"] = _session_deviation_zscore(
        rth["VWAPDeviation"],
        session=rth["SessionDate_ET"],
        bar_gap=rth["BarGapFromPrevious"],
        window=params.Z_WINDOW,
    )
    rth["ATR"] = session_atr(
        rth,
        high_col="High",
        low_col="Low",
        close_col="Close",
        session_col="SessionDate_ET",
        window=params.ATR_WINDOW,
    )
    rth["ADX"] = _session_adx(
        rth,
        session=rth["SessionDate_ET"],
        window=params.ADX_WINDOW,
    )

    result.loc[rth.index, INDICATOR_COLUMNS] = rth.loc[:, INDICATOR_COLUMNS]
    return result


def _validate_required_columns(bars: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in bars.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")


def _validate_session_bounds(
    *,
    rth_start_session_minute: int,
    last_rth_bar_open_session_minute: int,
) -> None:
    if rth_start_session_minute < 0:
        raise ValueError("rth_start_session_minute must be non-negative")
    if last_rth_bar_open_session_minute < rth_start_session_minute:
        raise ValueError(
            "last_rth_bar_open_session_minute must be >= "
            "rth_start_session_minute"
        )


def _rth_rows(
    bars: pd.DataFrame,
    *,
    rth_start_session_minute: int,
    last_rth_bar_open_session_minute: int,
) -> pd.Series:
    return bars["SessionMinute_ET"].between(
        rth_start_session_minute,
        last_rth_bar_open_session_minute,
    )


def _session_deviation_zscore(
    values: pd.Series,
    *,
    session: pd.Series,
    bar_gap: pd.Series,
    window: int,
) -> pd.Series:
    rolling_std = _session_rolling_std(values, session=session, window=window)
    zscore = values / rolling_std.mask(rolling_std == 0.0)
    gap_free_window = gap_free_rolling_window(
        bar_gap,
        session=session,
        window=window,
    )
    return zscore.mask(~gap_free_window)


def _session_rolling_std(
    values: pd.Series,
    *,
    session: pd.Series,
    window: int,
) -> pd.Series:
    return values.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).std()
    )


def _session_adx(
    bars: pd.DataFrame,
    *,
    session: pd.Series,
    window: int,
) -> pd.Series:
    result = pd.Series(index=bars.index, dtype="float64")
    for _, group in bars.groupby(session, sort=False):
        result.loc[group.index] = adx(group, window=window)["ADX"]
    return result
