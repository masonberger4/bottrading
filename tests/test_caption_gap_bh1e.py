"""Caption-gap pass, package bias_htf#1/7: the draw-lock adjustments (at the lock time and per bar) of bh1e.py on the real DayCtx of hand-made days (fifth file of tests/test_caption_gap_bh1.py)."""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import bh1e as BE, bias_day as BD, levels as L, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, A_ROWS, day, history  # noqa: E402
from test_day_week_context import daily  # noqa: E402
from test_caption_gap_dwc1 import mk, at  # noqa: E402
from test_caption_gap_bh1 import BR, _run_rows, K  # noqa: E402
from test_caption_gap_bh1d import blocks  # noqa: E402

FLAT = (100.0, 100.0, 100.0, 100.0)


def pad_to_0930(rows, price=None):
    """`rows` from 00:00, padded with flat bars (at the last close) up to 09:25 (114 bars)."""
    price = rows[-1][3] if price is None else price
    return list(rows) + [(price, price + 0.1, price - 0.1, price)] * (114 - len(rows))


def fake_mark(monkeypatch, marked, side=-1, target=None):
    """mark_levels replaced by a fixed lock (the relock helpers call it for the levels still intact)."""
    def fake(ctx, row, t_lock, session, p, spent=(), org_pref=True):
        return dict(side=side, target=target, kind="pool", name="x", marked=list(marked), delivered=False, delivered_t=None, delivered_i=None, traded=False, session=session, t_lock=t_lock,
                    px=float(ctx.c[0]), day=ctx.day)
    monkeypatch.setattr(S, "mark_levels", fake)


def lk_of(side, target, marked, **kw):
    return dict(dict(side=side, target=target, kind="pool", name="x", marked=list(marked), delivered=False, delivered_t=None, delivered_i=None, traded=False, session="AM", t_lock=570,
                     px=100.0), **kw)


# --- item 5: a 60m close below the discount BISI -------------------------------------------------------------------------------------

HOURS_5 = [FLAT, FLAT, (96.0, 97.0, 95.0, 96.5), (96.5, 101.0, 96.4, 100.5), (100.5, 105.0, 98.5, 104.0), (104.0, 104.5, 100.0, 101.0), (101.0, 101.5, 96.5, 96.8), (96.8, 97.5, 96.0, 97.0),
           (97.0, 98.0, 96.5, 97.5)]


def test_bisi60_lost_draw():
    p = Params(**BASE, bisi60_draw=True)
    ctx = mk(D0, history(D0), p, rows=blocks(HOURS_5, 12), start="00:00")
    kl = S._idx_at(ctx, 570)
    assert BE._bisi60_lost(ctx, kl) == -1                                               # swing 95-105 (EQ 100), the 60m BISI 97-98.5 under it, a 60m close at 96.8 under its low
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    lock = lk_of(1, 110.0, marked)
    out = BE.lock_post(ctx, p, BR(), 570, "AM", kl, float(ctx.c[kl - 1]), lock, [])
    assert out["side"] == -1 and out["target"] == 90.0 and "bisi60_lost" in out["bh1"]
    # no loss: the 60m close at 97.4 stays above the BISI's low 97
    h2 = list(HOURS_5)
    h2[6] = (101.0, 101.5, 97.1, 97.4)
    ctx2 = mk(D0, history(D0), p, rows=blocks(h2, 12), start="00:00")
    assert BE._bisi60_lost(ctx2, S._idx_at(ctx2, 570)) == 0
    # the mirror
    hm_ = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in HOURS_5]
    hm_[0] = hm_[1] = (100.0, 100.0, 100.0, 100.0)
    ctx3 = mk(D0, history(D0), p, rows=blocks(hm_, 12), start="00:00")
    assert BE._bisi60_lost(ctx3, S._idx_at(ctx3, 570)) == 1
    off = Params(**BASE)
    assert BE.lock_post(ctx, off, BR(), 570, "AM", kl, 97.5, lk_of(1, 110.0, marked), [])["side"] == 1


# --- item 10: the 1h BPR lean -------------------------------------------------------------------------------------------------------

HOURS_10 = [(105.0, 106.0, 103.0, 104.0), (104.0, 104.0, 100.0, 100.5), (100.5, 102.0, 99.0, 101.0), (101.0, 102.2, 100.8, 102.0), (102.0, 104.0, 101.9, 103.8),
            (103.8, 104.5, 102.8, 104.0), (104.0, 104.2, 101.0, 101.5), (101.5, 102.0, 101.0, 101.5), (101.5, 102.0, 101.0, 101.5)]


def test_bpr_lean():
    p = Params(**BASE, bpr_lean=True)
    ctx = mk(D0, history(D0), p, rows=blocks(HOURS_10, 12), start="00:00")
    kl = S._idx_at(ctx, 570)
    assert BE._bpr_dir(ctx, kl) == -1                                                   # down (bear FVG 102-103), up (bull FVG 102.2-102.8 overlapping it), then a close under the overlap
    marked = [(103.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    out = BE.lock_post(ctx, p, BR(flip=-1), 570, "AM", kl, 101.5, lk_of(1, 103.0, marked), [])
    assert out["side"] == -1 and out["target"] == 90.0 and "bpr_lean" in out["bh1"]       # the pool below, even though the pool above is nearer
    assert BE.lock_post(ctx, p, BR(flip=1), 570, "AM", kl, 101.5, lk_of(1, 103.0, marked), [])["side"] == 1       # a bullish state: no lean
    assert BE.lock_post(ctx, p, BR(flip=0), 570, "AM", kl, 101.5, lk_of(1, 103.0, marked), [])["side"] == 1
    hm_ = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in HOURS_10]
    ctx2 = mk(D0, history(D0), p, rows=blocks(hm_, 12), start="00:00")
    assert BE._bpr_dir(ctx2, S._idx_at(ctx2, 570)) == 1


def test_bpr_lean_up_down_up_clean():
    # review round 1: a clean up-down-up 60m sequence (bull FVG 101-102, the overlapping bear FVG 100.8-101.5, a close at 101.8 above the overlap top 101.5) and no third FVG
    hours = [(100.0, 101.0, 99.0, 100.5), (100.5, 103.0, 100.5, 102.8), (102.8, 104.0, 102.0, 103.5), (103.5, 103.6, 101.5, 101.8), (101.8, 102.1, 99.5, 100.0),
             (100.0, 100.8, 99.8, 100.6), (100.6, 102.0, 100.5, 101.8), (101.8, 102.0, 100.7, 101.9), (101.9, 102.0, 100.9, 101.5)]
    b = np.array(hours, float)
    assert [(z.kind, z.bottom, z.top) for z in L.fvgs(b[:, 1], b[:, 2], b[:, 0], b[:, 3])] == [("bull", 101.0, 102.0), ("bear", 100.8, 101.5)]
    p = Params(**BASE, bpr_lean=True)
    ctx = mk(D0, history(D0), p, rows=blocks(hours, 12), start="00:00")
    kl = S._idx_at(ctx, 570)
    assert BE._bpr_dir(ctx, kl) == 1
    marked = [(110.0, "pool", "pdh1", 1), (99.0, "pool", "pdl1", -1)]
    out = BE.lock_post(ctx, p, BR(flip=1), 570, "AM", kl, 100.0, lk_of(-1, 99.0, marked), [])
    assert out["side"] == 1 and out["target"] == 110.0 and "bpr_lean" in out["bh1"]
    # the wrong order (bear FVG first, then the bull FVG) is not an up-down-up
    mirrored = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in hours]
    ctx2 = mk(D0, history(D0), p, rows=blocks(mirrored, 12), start="00:00")
    assert BE._bpr_dir(ctx2, S._idx_at(ctx2, 570)) == -1


# --- item 15: the raid gap guard -----------------------------------------------------------------------------------------------------

RAID_POST = [(91.8, 96.6, 91.7, 96.5), (96.4, 97.0, 96.2, 96.9), (96.9, 96.95, 94.5, 94.8), (94.8, 95.0, 94.0, 94.4), (94.4, 94.5, 92.0, 92.2), (92.2, 92.3, 88.8, 89.0)]


def _raid_ctx(p, post, **kw):
    lead = [(100.0, 100.1, 99.9, 100.0)] * 24 + [(100.0, 100.0, 89.0, 89.5), (89.5, 92.0, 89.2, 91.8)]
    rows = pad_to_0930(lead) + post
    ctx = mk(D0, history(D0), p, rows=rows, start="00:00", bias_row=BR(drange_in=1))
    ctx.nwog, ctx.nwog_today = [(110.0, 108.0)], False
    ctx.state7 = {}
    return ctx


def test_raid_gap_guard(monkeypatch):
    p = Params(**BASE, raid_gap_guard=True)
    ctx = _raid_ctx(p, RAID_POST)
    kl = S._idx_at(ctx, 570)
    px = float(ctx.c[kl - 1])
    assert px == pytest.approx(91.8)
    marked = [(108.0, "array", "nwog", 0), (85.0, "pool", "x", -1), (82.0, "pool", "y", -1)]
    lock = BE.lock_post(ctx, p, BR(drange_in=1), 570, "AM", kl, px, lk_of(-1, 85.0, marked), [])
    assert lock["side"] == 1 and lock["target"] == 108.0 and lock["rg"]["raid"] == 89.0 and "raid_gap" in lock["bh1"]          # long toward the current NWOG's near edge
    fake_mark(monkeypatch, marked)
    i = at(ctx, "09:55")                                                                # the sixth post row (low 88.8 < 89, the bear FVG 95.0-96.2 still open)
    assert ctx.l[i] == 88.8
    r = BE.lock_bar(ctx, p, "AM", lock, i, {"AM": False}, [])
    assert r is not None and r[0]["side"] == -1 and r[0]["target"] == 82.0 and r[1] is True and r[0]["rg_done"]               # the raid low is taken with the gap open: the sell-side
    assert BE.lock_bar(ctx, p, "AM", dict(lock), i - 1, {"AM": False}, []) is None                                          # the bar before: the low is not taken yet
    filled = list(RAID_POST)
    filled[4] = (94.4, 96.3, 92.0, 92.2)                                                # price traded up through the gap (high 96.3 >= 96.2) before the low
    ctx2 = _raid_ctx(p, filled)
    lock2 = BE.lock_post(ctx2, p, BR(drange_in=1), 570, "AM", kl, px, lk_of(-1, 85.0, marked), [])
    assert BE.lock_bar(ctx2, p, "AM", lock2, at(ctx2, "09:55"), {"AM": False}, []) is None and lock2["rg_done"]               # the gap was filled first: no flip
    # not a consolidation (no range, no regime, a wide prior session): the lock is left alone
    lock3 = BE.lock_post(ctx, p, BR(), 570, "AM", kl, px, lk_of(-1, 85.0, marked), [])
    assert lock3["side"] == -1 and "rg" not in lock3
    off = Params(**BASE)
    assert "rg" not in BE.lock_post(ctx, off, BR(drange_in=1), 570, "AM", kl, px, lk_of(-1, 85.0, marked), [])
    # the mirror: a buy-side raid above the prior session's high, the NWOG below
    lead_m = [(100.0, 100.1, 99.9, 100.0)] * 24 + [(100.0, 111.0, 100.0, 110.5), (110.5, 110.8, 108.0, 108.2)]
    ctx3 = mk(D0, history(D0), p, rows=pad_to_0930(lead_m), start="00:00", bias_row=BR(drange_in=1))
    ctx3.nwog, ctx3.nwog_today = [(90.0, 92.0)], False
    lm = BE.lock_post(ctx3, p, BR(drange_in=1), 570, "AM", S._idx_at(ctx3, 570), 108.2, lk_of(1, 115.0, [(92.0, "array", "nwog", 0), (115.0, "pool", "x", 1)]), [])
    assert lm["side"] == -1 and lm["target"] == 92.0


# --- item 16: the pre-stated invalidation price ----------------------------------------------------------------------------------------

def test_inval_touch_flip(monkeypatch, tmp_path):
    p = Params(**BASE, inval_src="array")
    rows = pad_to_0930([(100.0, 100.1, 99.9, 100.0)] * 20) + [(100.0, 100.5, 99.8, 100.2), (100.2, 104.25, 100.0, 103.0), (103.0, 103.2, 102.5, 102.8)]
    ctx = mk(D0, history(D0), p, rows=rows, start="00:00", bias_row=BR())
    ctx.state7 = {}
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    fake_mark(monkeypatch, marked, side=-1, target=90.0)
    lock = lk_of(-1, 90.0, marked, inval=104.0)
    ctx.lock = {"AM": lock}
    pending = dict(side=SimpleNamespace(sign=-1), session="AM")
    i = at(ctx, "09:35")                                                                # the bar with the wick to 104.25 (no close above)
    assert ctx.h[i] == 104.25 and ctx.c[i] == 103.0
    done = {"AM": False}
    out = S._lock_step(ctx, p, {"AM": 570}, i, int(ctx.t[i]), {}, done, [], [], pending)
    assert out is None                                                                  # the pending short is cancelled
    nl = ctx.lock["AM"]
    assert nl["side"] == 1 and nl["target"] == 110.0 and nl["inval_touch"] and "inval_touch" in nl["bh1"]
    lock2 = lk_of(-1, 90.0, marked, inval=104.0)                                         # one bar earlier: the high 100.5 is below the level
    ctx.lock = {"AM": lock2}
    S._lock_step(ctx, p, {"AM": 570}, at(ctx, "09:30"), 570, {}, {"AM": False}, [], [], dict(side=SimpleNamespace(sign=-1), session="AM"))
    assert ctx.lock["AM"]["side"] == -1
    # the array source: the far edge of the nearest bear daily array above the lock price
    d0 = history(D0)
    dts = [x.index[0].date() for x in d0[-3:]]
    hist = d0[:-3] + [daily(dts[0], 107.0, 108.0, 106.0, 106.5), daily(dts[1], 106.5, 106.8, 100.0, 100.5), daily(dts[2], 100.5, 104.0, 99.0, 100.0)]
    ctx2 = mk(D0, hist, p, rows=rows, start="00:00", bias_row=BR())
    assert BE._inval_level(ctx2, p, "AM", -1, 100.0) == 106.0
    assert BE._inval_level(ctx2, p, "AM", 1, 100.0) is None                              # no bull array under the price
    lk = BE.lock_post(ctx2, p, BR(), 570, "AM", S._idx_at(ctx2, 570), 100.0, lk_of(-1, 99.0, marked), [])
    assert lk["inval"] == 106.0
    # the manual source
    f = tmp_path / "inval_levels.csv"
    f.write_text(f"date,session,price\n{D0},AM,104.5\n2020-01-02,AM,1.0\n")
    monkeypatch.setattr(BE, "INVAL_FILE", f)
    pm = Params(**BASE, inval_src="manual")
    assert BE._inval_level(ctx2, pm, "AM", -1, 100.0) == 104.5 and BE._inval_level(ctx2, pm, "PM", -1, 100.0) is None
    monkeypatch.setattr(BE, "INVAL_FILE", tmp_path / "nope.csv")
    assert BE._inval_level(ctx2, pm, "AM", -1, 100.0) is None                            # no file: no level, no flip
    # the mirror: a bullish lock flips on a touch of the level below
    lock3 = lk_of(1, 110.0, marked, inval=96.0)
    ctx.lock = {"AM": lock3}
    ctx2.state7 = {}
    ctx2.lock = {"AM": lock3}
    fake_mark(monkeypatch, marked, side=1, target=110.0)
    j = at(ctx2, "09:30")
    ctx2.l[j] = 95.9
    r = BE.lock_bar(ctx2, p, "AM", lock3, j, {"AM": False}, [])
    assert r is not None and r[0]["side"] == -1 and r[0]["target"] == 90.0


# --- item 40: the morning low is in -----------------------------------------------------------------------------------------------------

LOW_IN_POST = [(92.5, 92.6, 91.9, 92.4),           # D: the AM low target (92) is delivered
               (92.4, 92.6, 91.8, 92.5), (92.5, 93.0, 92.4, 92.9), (92.9, 92.8, 92.2, 92.3), (92.3, 93.4, 92.3, 93.3), (93.3, 93.35, 91.7, 92.8),
               (92.8, 93.9, 92.8, 93.8), (93.8, 93.85, 93.0, 93.1), (93.1, 94.4, 93.0, 94.3), (94.3, 94.35, 93.5, 93.6), (93.6, 94.9, 93.5, 94.8)]


def test_low_in_relock(monkeypatch):
    p = Params(**BASE, low_in_relock=True)
    rows = pad_to_0930([(100.0, 100.1, 92.0, 93.0)] * 3, price=93.0) + LOW_IN_POST
    ctx = mk(D0, history(D0), p, rows=rows, start="00:00", bias_row=BR())
    ctx.state7 = {"only_side": {"AM": 1}}
    d = at(ctx, "09:30")
    marked = [(100.0, "pool", "pdh1", 1), (85.0, "pool", "pdl1", -1)]
    fake_mark(monkeypatch, marked, side=-1, target=85.0)
    lk = lk_of(-1, 92.0, marked, delivered=True, delivered_i=d)
    counts = [(BE._pivot_highs_taken(ctx, d, d + q), BE._new_extremes(ctx, d, d + q)) for q in range(1, 11)]
    assert counts[-1] == (4, 2) and counts[-2] == (3, 2), counts                          # four short-term highs taken against two marginal new lows
    done = {"AM": True}
    assert BE.lock_bar(ctx, p, "AM", dict(lk), d + 9, done, []) is None                    # three highs against two lows: not yet (3 < 2.0 x 2)
    r = BE.lock_bar(ctx, p, "AM", dict(lk), d + 10, done, [])
    assert r is not None and r[0]["side"] == 1 and r[0]["target"] == 100.0 and r[0]["low_in_done"] and "low_in" in r[0]["bh1"]
    assert done["AM"] is False and "AM" not in ctx.state7["only_side"]                      # the session is open again
    assert BE.lock_bar(ctx, p, "AM", dict(lk, low_in_done=True), d + 10, done, []) is None   # once
    assert BE.lock_bar(ctx, p, "AM", dict(lk, delivered=False), d + 10, done, []) is None    # only after the draw was delivered
    p1 = Params(**BASE, low_in_relock=True, low_in_min_highs=5)
    assert BE.lock_bar(ctx, p1, "AM", dict(lk), d + 10, done, []) is None
    p2 = Params(**BASE, low_in_relock=True, low_in_ratio=3.0)
    assert BE.lock_bar(ctx, p2, "AM", dict(lk), d + 10, done, []) is None
    # the mirror: a delivered buy-side draw, repeated lows against few new highs -> short
    mrows = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in rows]
    ctx_m = mk(D0, history(D0), p, rows=mrows, start="00:00", bias_row=BR())
    ctx_m.state7 = {}
    fake_mark(monkeypatch, [(100.0, "pool", "pdl1", -1), (115.0, "pool", "pdh1", 1)], side=1, target=115.0)
    lk_m = lk_of(1, 108.0, [(100.0, "pool", "pdl1", -1), (115.0, "pool", "pdh1", 1)], delivered=True, delivered_i=d)
    r_m = BE.lock_bar(ctx_m, p, "AM", dict(lk_m), d + 10, {"AM": True}, [])
    assert r_m is not None and r_m[0]["side"] == -1 and r_m[0]["target"] == 100.0


# --- item 41: both the REL and the buy-side intact -------------------------------------------------------------------------------------

def test_neutral_fifty_fifty(monkeypatch):
    p = Params(**BASE, fifty_rel=True)
    d0 = history(D0)
    dts = [x.index[0].date() for x in d0[-3:]]
    hist = d0[:-3] + [daily(dts[0], 98.0, 99.0, 97.0, 98.5), daily(dts[1], 98.5, 103.0, 98.4, 102.5), daily(dts[2], 102.5, 104.0, 101.5, 101.0)]          # a daily FVG 99.0-101.5
    # relative equal lows 99.2 / 99.25 (two 5m swing lows), the price 100.5 inside the FVG
    pre = [(100.5, 100.8, 100.2, 100.6)] * 6 + [(100.6, 100.7, 99.2, 100.0), (100.0, 100.5, 99.9, 100.4), (100.4, 100.7, 100.1, 100.5), (100.5, 100.6, 99.25, 99.9), (99.9, 100.4, 99.8, 100.3)]
    pre = pre + [(100.3, 100.7, 100.2, 100.5)] * 3
    rows = pad_to_0930(pre, price=100.5)
    ctx = mk(D0, hist, p, rows=rows, start="00:00", bias_row=BR())
    ctx.state7 = {}
    kl = S._idx_at(ctx, 570)
    px = float(ctx.c[kl - 1])
    marked = [(106.0, "pool", "pdh1", 1), (95.0, "pool", "pdl1", -1)]
    mk_ = [(5.5, 106.0, "pool", "pdh1", 1), (5.5, 95.0, "pool", "pdl1", -1)]
    lock = BE.lock_post(ctx, p, BR(), 570, "AM", kl, px, lk_of(1, 106.0, marked), mk_)
    assert lock["side"] == 0 and lock["fifty"] and lock["rel"] is not None and "fifty_rel" in lock["bh1"]                # price in the FVG, REL below, buy-side above: neutral
    assert 99.1 < lock["rel"] < 99.3
    # not inside a daily FVG: no 50/50
    ctx_n = mk(D0, history(D0), p, rows=rows, start="00:00", bias_row=BR())
    ctx_n.state7 = {}
    assert BE.lock_post(ctx_n, p, BR(), 570, "AM", kl, px, lk_of(1, 106.0, marked), mk_)["side"] == 1
    # the REL is swept (low 98.9) and an MSS up follows (a close above the last short-term high before the sweep): +1
    post = [(100.5, 100.6, 100.2, 100.4), (100.4, 100.5, 98.9, 99.0), (99.0, 99.8, 98.95, 99.7), (99.7, 100.9, 99.6, 100.8)]
    ctx2 = mk(D0, hist, p, rows=rows + post, start="00:00", bias_row=BR())
    ctx2.state7 = {}
    fake_mark(monkeypatch, marked, side=0, target=None)
    sweep, mss = at(ctx2, "09:35"), at(ctx2, "09:45")
    assert BE.lock_bar(ctx2, p, "AM", dict(lock), sweep, {"AM": True}, []) is None                  # swept, no MSS yet
    r = BE.lock_bar(ctx2, p, "AM", dict(lock), mss, {"AM": True}, [])
    assert r is not None and r[0]["side"] == 1 and r[0]["target"] == 106.0 and r[0]["fifty_done"]


# --- item 59: the minimum criteria --------------------------------------------------------------------------------------------------------

HOURS_59 = [(102.0, 103.0, 101.0, 102.5), (102.5, 103.2, 100.0, 101.0), (101.0, 102.0, 99.5, 101.5), (101.5, 103.0, 99.6, 102.8), (102.8, 103.5, 100.5, 101.0), (101.0, 102.0, 99.55, 100.0),
            (100.0, 101.8, 100.0, 101.5), (101.5, 102.0, 96.5, 97.5), (97.5, 104.0, 97.0, 103.8)]


def test_min_criteria():
    d0 = history(D0)
    dts = [x.index[0].date() for x in d0[-3:]]
    hist = d0[:-3] + [daily(dts[0], 95.0, 96.0, 94.0, 95.5), daily(dts[1], 95.5, 99.0, 95.4, 98.5), daily(dts[2], 98.5, 99.5, 97.5, 99.0)]       # a daily bull FVG 96.0-97.5
    p = Params(**BASE, min_criteria=True)
    ctx = mk(D0, hist, p, rows=blocks(HOURS_59, 12), start="00:00")
    kl = S._idx_at(ctx, 570)
    ok, mt, k3 = BE.min_criteria(ctx, 1, kl, 0.5)
    assert ok and mt == pytest.approx(96.75) and k3 is not None                         # the array is traded into, the 60m REL (99.5 / 99.55) swept, a later high above the last 60m high
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    lock = BE.lock_post(ctx, p, BR(), 570, "AM", kl, 103.8, lk_of(1, 110.0, marked), [])
    assert lock["side"] == 1 and lock["mc"]["mt"] == pytest.approx(96.75) and "min_criteria" in lock["bh1"]
    # without a relative equal low the sweep step fails: the long lock is neutral
    h2 = list(HOURS_59)
    h2[5] = (101.0, 102.0, 98.8, 100.0)
    ctx2 = mk(D0, hist, p, rows=blocks(h2, 12), start="00:00")
    assert not BE.min_criteria(ctx2, 1, kl, 0.5)[0]
    lock2 = BE.lock_post(ctx2, p, BR(), 570, "AM", kl, 103.8, lk_of(1, 110.0, marked), [])
    assert lock2["side"] == 0 and "min_criteria_fail" in lock2["bh1"]
    # the bodies after the break stay above the array's MT; a body under it afterwards cancels the long
    ctx3 = mk(D0, hist, p, rows=pad_to_0930(blocks(HOURS_59, 12), price=103.8) + [(103.8, 104.0, 103.5, 103.9)] * 2 + [(103.9, 103.95, 96.0, 96.2)], start="00:00")
    ctx3.lock = {"AM": lock}
    o = {"lv_tags": ""}
    sd = SimpleNamespace(sign=1, x=lambda v: v)
    i_ok = at(ctx3, "09:35")
    assert BE.order_ok(ctx3, sd, o, "AM", i_ok, p) is None and "min_criteria" in o["lv_tags"]
    assert BE.order_ok(ctx3, sd, {"lv_tags": ""}, "AM", at(ctx3, "09:40"), p) == "x_bh1_min_criteria"
    # the mirror
    hm_ = [(200 - o_, 200 - l_, 200 - h_, 200 - c_) for o_, h_, l_, c_ in HOURS_59]
    histm = d0[:-3] + [daily(dts[0], 105.0, 106.0, 104.0, 104.5), daily(dts[1], 104.5, 104.6, 101.0, 101.5), daily(dts[2], 101.5, 102.5, 100.5, 101.0)]     # a daily bear FVG 102.5-104.0
    ctxm = mk(D0, histm, p, rows=blocks(hm_, 12), start="00:00")
    okm, mtm, _ = BE.min_criteria(ctxm, -1, S._idx_at(ctxm, 570), 0.5)
    assert okm and mtm == pytest.approx(103.25)


# --- item 74: the latest 60m BISI holds ----------------------------------------------------------------------------------------------------

HOURS_74 = [(99.0, 100.0, 98.5, 99.8), (99.8, 103.0, 99.7, 102.8), (102.8, 104.0, 101.0, 103.5)] + [(103.5, 104.0, 103.0, 103.5)] * 6


def test_bisi60_hold():
    # the 60m BISI 100-101 (CE 100.5): bars 1-3 form it; the lock is long at 103.5
    post = [(103.5, 103.6, 103.0, 103.4), (103.4, 103.5, 100.4, 103.0), (103.0, 103.1, 99.9, 102.5), (102.5, 103.0, 102.0, 102.8)]
    pt = Params(**BASE, bisi60_hold="trade")
    ctx = mk(D0, history(D0), pt, rows=pad_to_0930(blocks(HOURS_74, 12), price=103.5) + post, start="00:00", bias_row=BR())
    ctx.state7 = {}
    lk = lk_of(1, 110.0, [(110.0, "pool", "pdh1", 1)], px=103.5)
    i0, i1, i2 = at(ctx, "09:30"), at(ctx, "09:35"), at(ctx, "09:40")
    # the hours 0-8 end at 09:00; the BISI exists once hour 2 is complete
    assert BE._bisi_hold(ctx, pt, lk, i0) == ""
    assert BE._bisi_hold(ctx, pt, lk, i1) == "weak"                                       # a wick to 100.4 under the CE 100.5, above the low 100
    assert BE._bisi_hold(ctx, pt, lk, i2) == "dead"                                       # a wick to 99.9 under the BISI's low
    r = BE.lock_bar(ctx, pt, "AM", dict(lk), i1, {"AM": False}, [])
    assert r is None and True                                                              # (weak: the lock is only tagged, in place)
    lk_ = dict(lk)
    BE.lock_bar(ctx, pt, "AM", lk_, i1, {"AM": False}, [])
    assert "bias_weak" in lk_["bh1"] and lk_["weak"]
    done = {"AM": False}
    r = BE.lock_bar(ctx, pt, "AM", dict(lk), i2, done, [])
    assert r is not None and r[0]["side"] == 0 and r[0]["bisi_dead"] and r[1] is True
    # 'close': the wicks do nothing (no 60m close under the BISI yet)
    pc = Params(**BASE, bisi60_hold="close")
    assert BE._bisi_hold(ctx, pc, lk, i2) == ""
    # a full 60m bar closing under the CE / the low
    post2 = post + [(102.8, 102.9, 99.5, 99.8)] * 12
    ctx2 = mk(D0, history(D0), pc, rows=pad_to_0930(blocks(HOURS_74, 12), price=103.5) + post2, start="00:00", bias_row=BR())
    j = at(ctx2, "10:25")
    assert BE._bisi_hold(ctx2, pc, lk, j) == "dead"
    # the mirror (a -1 lock, the latest 60m SIBI)
    hm_ = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in HOURS_74]
    postm = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in post]
    ctxm = mk(D0, history(D0), pt, rows=pad_to_0930(blocks(hm_, 12), price=200 - 103.5) + postm, start="00:00", bias_row=BR())
    lkm = lk_of(-1, 90.0, [(90.0, "pool", "pdl1", -1)], px=200 - 103.5)
    assert BE._bisi_hold(ctxm, pt, lkm, at(ctxm, "09:35")) == "weak" and BE._bisi_hold(ctxm, pt, lkm, at(ctxm, "09:40")) == "dead"


# --- item 44: the counter-bias trade after the delivered draw ---------------------------------------------------------------------------

def test_allow_counter_trend():
    p = Params(**BASE, allow_counter_trend=True)
    ctx = mk(D0, history(D0), p, rows=[(100.0, 100.3, 99.8, 100.1)] * 8, bias_row=BR())
    ctx.state7 = {"only_side": {}}
    i = at(ctx, "10:05")
    lk = lk_of(1, 104.0, [(104.0, "pool", "pdh1", 1)], delivered=True, delivered_i=at(ctx, "09:50"))
    done = {"AM": True}
    assert BE.lock_bar(ctx, p, "AM", lk, i, done, []) is None
    assert lk["ct_open"] and done["AM"] is False and ctx.state7["only_side"]["AM"] == -1             # the session reopens for the opposite side only
    ctx.lock = {"AM": lk}
    short, long_ = SimpleNamespace(sign=-1), SimpleNamespace(sign=1)
    assert BE.counter_kind(ctx, short, i, p, 1, "AM") == "ct" and BE.counter_kind(ctx, long_, i, p, 1, "AM") == ""
    assert BE.counter_kind(ctx, short, i, Params(**BASE), 1, "AM") == ""
    # review round 1: a session / day closed by a stop or target switch is not reopened
    for st_ in ({"day_done": True}, {"stops": {"day": True}}, {"stops": {"AM": True}}):
        lk3 = lk_of(1, 104.0, [(104.0, "pool", "pdh1", 1)], delivered=True, delivered_i=at(ctx, "09:50"))
        done3 = {"AM": True}
        assert BE.lock_bar(ctx, p, "AM", lk3, i, done3, [], st_) is None and not lk3.get("ct_open") and done3["AM"] is True, st_
    lk4 = lk_of(1, 104.0, [(104.0, "pool", "pdh1", 1)], delivered=True, delivered_i=at(ctx, "09:50"))
    BE.lock_bar(ctx, p, "AM", lk4, i, {"AM": True}, [], {})
    assert lk4["ct_open"]
    lk2 = lk_of(1, 104.0, [], delivered=False)
    BE.lock_bar(ctx, p, "AM", lk2, i, {"AM": False}, [])
    assert not lk2.get("ct_open")                                                                      # the draw has not been delivered
    # the order needs a bearish MSS AFTER the raid; the counter-trend tag is added
    o_late = {"lv_tags": "counter_trend", "broke": at(ctx, "10:00")}
    o_early = {"lv_tags": "counter_trend", "broke": at(ctx, "09:45")}
    assert BE.order_ok(ctx, short, o_late, "AM", i, p) is None and "counter_trend" in o_late["lv_tags"]
    assert BE.order_ok(ctx, short, o_early, "AM", i, p) == "x_bh1_ct_mss"
    # through run_day: the A scenario delivers its PDH draw (108); with the switch on the day still runs and the lock reports the reopening
    off_tr, off_locks, *_ = _run_rows(Params(**BASE), bias=BR())
    on_tr, on_locks, *_ = _run_rows(p, bias=BR())
    assert [t.entry_time for t in on_tr[:1]] == [t.entry_time for t in off_tr[:1]] and any(lk_.get("ct_open") for lk_ in on_locks) == any(lk_.get("delivered") for lk_ in on_locks)


# --- item 45: the nearest draw, near-ties ----------------------------------------------------------------------------------------------

def test_draw_order_nearest_tiebreak():
    # items are (distance, level, kind, name, dir), nearest first
    up = [(10.0, 110.0, "pool", "pdh1", 1)]
    dn = [(10.2, 89.8, "pool", "pdl1", -1)]
    mk_ = sorted(up + dn)
    cands = [(110.0, "pool", "pdh1", 1, 5), (89.8, "pool", "pdl1", -1, 9)]
    # fewer opposing arrays in the path first: the upper candidate has one in the way
    assert BE.tiebreak(up, dn, mk_, cands, lambda sg, it: 1 if sg > 0 else 0) == -1
    assert BE.tiebreak(up, dn, mk_, cands, lambda sg, it: 0 if sg > 0 else 2) == 1
    # equal arrays: the newer wins (created 9), then the nearer
    assert BE.tiebreak(up, dn, mk_, cands) == -1
    assert BE.tiebreak(up, dn, mk_, [(110.0, "pool", "pdh1", 1, 12), (89.8, "pool", "pdl1", -1, 9)]) == 1
    assert BE.tiebreak(up, dn, mk_, [(110.0, "pool", "pdh1", 1, 9), (89.8, "pool", "pdl1", -1, 9)]) == 1


def test_draw_order_tiebreak_through_mark_levels():
    from dataclasses import replace
    from test_caption_gap_bh1d import ExtConf
    p = Params(**BASE, draw_order="nearest_tb")
    hist = history(D0, hi=110.0, lo=90.2)                                           # PDH1 110.0 is 10.0 away, PDL1 90.2 is 9.8 away: a near-tie within eq_tol_pts
    ctx = mk(D0, hist, p, rows=[(100.0, 100.1, 99.9, 100.0)] * 6, start="09:30")
    assert S.mark_levels(ctx, None, 570, "AM", replace(p, draw_order="nearest"))["side"] == -1       # the default: the nearer, 90.2
    assert S.mark_levels(ctx, None, 570, "AM", p)["side"] == -1                      # no array in either path: the formed-later / nearer decides
    ctx.conf = ExtConf({"1h": [(1, 95.0, 96.0)]}, known=ctx.idx[0].value - 10 ** 12)        # a bull 1h array between the price and the pool below
    lk = S.mark_levels(ctx, None, 570, "AM", p)
    assert lk["side"] == 1 and lk["target"] == 110.0 and lk["name"] == "pdh1"
    assert S.mark_levels(ctx, None, 570, "AM", replace(p, draw_order="nearest"))["side"] == -1
    ctx.conf = ExtConf({"1h": [(-1, 104.0, 105.0)]}, known=ctx.idx[0].value - 10 ** 12)     # a bear array in the upper path: the lower pool keeps it
    assert S.mark_levels(ctx, None, 570, "AM", p)["side"] == -1
    # a pool raided at 09:40 is skipped at the PM lock: PDH1 traded at 09:40 is not marked at 13:30, the lower pool is the draw
    rows = [(100.0, 100.1, 99.9, 100.0)] * 2 + [(100.0, 110.5, 99.9, 100.0)] + [(100.0, 100.1, 99.9, 100.0)] * 3
    ctx2 = mk(D0, hist, p, rows=rows, start="09:30")
    names = [m[2] for m in S.mark_levels(ctx2, None, 810, "PM", p)["marked"]]
    assert "pdh1" not in names and "pdl1" in names
    assert "pdh1" in [m[2] for m in S.mark_levels(ctx2, None, 570, "AM", p)["marked"]]
    assert p.draw_order == "nearest_tb" and Params(**BASE).draw_order == "nearest"
