from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd


REPORT_TYPE = "market_data_permutation_report"
METHOD = "within_session_single_bar_market_tuple_permutation"
STATISTIC = "mean_realized_r_completed_non_gap"
SIDEDNESS = "one_sided_positive"
MARKET_VALUE_COLUMNS = (
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "BidVolume",
    "AskVolume",
)
FIXED_SKELETON_COLUMNS = (
    "DateTime_UTC",
    "DateTime_ET",
    "SessionDate_ET",
    "SessionMinute_ET",
    "Contract",
    "IsFirstSessionAfterContractChange",
)
MARKET_PERMUTATION_CSV_FIELDS = [
    "iteration",
    "random_seed",
    "trade_count",
    "all_completed_trade_count",
    "completed_non_gap_trade_count",
    "incomplete_trade_count",
    "excluded_hold_crosses_gap_count",
    "mean_realized_r",
    "total_realized_r",
    "win_rate",
    "max_drawdown_r",
]


def permute_market_bars(
    bars: pd.DataFrame,
    *,
    random_seed: int,
    expected_bar_interval_minutes: int,
    market_columns: Sequence[str] = MARKET_VALUE_COLUMNS,
    session_column: str = "SessionDate_ET",
    datetime_column: str = "DateTime_ET",
) -> pd.DataFrame:
    if expected_bar_interval_minutes <= 0:
        raise ValueError("expected_bar_interval_minutes must be positive")

    market_column_list = list(market_columns)
    _require_columns(
        bars,
        [session_column, datetime_column, *market_column_list],
    )
    if bars.empty:
        raise ValueError("bars must not be empty")

    _validate_market_tuples(bars, market_columns=market_column_list)
    rng = _rng(random_seed)
    result = bars.copy()
    market_values = result.loc[:, market_column_list].to_numpy(copy=True)

    for positions in result.groupby(session_column, sort=False).indices.values():
        positions = pd.Index(positions).to_numpy()
        if len(positions) <= 1:
            continue
        order = rng.permutation(len(positions))
        market_values[positions, :] = market_values[positions[order], :]

    result.loc[:, market_column_list] = market_values
    _recompute_bar_gaps(
        result,
        session_column=session_column,
        datetime_column=datetime_column,
        expected_bar_interval_minutes=expected_bar_interval_minutes,
    )
    _validate_market_tuples(result, market_columns=market_column_list)
    return result


def market_permutation_report(
    observed_mean_realized_r: float,
    permutation_summaries: Sequence[Mapping[str, Any]],
    *,
    n_iter: int,
    random_seed: int,
) -> dict[str, Any]:
    if n_iter <= 0:
        raise ValueError("n_iter must be positive")
    if len(permutation_summaries) != n_iter:
        raise ValueError("permutation_summaries length must equal n_iter")

    observed = _finite_float(observed_mean_realized_r, "observed_mean_realized_r")
    rows = [
        _normalize_permutation_summary(summary, fallback_iteration=index + 1)
        for index, summary in enumerate(permutation_summaries)
    ]
    values = [row["mean_realized_r"] for row in rows]
    ge_observed_count = sum(1 for value in values if value >= observed)
    p_value = (1 + ge_observed_count) / (1 + n_iter)

    return {
        "report_type": REPORT_TYPE,
        "report_scope": "validation_child_market_data_permutation",
        "judgment_status": "report_only_no_pass_fail",
        "coverage_only": True,
        "edge_validation_status": "cannot_promote_edge",
        "selection_policy": "no_permutation_path_selection_allowed",
        "method": METHOD,
        "statistic": STATISTIC,
        "null_model": "within_session_iid_style_market_tuple_shuffle",
        "sidedness": SIDEDNESS,
        "p_value_formula": (
            "(1 + count(permuted_mean_R >= observed_mean_R)) / (1 + n_iter)"
        ),
        "n_iter": n_iter,
        "random_seed": int(random_seed),
        "observed_mean_realized_r": observed,
        "permuted_ge_observed_count": ge_observed_count,
        "one_sided_positive_p_value": p_value,
        "permuted_mean_realized_r_summary": _distribution_summary(values),
        "permutations": rows,
    }


def _recompute_bar_gaps(
    bars: pd.DataFrame,
    *,
    session_column: str,
    datetime_column: str,
    expected_bar_interval_minutes: int,
) -> None:
    datetimes = pd.to_datetime(bars[datetime_column], errors="raise")
    previous = datetimes.groupby(bars[session_column], sort=False).shift(1)
    gap_minutes = (datetimes - previous).dt.total_seconds() / 60.0
    bars["BarGapMinutesFromPrevious"] = gap_minutes
    bars["BarGapFromPrevious"] = gap_minutes.ne(
        float(expected_bar_interval_minutes)
    ) & gap_minutes.notna()


def _normalize_permutation_summary(
    summary: Mapping[str, Any],
    *,
    fallback_iteration: int,
) -> dict[str, Any]:
    row = dict(summary)
    row.setdefault("iteration", fallback_iteration)
    row["iteration"] = _required_int(row, "iteration")
    if "random_seed" in row and row["random_seed"] is not None:
        row["random_seed"] = _required_int(row, "random_seed")
    row["mean_realized_r"] = _required_float(row, "mean_realized_r")
    return row


def _distribution_summary(values: Sequence[float]) -> dict[str, float]:
    sorted_values = sorted(
        _finite_float(value, "permuted_mean_realized_r") for value in values
    )
    if not sorted_values:
        raise ValueError("values must not be empty")
    return {
        "min": sorted_values[0],
        "p05": _percentile(sorted_values, 0.05),
        "mean": sum(sorted_values) / len(sorted_values),
        "median": _percentile(sorted_values, 0.50),
        "p95": _percentile(sorted_values, 0.95),
        "max": sorted_values[-1],
    }


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = percentile * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _validate_market_tuples(
    bars: pd.DataFrame,
    *,
    market_columns: Sequence[str],
) -> None:
    _require_columns(bars, market_columns)
    high = bars["High"]
    low = bars["Low"]
    valid_ohlc = (
        high.ge(low)
        & high.ge(bars["Open"])
        & high.ge(bars["Close"])
        & low.le(bars["Open"])
        & low.le(bars["Close"])
    )
    if not valid_ohlc.fillna(False).all():
        raise ValueError("market tuples must have valid OHLC ordering")

    for column in ("Volume", "BidVolume", "AskVolume"):
        if column in market_columns and not bars[column].ge(0).fillna(False).all():
            raise ValueError(f"{column} must be non-negative")


def _require_columns(bars: pd.DataFrame, columns: Sequence[str]) -> None:
    missing = [column for column in columns if column not in bars.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")


def _rng(random_seed: int):
    seed = int(random_seed)
    if seed < 0:
        raise ValueError("random_seed must be non-negative")
    return np.random.default_rng(seed)


def _required_float(mapping: Mapping[str, Any], key: str) -> float:
    value = mapping.get(key)
    if value is None or value == "":
        raise ValueError(f"{key} must be numeric")
    return _finite_float(value, key)


def _required_int(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping.get(key)
    if value is None or value == "":
        raise ValueError(f"{key} must be an integer")
    return int(float(value))


def _finite_float(value: Any, label: str) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{label} must be finite")
    return converted
