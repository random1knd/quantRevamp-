import pandas as pd
import pytest

from shared.validation.rule_search import (
    build_threshold_rules,
    rule_mask,
    run_rule_search,
    score_rules,
)


def converged_spec(*, min_kept_count: int = 500) -> dict:
    return {
        "columns": [
            {"name": "SignalADX", "directions": ["<="]},
            {"name": "SignalEfficiencyRatio", "directions": ["<="]},
            {"name": "SignalVarRatio", "directions": ["<="]},
            {"name": "SignalVPIN", "directions": ["<="]},
            {"name": "SignalRealizedVol", "directions": ["<=", ">="]},
        ],
        "quantiles": [20, 30, 40, 50, 60, 70, 80],
        "realized_r_column": "RealizedR",
        "min_kept_count": min_kept_count,
        "winsorize_fraction": 0.05,
    }


def make_converged_frame(count: int = 1000) -> pd.DataFrame:
    values = [float(index) for index in range(count)]
    return pd.DataFrame(
        {
            "SignalADX": values,
            "SignalEfficiencyRatio": [value * 2.0 for value in values],
            "SignalVarRatio": [1000.0 - value for value in values],
            "SignalVPIN": [value % 97 for value in values],
            "SignalRealizedVol": [value / 10.0 for value in values],
            "RealizedR": [1.0 if index % 2 == 0 else -0.5 for index in range(count)],
        }
    )


def test_converged_plan_expands_to_42_concrete_rules():
    rules = build_threshold_rules(make_converged_frame(), converged_spec())

    assert len(rules) == 42
    assert {rule["rule_form"] for rule in rules} == {"single_column_threshold"}
    assert len({rule["rule_id"] for rule in rules}) == 42
    assert sum(1 for rule in rules if rule["column"] == "SignalRealizedVol") == 14
    assert sum(1 for rule in rules if rule["direction"] == ">=") == 7


def test_quantiles_use_non_null_values_and_nan_comparisons_are_false():
    frame = pd.DataFrame(
        {
            "SignalADX": [1.0, None, 3.0, 5.0],
            "RealizedR": [1.0, 10.0, 2.0, -3.0],
        }
    )
    spec = {
        "columns": [{"name": "SignalADX", "directions": ["<="]}],
        "quantiles": [50],
        "realized_r_column": "RealizedR",
        "min_kept_count": 1,
        "winsorize_fraction": 0.05,
    }

    rule = build_threshold_rules(frame, spec)[0]
    mask = rule_mask(frame, rule)
    scored = score_rules(frame, [rule], spec)[0]

    assert rule["threshold"] == 3.0
    assert mask.tolist() == [True, False, True, False]
    assert scored["non_null_count"] == 3
    assert scored["kept_count"] == 2
    assert scored["mean_realized_r"] == pytest.approx(1.5)


def test_greater_equal_mask_keeps_exact_threshold_and_excludes_nan():
    frame = pd.DataFrame(
        {
            "SignalRealizedVol": [1.0, None, 3.0, 5.0],
            "RealizedR": [1.0, 10.0, 2.0, -3.0],
        }
    )
    spec = {
        "columns": [{"name": "SignalRealizedVol", "directions": [">="]}],
        "quantiles": [50],
        "realized_r_column": "RealizedR",
        "min_kept_count": 1,
        "winsorize_fraction": 0.05,
    }

    rule = build_threshold_rules(frame, spec)[0]
    mask = rule_mask(frame, rule)
    scored = score_rules(frame, [rule], spec)[0]

    assert rule["threshold"] == 3.0
    assert mask.tolist() == [False, False, True, True]
    assert scored["kept_count"] == 2
    assert scored["mean_realized_r"] == pytest.approx(-0.5)


def test_eligibility_floor_excludes_rule_but_records_diagnostics():
    frame = pd.DataFrame(
        {
            "SignalADX": [1.0, 2.0, 3.0, 4.0],
            "RealizedR": [1.0, -1.0, 2.0, -2.0],
        }
    )
    spec = {
        "columns": [{"name": "SignalADX", "directions": ["<="]}],
        "quantiles": [50],
        "realized_r_column": "RealizedR",
        "min_kept_count": 3,
        "winsorize_fraction": 0.05,
    }

    result = run_rule_search(frame, spec)
    rule = result["rules"][0]

    assert rule["kept_count"] == 2
    assert rule["eligible"] is False
    assert rule["mean_realized_r"] == pytest.approx(0.0)
    assert result["candidate_status"] == "no_candidate"
    assert result["no_candidate_reason"] == "no_eligible_rules"


def test_no_candidate_when_best_eligible_mean_is_not_positive():
    frame = pd.DataFrame(
        {
            "SignalADX": [1.0, 2.0, 3.0],
            "RealizedR": [-1.0, -0.5, -0.25],
        }
    )
    spec = {
        "columns": [{"name": "SignalADX", "directions": ["<="]}],
        "quantiles": [100],
        "realized_r_column": "RealizedR",
        "min_kept_count": 1,
        "winsorize_fraction": 0.05,
    }

    result = run_rule_search(frame, spec)

    assert result["best_rule"]["mean_realized_r"] == pytest.approx(-0.5833333333)
    assert result["candidate_status"] == "no_candidate"
    assert result["no_candidate_reason"] == "best_mean_not_positive"
    assert result["selected_rule"] is None


def test_selected_rule_uses_median_only_outlier_divergence_flag():
    frame = pd.DataFrame(
        {
            "SignalADX": [1.0, 2.0, 3.0, 4.0, 5.0],
            "RealizedR": [-1.0, -1.0, -1.0, 0.0, 10.0],
        }
    )
    spec = {
        "columns": [{"name": "SignalADX", "directions": ["<="]}],
        "quantiles": [100],
        "realized_r_column": "RealizedR",
        "min_kept_count": 1,
        "winsorize_fraction": 0.05,
    }

    result = run_rule_search(frame, spec)
    selected = result["selected_rule"]

    assert result["candidate_status"] == "candidate_selected"
    assert selected["mean_realized_r"] == pytest.approx(1.4)
    assert selected["median_realized_r"] == pytest.approx(-1.0)
    assert selected["outlier_divergence_flag"] is True
    assert selected["winsorized_mean_realized_r"] is not None


def test_coincident_quantile_thresholds_remain_nominal_rules_with_identical_scores():
    frame = pd.DataFrame(
        {
            "SignalADX": [1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 2.0],
            "RealizedR": [1.0, -0.5, 0.25, 0.5, -1.0, 2.0, 0.0, -0.25],
        }
    )
    spec = {
        "columns": [{"name": "SignalADX", "directions": ["<="]}],
        "quantiles": [20, 30],
        "realized_r_column": "RealizedR",
        "min_kept_count": 1,
        "winsorize_fraction": 0.05,
    }

    result = run_rule_search(frame, spec)
    first, second = result["rules"]

    assert result["searched_rule_count"] == 2
    assert first["threshold"] == second["threshold"] == 1.0
    assert first["coincident_threshold_group"] == second["coincident_threshold_group"]
    assert first["coincident_threshold_count"] == 2
    assert second["coincident_threshold_count"] == 2
    assert first["kept_count"] == second["kept_count"] == 4
    assert first["mean_realized_r"] == second["mean_realized_r"]
    assert result["selected_rule"]["rule_id"] == first["rule_id"]


def test_per_rule_diagnostics_include_win_rate_drawdown_and_rank():
    frame = pd.DataFrame(
        {
            "SignalADX": [1.0, 2.0, 3.0, 4.0],
            "RealizedR": [1.0, -0.5, -1.0, 2.0],
        }
    )
    spec = {
        "columns": [{"name": "SignalADX", "directions": ["<="]}],
        "quantiles": [100],
        "realized_r_column": "RealizedR",
        "min_kept_count": 1,
        "winsorize_fraction": 0.05,
    }

    rule = run_rule_search(frame, spec)["rules"][0]

    assert rule["win_rate"] == pytest.approx(0.5)
    assert rule["max_drawdown_r"] == pytest.approx(1.5)
    assert rule["selected_metric_rank"] == 1
    assert rule["selected"] is True
