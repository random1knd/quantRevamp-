from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from shared.validation.realized_r import max_drawdown_r


RULE_FORM = "single_column_threshold"
LE = "<="
GE = ">="


def build_threshold_rules(
    frame: pd.DataFrame,
    spec: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build predeclared one-column threshold rules from context quantiles."""

    columns = _columns_spec(spec)
    quantiles = _quantiles(spec)

    rules: list[dict[str, Any]] = []
    for column_spec in columns:
        column = _column_name(column_spec)
        directions = _directions(column_spec)
        if column not in frame.columns:
            raise ValueError(f"missing search column: {column}")

        values = pd.to_numeric(frame[column], errors="raise").dropna()
        if values.empty:
            raise ValueError(f"search column has no non-null values: {column}")

        thresholds = {
            quantile: float(values.quantile(quantile / 100.0))
            for quantile in quantiles
        }
        for direction in directions:
            for quantile in quantiles:
                threshold = thresholds[quantile]
                rules.append(
                    {
                        "rule_id": _rule_id(
                            column=column,
                            direction=direction,
                            quantile=quantile,
                        ),
                        "rule_index": len(rules),
                        "rule_form": RULE_FORM,
                        "column": column,
                        "direction": direction,
                        "threshold_quantile": quantile,
                        "threshold": threshold,
                    }
                )

    return _with_coincident_thresholds(rules)


def score_rules(
    frame: pd.DataFrame,
    rules: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
) -> list[dict[str, Any]]:
    realized_r_column = _required_string(spec, "realized_r_column")
    if realized_r_column not in frame.columns:
        raise ValueError(f"missing realized-R column: {realized_r_column}")

    realized_r = pd.to_numeric(frame[realized_r_column], errors="raise")
    if realized_r.isna().any():
        raise ValueError("realized-R values must not be null")

    min_kept_count = _required_int(spec, "min_kept_count")
    if min_kept_count < 1:
        raise ValueError("min_kept_count must be positive")

    winsorize_fraction = _winsorize_fraction(spec)

    scored: list[dict[str, Any]] = []
    for rule in rules:
        mask = rule_mask(frame, rule)
        kept = realized_r.loc[mask]
        kept_count = int(len(kept))
        mean_realized_r = _mean(kept)
        median_realized_r = _median(kept)
        scored.append(
            {
                **dict(rule),
                "non_null_count": int(frame[rule["column"]].notna().sum()),
                "kept_count": kept_count,
                "eligible": kept_count >= min_kept_count,
                "mean_realized_r": mean_realized_r,
                "median_realized_r": median_realized_r,
                "winsorized_mean_realized_r": _winsorized_mean(
                    kept,
                    fraction=winsorize_fraction,
                ),
                "win_rate": _win_rate(kept),
                "max_drawdown_r": max_drawdown_r(kept.to_list()),
                "selected_metric_rank": None,
                "selected": False,
                "outlier_divergence_flag": _outlier_divergence(
                    mean_realized_r=mean_realized_r,
                    median_realized_r=median_realized_r,
                ),
            }
        )

    _assign_ranks(scored)
    return scored


def run_rule_search(
    frame: pd.DataFrame,
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    rules = build_threshold_rules(frame, spec)
    scored_rules = score_rules(frame, rules, spec)

    eligible_rules = [
        rule
        for rule in scored_rules
        if rule["eligible"] and rule["mean_realized_r"] is not None
    ]
    best_rule = _best_rule(eligible_rules)

    selected_rule = None
    no_candidate_reason = None
    if best_rule is None:
        no_candidate_reason = "no_eligible_rules"
    elif best_rule["mean_realized_r"] <= 0.0:
        no_candidate_reason = "best_mean_not_positive"
    else:
        selected_rule = best_rule
        selected_rule["selected"] = True
        scored_rules[selected_rule["rule_index"]]["selected"] = True

    return {
        "searched_rule_count": len(scored_rules),
        "eligible_rule_count": len(eligible_rules),
        "candidate_status": (
            "candidate_selected" if selected_rule is not None else "no_candidate"
        ),
        "no_candidate_reason": no_candidate_reason,
        "selected_rule": selected_rule,
        "best_rule": best_rule,
        "rules": scored_rules,
    }


def rule_mask(
    frame: pd.DataFrame,
    rule: Mapping[str, Any],
) -> pd.Series:
    column = _required_string(rule, "column")
    direction = _required_string(rule, "direction")
    threshold = float(rule["threshold"])
    values = pd.to_numeric(frame[column], errors="raise")

    if direction == LE:
        return values.notna() & (values <= threshold)
    if direction == GE:
        return values.notna() & (values >= threshold)
    raise ValueError(f"unsupported direction: {direction}")


def _with_coincident_thresholds(
    rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    group_counts: dict[tuple[str, str, float], int] = {}
    for rule in rules:
        key = (rule["column"], rule["direction"], rule["threshold"])
        group_counts[key] = group_counts.get(key, 0) + 1

    group_ids: dict[tuple[str, str, float], str] = {}
    for rule in rules:
        key = (rule["column"], rule["direction"], rule["threshold"])
        group_id = group_ids.setdefault(key, f"coincident_{len(group_ids) + 1}")
        rule["coincident_threshold_group"] = group_id
        rule["coincident_threshold_count"] = group_counts[key]

    return rules


def _assign_ranks(scored_rules: list[dict[str, Any]]) -> None:
    eligible = [
        rule
        for rule in scored_rules
        if rule["eligible"] and rule["mean_realized_r"] is not None
    ]
    ranked = sorted(
        eligible,
        key=lambda rule: (-rule["mean_realized_r"], rule["rule_index"]),
    )
    for rank, rule in enumerate(ranked, start=1):
        scored_rules[rule["rule_index"]]["selected_metric_rank"] = rank


def _best_rule(rules: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    if not rules:
        return None
    return sorted(
        rules,
        key=lambda rule: (-rule["mean_realized_r"], rule["rule_index"]),
    )[0]


def _columns_spec(spec: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    columns = spec.get("columns")
    if not isinstance(columns, Sequence) or isinstance(columns, (str, bytes)):
        raise ValueError("columns must be a sequence")
    if not columns:
        raise ValueError("columns must not be empty")
    return columns


def _column_name(column_spec: Mapping[str, Any]) -> str:
    column = column_spec.get("name")
    if not isinstance(column, str) or not column:
        raise ValueError("column name must be a non-empty string")
    return column


def _directions(column_spec: Mapping[str, Any]) -> Sequence[str]:
    directions = column_spec.get("directions")
    if not isinstance(directions, Sequence) or isinstance(directions, (str, bytes)):
        raise ValueError("directions must be a sequence")
    if not directions:
        raise ValueError("directions must not be empty")
    unsupported = [direction for direction in directions if direction not in (LE, GE)]
    if unsupported:
        raise ValueError(f"unsupported directions: {unsupported}")
    return directions


def _quantiles(spec: Mapping[str, Any]) -> Sequence[float]:
    quantiles = spec.get("quantiles")
    if not isinstance(quantiles, Sequence) or isinstance(quantiles, (str, bytes)):
        raise ValueError("quantiles must be a sequence")
    if not quantiles:
        raise ValueError("quantiles must not be empty")

    result = [float(quantile) for quantile in quantiles]
    invalid = [quantile for quantile in result if quantile < 0.0 or quantile > 100.0]
    if invalid:
        raise ValueError(f"quantiles must be between 0 and 100: {invalid}")
    return result


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_int(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _winsorize_fraction(spec: Mapping[str, Any]) -> float:
    value = spec.get("winsorize_fraction")
    if not isinstance(value, (int, float)):
        raise ValueError("winsorize_fraction must be numeric")
    result = float(value)
    if result < 0.0 or result >= 0.5:
        raise ValueError("winsorize_fraction must be >= 0 and < 0.5")
    return result


def _rule_id(
    *,
    column: str,
    direction: str,
    quantile: float,
) -> str:
    direction_label = "le" if direction == LE else "ge"
    return f"{column}__{direction_label}__q{quantile:g}"


def _mean(values: pd.Series) -> float | None:
    if values.empty:
        return None
    return float(values.mean())


def _median(values: pd.Series) -> float | None:
    if values.empty:
        return None
    return float(values.median())


def _winsorized_mean(values: pd.Series, *, fraction: float) -> float | None:
    if values.empty:
        return None
    if fraction == 0.0:
        return float(values.mean())

    lower = values.quantile(fraction)
    upper = values.quantile(1.0 - fraction)
    return float(values.clip(lower=lower, upper=upper).mean())


def _win_rate(values: pd.Series) -> float | None:
    if values.empty:
        return None
    return float((values > 0.0).mean())


def _outlier_divergence(
    *,
    mean_realized_r: float | None,
    median_realized_r: float | None,
) -> bool:
    if mean_realized_r is None or median_realized_r is None:
        return False
    return mean_realized_r > 0.0 and median_realized_r <= 0.0
