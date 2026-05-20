from __future__ import annotations

import pandas as pd

from shared.indicators.zscore import rolling_percentile


TRUE_RANGE_NAME = "TrueRange"
ATR_NAME = "ATR"
REALIZED_VOLATILITY_NAME = "RealizedVolatility"
VOL_PERCENTILE_NAME = "VolPercentile"
ATR_PERCENTILE_NAME = "ATRPercentile"


def true_range(
    frame: pd.DataFrame,
    *,
    high_col: str,
    low_col: str,
    close_col: str,
    session_col: str,
) -> pd.Series:
    _validate_columns(
        frame,
        columns=(high_col, low_col, close_col, session_col),
    )

    if frame.empty:
        return pd.Series(index=frame.index, dtype="float64", name=TRUE_RANGE_NAME)

    high = frame[high_col]
    low = frame[low_col]
    close = frame[close_col]
    session = frame[session_col]

    _validate_ohlc(high=high, low=low, close=close)
    _validate_session(session)

    previous_close = close.groupby(session, sort=False).shift(1)
    ranges = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    )

    result = ranges.max(axis=1)
    result.name = TRUE_RANGE_NAME
    return result


def session_atr(
    frame: pd.DataFrame,
    *,
    high_col: str,
    low_col: str,
    close_col: str,
    session_col: str,
    window: int,
) -> pd.Series:
    if window <= 0:
        raise ValueError(f"window must be positive, got: {window}")

    true_ranges = true_range(
        frame,
        high_col=high_col,
        low_col=low_col,
        close_col=close_col,
        session_col=session_col,
    )

    if frame.empty:
        return pd.Series(index=frame.index, dtype="float64", name=ATR_NAME)

    session = frame[session_col]
    result = true_ranges.groupby(session, sort=False).transform(
        lambda values: values.rolling(window=window, min_periods=window).mean()
    )
    result.name = ATR_NAME
    return result


def realized_volatility(
    returns: pd.Series,
    *,
    window: int,
) -> pd.Series:
    if window <= 0:
        raise ValueError(f"window must be positive, got: {window}")

    # Does not reset at session boundaries. Caller is responsible for handling
    # session-boundary returns (e.g. NaN-ing the first bar of each session) if
    # session-scoped vol is needed.
    result = returns.rolling(window=window, min_periods=window).std()
    result.name = REALIZED_VOLATILITY_NAME
    return result


def vol_percentile(
    series: pd.Series,
    *,
    window: int,
) -> pd.Series:
    # Delegates to rolling_percentile - bar N is not in its own reference set.
    result = rolling_percentile(series, window=window)
    result.name = VOL_PERCENTILE_NAME
    return result


def atr_percentile(
    series: pd.Series,
    *,
    window: int,
) -> pd.Series:
    # Delegates to rolling_percentile - bar N is not in its own reference set.
    result = rolling_percentile(series, window=window)
    result.name = ATR_PERCENTILE_NAME
    return result


def _validate_columns(
    frame: pd.DataFrame,
    *,
    columns: tuple[str, ...],
) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")


def _validate_ohlc(
    *,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> None:
    if high.isna().any() or low.isna().any() or close.isna().any():
        raise ValueError("OHLC values must not be null")

    if (high < low).any():
        raise ValueError("high must be greater than or equal to low")


def _validate_session(session: pd.Series) -> None:
    if session.isna().any():
        raise ValueError("session values must not be null")
