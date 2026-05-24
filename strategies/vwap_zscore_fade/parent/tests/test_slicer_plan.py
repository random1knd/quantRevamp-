import json
from pathlib import Path

import pandas as pd

from shared.validation.rule_search import build_threshold_rules


PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "campaigns"
    / "vwap_zscore_fade__NQ__5min__2014-11-28_2018-04-17"
    / "slicer_plan.json"
)


def test_frozen_slicer_plan_matches_locked_campaign_contract():
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))

    assert plan["campaign_id"] == "vwap_zscore_fade__NQ__5min__2014-11-28_2018-04-17"
    assert plan["input_population"]["name"] == "completed_non_gap"
    assert plan["expected_searched_rule_count"] == 42
    assert plan["min_kept_count"] == 500
    assert plan["winsorize_fraction"] == 0.05
    assert plan["nan_policy"]["filter_value_nan"] == "excluded_from_kept_subset"
    assert plan["multiple_testing"]["random_seed"] == 0
    assert plan["multiple_testing"]["n_iter"] == 10000
    assert plan["multiple_testing"]["p_value_smoothing"] == "plus_one"

    directions = {column["name"]: column["directions"] for column in plan["columns"]}
    assert directions == {
        "SignalADX": ["<="],
        "SignalEfficiencyRatio": ["<="],
        "SignalVarRatio": ["<="],
        "SignalVPIN": ["<="],
        "SignalRealizedVol": ["<=", ">="],
    }


def test_frozen_slicer_plan_expands_to_expected_rule_count():
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    count = 1000
    frame = pd.DataFrame(
        {
            "SignalADX": range(count),
            "SignalEfficiencyRatio": range(count),
            "SignalVarRatio": range(count),
            "SignalVPIN": range(count),
            "SignalRealizedVol": range(count),
            "RealizedR": [0.0] * count,
        }
    )

    rules = build_threshold_rules(frame, plan)

    assert len(rules) == plan["expected_searched_rule_count"]
    assert sum(1 for rule in rules if rule["direction"] == ">=") == 7
    assert sum(1 for rule in rules if rule["column"] == "SignalRealizedVol") == 14
