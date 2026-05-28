from datetime import date

import pandas as pd
import pytest

from shared.validation.market_permutation import (
    FIXED_SKELETON_COLUMNS,
    MARKET_VALUE_COLUMNS,
    market_permutation_report,
    permute_market_bars,
)


def test_permute_market_bars_keeps_market_tuples_inside_each_session():
    bars = _bars()

    permuted = permute_market_bars(
        bars,
        random_seed=7,
        expected_bar_interval_minutes=5,
    )

    skeleton_columns = [
        column for column in FIXED_SKELETON_COLUMNS if column in bars.columns
    ]
    pd.testing.assert_frame_equal(
        permuted[skeleton_columns],
        bars[skeleton_columns],
    )
    for session in bars["SessionDate_ET"].drop_duplicates():
        assert _market_tuples(permuted, session) == _market_tuples(bars, session)

    assert (
        (permuted["High"] >= permuted["Open"])
        & (permuted["High"] >= permuted["Close"])
        & (permuted["Low"] <= permuted["Open"])
        & (permuted["Low"] <= permuted["Close"])
    ).all()
    assert permuted["BarGapMinutesFromPrevious"].isna().sum() == 2
    assert permuted["BarGapFromPrevious"].sum() == 0


def test_permute_market_bars_is_deterministic_under_fixed_seed():
    bars = _bars()

    first = permute_market_bars(
        bars,
        random_seed=12,
        expected_bar_interval_minutes=5,
    )
    second = permute_market_bars(
        bars,
        random_seed=12,
        expected_bar_interval_minutes=5,
    )

    pd.testing.assert_frame_equal(first, second)


def test_market_permutation_report_uses_plus_one_smoothed_positive_tail():
    report = market_permutation_report(
        0.50,
        [
            {"iteration": 1, "random_seed": 20, "mean_realized_r": 0.60},
            {"iteration": 2, "random_seed": 21, "mean_realized_r": 0.40},
            {"iteration": 3, "random_seed": 22, "mean_realized_r": 0.70},
        ],
        n_iter=3,
        random_seed=20,
    )

    assert report["report_type"] == "market_data_permutation_report"
    assert report["coverage_only"] is True
    assert report["selection_policy"] == "no_permutation_path_selection_allowed"
    assert report["permuted_ge_observed_count"] == 2
    assert report["one_sided_positive_p_value"] == pytest.approx(0.75)
    assert report["permuted_mean_realized_r_summary"]["mean"] == pytest.approx(
        (0.60 + 0.40 + 0.70) / 3
    )


def test_market_permutation_report_requires_full_iteration_set():
    with pytest.raises(ValueError, match="length must equal n_iter"):
        market_permutation_report(
            0.0,
            [{"iteration": 1, "mean_realized_r": 0.1}],
            n_iter=2,
            random_seed=0,
        )


def _market_tuples(frame: pd.DataFrame, session: date) -> list[tuple]:
    values = frame.loc[
        frame["SessionDate_ET"] == session,
        list(MARKET_VALUE_COLUMNS),
    ]
    return sorted(tuple(row) for row in values.to_numpy().tolist())


def _bars() -> pd.DataFrame:
    rows = []
    for session_index, session in enumerate((date(2026, 1, 2), date(2026, 1, 3))):
        start = pd.Timestamp(f"{session.isoformat()} 09:30", tz="America/New_York")
        for bar_index in range(4):
            base = 100.0 + session_index * 100.0 + bar_index * 2.0
            timestamp_et = start + pd.Timedelta(minutes=bar_index * 5)
            rows.append(
                {
                    "DateTime_UTC": timestamp_et.tz_convert("UTC"),
                    "DateTime_ET": timestamp_et,
                    "SessionDate_ET": session,
                    "SessionMinute_ET": bar_index * 5,
                    "Contract": f"NQ{session_index}",
                    "IsFirstSessionAfterContractChange": session_index == 1,
                    "Open": base,
                    "High": base + 1.0,
                    "Low": base - 1.0,
                    "Close": base + 0.25,
                    "Volume": 1000 + session_index * 100 + bar_index,
                    "BidVolume": 400 + session_index * 100 + bar_index,
                    "AskVolume": 600 + session_index * 100 + bar_index,
                    "BarGapMinutesFromPrevious": 999.0,
                    "BarGapFromPrevious": True,
                }
            )
    return pd.DataFrame(rows)
