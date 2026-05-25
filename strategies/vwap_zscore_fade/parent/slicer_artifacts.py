from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


CANDIDATE_GATE_ADJUSTED_P_VALUE_THRESHOLD = 0.10


def write_slicer_artifacts(
    *,
    output_dir: Path,
    plan: dict[str, Any],
    search_result: dict[str, Any],
    permutation_report: dict[str, Any],
    population_summary: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)

    _write_json(output_dir / "slicer_plan.json", plan)
    _write_slice_report(
        output_dir / "slice_report.csv",
        rules=search_result["rules"],
        fieldnames=plan["required_rule_diagnostics"],
    )
    _write_permutation_null(
        output_dir / "permutation_null.csv",
        permutation_null=permutation_report["permutation_null"],
    )
    _write_json(
        output_dir / "filter_candidate.json",
        _filter_candidate(
            plan=plan,
            search_result=search_result,
            permutation_report=permutation_report,
            population_summary=population_summary,
        ),
    )


def _filter_candidate(
    *,
    plan: dict[str, Any],
    search_result: dict[str, Any],
    permutation_report: dict[str, Any],
    population_summary: dict[str, Any],
) -> dict[str, Any]:
    candidate_gate = _candidate_gate(
        search_result=search_result,
        permutation_report=permutation_report,
        min_kept_count=int(plan["min_kept_count"]),
    )
    candidate_status = candidate_gate["candidate_status"]
    promoted = candidate_status == "candidate_selected"
    artifact_selected_rule = search_result["selected_rule"] if promoted else None
    return {
        "campaign_id": plan["campaign_id"],
        "plan_label": plan["plan_label"],
        "parent_strategy": plan["parent_strategy"],
        "discovery_artifact": plan["discovery_artifact"],
        "slicer_input_population": plan["input_population"]["name"],
        "population_summary": population_summary,
        "searched_rule_count": search_result["searched_rule_count"],
        "eligible_rule_count": search_result["eligible_rule_count"],
        "selection_metric": plan["selection_metric"],
        "min_kept_count": plan["min_kept_count"],
        "candidate_status": candidate_status,
        "promotion_decision": (
            "filter_candidate_promoted"
            if promoted
            else "no_filter_candidate_promoted"
        ),
        "no_candidate_reason": candidate_gate["no_candidate_reason"],
        "candidate_gate": candidate_gate,
        "selected_rule": artifact_selected_rule,
        "best_rule": search_result["best_rule"],
        "multiple_testing": {
            "method": permutation_report["method"],
            "sidedness": permutation_report["sidedness"],
            "random_seed": permutation_report["random_seed"],
            "n_iter": permutation_report["n_iter"],
            "adjusted_p_value": permutation_report["adjusted_p_value"],
            "bonferroni": permutation_report["bonferroni"],
        },
        "outlier_divergence_flag": (
            False
            if artifact_selected_rule is None
            else bool(artifact_selected_rule["outlier_divergence_flag"])
        ),
        "workflow_test_label": (
            "pipeline_test_only_not_a_profit_claim"
            if not promoted
            else "requires_validation_not_a_profit_claim"
        ),
    }


def _candidate_gate(
    *,
    search_result: dict[str, Any],
    permutation_report: dict[str, Any],
    min_kept_count: int,
) -> dict[str, Any]:
    search_selected_rule = search_result["selected_rule"]
    if search_selected_rule is None:
        reason = search_result["no_candidate_reason"] or "no_search_candidate"
        return {
            "method": "slicer_artifact_candidate_gate",
            "candidate_status": "no_candidate",
            "no_candidate_reason": reason,
            "failed_reasons": [reason],
            "adjusted_p_value_threshold": (
                CANDIDATE_GATE_ADJUSTED_P_VALUE_THRESHOLD
            ),
            "search_candidate_status": search_result["candidate_status"],
            "permutation_candidate_status": permutation_report["candidate_status"],
            "requirements": _requirements_for_unselected_search(
                best_rule=search_result["best_rule"],
                min_kept_count=min_kept_count,
            ),
        }

    adjusted_p_value = permutation_report["adjusted_p_value"]
    requirements = {
        "mean_realized_r_positive": {
            "passed": search_selected_rule["mean_realized_r"] > 0.0,
            "observed": search_selected_rule["mean_realized_r"],
            "threshold": 0.0,
        },
        "min_kept_count_met": {
            "passed": search_selected_rule["kept_count"] >= min_kept_count,
            "observed": search_selected_rule["kept_count"],
            "threshold": min_kept_count,
        },
        "adjusted_p_value_lte_0.10": {
            "passed": (
                adjusted_p_value is not None
                and adjusted_p_value <= CANDIDATE_GATE_ADJUSTED_P_VALUE_THRESHOLD
            ),
            "observed": adjusted_p_value,
            "threshold": CANDIDATE_GATE_ADJUSTED_P_VALUE_THRESHOLD,
        },
        "no_outlier_divergence": {
            "passed": not bool(search_selected_rule["outlier_divergence_flag"]),
            "observed": bool(search_selected_rule["outlier_divergence_flag"]),
            "threshold": False,
        },
    }
    failed_reasons = _failed_reasons(requirements)
    candidate_status = "candidate_selected" if not failed_reasons else "no_candidate"
    return {
        "method": "slicer_artifact_candidate_gate",
        "candidate_status": candidate_status,
        "no_candidate_reason": None if not failed_reasons else failed_reasons[0],
        "failed_reasons": failed_reasons,
        "adjusted_p_value_threshold": CANDIDATE_GATE_ADJUSTED_P_VALUE_THRESHOLD,
        "search_candidate_status": search_result["candidate_status"],
        "permutation_candidate_status": permutation_report["candidate_status"],
        "requirements": requirements,
    }


def _requirements_for_unselected_search(
    *,
    best_rule: dict[str, Any] | None,
    min_kept_count: int,
) -> dict[str, Any]:
    mean_realized_r = None if best_rule is None else best_rule["mean_realized_r"]
    kept_count = None if best_rule is None else best_rule["kept_count"]
    outlier_divergence = (
        False if best_rule is None else bool(best_rule["outlier_divergence_flag"])
    )
    return {
        "mean_realized_r_positive": {
            "passed": mean_realized_r is not None and mean_realized_r > 0.0,
            "observed": mean_realized_r,
            "threshold": 0.0,
        },
        "min_kept_count_met": {
            "passed": kept_count is not None and kept_count >= min_kept_count,
            "observed": kept_count,
            "threshold": min_kept_count,
        },
        "adjusted_p_value_lte_0.10": {
            "passed": False,
            "observed": None,
            "threshold": CANDIDATE_GATE_ADJUSTED_P_VALUE_THRESHOLD,
            "not_evaluated_reason": "no_search_candidate",
        },
        "no_outlier_divergence": {
            "passed": not outlier_divergence,
            "observed": outlier_divergence,
            "threshold": False,
        },
    }


def _failed_reasons(requirements: dict[str, dict[str, Any]]) -> list[str]:
    reasons = []
    if not requirements["mean_realized_r_positive"]["passed"]:
        reasons.append("selected_mean_not_positive")
    if not requirements["min_kept_count_met"]["passed"]:
        reasons.append("min_kept_count_not_met")
    if not requirements["adjusted_p_value_lte_0.10"]["passed"]:
        adjusted_p_value = requirements["adjusted_p_value_lte_0.10"]["observed"]
        if adjusted_p_value is None:
            reasons.append("adjusted_p_value_missing")
        else:
            reasons.append("adjusted_p_value_above_threshold")
    if not requirements["no_outlier_divergence"]["passed"]:
        reasons.append("outlier_divergence_flag")
    return reasons


def _write_slice_report(
    path: Path,
    *,
    rules: list[dict[str, Any]],
    fieldnames: list[str],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for rule in rules:
            writer.writerow({field: _csv_value(rule.get(field)) for field in fieldnames})


def _write_permutation_null(
    path: Path,
    *,
    permutation_null: list[dict[str, Any]],
) -> None:
    fieldnames = (
        "iteration",
        "max_eligible_mean_realized_r",
        "max_rule_id",
    )
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in permutation_null:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _write_json(path: Path, content: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(_json_value(content), file, indent=2, sort_keys=True)
        file.write("\n")


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value
