import pytest

from shared.validation.threshold_neighborhood import threshold_neighborhood_report


def make_rule(
    *,
    rule_id: str,
    rule_index: int,
    column: str = "SignalADX",
    direction: str = "<=",
    quantile: float,
    kept_count: int = 100,
    mean_realized_r,
    median_realized_r=0.1,
    winsorized_mean_realized_r=0.1,
    win_rate=0.55,
    max_drawdown_r=2.0,
    rank: int = 1,
    eligible=True,
    outlier=False,
) -> dict:
    return {
        "rule_id": rule_id,
        "rule_index": rule_index,
        "column": column,
        "direction": direction,
        "threshold_quantile": quantile,
        "threshold": quantile * 10.0,
        "kept_count": kept_count,
        "eligible": eligible,
        "mean_realized_r": mean_realized_r,
        "median_realized_r": median_realized_r,
        "winsorized_mean_realized_r": winsorized_mean_realized_r,
        "win_rate": win_rate,
        "max_drawdown_r": max_drawdown_r,
        "selected_metric_rank": rank,
        "outlier_divergence_flag": outlier,
    }


def test_threshold_neighborhood_reports_same_column_direction_neighbors():
    anchor = make_rule(
        rule_id="SignalADX__le__q30",
        rule_index=1,
        quantile=30,
        mean_realized_r=1.0,
        rank=1,
    )
    rows = [
        make_rule(
            rule_id="SignalADX__le__q20",
            rule_index=0,
            quantile=20,
            mean_realized_r=0.2,
            rank=3,
        ),
        anchor,
        make_rule(
            rule_id="SignalADX__le__q40",
            rule_index=2,
            quantile=40,
            mean_realized_r=0.55,
            rank=2,
        ),
        make_rule(
            rule_id="SignalADX__le__q50",
            rule_index=3,
            quantile=50,
            mean_realized_r=0.1,
            rank=4,
        ),
        make_rule(
            rule_id="SignalVPIN__le__q30",
            rule_index=4,
            column="SignalVPIN",
            quantile=30,
            mean_realized_r=5.0,
        ),
    ]

    report = threshold_neighborhood_report(
        rows,
        anchor,
        anchor_rule_role="selected_rule",
    )

    assert report["edge_validation_status"] == "cannot_validate_edge"
    assert report["same_column_direction_rule_count"] == 4
    assert report["neighbor_count"] == 3
    assert report["immediate_neighbor_count"] == 2
    assert report["spike_policy"]["policy_status"] == "pass"
    assert report["spike_policy"]["isolated_spike_flag"] is False

    immediate = [
        neighbor for neighbor in report["neighbors"] if neighbor["is_immediate_neighbor"]
    ]
    assert [neighbor["neighbor_rule_id"] for neighbor in immediate] == [
        "SignalADX__le__q20",
        "SignalADX__le__q40",
    ]
    assert immediate[0]["passes_spike_policy"] is False
    assert immediate[1]["passes_spike_policy"] is True
    assert immediate[1]["delta_mean_realized_r"] == pytest.approx(-0.45)
    assert immediate[1]["mean_fraction_of_anchor"] == pytest.approx(0.55)


def test_threshold_neighborhood_flags_two_sided_isolated_spike():
    anchor = make_rule(
        rule_id="SignalADX__le__q30",
        rule_index=1,
        quantile=30,
        mean_realized_r=1.0,
    )
    rows = [
        make_rule(
            rule_id="SignalADX__le__q20",
            rule_index=0,
            quantile=20,
            mean_realized_r=0.49,
        ),
        anchor,
        make_rule(
            rule_id="SignalADX__le__q40",
            rule_index=2,
            quantile=40,
            mean_realized_r=-0.1,
        ),
    ]

    report = threshold_neighborhood_report(
        rows,
        anchor,
        anchor_rule_role="selected_rule",
    )

    assert report["spike_policy"]["policy_status"] == "fail_isolated_spike"
    assert report["spike_policy"]["passing_immediate_neighbor_count"] == 0
    assert report["spike_policy"]["isolated_spike_flag"] is True


def test_threshold_neighborhood_policy_not_applicable_for_negative_best_rule():
    anchor = make_rule(
        rule_id="SignalADX__le__q30",
        rule_index=1,
        quantile=30,
        mean_realized_r=-0.08,
    )
    rows = [
        make_rule(
            rule_id="SignalADX__le__q20",
            rule_index=0,
            quantile=20,
            mean_realized_r=-0.09,
        ),
        anchor,
        make_rule(
            rule_id="SignalADX__le__q40",
            rule_index=2,
            quantile=40,
            mean_realized_r=-0.11,
        ),
    ]

    report = threshold_neighborhood_report(
        rows,
        anchor,
        anchor_rule_role="best_rule",
    )

    assert report["spike_policy"]["policy_status"] == "not_applicable"
    assert (
        report["spike_policy"]["applicability"]
        == "not_applicable_anchor_mean_not_positive"
    )
    assert report["spike_policy"]["isolated_spike_flag"] is False


def test_threshold_neighborhood_accepts_csv_string_values():
    anchor = make_rule(
        rule_id="SignalADX__le__q30",
        rule_index=1,
        quantile=30,
        mean_realized_r=1.0,
    )
    rows = [
        {
            key: str(value)
            for key, value in make_rule(
                rule_id="SignalADX__le__q20",
                rule_index=0,
                quantile=20,
                mean_realized_r=0.5,
            ).items()
        },
        {key: str(value) for key, value in anchor.items()},
    ]

    report = threshold_neighborhood_report(
        rows,
        anchor,
        anchor_rule_role="selected_rule",
    )

    assert report["anchor_rule"]["threshold_quantile"] == 30.0
    assert report["neighbors"][0]["eligible"] is True
    assert report["neighbors"][0]["mean_realized_r"] == pytest.approx(0.5)


def test_threshold_neighborhood_rejects_anchor_not_in_rows():
    with pytest.raises(ValueError, match="anchor_rule must match one scored rule"):
        threshold_neighborhood_report(
            [
                make_rule(
                    rule_id="SignalADX__le__q20",
                    rule_index=0,
                    quantile=20,
                    mean_realized_r=0.5,
                )
            ],
            make_rule(
                rule_id="SignalADX__le__q30",
                rule_index=1,
                quantile=30,
                mean_realized_r=1.0,
            ),
            anchor_rule_role="selected_rule",
        )
