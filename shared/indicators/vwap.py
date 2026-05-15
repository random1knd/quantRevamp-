from __future__ import annotations

import pandas as pd


VWAP_NAME = "SessionVWAP"


def typical_price(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    return (high + low + close) / 3.0


def session_vwap(
    frame: pd.DataFrame,
    *,
    price_col: str,
    volume_col: str,
    session_col: str,
) -> pd.Series:
    missing = [
        column
        for column in (price_col, volume_col, session_col)
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    if frame.empty:
        return pd.Series(index=frame.index, dtype="float64", name=VWAP_NAME)

    price = frame[price_col]
    volume = frame[volume_col]
    session = frame[session_col]

    if price.isna().any():
        raise ValueError("price values must not be null")

    if session.isna().any():
        raise ValueError("session values must not be null")

    if volume.isna().any() or (volume <= 0).any():
        raise ValueError("volume must be positive")

    price_volume = price * volume
    cumulative_price_volume = price_volume.groupby(session, sort=False).cumsum()
    cumulative_volume = volume.groupby(session, sort=False).cumsum()

    result = cumulative_price_volume / cumulative_volume
    result.name = VWAP_NAME
    return result
