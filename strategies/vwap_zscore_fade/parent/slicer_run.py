from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from shared.validation.multiple_testing import full_search_permutation_report
from shared.validation.rule_search import run_rule_search
from strategies.vwap_zscore_fade.parent.slicer_artifacts import write_slicer_artifacts


ROOT = Path(__file__).resolve().parents[3]
CAMPAIGN_ID = "vwap_zscore_fade__NQ__5min__2014-11-28_2018-04-17"
DEFAULT_PLAN_PATH = (
    Path(__file__).resolve().parent
    / "campaigns"
    / CAMPAIGN_ID
    / "slicer_plan.json"
)


def run_slicer(
    *,
    plan_path: str | Path = DEFAULT_PLAN_PATH,
    output_dir: str | Path | None = None,
) -> Path:
    plan = load_slicer_plan(plan_path)
    context_trades = pd.read_csv(_repo_path(plan["context_trades_path"]))
    population = completed_non_gap_population(context_trades, plan=plan)
    search_result = run_rule_search(population, plan)
    permutation_report = full_search_permutation_report(
        population,
        plan,
        n_iter=int(plan["multiple_testing"]["n_iter"]),
        random_seed=int(plan["multiple_testing"]["random_seed"]),
    )
    destination = (
        Path(output_dir)
        if output_dir is not None
        else _default_output_dir(plan["discovery_artifact"])
    )
    write_slicer_artifacts(
        output_dir=destination,
        plan=plan,
        search_result=search_result,
        permutation_report=permutation_report,
        population_summary=_population_summary(
            input_rows=len(context_trades),
            population_rows=len(population),
            plan=plan,
        ),
    )
    return destination


def load_slicer_plan(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def completed_non_gap_population(
    context_trades: pd.DataFrame,
    *,
    plan: dict[str, Any],
) -> pd.DataFrame:
    population = plan["input_population"]
    exit_reason_column = population["exit_reason_column"]
    hold_crosses_gap_column = population["hold_crosses_gap_column"]
    missing = [
        column
        for column in (exit_reason_column, hold_crosses_gap_column)
        if column not in context_trades.columns
    ]
    if missing:
        raise ValueError(f"missing population columns: {missing}")

    completed = context_trades[exit_reason_column] != population["excluded_exit_reason"]
    non_gap = _false_values(context_trades[hold_crosses_gap_column])
    return context_trades.loc[completed & non_gap].copy()


def _false_values(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values == False

    normalized = values.astype("string").str.strip().str.lower()
    return normalized.isin(("false", "0"))


def _population_summary(
    *,
    input_rows: int,
    population_rows: int,
    plan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "input_rows": input_rows,
        "population_rows": population_rows,
        "population_name": plan["input_population"]["name"],
    }


def _repo_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT / path


def _default_output_dir(discovery_artifact: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return _repo_path(discovery_artifact) / f"slicer_{timestamp}"


if __name__ == "__main__":
    print(run_slicer())
