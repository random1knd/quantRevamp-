from __future__ import annotations

import pandas as pd

from strategies.vwap_zscore_fade.parent import params


REQUIRED_COLUMNS = (
    "SessionDate_ET",
    "SessionMinute_ET",
    "BarGapFromPrevious",
    "Volume",
    "BidVolume",
    "AskVolume",
)

RESEARCH_INDICATOR_COLUMNS = (
    "EntryVolumeZ",
    "EntryDelta",
    "EntryDeltaPct",
)


def add_research_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    """Add post-trade research context fields for later slicing."""

    _validate_required_columns(bars)

    result = bars.copy()
    for column in RESEARCH_INDICATOR_COLUMNS:
        result[column] = pd.Series(index=result.index, dtype="float64")

    rth_mask = _rth_rows(result)
    if not rth_mask.any():
        return result

    rth = result.loc[rth_mask].copy()
    rth["EntryVolumeZ"] = _session_standard_zscore(
        rth["Volume"],
        session=rth["SessionDate_ET"],
        bar_gap=rth["BarGapFromPrevious"],
        window=params.VOLUME_Z_WINDOW,
    )
    rth["EntryDelta"] = rth["AskVolume"] - rth["BidVolume"]
    rth["EntryDeltaPct"] = rth["EntryDelta"] / rth["Volume"].mask(
        rth["Volume"] == 0.0
    )

    result.loc[rth.index, RESEARCH_INDICATOR_COLUMNS] = rth.loc[
        :, RESEARCH_INDICATOR_COLUMNS
    ]
    return result


def _validate_required_columns(bars: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in bars.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")


def _rth_rows(bars: pd.DataFrame) -> pd.Series:
    return bars["SessionMinute_ET"].between(
        params.RTH_START_SESSION_MINUTE,
        params.LAST_RTH_BAR_OPEN_SESSION_MINUTE,
    )


def _session_standard_zscore(
    values: pd.Series,
    *,
    session: pd.Series,
    bar_gap: pd.Series,
    window: int,
) -> pd.Series:
    rolling_mean = values.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).mean()
    )
    rolling_std = values.groupby(session, sort=False).transform(
        lambda group: group.rolling(window=window, min_periods=window).std()
    )
    zscore = (values - rolling_mean) / rolling_std.mask(rolling_std == 0.0)
    return zscore.mask(
        ~_gap_free_rolling_window(
            bar_gap,
            session=session,
            window=window,
        )
    )


def _gap_free_rolling_window(
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
