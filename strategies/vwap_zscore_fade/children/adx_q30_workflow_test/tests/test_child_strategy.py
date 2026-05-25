from datetime import date
import json
from pathlib import Path

import pandas as pd
import pytest

from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import params
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test.indicators import (
    INDICATOR_COLUMNS,
    add_child_indicators,
)
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test import strategy
from strategies.vwap_zscore_fade.children.adx_q30_workflow_test.strategy import (
    _entry_allowed,
    generate_trades,
)


SESSION_DATE = date(2026, 1, 2)
EVIDENCE_PATH = Path(__file__).resolve().parents[1] / "evidence" / "filter_candidate.json"


def make_bar(
    *,
    minute: int,
    session_date: date = SESSION_DATE,
    Open: float,
    High: float,
    Low: float,
    Close: float,
) -> dict[str, object]:
    start = pd.Timestamp(f"{session_date.isoformat()} 09:30:00", tz="America/New_York")
    return {
        "DateTime_ET": start + pd.Timedelta(minutes=minute),
        "SessionDate_ET": session_date,
        "SessionMinute_ET": minute,
        "BarGapFromPrevious": False,
        "Open": Open,
        "High": High,
        "Low": Low,
        "Close": Close,
        "Volume": 100.0,
        "BidVolume": 40.0,
        "AskVolume": 60.0,
        "Contract": "NQH26",
        "IsFirstSessionAfterContractChange": False,
    }


def make_adx_missing_signal_setup() -> pd.DataFrame:
    rows = []
    for index in range(19):
        rows.append(
            make_bar(
                minute=index * 5,
                Open=100.0,
                High=100.0,
                Low=100.0,
                Close=100.0,
            )
        )
    rows.append(make_bar(minute=95, Open=81.0, High=81.0, Low=80.0, Close=80.0))
    rows.append(make_bar(minute=100, Open=80.0, High=100.0, Low=79.0, Close=90.0))
    return pd.DataFrame(rows)


def make_adx_bars(*, sessions: int = 1, bars_per_session: int = 50) -> pd.DataFrame:
    rows = []
    for session_index in range(sessions):
        session_date = date(2026, 1, 2 + session_index)
        for index in range(bars_per_session):
            close = 100.0 + index + ((index % 4) * 0.25)
            rows.append(
                make_bar(
                    minute=index * 5,
                    session_date=session_date,
                    Open=close - 0.2,
                    High=close + 0.8,
                    Low=close - 0.8,
                    Close=close,
                )
            )
    return pd.DataFrame(rows)


def generate_smoke_trades(bars: pd.DataFrame):
    return generate_trades(
        bars,
        exclude_roll_sessions=True,
        commission_per_round_turn=0.0,
        commission_is_smoke_test=True,
    )


def test_frozen_adx_threshold_matches_slicer_evidence():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    assert evidence["candidate_status"] == "no_candidate"
    assert evidence["best_rule"]["rule_id"] == "SignalADX__le__q30"
    assert params.ADX_FILTER_THRESHOLD == pytest.approx(
        evidence["best_rule"]["threshold"]
    )


def test_child_adx_is_causal_when_future_rows_change():
    bars = make_adx_bars()
    mutated = bars.copy()
    mutated.loc[36:, "High"] = [300.0 + index for index in range(len(mutated.loc[36:]))]
    mutated.loc[36:, "Low"] = [250.0 + index for index in range(len(mutated.loc[36:]))]
    mutated.loc[36:, "Close"] = [275.0 + index for index in range(len(mutated.loc[36:]))]

    original_result = add_child_indicators(bars)
    mutated_result = add_child_indicators(mutated)

    assert pd.notna(original_result.loc[35, "ADX"])
    assert original_result.loc[35, "ADX"] == mutated_result.loc[35, "ADX"]


def test_child_adx_resets_at_session_boundary():
    bars = make_adx_bars(sessions=2, bars_per_session=45)
    mutated = bars.copy()
    mutated.loc[:44, "High"] = [1000.0 + index * 5.0 for index in range(45)]
    mutated.loc[:44, "Low"] = [990.0 + index * 5.0 for index in range(45)]
    mutated.loc[:44, "Close"] = [995.0 + index * 5.0 for index in range(45)]

    original_result = add_child_indicators(bars)
    mutated_result = add_child_indicators(mutated)

    pd.testing.assert_series_equal(
        original_result.loc[45:, "ADX"],
        mutated_result.loc[45:, "ADX"],
    )


def test_child_strategy_skips_signal_when_adx_is_missing():
    bars = make_adx_missing_signal_setup()
    prepared = add_child_indicators(bars)

    assert pd.notna(prepared.loc[19, "EntryZ"])
    assert pd.notna(prepared.loc[19, "ATR"])
    assert pd.isna(prepared.loc[19, "ADX"])

    assert generate_smoke_trades(bars) == []


def test_child_strategy_rejects_unsorted_bars():
    bars = make_adx_missing_signal_setup().iloc[
        [1, 0, *range(2, 21)]
    ].reset_index(drop=True)

    with pytest.raises(ValueError, match="DateTime_ET ascending"):
        generate_smoke_trades(bars)


def test_child_entry_gate_blocks_high_adx_and_allows_low_adx():
    bars = pd.DataFrame(
        [
            make_bar(
                minute=95,
                Open=100.0,
                High=101.0,
                Low=99.0,
                Close=100.0,
            ),
            make_bar(
                minute=100,
                Open=100.0,
                High=101.0,
                Low=99.0,
                Close=100.0,
            ),
        ]
    )
    bars["ATR"] = [1.0, 1.0]
    bars["ADX"] = [params.ADX_FILTER_THRESHOLD + 0.01, params.ADX_FILTER_THRESHOLD]
    rth_bar_number = pd.Series([params.SIGNAL_MIN_BARS, params.SIGNAL_MIN_BARS + 1])

    blocked = _entry_allowed(
        bars,
        rth_bar_number=rth_bar_number,
        signal_pos=0,
        exclude_roll_sessions=True,
        adx_filter_threshold=params.ADX_FILTER_THRESHOLD,
    )
    bars.loc[0, "ADX"] = params.ADX_FILTER_THRESHOLD
    allowed = _entry_allowed(
        bars,
        rth_bar_number=rth_bar_number,
        signal_pos=0,
        exclude_roll_sessions=True,
        adx_filter_threshold=params.ADX_FILTER_THRESHOLD,
    )

    assert blocked is False
    assert allowed is True


def test_child_generate_trades_none_threshold_matches_frozen_threshold(monkeypatch):
    bars = make_adx_bars(bars_per_session=21)
    prepared = bars.copy()
    prepared["ATR"] = 2.0
    prepared["ADX"] = params.ADX_FILTER_THRESHOLD
    prepared["EntryZ"] = None
    prepared["SessionVWAP"] = 105.0
    prepared["VWAPDeviation"] = 0.0
    prepared.loc[19, "EntryZ"] = -params.ENTRY_Z_THRESHOLD
    prepared.loc[20, "Open"] = 100.0
    prepared.loc[20, "High"] = 106.0
    prepared.loc[20, "Low"] = 99.0
    prepared.loc[20, "Close"] = 105.0

    monkeypatch.setattr(strategy, "add_child_indicators", lambda _: prepared)

    default_trades = generate_trades(
        bars,
        exclude_roll_sessions=True,
        commission_per_round_turn=0.0,
        commission_is_smoke_test=True,
    )
    explicit_trades = generate_trades(
        bars,
        exclude_roll_sessions=True,
        commission_per_round_turn=0.0,
        commission_is_smoke_test=True,
        adx_filter_threshold=params.ADX_FILTER_THRESHOLD,
    )

    assert len(default_trades) == 1
    assert default_trades == explicit_trades


def test_child_indicator_columns_include_trade_driving_adx():
    assert "ADX" in INDICATOR_COLUMNS
