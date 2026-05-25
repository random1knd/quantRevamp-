from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from shared.validation.realized_r import summarize_realized_r
from shared.validation.threshold_nudge import (
    NUDGE_CSV_FIELDS,
    child_threshold_nudge_report,
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
    JUDGMENT_POPULATION,
    OUTPUT_ROOT,
    judgment_population_trades,
    load_validation_bars,
)


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SLICER_DIR = (
    ROOT
    / "data"
    / "results"
    / "vwap_zscore_fade"
    / "parent"
    / "discovery_20260524T050004Z"
    / "slicer_20260524T061833Z"
)
REPORT_JSON = "threshold_nudge_report.json"
REPORT_CSV = "threshold_nudge_report.csv"
THRESHOLD_QUANTILES = (20.0, 30.0, 40.0)
BASELINE_THRESHOLD_QUANTILE = 30.0
REPORT_LABEL = "coverage_only_validation_child_nudge_no_edge_claim"


def run_threshold_nudge_report(
    *,
    slicer_dir: str | Path = DEFAULT_SLICER_DIR,
    output_dir: str | Path | None = None,
) -> Path:
    source_dir = Path(slicer_dir)
    threshold_rules = _read_adx_threshold_grid(source_dir / "slice_report.csv")
    candidate = _read_json(source_dir / "filter_candidate.json")
    validation_bars, splits = load_validation_bars()

    summaries = []
    for rule in threshold_rules:
        child_trades = generate_child_trades(
            validation_bars,
            exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
            commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
            commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
            adx_filter_threshold=rule["adx_filter_threshold"],
        )
        summaries.append(_threshold_summary(rule=rule, trades=child_trades))

    report = build_threshold_nudge_report(
        threshold_summaries=summaries,
        validation_bars=validation_bars,
        splits=splits,
        source_slicer_dir=source_dir,
        candidate=candidate,
    )
    destination = Path(output_dir) if output_dir is not None else _output_dir()
    destination.mkdir(parents=True, exist_ok=True)
    _write_json(destination / REPORT_JSON, report)
    _write_nudge_csv(destination / REPORT_CSV, report["grid"])
    return destination


def build_threshold_nudge_report(
    *,
    threshold_summaries: Sequence[dict[str, Any]],
    validation_bars: pd.DataFrame,
    splits: dict[str, Any],
    source_slicer_dir: Path,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    report = child_threshold_nudge_report(
        threshold_summaries,
        baseline_threshold_quantile=BASELINE_THRESHOLD_QUANTILE,
    )
    report.update(
        {
            "run_type": "validation_child_threshold_nudge",
            "split": "validation",
            "report_label": REPORT_LABEL,
            "coverage_label": COVERAGE_LABEL,
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
            "source_slicer_dir": str(source_slicer_dir),
            "source_artifacts": {
                "slice_report": str(source_slicer_dir / "slice_report.csv"),
                "filter_candidate": str(source_slicer_dir / "filter_candidate.json"),
            },
            "candidate_status_at_slicer": candidate["candidate_status"],
            "no_candidate_reason_at_slicer": candidate.get("no_candidate_reason"),
            "threshold_usage_note": (
                "Thresholds are literal SignalADX q20/q30/q40 slicer row "
                "values; validation-period quantiles are not recomputed or "
                "used for selection."
            ),
        }
    )
    return report


def _read_adx_threshold_grid(path: Path) -> list[dict[str, Any]]:
    required = set(THRESHOLD_QUANTILES)
    by_quantile: dict[float, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["column"] != "SignalADX" or row["direction"] != "<=":
                continue
            quantile = float(row["threshold_quantile"])
            if quantile not in required:
                continue
            if quantile in by_quantile:
                raise ValueError(f"duplicate SignalADX <= q{quantile:g} slicer row")
            by_quantile[quantile] = {
                "threshold_label": f"q{quantile:g}",
                "threshold_quantile": quantile,
                "adx_filter_threshold": float(row["threshold"]),
                "source_rule_id": row["rule_id"],
            }

    missing = sorted(required - set(by_quantile))
    if missing:
        labels = ", ".join(f"q{quantile:g}" for quantile in missing)
        raise ValueError(f"missing SignalADX <= slicer rows: {labels}")

    baseline = by_quantile[BASELINE_THRESHOLD_QUANTILE]["adx_filter_threshold"]
    if abs(baseline - child_params.ADX_FILTER_THRESHOLD) > 1e-12:
        raise ValueError("q30 slicer threshold does not match frozen child threshold")

    return [by_quantile[quantile] for quantile in THRESHOLD_QUANTILES]


def _threshold_summary(
    *,
    rule: dict[str, Any],
    trades: Sequence[Any],
) -> dict[str, Any]:
    all_completed = [trade for trade in trades if trade.exit_reason != "end_of_data"]
    judged_trades = judgment_population_trades(trades)
    summary = summarize_realized_r(
        [trade.realized_r for trade in judged_trades],
        trade_count=len(trades),
        incomplete_trade_count=len(trades) - len(all_completed),
    )
    return {
        **rule,
        "trade_count": summary["trade_count"],
        "all_completed_trade_count": len(all_completed),
        "completed_non_gap_trade_count": len(judged_trades),
        "incomplete_trade_count": summary["incomplete_trade_count"],
        "excluded_hold_crosses_gap_count": len(all_completed) - len(judged_trades),
        "mean_realized_r": summary["mean_realized_r"],
        "total_realized_r": summary["total_realized_r"],
        "win_rate": summary["win_rate"],
        "max_drawdown_r": summary["max_drawdown_r"],
    }


def _output_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return OUTPUT_ROOT / f"threshold_nudge_{timestamp}"


def _split_summary(splits: dict[str, Any]) -> dict[str, Any]:
    return {
        "discovery_end": splits["discovery_end"].isoformat(),
        "validation_end": splits["validation_end"].isoformat(),
        "test_end": splits["test_end"].isoformat(),
        "discovery_session_count": splits["discovery_session_count"],
        "validation_session_count": splits["validation_session_count"],
        "test_session_count": splits["test_session_count"],
    }


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(_json_value(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_nudge_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=NUDGE_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field: _csv_value(row.get(field)) for field in NUDGE_CSV_FIELDS}
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
    print(run_threshold_nudge_report())
