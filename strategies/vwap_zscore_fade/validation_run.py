"""Run parent-vs-child validation without touching final-test rows."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
import subprocess
from typing import Any, Sequence

import pandas as pd

from shared.data.bars import prepare_bars, rth_only_raw_bars
from shared.data.splits import (
    ChronologicalSessionSplits,
    chronological_session_splits,
)
from shared.validation.realized_r import summarize_realized_r
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import (
    params as child_params,
)
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test.strategy import (
    generate_trades as generate_child_trades,
)
from strategies.vwap_zscore_fade.parent import params as parent_params
from strategies.vwap_zscore_fade.parent.strategy import (
    generate_trades as generate_parent_trades,
)
from strategies.vwap_zscore_fade.validation_artifacts import (
    write_validation_artifacts,
)


ROOT = Path(__file__).resolve().parents[2]
INPUT_DATA_PATH = ROOT / "data" / "bars" / "5min" / "NQ_all_5min.csv"
CHILD_ID = "adx_q30_workflow_test"
OUTPUT_ROOT = (
    ROOT
    / "data"
    / "results"
    / parent_params.STRATEGY_NAME
    / "children"
    / CHILD_ID
)

EXCLUDE_ROLL_SESSIONS = True
COMMISSION_PER_ROUND_TURN = 5.16
COMMISSION_IS_SMOKE_TEST = False
RANDOM_SEED = 0
COVERAGE_LABEL = "coverage only / not edge evidence"
FINAL_TEST_STATUS = "not_run"
JUDGMENT_POPULATION = "completed_non_gap"
MIN_CHILD_PARENT_MEAN_DELTA_R = 0.05
POST_HOC_VS_LIVE_NOTE = (
    "The slicer estimate was a post-hoc discovery-subset result for "
    "SignalADX <= q30 with mean RealizedR -0.08195238266039637. This "
    "validation child is a live rerun on later validation sessions, so the "
    "validation result is expected to differ from the post-hoc estimate."
)
DSR_UNAVAILABLE_REASON = (
    "Unavailable: the slicer artifact did not persist a per-rule Sharpe/std "
    "distribution, so Deflated Sharpe Ratio cannot be computed honestly here."
)
FINAL_PROMOTION_STATUS = "not_evaluated_requires_overfitting_cross_instrument_final_test"
RTH_FILTER_NOTE = (
    "Validation uses shared.data.bars.rth_only_raw_bars with the same declared "
    "RTH bounds as discovery before prepare_bars."
)


def run_validation() -> Path:
    validation_bars, splits = load_validation_bars()

    parent_trades = generate_parent_trades(
        validation_bars,
        exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
        commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
    )
    child_trades = generate_child_trades(
        validation_bars,
        exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
        commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
    )

    output_dir = _output_dir()
    report = build_validation_report(
        parent_trades=parent_trades,
        child_trades=child_trades,
        validation_bars=validation_bars,
        splits=splits,
    )
    run_config = build_run_config(
        validation_bars=validation_bars,
        splits=splits,
        output_dir=output_dir,
    )
    write_validation_artifacts(
        output_dir=output_dir,
        parent_trades=parent_trades,
        child_trades=child_trades,
        validation_report=report,
        run_config=run_config,
    )
    return output_dir


def load_validation_bars() -> tuple[pd.DataFrame, ChronologicalSessionSplits]:
    raw_bars = pd.read_csv(INPUT_DATA_PATH)
    raw_bars = rth_only_raw_bars(
        raw_bars,
        source_timezone=parent_params.SOURCE_TIMEZONE,
        strategy_timezone=parent_params.STRATEGY_TIMEZONE,
        session_open=parent_params.SESSION_OPEN,
        rth_start_session_minute=parent_params.RTH_START_SESSION_MINUTE,
        last_rth_bar_open_session_minute=(
            parent_params.LAST_RTH_BAR_OPEN_SESSION_MINUTE
        ),
    )
    prepared = prepare_bars(
        raw_bars,
        source_timezone=parent_params.SOURCE_TIMEZONE,
        strategy_timezone=parent_params.STRATEGY_TIMEZONE,
        session_open=parent_params.SESSION_OPEN,
        expected_bar_interval_minutes=parent_params.BAR_INTERVAL_MINUTES,
    )
    splits = chronological_session_splits(prepared)
    validation_bars = validation_split_bars(prepared, splits=splits)
    return validation_bars, splits


def validation_split_bars(
    prepared_bars: pd.DataFrame,
    *,
    splits: ChronologicalSessionSplits,
) -> pd.DataFrame:
    if "SessionDate_ET" not in prepared_bars.columns:
        raise ValueError("missing required column: SessionDate_ET")

    mask = (
        (prepared_bars["SessionDate_ET"] > splits["discovery_end"])
        & (prepared_bars["SessionDate_ET"] <= splits["validation_end"])
    )
    validation_bars = prepared_bars.loc[mask].copy()
    _validate_validation_does_not_overlap_final_test(
        validation_bars,
        splits=splits,
    )
    return validation_bars


def build_validation_report(
    *,
    parent_trades: Sequence[Any],
    child_trades: Sequence[Any],
    validation_bars: pd.DataFrame,
    splits: ChronologicalSessionSplits,
) -> dict[str, Any]:
    parent_summary = _strategy_summary(parent_trades)
    child_summary = _strategy_summary(child_trades)
    comparison = _comparison(parent_summary=parent_summary, child_summary=child_summary)
    verdict = _verdict(comparison=comparison, child_summary=child_summary)

    return {
        "run_type": "validation",
        "split": "validation",
        "coverage_label": COVERAGE_LABEL,
        "child_workflow_label": child_params.WORKFLOW_TEST_LABEL,
        "strategy_family": parent_params.STRATEGY_NAME,
        "parent_strategy_name": parent_params.STRATEGY_NAME,
        "child_strategy_name": child_params.STRATEGY_NAME,
        "child_id": CHILD_ID,
        "data_start": validation_bars["DateTime_UTC"].min().isoformat(),
        "data_end": validation_bars["DateTime_UTC"].max().isoformat(),
        "session_start": validation_bars["SessionDate_ET"].min().isoformat(),
        "session_end": validation_bars["SessionDate_ET"].max().isoformat(),
        "splits": _split_summary(splits),
        "validation_split_policy": (
            "discovery_end < SessionDate_ET <= validation_end; final-test rows "
            "are not passed to either strategy"
        ),
        "final_test_status": FINAL_TEST_STATUS,
        "parent": parent_summary,
        "child": child_summary,
        "comparison": comparison,
        "verdict": verdict,
        "deflated_sharpe_ratio": {
            "status": "unavailable",
            "reason": DSR_UNAVAILABLE_REASON,
        },
        "post_hoc_vs_live_note": POST_HOC_VS_LIVE_NOTE,
    }


def build_run_config(
    *,
    validation_bars: pd.DataFrame,
    splits: ChronologicalSessionSplits,
    output_dir: Path,
) -> dict[str, Any]:
    input_data = _input_data_metadata([INPUT_DATA_PATH])
    return {
        "campaign_id": _campaign_id(validation_bars),
        "run_type": "validation",
        "split": "validation",
        "coverage_label": COVERAGE_LABEL,
        "child_workflow_label": child_params.WORKFLOW_TEST_LABEL,
        "strategy_family": parent_params.STRATEGY_NAME,
        "parent_strategy_name": parent_params.STRATEGY_NAME,
        "child_strategy_name": child_params.STRATEGY_NAME,
        "child_id": CHILD_ID,
        "instrument": parent_params.INSTRUMENT,
        "timeframe": parent_params.TIMEFRAME,
        "data_start": validation_bars["DateTime_UTC"].min().isoformat(),
        "data_end": validation_bars["DateTime_UTC"].max().isoformat(),
        "session_start": validation_bars["SessionDate_ET"].min().isoformat(),
        "session_end": validation_bars["SessionDate_ET"].max().isoformat(),
        "splits": _split_summary(splits),
        "final_test_status": FINAL_TEST_STATUS,
        "output_dir": _repo_key(output_dir),
        "random_seed": RANDOM_SEED,
        "code_version": _code_version(),
        "input_data_sha256": input_data["sha256"],
        "input_data_bytes": input_data["bytes"],
        "input_data_is_repo_relative": input_data["is_repo_relative"],
        "non_reproducible_input_paths": input_data["non_reproducible_paths"],
        "source_timezone": parent_params.SOURCE_TIMEZONE,
        "strategy_timezone": parent_params.STRATEGY_TIMEZONE,
        "declared_session_open": parent_params.SESSION_OPEN,
        "rth_filter_note": RTH_FILTER_NOTE,
        "parameter_snapshot": _parameter_snapshot(),
        "exclude_roll_sessions": EXCLUDE_ROLL_SESSIONS,
        "commission_model": {
            "model": "round_turn_currency",
            "commission_per_round_turn": COMMISSION_PER_ROUND_TURN,
            "commission_is_smoke_test": COMMISSION_IS_SMOKE_TEST,
        },
        "slippage_model": {
            "model": "fixed_ticks_per_side",
            "ticks_per_side": parent_params.SLIPPAGE_TICKS_PER_SIDE,
            "tick_size": parent_params.NQ_TICK_SIZE,
        },
        "point_value": parent_params.NQ_POINT_VALUE,
    }


def _validate_validation_does_not_overlap_final_test(
    validation_bars: pd.DataFrame,
    *,
    splits: ChronologicalSessionSplits,
) -> None:
    if validation_bars.empty:
        raise RuntimeError("validation slice is empty - aborting")

    min_session = validation_bars["SessionDate_ET"].min()
    max_session = validation_bars["SessionDate_ET"].max()
    if min_session <= splits["discovery_end"]:
        raise RuntimeError("validation slice overlaps discovery split - aborting")
    if max_session > splits["validation_end"]:
        raise RuntimeError("validation slice overlaps final-test split - aborting")


def _strategy_summary(trades: Sequence[Any]) -> dict[str, object]:
    completed = [trade for trade in trades if trade.exit_reason != "end_of_data"]
    completed_non_gap = judgment_population_trades(trades)
    incomplete_count = len(trades) - len(completed)
    summary = summarize_realized_r(
        [trade.realized_r for trade in completed_non_gap],
        trade_count=len(trades),
        incomplete_trade_count=incomplete_count,
    )
    summary["judgment_population"] = JUDGMENT_POPULATION
    summary["all_completed_trade_count"] = len(completed)
    summary["excluded_hold_crosses_gap_count"] = (
        len(completed) - len(completed_non_gap)
    )
    return summary


def judgment_population_trades(trades: Sequence[Any]) -> list[Any]:
    completed = [trade for trade in trades if trade.exit_reason != "end_of_data"]
    return [trade for trade in completed if not trade.hold_crosses_gap]


def _comparison(
    *,
    parent_summary: dict[str, object],
    child_summary: dict[str, object],
) -> dict[str, object]:
    parent_mean = parent_summary["mean_realized_r"]
    child_mean = child_summary["mean_realized_r"]
    if parent_mean is None or child_mean is None:
        child_minus_parent = None
        child_beats_parent = False
    else:
        child_minus_parent = float(child_mean) - float(parent_mean)
        child_beats_parent = child_minus_parent > 0.0

    return {
        "child_minus_parent_mean_realized_r": child_minus_parent,
        "child_beats_parent": child_beats_parent,
        "parent_comparison_status": "pass" if child_beats_parent else "fail",
    }


def _verdict(
    *,
    comparison: dict[str, object],
    child_summary: dict[str, object],
) -> dict[str, object]:
    child_mean = child_summary["mean_realized_r"]
    minimum_trade_count_tier = child_summary["minimum_trade_count_tier"]
    standalone_credible = (
        minimum_trade_count_tier == "normal_ge_100"
        and child_mean is not None
        and float(child_mean) > 0.0
    )
    child_beats_parent = bool(comparison["child_beats_parent"])
    child_minus_parent = comparison["child_minus_parent_mean_realized_r"]
    effect_size_ok = (
        child_minus_parent is not None
        and float(child_minus_parent) >= MIN_CHILD_PARENT_MEAN_DELTA_R
    )
    advance_to_overfitting = standalone_credible and child_beats_parent and effect_size_ok

    reasons = []
    if minimum_trade_count_tier != "normal_ge_100":
        reasons.append("child_completed_trade_count_below_100_normal_tier")
    if child_mean is None:
        reasons.append("child_has_no_completed_validation_trades")
    elif float(child_mean) <= 0.0:
        reasons.append("child_mean_realized_r_not_positive")
    if not child_beats_parent:
        reasons.append("child_did_not_beat_parent_mean_realized_r")
    if not effect_size_ok:
        reasons.append("child_minus_parent_mean_realized_r_below_0.05R")

    return {
        "decision": (
            "advance_to_overfitting_review" if advance_to_overfitting else "reject"
        ),
        "preliminary_validation_status": (
            "pass" if advance_to_overfitting else "fail"
        ),
        "final_promotion_status": FINAL_PROMOTION_STATUS,
        "minimum_child_parent_mean_delta_r": MIN_CHILD_PARENT_MEAN_DELTA_R,
        "standalone_child_credibility_status": (
            "pass" if standalone_credible else "fail"
        ),
        "parent_comparison_status": comparison["parent_comparison_status"],
        "reasons": reasons,
    }


def _split_summary(splits: ChronologicalSessionSplits) -> dict[str, Any]:
    return {
        "discovery_end": splits["discovery_end"].isoformat(),
        "validation_end": splits["validation_end"].isoformat(),
        "test_end": splits["test_end"].isoformat(),
        "discovery_session_count": splits["discovery_session_count"],
        "validation_session_count": splits["validation_session_count"],
        "test_session_count": splits["test_session_count"],
    }


def _parameter_snapshot() -> dict[str, Any]:
    return {
        "parent": {
            "entry_z_threshold": parent_params.ENTRY_Z_THRESHOLD,
            "z_window": parent_params.Z_WINDOW,
            "signal_min_bars": parent_params.SIGNAL_MIN_BARS,
            "atr_window": parent_params.ATR_WINDOW,
            "stop_atr_multiple": parent_params.STOP_ATR_MULTIPLE,
            "time_stop_minutes": parent_params.TIME_STOP_MINUTES,
            "no_entry_before_session_minute": (
                parent_params.NO_ENTRY_BEFORE_SESSION_MINUTE
            ),
            "no_entry_at_or_after_session_minute": (
                parent_params.NO_ENTRY_AT_OR_AFTER_SESSION_MINUTE
            ),
            "rth_start_session_minute": parent_params.RTH_START_SESSION_MINUTE,
            "last_rth_bar_open_session_minute": (
                parent_params.LAST_RTH_BAR_OPEN_SESSION_MINUTE
            ),
            "session_force_flat_minute": parent_params.SESSION_FORCE_FLAT_MINUTE,
        },
        "child": {
            "adx_filter_threshold": child_params.ADX_FILTER_THRESHOLD,
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
        },
    }


def _output_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return OUTPUT_ROOT / f"validation_{timestamp}"


def _campaign_id(validation_bars: pd.DataFrame) -> str:
    validation_start = validation_bars["SessionDate_ET"].min().isoformat()
    validation_end = validation_bars["SessionDate_ET"].max().isoformat()
    return (
        f"{parent_params.STRATEGY_NAME}__{CHILD_ID}__{parent_params.INSTRUMENT}"
        f"__{parent_params.TIMEFRAME}__validation__{validation_start}_{validation_end}"
    )


def _input_data_metadata(paths: Sequence[str | Path]) -> dict[str, Any]:
    sha256: dict[str, str] = {}
    byte_counts: dict[str, int] = {}
    is_repo_relative = True
    non_reproducible_paths: list[str] = []

    for path_value in paths:
        path = Path(path_value).resolve()
        key = _repo_key(path)
        repo_relative = not Path(key).is_absolute()
        is_repo_relative = is_repo_relative and repo_relative
        if not repo_relative:
            non_reproducible_paths.append(key)
        sha256[key] = _sha256(path)
        byte_counts[key] = path.stat().st_size

    return {
        "sha256": sha256,
        "bytes": byte_counts,
        "is_repo_relative": is_repo_relative,
        "non_reproducible_paths": non_reproducible_paths,
    }


def _repo_key(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_version() -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"

    version = commit.stdout.strip()
    if status.stdout.strip():
        version = f"{version}-dirty"
    return version


if __name__ == "__main__":
    print(run_validation())
