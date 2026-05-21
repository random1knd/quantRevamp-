from __future__ import annotations

import pandas as pd


DELTA_NAME = "Delta"
CUM_DELTA_NAME = "CumDelta"
DELTA_ROC_NAME = "DeltaROC"
OFI_APPROX_NAME = "OFI_Approx"


def delta(
    bid_volume: pd.Series,
    ask_volume: pd.Series,
) -> pd.Series:
    result = ask_volume - bid_volume
    result.name = DELTA_NAME
    return result


def cumulative_delta(
    delta: pd.Series,
    *,
    session: pd.Series,
) -> pd.Series:
    result = delta.groupby(session, sort=False).cumsum()
    result.name = CUM_DELTA_NAME
    return result


def delta_roc(
    delta: pd.Series,
    *,
    lookback: int,
) -> pd.Series:
    if lookback <= 0:
        raise ValueError(f"lookback must be positive, got: {lookback}")

    result = delta - delta.shift(lookback)
    result.name = DELTA_ROC_NAME
    return result


def ofi_approx(bars: pd.DataFrame) -> pd.Series:
    _validate_columns(bars, columns=("BidVolume", "AskVolume"))

    # Time-bar approximation. Not equivalent to true order-book OFI.
    bid_change = bars["BidVolume"].diff()
    ask_change = bars["AskVolume"].diff()
    # Context-only. Do not use for trade decisions without further review.
    result = ask_change - bid_change
    result.name = OFI_APPROX_NAME
    return result


def _validate_columns(
    frame: pd.DataFrame,
    *,
    columns: tuple[str, ...],
) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
