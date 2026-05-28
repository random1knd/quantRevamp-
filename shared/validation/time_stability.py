from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from shared.validation.realized_r import summarize_realized_r


REPORT_TYPE = "time_stability_report"
SPARSE_TRADE_FLOOR = 20
GRANULARITIES = ("month", "quarter", "year")
TIME_STABILITY_CSV_FIELDS = [
    "granularity",
    "period_index",
    "period_label",
    "period_start",
    "period_end",
    "bucket_status",
    "trade_count",
    "mean_realized_r",
    "total_realized_r",
    "win_rate",
    "max_drawdown_r",
    "absolute_total_realized_r",
    "share_of_total_abs_bucket_r",
    "leave_one_bucket_out_total_r",
]


def time_stability_report(
    trades: Sequence[Mapping[str, Any]],
    *,
    granularities: Sequence[str] = GRANULARITIES,
    sparse_trade_floor: int = SPARSE_TRADE_FLOOR,
) -> dict[str, Any]:
    if sparse_trade_floor <= 0:
        raise ValueError("sparse_trade_floor must be positive")

    normalized_trades = _normalize_trades(trades)
    if not normalized_trades:
        raise ValueError("trades must not be empty")

    requested = _normalize_granularities(granularities)
    groups = {
        granularity: _granularity_report(
            normalized_trades,
            granularity=granularity,
            sparse_trade_floor=sparse_trade_floor,
        )
        for granularity in requested
    }
    return {
        "report_type": REPORT_TYPE,
        "report_scope": "validation_child_time_stability",
        "judgment_status": "report_only_no_pass_fail",
        "coverage_only": True,
        "edge_validation_status": "cannot_promote_edge",
        "selection_policy": "no_period_selection_allowed",
        "grouping_timestamp": "entry_time",
        "sparse_trade_floor": sparse_trade_floor,
        "granularity_order": list(requested),
        "trade_count": len(normalized_trades),
        "total_realized_r": sum(trade["realized_r"] for trade in normalized_trades),
        "granularities": groups,
    }


def _granularity_report(
    trades: Sequence[dict[str, Any]],
    *,
    granularity: str,
    sparse_trade_floor: int,
) -> dict[str, Any]:
    buckets = _bucket_summaries(
        trades,
        granularity=granularity,
        sparse_trade_floor=sparse_trade_floor,
    )
    sufficient = [
        bucket for bucket in buckets if bucket["bucket_status"] == "sufficient"
    ]
    concentration = _concentration_summary(buckets)
    return {
        "granularity": granularity,
        "bucket_count": len(buckets),
        "sufficient_bucket_count": len(sufficient),
        "sparse_bucket_count": len(buckets) - len(sufficient),
        "bucket_mean_sign_counts": _mean_sign_counts(sufficient),
        "total_realized_r": sum(bucket["total_realized_r"] for bucket in buckets),
        **concentration,
        "buckets": buckets,
    }


def _bucket_summaries(
    trades: Sequence[dict[str, Any]],
    *,
    granularity: str,
    sparse_trade_floor: int,
) -> list[dict[str, Any]]:
    by_period: dict[pd.Period, list[dict[str, Any]]] = {}
    for trade in trades:
        period = _period(trade["entry_time"], granularity=granularity)
        by_period.setdefault(period, []).append(trade)

    period_items = sorted(by_period.items(), key=lambda item: item[0].start_time)
    total_realized_r = sum(trade["realized_r"] for trade in trades)
    total_abs_bucket_r = sum(
        abs(sum(trade["realized_r"] for trade in period_trades))
        for _, period_trades in period_items
    )

    buckets = []
    for index, (period, period_trades) in enumerate(period_items, start=1):
        period_trades = sorted(period_trades, key=lambda trade: trade["entry_time"])
        values = [trade["realized_r"] for trade in period_trades]
        summary = summarize_realized_r(values)
        bucket_total = float(summary["total_realized_r"])
        absolute_total = abs(bucket_total)
        buckets.append(
            {
                "granularity": granularity,
                "period_index": index,
                "period_label": _period_label(period, granularity=granularity),
                "period_start": period.start_time.date().isoformat(),
                "period_end": period.end_time.date().isoformat(),
                "bucket_status": (
                    "insufficient"
                    if len(period_trades) < sparse_trade_floor
                    else "sufficient"
                ),
                "trade_count": len(period_trades),
                "mean_realized_r": summary["mean_realized_r"],
                "total_realized_r": bucket_total,
                "win_rate": summary["win_rate"],
                "max_drawdown_r": summary["max_drawdown_r"],
                "absolute_total_realized_r": absolute_total,
                "share_of_total_abs_bucket_r": (
                    0.0 if total_abs_bucket_r == 0.0 else absolute_total / total_abs_bucket_r
                ),
                "leave_one_bucket_out_total_r": total_realized_r - bucket_total,
            }
        )
    return buckets


def _concentration_summary(buckets: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total_abs_bucket_r = sum(
        _required_float(bucket, "absolute_total_realized_r") for bucket in buckets
    )
    total_realized_r = sum(
        _required_float(bucket, "total_realized_r") for bucket in buckets
    )
    largest = max(
        buckets,
        key=lambda bucket: (
            _required_float(bucket, "absolute_total_realized_r"),
            -int(bucket["period_index"]),
        ),
    )
    largest_abs = _required_float(largest, "absolute_total_realized_r")
    return {
        "total_abs_bucket_realized_r": total_abs_bucket_r,
        "largest_abs_total_r_bucket": {
            "granularity": largest["granularity"],
            "period_label": largest["period_label"],
            "period_start": largest["period_start"],
            "period_end": largest["period_end"],
            "trade_count": largest["trade_count"],
            "total_realized_r": largest["total_realized_r"],
            "absolute_total_realized_r": largest_abs,
        },
        "largest_abs_total_r_share": (
            0.0 if total_abs_bucket_r == 0.0 else largest_abs / total_abs_bucket_r
        ),
        "leave_one_largest_abs_total_r_out_total_r": (
            total_realized_r - _required_float(largest, "total_realized_r")
        ),
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


def _normalize_trades(trades: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, trade in enumerate(trades, start=1):
        entry_time = _timestamp(_trade_value(trade, "entry_time", "EntryTime"))
        realized_r = _finite_float(
            _trade_value(trade, "realized_r", "RealizedR"),
            f"trade {index} realized_r",
        )
        rows.append({"entry_time": entry_time, "realized_r": realized_r})
    return sorted(rows, key=lambda row: row["entry_time"])


def _normalize_granularities(granularities: Sequence[str]) -> tuple[str, ...]:
    if not granularities:
        raise ValueError("granularities must not be empty")
    invalid = [value for value in granularities if value not in GRANULARITIES]
    if invalid:
        raise ValueError(f"unsupported granularities: {invalid}")
    return tuple(dict.fromkeys(granularities))


def _period(entry_time: pd.Timestamp, *, granularity: str) -> pd.Period:
    if entry_time.tzinfo is not None:
        entry_time = entry_time.tz_localize(None)
    if granularity == "month":
        return entry_time.to_period("M")
    if granularity == "quarter":
        return entry_time.to_period("Q")
    if granularity == "year":
        return entry_time.to_period("Y")
    raise ValueError(f"unsupported granularity: {granularity}")


def _period_label(period: pd.Period, *, granularity: str) -> str:
    if granularity == "quarter":
        return f"{period.year}Q{period.quarter}"
    return str(period)


def _trade_value(trade: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in trade:
            return trade[key]
    raise ValueError(f"missing required trade field, expected one of: {keys}")


def _timestamp(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("entry_time must be a valid timestamp")
    return timestamp


def _required_float(mapping: Mapping[str, Any], key: str) -> float:
    return _finite_float(mapping[key], key)


def _finite_float(value: Any, label: str) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{label} must be finite")
    return converted
