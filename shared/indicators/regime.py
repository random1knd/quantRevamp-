from __future__ import annotations

import pandas as pd
from statsmodels.tsa.stattools import adfuller


# ADF is computationally heavy and context-only; it must not drive trades.
AUTOCORR_NAME = "AutoCorr"
VARIANCE_RATIO_NAME = "VarianceRatio"
ADF_PVALUE_NAME = "ADF_PValue"


def rolling_autocorr(
    series: pd.Series,
    *,
    window: int,
    lag: int,
) -> pd.Series:
    _validate_positive_window(window, name="window")
    _validate_positive_window(lag, name="lag")

    # Does not reset at session boundaries.
    shifted = series.shift(lag)
    result = series.rolling(window=window, min_periods=window).corr(shifted)
    result.name = AUTOCORR_NAME
    return result


def rolling_variance_ratio(
    series: pd.Series,
    *,
    window: int,
    q: int,
) -> pd.Series:
    _validate_positive_window(window, name="window")
    _validate_positive_window(q, name="q")

    # VR > 1 is trending, VR < 1 is mean-reverting, VR = 1 is random-walk-like.
    # Does not reset at session boundaries.
    returns_1 = series.diff(1)
    returns_q = series.diff(q)
    var_1 = returns_1.rolling(window=window, min_periods=window).var()
    var_q = returns_q.rolling(window=window, min_periods=window).var()
    result = var_q / (q * var_1.mask(var_1 == 0.0))
    result.name = VARIANCE_RATIO_NAME
    return result


def rolling_adf_pvalue(
    series: pd.Series,
    *,
    window: int,
) -> pd.Series:
    _validate_positive_window(window, name="window")

    # Does not reset at session boundaries.
    result = series.rolling(window=window, min_periods=window).apply(
        _adf_pvalue,
        raw=True,
    )
    result.name = ADF_PVALUE_NAME
    return result


def _adf_pvalue(window_values) -> float:
    try:
        return adfuller(window_values, autolag="AIC")[1]
    except Exception:
        return float("nan")


def _validate_positive_window(value: int, *, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got: {value}")
