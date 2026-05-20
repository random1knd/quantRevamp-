from __future__ import annotations

import pandas as pd


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
