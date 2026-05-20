from __future__ import annotations

import pandas as pd


ZSCORE_NAME = "ZScore"
PERCENTILE_NAME = "RollingPercentile"


def gap_free_rolling_window(
    bar_gap: pd.Series,
    *,
    session: pd.Series,
    window: int,
) -> pd.Series:
    gap_flags = bar_gap.fillna(False).astype(bool).astype(int)
    gap_in_window = gap_flags.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=1).max()
    )
    return ~gap_in_window.astype(bool)


def rolling_zscore(
    series: pd.Series,
    *,
    session: pd.Series,
    window: int,
) -> pd.Series:
    _validate_positive_window(window)
    rolling_mean = series.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).mean()
    )
    rolling_std = series.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).std()
    )
    result = (series - rolling_mean) / rolling_std.mask(rolling_std == 0.0)
    result.name = ZSCORE_NAME
    return result


def rolling_zscore_cross_session(
    series: pd.Series,
    *,
    window: int,
) -> pd.Series:
    _validate_positive_window(window)
    rolling_mean = series.rolling(window=window, min_periods=window).mean()
    rolling_std = series.rolling(window=window, min_periods=window).std()
    result = (series - rolling_mean) / rolling_std.mask(rolling_std == 0.0)
    result.name = ZSCORE_NAME
    return result


def ewma_zscore(
    series: pd.Series,
    *,
    span: int,
) -> pd.Series:
    if span <= 0:
        raise ValueError(f"span must be positive, got: {span}")

    # EWMA state intentionally does not reset at session boundaries.
    ewm = series.ewm(span=span)
    ewm_mean = ewm.mean()
    ewm_std = ewm.std()
    result = (series - ewm_mean) / ewm_std.mask(ewm_std == 0.0)
    result.name = ZSCORE_NAME
    return result


def robust_zscore(
    series: pd.Series,
    *,
    session: pd.Series,
    window: int,
) -> pd.Series:
    _validate_positive_window(window)
    rolling_median = series.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).median()
    )
    rolling_mad = series.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).apply(
            _median_absolute_deviation,
            raw=True,
        )
    )
    denominator = (1.4826 * rolling_mad).mask(rolling_mad == 0.0)
    result = (series - rolling_median) / denominator
    result.name = ZSCORE_NAME
    return result


def rolling_percentile(
    series: pd.Series,
    *,
    window: int,
) -> pd.Series:
    _validate_positive_window(window)
    result = series.rolling(window=window + 1, min_periods=window + 1).apply(
        lambda values: (values[:-1] < values[-1]).mean(),
        raw=True,
    )
    result.name = PERCENTILE_NAME
    return result


def _median_absolute_deviation(values) -> float:
    median = pd.Series(values).median()
    return (pd.Series(values) - median).abs().median()


def _validate_positive_window(window: int) -> None:
    if window <= 0:
        raise ValueError(f"window must be positive, got: {window}")
