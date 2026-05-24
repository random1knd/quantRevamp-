from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from shared.validation.rule_search import (
    build_threshold_rules,
    score_rules,
)


METHOD = "full_search_permutation_max_stat"
SIDEDNESS = "one_sided_positive"


def full_search_permutation_report(
    frame: pd.DataFrame,
    spec: Mapping[str, Any],
    *,
    n_iter: int,
    random_seed: int,
) -> dict[str, Any]:
    if n_iter <= 0:
        raise ValueError(f"n_iter must be positive, got: {n_iter}")

    realized_r_column = _required_string(spec, "realized_r_column")
    if realized_r_column not in frame.columns:
        raise ValueError(f"missing realized-R column: {realized_r_column}")

    rules = build_threshold_rules(frame, spec)
    observed_rules = score_rules(frame, rules, spec)
    selected_rule = _selected_rule(observed_rules)
    if selected_rule is None:
        return {
            "method": METHOD,
            "sidedness": SIDEDNESS,
            "random_seed": random_seed,
            "n_iter": n_iter,
            "searched_rule_count": len(rules),
            "candidate_status": "no_candidate",
            "observed_selected_rule": None,
            "observed_selected_mean_realized_r": None,
            "permutation_null": [],
            "adjusted_p_value": None,
            "bonferroni": _bonferroni(len(rules), raw_p_value=None),
        }

    observed_score = selected_rule["mean_realized_r"]
    permutation_null = _permutation_null(
        frame,
        rules=rules,
        spec=spec,
        realized_r_column=realized_r_column,
        n_iter=n_iter,
        random_seed=random_seed,
    )
    null_scores = [
        item["max_eligible_mean_realized_r"]
        for item in permutation_null
        if item["max_eligible_mean_realized_r"] is not None
    ]
    null_count_at_or_above = sum(
        1 for score in null_scores if score >= observed_score
    )
    adjusted_p_value = (1 + null_count_at_or_above) / (1 + n_iter)

    return {
        "method": METHOD,
        "sidedness": SIDEDNESS,
        "random_seed": random_seed,
        "n_iter": n_iter,
        "searched_rule_count": len(rules),
        "candidate_status": "candidate_selected",
        "observed_selected_rule": selected_rule,
        "observed_selected_mean_realized_r": observed_score,
        "permutation_null": permutation_null,
        "adjusted_p_value": adjusted_p_value,
        "bonferroni": _bonferroni(len(rules), raw_p_value=None),
    }


def _permutation_null(
    frame: pd.DataFrame,
    *,
    rules: list[dict[str, Any]],
    spec: Mapping[str, Any],
    realized_r_column: str,
    n_iter: int,
    random_seed: int,
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(random_seed)
    realized_values = frame[realized_r_column].to_numpy(copy=True)
    null: list[dict[str, Any]] = []

    for iteration in range(n_iter):
        permuted = frame.copy()
        permuted[realized_r_column] = rng.permutation(realized_values)
        scored_rules = score_rules(permuted, rules, spec)
        max_rule = _max_eligible_rule(scored_rules)
        null.append(
            {
                "iteration": iteration,
                "max_eligible_mean_realized_r": (
                    None if max_rule is None else max_rule["mean_realized_r"]
                ),
                "max_rule_id": None if max_rule is None else max_rule["rule_id"],
            }
        )

    return null


def _selected_rule(scored_rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    best = _max_eligible_rule(scored_rules)
    if best is None or best["mean_realized_r"] <= 0.0:
        return None
    return best


def _max_eligible_rule(scored_rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [
        rule
        for rule in scored_rules
        if rule["eligible"] and rule["mean_realized_r"] is not None
    ]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda rule: (-rule["mean_realized_r"], rule["rule_index"]),
    )[0]


def _bonferroni(
    searched_rule_count: int,
    *,
    raw_p_value: float | None,
) -> dict[str, Any]:
    adjusted_p_value = None
    if raw_p_value is not None:
        adjusted_p_value = min(1.0, raw_p_value * searched_rule_count)
    return {
        "method": "bonferroni",
        "searched_rule_count": searched_rule_count,
        "raw_p_value": raw_p_value,
        "adjusted_p_value": adjusted_p_value,
        "informational_only": True,
    }


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value
