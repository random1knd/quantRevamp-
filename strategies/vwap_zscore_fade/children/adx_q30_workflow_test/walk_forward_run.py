from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from shared.validation.realized_r import summarize_realized_r
from shared.validation.walk_forward import (
    SPARSE_TRADE_FLOOR,
    WALK_FORWARD_CSV_FIELDS,
    walk_forward_report,
)
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import (
    params as child_params,
)
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test.indicators import (
    add_child_indicators,
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


WALK_FORWARD_WINDOW_COUNT = 8
WINDOW_COUNT_RATIONALE = (
    "Predeclared before running: the validation span is 2018-04-18 through "
    "2023-12-01, and the frozen q30 child has 1810 completed_non_gap "
    "validation trades, so eight whole-session windows should average about "
    "226 completed_non_gap trades per window, well above the 20-trade sparse "
    "floor while still showing multi-period behavior."
)
REPORT_JSON = "walk_forward_report.json"
REPORT_CSV = "walk_forward_report.csv"
REPORT_LABEL = "coverage_only_validation_child_walk_forward_no_edge_claim"


@dataclass(frozen=True)
class _WindowBars:
    window_index: int
    window_count: int
    session_start: Any
    session_end: Any
    session_count: int
    bars: pd.DataFrame


def run_walk_forward_report(
    *,
    output_dir: str | Path | None = None,
) -> Path:
    validation_bars, splits = load_validation_bars()
    windows = _session_windows(
        validation_bars,
        window_count=WALK_FORWARD_WINDOW_COUNT,
    )

    window_summaries = []
    for window in windows:
        child_trades = generate_child_trades(
            window.bars,
            exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
            commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
            commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
        )
        window_summaries.append(
            _window_summary(
                window=window,
                trades=child_trades,
                restrictiveness=_adx_restrictiveness_summary(
                    window.bars,
                    exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
                ),
            )
        )

    report = build_walk_forward_report(
        window_summaries=window_summaries,
        validation_bars=validation_bars,
        splits=splits,
    )
    destination = Path(output_dir) if output_dir is not None else _output_dir()
    destination.mkdir(parents=True, exist_ok=True)
    _write_json(destination / REPORT_JSON, report)
    _write_walk_forward_csv(destination / REPORT_CSV, report["windows"])
    return destination


def build_walk_forward_report(
    *,
    window_summaries: Sequence[dict[str, Any]],
    validation_bars: pd.DataFrame,
    splits: dict[str, Any],
) -> dict[str, Any]:
    report = walk_forward_report(
        window_summaries,
        sparse_trade_floor=SPARSE_TRADE_FLOOR,
    )
    report.update(
        {
            "run_type": "validation_child_walk_forward",
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
            "predeclared_window_count": WALK_FORWARD_WINDOW_COUNT,
            "window_count_rationale": WINDOW_COUNT_RATIONALE,
            "window_split_policy": (
                "contiguous whole SessionDate_ET blocks inside the validation "
                "split; sessions are never cut in half"
            ),
            "frozen_child_thresholds": {
                "adx_filter_threshold": child_params.ADX_FILTER_THRESHOLD,
                "entry_z_threshold": child_params.ENTRY_Z_THRESHOLD,
                "stop_atr_multiple": child_params.STOP_ATR_MULTIPLE,
                "time_stop_minutes": child_params.TIME_STOP_MINUTES,
            },
            "threshold_restrictiveness_definition": (
                "Counts entry-candidate signal bars where z-side exists, "
                "same-session next-bar entry is possible, RTH/warmup and ATR "
                "requirements pass, post-open entry timing passes, and roll "
                "session exclusion would not block; ADX then contributes kept, "
                "rejected, or missing counts."
            ),
        }
    )
    return report


def _session_windows(
    validation_bars: pd.DataFrame,
    *,
    window_count: int,
) -> list[_WindowBars]:
    if window_count <= 0:
        raise ValueError("window_count must be positive")
    if "SessionDate_ET" not in validation_bars.columns:
        raise ValueError("missing required column: SessionDate_ET")

    sessions = list(validation_bars["SessionDate_ET"].drop_duplicates())
    if not sessions:
        raise ValueError("validation_bars must contain at least one session")
    if len(sessions) < window_count:
        raise ValueError("window_count cannot exceed validation session count")

    base_size, remainder = divmod(len(sessions), window_count)
    windows: list[_WindowBars] = []
    cursor = 0
    for offset in range(window_count):
        size = base_size + (1 if offset < remainder else 0)
        window_sessions = sessions[cursor : cursor + size]
        cursor += size
        mask = validation_bars["SessionDate_ET"].isin(window_sessions)
        window_bars = validation_bars.loc[mask].copy()
        windows.append(
            _WindowBars(
                window_index=offset + 1,
                window_count=window_count,
                session_start=window_sessions[0],
                session_end=window_sessions[-1],
                session_count=len(window_sessions),
                bars=window_bars,
            )
        )
    return windows


def _window_summary(
    *,
    window: _WindowBars,
    trades: Sequence[Any],
    restrictiveness: dict[str, int],
) -> dict[str, Any]:
    all_completed = [trade for trade in trades if trade.exit_reason != "end_of_data"]
    judged_trades = judgment_population_trades(trades)
    summary = summarize_realized_r(
        [trade.realized_r for trade in judged_trades],
        trade_count=len(trades),
        incomplete_trade_count=len(trades) - len(all_completed),
    )
    return {
        "window_index": window.window_index,
        "window_count": window.window_count,
        "session_start": window.session_start.isoformat(),
        "session_end": window.session_end.isoformat(),
        "session_count": window.session_count,
        "bar_count": len(window.bars),
        "trade_count": summary["trade_count"],
        "all_completed_trade_count": len(all_completed),
        "completed_non_gap_trade_count": len(judged_trades),
        "incomplete_trade_count": summary["incomplete_trade_count"],
        "excluded_hold_crosses_gap_count": len(all_completed) - len(judged_trades),
        "mean_realized_r": summary["mean_realized_r"],
        "total_realized_r": summary["total_realized_r"],
        "win_rate": summary["win_rate"],
        "max_drawdown_r": summary["max_drawdown_r"],
        **restrictiveness,
    }


def _adx_restrictiveness_summary(
    bars: pd.DataFrame,
    *,
    exclude_roll_sessions: bool,
) -> dict[str, int]:
    prepared = add_child_indicators(bars)
    rth_bar_number = _rth_bar_number(prepared)
    kept = 0
    rejected = 0
    missing = 0

    for signal_pos in range(len(prepared) - 1):
        signal_bar = prepared.iloc[signal_pos]
        entry_bar = prepared.iloc[signal_pos + 1]
        if not _has_entry_side(signal_bar):
            continue
        if signal_bar["SessionDate_ET"] != entry_bar["SessionDate_ET"]:
            continue
        expected_entry_time = signal_bar["DateTime_ET"] + pd.Timedelta(
            minutes=child_params.BAR_INTERVAL_MINUTES,
        )
        if entry_bar["DateTime_ET"] != expected_entry_time:
            continue
        if pd.isna(rth_bar_number.iloc[signal_pos]):
            continue
        if rth_bar_number.iloc[signal_pos] < child_params.SIGNAL_MIN_BARS:
            continue
        if pd.isna(signal_bar["ATR"]) or signal_bar["ATR"] <= 0.0:
            continue
        if not (
            child_params.NO_ENTRY_BEFORE_SESSION_MINUTE
            <= entry_bar["SessionMinute_ET"]
            < child_params.NO_ENTRY_AT_OR_AFTER_SESSION_MINUTE
        ):
            continue
        if exclude_roll_sessions and bool(signal_bar["IsFirstSessionAfterContractChange"]):
            continue

        if pd.isna(signal_bar["ADX"]):
            missing += 1
        elif signal_bar["ADX"] <= child_params.ADX_FILTER_THRESHOLD:
            kept += 1
        else:
            rejected += 1

    return {
        "adx_kept_count": kept,
        "adx_rejected_count": rejected,
        "adx_missing_count": missing,
    }


def _has_entry_side(signal_bar: pd.Series) -> bool:
    entry_z = signal_bar["EntryZ"]
    if pd.isna(entry_z):
        return False
    return (
        entry_z <= -child_params.ENTRY_Z_THRESHOLD
        or entry_z >= child_params.ENTRY_Z_THRESHOLD
    )


def _rth_bar_number(bars: pd.DataFrame) -> pd.Series:
    rth = bars["SessionMinute_ET"].between(
        child_params.RTH_START_SESSION_MINUTE,
        child_params.LAST_RTH_BAR_OPEN_SESSION_MINUTE,
    )
    counts = pd.Series(index=bars.index, dtype="float64")
    counts.loc[rth] = bars.loc[rth].groupby("SessionDate_ET", sort=False).cumcount() + 1
    return counts


def _output_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return OUTPUT_ROOT / f"walk_forward_{timestamp}"


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


def _write_walk_forward_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=WALK_FORWARD_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field: _csv_value(row.get(field)) for field in WALK_FORWARD_CSV_FIELDS}
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
    print(run_walk_forward_report())
