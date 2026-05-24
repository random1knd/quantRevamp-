from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


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
    candidate_status = search_result["candidate_status"]
    promoted = candidate_status == "candidate_selected"
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
        "no_candidate_reason": search_result["no_candidate_reason"],
        "selected_rule": search_result["selected_rule"],
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
            if search_result["selected_rule"] is None
            else bool(search_result["selected_rule"]["outlier_divergence_flag"])
        ),
        "workflow_test_label": (
            "pipeline_test_only_not_a_profit_claim"
            if not promoted
            else "requires_validation_not_a_profit_claim"
        ),
    }


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
