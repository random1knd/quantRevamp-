from __future__ import annotations

import pandas as pd

from shared.indicators.candle import body_ratio, close_position
from shared.indicators.liquidity import (
    kyle_lambda,
    kyle_lambda_percentile,
    vpin_approx,
)
from shared.indicators.order_flow import cumulative_delta, delta_roc, ofi_approx
from shared.indicators.regime import rolling_autocorr, rolling_variance_ratio
from shared.indicators.time_context import bars_since_open
from shared.indicators.trend import adx, efficiency_ratio
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
    "SignalVolumeZ",
    "SignalDelta",
    "SignalDeltaPct",
    "SignalBodyRatio",
    "SignalClosePosition",
    "SignalVWAPDist",
    "SignalVWAPDistATR",
    "SignalRealizedVol",
    "SignalVolRatio",
    "SignalVolRobustZ",
    "SignalATRPctile",
    "SignalCumDelta",
    "SignalDeltaROC",
    "SignalOFI",
    "SignalVPIN",
    "SignalKyleLambda",
    "SignalKyleLambdaPctile",
    "SignalAutoCorr",
    "SignalVarRatio",
    "SignalADX",
    "SignalEfficiencyRatio",
    "SignalBarsSinceOpen",
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
    session = rth["SessionDate_ET"]
    rth["SignalVolumeZ"] = _session_standard_zscore(
        rth["Volume"],
        session=session,
        bar_gap=rth["BarGapFromPrevious"],
        window=params.VOLUME_Z_WINDOW,
    )
    rth["SignalDelta"] = rth["AskVolume"] - rth["BidVolume"]
    rth["SignalDeltaPct"] = rth["SignalDelta"] / rth["Volume"].mask(
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
    rth["SignalBodyRatio"] = body_ratio(
        rth["Open"],
        rth["High"],
        rth["Low"],
        rth["Close"],
    )
    rth["SignalClosePosition"] = close_position(
        rth["High"],
        rth["Low"],
        rth["Close"],
    )
    _dist = vwap_distance(rth["Close"], _vwap)
    rth["SignalVWAPDist"] = _dist
    rth["SignalVWAPDistATR"] = vwap_distance_atr_normalized(_dist, _atr)
    rth["SignalRealizedVol"] = _session_realized_volatility(
        rth["Close"],
        session=session,
        window=20,
    )
    rth["SignalVolRatio"] = volume_ratio(rth["Volume"], window=20)
    rth["SignalVolRobustZ"] = volume_robust_zscore(rth["Volume"], window=20)
    rth["SignalATRPctile"] = atr_percentile(_atr, window=20)
    rth["SignalCumDelta"] = cumulative_delta(
        rth["SignalDelta"],
        session=session,
    )
    rth["SignalDeltaROC"] = _session_delta_roc(
        rth["SignalDelta"],
        session=session,
        lookback=5,
    )
    rth["SignalOFI"] = _session_ofi_approx(rth, session=session)
    rth["SignalVPIN"] = vpin_approx(rth, window=20)
    _kyle = _session_kyle_lambda(
        close=rth["Close"],
        signed_volume=rth["SignalDelta"],
        session=session,
        window=20,
    )
    rth["SignalKyleLambda"] = _kyle
    rth["SignalKyleLambdaPctile"] = kyle_lambda_percentile(_kyle, window=20)
    rth["SignalAutoCorr"] = _session_return_autocorr(
        rth["Close"],
        session=session,
        window=20,
        lag=1,
    )
    rth["SignalVarRatio"] = _session_rolling_variance_ratio(
        rth["Close"],
        session=session,
        window=20,
        q=2,
    )
    rth["SignalADX"] = adx(rth, window=14)["ADX"]
    rth["SignalEfficiencyRatio"] = efficiency_ratio(rth["Close"], window=20)
    rth["SignalBarsSinceOpen"] = bars_since_open(session=session)

    result.loc[rth.index, RESEARCH_INDICATOR_COLUMNS] = rth.loc[
        :, RESEARCH_INDICATOR_COLUMNS
    ]
    return result


def _session_realized_volatility(
    close: pd.Series,
    *,
    session: pd.Series,
    window: int,
) -> pd.Series:
    return close.groupby(session, sort=False).transform(
        lambda group: realized_volatility(group.pct_change(), window=window)
    )


def _session_kyle_lambda(
    *,
    close: pd.Series,
    signed_volume: pd.Series,
    session: pd.Series,
    window: int,
) -> pd.Series:
    result = pd.Series(index=close.index, dtype="float64")
    for _, group in close.groupby(session, sort=False):
        group_signed_volume = signed_volume.loc[group.index]
        result.loc[group.index] = kyle_lambda(
            group.diff(),
            group_signed_volume,
            window=window,
        )
    return result


def _session_delta_roc(
    delta: pd.Series,
    *,
    session: pd.Series,
    lookback: int,
) -> pd.Series:
    return delta.groupby(session, sort=False).transform(
        lambda group: delta_roc(group, lookback=lookback)
    )


def _session_ofi_approx(
    bars: pd.DataFrame,
    *,
    session: pd.Series,
) -> pd.Series:
    result = pd.Series(index=bars.index, dtype="float64")
    for _, group in bars.groupby(session, sort=False):
        result.loc[group.index] = ofi_approx(group)
    return result


def _session_rolling_autocorr(
    values: pd.Series,
    *,
    session: pd.Series,
    window: int,
    lag: int,
) -> pd.Series:
    return values.groupby(session, sort=False).transform(
        lambda group: rolling_autocorr(group, window=window, lag=lag)
    )


def _session_return_autocorr(
    close: pd.Series,
    *,
    session: pd.Series,
    window: int,
    lag: int,
) -> pd.Series:
    returns = close.groupby(session, sort=False).transform(
        lambda group: group.pct_change()
    )
    return _session_rolling_autocorr(
        returns,
        session=session,
        window=window,
        lag=lag,
    )


def _session_rolling_variance_ratio(
    values: pd.Series,
    *,
    session: pd.Series,
    window: int,
    q: int,
) -> pd.Series:
    return values.groupby(session, sort=False).transform(
        lambda group: rolling_variance_ratio(group, window=window, q=q)
    )


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
