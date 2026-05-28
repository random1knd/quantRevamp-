from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


REPORT_TYPE = "cross_instrument_report"
CROSS_INSTRUMENT_CSV_FIELDS = [
    "instrument",
    "input_file",
    "session_model",
    "split",
    "trade_count",
    "all_completed_trade_count",
    "completed_non_gap_trade_count",
    "incomplete_trade_count",
    "excluded_hold_crosses_gap_count",
    "mean_realized_r",
    "total_realized_r",
    "win_rate",
    "max_drawdown_r",
    "minimum_trade_count_tier",
    "tick_size",
    "point_value",
    "tick_value",
    "slippage_ticks_per_side",
    "commission_per_round_turn",
    "commission_is_smoke_test",
    "adx_decision_point_count",
    "adx_observed_decision_count",
    "adx_kept_count",
    "adx_rejected_count",
    "adx_missing_count",
    "adx_kept_fraction",
    "adx_missing_fraction",
]


def cross_instrument_report(
    instrument_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [_normalize_summary(summary) for summary in instrument_summaries]
    if not rows:
        raise ValueError("instrument_summaries must not be empty")

    rows = sorted(rows, key=lambda row: row["instrument"])
    return {
        "report_type": REPORT_TYPE,
        "report_scope": "validation_child_cross_instrument",
        "judgment_status": "report_only_no_pass_fail",
        "coverage_only": True,
        "edge_validation_status": "cannot_promote_edge",
        "blueprint_demonstration": True,
        "rejected_child_not_edge_evidence": True,
        "selection_policy": "no_instrument_selection_allowed",
        "instrument_count": len(rows),
        "instrument_order": [row["instrument"] for row in rows],
        "instrument_mean_sign_counts": _mean_sign_counts(rows),
        "mean_realized_r_range": _mean_range(rows),
        "completed_non_gap_trade_count_range": _count_range(
            rows,
            "completed_non_gap_trade_count",
        ),
        "instruments": rows,
    }


def _normalize_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    kept = _required_int(summary, "adx_kept_count")
    rejected = _required_int(summary, "adx_rejected_count")
    missing = _required_int(summary, "adx_missing_count")
    observed = kept + rejected
    decision_point = observed + missing
    accounting = dict(summary.get("accounting_constants", {}))
    return {
        "instrument": _required_string(summary, "instrument"),
        "input_file": _required_string(summary, "input_file"),
        "session_model": _required_string(summary, "session_model"),
        "split": _required_string(summary, "split"),
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
        "minimum_trade_count_tier": _required_string(
            summary,
            "minimum_trade_count_tier",
        ),
        "tick_size": _float_or_none(accounting.get("tick_size")),
        "point_value": _float_or_none(accounting.get("point_value")),
        "tick_value": _float_or_none(accounting.get("tick_value")),
        "slippage_ticks_per_side": _float_or_none(
            accounting.get("slippage_ticks_per_side")
        ),
        "commission_per_round_turn": _float_or_none(
            accounting.get("commission_per_round_turn")
        ),
        "commission_is_smoke_test": accounting.get("commission_is_smoke_test"),
        "adx_decision_point_count": decision_point,
        "adx_observed_decision_count": observed,
        "adx_kept_count": kept,
        "adx_rejected_count": rejected,
        "adx_missing_count": missing,
        "adx_kept_fraction": None if observed == 0 else kept / observed,
        "adx_missing_fraction": None if decision_point == 0 else missing / decision_point,
        "accounting_constants": accounting,
        "session_config": dict(summary.get("session_config", {})),
        "data_start": summary.get("data_start"),
        "data_end": summary.get("data_end"),
        "session_start": summary.get("session_start"),
        "session_end": summary.get("session_end"),
        "splits": dict(summary.get("splits", {})),
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


def _count_range(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    values = [_required_int(row, key) for row in rows]
    return {
        "min": min(values),
        "max": max(values),
        "range": max(values) - min(values),
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
