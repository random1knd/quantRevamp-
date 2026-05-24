"""Run a single-hypothesis Monte Carlo check on the validation child."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
import subprocess
from typing import Any, Sequence

import pandas as pd

from shared.validation.monte_carlo import centered_bootstrap_mean_report
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import (
    params as child_params,
)
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test.strategy import (
    generate_trades as generate_child_trades,
)
from strategies.vwap_zscore_fade.parent import params as parent_params
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
    load_validation_bars,
    judgment_population_trades,
)


ROOT = Path(__file__).resolve().parents[2]
N_ITER = 10000
RANDOM_SEED = 0
SIDEDNESS = "one_sided_positive"
IID_ASSUMPTION = (
    "The centered bootstrap treats the child validation completed_non_gap "
    "trades as i.i.d. draws. This is a single frozen-child check, not a "
    "full-search slicer correction."
)


def run_validation_monte_carlo() -> Path:
    validation_bars, splits = load_validation_bars()
    child_trades = generate_child_trades(
        validation_bars,
        exclude_roll_sessions=EXCLUDE_ROLL_SESSIONS,
        commission_per_round_turn=COMMISSION_PER_ROUND_TURN,
        commission_is_smoke_test=COMMISSION_IS_SMOKE_TEST,
    )

    report = build_monte_carlo_report(
        child_trades=child_trades,
        validation_bars=validation_bars,
        splits=splits,
        n_iter=N_ITER,
        random_seed=RANDOM_SEED,
        sidedness=SIDEDNESS,
    )
    output_dir = _output_dir()
    run_config = build_run_config(
        validation_bars=validation_bars,
        splits=splits,
        output_dir=output_dir,
    )
    write_monte_carlo_artifacts(
        output_dir=output_dir,
        monte_carlo_report=report,
        run_config=run_config,
    )
    return output_dir


def build_monte_carlo_report(
    *,
    child_trades: Sequence[Any],
    validation_bars: pd.DataFrame,
    splits: dict[str, Any],
    n_iter: int,
    random_seed: int,
    sidedness: str,
) -> dict[str, Any]:
    judged_trades = judgment_population_trades(child_trades)
    realized_r = [trade.realized_r for trade in judged_trades]
    monte_carlo = centered_bootstrap_mean_report(
        realized_r,
        n_iter=n_iter,
        random_seed=random_seed,
        sidedness=sidedness,
    )

    return {
        "run_type": "validation_monte_carlo",
        "coverage_label": COVERAGE_LABEL,
        "child_workflow_label": child_params.WORKFLOW_TEST_LABEL,
        "strategy_family": parent_params.STRATEGY_NAME,
        "child_strategy_name": child_params.STRATEGY_NAME,
        "child_id": CHILD_ID,
        "split": "validation",
        "final_test_status": FINAL_TEST_STATUS,
        "data_start": validation_bars["DateTime_UTC"].min().isoformat(),
        "data_end": validation_bars["DateTime_UTC"].max().isoformat(),
        "session_start": validation_bars["SessionDate_ET"].min().isoformat(),
        "session_end": validation_bars["SessionDate_ET"].max().isoformat(),
        "splits": _split_summary(splits),
        "population": _population_summary(
            child_trades=child_trades,
            judged_trades=judged_trades,
        ),
        "observed": {
            "mean_realized_r": monte_carlo["observed_mean_realized_r"],
            "p_value": monte_carlo["p_value"],
            "sidedness": monte_carlo["sidedness"],
        },
        "monte_carlo": monte_carlo,
        "iid_assumption": IID_ASSUMPTION,
        "block_bootstrap_status": "deferred",
    }


def build_run_config(
    *,
    validation_bars: pd.DataFrame,
    splits: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    input_data = _input_data_metadata([INPUT_DATA_PATH])
    return {
        "run_type": "validation_monte_carlo",
        "coverage_label": COVERAGE_LABEL,
        "child_workflow_label": child_params.WORKFLOW_TEST_LABEL,
        "strategy_family": parent_params.STRATEGY_NAME,
        "child_strategy_name": child_params.STRATEGY_NAME,
        "child_id": CHILD_ID,
        "instrument": parent_params.INSTRUMENT,
        "timeframe": parent_params.TIMEFRAME,
        "split": "validation",
        "final_test_status": FINAL_TEST_STATUS,
        "output_dir": _repo_key(output_dir),
        "data_start": validation_bars["DateTime_UTC"].min().isoformat(),
        "data_end": validation_bars["DateTime_UTC"].max().isoformat(),
        "session_start": validation_bars["SessionDate_ET"].min().isoformat(),
        "session_end": validation_bars["SessionDate_ET"].max().isoformat(),
        "splits": _split_summary(splits),
        "input_data_sha256": input_data["sha256"],
        "input_data_bytes": input_data["bytes"],
        "input_data_is_repo_relative": input_data["is_repo_relative"],
        "non_reproducible_input_paths": input_data["non_reproducible_paths"],
        "code_version": _code_version(),
        "monte_carlo_config": {
            "n_iter": N_ITER,
            "random_seed": RANDOM_SEED,
            "sidedness": SIDEDNESS,
            "method": "centered_bootstrap_mean",
            "p_value_smoothing": "plus_one",
            "judgment_population": JUDGMENT_POPULATION,
        },
        "iid_assumption": IID_ASSUMPTION,
    }


def write_monte_carlo_artifacts(
    *,
    output_dir: str | Path,
    monte_carlo_report: dict[str, Any],
    run_config: dict[str, Any],
) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=False)
    _write_json(output_path / "monte_carlo_report.json", monte_carlo_report)
    _write_json(output_path / "run_config.json", run_config)


def _population_summary(
    *,
    child_trades: Sequence[Any],
    judged_trades: Sequence[Any],
) -> dict[str, Any]:
    all_completed = [
        trade for trade in child_trades if trade.exit_reason != "end_of_data"
    ]
    return {
        "name": JUDGMENT_POPULATION,
        "trade_count": len(child_trades),
        "all_completed_trade_count": len(all_completed),
        "completed_non_gap_trade_count": len(judged_trades),
        "incomplete_trade_count": len(child_trades) - len(all_completed),
        "excluded_hold_crosses_gap_count": len(all_completed) - len(judged_trades),
    }


def _output_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return OUTPUT_ROOT / f"validation_monte_carlo_{timestamp}"


def _split_summary(splits: dict[str, Any]) -> dict[str, Any]:
    return {
        "discovery_end": splits["discovery_end"].isoformat(),
        "validation_end": splits["validation_end"].isoformat(),
        "test_end": splits["test_end"].isoformat(),
        "discovery_session_count": splits["discovery_session_count"],
        "validation_session_count": splits["validation_session_count"],
        "test_session_count": splits["test_session_count"],
    }


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(_json_value(payload), indent=2, sort_keys=True),
        encoding="utf-8",
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


if __name__ == "__main__":
    print(run_validation_monte_carlo())
