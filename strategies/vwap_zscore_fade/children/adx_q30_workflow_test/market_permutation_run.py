from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from shared.data.provenance import code_version, input_data_metadata, repo_key
from shared.validation.market_permutation import (
    FIXED_SKELETON_COLUMNS,
    MARKET_PERMUTATION_CSV_FIELDS,
    MARKET_VALUE_COLUMNS,
    METHOD,
    SIDEDNESS,
    STATISTIC,
    market_permutation_report,
    permute_market_bars,
)
from shared.validation.realized_r import summarize_realized_r
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import (
    params as child_params,
)
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test.strategy import (
    generate_trades as generate_child_trades,
)
from strategies.vwap_zscore_fade.validation_run import (
    CHILD_ID,
    COMMISSION_IS_SMOKE_TEST,
    COMMISSION_PER_ROUND_TURN,
    COVERAGE_LABEL,
    EXCLUDE_ROLL_SESSIONS,
    FINAL_TEST_STATUS,
    INPUT_DATA_PATH,
    JUDGMENT_POPULATION,
    OUTPUT_ROOT,
    judgment_population_trades,
    load_validation_bars,
)


ROOT = Path(__file__).resolve().parents[4]
N_ITER = 10
RANDOM_SEED = 0
REPORT_JSON = "market_permutation_report.json"
REPORT_CSV = "market_permutation_report.csv"
RUN_CONFIG_JSON = "run_config.json"
REPORT_LABEL = "coverage_only_validation_child_market_permutation_no_edge_claim"


def run_market_permutation_report(
    *,
    output_dir: str | Path | None = None,
    n_iter: int = N_ITER,
    random_seed: int = RANDOM_SEED,
) -> Path:
    validation_bars, splits = load_validation_bars()

    observed_trades = generate_child_trades(
        validation_bars,
        exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
        commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
    )
    observed_summary = _strategy_summary(observed_trades)

    permutation_summaries = []
    for iteration, iteration_seed in enumerate(
        _iteration_seeds(n_iter=n_iter, random_seed=random_seed),
        start=1,
    ):
        permuted_bars = permute_market_bars(
            validation_bars,
            random_seed=iteration_seed,
            expected_bar_interval_minutes=child_params.BAR_INTERVAL_MINUTES,
        )
        child_trades = generate_child_trades(
            permuted_bars,
            exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
            commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
            commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
        )
        permutation_summaries.append(
            {
                "iteration": iteration,
                "random_seed": iteration_seed,
                **_strategy_summary(child_trades),
            }
        )

    report = build_market_permutation_report(
        observed_summary=observed_summary,
        permutation_summaries=permutation_summaries,
        validation_bars=validation_bars,
        splits=splits,
        n_iter=n_iter,
        random_seed=random_seed,
    )
    destination = Path(output_dir) if output_dir is not None else _output_dir()
    destination.mkdir(parents=True, exist_ok=True)
    run_config = build_run_config(
        validation_bars=validation_bars,
        splits=splits,
        output_dir=destination,
        n_iter=n_iter,
        random_seed=random_seed,
    )
    _write_json(destination / REPORT_JSON, report)
    _write_market_permutation_csv(destination / REPORT_CSV, report["permutations"])
    _write_json(destination / RUN_CONFIG_JSON, run_config)
    return destination


def build_market_permutation_report(
    *,
    observed_summary: dict[str, Any],
    permutation_summaries: Sequence[dict[str, Any]],
    validation_bars: pd.DataFrame,
    splits: dict[str, Any],
    n_iter: int,
    random_seed: int,
) -> dict[str, Any]:
    observed_mean = observed_summary.get("mean_realized_r")
    if observed_mean is None:
        raise ValueError("observed mean_realized_r is required")

    report = market_permutation_report(
        float(observed_mean),
        permutation_summaries,
        n_iter=n_iter,
        random_seed=random_seed,
    )
    report.update(
        {
            "run_type": "validation_child_market_data_permutation",
            "split": "validation",
            "report_label": REPORT_LABEL,
            "coverage_label": COVERAGE_LABEL,
            "coverage_flags": [
                "coverage_only",
                "cannot_validate_edge",
                "workflow_test_child",
            ],
            "child_workflow_label": child_params.WORKFLOW_TEST_LABEL,
            "child_strategy_name": child_params.STRATEGY_NAME,
            "child_id": CHILD_ID,
            "judgment_population": JUDGMENT_POPULATION,
            "final_test_status": FINAL_TEST_STATUS,
            "data_start": validation_bars["DateTime_UTC"].min().isoformat(),
            "data_end": validation_bars["DateTime_UTC"].max().isoformat(),
            "session_start": validation_bars["SessionDate_ET"].min().isoformat(),
            "session_end": validation_bars["SessionDate_ET"].max().isoformat(),
            "splits": _split_summary(splits),
            "observed": observed_summary,
            "permutation_spec": _permutation_spec(
                n_iter=n_iter,
                random_seed=random_seed,
            ),
            "interpretation": (
                "Coverage-only diagnostic for a negative workflow-test child. "
                "For VWAP-fade mean reversion, the single-bar within-session "
                "shuffle manufactures regression-to-the-mean toward the "
                "session center/VWAP and removes adverse momentum after "
                "extreme deviations, so it is not a valid edge-validating "
                "null for this strategy family."
            ),
        }
    )
    return report


def build_run_config(
    *,
    validation_bars: pd.DataFrame,
    splits: dict[str, Any],
    output_dir: str | Path,
    n_iter: int,
    random_seed: int,
) -> dict[str, Any]:
    input_data = input_data_metadata([INPUT_DATA_PATH], repo_root=ROOT)
    return {
        "run_type": "validation_child_market_data_permutation",
        "split": "validation",
        "report_label": REPORT_LABEL,
        "coverage_label": COVERAGE_LABEL,
        "child_workflow_label": child_params.WORKFLOW_TEST_LABEL,
        "child_strategy_name": child_params.STRATEGY_NAME,
        "child_id": CHILD_ID,
        "instrument": child_params.INSTRUMENT,
        "timeframe": child_params.TIMEFRAME,
        "output_dir": repo_key(output_dir, repo_root=ROOT),
        "final_test_status": FINAL_TEST_STATUS,
        "data_start": validation_bars["DateTime_UTC"].min().isoformat(),
        "data_end": validation_bars["DateTime_UTC"].max().isoformat(),
        "session_start": validation_bars["SessionDate_ET"].min().isoformat(),
        "session_end": validation_bars["SessionDate_ET"].max().isoformat(),
        "splits": _split_summary(splits),
        "code_version": code_version(ROOT),
        "input_data_sha256": input_data["sha256"],
        "input_data_bytes": input_data["bytes"],
        "input_data_is_repo_relative": input_data["is_repo_relative"],
        "non_reproducible_input_paths": input_data["non_reproducible_paths"],
        "judgment_population": JUDGMENT_POPULATION,
        "permutation_spec": _permutation_spec(
            n_iter=n_iter,
            random_seed=random_seed,
        ),
        "frozen_child_parameters": _frozen_child_parameters(),
        "exclude_roll_sessions": EXCLUDE_ROLL_SESSIONS,
        "commission_model": {
            "model": "round_turn_currency",
            "commission_per_round_turn": COMMISSION_PER_ROUND_TURN,
            "commission_is_smoke_test": COMMISSION_IS_SMOKE_TEST,
        },
        "slippage_model": {
            "model": "fixed_ticks_per_side",
            "ticks_per_side": child_params.SLIPPAGE_TICKS_PER_SIDE,
            "tick_size": child_params.NQ_TICK_SIZE,
        },
        "point_value": child_params.NQ_POINT_VALUE,
    }


def _strategy_summary(trades: Sequence[Any]) -> dict[str, Any]:
    all_completed = [trade for trade in trades if trade.exit_reason != "end_of_data"]
    judged_trades = judgment_population_trades(trades)
    summary = summarize_realized_r(
        [trade.realized_r for trade in judged_trades],
        trade_count=len(trades),
        incomplete_trade_count=len(trades) - len(all_completed),
    )
    return {
        "judgment_population": JUDGMENT_POPULATION,
        "trade_count": summary["trade_count"],
        "all_completed_trade_count": len(all_completed),
        "completed_non_gap_trade_count": len(judged_trades),
        "incomplete_trade_count": summary["incomplete_trade_count"],
        "excluded_hold_crosses_gap_count": len(all_completed) - len(judged_trades),
        "mean_realized_r": summary["mean_realized_r"],
        "median_realized_r": summary["median_realized_r"],
        "total_realized_r": summary["total_realized_r"],
        "win_rate": summary["win_rate"],
        "max_drawdown_r": summary["max_drawdown_r"],
        "minimum_trade_count_tier": summary["minimum_trade_count_tier"],
        "minimum_trade_count_policy": summary["minimum_trade_count_policy"],
    }


def _iteration_seeds(*, n_iter: int, random_seed: int) -> list[int]:
    if n_iter <= 0:
        raise ValueError("n_iter must be positive")
    if random_seed < 0:
        raise ValueError("random_seed must be non-negative")
    return [random_seed + offset for offset in range(n_iter)]


def _permutation_spec(*, n_iter: int, random_seed: int) -> dict[str, Any]:
    return {
        "method": METHOD,
        "statistic": STATISTIC,
        "n_iter": n_iter,
        "random_seed": random_seed,
        "iteration_seed_policy": "random_seed + iteration_index_zero_based",
        "iteration_seeds": _iteration_seeds(n_iter=n_iter, random_seed=random_seed),
        "permutation_unit": "within_session_single_bar",
        "market_value_columns": list(MARKET_VALUE_COLUMNS),
        "fixed_skeleton_columns": list(FIXED_SKELETON_COLUMNS),
        "session_column": "SessionDate_ET",
        "derived_gap_handling": (
            "BarGapMinutesFromPrevious and BarGapFromPrevious are recomputed "
            "from the preserved DateTime_ET and SessionDate_ET skeleton after "
            "the market-value tuple shuffle."
        ),
        "p_value": {
            "sidedness": SIDEDNESS,
            "formula": (
                "(1 + count(permuted_mean_R >= observed_mean_R)) / "
                "(1 + n_iter)"
            ),
        },
        "future_block_permutation_status": "deferred",
        "mean_reversion_null_warning": (
            "Single-bar shuffling is disqualified as an edge-validating null "
            "for VWAP-fade mean-reversion candidates because it manufactures "
            "regression-to-the-mean and removes adverse momentum."
        ),
        "positive_candidate_requirement": (
            "A real positive mean-reversion candidate requires a predeclared "
            "structure-preserving within-session block permutation with block "
            "length and sampling frozen before results are inspected."
        ),
    }


def _frozen_child_parameters() -> dict[str, Any]:
    return {
        "adx_filter_threshold": child_params.ADX_FILTER_THRESHOLD,
        "adx_window": child_params.ADX_WINDOW,
        "entry_z_threshold": child_params.ENTRY_Z_THRESHOLD,
        "z_window": child_params.Z_WINDOW,
        "signal_min_bars": child_params.SIGNAL_MIN_BARS,
        "atr_window": child_params.ATR_WINDOW,
        "stop_atr_multiple": child_params.STOP_ATR_MULTIPLE,
        "time_stop_minutes": child_params.TIME_STOP_MINUTES,
        "no_entry_before_session_minute": (
            child_params.NO_ENTRY_BEFORE_SESSION_MINUTE
        ),
        "no_entry_at_or_after_session_minute": (
            child_params.NO_ENTRY_AT_OR_AFTER_SESSION_MINUTE
        ),
        "rth_start_session_minute": child_params.RTH_START_SESSION_MINUTE,
        "last_rth_bar_open_session_minute": (
            child_params.LAST_RTH_BAR_OPEN_SESSION_MINUTE
        ),
        "session_force_flat_minute": child_params.SESSION_FORCE_FLAT_MINUTE,
    }


def _output_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return OUTPUT_ROOT / f"market_permutation_{timestamp}"


def _split_summary(splits: dict[str, Any]) -> dict[str, Any]:
    return {
        "discovery_end": splits["discovery_end"].isoformat(),
        "validation_end": splits["validation_end"].isoformat(),
        "test_end": splits["test_end"].isoformat(),
        "discovery_session_count": splits["discovery_session_count"],
        "validation_session_count": splits["validation_session_count"],
        "test_session_count": splits["test_session_count"],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(_json_value(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_market_permutation_csv(
    path: Path,
    rows: Sequence[dict[str, Any]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=MARKET_PERMUTATION_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: _csv_value(row.get(field))
                    for field in MARKET_PERMUTATION_CSV_FIELDS
                }
            )


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if hasattr(value, "item"):
        return _json_value(value.item())
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    return value


if __name__ == "__main__":
    print(run_market_permutation_report())
