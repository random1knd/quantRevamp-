import pandas as pd
import pytest

from strategies.vwap_zscore_fade.parent.strategy import generate_trades


def make_target_exit_setup(*, side: str, roll_session: bool = False) -> pd.DataFrame:
    if side == "long":
        signal_open = signal_high = 81.0
        signal_low = signal_close = 80.0
        entry_open = 80.0
        entry_high = 100.0
        entry_low = 79.0
        entry_close = 90.0
    elif side == "short":
        signal_open = signal_low = 119.0
        signal_high = signal_close = 120.0
        entry_open = 120.0
        entry_high = 121.0
        entry_low = 100.0
        entry_close = 110.0
    else:
        raise ValueError(f"unsupported side: {side}")

    rows = []
    start = pd.Timestamp("2026-01-02 09:30:00", tz="America/New_York")
    for index in range(19):
        rows.append(
            {
                "DateTime_ET": start + pd.Timedelta(minutes=index * 5),
                "SessionDate_ET": "2026-01-02",
                "SessionMinute_ET": index * 5,
                "Open": 100.0,
                "High": 100.0,
                "Low": 100.0,
                "Close": 100.0,
                "Volume": 100.0,
                "BidVolume": 40.0,
                "AskVolume": 60.0,
                "Contract": "NQH26",
                "IsFirstSessionAfterContractChange": roll_session,
            }
        )

    rows.append(
        {
            "DateTime_ET": start + pd.Timedelta(minutes=95),
            "SessionDate_ET": "2026-01-02",
            "SessionMinute_ET": 95,
            "Open": signal_open,
            "High": signal_high,
            "Low": signal_low,
            "Close": signal_close,
            "Volume": 100.0,
            "BidVolume": 40.0,
            "AskVolume": 60.0,
            "Contract": "NQH26",
            "IsFirstSessionAfterContractChange": roll_session,
        }
    )
    rows.append(
        {
            "DateTime_ET": start + pd.Timedelta(minutes=100),
            "SessionDate_ET": "2026-01-02",
            "SessionMinute_ET": 100,
            "Open": entry_open,
            "High": entry_high,
            "Low": entry_low,
            "Close": entry_close,
            "Volume": 100.0,
            "BidVolume": 40.0,
            "AskVolume": 60.0,
            "Contract": "NQH26",
            "IsFirstSessionAfterContractChange": roll_session,
        }
    )

    return pd.DataFrame(rows)


def generate_smoke_trades(bars: pd.DataFrame, *, exclude_roll_sessions: bool = True):
    return generate_trades(
        bars,
        exclude_roll_sessions=exclude_roll_sessions,
        commission_per_round_turn=0.0,
        commission_is_smoke_test=True,
    )


def test_generate_trades_enters_long_after_negative_zscore_and_exits_at_vwap_target():
    bars = make_target_exit_setup(side="long")

    trades = generate_smoke_trades(bars)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.side == "long"
    assert trade.entry_time == bars.loc[20, "DateTime_ET"]
    assert trade.signal_time == bars.loc[19, "DateTime_ET"]
    assert trade.entry_price == 80.25
    assert trade.signal_atr == pytest.approx(20.0 / 14.0)
    assert trade.initial_stop_price == pytest.approx(78.10714285714286)
    assert trade.initial_risk == pytest.approx(2.142857142857139)
    assert trade.exit_reason == "target"
    assert trade.bars_held == 1
    assert trade.entry_z <= -2.0
    assert trade.realized_r > 0.0
    assert trade.commission_is_smoke_test is True


def test_generate_trades_enters_short_after_positive_zscore_and_exits_at_vwap_target():
    bars = make_target_exit_setup(side="short")

    trades = generate_smoke_trades(bars)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.side == "short"
    assert trade.entry_time == bars.loc[20, "DateTime_ET"]
    assert trade.signal_time == bars.loc[19, "DateTime_ET"]
    assert trade.entry_price == 119.75
    assert trade.signal_atr == pytest.approx(20.0 / 14.0)
    assert trade.initial_stop_price == pytest.approx(121.89285714285714)
    assert trade.initial_risk == pytest.approx(2.142857142857139)
    assert trade.exit_reason == "target"
    assert trade.bars_held == 1
    assert trade.entry_z >= 2.0
    assert trade.realized_r > 0.0


def test_generate_trades_excludes_roll_session_signals_when_requested():
    bars = make_target_exit_setup(side="long", roll_session=True)

    excluded = generate_smoke_trades(bars, exclude_roll_sessions=True)
    included = generate_smoke_trades(bars, exclude_roll_sessions=False)

    assert excluded == []
    assert len(included) == 1


def test_generate_trades_requires_smoke_label_for_zero_commission():
    bars = make_target_exit_setup(side="long")

    with pytest.raises(ValueError, match="zero commission requires smoke-test label"):
        generate_trades(
            bars,
            exclude_roll_sessions=True,
            commission_per_round_turn=0.0,
            commission_is_smoke_test=False,
        )
