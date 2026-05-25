from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


REPORT_TYPE = "walk_forward_report"
SPARSE_TRADE_FLOOR = 20
WALK_FORWARD_CSV_FIELDS = [
    "window_index",
    "window_count",
    "session_start",
    "session_end",
    "session_count",
    "bar_count",
    "trade_count",
    "all_completed_trade_count",
    "completed_non_gap_trade_count",
    "incomplete_trade_count",
    "excluded_hold_crosses_gap_count",
    "mean_realized_r",
    "total_realized_r",
    "win_rate",
    "max_drawdown_r",
    "window_status",
    "adx_decision_point_count",
    "adx_observed_decision_count",
    "adx_kept_count",
    "adx_rejected_count",
    "adx_missing_count",
    "adx_kept_fraction",
    "adx_missing_fraction",
]


def walk_forward_report(
    window_summaries: Sequence[Mapping[str, Any]],
    *,
    sparse_trade_floor: int = SPARSE_TRADE_FLOOR,
) -> dict[str, Any]:
    if sparse_trade_floor <= 0:
        raise ValueError("sparse_trade_floor must be positive")

    windows = [
        _with_window_status(_normalize_summary(summary), sparse_trade_floor)
        for summary in window_summaries
    ]
    if not windows:
        raise ValueError("window_summaries must not be empty")

    windows = sorted(windows, key=lambda row: row["window_index"])
    sparse_count = sum(1 for row in windows if row["window_status"] == "insufficient")
    sufficient = [row for row in windows if row["window_status"] == "sufficient"]
    overall_result = (
        "inconclusive"
        if sparse_count > len(windows) / 2
        else "reported_no_pass_fail"
    )

    return {
        "report_type": REPORT_TYPE,
        "report_scope": "validation_child_walk_forward",
        "judgment_status": "report_only_no_pass_fail",
        "coverage_only": True,
        "edge_validation_status": "cannot_promote_edge",
        "selection_policy": "no_window_or_threshold_selection_allowed",
        "sparse_trade_floor": sparse_trade_floor,
        "window_count": len(windows),
        "sufficient_window_count": len(sufficient),
        "sparse_window_count": sparse_count,
        "overall_result": overall_result,
        "window_mean_sign_counts": _mean_sign_counts(sufficient),
        "mean_realized_r_range": _mean_range(sufficient),
        "restrictiveness_drift": _restrictiveness_drift(windows),
        "windows": windows,
    }


def _with_window_status(
    row: dict[str, Any],
    sparse_trade_floor: int,
) -> dict[str, Any]:
    status = (
        "insufficient"
        if row["completed_non_gap_trade_count"] < sparse_trade_floor
        else "sufficient"
    )
    return {**row, "window_status": status}


def _normalize_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    kept = _required_int(summary, "adx_kept_count")
    rejected = _required_int(summary, "adx_rejected_count")
    missing = _required_int(summary, "adx_missing_count")
    observed = kept + rejected
    decision_point = observed + missing
    return {
        "window_index": _required_int(summary, "window_index"),
        "window_count": _required_int(summary, "window_count"),
        "session_start": _required_string(summary, "session_start"),
        "session_end": _required_string(summary, "session_end"),
        "session_count": _required_int(summary, "session_count"),
        "bar_count": _required_int(summary, "bar_count"),
        "trade_count": _required_int(summary, "trade_count"),
        "all_completed_trade_count": _required_int(
            summary,
            "all_completed_trade_count",
        ),
        "completed_non_gap_trade_count": _required_int(
            summary,
            "completed_non_gap_trade_count",
        ),
        "incomplete_trade_count": _required_int(summary, "incomplete_trade_count"),
        "excluded_hold_crosses_gap_count": _required_int(
            summary,
            "excluded_hold_crosses_gap_count",
        ),
        "mean_realized_r": _float_or_none(summary.get("mean_realized_r")),
        "total_realized_r": _required_float(summary, "total_realized_r"),
        "win_rate": _float_or_none(summary.get("win_rate")),
        "max_drawdown_r": _float_or_none(summary.get("max_drawdown_r")),
        "adx_decision_point_count": decision_point,
        "adx_observed_decision_count": observed,
        "adx_kept_count": kept,
        "adx_rejected_count": rejected,
        "adx_missing_count": missing,
        "adx_kept_fraction": None if observed == 0 else kept / observed,
        "adx_missing_fraction": None if decision_point == 0 else missing / decision_point,
    }


def _mean_sign_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"positive": 0, "zero": 0, "negative": 0, "missing": 0}
    for row in rows:
        value = row["mean_realized_r"]
        if value is None:
            counts["missing"] += 1
        elif value > 0.0:
            counts["positive"] += 1
        elif value < 0.0:
            counts["negative"] += 1
        else:
            counts["zero"] += 1
    return counts


def _mean_range(rows: Sequence[Mapping[str, Any]]) -> dict[str, float] | None:
    values = [
        float(row["mean_realized_r"])
        for row in rows
        if row["mean_realized_r"] is not None
    ]
    if not values:
        return None
    minimum = min(values)
    maximum = max(values)
    return {
        "min": minimum,
        "max": maximum,
        "range": maximum - minimum,
    }


def _restrictiveness_drift(rows: Sequence[Mapping[str, Any]]) -> dict[str, float] | None:
    values = [
        float(row["adx_kept_fraction"])
        for row in rows
        if row["adx_kept_fraction"] is not None
    ]
    if not values:
        return None
    minimum = min(values)
    maximum = max(values)
    return {
        "min_adx_kept_fraction": minimum,
        "max_adx_kept_fraction": maximum,
        "range_adx_kept_fraction": maximum - minimum,
    }


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_float(mapping: Mapping[str, Any], key: str) -> float:
    value = _float_or_none(mapping.get(key))
    if value is None:
        raise ValueError(f"{key} must be numeric")
    return value


def _required_int(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping.get(key)
    if value is None or value == "":
        raise ValueError(f"{key} must be an integer")
    return int(float(value))


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
