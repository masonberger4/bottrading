"""Narrow morning engine (narrow.py; PR #82 option D): sweep -> shift -> gap -> entry on the reaction."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from mentorship import strategy as ST

NY = "America/New_York"
SEQ = [  # minute, open, high, low, close
    (570, 5000, 5001, 4999, 5000), (571, 5000, 5002, 4998, 4999), (572, 4999, 5003, 4998, 5000),      # 09:32 = the swing high
    (573, 5000, 5001, 4994, 4995), (574, 4995, 4996, 4989, 4990),                                     # 09:34 runs the 4990 overnight low
    (575, 4990, 4992, 4988, 4991),                                                                    # 09:35 sweep extreme 4988
    (576, 4991, 4998, 4991, 4997), (577, 4997, 5006, 4997, 5005),                                     # 09:37 closes above 5003: shift; gap 4992-4997
    (578, 5005, 5007, 4998, 5006), (579, 5006, 5006, 4996, 4999),                                     # 09:39 trades into the gap, down close
    (580, 4999, 5002, 4998, 5001),                                                                    # 09:40 up close above the gap: order
    (581, 5001.5, 5004, 5001, 5003),                                                                  # 09:41 open = the fill
]


def day(after, mirror=False, cut=None):
    idx = pd.date_range("2024-03-05 00:00", periods=975, freq="1min", tz=NY)
    a = np.full((975, 4), 5000.0)
    a[180] = (5000, 5000, 4990, 5000)            # 03:00 overnight / London low
    a[240] = (5000, 5010, 5000, 5000)            # 04:00 overnight / London high
    last = 5000.0
    for m, *row in SEQ + after:
        a[m] = row
        last = row[3]
    k = max(m for m, *_ in SEQ + after)
    a[k + 1:] = last
    if mirror:
        a = 10000 - a[:, [0, 2, 1, 3]]
    df = pd.DataFrame(a, index=idx, columns=["open", "high", "low", "close"])
    df["volume"] = 1
    return df if cut is None else df[(df.index.hour * 60 + df.index.minute) <= cut]


def hist(mirror=False):
    idx = pd.date_range("2024-03-04 09:30", periods=390, freq="1min", tz=NY)
    a = np.full((390, 4), 5000.0)
    a[10] = (5000, 5050, 4950, 5000)
    a[-1] = (5000, 5005, 5000, 5005)
    if mirror:
        a = 10000 - a[:, [0, 2, 1, 3]]
    h = pd.DataFrame(a, index=idx, columns=["open", "high", "low", "close"])
    h["volume"] = 1
    return [h]


def P(**kw):
    return replace(ST.Params(), narrow="am", es_pt=1.0, risk_dollars=1000.0, max_notional=1e12, cost_per_share=0.1,
                   session_close=975, **kw)


UP = [(582, 5003, 5015, 5002, 5014), (583, 5014, 5030, 5013, 5028)]
DOWN = [(582, 5003, 5003, 4987, 4988)]


def run(df, p=None, mirror=False, **kw):
    return ST.run_day(df, hist(mirror), "ES", p or P(), 1, **kw)


def test_default_is_off():
    assert ST.Params().narrow == "off"


def test_long_reaction_entry_and_target():
    (tr,) = run(day(UP))
    assert (tr.setup, tr.side, tr.session, tr.entry_kind) == ("nar_am", "long", "AM", "react")
    assert tr.swept in ("on", "lon")
    assert tr.armed == pd.Timestamp("2024-03-05 09:37", tz=NY)
    assert tr.entry_time == pd.Timestamp("2024-03-05 09:41", tz=NY)
    assert tr.entry == 5001.5 and tr.stop == 4987.75 and tr.t1 == pytest.approx(5029.0)
    assert tr.shares == 72                                     # $1,000 / 13.75 points
    assert tr.exits == [(pd.Timestamp("2024-03-05 09:43", tz=NY), 5029.0, 72, "target")]
    r = tr.row(0.1)
    assert r["R"] == pytest.approx((27.5 * 72 - 0.2 * 72) / (13.75 * 72), abs=1e-3)


def test_short_is_the_mirror():
    (tr,) = run(day(UP, mirror=True), mirror=True)
    assert tr.side == "short" and tr.entry == 4998.5 and tr.stop == 5012.25 and tr.t1 == pytest.approx(4971.0)
    assert tr.exits[-1][1] == 4971.0 and tr.exits[-1][3] == "target"
    assert tr.row(0.1)["net"] > 0


def test_stop_out():
    (tr,) = run(day(DOWN))
    assert tr.exits[-1][1] == 4987.75 and tr.exits[-1][3] == "stop"
    assert tr.row(0.1)["R"] == pytest.approx(-1 - 0.2 / 13.75, abs=1e-3)


def test_flat_at_noon():
    (tr,) = run(day([]))
    assert tr.exits[-1][0] == pd.Timestamp("2024-03-05 12:00", tz=NY) and tr.exits[-1][3] == "time"


def test_no_lookahead():
    assert run(day(UP, cut=580), live=True) == []              # the reaction bar is the last bar: nothing filled yet
    (tr,) = run(day(UP, cut=581), live=True)                   # one bar later the fill is the same as on the full day
    assert tr.entry == 5001.5 and tr.entry_time == pd.Timestamp("2024-03-05 09:41", tz=NY) and tr.exits == []


def test_limit_entry_fills_in_the_gap():
    (tr,) = run(day(UP), P(nar_entry="limit", entry="edge"))
    assert tr.entry == 4997.0 and tr.entry_time == pd.Timestamp("2024-03-05 09:39", tz=NY) and tr.entry_kind == "limit"
    assert run(day(UP), P(nar_entry="limit", entry="ce")) == []      # the return's low (4996) never reaches the gap's CE (4994.5)


def test_gap_stop_and_r_target():
    (tr,) = run(day(UP), P(nar_stop="gap", nar_target=1.0))
    assert tr.stop == 4987.75                                  # the gap's first candle is the sweep-extreme bar here
    assert tr.t1 == pytest.approx(5001.5 + 13.75)


def test_pool_target():
    (tr,) = run(day(UP), P(nar_target="pool"))
    assert tr.t1 == pytest.approx(5050 - 0.25) and tr.lv_tags == "tgt_pd"      # 5010 is under 1R away: the prior day's high is next


def test_bias_filter_blocks_long_above_midnight_open():
    assert run(day(UP), P(nar_bias="midnight")) == []
    assert len(run(day(UP), P(nar_bias="prevday"))) == 1       # the prior day closed up
    assert run(day(UP), P(nar_bias="anti_prevday")) == []


def test_window_and_pool_switches():
    assert run(day(UP), P(nar_win=(600, 660))) == []           # the setup is before 10:00
    assert run(day(UP), P(nar_pools=("pd",))) == []            # the prior day's low (4950) was not run
    assert run(day(UP), P(nar_gap_min=6.0)) == []              # the gap is 5 points


def test_breakeven_switch():
    after = [(582, 5003, 5016, 5002, 5015), (583, 5015, 5015, 5000, 5001)]
    (tr,) = run(day(after), P(nar_be_at=1.0))
    assert tr.exits[-1][1] == 5001.5 and tr.exits[-1][3] == "be"


def test_bad_values_raise():
    for kw in (dict(narrow="pm"), dict(nar_entry="x"), dict(nar_stop="x"), dict(nar_bias="x"), dict(nar_target="x"), dict(nar_pools=("zz",))):
        with pytest.raises(ValueError):
            replace(ST.Params(), **kw)
