"""Engine-only dependence-aware search-significance permutation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from shared.validation.rule_search import build_threshold_rules, score_rules


METHOD = "whole_session_outcome_block_permutation"
SIDEDNESS = "one_sided_positive"
STATISTIC = "max_eligible_mean_realized_r"
UNEQUAL_LENGTH_POLICY = "permute_blocks_then_concatenate"
WIRING_STATUS = "engine_only_not_wired_to_slicer_or_promotion"
LOW_SESSION_COUNT_WARNING_THRESHOLD = 10


def whole_session_outcome_block_permutation_report(
    frame: pd.DataFrame,
    spec: Mapping[str, Any],
    *,
    session_column: str,
    n_iter: int,
    random_seed: int,
) -> dict[str, Any]:
    if n_iter <= 0:
        raise ValueError(f"n_iter must be positive, got: {n_iter}")
    if session_column not in frame.columns:
        raise ValueError(f"missing session column: {session_column}")

    realized_r_column = _required_string(spec, "realized_r_column")
    if realized_r_column not in frame.columns:
        raise ValueError(f"missing realized-R column: {realized_r_column}")
    _reject_non_finite_realized_r(frame[realized_r_column])

    blocks = _contiguous_session_blocks(
        frame,
        session_column=session_column,
        realized_r_column=realized_r_column,
    )
    rules = build_threshold_rules(frame, spec)
    observed_rules = score_rules(frame, rules, spec)
    selected_rule = _selected_rule(observed_rules)
    base_report = _base_report(
        n_iter=n_iter,
        random_seed=random_seed,
        session_column=session_column,
        blocks=blocks,
    )

    if selected_rule is None:
        return {
            **base_report,
            "candidate_status": "no_candidate",
            "observed_selected_rule": None,
            "observed_selected_mean_realized_r": None,
            "permutation_null": [],
            "null_distribution_summary": None,
            "extreme_null_count": None,
            "adjusted_p_value": None,
        }

    observed_score = selected_rule["mean_realized_r"]
    permutation_null = _permutation_null(
        frame,
        rules=rules,
        spec=spec,
        realized_r_column=realized_r_column,
        blocks=blocks,
        n_iter=n_iter,
        random_seed=random_seed,
    )
    null_scores = [
        item[STATISTIC]
        for item in permutation_null
        if item[STATISTIC] is not None
    ]
    extreme_null_count = sum(
        1 for score in null_scores if score >= observed_score
    )
    adjusted_p_value = (1 + extreme_null_count) / (1 + n_iter)

    return {
        **base_report,
        "candidate_status": "candidate_selected",
        "observed_selected_rule": selected_rule,
        "observed_selected_mean_realized_r": observed_score,
        "permutation_null": permutation_null,
        "null_distribution_summary": _null_distribution_summary(null_scores),
        "extreme_null_count": extreme_null_count,
        "adjusted_p_value": adjusted_p_value,
        "seam_crossing_count": sum(
            item["seam_crossing_count"] for item in permutation_null
        ),
        "seam_crossing_flag": any(
            item["seam_crossing_flag"] for item in permutation_null
        ),
    }


def _base_report(
    *,
    n_iter: int,
    random_seed: int,
    session_column: str,
    blocks: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "method": METHOD,
        "unequal_length_policy": UNEQUAL_LENGTH_POLICY,
        "statistic": STATISTIC,
        "sidedness": SIDEDNESS,
        "n_iter": n_iter,
        "random_seed": random_seed,
        "session_column": session_column,
        "session_count": len(blocks),
        "block_length_summary": _block_length_summary(blocks),
        "session_count_floor_enforced": False,
        "session_count_warning": _session_count_warning(len(blocks)),
        "wiring_status": WIRING_STATUS,
        "seam_crossing_count": 0,
        "seam_crossing_flag": False,
    }


def _permutation_null(
    frame: pd.DataFrame,
    *,
    rules: list[dict[str, Any]],
    spec: Mapping[str, Any],
    realized_r_column: str,
    blocks: Sequence[dict[str, Any]],
    n_iter: int,
    random_seed: int,
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(random_seed)
    feature_boundaries = _boundaries([block["length"] for block in blocks])
    null: list[dict[str, Any]] = []

    for iteration in range(n_iter):
        block_order = [int(index) for index in rng.permutation(len(blocks))]
        permuted_values = np.concatenate(
            [blocks[index]["values"] for index in block_order]
        )
        outcome_boundaries = _boundaries(
            [blocks[index]["length"] for index in block_order]
        )
        seam_crossing_count = len(outcome_boundaries - feature_boundaries)

        permuted = frame.copy()
        permuted[realized_r_column] = permuted_values
        scored_rules = score_rules(permuted, rules, spec)
        max_rule = _max_eligible_rule(scored_rules)
        null.append(
            {
                "iteration": iteration,
                "block_order": block_order,
                STATISTIC: None if max_rule is None else max_rule["mean_realized_r"],
                "max_rule_id": None if max_rule is None else max_rule["rule_id"],
                "seam_crossing_count": seam_crossing_count,
                "seam_crossing_flag": seam_crossing_count > 0,
            }
        )

    return null


def _contiguous_session_blocks(
    frame: pd.DataFrame,
    *,
    session_column: str,
    realized_r_column: str,
) -> list[dict[str, Any]]:
    if frame.empty:
        raise ValueError("session blocks must contain at least one row")

    session_values = frame[session_column].to_list()
    realized_values = pd.to_numeric(frame[realized_r_column], errors="raise").to_numpy(
        dtype=float,
        copy=True,
    )
    blocks: list[dict[str, Any]] = []
    closed_sessions: list[Any] = []
    start = 0
    current_session = session_values[0]
    if pd.isna(current_session):
        raise ValueError("session column values must not be null")

    for pos, session in enumerate(session_values[1:], start=1):
        if pd.isna(session):
            raise ValueError("session column values must not be null")
        if session == current_session:
            continue
        closed_sessions.append(current_session)
        if session in closed_sessions:
            raise ValueError(
                "session rows must be contiguous; found interleaved session"
            )
        blocks.append(
            _block(
                session=current_session,
                start=start,
                end=pos,
                values=realized_values[start:pos],
            )
        )
        start = pos
        current_session = session

    blocks.append(
        _block(
            session=current_session,
            start=start,
            end=len(session_values),
            values=realized_values[start:],
        )
    )
    if not blocks:
        raise ValueError("session blocks must contain at least one row")
    return blocks


def _block(
    *,
    session: Any,
    start: int,
    end: int,
    values: np.ndarray,
) -> dict[str, Any]:
    if end <= start or values.size == 0:
        raise ValueError("session blocks must not be empty")
    return {
        "session": session,
        "start": start,
        "end": end,
        "length": int(values.size),
        "values": values,
    }


def _reject_non_finite_realized_r(values: pd.Series) -> None:
    realized_r = pd.to_numeric(values, errors="raise").to_numpy(dtype=float)
    if not np.isfinite(realized_r).all():
        raise ValueError("realized R must be finite")


def _selected_rule(scored_rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    best = _max_eligible_rule(scored_rules)
    if best is None or best["mean_realized_r"] <= 0.0:
        return None
    return best


def _max_eligible_rule(scored_rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [
        rule
        for rule in scored_rules
        if rule["eligible"] and rule["mean_realized_r"] is not None
    ]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda rule: (-rule["mean_realized_r"], rule["rule_index"]),
    )[0]


def _block_length_summary(blocks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    lengths = np.array([int(block["length"]) for block in blocks], dtype=float)
    return {
        "min": int(lengths.min()),
        "max": int(lengths.max()),
        "mean": float(lengths.mean()),
        "median": float(np.median(lengths)),
        "unique_lengths": sorted({int(length) for length in lengths}),
    }


def _null_distribution_summary(null_scores: Sequence[float]) -> dict[str, float]:
    values = np.array(null_scores, dtype=float)
    percentiles = np.percentile(values, [5, 50, 95])
    return {
        "mean": float(values.mean()),
        "median": float(percentiles[1]),
        "p05": float(percentiles[0]),
        "p95": float(percentiles[2]),
        "min": float(values.min()),
        "max": float(values.max()),
    }


def _session_count_warning(session_count: int) -> str | None:
    if session_count == 1:
        return "single_session_block_permutation_degenerate"
    if session_count < LOW_SESSION_COUNT_WARNING_THRESHOLD:
        return "low_session_count_null_is_coarse"
    return None


def _boundaries(lengths: Sequence[int]) -> set[int]:
    total = 0
    boundaries = set()
    for length in lengths[:-1]:
        total += int(length)
        boundaries.add(total)
    return boundaries


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value
