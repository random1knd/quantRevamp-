from __future__ import annotations

import pandas as pd

from shared.indicators.volatility import session_atr
from shared.indicators.vwap import session_vwap, typical_price
from strategies.vwap_zscore_fade.parent import params


REQUIRED_COLUMNS = (
    "SessionDate_ET",
    "SessionMinute_ET",
    "High",
    "Low",
    "Close",
    "Volume",
    "BidVolume",
    "AskVolume",
)

INDICATOR_COLUMNS = (
    "TypicalPrice",
    "SessionVWAP",
    "VWAPDeviation",
    "EntryZ",
    "ATR",
    "EntryVolumeZ",
    "EntryDelta",
    "EntryDeltaPct",
)


def add_parent_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    """Add v0 parent trading and declared research-context indicators."""

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
    rth["EntryVolumeZ"] = _session_standard_zscore(
        rth["Volume"],
        session=rth["SessionDate_ET"],
        window=params.VOLUME_Z_WINDOW,
    )
    rth["EntryDelta"] = rth["AskVolume"] - rth["BidVolume"]
    rth["EntryDeltaPct"] = rth["EntryDelta"] / rth["Volume"]

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
    window: int,
) -> pd.Series:
    rolling_std = _session_rolling_std(values, session=session, window=window)
    return values / rolling_std.mask(rolling_std == 0.0)


def _session_standard_zscore(
    values: pd.Series,
    *,
    session: pd.Series,
    window: int,
) -> pd.Series:
    rolling_mean = values.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).mean()
    )
    rolling_std = _session_rolling_std(values, session=session, window=window)
    return (values - rolling_mean) / rolling_std.mask(rolling_std == 0.0)


def _session_rolling_std(
    values: pd.Series,
    *,
    session: pd.Series,
    window: int,
) -> pd.Series:
    return values.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).std()
    )
