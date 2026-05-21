from __future__ import annotations

import pandas as pd


BODY_RATIO_NAME = "BodyRatio"
CLOSE_POSITION_NAME = "ClosePosition"


def body_ratio(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    denominator = high - low
    result = (close - open_).abs() / denominator.mask(denominator == 0.0)
    result.name = BODY_RATIO_NAME
    return result


def close_position(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    denominator = high - low
    result = (close - low) / denominator.mask(denominator == 0.0)
    result.name = CLOSE_POSITION_NAME
    return result
