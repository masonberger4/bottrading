"""The coded ICT direction read (ict_read.py, PR #101) and its narrow-engine switches: nar_bias="read",
nar_on_block, nar_entry="open" and nar_day_skip (PR #103 option C)."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, ict_read as R, narrow as N, strategy as ST
from tests.test_narrow import DOWN, NY, UP, P, day, hist


def past(level=5000.0, mirror=False, big_last=False):
    """20 weekday sessions before 2024-03-05, flat at `level` with one 40-point bar at 10:00 each day (so the average
    daily range is 40), all hours but 17:00-18:00, up to midnight of the test day."""
    idx = pd.date_range("2024-02-04 18:00", "2024-03-04 23:59", freq="1min", tz=NY)
    idx = idx[(idx.hour != 17) & ~((idx.dayofweek == 4) & (idx.hour >= 17)) & (idx.dayofweek != 5)
              & ~((idx.dayofweek == 6) & (idx.hour < 18))]
    a = np.full((len(idx), 4), float(level))
    ten = np.flatnonzero((idx.hour == 10) & (idx.minute == 0))
    a[ten] = (level, level + 20, level - 20, level)
    if big_last:
        a[ten[-1]] = (level, level + 50, level - 50, level)
    if mirror:
        a = 10000 - a[:, [0, 2, 1, 3]]
    df = pd.DataFrame(a, index=idx, columns=["open", "high", "low", "close"])
    df["volume"] = 1
    return df


def run(df, p, mirror=False, **kw):
    kw.setdefault("nar_past", past(mirror=mirror))
    return ST.run_day(df, hist(mirror), "ES", p, 1, **kw)


def arrays(pst, df):
    both = pd.concat([pst, df])
    return (R.minutes(both.index), *(both[k].to_numpy(float) for k in ("open", "high", "low", "close")))


def at(pst, df, minute):
    return R.read(*arrays(pst, df), len(pst) + minute)


# ---- the read itself -----------------------------------------------------------------------------------------------
def test_votes_on_a_plain_day():
    r = at(past(5020), day(UP), 581)                 # the 09:41 entry bar of the long test day; price 5001
    assert r["adr"] == pytest.approx(40) and r["settle"] == 5020 and r["prev_rng"] == pytest.approx(1.0)
    assert r["s_settle"] == 1                        # yesterday's settlement is above
    assert r["s_first"] == 1                         # the 4988 low (09:35) came after the 04:00 high: the highs are next
    assert r["s_gapcl"] == 1                         # five opening gaps at 5020, all above and within one range
    assert r["side"] == 1 and r["total"] >= 3
    assert r["on_pos"] == pytest.approx((5001 - 4988) / (5020 - 4988))


def test_read_mirrors():
    a, b = at(past(5020), day(UP), 581), at(past(5020, mirror=True), day(UP, mirror=True), 581)
    assert b["side"] == -1 and b["total"] == -a["total"] and b["on_pos"] == pytest.approx(1 - a["on_pos"])


def test_equal_highs_are_the_draw_until_taken():
    r = at(past(5020), day(UP), 570)                 # 5040 printed on each prior day: equal highs 40 points up
    assert r["s_req"] == 1
    r = at(past(4970), day(UP), 570)                 # those highs (4990) were traded through overnight; the lows are 50 away
    assert r["s_req"] == 0


def test_high_made_last_votes_down():
    assert at(past(), day(UP), 570)["s_first"] == -1          # 03:00 low, then the 04:00 high


def test_read_uses_closed_bars_only():
    pst, df = past(5020), day(UP)
    t, o, h, l, c = arrays(pst, df)
    e = len(pst) + 581
    full = R.read(t, o, h, l, c, e)
    assert full == R.read(t[:e], o[:e], h[:e], l[:e], c[:e], e)
    h2, l2 = h.copy(), l.copy()
    h2[e:] += 500
    l2[e:] -= 500
    assert full == R.read(t, o, h2, l2, c, e)


def test_read_needs_history():
    pst = past()
    assert at(pst[pst.index >= "2024-02-26"], day(UP), 581) is None       # five sessions: not enough for the average range


# ---- nar_bias="read" and nar_on_block ---------------------------------------------------------------------------------
def test_defaults_are_off():
    p = ST.Params()
    assert p.nar_bias == "none" and p.nar_on_block == 0.0 and p.nar_day_skip == () and p.nar_entry == "react"
    assert not N.needs_past(P()) and N.needs_past(P(nar_bias="read"))


def test_read_bias_takes_the_trade_with_the_read():
    (tr,) = run(day(UP), P(nar_bias="read"), nar_past=past(5020))
    assert tr.side == "long"
    (tr,) = run(day(UP, mirror=True), P(nar_bias="read"), mirror=True, nar_past=past(5020, mirror=True))
    assert tr.side == "short"


def test_read_bias_blocks_the_trade_against_the_read():
    skips = []
    assert run(day(UP), P(nar_bias="read"), nar_past=past(4980), skips=skips) == []     # settlement and gaps below: no long
    assert skips[-1][-1] == "bias"
    assert len(run(day(UP), P(), nar_past=past(4980))) == 1                             # the same day with the switch off


def test_read_without_past_bars_skips_the_day():
    skips = []
    assert run(day(UP), P(nar_bias="read"), nar_past=None, skips=skips) == []
    assert skips[-1][-1] == "no_past"


def test_on_block_stops_a_trade_toward_the_overnight_extreme():
    # at the entry price sits 13 points up a 22-point range since 18:00 (0.59)
    assert len(run(day(UP), P(nar_on_block=0.67))) == 1
    skips = []
    assert run(day(UP), P(nar_on_block=0.55), skips=skips) == [] and skips[-1][-1] == "on_ext"
    assert run(day(UP, mirror=True), P(nar_on_block=0.55), mirror=True) == []
    assert len(run(day(UP, mirror=True), P(nar_on_block=0.67), mirror=True)) == 1


# ---- nar_entry="open" and nar_day_skip (option C) ------------------------------------------------------------------------
def test_open_entry_trades_the_read_at_the_first_open():
    (tr,) = run(day(UP), P(nar_entry="open"), nar_past=past(5020))
    assert tr.side == "long" and tr.entry == 5000 and tr.entry_time.strftime("%H:%M") == "09:30"
    assert tr.stop == pytest.approx(5000 * (1 - 0.0025)) and tr.t1 == pytest.approx(5025)
    assert tr.exits[-1][1] == pytest.approx(5025) and tr.exits[-1][3] == "target"
    (tr,) = run(day(DOWN), P(nar_entry="open", nar_open_stop_pct=0.2), nar_past=past(5020))
    assert tr.stop == pytest.approx(4990) and tr.exits[-1][3] == "stop"
    (tr,) = run(day(UP, mirror=True), P(nar_entry="open"), mirror=True, nar_past=past(5020, mirror=True))
    assert tr.side == "short" and tr.exits[-1][3] == "target"


def test_open_entry_is_one_trade_and_flat_at_noon():
    (tr,) = run(day([]), P(nar_entry="open", nar_max_trades=3), nar_past=past(5020))
    assert tr.exits[-1][3] == "time" and tr.exits[-1][0].strftime("%H:%M") == "12:00"


def test_open_entry_no_lookahead():
    a = run(day(UP), P(nar_entry="open"), nar_past=past(5020))
    b = run(day(UP, cut=570), P(nar_entry="open"), nar_past=past(5020), live=True)
    assert (b[0].side, b[0].entry, b[0].stop, b[0].t1) == (a[0].side, a[0].entry, a[0].stop, a[0].t1)


def test_day_skip_small_gap_and_big_prior_range():
    skips = []
    assert run(day(UP), P(nar_day_skip=("small_gap",)), skips=skips) == [] and skips[-1][-1] == "day_small_gap"   # open = settlement
    assert len(run(day(UP), P(nar_day_skip=("small_gap", "prev_big", "friday")), nar_past=past(5020))) == 1       # a 20-point gap, a Tuesday
    assert run(day(UP), P(nar_day_skip=("prev_big",)), nar_past=past(5020, big_last=True), skips=skips) == []
    assert skips[-1][-1] == "day_prev_big"
    assert len(run(day(UP), P(nar_day_skip=("prev_big",), nar_prev_big=3.0), nar_past=past(5020, big_last=True))) == 1


def test_day_skip_news_and_holiday_eve(monkeypatch):
    from mentorship import calendar as C
    monkeypatch.setattr(C, "events", lambda d: {"cpi"})
    assert run(day(UP), P(nar_day_skip=("news",))) == []
    assert len(run(day(UP), P(nar_day_skip=("news",), nar_skip_news=("fomc",)))) == 1
    monkeypatch.setattr(C, "is_holiday_eve", lambda d, bank=False: True)
    assert run(day(UP), P(nar_day_skip=("holiday_eve",))) == []
    assert len(run(day(UP), P())) == 1


def test_bad_values_raise():
    for kw in (dict(nar_day_skip=("x",)), dict(nar_on_block=0.3), dict(nar_on_block=1.0), dict(nar_open_stop_pct=0)):
        with pytest.raises(ValueError):
            replace(ST.Params(), **kw)


def test_past_bars_window():
    df = pd.concat([past(), day(UP)])
    pb = R.past_bars(df, pd.Timestamp("2024-03-05").date())
    assert pb.index[-1] == pd.Timestamp("2024-03-04 23:59", tz=NY) and pb.index[0] == df.index[0]
    assert "nar_past" in B.day_kwargs.__code__.co_names or "past_bars" in B.day_kwargs.__code__.co_names
