from __future__ import annotations

from collections.abc import Sequence
from typing import Any
import math

import numpy as np

from shared.validation.realized_r import max_drawdown_r


METHOD = "iid_bootstrap_equity_curves"
PERCENTILES = (5, 50, 95)


def monte_carlo_equity_curves(
    realized_r: Sequence[float],
    n_iter: int,
    random_seed: int,
) -> dict[str, Any]:
    if n_iter <= 0:
        raise ValueError(f"n_iter must be positive, got: {n_iter}")

    values = np.array([_finite_float(value) for value in realized_r], dtype=float)
    if values.size == 0:
        raise ValueError("realized_r must contain at least one value")

    observed_curve = _equity_curve(values)
    rng = np.random.default_rng(random_seed)
    sampled_returns = rng.choice(values, size=(n_iter, values.size), replace=True)
    sampled_curves = sampled_returns.cumsum(axis=1)
    final_equity = sampled_curves[:, -1]
    max_drawdowns = np.array(
        [max_drawdown_r(row) for row in sampled_returns],
        dtype=float,
    )
    band_values = np.percentile(sampled_curves, PERCENTILES, axis=0)

    return {
        "method": METHOD,
        "random_seed": random_seed,
        "n_iter": n_iter,
        "sample_count": int(values.size),
        "observed": {
            "equity_curve": observed_curve,
            "final_equity_r": observed_curve[-1],
            "max_drawdown_r": max_drawdown_r(values),
        },
        "equity_curve_percentile_bands": _equity_curve_bands(band_values),
        "final_equity_distribution": _distribution_summary(
            final_equity,
            include_probability_positive=True,
        ),
        "max_drawdown_distribution": _distribution_summary(
            max_drawdowns,
            include_probability_positive=False,
        ),
    }


def _finite_float(value: float) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"realized R must be finite, got: {value}")
    return converted


def _equity_curve(values: np.ndarray) -> list[float]:
    return [float(value) for value in values.cumsum()]


def _equity_curve_bands(band_values: np.ndarray) -> list[dict[str, float | int]]:
    bands: list[dict[str, float | int]] = []
    for index in range(band_values.shape[1]):
        bands.append(
            {
                "trade_number": index + 1,
                "p05": float(band_values[0, index]),
                "p50": float(band_values[1, index]),
                "p95": float(band_values[2, index]),
            }
        )
    return bands


def _distribution_summary(
    values: np.ndarray,
    *,
    include_probability_positive: bool,
) -> dict[str, float]:
    percentiles = np.percentile(values, PERCENTILES)
    summary = {
        "mean": float(values.mean()),
        "p05": float(percentiles[0]),
        "p50": float(percentiles[1]),
        "p95": float(percentiles[2]),
        "min": float(values.min()),
        "max": float(values.max()),
    }
    if include_probability_positive:
        summary["probability_positive_total_r"] = float(np.mean(values > 0.0))
    return summary
