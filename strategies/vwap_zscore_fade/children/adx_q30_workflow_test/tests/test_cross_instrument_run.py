import csv
from datetime import date
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pandas as pd
import pytest

from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import (
    cross_instrument_run,
)


SCRATCH_ROOT = Path(".test_artifacts/child_cross_instrument_tests")


@pytest.fixture
def scratch(request):
    path = SCRATCH_ROOT / request.node.name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        for parent in (SCRATCH_ROOT, SCRATCH_ROOT.parent):
            try:
                parent.rmdir()
            except OSError:
                pass


def test_cross_instrument_runner_proves_nq_lookup_before_es_and_blocks_6e(
    scratch,
    monkeypatch,
):
    nq_bars = _validation_bars("NQ", close_offset=0.25)
    es_bars = _validation_bars("ES", close_offset=0.50)
    splits = _splits()
    input_paths = {
        "NQ": scratch / "NQ_sample.csv",
        "ES": scratch / "ES_sample.csv",
        "6E": scratch / "6E_sample.csv",
    }
    input_paths["NQ"].write_text("nq", encoding="utf-8")
    input_paths["ES"].write_text("es-data", encoding="utf-8")
    monkeypatch.setattr(
        cross_instrument_run,
        "INSTRUMENTS",
        _instrument_lookup(input_paths),
    )
    monkeypatch.setattr(
        cross_instrument_run,
        "load_validation_bars",
        lambda: (nq_bars.copy(), splits),
    )

    loaded_instruments = []

    def fake_load_instrument_validation_bars(config):
        loaded_instruments.append(config.instrument)
        if config.instrument == "NQ":
            return nq_bars.copy(), splits
        if config.instrument == "ES":
            return es_bars.copy(), splits
        raise AssertionError("6E must not be loaded in Cycle B")

    generate_calls = []

    def fake_generate_child_trades(
        bars,
        *,
        exclude_roll_sessions,
        commission_per_round_turn,
        commission_is_smoke_test,
        tick_size=None,
        point_value=None,
        slippage_ticks_per_side=None,
    ):
        instrument = bars["Instrument"].iloc[0]
        generate_calls.append(
            {
                "instrument": instrument,
                "tick_size": tick_size,
                "point_value": point_value,
                "slippage_ticks_per_side": slippage_ticks_per_side,
                "commission_per_round_turn": commission_per_round_turn,
                "commission_is_smoke_test": commission_is_smoke_test,
            }
        )
        if instrument == "ES":
            return [_trade("ES", realized_r=0.40, entry_price=5000.0)]
        return [_trade("NQ", realized_r=-0.20, entry_price=17000.0)]

    monkeypatch.setattr(
        cross_instrument_run,
        "load_instrument_validation_bars",
        fake_load_instrument_validation_bars,
    )
    monkeypatch.setattr(
        cross_instrument_run,
        "generate_child_trades",
        fake_generate_child_trades,
    )
    monkeypatch.setattr(
        cross_instrument_run,
        "_adx_restrictiveness_summary",
        lambda bars, *, exclude_roll_sessions: {
            "adx_kept_count": 3,
            "adx_rejected_count": 1,
            "adx_missing_count": 0,
        },
    )

    output_dir = scratch / "cross_instrument"
    result = cross_instrument_run.run_cross_instrument_report(output_dir=output_dir)

    assert result == output_dir
    assert loaded_instruments == ["NQ", "ES"]
    assert generate_calls[0]["instrument"] == "NQ"
    assert generate_calls[0]["point_value"] is None
    assert generate_calls[1]["instrument"] == "NQ"
    assert generate_calls[1]["point_value"] == pytest.approx(20.0)
    assert generate_calls[2]["instrument"] == "ES"
    assert generate_calls[2]["tick_size"] == pytest.approx(0.25)
    assert generate_calls[2]["point_value"] == pytest.approx(50.0)

    report = json.loads(
        (output_dir / cross_instrument_run.REPORT_JSON).read_text(encoding="utf-8")
    )
    assert report["report_type"] == "cross_instrument_report"
    assert report["report_label"] == (
        "coverage_only_validation_child_cross_instrument_no_edge_claim"
    )
    assert report["coverage_only"] is True
    assert report["judgment_status"] == "report_only_no_pass_fail"
    assert report["instruments_run"] == ["NQ", "ES"]
    assert "6E" in report["instruments_not_run"]
    assert report["nq_lookup_regression_proof"]["bit_identical"] is True
    assert report["nq_lookup_regression_proof"]["trade_rows_match"] is True
    assert report["nq_lookup_regression_proof"]["validation_bars_match"] is True
    assert report["instrument_order"] == ["ES", "NQ"]
    assert report["instrument_mean_sign_counts"] == {
        "positive": 1,
        "zero": 0,
        "negative": 1,
        "missing": 0,
    }

    with (output_dir / cross_instrument_run.REPORT_CSV).open(
        newline="",
        encoding="utf-8",
    ) as file:
        rows = list(csv.DictReader(file))
    assert [row["instrument"] for row in rows] == ["ES", "NQ"]
    assert rows[0]["point_value"] == "50.0"
    assert rows[1]["point_value"] == "20.0"

    run_config = json.loads(
        (output_dir / cross_instrument_run.RUN_CONFIG_JSON).read_text(
            encoding="utf-8"
        )
    )
    assert run_config["run_type"] == "validation_child_cross_instrument"
    assert run_config["instrument_lookup"]["6E"]["implementation_status"] == (
        "blocked_until_cycle_c_session_model"
    )
    assert run_config["input_data_bytes"][
        ".test_artifacts/child_cross_instrument_tests/"
        f"{scratch.name}/NQ_sample.csv"
    ] == 2
    assert run_config["input_data_bytes"][
        ".test_artifacts/child_cross_instrument_tests/"
        f"{scratch.name}/ES_sample.csv"
    ] == 7


def _instrument_lookup(input_paths: dict[str, Path]) -> dict[str, object]:
    config = cross_instrument_run.InstrumentConfig
    return {
        "NQ": config(
            instrument="NQ",
            input_path=input_paths["NQ"],
            session_model="same_day_rth",
            source_timezone="UTC",
            strategy_timezone="America/New_York",
            session_open="09:30",
            rth_start_session_minute=0,
            last_rth_bar_open_session_minute=385,
            session_force_flat_minute=390,
            tick_size=0.25,
            point_value=20.0,
            tick_value=5.0,
            slippage_ticks_per_side=1.0,
            commission_per_round_turn=5.16,
            commission_is_smoke_test=False,
            implementation_status="cycle_b_run",
        ),
        "ES": config(
            instrument="ES",
            input_path=input_paths["ES"],
            session_model="same_day_rth",
            source_timezone="UTC",
            strategy_timezone="America/New_York",
            session_open="09:30",
            rth_start_session_minute=0,
            last_rth_bar_open_session_minute=385,
            session_force_flat_minute=390,
            tick_size=0.25,
            point_value=50.0,
            tick_value=12.5,
            slippage_ticks_per_side=1.0,
            commission_per_round_turn=5.16,
            commission_is_smoke_test=False,
            implementation_status="cycle_b_run",
        ),
        "6E": config(
            instrument="6E",
            input_path=input_paths["6E"],
            session_model="overnight_18et_blocked_until_cycle_c",
            source_timezone="UTC",
            strategy_timezone="America/New_York",
            session_open="18:00",
            rth_start_session_minute=0,
            last_rth_bar_open_session_minute=1375,
            session_force_flat_minute=1380,
            tick_size=0.00005,
            point_value=125000.0,
            tick_value=6.25,
            slippage_ticks_per_side=1.0,
            commission_per_round_turn=5.60,
            commission_is_smoke_test=False,
            implementation_status="blocked_until_cycle_c_session_model",
        ),
    }


def _validation_bars(instrument: str, *, close_offset: float) -> pd.DataFrame:
    session = date(2026, 1, 2)
    rows = []
    start = pd.Timestamp("2026-01-02 09:30", tz="America/New_York")
    for index in range(2):
        timestamp_et = start + pd.Timedelta(minutes=index * 5)
        base = 100.0 + index
        rows.append(
            {
                "Instrument": instrument,
                "DateTime_UTC": timestamp_et.tz_convert("UTC"),
                "DateTime_ET": timestamp_et,
                "SessionDate_ET": session,
                "SessionMinute_ET": index * 5,
                "Open": base,
                "High": base + 1.0,
                "Low": base - 1.0,
                "Close": base + close_offset,
                "Volume": 1000 + index,
                "BidVolume": 400 + index,
                "AskVolume": 600 + index,
                "Contract": instrument,
                "IsFirstSessionAfterContractChange": False,
                "BarGapFromPrevious": False,
            }
        )
    return pd.DataFrame(rows)


def _splits() -> dict[str, object]:
    return {
        "discovery_end": date(2026, 1, 1),
        "validation_end": date(2026, 1, 2),
        "test_end": date(2026, 1, 3),
        "discovery_session_count": 1,
        "validation_session_count": 1,
        "test_session_count": 1,
    }


def _trade(
    contract: str,
    *,
    realized_r: float,
    entry_price: float,
) -> SimpleNamespace:
    entry_time = pd.Timestamp("2026-01-02 09:35", tz="America/New_York")
    exit_time = pd.Timestamp("2026-01-02 10:00", tz="America/New_York")
    return SimpleNamespace(
        entry_time=entry_time,
        exit_time=exit_time,
        side="long",
        entry_price=entry_price,
        exit_price=entry_price + realized_r,
        initial_stop_price=entry_price - 1.0,
        initial_risk=1.0,
        realized_r_gross=realized_r,
        realized_r_net=realized_r,
        realized_r=realized_r,
        exit_reason="target",
        bars_held=5,
        signal_time=entry_time - pd.Timedelta(minutes=5),
        signal_atr=1.25,
        entry_z=-2.0,
        entry_session_vwap=entry_price + 0.5,
        entry_vwap_deviation=-0.5,
        contract=contract,
        commission_is_smoke_test=False,
        gap_through=False,
        hold_crosses_gap=False,
    )
