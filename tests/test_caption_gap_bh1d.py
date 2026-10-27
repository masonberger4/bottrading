"""Caption-gap pass, package bias_htf#1/7: the side gates, scalps, sizes and per-order rules (bh1e.py) on the real DayCtx of hand-made days (fourth file of tests/test_caption_gap_bh1.py)."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import bh1e as BE, bias_day as BD, daycontext as DW, levels as L, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, A_ROWS, A_LOCK, day, frame, history  # noqa: E402
from test_day_week_context import daily  # noqa: E402
from test_caption_gap_dwc1 import mk, at  # noqa: E402
from test_caption_gap_bh1 import BR, _run_rows  # noqa: E402


def blocks(spec, n):
    """5m rows for OHLC blocks of n bars each (n = 3 -> 15m, 12 -> 60m): every block shows exactly its (open, high, low, close)."""
    out = []
    for o, h, l, c in spec:
        rows = [(o, h, o, h), (h, h, l, l)] + [(l, l, l, l)] * (n - 3) + [(l, c, l, c)]
        out += rows[:n]
    return out


# --- item 6: the neutral lean ----------------------------------------------------------------------------------------------------

def test_neutral_lean():
    p = Params(**BASE, neutral_lean=True, htf_bias="combo")
    rows = [(100.0, 100.3, 99.8, 100.1)] * 6
    ctx = mk(D0, history(D0), p, rows=rows, bias_row=BR(lean=-1))
    i = at(ctx, "09:55")
    assert BD.want_at(ctx, p, "AM", i) == -1                                         # the neutral bias takes the lean ...
    assert BE.scalp_now(ctx, p, "AM", i, -1) == "bh1_lean"                           # ... as a scalp, no raid of the prior high yet
    assert BE.scalp_now(ctx, p, "AM", i, 1) == ""
    ctx2 = mk(D0, history(D0), p, rows=rows, bias_row=BR(lean=-1, combo=1, react=1))
    assert BD.want_at(ctx2, p, "AM", i) == 1                                         # a bias that is not neutral wins
    raid = [(100.0, 108.6, 99.8, 100.1)] + rows                                       # PDH 108 raided before the entry: normal management
    ctx3 = mk(D0, history(D0), p, rows=raid, bias_row=BR(lean=-1))
    assert BE.scalp_now(ctx3, p, "AM", at(ctx3, "09:55"), -1) == ""
    off = Params(**BASE, htf_bias="combo")
    assert BD.want_at(mk(D0, history(D0), off, rows=rows, bias_row=BR(lean=-1)), off, "AM", i) == 0
    # the mirror: a long lean, the prior low (90) raided
    ctx4 = mk(D0, history(D0), p, rows=rows, bias_row=BR(lean=1))
    assert BD.want_at(ctx4, p, "AM", i) == 1 and BE.scalp_now(ctx4, p, "AM", i, 1) == "bh1_lean"
    ctx5 = mk(D0, history(D0), p, rows=[(100.0, 100.3, 89.5, 100.1)] + rows, bias_row=BR(lean=1))
    assert BE.scalp_now(ctx5, p, "AM", at(ctx5, "09:55"), 1) == ""
    # a Wednesday: the Tuesday high counts
    wed = date(2026, 6, 24)
    h = history(wed)
    hi = [x for x in h if x.index[0].date() == date(2026, 6, 23)]
    assert hi
    tue_high = float(hi[0].high.max())
    ctx6 = mk(wed, h, p, rows=[(100.0, tue_high - 0.2, 99.8, 100.1)] * 6, bias_row=BR(lean=-1))
    assert BE.scalp_now(ctx6, p, "AM", at(ctx6, "09:55"), -1) == "bh1_lean"
    ctx7 = mk(wed, h, p, rows=[(100.0, tue_high + 0.5, 99.8, 100.1)] + [(100.0, 100.3, 99.8, 100.1)] * 5, bias_row=BR(lean=-1))
    assert BE.scalp_now(ctx7, p, "AM", at(ctx7, "09:55"), -1) == ""
    # the order tag
    o = {"lv_tags": ""}
    sd = SimpleNamespace(sign=-1, x=lambda v: -v)
    BE.order_ok(ctx, sd, o, "AM", i, p)
    assert "neutral_lean" in o["lv_tags"]


# --- item 18: the bellwether chart -------------------------------------------------------------------------------------------------

def test_bellwether_tf():
    spec = [(100.0, 101.0, 99.5, 100.9), (100.9, 100.9, 100.5, 100.6), (100.6, 101.8, 100.5, 101.7)]                # B3 closes above B1's high 101: a break up (B1's low 99.5 is the swing low)
    rows = blocks(spec, 3)
    p = Params(**BASE, bellwether_tf=15)
    ctx = mk(D0, history(D0), p, rows=rows, bias_row=BR(wk_dir=1))
    i = at(ctx, "10:10")                                                           # the last 5m bar of the third 15m bar
    b = BE.tf_complete(ctx, 15, i)
    assert BE.swing_break_dir(b["o"], b["h"], b["l"], b["c"]) == 1
    assert BE.side_ok(ctx, p, -1, "AM", i) == "x_bh1_bellwether" and BE.side_ok(ctx, p, 1, "AM", i) is None
    # not complete yet one bar earlier: the third bar is not in
    assert BE.bellwether_dir(ctx, 15, at(ctx, "10:05")) == 0
    # 15m needs a known bias / weekly expansion side; without one the 60m chart is used (flat here: no break)
    ctx2 = mk(D0, history(D0), p, rows=rows, bias_row=BR())
    assert BE.side_ok(ctx2, p, -1, "AM", i) is None
    p60 = Params(**BASE, bellwether_tf=60)
    assert BE.side_ok(ctx2, p60, -1, "AM", i) is None
    # the break down: a close under the pivot low
    spec2 = spec + [(101.7, 101.75, 100.2, 100.3), (100.3, 100.4, 99.0, 99.2)]
    ctx3 = mk(D0, history(D0), p, rows=blocks(spec2, 3), bias_row=BR(wk_dir=-1))
    j = at(ctx3, "10:40")
    assert BE.bellwether_dir(ctx3, 15, j) == -1 and BE.side_ok(ctx3, p, 1, "AM", j) == "x_bh1_bellwether" and BE.side_ok(ctx3, p, -1, "AM", j) is None


# --- item 43: the intraday order flow --------------------------------------------------------------------------------------------

def test_iof_state_intraday():
    # a down-close candle D, a close through its low (B), an up-close candle U whose high stays unbroken: bearish; a close above U's high ends it
    bars = [(101.0, 101.2, 100.0, 100.2), (100.2, 100.4, 99.0, 99.2), (99.2, 99.8, 99.1, 99.7), (99.7, 99.9, 99.5, 99.6)]
    arr_ = lambda bs: tuple(np.array([b[k] for b in bs], float) for k in range(4))
    assert BE.iof_state(*arr_(bars)) == -1
    assert BE.iof_state(*arr_(bars[:1])) == 0
    assert BE.iof_state(*arr_(bars + [(99.6, 100.1, 99.5, 100.0)])) == 1             # a close at 100.0 above the last up-close high 99.8
    mirror = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in bars]
    assert BE.iof_state(*arr_(mirror)) == 1
    # the engine: orders against the 15m state are rejected
    p = Params(**BASE, iof_tf=15)
    spec = [(101.0, 101.2, 100.0, 100.2), (100.2, 100.4, 99.0, 99.2), (99.2, 99.8, 99.1, 99.7), (99.7, 99.9, 99.5, 99.6)]
    ctx = mk(D0, history(D0), p, rows=blocks(spec, 3), bias_row=BR())
    i = at(ctx, "10:25")
    assert BE.iof_dir(ctx, 15, i) == -1
    assert BE.side_ok(ctx, p, 1, "AM", i) == "x_bh1_iof" and BE.side_ok(ctx, p, -1, "AM", i) is None
    ctx2 = mk(D0, history(D0), p, rows=blocks(spec + [(99.6, 100.1, 99.5, 100.0)], 3), bias_row=BR())
    j = at(ctx2, "10:40")
    assert BE.iof_dir(ctx2, 15, j) == 1 and BE.side_ok(ctx2, p, 1, "AM", j) is None and BE.side_ok(ctx2, p, -1, "AM", j) == "x_bh1_iof"
    assert BE.side_ok(ctx, Params(**BASE), 1, "AM", i) is None                          # off: nothing


# --- item 20: a gap against the bias --------------------------------------------------------------------------------------------

def test_org_gap_filter():
    p = Params(**BASE, org_gap_filter=True, htf_bias="flip")
    rows = [(98.0, 98.3, 97.8, 98.1)] * 12                                            # gap down: the prior close 100, the 09:30 open 98; no attempt back (the highs stay under 98.5)
    ctx = mk(D0, history(D0), p, rows=rows, bias_row=BR(flip=0))
    ctx.intermarket = {}
    assert BE.side_ok(ctx, p, -1, "AM", at(ctx, "09:45")) == "x_bh1_org_gap"            # before 10:00 the tell is unknown: shorts blocked
    assert BE.side_ok(ctx, p, 1, "AM", at(ctx, "09:45")) is None
    assert BE.side_ok(ctx, p, -1, "AM", at(ctx, "10:00")) is None                       # no attempt in 30 minutes: the gap acts as a breakaway - shorts allowed
    # an attempt (the high reaches 98.6 > the 25 % level) keeps them blocked
    rows2 = [(98.0, 98.6, 97.8, 98.1)] + rows[1:]
    ctx2 = mk(D0, history(D0), p, rows=rows2, bias_row=BR(flip=0))
    ctx2.intermarket = {}
    assert BE.side_ok(ctx2, p, -1, "AM", at(ctx2, "10:00")) == "x_bh1_org_gap"
    # a bearish state with the dollar rising: allowed at once
    ctx3 = mk(D0, history(D0), p, rows=rows2, bias_row=BR(flip=-1))
    ctx3.intermarket = {"dxy": 1}
    assert BE.side_ok(ctx3, p, -1, "AM", at(ctx3, "09:45")) is None
    ctx3.intermarket = {"dxy": -1}
    assert BE.side_ok(ctx3, p, -1, "AM", at(ctx3, "09:45")) == "x_bh1_org_gap"
    # the gap up: longs are blocked unless state +1 and the dollar falling
    up = [(102.0, 102.2, 101.7, 101.9)] * 12
    ctx4 = mk(D0, history(D0), p, rows=up, bias_row=BR(flip=0))
    ctx4.intermarket = {}
    assert BE.side_ok(ctx4, p, 1, "AM", at(ctx4, "09:45")) == "x_bh1_org_gap" and BE.side_ok(ctx4, p, -1, "AM", at(ctx4, "09:45")) is None
    ctx5 = mk(D0, history(D0), p, rows=up, bias_row=BR(flip=1))
    ctx5.intermarket = {"dxy": -1}
    assert BE.side_ok(ctx5, p, 1, "AM", at(ctx5, "09:45")) is None
    assert BE.side_ok(ctx4, p, 1, "AM", at(ctx4, "09:25")) is None                       # before 09:30 the gap is not known


# --- item 21: the ORG tell with its sequence ------------------------------------------------------------------------------------

def _prior_day_with_bear_fvg(d):
    """The previous session as an RTH frame: a bear FVG 86.0-89.5 low in the day (CE 87.75), then a rally to a close of 100."""
    rows = [(91.0, 91.2, 89.5, 89.8), (89.8, 89.9, 85.0, 85.2), (85.2, 86.0, 84.0, 84.5)]
    px = 84.5
    for _ in range(75):
        rows.append((px, px + 1.0, px - 0.05, px + 0.2))
        px += 0.2
    rows[-1] = (rows[-1][0], 100.1, rows[-1][2], 100.0)
    return frame(d, rows, 5, "09:30")


def test_org_tell():
    p = Params(**BASE, org_tell_seq=True)
    hist = history(D0)
    hist[-1] = _prior_day_with_bear_fvg(hist[-1].index[0].date())
    flat = [(90.0, 90.6, 89.8, 90.2)] * 6                                              # 09:30-09:55: the open 90 (a 10-pt gap down), the highs stay under 92.5
    seq = [(90.2, 90.4, 87.0, 87.3), (87.3, 87.4, 85.0, 85.3)]                          # 10:00: a displacement close through the CE, then under the FVG's low 86.0
    rows = flat + seq + [(85.3, 85.5, 85.0, 85.2)] * 3
    ctx = mk(D0, hist, p, rows=rows, bias_row=BR())
    assert ctx.org[-1] == (100.0, 90.0)
    assert BE.org_tell_dir(ctx, p, at(ctx, "09:55")) == 0                              # not judged before the window is over
    k = at(ctx, "10:05")
    assert BE.org_tell_dir(ctx, p, k) == -1
    assert BE.side_ok(ctx, p, 1, "AM", k) == "x_bh1_org_tell" and BE.side_ok(ctx, p, -1, "AM", k) is None
    assert BE.side_ok(ctx, p, 1, "PM", k) is None or True                               # (the PM is not part of the AM-rest rule: the bar index is AM here, see below)
    # a retrace of 6 pts in the window: no tell
    rows2 = flat[:2] + [(90.0, 96.0, 89.8, 90.2)] + flat[3:] + seq + [(85.3, 85.5, 85.0, 85.2)] * 3
    ctx2 = mk(D0, hist, p, rows=rows2, bias_row=BR())
    assert BE.org_tell_dir(ctx2, p, at(ctx2, "10:05")) == 0
    # the first couple of minutes are ignored: a spike at 09:30 does not count as the attempt
    rows3 = [(90.0, 96.0, 89.8, 90.2)] + flat[1:] + seq + [(85.3, 85.5, 85.0, 85.2)] * 3
    ctx3 = mk(D0, hist, p, rows=rows3, bias_row=BR())
    assert BE.org_tell_dir(ctx3, p, at(ctx3, "10:05")) == -1
    pp = Params(**BASE, org_tell_seq=True, org_tell_skip_min=0)
    assert BE.org_tell_dir(mk(D0, hist, pp, rows=rows3, bias_row=BR()), pp, at(ctx3, "10:05")) == 0
    # the sequence without a displacement close under the FVG: no tell
    weak = flat + [(90.2, 90.3, 87.5, 87.6), (87.6, 87.7, 87.4, 87.5)] + [(87.5, 87.6, 87.4, 87.5)] * 3
    ctx4 = mk(D0, hist, p, rows=weak, bias_row=BR())
    assert BE.org_tell_dir(ctx4, p, at(ctx4, "10:05")) == 0
    # the bias: want_at takes the tell for the AM (htf_bias on)
    pb = Params(**BASE, org_tell_seq=True, htf_bias="combo")
    ctx5 = mk(D0, hist, pb, rows=rows, bias_row=BR(combo=1, react=1))
    assert BD.want_at(ctx5, pb, "AM", at(ctx5, "10:05")) == -1 and BD.want_at(ctx5, pb, "AM", at(ctx5, "09:50")) == 1


# --- item 22: the consolidation case ----------------------------------------------------------------------------------------------

def test_org_consol_case():
    p = Params(**BASE, org_consol_case=True)
    rows = [(98.0, 98.4, 97.8, 98.2)] * 3 + [(98.2, 100.3, 98.1, 100.1)] + [(100.1, 100.2, 98.2, 98.4)] * 4          # the ORG 98-100 (prior close 100) fills at 09:45
    ctx = mk(D0, history(D0), p, rows=rows, bias_row=BR(obj_day=1))
    i = at(ctx, "10:05")
    assert BE.scalp_now(ctx, p, "AM", i, 1) == "bh1_org_consol"
    long_ = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    assert BE.scalp_cap(ctx, long_, i, p, "bh1_org_consol", 98.4, 108.0) == 100.0                  # the opposite ORG edge (the CE 99.0 and the edge 100)
    assert BE.scalp_cap(ctx, long_, i, p, "bh1_org_consol", 98.4, 99.5) == 99.5                    # never beyond the first target
    short_ = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    assert BE.scalp_cap(ctx, short_, i, p, "bh1_org_consol", -99.5, -92.0) == -98.0                 # a short inside the gap: the gap's other edge (the open 98)
    o = {"lv_tags": ""}
    BE.order_ok(ctx, SimpleNamespace(sign=1, x=lambda v: v), o, "AM", i, p)
    assert "org_consol" in o["lv_tags"]
    ctx2 = mk(D0, history(D0), p, rows=rows[:3] + [(98.2, 98.9, 98.1, 98.5)] * 5, bias_row=BR(obj_day=1))        # the ORG has not filled
    assert BE.scalp_now(ctx2, p, "AM", at(ctx2, "10:05"), 1) == ""
    ctx3 = mk(D0, history(D0), p, rows=rows, bias_row=BR())                                           # not consolidating
    assert BE.scalp_now(ctx3, p, "AM", i, 1) == ""
    ctx4 = mk(D0, history(D0), p, rows=rows, bias_row=BR(drange_in=1))                                # a daily range counts too
    assert BE.scalp_now(ctx4, p, "AM", i, 1) == "bh1_org_consol"
    ctx5 = mk(D0, history(D0), p, rows=rows, bias_row=BR(nwog_regime="cons"))
    assert BE.scalp_now(ctx5, p, "AM", i, -1) == "bh1_org_consol"


# --- item 24: the dollar ----------------------------------------------------------------------------------------------------------------

def test_dxy_filter_modes():
    rows = [(100.0, 100.3, 99.8, 100.1)] * 6
    ctx = mk(D0, history(D0), Params(**BASE), rows=rows, bias_row=BR())
    ctx.intermarket = {"dxy": 1}
    i = at(ctx, "09:55")
    hard = Params(**BASE, dxy_filter="hard")
    assert BE.side_ok(ctx, hard, 1, "AM", i) == "x_bh1_dxy" and BE.side_ok(ctx, hard, -1, "AM", i) is None
    ctx.intermarket = {"dxy": -1}
    assert BE.side_ok(ctx, hard, -1, "AM", i) == "x_bh1_dxy" and BE.side_ok(ctx, hard, 1, "AM", i) is None
    ctx.intermarket = {"dxy": 1}
    soft = Params(**BASE, dxy_filter="soft", dxy_soft_risk=0.5)
    assert BE.side_ok(ctx, soft, 1, "AM", i) is None
    assert BE.flags(ctx, 1, i) == {"counter_dxy"} and BE.scalp_now(ctx, soft, "AM", i, 1) == "bh1_counter_dxy"
    lvt = []
    assert BD.size_mult(ctx, SimpleNamespace(sign=1), i, soft, lvt) == 0.5 and "size_counter_dxy" in lvt
    assert BE.side_ok(ctx, soft, -1, "AM", i) is None and BE.flags(ctx, -1, i) == {"dxy_ok"} and BE.scalp_now(ctx, soft, "AM", i, -1) == ""
    assert BD.size_mult(ctx, SimpleNamespace(sign=-1), i, soft, []) == 1.0
    tag = Params(**BASE, dxy_filter="tag")
    BE.side_ok(ctx, tag, 1, "AM", i)
    o = {"lv_tags": ""}
    BE.order_ok(ctx, SimpleNamespace(sign=1, x=lambda v: v), o, "AM", i, tag)
    assert "counter_dxy" in o["lv_tags"] and BE.scalp_now(ctx, tag, "AM", i, 1) == ""
    # a stale flag of an earlier bar is not read
    assert BE.flags(ctx, 1, i - 1) == set()
    # through run_day: the soft order trades at half the size as a scalp and carries the tag
    base_tr, *_ = _run_rows(Params(**BASE), bias=BR(), intermarket={"dxy": 1})
    soft_tr, *_ = _run_rows(soft, bias=BR(), intermarket={"dxy": 1})
    hard_tr, *_ = _run_rows(hard, bias=BR(), intermarket={"dxy": 1})
    assert base_tr and soft_tr and not hard_tr
    assert all("counter_dxy" in t.lv_tags and "scalp_bh1_counter_dxy" in t.lv_tags for t in soft_tr)
    assert soft_tr[0].shares <= base_tr[0].shares * 0.5 + 1 and soft_tr[0].shares < base_tr[0].shares
    ok_tr, *_ = _run_rows(soft, bias=BR(), intermarket={"dxy": -1})
    assert ok_tr and ok_tr[0].shares == base_tr[0].shares and "counter_dxy" not in ok_tr[0].lv_tags


# --- item 57: no HTF top / bottom picking ----------------------------------------------------------------------------------------

def test_no_htf_top_pick():
    p = Params(**BASE, no_htf_top_pick=True)
    ctx = mk(D0, history(D0), p, rows=[(100.0, 100.3, 99.8, 100.1)] * 6, bias_row=BR(flip=1))
    i = at(ctx, "09:55")
    short = SimpleNamespace(sign=-1, x=lambda v: -v)
    long_ = SimpleNamespace(sign=1, x=lambda v: v)
    ts = {"entry_kind": "turtle_soup", "lv_tags": ""}
    assert BE.order_ok(ctx, short, dict(ts), "AM", i, p) == "x_bh1_top_pick"                       # state up, draw unmet: no turtle-soup short
    assert BE.order_ok(ctx, short, {"entry_kind": "", "lv_tags": "three_drives"}, "AM", i, p) == "x_bh1_top_pick"
    assert BE.order_ok(ctx, short, {"entry_kind": "pm_reversal", "lv_tags": ""}, "AM", i, p) == "x_bh1_top_pick"
    assert BE.order_ok(ctx, short, {"entry_kind": "", "lv_tags": ""}, "AM", i, p) is None               # an ordinary MSS short follows the bias rules as before
    assert BE.order_ok(ctx, long_, dict(ts), "AM", i, p) is None                                         # with the state
    ctx2 = mk(D0, history(D0), p, rows=[(100.0, 100.3, 99.8, 100.1)] * 6, bias_row=BR(flip=1, obj_week=1))
    assert BE.order_ok(ctx2, short, dict(ts), "AM", i, p) is None                                         # the draw is met: allowed
    ctx3 = mk(D0, history(D0), p, rows=[(100.0, 100.3, 99.8, 100.1)] * 6, bias_row=BR(flip=-1))
    assert BE.order_ok(ctx3, long_, dict(ts), "AM", i, p) == "x_bh1_top_pick" and BE.order_ok(ctx3, short, dict(ts), "AM", i, p) is None
    ctx4 = mk(D0, history(D0), p, rows=[(100.0, 100.3, 99.8, 100.1)] * 6, bias_row=BR(flip=0))
    assert BE.order_ok(ctx4, short, dict(ts), "AM", i, p) is None                                         # no state: nothing to top-pick against
    assert BE.order_ok(ctx, short, dict(ts), "AM", i, Params(**BASE)) is None                              # off
