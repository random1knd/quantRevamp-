from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from shared.data.bars import prepare_bars, rth_only_raw_bars
from shared.data.provenance import code_version, input_data_metadata, repo_key
from shared.data.splits import chronological_session_splits
from shared.validation.cross_instrument import (
    CROSS_INSTRUMENT_CSV_FIELDS,
    cross_instrument_report,
)
from shared.validation.realized_r import summarize_realized_r
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
    COVERAGE_LABEL,
    EXCLUDE_ROLL_SESSIONS,
    FINAL_TEST_STATUS,
    INPUT_DATA_PATH,
    JUDGMENT_POPULATION,
    OUTPUT_ROOT,
    judgment_population_trades,
    load_validation_bars,
    validation_split_bars,
)


ROOT = Path(__file__).resolve().parents[4]
REPORT_JSON = "cross_instrument_report.json"
REPORT_CSV = "cross_instrument_report.csv"
RUN_CONFIG_JSON = "run_config.json"
REPORT_LABEL = "coverage_only_validation_child_cross_instrument_no_edge_claim"
COMMISSION_SOURCE = (
    "NinjaTrader futures commission PDF checked 2026-05-28; monthly all-in "
    "per-side convention"
)
CONTRACT_SPEC_SOURCES = {
    "NQ": (
        "https://www.cmegroup.com/markets/equities/nasdaq/"
        "e-mini-nasdaq-100.contractSpecs.html"
    ),
    "ES": (
        "https://www.cmegroup.com/markets/equities/sp/"
        "e-mini-sandp500.contractSpecs.html"
    ),
    "6E": "https://www.cmegroup.com/markets/fx/fx-product-guide.html",
}


@dataclass(frozen=True)
class InstrumentConfig:
    instrument: str
    input_path: Path
    session_model: str
    source_timezone: str
    strategy_timezone: str
    session_open: str
    rth_start_session_minute: int
    last_rth_bar_open_session_minute: int
    session_force_flat_minute: int
    tick_size: float
    point_value: float
    tick_value: float
    slippage_ticks_per_side: float
    commission_per_round_turn: float
    commission_is_smoke_test: bool
    implementation_status: str


INSTRUMENTS = {
    "NQ": InstrumentConfig(
        instrument="NQ",
        input_path=INPUT_DATA_PATH,
        session_model="same_day_rth",
        source_timezone=child_params.SOURCE_TIMEZONE,
        strategy_timezone=child_params.STRATEGY_TIMEZONE,
        session_open=child_params.SESSION_OPEN,
        rth_start_session_minute=child_params.RTH_START_SESSION_MINUTE,
        last_rth_bar_open_session_minute=(
            child_params.LAST_RTH_BAR_OPEN_SESSION_MINUTE
        ),
        session_force_flat_minute=child_params.SESSION_FORCE_FLAT_MINUTE,
        tick_size=child_params.NQ_TICK_SIZE,
        point_value=child_params.NQ_POINT_VALUE,
        tick_value=child_params.NQ_TICK_VALUE,
        slippage_ticks_per_side=child_params.SLIPPAGE_TICKS_PER_SIDE,
        commission_per_round_turn=5.16,
        commission_is_smoke_test=False,
        implementation_status="cycle_b_run",
    ),
    "ES": InstrumentConfig(
        instrument="ES",
        input_path=ROOT / "data" / "bars" / "5min" / "ES_all_5min.csv",
        session_model="same_day_rth",
        source_timezone=child_params.SOURCE_TIMEZONE,
        strategy_timezone=child_params.STRATEGY_TIMEZONE,
        session_open=child_params.SESSION_OPEN,
        rth_start_session_minute=child_params.RTH_START_SESSION_MINUTE,
        last_rth_bar_open_session_minute=(
            child_params.LAST_RTH_BAR_OPEN_SESSION_MINUTE
        ),
        session_force_flat_minute=child_params.SESSION_FORCE_FLAT_MINUTE,
        tick_size=0.25,
        point_value=50.0,
        tick_value=12.50,
        slippage_ticks_per_side=child_params.SLIPPAGE_TICKS_PER_SIDE,
        commission_per_round_turn=5.16,
        commission_is_smoke_test=False,
        implementation_status="cycle_b_run",
    ),
    "6E": InstrumentConfig(
        instrument="6E",
        input_path=ROOT / "data" / "bars" / "5min" / "6E_all_5min.csv",
        session_model="overnight_18et_blocked_until_cycle_c",
        source_timezone=child_params.SOURCE_TIMEZONE,
        strategy_timezone=child_params.STRATEGY_TIMEZONE,
        session_open="18:00",
        rth_start_session_minute=0,
        last_rth_bar_open_session_minute=1375,
        session_force_flat_minute=1380,
        tick_size=0.00005,
        point_value=125000.0,
        tick_value=6.25,
        slippage_ticks_per_side=child_params.SLIPPAGE_TICKS_PER_SIDE,
        commission_per_round_turn=5.60,
        commission_is_smoke_test=False,
        implementation_status="blocked_until_cycle_c_session_model",
    ),
}


def run_cross_instrument_report(
    *,
    output_dir: str | Path | None = None,
) -> Path:
    baseline_bars, baseline_splits = load_validation_bars()
    baseline_trades = generate_child_trades(
        baseline_bars,
        exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        commission_per_round_turn=INSTRUMENTS["NQ"].commission_per_round_turn,
        commission_is_smoke_test=INSTRUMENTS["NQ"].commission_is_smoke_test,
    )

    nq_bars, nq_splits = load_instrument_validation_bars(INSTRUMENTS["NQ"])
    nq_trades = _generate_config_trades(nq_bars, INSTRUMENTS["NQ"])
    nq_proof = _nq_bit_identical_proof(
        baseline_trades=baseline_trades,
        lookup_trades=nq_trades,
        baseline_splits=baseline_splits,
        lookup_splits=nq_splits,
        baseline_bars=baseline_bars,
        lookup_bars=nq_bars,
    )
    if not nq_proof["bit_identical"]:
        raise RuntimeError(f"NQ lookup regression proof failed: {nq_proof}")

    es_bars, es_splits = load_instrument_validation_bars(INSTRUMENTS["ES"])
    es_trades = _generate_config_trades(es_bars, INSTRUMENTS["ES"])

    summaries = [
        _instrument_summary(
            config=INSTRUMENTS["NQ"],
            validation_bars=nq_bars,
            splits=nq_splits,
            trades=nq_trades,
        ),
        _instrument_summary(
            config=INSTRUMENTS["ES"],
            validation_bars=es_bars,
            splits=es_splits,
            trades=es_trades,
        ),
    ]
    report = build_cross_instrument_report(
        instrument_summaries=summaries,
        nq_proof=nq_proof,
    )
    destination = Path(output_dir) if output_dir is not None else _output_dir()
    destination.mkdir(parents=True, exist_ok=True)
    run_config = build_run_config(
        output_dir=destination,
        instrument_summaries=summaries,
        nq_proof=nq_proof,
    )
    _write_json(destination / REPORT_JSON, report)
    _write_cross_instrument_csv(destination / REPORT_CSV, report["instruments"])
    _write_json(destination / RUN_CONFIG_JSON, run_config)
    return destination


def build_cross_instrument_report(
    *,
    instrument_summaries: Sequence[dict[str, Any]],
    nq_proof: dict[str, Any],
) -> dict[str, Any]:
    report = cross_instrument_report(instrument_summaries)
    report.update(
        {
            "run_type": "validation_child_cross_instrument",
            "split": "validation",
            "report_label": REPORT_LABEL,
            "coverage_label": COVERAGE_LABEL,
            "coverage_flags": [
                "coverage_only",
                "blueprint_demonstration",
                "rejected_child_not_edge_evidence",
                "no_instrument_selection_allowed",
            ],
            "child_workflow_label": child_params.WORKFLOW_TEST_LABEL,
            "child_strategy_name": child_params.STRATEGY_NAME,
            "child_id": CHILD_ID,
            "judgment_population": JUDGMENT_POPULATION,
            "final_test_status": FINAL_TEST_STATUS,
            "nq_lookup_regression_proof": nq_proof,
            "instruments_run": ["NQ", "ES"],
            "instruments_not_run": {
                "6E": (
                    "blocked until Cycle C session-date policy and mandatory "
                    "6E sanity checks are implemented"
                )
            },
            "interpretation": (
                "Coverage-only blueprint demonstration on a rejected child. "
                "NQ proves the explicit lookup did not change current behavior; "
                "ES is a same-day RTH constants-swap transfer check. No "
                "instrument may be selected from this report."
            ),
        }
    )
    return report


def build_run_config(
    *,
    output_dir: str | Path,
    instrument_summaries: Sequence[dict[str, Any]],
    nq_proof: dict[str, Any],
) -> dict[str, Any]:
    input_paths = [INSTRUMENTS["NQ"].input_path, INSTRUMENTS["ES"].input_path]
    input_data = input_data_metadata(input_paths, repo_root=ROOT)
    return {
        "run_type": "validation_child_cross_instrument",
        "split": "validation",
        "report_label": REPORT_LABEL,
        "coverage_label": COVERAGE_LABEL,
        "child_workflow_label": child_params.WORKFLOW_TEST_LABEL,
        "child_strategy_name": child_params.STRATEGY_NAME,
        "child_id": CHILD_ID,
        "output_dir": repo_key(output_dir, repo_root=ROOT),
        "final_test_status": FINAL_TEST_STATUS,
        "code_version": code_version(ROOT),
        "input_data_sha256": input_data["sha256"],
        "input_data_bytes": input_data["bytes"],
        "input_data_is_repo_relative": input_data["is_repo_relative"],
        "non_reproducible_input_paths": input_data["non_reproducible_paths"],
        "judgment_population": JUDGMENT_POPULATION,
        "instrument_lookup": {
            key: _config_payload(config) for key, config in INSTRUMENTS.items()
        },
        "instruments_run": ["NQ", "ES"],
        "instruments_not_run": ["6E"],
        "nq_lookup_regression_proof": nq_proof,
        "instrument_splits": {
            summary["instrument"]: summary["splits"]
            for summary in instrument_summaries
        },
        "frozen_child_parameters": _frozen_child_parameters(),
        "commission_source": COMMISSION_SOURCE,
        "contract_spec_sources": CONTRACT_SPEC_SOURCES,
    }


def load_instrument_validation_bars(
    config: InstrumentConfig,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if config.session_model != "same_day_rth":
        raise RuntimeError(
            f"{config.instrument} session model is not implemented in Cycle B"
        )
    raw_bars = pd.read_csv(config.input_path)
    raw_bars = rth_only_raw_bars(
        raw_bars,
        source_timezone=config.source_timezone,
        strategy_timezone=config.strategy_timezone,
        session_open=config.session_open,
        rth_start_session_minute=config.rth_start_session_minute,
        last_rth_bar_open_session_minute=config.last_rth_bar_open_session_minute,
    )
    prepared = prepare_bars(
        raw_bars,
        source_timezone=config.source_timezone,
        strategy_timezone=config.strategy_timezone,
        session_open=config.session_open,
        expected_bar_interval_minutes=child_params.BAR_INTERVAL_MINUTES,
    )
    splits = chronological_session_splits(prepared)
    validation_bars = validation_split_bars(prepared, splits=splits)
    return validation_bars, splits


def _generate_config_trades(
    validation_bars: pd.DataFrame,
    config: InstrumentConfig,
) -> list[Any]:
    return generate_child_trades(
        validation_bars,
        exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        commission_per_round_turn=config.commission_per_round_turn,
        commission_is_smoke_test=config.commission_is_smoke_test,
        tick_size=config.tick_size,
        point_value=config.point_value,
        slippage_ticks_per_side=config.slippage_ticks_per_side,
    )


def _instrument_summary(
    *,
    config: InstrumentConfig,
    validation_bars: pd.DataFrame,
    splits: dict[str, Any],
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
        "instrument": config.instrument,
        "input_file": repo_key(config.input_path, repo_root=ROOT),
        "session_model": config.session_model,
        "split": "validation",
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
        **_adx_restrictiveness_summary(
            validation_bars,
            exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        ),
        "accounting_constants": _accounting_payload(config),
        "session_config": _session_payload(config),
        "data_start": validation_bars["DateTime_UTC"].min().isoformat(),
        "data_end": validation_bars["DateTime_UTC"].max().isoformat(),
        "session_start": validation_bars["SessionDate_ET"].min().isoformat(),
        "session_end": validation_bars["SessionDate_ET"].max().isoformat(),
        "splits": _split_summary(splits),
    }


def _nq_bit_identical_proof(
    *,
    baseline_trades: Sequence[Any],
    lookup_trades: Sequence[Any],
    baseline_splits: dict[str, Any],
    lookup_splits: dict[str, Any],
    baseline_bars: pd.DataFrame,
    lookup_bars: pd.DataFrame,
) -> dict[str, Any]:
    baseline_rows = _trade_rows(baseline_trades)
    lookup_rows = _trade_rows(lookup_trades)
    baseline_judged = judgment_population_trades(baseline_trades)
    lookup_judged = judgment_population_trades(lookup_trades)
    baseline_mean = summarize_realized_r(
        [trade.realized_r for trade in baseline_judged]
    )["mean_realized_r"]
    lookup_mean = summarize_realized_r(
        [trade.realized_r for trade in lookup_judged]
    )["mean_realized_r"]
    split_match = _split_summary(baseline_splits) == _split_summary(lookup_splits)
    bars_match = _validation_bar_fingerprint(baseline_bars) == _validation_bar_fingerprint(
        lookup_bars
    )
    rows_match = baseline_rows == lookup_rows
    return {
        "bit_identical": (
            split_match
            and bars_match
            and rows_match
            and len(baseline_trades) == len(lookup_trades)
            and len(baseline_judged) == len(lookup_judged)
            and baseline_mean == lookup_mean
        ),
        "split_match": split_match,
        "validation_bars_match": bars_match,
        "trade_rows_match": rows_match,
        "baseline_trade_count": len(baseline_trades),
        "lookup_trade_count": len(lookup_trades),
        "baseline_completed_non_gap_count": len(baseline_judged),
        "lookup_completed_non_gap_count": len(lookup_judged),
        "baseline_mean_realized_r": baseline_mean,
        "lookup_mean_realized_r": lookup_mean,
        "baseline_trade_rows_sha256": _rows_hash(baseline_rows),
        "lookup_trade_rows_sha256": _rows_hash(lookup_rows),
    }


def _trade_rows(trades: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        {
            "entry_time": _serialize(trade.entry_time),
            "exit_time": _serialize(trade.exit_time),
            "side": trade.side,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "initial_stop_price": trade.initial_stop_price,
            "initial_risk": trade.initial_risk,
            "realized_r_gross": trade.realized_r_gross,
            "realized_r_net": trade.realized_r_net,
            "realized_r": trade.realized_r,
            "exit_reason": trade.exit_reason,
            "bars_held": trade.bars_held,
            "signal_time": _serialize(trade.signal_time),
            "signal_atr": trade.signal_atr,
            "entry_z": trade.entry_z,
            "entry_session_vwap": trade.entry_session_vwap,
            "entry_vwap_deviation": trade.entry_vwap_deviation,
            "contract": trade.contract,
            "commission_is_smoke_test": trade.commission_is_smoke_test,
            "gap_through": trade.gap_through,
            "hold_crosses_gap": trade.hold_crosses_gap,
        }
        for trade in trades
    ]


def _validation_bar_fingerprint(validation_bars: pd.DataFrame) -> str:
    columns = [
        "DateTime_UTC",
        "DateTime_ET",
        "SessionDate_ET",
        "SessionMinute_ET",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "BidVolume",
        "AskVolume",
        "Contract",
        "IsFirstSessionAfterContractChange",
        "BarGapFromPrevious",
    ]
    rows = [
        {column: _json_value(value) for column, value in row.items()}
        for row in validation_bars[columns].to_dict(orient="records")
    ]
    return _rows_hash(rows)


def _rows_hash(rows: Sequence[dict[str, Any]]) -> str:
    payload = json.dumps(
        _json_value(list(rows)),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
    return OUTPUT_ROOT / f"cross_instrument_es_{timestamp}"


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


def _config_payload(config: InstrumentConfig) -> dict[str, Any]:
    return {
        "instrument": config.instrument,
        "input_path": repo_key(config.input_path, repo_root=ROOT),
        "implementation_status": config.implementation_status,
        "accounting_constants": _accounting_payload(config),
        "session_config": _session_payload(config),
    }


def _accounting_payload(config: InstrumentConfig) -> dict[str, Any]:
    return {
        "tick_size": config.tick_size,
        "point_value": config.point_value,
        "tick_value": config.tick_value,
        "slippage_ticks_per_side": config.slippage_ticks_per_side,
        "commission_per_round_turn": config.commission_per_round_turn,
        "commission_is_smoke_test": config.commission_is_smoke_test,
    }


def _session_payload(config: InstrumentConfig) -> dict[str, Any]:
    return {
        "session_model": config.session_model,
        "source_timezone": config.source_timezone,
        "strategy_timezone": config.strategy_timezone,
        "session_open": config.session_open,
        "rth_start_session_minute": config.rth_start_session_minute,
        "last_rth_bar_open_session_minute": config.last_rth_bar_open_session_minute,
        "session_force_flat_minute": config.session_force_flat_minute,
    }


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


def _write_cross_instrument_csv(
    path: Path,
    rows: Sequence[dict[str, Any]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CROSS_INSTRUMENT_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: _csv_value(row.get(field))
                    for field in CROSS_INSTRUMENT_CSV_FIELDS
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


def _serialize(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


if __name__ == "__main__":
    print(run_cross_instrument_report())
