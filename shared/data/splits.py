from __future__ import annotations

from datetime import date
from typing import TypedDict

import pandas as pd


class ChronologicalSessionSplits(TypedDict):
    discovery_end: date
    validation_end: date
    test_end: date
    discovery_session_count: int
    validation_session_count: int
    test_session_count: int


def chronological_session_splits(
    prepared_bars: pd.DataFrame,
) -> ChronologicalSessionSplits:
    """Return 30/50/20 whole-session split boundaries.

    Precondition: rows are already in chronological order by session
    appearance, as produced by `prepare_bars`. Every unique `SessionDate_ET`
    counts as one session, including sessions that a later RTH-only consumer
    might filter down to zero tradeable rows.
    """

    if "SessionDate_ET" not in prepared_bars.columns:
        raise ValueError("missing required column: SessionDate_ET")

    sessions = list(prepared_bars["SessionDate_ET"].drop_duplicates())
    total = len(sessions)
    if total < 3:
        raise ValueError("at least 3 sessions are required for 30/50/20 splits")

    discovery_count = max(1, int(total * 0.30))
    validation_count = max(1, int(total * 0.80) - discovery_count)
    test_count = total - discovery_count - validation_count
    if test_count < 1:
        raise ValueError("at least 1 test session is required for 30/50/20 splits")

    discovery_end_index = discovery_count - 1
    validation_end_index = discovery_count + validation_count - 1

    return {
        "discovery_end": sessions[discovery_end_index],
        "validation_end": sessions[validation_end_index],
        "test_end": sessions[-1],
        "discovery_session_count": discovery_count,
        "validation_session_count": validation_count,
        "test_session_count": test_count,
    }
