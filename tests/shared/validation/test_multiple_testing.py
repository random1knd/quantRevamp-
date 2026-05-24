import pytest

from shared.validation import multiple_testing
from shared.validation.multiple_testing import full_search_permutation_report


def two_rule_frame():
    import pandas as pd

    return pd.DataFrame(
        {
            "A": [1.0, 2.0, 3.0, 4.0],
            "B": [4.0, 3.0, 2.0, 1.0],
            "RealizedR": [2.0, 2.0, -10.0, -10.0],
        }
    )


def two_rule_spec() -> dict:
    return {
        "columns": [
            {"name": "A", "directions": ["<="]},
            {"name": "B", "directions": ["<="]},
        ],
        "quantiles": [50],
        "realized_r_column": "RealizedR",
        "min_kept_count": 1,
        "winsorize_fraction": 0.05,
    }


def test_full_search_permutation_uses_max_eligible_score_not_selected_rule_score():
    report = full_search_permutation_report(
        two_rule_frame(),
        two_rule_spec(),
        n_iter=2,
        random_seed=0,
    )

    assert report["searched_rule_count"] == 2
    assert report["observed_selected_rule"]["rule_id"] == "A__le__q50"
    assert report["observed_selected_mean_realized_r"] == pytest.approx(2.0)
    assert report["permutation_null"][0]["max_eligible_mean_realized_r"] == -4.0
    assert report["permutation_null"][1]["max_eligible_mean_realized_r"] == 2.0
    assert report["permutation_null"][1]["max_rule_id"] == "B__le__q50"
    assert report["adjusted_p_value"] == pytest.approx(2 / 3)


def test_full_search_permutation_is_deterministic_under_seed():
    first = full_search_permutation_report(
        two_rule_frame(),
        two_rule_spec(),
        n_iter=5,
        random_seed=0,
    )
    second = full_search_permutation_report(
        two_rule_frame(),
        two_rule_spec(),
        n_iter=5,
        random_seed=0,
    )

    assert first["permutation_null"] == second["permutation_null"]
    assert first["adjusted_p_value"] == second["adjusted_p_value"]


def test_full_search_permutation_builds_rules_once(monkeypatch):
    calls = 0
    original = multiple_testing.build_threshold_rules

    def counting_build_threshold_rules(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        multiple_testing,
        "build_threshold_rules",
        counting_build_threshold_rules,
    )

    full_search_permutation_report(
        two_rule_frame(),
        two_rule_spec(),
        n_iter=3,
        random_seed=0,
    )

    assert calls == 1


def test_full_search_permutation_returns_no_candidate_without_null_when_best_not_positive():
    import pandas as pd

    frame = pd.DataFrame(
        {
            "A": [1.0, 2.0, 3.0],
            "RealizedR": [-1.0, -0.5, -0.25],
        }
    )
    spec = {
        "columns": [{"name": "A", "directions": ["<="]}],
        "quantiles": [100],
        "realized_r_column": "RealizedR",
        "min_kept_count": 1,
        "winsorize_fraction": 0.05,
    }

    report = full_search_permutation_report(
        frame,
        spec,
        n_iter=2,
        random_seed=0,
    )

    assert report["candidate_status"] == "no_candidate"
    assert report["observed_selected_rule"] is None
    assert report["permutation_null"] == []
    assert report["adjusted_p_value"] is None


def test_full_search_permutation_rejects_non_positive_iteration_count():
    with pytest.raises(ValueError, match="n_iter must be positive"):
        full_search_permutation_report(
            two_rule_frame(),
            two_rule_spec(),
            n_iter=0,
            random_seed=0,
        )
