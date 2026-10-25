"""Hand-built price paths that check each rule fires (or doesn't) as intended."""
import os
import sys
from dataclasses import replace

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from silver_bullet import backtest  # noqa: E402
from silver_bullet.config import INSTRUMENTS, params_for  # noqa: E402
from silver_bullet.data import normalize  # noqa: E402

MES = INSTRUMENTS["MES"]

# Day 1 sets PDH 5030 / PDL 4990. Day 2, 10:00-10:12 NY:
# swing high 5012 at 10:02, swing low 5004 at 10:05, 10:09 closes above 5012 (MSS)
# leaving an FVG between 5007 (10:07 high) and 5010 (10:09 low). Buy limit 5010,
# stop 5004 - 2 ticks = 5003.50, target 5015, draw = PDH 5030 (20 pts away).
DAY1 = [("2026-03-02 09:30", 5000, 5030, 4990, 5010)]
DAY2 = [
    ("10:00", 5005, 5008, 5004.5, 5007),
    ("10:01", 5007, 5010, 5007, 5009),
    ("10:02", 5009, 5012, 5008, 5010),
    ("10:03", 5010, 5011, 5007, 5008),
    ("10:04", 5008, 5009, 5005, 5006),
    ("10:05", 5006, 5007, 5004, 5005),
    ("10:06", 5005, 5006, 5005, 5006),
    ("10:07", 5006, 5007, 5006, 5007),
    ("10:08", 5007, 5009, 5007, 5009),
    ("10:09", 5010, 5014, 5010, 5014),   # MSS close > 5012, FVG 5007-5010
    ("10:10", 5014, 5014.5, 5011, 5011),
    ("10:11", 5011, 5011, 5009.5, 5010),  # retrace fills the buy limit at 5010
]


def frame(day2_rest, day1=DAY1):
    rows = [(pd.Timestamp(t), o, h, l, c) for t, o, h, l, c in day1]
    rows += [(pd.Timestamp("2026-03-03 " + t), o, h, l, c) for t, o, h, l, c in DAY2 + day2_rest]
    df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close"]).set_index("datetime")
    return normalize(df)


def run(df, **kw):
    p = params_for("MES", **kw)
    trades, summary = backtest.run(df, MES, p)
    return trades, summary


def test_long_setup_hits_target():
    t, s = run(frame([("10:12", 5010, 5015.5, 5010, 5015)]))
    assert len(t) == 1
    tr = t.iloc[0]
    assert tr.side == "long" and tr.window == "AM"
    assert tr.entry == 5010 and tr.stop == 5003.5 and tr.target == 5015
    assert tr.reason == "target" and tr.points == 5
    assert tr.draw_name == "PDH"
    assert abs(tr.pnl - (5 * 5 - 2 * 0.62)) < 1e-9


def test_bar_touching_stop_and_target_counts_as_stop():
    t, _ = run(frame([("10:12", 5010, 5016, 5003, 5012)]))
    assert len(t) == 1 and t.iloc[0].reason == "stop"
    assert t.iloc[0].exit == 5003.25          # stop 5003.50 minus 1 tick slippage


def test_unfilled_order_cancelled_at_window_end():
    rest = [(f"10:{m:02d}", 5012, 5013, 5011, 5012) for m in range(12, 60)]
    rest += [("11:00", 5012, 5012, 5008, 5009)]   # would fill, but the window has closed
    # drop the 10:11 retrace so nothing fills inside the window
    df = frame(rest)
    df = df[df.index != pd.Timestamp("2026-03-03 10:11", tz="America/New_York")]
    t, s = run(df)
    assert s["setups_signalled"] >= 1
    assert len(t) == 0


def test_no_trade_without_ten_point_framework():
    day1 = [("2026-03-02 09:30", 5000, 5015, 4990, 5010)]   # PDH only 5 pts above entry
    t, s = run(frame([("10:12", 5010, 5015.5, 5010, 5015)], day1=day1))
    assert s["setups_signalled"] == 0 and len(t) == 0


def test_outside_window_no_trade():
    t, s = run(frame([("10:12", 5010, 5015.5, 5010, 5015)]), windows=("London", "PM"))
    assert len(t) == 0


def test_bias_filter_blocks_longs():
    t, s = run(frame([("10:12", 5010, 5015.5, 5010, 5015)]), bias="short")
    assert len(t) == 0


def test_flat_time_closes_position():
    rest = [(f"{h}:{m:02d}", 5011, 5012, 5010.5, 5011) for h in range(10, 16) for m in range(60)
            if (h, m) > (10, 11) and (h, m) < (15, 57)]
    t, _ = run(frame(rest))
    assert len(t) == 1 and t.iloc[0].reason == "flat time"


def test_synthetic_smoke():
    from silver_bullet.data import synthetic
    t, s = run(synthetic(days=10))
    assert s["overall"]["trades"] == len(t)


def test_schwab_bracket_json():
    import pytest
    pytest.importorskip("schwab")            # optional broker package; skip where it isn't installed
    from silver_bullet.schwab_broker import bracket_order
    from silver_bullet.strategy import Setup
    from datetime import datetime
    s = Setup(1, "AM", 571.23, 570.40, 571.73, 573.0, "PDH", datetime.now(), datetime.now())
    spec = bracket_order("SPY", 100, s).build()
    assert spec["orderStrategyType"] == "TRIGGER"
    assert spec["orderLegCollection"][0]["instruction"] == "BUY"
    assert spec["price"] == "571.23"
    oco = spec["childOrderStrategies"][0]
    assert oco["orderStrategyType"] == "OCO"
    legs = {c["orderType"]: c for c in oco["childOrderStrategies"]}
    assert legs["LIMIT"]["price"] == "571.73"
    assert legs["STOP"]["stopPrice"] == "570.40"
