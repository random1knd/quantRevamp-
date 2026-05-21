from __future__ import annotations

import pandas as pd

from shared.indicators.candle import body_ratio, close_position
from shared.indicators.order_flow import cumulative_delta
from shared.indicators.volatility import (
    atr_percentile,
    realized_volatility,
    session_atr,
)
from shared.indicators.volume import volume_ratio, volume_robust_zscore
from shared.indicators.vwap import (
    session_vwap,
    typical_price,
    vwap_distance,
    vwap_distance_atr_normalized,
)
from shared.indicators.zscore import gap_free_rolling_window
from strategies.vwap_zscore_fade.parent import params


REQUIRED_COLUMNS = (
    "SessionDate_ET",
    "SessionMinute_ET",
    "BarGapFromPrevious",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "BidVolume",
    "AskVolume",
)

RESEARCH_INDICATOR_COLUMNS = (
    "EntryVolumeZ",
    "EntryDelta",
    "EntryDeltaPct",
    "EntryBodyRatio",
    "EntryClosePosition",
    "EntryVWAPDist",
    "EntryVWAPDistATR",
    "EntryRealizedVol",
    "EntryVolRatio",
    "EntryVolRobustZ",
    "EntryATRPctile",
    "EntryCumDelta",
)


def add_research_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    """Add post-trade research context fields for later slicing."""

    _validate_required_columns(bars)

    result = bars.copy()
    for column in RESEARCH_INDICATOR_COLUMNS:
        result[column] = pd.Series(index=result.index, dtype="float64")

    rth_mask = _rth_rows(result)
    if not rth_mask.any():
        return result

    rth = result.loc[rth_mask].copy()
    rth["EntryVolumeZ"] = _session_standard_zscore(
        rth["Volume"],
        session=rth["SessionDate_ET"],
        bar_gap=rth["BarGapFromPrevious"],
        window=params.VOLUME_Z_WINDOW,
    )
    rth["EntryDelta"] = rth["AskVolume"] - rth["BidVolume"]
    rth["EntryDeltaPct"] = rth["EntryDelta"] / rth["Volume"].mask(
        rth["Volume"] == 0.0
    )
    _typical = typical_price(rth["High"], rth["Low"], rth["Close"])
    rth["_TP"] = _typical
    _vwap = pd.Series(index=rth.index, dtype="float64")
    positive_volume = rth["Volume"] > 0.0
    if positive_volume.any():
        _vwap.loc[positive_volume] = session_vwap(
            rth.loc[positive_volume].copy(),
            price_col="_TP",
            volume_col="Volume",
            session_col="SessionDate_ET",
        )
    _atr = session_atr(
        rth,
        high_col="High",
        low_col="Low",
        close_col="Close",
        session_col="SessionDate_ET",
        window=params.ATR_WINDOW,
    )
    rth["EntryBodyRatio"] = body_ratio(
        rth["Open"],
        rth["High"],
        rth["Low"],
        rth["Close"],
    )
    rth["EntryClosePosition"] = close_position(
        rth["High"],
        rth["Low"],
        rth["Close"],
    )
    _dist = vwap_distance(rth["Close"], _vwap)
    rth["EntryVWAPDist"] = _dist
    rth["EntryVWAPDistATR"] = vwap_distance_atr_normalized(_dist, _atr)
    _returns = rth["Close"].pct_change()
    rth["EntryRealizedVol"] = realized_volatility(_returns, window=20)
    rth["EntryVolRatio"] = volume_ratio(rth["Volume"], window=20)
    rth["EntryVolRobustZ"] = volume_robust_zscore(rth["Volume"], window=20)
    rth["EntryATRPctile"] = atr_percentile(_atr, window=20)
    rth["EntryCumDelta"] = cumulative_delta(
        rth["EntryDelta"],
        session=rth["SessionDate_ET"],
    )

    result.loc[rth.index, RESEARCH_INDICATOR_COLUMNS] = rth.loc[
        :, RESEARCH_INDICATOR_COLUMNS
    ]
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


def _session_standard_zscore(
    values: pd.Series,
    *,
    session: pd.Series,
    bar_gap: pd.Series,
    window: int,
) -> pd.Series:
    rolling_mean = values.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).mean()
    )
    rolling_std = values.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).std()
    )
    zscore = (values - rolling_mean) / rolling_std.mask(rolling_std == 0.0)
    return zscore.mask(
        ~gap_free_rolling_window(
            bar_gap,
            session=session,
            window=window,
        )
    )
