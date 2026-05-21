from __future__ import annotations

import pandas as pd

from shared.indicators.zscore import robust_zscore_cross_session


VOLUME_RATIO_NAME = "VolumeRatio"
VOLUME_ROBUST_Z_NAME = "VolumeRobustZ"
ABSORPTION_RATIO_NAME = "AbsorptionRatio"


def volume_ratio(
    volume: pd.Series,
    *,
    window: int,
) -> pd.Series:
    _validate_positive_window(window)
    rolling_mean = volume.rolling(window=window, min_periods=window).mean()
    result = volume / rolling_mean.mask(rolling_mean == 0.0)
    result.name = VOLUME_RATIO_NAME
    return result


def volume_robust_zscore(
    volume: pd.Series,
    *,
    window: int,
) -> pd.Series:
    # Cross-session - no session reset.
    result = robust_zscore_cross_session(volume, window=window)
    result.name = VOLUME_ROBUST_Z_NAME
    return result


def absorption_ratio(
    delta: pd.Series,
    price_change: pd.Series,
) -> pd.Series:
    # Time-bar approximation. Bar-level delta cannot reveal intrabar
    # absorption. Context-only.
    result = delta.abs() / price_change.abs().mask(price_change == 0.0)
    result.name = ABSORPTION_RATIO_NAME
    return result


def _validate_positive_window(window: int) -> None:
    if window <= 0:
        raise ValueError(f"window must be positive, got: {window}")
