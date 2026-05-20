"""Run one parent VWAP z-score fade smoke pass on the local NQ 5-minute file.

Source DateTime is inferred as UTC: on EST dates, high NQ volume clusters
around 14:30 source time, matching the 09:30 ET cash open; on an EDT date, the
same open-volume cluster shifts to 13:30 source time.

This smoke run filters the full source file to RTH rows before `prepare_bars`
because the parent v0 strategy is RTH-only and the full ETH-style file can
contain old and new contract labels on the same ET calendar date around rolls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import subprocess

import pandas as pd

from shared.data.bars import prepare_bars
from strategies.vwap_zscore_fade.parent import params
from strategies.vwap_zscore_fade.parent.artifacts import write_parent_artifacts
from strategies.vwap_zscore_fade.parent.strategy import generate_trades


ROOT = Path(__file__).resolve().parents[3]
INPUT_DATA_PATH = ROOT / "data" / "bars" / "5min" / "NQ_all_5min.csv"
OUTPUT_ROOT = ROOT / "data" / "results" / params.STRATEGY_NAME / "parent"
EXCLUDE_ROLL_SESSIONS = True
COMMISSION_PER_ROUND_TURN = 0.0
COMMISSION_IS_SMOKE_TEST = True
RANDOM_SEED = 0
STRATEGY_VERSION = "parent_v0"

TIMEZONE_INFERENCE = (
    "Source DateTime is inferred as UTC: on EST dates, high NQ volume clusters "
    "around 14:30 source time, matching the 09:30 ET cash open; on an EDT date, "
    "the same open-volume cluster shifts to 13:30 source time."
)
RTH_FILTER_NOTE = (
    "This smoke run filters the full source file to RTH rows before prepare_bars "
    "because the parent v0 strategy is RTH-only and the full ETH-style file can "
    "contain old and new contract labels on the same ET calendar date around "
    "rolls."
)


def run_smoke() -> Path:
    raw_bars = pd.read_csv(INPUT_DATA_PATH)
    raw_bars = _rth_only_raw_bars(raw_bars)
    prepared = prepare_bars(
        raw_bars,
        source_timezone=params.SOURCE_TIMEZONE,
        strategy_timezone=params.STRATEGY_TIMEZONE,
        session_open=params.SESSION_OPEN,
        expected_bar_interval_minutes=params.BAR_INTERVAL_MINUTES,
    )
    trades = generate_trades(
        prepared,
        exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
        commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
    )

    output_dir = _output_dir()
    write_parent_artifacts(
        trades=trades,
        output_dir=output_dir,
        run_type="smoke",
        split="full_file_smoke",
        data_start=prepared["DateTime_UTC"].min().isoformat(),
        data_end=prepared["DateTime_UTC"].max().isoformat(),
        input_data_paths=[INPUT_DATA_PATH],
        strategy_version=STRATEGY_VERSION,
        code_version=_code_version(),
        random_seed=RANDOM_SEED,
        exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
        commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
        bar_gap_count=_bar_gap_count(prepared),
        bar_gap_session_count=_bar_gap_session_count(prepared),
    )
    return output_dir


def _rth_only_raw_bars(raw_bars: pd.DataFrame) -> pd.DataFrame:
    source_times = pd.to_datetime(raw_bars["DateTime"], errors="raise")
    source_times = source_times.dt.tz_localize(params.SOURCE_TIMEZONE)
    strategy_times = source_times.dt.tz_convert(params.STRATEGY_TIMEZONE)
    minute_of_day = strategy_times.dt.hour * 60 + strategy_times.dt.minute
    session_open = pd.to_datetime(params.SESSION_OPEN, format="%H:%M").time()
    session_open_minute = session_open.hour * 60 + session_open.minute
    session_minute = minute_of_day - session_open_minute
    rth_mask = session_minute.between(
        params.RTH_START_SESSION_MINUTE,
        params.LAST_RTH_BAR_OPEN_SESSION_MINUTE,
    )
    return raw_bars.loc[rth_mask].copy()


def _output_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return OUTPUT_ROOT / f"smoke_{timestamp}"


def _bar_gap_count(prepared_bars: pd.DataFrame) -> int:
    return int(prepared_bars["BarGapFromPrevious"].sum())


def _bar_gap_session_count(prepared_bars: pd.DataFrame) -> int:
    return int(
        prepared_bars.loc[
            prepared_bars["BarGapFromPrevious"],
            "SessionDate_ET",
        ].nunique()
    )


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
    print(run_smoke())
