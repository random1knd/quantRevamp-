from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from shared.data.provenance import code_version, input_data_metadata, repo_key
from shared.validation.time_stability import (
    GRANULARITIES,
    SPARSE_TRADE_FLOOR,
    TIME_STABILITY_CSV_FIELDS,
    time_stability_report,
)
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
REPORT_JSON = "time_stability_report.json"
REPORT_CSV = "time_stability_report.csv"
RUN_CONFIG_JSON = "run_config.json"
REPORT_LABEL = "coverage_only_validation_child_time_stability_no_edge_claim"


def run_time_stability_report(
    *,
    output_dir: str | Path | None = None,
    sparse_trade_floor: int = SPARSE_TRADE_FLOOR,
) -> Path:
    validation_bars, splits = load_validation_bars()
    child_trades = generate_child_trades(
        validation_bars,
        exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
        commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
    )
    judged_trades = judgment_population_trades(child_trades)
    trade_records = [_trade_record(trade) for trade in judged_trades]

    report = build_time_stability_report(
        trade_records=trade_records,
        child_trades=child_trades,
        judged_trades=judged_trades,
        validation_bars=validation_bars,
        splits=splits,
        sparse_trade_floor=sparse_trade_floor,
    )
    destination = Path(output_dir) if output_dir is not None else _output_dir()
    destination.mkdir(parents=True, exist_ok=True)
    run_config = build_run_config(
        validation_bars=validation_bars,
        splits=splits,
        output_dir=destination,
        sparse_trade_floor=sparse_trade_floor,
    )
    _write_json(destination / REPORT_JSON, report)
    _write_time_stability_csv(destination / REPORT_CSV, report)
    _write_json(destination / RUN_CONFIG_JSON, run_config)
    return destination


def build_time_stability_report(
    *,
    trade_records: Sequence[dict[str, Any]],
    child_trades: Sequence[Any],
    judged_trades: Sequence[Any],
    validation_bars: pd.DataFrame,
    splits: dict[str, Any],
    sparse_trade_floor: int,
) -> dict[str, Any]:
    all_completed = [trade for trade in child_trades if trade.exit_reason != "end_of_data"]
    report = time_stability_report(
        trade_records,
        granularities=GRANULARITIES,
        sparse_trade_floor=sparse_trade_floor,
    )
    report.update(
        {
            "run_type": "validation_child_time_stability",
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
            "trade_population": {
                "trade_count": len(child_trades),
                "all_completed_trade_count": len(all_completed),
                "completed_non_gap_trade_count": len(judged_trades),
                "incomplete_trade_count": len(child_trades) - len(all_completed),
                "excluded_hold_crosses_gap_count": (
                    len(all_completed) - len(judged_trades)
                ),
            },
            "time_stability_spec": _time_stability_spec(
                sparse_trade_floor=sparse_trade_floor,
            ),
            "interpretation": (
                "Coverage-only calendar concentration view of one full "
                "validation child trade generation. Buckets are report-only; "
                "no month, quarter, year, or time-of-year filter may be "
                "selected from this artifact."
            ),
        }
    )
    return report


def build_run_config(
    *,
    validation_bars: pd.DataFrame,
    splits: dict[str, Any],
    output_dir: str | Path,
    sparse_trade_floor: int,
) -> dict[str, Any]:
    input_data = input_data_metadata([INPUT_DATA_PATH], repo_root=ROOT)
    return {
        "run_type": "validation_child_time_stability",
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
        "time_stability_spec": _time_stability_spec(
            sparse_trade_floor=sparse_trade_floor,
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


def _trade_record(trade: Any) -> dict[str, Any]:
    return {
        "entry_time": trade.entry_time,
        "realized_r": trade.realized_r,
    }


def _time_stability_spec(*, sparse_trade_floor: int) -> dict[str, Any]:
    return {
        "judgment_population": JUDGMENT_POPULATION,
        "source_trades": (
            "single full-validation frozen-child generation; no per-period "
            "reruns"
        ),
        "grouping_timestamp": "entry_time",
        "granularities": list(GRANULARITIES),
        "sparse_trade_floor": sparse_trade_floor,
        "bucket_status_rule": (
            "completed_non_gap trade_count below sparse_trade_floor is "
            "insufficient"
        ),
        "concentration_metrics": [
            "sign_counts_across_sufficient_buckets",
            "largest_abs_total_r_bucket_share",
            "leave_one_largest_abs_total_r_out_total_r",
        ],
        "selection_policy": "no_period_selection_allowed",
        "signed_total_ratio_policy": (
            "do not divide by signed total R because totals can be negative "
            "or near zero"
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
    return OUTPUT_ROOT / f"time_stability_{timestamp}"


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


def _write_time_stability_csv(path: Path, report: dict[str, Any]) -> None:
    rows = []
    for granularity in report["granularity_order"]:
        rows.extend(report["granularities"][granularity]["buckets"])

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TIME_STABILITY_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: _csv_value(row.get(field))
                    for field in TIME_STABILITY_CSV_FIELDS
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
    print(run_time_stability_report())
