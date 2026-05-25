from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


REPORT_TYPE = "threshold_neighborhood_report"
POLICY_NAME = "immediate_neighbor_positive_half_mean"
MIN_IMMEDIATE_NEIGHBOR_MEAN_FRACTION = 0.5

NEIGHBOR_CSV_FIELDS = [
    "anchor_rule_id",
    "neighbor_rule_id",
    "neighbor_rule_index",
    "column",
    "direction",
    "threshold_quantile",
    "threshold",
    "neighbor_position",
    "is_immediate_neighbor",
    "kept_count",
    "eligible",
    "mean_realized_r",
    "median_realized_r",
    "winsorized_mean_realized_r",
    "win_rate",
    "max_drawdown_r",
    "selected_metric_rank",
    "outlier_divergence_flag",
    "delta_kept_count",
    "delta_mean_realized_r",
    "delta_median_realized_r",
    "delta_winsorized_mean_realized_r",
    "mean_fraction_of_anchor",
    "passes_spike_policy",
]


def threshold_neighborhood_report(
    scored_rules: Sequence[Mapping[str, Any]],
    anchor_rule: Mapping[str, Any],
    *,
    anchor_rule_role: str,
) -> dict[str, Any]:
    rows = [_normalize_rule(rule) for rule in scored_rules]
    if not rows:
        raise ValueError("scored_rules must not be empty")

    anchor_input = _normalize_rule(anchor_rule)
    anchor_index = _find_anchor_index(rows, anchor_input)
    anchor = rows[anchor_index]

    same_column_direction = sorted(
        [
            rule
            for rule in rows
            if rule["column"] == anchor["column"]
            and rule["direction"] == anchor["direction"]
        ],
        key=lambda rule: (rule["threshold_quantile"], rule["rule_index"]),
    )
    same_index = _find_anchor_index(same_column_direction, anchor)
    neighbors = [
        _neighbor_diagnostic(
            anchor=anchor,
            neighbor=rule,
            is_immediate_neighbor=abs(index - same_index) == 1,
        )
        for index, rule in enumerate(same_column_direction)
        if index != same_index
    ]
    immediate_neighbors = [
        neighbor for neighbor in neighbors if neighbor["is_immediate_neighbor"]
    ]
    spike_policy = _spike_policy(anchor, immediate_neighbors)

    return {
        "report_type": REPORT_TYPE,
        "report_scope": "train_side_discovery_contaminated",
        "edge_validation_status": "cannot_validate_edge",
        "anchor_rule_role": anchor_rule_role,
        "anchor_rule": _rule_diagnostic(anchor),
        "same_column_direction_rule_count": len(same_column_direction),
        "neighbor_count": len(neighbors),
        "immediate_neighbor_count": len(immediate_neighbors),
        "spike_policy": spike_policy,
        "neighbors": neighbors,
    }


def _neighbor_diagnostic(
    *,
    anchor: dict[str, Any],
    neighbor: dict[str, Any],
    is_immediate_neighbor: bool,
) -> dict[str, Any]:
    anchor_mean = anchor["mean_realized_r"]
    neighbor_mean = neighbor["mean_realized_r"]
    return {
        "anchor_rule_id": anchor["rule_id"],
        "neighbor_rule_id": neighbor["rule_id"],
        "neighbor_rule_index": neighbor["rule_index"],
        "column": neighbor["column"],
        "direction": neighbor["direction"],
        "threshold_quantile": neighbor["threshold_quantile"],
        "threshold": neighbor["threshold"],
        "neighbor_position": _neighbor_position(anchor, neighbor),
        "is_immediate_neighbor": is_immediate_neighbor,
        "kept_count": neighbor["kept_count"],
        "eligible": neighbor["eligible"],
        "mean_realized_r": neighbor_mean,
        "median_realized_r": neighbor["median_realized_r"],
        "winsorized_mean_realized_r": neighbor["winsorized_mean_realized_r"],
        "win_rate": neighbor["win_rate"],
        "max_drawdown_r": neighbor["max_drawdown_r"],
        "selected_metric_rank": neighbor["selected_metric_rank"],
        "outlier_divergence_flag": neighbor["outlier_divergence_flag"],
        "delta_kept_count": _delta(neighbor["kept_count"], anchor["kept_count"]),
        "delta_mean_realized_r": _delta(neighbor_mean, anchor_mean),
        "delta_median_realized_r": _delta(
            neighbor["median_realized_r"],
            anchor["median_realized_r"],
        ),
        "delta_winsorized_mean_realized_r": _delta(
            neighbor["winsorized_mean_realized_r"],
            anchor["winsorized_mean_realized_r"],
        ),
        "mean_fraction_of_anchor": _mean_fraction(
            neighbor_mean=neighbor_mean,
            anchor_mean=anchor_mean,
        ),
        "passes_spike_policy": _passes_spike_policy(
            neighbor_mean=neighbor_mean,
            anchor_mean=anchor_mean,
        )
        if is_immediate_neighbor
        else None,
    }


def _spike_policy(
    anchor: dict[str, Any],
    immediate_neighbors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    anchor_mean = anchor["mean_realized_r"]
    if anchor_mean is None or anchor_mean <= 0.0:
        return {
            "policy_name": POLICY_NAME,
            "advisory_only": True,
            "applicability": "not_applicable_anchor_mean_not_positive",
            "minimum_neighbor_mean_fraction_of_anchor": (
                MIN_IMMEDIATE_NEIGHBOR_MEAN_FRACTION
            ),
            "coarse_grid_note": (
                "Immediate neighbors are adjacent searched quantiles; current "
                "q20/q30/q40-style grids only catch obvious threshold spikes."
            ),
            "policy_status": "not_applicable",
            "passing_immediate_neighbor_count": 0,
            "isolated_spike_flag": False,
        }

    passing_count = sum(
        1 for neighbor in immediate_neighbors if neighbor["passes_spike_policy"]
    )
    immediate_count = len(immediate_neighbors)
    isolated_spike = immediate_count >= 2 and passing_count == 0
    if passing_count > 0:
        policy_status = "pass"
    elif isolated_spike:
        policy_status = "fail_isolated_spike"
    elif immediate_count == 0:
        policy_status = "not_evaluable_no_immediate_neighbors"
    else:
        policy_status = "fail_no_passing_immediate_neighbor"

    return {
        "policy_name": POLICY_NAME,
        "advisory_only": True,
        "applicability": "applicable_anchor_mean_positive",
        "minimum_neighbor_mean_fraction_of_anchor": (
            MIN_IMMEDIATE_NEIGHBOR_MEAN_FRACTION
        ),
        "coarse_grid_note": (
            "Immediate neighbors are adjacent searched quantiles; current "
            "q20/q30/q40-style grids only catch obvious threshold spikes."
        ),
        "policy_status": policy_status,
        "passing_immediate_neighbor_count": passing_count,
        "isolated_spike_flag": isolated_spike,
    }


def _passes_spike_policy(
    *,
    neighbor_mean: float | None,
    anchor_mean: float | None,
) -> bool | None:
    if anchor_mean is None or anchor_mean <= 0.0:
        return None
    if neighbor_mean is None:
        return False
    return (
        neighbor_mean > 0.0
        and neighbor_mean >= anchor_mean * MIN_IMMEDIATE_NEIGHBOR_MEAN_FRACTION
    )


def _rule_diagnostic(rule: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": rule["rule_id"],
        "rule_index": rule["rule_index"],
        "column": rule["column"],
        "direction": rule["direction"],
        "threshold_quantile": rule["threshold_quantile"],
        "threshold": rule["threshold"],
        "kept_count": rule["kept_count"],
        "eligible": rule["eligible"],
        "mean_realized_r": rule["mean_realized_r"],
        "median_realized_r": rule["median_realized_r"],
        "winsorized_mean_realized_r": rule["winsorized_mean_realized_r"],
        "win_rate": rule["win_rate"],
        "max_drawdown_r": rule["max_drawdown_r"],
        "selected_metric_rank": rule["selected_metric_rank"],
        "outlier_divergence_flag": rule["outlier_divergence_flag"],
    }


def _normalize_rule(rule: Mapping[str, Any]) -> dict[str, Any]:
    if rule is None:
        raise ValueError("anchor_rule must not be None")
    return {
        "rule_id": _required_string(rule, "rule_id"),
        "rule_index": _int_or_none(rule.get("rule_index")),
        "column": _required_string(rule, "column"),
        "direction": _required_string(rule, "direction"),
        "threshold_quantile": _required_float(rule, "threshold_quantile"),
        "threshold": _float_or_none(rule.get("threshold")),
        "kept_count": _int_or_none(rule.get("kept_count")),
        "eligible": _bool_or_none(rule.get("eligible")),
        "mean_realized_r": _float_or_none(rule.get("mean_realized_r")),
        "median_realized_r": _float_or_none(rule.get("median_realized_r")),
        "winsorized_mean_realized_r": _float_or_none(
            rule.get("winsorized_mean_realized_r")
        ),
        "win_rate": _float_or_none(rule.get("win_rate")),
        "max_drawdown_r": _float_or_none(rule.get("max_drawdown_r")),
        "selected_metric_rank": _int_or_none(rule.get("selected_metric_rank")),
        "outlier_divergence_flag": bool(
            _bool_or_none(rule.get("outlier_divergence_flag"))
        ),
    }


def _find_anchor_index(
    rows: Sequence[Mapping[str, Any]],
    anchor: Mapping[str, Any],
) -> int:
    for index, row in enumerate(rows):
        if row["rule_id"] == anchor["rule_id"]:
            return index

    for index, row in enumerate(rows):
        if (
            row["column"] == anchor["column"]
            and row["direction"] == anchor["direction"]
            and row["threshold_quantile"] == anchor["threshold_quantile"]
        ):
            return index

    raise ValueError("anchor_rule must match one scored rule")


def _neighbor_position(anchor: Mapping[str, Any], neighbor: Mapping[str, Any]) -> str:
    if neighbor["threshold_quantile"] < anchor["threshold_quantile"]:
        return "lower_quantile"
    if neighbor["threshold_quantile"] > anchor["threshold_quantile"]:
        return "higher_quantile"
    return "same_quantile"


def _delta(value: float | int | None, anchor_value: float | int | None) -> float | None:
    if value is None or anchor_value is None:
        return None
    return float(value) - float(anchor_value)


def _mean_fraction(
    *,
    neighbor_mean: float | None,
    anchor_mean: float | None,
) -> float | None:
    if neighbor_mean is None or anchor_mean in (None, 0.0):
        return None
    return neighbor_mean / anchor_mean


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


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def _bool_or_none(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("true", "1"):
            return True
        if normalized in ("false", "0"):
            return False
    raise ValueError(f"invalid boolean value: {value!r}")
