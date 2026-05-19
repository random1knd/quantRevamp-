from strategies.vwap_zscore_fade.parent import params


def test_parent_params_match_locked_readme_values():
    assert params.STRATEGY_NAME == "vwap_zscore_fade"
    assert params.INSTRUMENT == "NQ"
    assert params.TIMEFRAME == "5min"
    assert params.SESSION_OPEN == "09:30"
    assert params.STRATEGY_TIMEZONE == "America/New_York"

    assert params.NO_ENTRY_BEFORE_SESSION_MINUTE == 60
    assert params.NO_ENTRY_AT_OR_AFTER_SESSION_MINUTE == 360
    assert params.LAST_RTH_BAR_OPEN_SESSION_MINUTE == 385
    assert params.SESSION_FORCE_FLAT_MINUTE == 390

    assert params.ENTRY_Z_THRESHOLD == 2.0
    assert params.Z_WINDOW == 20
    assert params.SIGNAL_MIN_BARS == 20
    assert params.ATR_WINDOW == 14
    assert params.STOP_ATR_MULTIPLE == 1.5
    assert params.MAX_BARS_HELD == 12

    assert params.SLIPPAGE_TICKS_PER_SIDE == 1
    assert params.NQ_TICK_SIZE == 0.25
    assert params.NQ_POINT_VALUE == 20.0
    assert params.NQ_TICK_VALUE == 5.0


def test_signal_min_bars_covers_entry_z_warmup_window():
    assert params.SIGNAL_MIN_BARS >= params.Z_WINDOW
