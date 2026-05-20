from datetime import date

import pandas as pd
import pytest

from strategies.vwap_zscore_fade.parent.indicators import add_parent_indicators
from strategies.vwap_zscore_fade.parent.strategy import generate_trades


SESSION_DATE = date(2026, 1, 2)


def make_signal_setup(
    *,
    side: str,
    roll_session: bool = False,
    signal_minute: int = 95,
    entry_overrides: dict[str, float] | None = None,
    following_overrides: list[dict[str, float]] | None = None,
) -> pd.DataFrame:
    if side == "long":
        signal_values = {"Open": 81.0, "High": 81.0, "Low": 80.0, "Close": 80.0}
        entry_values = {"Open": 80.0, "High": 100.0, "Low": 79.0, "Close": 90.0}
    elif side == "short":
        signal_values = {"Open": 119.0, "High": 120.0, "Low": 119.0, "Close": 120.0}
        entry_values = {"Open": 120.0, "High": 121.0, "Low": 100.0, "Close": 110.0}
    else:
        raise ValueError(f"unsupported side: {side}")

    if entry_overrides:
        entry_values.update(entry_overrides)

    rows = []
    first_minute = signal_minute - 95
    for index in range(19):
        rows.append(
            make_bar(
                minute=first_minute + index * 5,
                roll_session=roll_session,
                Open=100.0,
                High=100.0,
                Low=100.0,
                Close=100.0,
            )
        )

    rows.append(
        make_bar(
            minute=signal_minute,
            roll_session=roll_session,
            **signal_values,
        )
    )
    rows.append(
        make_bar(
            minute=signal_minute + 5,
            roll_session=roll_session,
            **entry_values,
        )
    )

    for offset, overrides in enumerate(following_overrides or [], start=2):
        rows.append(
            make_bar(
                minute=signal_minute + offset * 5,
                roll_session=roll_session,
                **overrides,
            )
        )

    return pd.DataFrame(rows)


def make_bar(
    *,
    minute: int,
    roll_session: bool,
    Open: float,
    High: float,
    Low: float,
    Close: float,
) -> dict[str, object]:
    start = pd.Timestamp("2026-01-02 09:30:00", tz="America/New_York")
    return {
        "DateTime_ET": start + pd.Timedelta(minutes=minute),
        "SessionDate_ET": SESSION_DATE,
        "SessionMinute_ET": minute,
        "Open": Open,
        "High": High,
        "Low": Low,
        "Close": Close,
        "Volume": 100.0,
        "BidVolume": 40.0,
        "AskVolume": 60.0,
        "Contract": "NQH26",
        "IsFirstSessionAfterContractChange": roll_session,
    }


def generate_smoke_trades(bars: pd.DataFrame, *, exclude_roll_sessions: bool = True):
    return generate_trades(
        bars,
        exclude_roll_sessions=exclude_roll_sessions,
        commission_per_round_turn=0.0,
        commission_is_smoke_test=True,
    )


def test_generate_trades_enters_long_after_negative_zscore_and_exits_at_vwap_target():
    bars = make_signal_setup(side="long")

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
    bars = make_signal_setup(side="short")

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


def test_generate_trades_exits_long_at_stop():
    bars = make_signal_setup(
        side="long",
        entry_overrides={"High": 81.0, "Low": 78.0, "Close": 79.0},
    )

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "stop"
    assert trade.exit_price == pytest.approx(trade.initial_stop_price - 0.25)
    assert trade.realized_r < 0.0


def test_generate_trades_exits_short_at_stop():
    bars = make_signal_setup(
        side="short",
        entry_overrides={"High": 122.0, "Low": 119.0, "Close": 121.0},
    )

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "stop"
    assert trade.exit_price == pytest.approx(trade.initial_stop_price + 0.25)
    assert trade.realized_r < 0.0


def test_generate_trades_records_long_gap_stop_when_bar_opens_beyond_stop():
    hold_bar = {"Open": 81.0, "High": 82.0, "Low": 79.5, "Close": 81.0}
    gap_bar = {"Open": 77.5, "High": 78.0, "Low": 77.0, "Close": 77.5}
    bars = make_signal_setup(
        side="long",
        entry_overrides=hold_bar,
        following_overrides=[gap_bar],
    )

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "gap_stop"
    assert trade.gap_through is True
    assert trade.exit_price == 77.5


def test_generate_trades_records_short_gap_stop_when_bar_opens_beyond_stop():
    hold_bar = {"Open": 120.0, "High": 120.5, "Low": 118.0, "Close": 119.0}
    gap_bar = {"Open": 122.5, "High": 123.0, "Low": 122.0, "Close": 122.5}
    bars = make_signal_setup(
        side="short",
        entry_overrides=hold_bar,
        following_overrides=[gap_bar],
    )

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "gap_stop"
    assert trade.gap_through is True
    assert trade.exit_price == 122.5


def test_generate_trades_treats_long_open_equal_stop_as_regular_stop():
    stop = 79.10714285714286
    hold_bar = {"Open": 81.0, "High": 82.0, "Low": 79.5, "Close": 81.0}
    stop_bar = {"Open": stop, "High": stop + 0.5, "Low": stop - 0.5, "Close": stop}
    bars = make_signal_setup(
        side="long",
        entry_overrides=hold_bar,
        following_overrides=[stop_bar],
    )

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "stop"
    assert trade.gap_through is False
    assert trade.exit_price == pytest.approx(trade.initial_stop_price - 0.25)


def test_generate_trades_treats_short_open_equal_stop_as_regular_stop():
    stop = 121.89285714285714
    hold_bar = {"Open": 120.0, "High": 120.5, "Low": 118.0, "Close": 119.0}
    stop_bar = {"Open": stop, "High": stop + 0.5, "Low": stop - 0.5, "Close": stop}
    bars = make_signal_setup(
        side="short",
        entry_overrides=hold_bar,
        following_overrides=[stop_bar],
    )

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "stop"
    assert trade.gap_through is False
    assert trade.exit_price == pytest.approx(trade.initial_stop_price + 0.25)


def test_generate_trades_fills_long_gap_through_target_at_target_without_slippage():
    bars = make_signal_setup(
        side="long",
        entry_overrides={"Open": 105.0, "High": 106.0, "Low": 104.0, "Close": 105.0},
    )
    expected_target = add_parent_indicators(bars).loc[20, "SessionVWAP"]

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "target"
    assert trade.gap_through is True
    assert trade.exit_price == pytest.approx(expected_target)


def test_generate_trades_treats_long_open_equal_target_as_regular_target():
    bars = make_signal_setup(
        side="long",
        entry_overrides={"Open": 99.0, "High": 101.0, "Low": 98.0, "Close": 99.0},
    )
    expected_target = add_parent_indicators(bars).loc[20, "SessionVWAP"]
    bars.loc[20, "Open"] = expected_target

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "target"
    assert trade.gap_through is False
    assert trade.exit_price == pytest.approx(expected_target - 0.25)


def test_generate_trades_fills_short_gap_through_target_at_target_without_slippage():
    bars = make_signal_setup(
        side="short",
        entry_overrides={"Open": 95.0, "High": 96.0, "Low": 94.0, "Close": 95.0},
    )
    expected_target = add_parent_indicators(bars).loc[20, "SessionVWAP"]

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "target"
    assert trade.gap_through is True
    assert trade.exit_price == pytest.approx(expected_target)


def test_generate_trades_treats_short_open_equal_target_as_regular_target():
    bars = make_signal_setup(
        side="short",
        entry_overrides={"Open": 101.0, "High": 102.0, "Low": 99.0, "Close": 100.0},
    )
    expected_target = add_parent_indicators(bars).loc[20, "SessionVWAP"]
    bars.loc[20, "Open"] = expected_target

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "target"
    assert trade.gap_through is False
    assert trade.exit_price == pytest.approx(expected_target + 0.25)


def test_generate_trades_uses_stop_before_target_on_same_bar_conflict():
    bars = make_signal_setup(
        side="long",
        entry_overrides={"High": 100.0, "Low": 78.0, "Close": 90.0},
    )

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "stop"
    assert trade.exit_price == pytest.approx(trade.initial_stop_price - 0.25)


def test_time_stop_uses_elapsed_minutes_not_row_count():
    hold_bar = {"Open": 81.0, "High": 82.0, "Low": 79.5, "Close": 81.0}
    bars = make_signal_setup(
        side="long",
        entry_overrides=hold_bar,
        following_overrides=[hold_bar] * 11,
    )
    start = pd.Timestamp("2026-01-02 09:30:00", tz="America/New_York")
    custom_minutes = [100, 105, 110, 115, 120, 125, 130, 135, 140, 155, 185, 190]
    for row_index, minute in zip(range(20, 32), custom_minutes, strict=True):
        bars.loc[row_index, "SessionMinute_ET"] = minute
        bars.loc[row_index, "DateTime_ET"] = start + pd.Timedelta(minutes=minute)

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "time_stop"
    assert trade.bars_held == 10
    assert trade.exit_time == bars.loc[29, "DateTime_ET"] + pd.Timedelta(minutes=5)


def test_time_stop_fires_at_row_12_when_bars_are_continuous():
    hold_bar = {"Open": 81.0, "High": 82.0, "Low": 79.5, "Close": 81.0}
    bars = make_signal_setup(
        side="long",
        entry_overrides=hold_bar,
        following_overrides=[hold_bar] * 11,
    )

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "time_stop"
    assert trade.bars_held == 12
    assert trade.exit_time == bars.loc[31, "DateTime_ET"] + pd.Timedelta(minutes=5)


def test_early_close_session_exits_as_session_end_not_end_of_data():
    hold_bar = {"Open": 81.0, "High": 82.0, "Low": 79.5, "Close": 81.0}
    bars = make_signal_setup(
        side="long",
        signal_minute=200,
        entry_overrides=hold_bar,
        following_overrides=[hold_bar] * 7,
    )
    next_session_row = make_bar(
        minute=0,
        roll_session=False,
        Open=100.0,
        High=100.0,
        Low=100.0,
        Close=100.0,
    )
    next_session_row["SessionDate_ET"] = date(2026, 1, 5)
    next_session_row["DateTime_ET"] = pd.Timestamp(
        "2026-01-05 09:30:00",
        tz="America/New_York",
    )
    bars = pd.concat([bars, pd.DataFrame([next_session_row])], ignore_index=True)

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "session_end"
    assert trade.exit_time == bars.loc[27, "DateTime_ET"] + pd.Timedelta(minutes=5)


def test_generate_trades_exits_at_session_end_before_time_stop():
    hold_bar = {"Open": 81.0, "High": 82.0, "Low": 79.5, "Close": 81.0}
    bars = make_signal_setup(
        side="long",
        signal_minute=350,
        entry_overrides=hold_bar,
        following_overrides=[hold_bar] * 6,
    )

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "session_end"
    assert trade.bars_held == 7
    assert trade.exit_time == bars.loc[26, "DateTime_ET"] + pd.Timedelta(minutes=5)
    assert trade.exit_time.hour == 16
    assert trade.exit_time.minute == 0


def test_dataset_tail_trade_exits_as_end_of_data():
    hold_bar = {"Open": 81.0, "High": 82.0, "Low": 79.5, "Close": 81.0}
    bars = make_signal_setup(
        side="long",
        entry_overrides=hold_bar,
    )

    trade = generate_smoke_trades(bars)[0]

    assert trade.exit_reason == "end_of_data"
    assert trade.bars_held == 1
    assert trade.exit_time == bars.loc[20, "DateTime_ET"] + pd.Timedelta(minutes=5)


def test_generate_trades_excludes_roll_session_signals_when_requested():
    bars = make_signal_setup(side="long", roll_session=True)

    excluded = generate_smoke_trades(bars, exclude_roll_sessions=True)
    included = generate_smoke_trades(bars, exclude_roll_sessions=False)

    assert excluded == []
    assert len(included) == 1


def test_generate_trades_requires_smoke_label_for_zero_commission():
    bars = make_signal_setup(side="long")

    with pytest.raises(ValueError, match="zero commission requires smoke-test label"):
        generate_trades(
            bars,
            exclude_roll_sessions=True,
            commission_per_round_turn=0.0,
            commission_is_smoke_test=False,
        )
