from __future__ import annotations

import pandas as pd


TRUE_RANGE_NAME = "TrueRange"
ATR_NAME = "ATR"


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
