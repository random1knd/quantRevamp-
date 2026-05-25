from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


REPORT_TYPE = "child_threshold_nudge_report"
NUDGE_CSV_FIELDS = [
    "threshold_label",
    "threshold_quantile",
    "adx_filter_threshold",
    "source_rule_id",
    "is_baseline",
    "trade_count",
    "all_completed_trade_count",
    "completed_non_gap_trade_count",
    "incomplete_trade_count",
    "excluded_hold_crosses_gap_count",
    "mean_realized_r",
    "total_realized_r",
    "win_rate",
    "max_drawdown_r",
    "delta_completed_non_gap_trade_count",
    "delta_mean_realized_r",
    "delta_total_realized_r",
    "delta_win_rate",
    "delta_max_drawdown_r",
]


def child_threshold_nudge_report(
    rerun_summaries: Sequence[Mapping[str, Any]],
    *,
    baseline_threshold_quantile: float,
) -> dict[str, Any]:
    rows = [_normalize_summary(summary) for summary in rerun_summaries]
    if not rows:
        raise ValueError("rerun_summaries must not be empty")

    baseline_quantile = float(baseline_threshold_quantile)
    baselines = [
        row for row in rows if row["threshold_quantile"] == baseline_quantile
    ]
    if len(baselines) != 1:
        raise ValueError("exactly one baseline threshold summary is required")
    baseline = baselines[0]

    compared = [
        _with_deltas(row, baseline=baseline)
        for row in sorted(rows, key=lambda item: item["threshold_quantile"])
    ]
    return {
        "report_type": REPORT_TYPE,
        "report_scope": "validation_child_rerun",
        "threshold_name": "adx_filter_threshold",
        "threshold_grid_source": "literal_slicer_rows",
        "baseline_threshold_quantile": baseline_quantile,
        "judgment_status": "report_only_no_pass_fail",
        "coverage_only": True,
        "edge_validation_status": "cannot_promote_edge",
        "selection_policy": "no_threshold_selection_allowed",
        "baseline": _with_deltas(baseline, baseline=baseline),
        "grid": compared,
    }


def _with_deltas(
    row: Mapping[str, Any],
    *,
    baseline: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        **dict(row),
        "is_baseline": row["threshold_quantile"] == baseline["threshold_quantile"],
        "delta_completed_non_gap_trade_count": _delta(
            row["completed_non_gap_trade_count"],
            baseline["completed_non_gap_trade_count"],
        ),
        "delta_mean_realized_r": _delta(
            row["mean_realized_r"],
            baseline["mean_realized_r"],
        ),
        "delta_total_realized_r": _delta(
            row["total_realized_r"],
            baseline["total_realized_r"],
        ),
        "delta_win_rate": _delta(row["win_rate"], baseline["win_rate"]),
        "delta_max_drawdown_r": _delta(
            row["max_drawdown_r"],
            baseline["max_drawdown_r"],
        ),
    }


def _normalize_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "threshold_label": _required_string(summary, "threshold_label"),
        "threshold_quantile": _required_float(summary, "threshold_quantile"),
        "adx_filter_threshold": _required_float(summary, "adx_filter_threshold"),
        "source_rule_id": _required_string(summary, "source_rule_id"),
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
    }


def _delta(value: float | int | None, baseline: float | int | None) -> float | None:
    if value is None or baseline is None:
        return None
    return float(value) - float(baseline)


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
