"""Run the parent VWAP z-score fade on the discovery split.

This runner intentionally keeps local loading, git-version, and
artifact-writing shape. The RTH source filter is a small shared data helper
because validation must use identical source preprocessing.

Commission is fixed here for this discovery campaign at 5.16 USD per round
turn. Source: NinjaTrader futures commission PDF lists NQ all-in monthly-plan
cost as 2.58 USD per side; 2.58 * 2 = 5.16. Keeping this as a run-level
constant locks the cost assumption into the discovery artifacts without making
broker cost a strategy parameter.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
import subprocess

import pandas as pd

from shared.data.bars import prepare_bars, rth_only_raw_bars
from shared.data.splits import chronological_session_splits
from strategies.vwap_zscore_fade.parent import params
from strategies.vwap_zscore_fade.parent.artifacts import write_parent_artifacts
from strategies.vwap_zscore_fade.parent.research_indicators import (
    RESEARCH_INDICATOR_COLUMNS,
    add_research_indicators,
)
from strategies.vwap_zscore_fade.parent.strategy import generate_trades


ROOT = Path(__file__).resolve().parents[3]
INPUT_DATA_PATH = ROOT / "data" / "bars" / "5min" / "NQ_all_5min.csv"
OUTPUT_ROOT = ROOT / "data" / "results" / params.STRATEGY_NAME / "parent"
EXCLUDE_ROLL_SESSIONS = True
COMMISSION_PER_ROUND_TURN = 5.16
COMMISSION_IS_SMOKE_TEST = False
RANDOM_SEED = 0
STRATEGY_VERSION = "parent_v0"

COMMISSION_SOURCE = (
    "NinjaTrader futures commission PDF: NQ E-mini Nasdaq 100 all-in "
    "monthly-plan rate is 2.58 USD per side; 2.58 * 2 = 5.16 USD round turn. "
    "https://ninjatrader.com/PDF/ninjatrader_futures_commissions.pdf"
)
TIMEZONE_INFERENCE = (
    "Source DateTime is inferred as UTC: on EST dates, high NQ volume clusters "
    "around 14:30 source time, matching the 09:30 ET cash open; on an EDT date, "
    "the same open-volume cluster shifts to 13:30 source time."
)
RTH_FILTER_NOTE = (
    "This discovery run filters the full source file to RTH rows before "
    "prepare_bars because the parent v0 strategy is RTH-only and the full "
    "ETH-style file can contain old and new contract labels on the same ET "
    "calendar date around rolls."
)


def run_discovery() -> Path:
    raw_bars = pd.read_csv(INPUT_DATA_PATH)
    raw_bars = _rth_only_raw_bars(raw_bars)
    prepared = prepare_bars(
        raw_bars,
        source_timezone=params.SOURCE_TIMEZONE,
        strategy_timezone=params.STRATEGY_TIMEZONE,
        session_open=params.SESSION_OPEN,
        expected_bar_interval_minutes=params.BAR_INTERVAL_MINUTES,
    )
    splits = chronological_session_splits(prepared)
    discovery_bars = prepared.loc[
        prepared["SessionDate_ET"] <= splits["discovery_end"]
    ].copy()
    _validate_discovery_does_not_overlap_final_test(discovery_bars, splits=splits)
    trades = generate_trades(
        discovery_bars,
        exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
        commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
    )
    context_bars = add_research_indicators(discovery_bars)

    output_dir = _output_dir()
    write_parent_artifacts(
        trades=trades,
        output_dir=output_dir,
        run_type="discovery",
        split="train",
        data_start=discovery_bars["DateTime_UTC"].min().isoformat(),
        data_end=discovery_bars["DateTime_UTC"].max().isoformat(),
        input_data_paths=[INPUT_DATA_PATH],
        campaign_id=_campaign_id(discovery_bars),
        commission_source=COMMISSION_SOURCE,
        source_timezone_rationale=TIMEZONE_INFERENCE,
        rth_filter_note=RTH_FILTER_NOTE,
        strategy_version=STRATEGY_VERSION,
        code_version=_code_version(),
        random_seed=RANDOM_SEED,
        exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
        commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
        bar_gap_count=_bar_gap_count(discovery_bars),
        bar_gap_session_count=_bar_gap_session_count(discovery_bars),
    )
    _write_context_trades_csv(
        output_dir=output_dir,
        context_bars=context_bars,
        research_indicator_columns=RESEARCH_INDICATOR_COLUMNS,
    )
    return output_dir


def _rth_only_raw_bars(raw_bars: pd.DataFrame) -> pd.DataFrame:
    return rth_only_raw_bars(
        raw_bars,
        source_timezone=params.SOURCE_TIMEZONE,
        strategy_timezone=params.STRATEGY_TIMEZONE,
        session_open=params.SESSION_OPEN,
        rth_start_session_minute=params.RTH_START_SESSION_MINUTE,
        last_rth_bar_open_session_minute=params.LAST_RTH_BAR_OPEN_SESSION_MINUTE,
    )


def _output_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return OUTPUT_ROOT / f"discovery_{timestamp}"


def _bar_gap_count(prepared_bars: pd.DataFrame) -> int:
    return int(prepared_bars["BarGapFromPrevious"].sum())


def _bar_gap_session_count(prepared_bars: pd.DataFrame) -> int:
    return int(
        prepared_bars.loc[
            prepared_bars["BarGapFromPrevious"],
            "SessionDate_ET",
        ].nunique()
    )


def _campaign_id(discovery_bars: pd.DataFrame) -> str:
    discovery_start = discovery_bars["SessionDate_ET"].min().isoformat()
    discovery_end = discovery_bars["SessionDate_ET"].max().isoformat()
    return (
        f"{params.STRATEGY_NAME}__{params.INSTRUMENT}__{params.TIMEFRAME}"
        f"__{discovery_start}_{discovery_end}"
    )


def _validate_discovery_does_not_overlap_final_test(
    discovery_bars: pd.DataFrame,
    *,
    splits: dict,
) -> None:
    # Mirror validation_run's explicit split-bound guard for accidental slice widening.
    if discovery_bars["SessionDate_ET"].max() > splits["discovery_end"]:
        raise RuntimeError(
            "discovery slice overlaps validation/final-test splits - aborting"
        )


def _write_context_trades_csv(
    *,
    output_dir: Path,
    context_bars: pd.DataFrame,
    research_indicator_columns: tuple[str, ...],
) -> None:
    trades_path = output_dir / "trades.csv"
    context_path = output_dir / "context_trades.csv"
    context_by_signal_time = _context_by_signal_time(
        context_bars,
        research_indicator_columns=research_indicator_columns,
    )

    with trades_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        fieldnames = list(reader.fieldnames or []) + list(research_indicator_columns)
        rows = []
        for row in reader:
            context_values = context_by_signal_time.get(row["SignalTime"])
            if context_values is None:
                raise ValueError(
                    "missing research context for SignalTime: "
                    f"{row['SignalTime']}"
                )
            rows.append(row | context_values)

    with context_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _context_by_signal_time(
    context_bars: pd.DataFrame,
    *,
    research_indicator_columns: tuple[str, ...],
) -> dict[str, dict[str, object]]:
    return {
        row["DateTime_ET"].isoformat(): {
            column: _context_value(row[column])
            for column in research_indicator_columns
        }
        for _, row in context_bars.iterrows()
    }


def _context_value(value: object) -> object:
    if pd.isna(value):
        return ""
    return value


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
    print(run_discovery())
