import time

import numpy as np
import pandas as pd

from shared.indicators.regime import (
    rolling_adf_pvalue,
    rolling_autocorr,
    rolling_variance_ratio,
)


def test_rolling_autocorr_returns_positive_lag_one_autocorr():
    series = pd.Series([0.9**index for index in range(10)])

    result = rolling_autocorr(series, window=5, lag=1)

    assert result.name == "AutoCorr"
    assert result.iloc[-1] > 0.0


def test_rolling_autocorr_returns_negative_lag_one_autocorr():
    series = pd.Series([1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0])

    result = rolling_autocorr(series, window=5, lag=1)

    assert result.iloc[-1] < 0.0


def test_rolling_autocorr_returns_nan_before_window():
    series = pd.Series([0.9**index for index in range(10)])

    result = rolling_autocorr(series, window=5, lag=1)

    assert result.iloc[:5].isna().all()


def test_rolling_variance_ratio_returns_positive_for_trending_series():
    series = pd.Series([1.0, 2.0, 4.0, 7.0, 11.0, 16.0, 22.0, 29.0, 37.0, 46.0])

    result = rolling_variance_ratio(series, window=6, q=2)

    assert result.name == "VarianceRatio"
    assert not pd.isna(result.iloc[-1])
    assert result.iloc[-1] > 0.0


def test_rolling_variance_ratio_returns_below_one_for_mean_reverting_series():
    series = pd.Series([0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0])

    result = rolling_variance_ratio(series, window=8, q=2)

    assert result.iloc[-1] < 1.0


def test_rolling_variance_ratio_returns_nan_before_window():
    series = pd.Series([1.0, 2.0, 4.0, 7.0, 11.0, 16.0, 22.0])

    result = rolling_variance_ratio(series, window=6, q=2)

    assert pd.isna(result.iloc[0])


def test_rolling_variance_ratio_returns_nan_when_one_bar_variance_is_zero():
    series = pd.Series([5.0, 5.0, 5.0, 5.0, 5.0, 5.0])

    result = rolling_variance_ratio(series, window=3, q=2)

    assert result.isna().all()


def test_rolling_adf_pvalue_returns_low_value_for_stationary_series():
    series = pd.Series([1.0, -1.0] * 25)

    result = rolling_adf_pvalue(series, window=40)

    assert result.name == "ADF_PValue"
    assert result.iloc[-1] < 0.10


def test_rolling_adf_pvalue_returns_high_value_for_random_walk():
    random_walk = _deterministic_random_walk(length=50)

    result = rolling_adf_pvalue(random_walk, window=40)

    assert result.iloc[-1] > 0.50


def test_rolling_adf_pvalue_returns_nan_before_window():
    series = pd.Series([1.0, -1.0] * 25)

    result = rolling_adf_pvalue(series, window=40)

    assert pd.isna(result.iloc[0])


def test_rolling_adf_pvalue_timing_is_visible():
    series = _deterministic_random_walk(length=500)

    start = time.perf_counter()
    rolling_adf_pvalue(series, window=60)
    elapsed = time.perf_counter() - start

    print(f"ADF timing elapsed: {elapsed:.6f} seconds")
    assert elapsed < 120.0


def test_rolling_autocorr_is_causal_when_future_value_changes():
    series = pd.Series([0.9**index for index in range(10)])
    mutated = series.copy()
    mutated.iloc[9] = 10_000.0

    original = rolling_autocorr(series, window=5, lag=1)
    changed = rolling_autocorr(mutated, window=5, lag=1)

    assert original.iloc[8] == changed.iloc[8]


def test_rolling_variance_ratio_is_causal_when_future_value_changes():
    series = pd.Series([1.0, 2.0, 4.0, 7.0, 11.0, 16.0, 22.0, 29.0, 37.0, 46.0])
    mutated = series.copy()
    mutated.iloc[9] = 10_000.0

    original = rolling_variance_ratio(series, window=6, q=2)
    changed = rolling_variance_ratio(mutated, window=6, q=2)

    assert original.iloc[8] == changed.iloc[8]


def _deterministic_random_walk(*, length: int) -> pd.Series:
    rng = np.random.default_rng(0)
    return pd.Series(rng.normal(size=length).cumsum())
