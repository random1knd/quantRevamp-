import pandas as pd
import pytest

from shared.validation.block_permutation import (
    WIRING_STATUS,
    whole_session_outcome_block_permutation_report,
)
from shared.validation.multiple_testing import full_search_permutation_report


def basic_spec() -> dict:
    return {
        "columns": [{"name": "A", "directions": ["<="]}],
        "quantiles": [50],
        "realized_r_column": "RealizedR",
        "min_kept_count": 1,
        "winsorize_fraction": 0.05,
    }


def test_whole_session_outcome_block_permutation_is_deterministic_under_seed():
    frame = pd.DataFrame(
        {
            "SessionDate_ET": ["s1", "s1", "s2", "s2", "s3", "s3"],
            "A": [0.0, 0.0, 1.0, 1.0, 2.0, 2.0],
            "RealizedR": [2.0, 1.0, -1.0, -2.0, 0.5, 0.25],
        }
    )

    first = whole_session_outcome_block_permutation_report(
        frame,
        basic_spec(),
        session_column="SessionDate_ET",
        n_iter=6,
        random_seed=7,
    )
    second = whole_session_outcome_block_permutation_report(
        frame,
        basic_spec(),
        session_column="SessionDate_ET",
        n_iter=6,
        random_seed=7,
    )

    assert first["permutation_null"] == second["permutation_null"]
    assert first["adjusted_p_value"] == second["adjusted_p_value"]


def test_whole_session_outcome_block_permutation_rejects_bad_arguments():
    frame = pd.DataFrame(
        {
            "SessionDate_ET": ["s1", "s1"],
            "A": [0.0, 1.0],
            "RealizedR": [1.0, -1.0],
        }
    )

    with pytest.raises(ValueError, match="n_iter must be positive"):
        whole_session_outcome_block_permutation_report(
            frame,
            basic_spec(),
            session_column="SessionDate_ET",
            n_iter=0,
            random_seed=0,
        )

    with pytest.raises(ValueError, match="missing session column"):
        whole_session_outcome_block_permutation_report(
            frame,
            basic_spec(),
            session_column="MissingSession",
            n_iter=1,
            random_seed=0,
        )

    with pytest.raises(ValueError, match="at least one row"):
        whole_session_outcome_block_permutation_report(
            frame.iloc[:0],
            basic_spec(),
            session_column="SessionDate_ET",
            n_iter=1,
            random_seed=0,
        )

    with pytest.raises(ValueError, match="interleaved session"):
        whole_session_outcome_block_permutation_report(
            pd.DataFrame(
                {
                    "SessionDate_ET": ["s1", "s2", "s1"],
                    "A": [0.0, 1.0, 0.0],
                    "RealizedR": [1.0, -1.0, 1.0],
                }
            ),
            basic_spec(),
            session_column="SessionDate_ET",
            n_iter=1,
            random_seed=0,
        )

    with pytest.raises(ValueError, match="session column values must not be null"):
        whole_session_outcome_block_permutation_report(
            pd.DataFrame(
                {
                    "SessionDate_ET": ["s1", None],
                    "A": [0.0, 1.0],
                    "RealizedR": [1.0, -1.0],
                }
            ),
            basic_spec(),
            session_column="SessionDate_ET",
            n_iter=1,
            random_seed=0,
        )

    with pytest.raises(ValueError, match="realized R must be finite"):
        whole_session_outcome_block_permutation_report(
            pd.DataFrame(
                {
                    "SessionDate_ET": ["s1", "s1"],
                    "A": [0.0, 1.0],
                    "RealizedR": [1.0, float("inf")],
                }
            ),
            basic_spec(),
            session_column="SessionDate_ET",
            n_iter=1,
            random_seed=0,
        )


def test_whole_session_outcome_block_permutation_reports_low_session_count():
    single_session = _session_count_frame(1)
    low_session_count = _session_count_frame(9)
    normal_session_count = _session_count_frame(10)

    single_report = whole_session_outcome_block_permutation_report(
        single_session,
        basic_spec(),
        session_column="SessionDate_ET",
        n_iter=1,
        random_seed=0,
    )
    low_report = whole_session_outcome_block_permutation_report(
        low_session_count,
        basic_spec(),
        session_column="SessionDate_ET",
        n_iter=1,
        random_seed=0,
    )
    normal_report = whole_session_outcome_block_permutation_report(
        normal_session_count,
        basic_spec(),
        session_column="SessionDate_ET",
        n_iter=1,
        random_seed=0,
    )

    assert single_report["session_count_floor_enforced"] is False
    assert (
        single_report["session_count_warning"]
        == "single_session_block_permutation_degenerate"
    )
    assert low_report["session_count_warning"] == "low_session_count_null_is_coarse"
    assert normal_report["session_count_warning"] is None


def test_whole_session_outcome_block_permutation_returns_no_candidate_without_null():
    frame = pd.DataFrame(
        {
            "SessionDate_ET": ["s1", "s1", "s2"],
            "A": [1.0, 2.0, 3.0],
            "RealizedR": [-1.0, -0.5, -0.25],
        }
    )
    spec = {
        **basic_spec(),
        "quantiles": [100],
    }

    report = whole_session_outcome_block_permutation_report(
        frame,
        spec,
        session_column="SessionDate_ET",
        n_iter=3,
        random_seed=0,
    )

    assert report["candidate_status"] == "no_candidate"
    assert report["observed_selected_rule"] is None
    assert report["permutation_null"] == []
    assert report["null_distribution_summary"] is None
    assert report["adjusted_p_value"] is None


def test_whole_session_outcome_block_permutation_inflates_clustered_null():
    frame = _clustered_edge_frame()
    spec = basic_spec()
    block = whole_session_outcome_block_permutation_report(
        frame,
        spec,
        session_column="SessionDate_ET",
        n_iter=2000,
        random_seed=3,
    )
    iid = full_search_permutation_report(
        frame,
        spec,
        n_iter=2000,
        random_seed=3,
    )

    assert block["observed_selected_mean_realized_r"] == pytest.approx(
        iid["observed_selected_mean_realized_r"]
    )
    assert block["adjusted_p_value"] > iid["adjusted_p_value"]
    assert block["null_distribution_summary"]["p95"] > 0.0


def test_whole_session_outcome_block_permutation_records_seam_crossing():
    frame = pd.DataFrame(
        {
            "SessionDate_ET": ["s1", "s2", "s2", "s3", "s3", "s3"],
            "A": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
            "RealizedR": [1.0, 1.0, 1.0, -1.0, -1.0, -1.0],
        }
    )

    report = whole_session_outcome_block_permutation_report(
        frame,
        basic_spec(),
        session_column="SessionDate_ET",
        n_iter=20,
        random_seed=0,
    )

    assert report["block_length_summary"]["unique_lengths"] == [1, 2, 3]
    assert report["seam_crossing_flag"] is True
    assert report["seam_crossing_count"] > 0


def test_whole_session_outcome_block_permutation_marks_report_as_not_wired():
    report = whole_session_outcome_block_permutation_report(
        _clustered_edge_frame(),
        basic_spec(),
        session_column="SessionDate_ET",
        n_iter=1,
        random_seed=0,
    )

    assert report["method"] == "whole_session_outcome_block_permutation"
    assert report["unequal_length_policy"] == "permute_blocks_then_concatenate"
    assert report["statistic"] == "max_eligible_mean_realized_r"
    assert report["wiring_status"] == WIRING_STATUS


def _clustered_edge_frame():
    sessions = []
    feature = []
    realized_r = []
    for session_index in range(10):
        positive_session = session_index < 5
        for _ in range(10):
            sessions.append(f"s{session_index}")
            feature.append(0.0 if positive_session else 1.0)
            realized_r.append(1.0 if positive_session else -1.0)
    return pd.DataFrame(
        {
            "SessionDate_ET": sessions,
            "A": feature,
            "RealizedR": realized_r,
        }
    )


def _session_count_frame(session_count: int):
    sessions = [f"s{index}" for index in range(session_count)]
    return pd.DataFrame(
        {
            "SessionDate_ET": sessions,
            "A": [0.0 for _ in sessions],
            "RealizedR": [1.0 for _ in sessions],
        }
    )
