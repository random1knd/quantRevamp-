from __future__ import annotations

import pandas as pd


PLUS_DI_NAME = "PlusDI"
MINUS_DI_NAME = "MinusDI"
ADX_NAME = "ADX"
MA_SLOPE_NAME = "MA_Slope"
EFFICIENCY_RATIO_NAME = "EfficiencyRatio"
MOMENTUM_NAME = "Momentum"


def adx(
    bars: pd.DataFrame,
    *,
    window: int,
) -> pd.DataFrame:
    _validate_positive_window(window, name="window")
    _validate_columns(bars, columns=("High", "Low", "Close"))

    if bars.empty:
        return pd.DataFrame(
            index=bars.index,
            columns=[PLUS_DI_NAME, MINUS_DI_NAME, ADX_NAME],
            dtype="float64",
        )

    high = bars["High"]
    low = bars["Low"]
    close = bars["Close"]

    # ADX is a multi-session trend indicator and intentionally does not reset
    # at session boundaries.
    up_move = high.diff().fillna(0.0)
    down_move = (low.shift(1) - low).fillna(0.0)
    plus_dm = up_move.where((up_move > 0.0) & (up_move > down_move), 0.0)
    minus_dm = down_move.where((down_move > 0.0) & (down_move >= up_move), 0.0)

    prev_close = close.shift(1)
    ranges = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    true_range = ranges.max(axis=1)
    true_range.iloc[0] = None

    smoothed_plus_dm = _wilder_smooth(plus_dm, window=window)
    smoothed_minus_dm = _wilder_smooth(minus_dm, window=window)
    # Raw TR starts with no prior close; skip only that seed NaN so DI aligns
    # with the specified first Wilder seed position.
    smoothed_tr = _wilder_smooth(true_range, window=window, skip_seed_na=True)

    plus_di = 100.0 * smoothed_plus_dm / smoothed_tr.mask(smoothed_tr == 0.0)
    minus_di = 100.0 * smoothed_minus_dm / smoothed_tr.mask(smoothed_tr == 0.0)

    directional_sum = plus_di + minus_di
    dx = 100.0 * (plus_di - minus_di).abs() / directional_sum.mask(
        directional_sum == 0.0
    )
    # ADX has a second Wilder warmup after DI/DX, so early NaNs are expected.
    adx_value = _wilder_smooth(dx, window=window)

    return pd.DataFrame(
        {
            PLUS_DI_NAME: plus_di,
            MINUS_DI_NAME: minus_di,
            ADX_NAME: adx_value,
        },
        index=bars.index,
    )


def ma_slope(
    series: pd.Series,
    *,
    window: int,
) -> pd.Series:
    _validate_positive_window(window, name="window")
    result = (series - series.shift(window)) / window
    result.name = MA_SLOPE_NAME
    return result


def efficiency_ratio(
    series: pd.Series,
    *,
    window: int,
) -> pd.Series:
    _validate_positive_window(window, name="window")
    abs_moves = series.diff().abs()
    path_length = abs_moves.rolling(window=window, min_periods=window).sum()
    net_move = series.diff(window).abs()
    result = net_move / path_length.mask(path_length == 0.0)
    result.name = EFFICIENCY_RATIO_NAME
    return result


def momentum(
    series: pd.Series,
    *,
    lookback: int,
) -> pd.Series:
    _validate_positive_window(lookback, name="lookback")
    denominator = series.shift(lookback)
    result = (series - denominator) / denominator.mask(denominator == 0.0)
    result.name = MOMENTUM_NAME
    return result


def _wilder_smooth(
    values: pd.Series,
    *,
    window: int,
    skip_seed_na: bool = False,
) -> pd.Series:
    result = pd.Series(index=values.index, dtype="float64")
    if len(values) < window:
        return result

    seed_values = values.iloc[:window]
    if skip_seed_na:
        initial_seed = (
            seed_values.iloc[1:] if pd.isna(seed_values.iloc[0]) else seed_values
        )
        if not initial_seed.isna().any():
            result.iloc[window - 1] = initial_seed.mean()
    elif not seed_values.isna().any():
        result.iloc[window - 1] = seed_values.mean()

    for position in range(window, len(values)):
        value = values.iloc[position]
        previous = result.iloc[position - 1]
        if pd.isna(value):
            continue

        if pd.isna(previous):
            seed_values = values.iloc[position - window + 1 : position + 1]
            if not seed_values.isna().any():
                result.iloc[position] = seed_values.mean()
            continue

        result.iloc[position] = previous * (window - 1) / window + value / window

    return result


def _validate_columns(
    frame: pd.DataFrame,
    *,
    columns: tuple[str, ...],
) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")


def _validate_positive_window(value: int, *, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got: {value}")
