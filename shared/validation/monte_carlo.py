from __future__ import annotations

from collections.abc import Sequence
from typing import Any
import math

import numpy as np


METHOD = "centered_bootstrap_mean"
DEFAULT_SIDEDNESS = "one_sided_positive"
SIDEDNESSES = ("one_sided_positive", "two_sided")


def centered_bootstrap_mean_report(
    realized_r: Sequence[float],
    *,
    n_iter: int,
    random_seed: int,
    sidedness: str = DEFAULT_SIDEDNESS,
    include_null_values: bool = False,
) -> dict[str, Any]:
    if n_iter <= 0:
        raise ValueError(f"n_iter must be positive, got: {n_iter}")
    if sidedness not in SIDEDNESSES:
        raise ValueError(f"unsupported sidedness: {sidedness}")

    values = np.array([_finite_float(value) for value in realized_r], dtype=float)
    if values.size == 0:
        raise ValueError("realized_r must contain at least one value")

    observed_mean = float(values.mean())
    centered_values = values - observed_mean
    rng = np.random.default_rng(random_seed)
    null_means: list[float] = []

    for _ in range(n_iter):
        sample = rng.choice(centered_values, size=values.size, replace=True)
        null_means.append(float(sample.mean()))

    extreme_null_count = _extreme_null_count(
        null_means,
        observed_mean=observed_mean,
        sidedness=sidedness,
    )
    p_value = (1 + extreme_null_count) / (1 + n_iter)

    report = {
        "method": METHOD,
        "score": "mean_realized_r",
        "null_model": "centered_bootstrap_with_replacement",
        "p_value_smoothing": "plus_one",
        "sidedness": sidedness,
        "random_seed": random_seed,
        "n_iter": n_iter,
        "sample_count": int(values.size),
        "observed_mean_realized_r": observed_mean,
        "centered_sample_mean_realized_r": float(centered_values.mean()),
        "extreme_null_count": extreme_null_count,
        "extreme_rule": _extreme_rule(sidedness),
        "p_value": p_value,
        "null_distribution_summary": _null_distribution_summary(null_means),
    }
    if include_null_values:
        report["null_mean_realized_r"] = null_means
    return report


def _finite_float(value: float) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"realized R must be finite, got: {value}")
    return converted


def _extreme_null_count(
    null_means: Sequence[float],
    *,
    observed_mean: float,
    sidedness: str,
) -> int:
    if sidedness == "one_sided_positive":
        return sum(1 for value in null_means if value >= observed_mean)
    if sidedness == "two_sided":
        return sum(
            1 for value in null_means if abs(value) >= abs(observed_mean)
        )
    raise ValueError(f"unsupported sidedness: {sidedness}")


def _extreme_rule(sidedness: str) -> str:
    if sidedness == "one_sided_positive":
        return "null_mean >= observed_mean"
    if sidedness == "two_sided":
        return "abs(null_mean) >= abs(observed_mean)"
    raise ValueError(f"unsupported sidedness: {sidedness}")


def _null_distribution_summary(null_means: Sequence[float]) -> dict[str, float]:
    values = np.array(null_means, dtype=float)
    percentiles = np.percentile(values, [5, 50, 95])
    return {
        "mean": float(values.mean()),
        "median": float(percentiles[1]),
        "p05": float(percentiles[0]),
        "p95": float(percentiles[2]),
        "min": float(values.min()),
        "max": float(values.max()),
    }
