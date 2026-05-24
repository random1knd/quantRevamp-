from __future__ import annotations

import math
from statistics import median
from typing import Sequence


MINIMUM_TRADE_COUNT_POLICY = "lt30 insufficient; 30-99 low_sample; ge100 normal"


def summarize_realized_r(
    realized_r: Sequence[float],
    *,
    trade_count: int | None = None,
    incomplete_trade_count: int = 0,
) -> dict[str, object]:
    values = [_finite_float(value) for value in realized_r]
    if incomplete_trade_count < 0:
        raise ValueError("incomplete_trade_count must be non-negative")

    minimum_trade_count = len(values) + incomplete_trade_count
    if trade_count is None:
        trade_count = minimum_trade_count
    elif trade_count < minimum_trade_count:
        raise ValueError(
            "trade_count must be at least completed plus incomplete trades"
        )

    return {
        "trade_count": trade_count,
        "completed_trade_count": len(values),
        "incomplete_trade_count": incomplete_trade_count,
        "mean_realized_r": _mean(values),
        "median_realized_r": _median(values),
        "total_realized_r": sum(values),
        "win_rate": _win_rate(values),
        "max_drawdown_r": max_drawdown_r(values),
        "r_multiple_diagnostics": _r_multiple_diagnostics(values),
        "minimum_trade_count_tier": minimum_trade_count_policy(len(values)),
        "minimum_trade_count_policy": MINIMUM_TRADE_COUNT_POLICY,
    }


def minimum_trade_count_policy(completed_trade_count: int) -> str:
    if completed_trade_count < 0:
        raise ValueError("completed_trade_count must be non-negative")
    if completed_trade_count < 30:
        return "insufficient_lt_30"
    if completed_trade_count < 100:
        return "low_sample_30_to_99"
    return "normal_ge_100"


def max_drawdown_r(realized_r: Sequence[float]) -> float | None:
    values = [_finite_float(value) for value in realized_r]
    if not values:
        return None

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return max_drawdown


def _finite_float(value: float) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"realized R must be finite, got: {value}")
    return converted


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(median(values))


def _win_rate(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(1 for value in values if value > 0.0) / len(values)


def _r_multiple_diagnostics(values: list[float]) -> dict[str, int]:
    return {
        f"{threshold}R_or_better": sum(1 for value in values if value >= threshold)
        for threshold in range(1, 11)
    }
