from __future__ import annotations

import pandas as pd

from shared.indicators.zscore import rolling_percentile


VPIN_APPROX_NAME = "VPIN_Approx"
KYLE_LAMBDA_NAME = "KyleLambda"
KYLE_LAMBDA_PCTILE_NAME = "KyleLambda_Pctile"


def vpin_approx(
    bars: pd.DataFrame,
    *,
    window: int,
) -> pd.Series:
    _validate_columns(bars, ("BidVolume", "AskVolume", "Volume"))
    _validate_positive_window(window)

    # Time-bar approximation. Not volume-synchronized VPIN.
    # Context-only.
    volume = bars["Volume"].mask(bars["Volume"] == 0.0)
    imbalance = (bars["AskVolume"] - bars["BidVolume"]).abs() / volume
    result = imbalance.rolling(window=window, min_periods=window).mean()
    result.name = VPIN_APPROX_NAME
    return result


def kyle_lambda(
    price_change: pd.Series,
    signed_volume: pd.Series,
    *,
    window: int,
) -> pd.Series:
    _validate_positive_window(window)
    rolling_cov = price_change.rolling(window=window, min_periods=window).cov(
        signed_volume
    )
    rolling_var = signed_volume.rolling(window=window, min_periods=window).var()
    result = rolling_cov / rolling_var.mask(rolling_var == 0.0)
    result.name = KYLE_LAMBDA_NAME
    return result


def kyle_lambda_percentile(
    series: pd.Series,
    *,
    window: int,
) -> pd.Series:
    result = rolling_percentile(series, window=window)
    result.name = KYLE_LAMBDA_PCTILE_NAME
    return result


def _validate_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")


def _validate_positive_window(window: int) -> None:
    if window <= 0:
        raise ValueError(f"window must be positive, got: {window}")
