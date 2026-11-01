"""Caption-gap pass, package bias_htf#2/7: the ENGINE hooks of bh2e.py on the real DayCtx of hand-made days (second file of tests/test_caption_gap_bh2.py): the bias readings, the side gates, the scalps /
sizes / tags, the draw-lock adjustments and the per-bar lock changes, the inside-BISI release and a few full run_day paths."""
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import bh1e as BE, bh2e as B2, bias_day as BD, levels as L, manage as MG, strategy as S
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_review_fixes import BASE, D0, A_ROWS, day, history  # noqa: E402
from test_caption_gap_dwc1 import mk, at  # noqa: E402
from test_caption_gap_bh1 import BR, _run_rows  # noqa: E402
from test_caption_gap_bh1d import blocks  # noqa: E402
from test_caption_gap_bh1e import pad_to_0930, fake_mark, lk_of, FLAT  # noqa: E402
from test_caption_gap_dwc3 import _bisi_hist  # noqa: E402
NAN = float("nan")

FLATROWS = [(100.0, 100.3, 99.8, 100.1)] * 8


def order(entry=100.0, t1=104.0, **kw):
    return dict(dict(entry=entry, t1=t1, lv_tags="", levels=[t1]), **kw)


def sd_of(ctx, sign=1):
    return ctx.sides_map[sign]


def ctx_at(p, rows=None, bias_row=None, start="09:30", **kw):
    return mk(D0, history(D0), p, rows=FLATROWS if rows is None else rows, start=start, bias_row=bias_row, **kw)


# --- item 82: a week without an HTF draw ---------------------------------------------------------------------------------------------

def test_bias_neutral_scalp_week():
    p = Params(**BASE, bias_neutral="scalp_week", htf_bias="combo")
    ctx = ctx_at(p, bias_row=BR(combo=0))
    i = at(ctx, "09:55")
    assert BD.want_at(ctx, p, "AM", i) == 0
    assert BD.row_state(ctx, p, "AM", i).scalp == "bias_neutral"                          # the scalp reason is the Ep02.6 one (implemented once)
    lvt: list = []
    assert BD.size_mult(ctx, sd_of(ctx), i, p, lvt) == 0.5 and "size_scalp_week" in lvt    # reduced size
    ctx2 = ctx_at(p, bias_row=BR(combo=1, react=1))
    assert BD.size_mult(ctx2, sd_of(ctx2), i, p, []) == 1.0                                 # a week with a draw trades at full size
    assert BD.row_state(ctx2, p, "AM", i).scalp == ""
    p2 = Params(**BASE, bias_neutral="scalp", htf_bias="combo")
    assert BD.size_mult(ctx, sd_of(ctx), i, p2, []) == 1.0 and BD.row_state(ctx, p2, "AM", i).scalp == "bias_neutral"      # "scalp" (Ep02.6) is the same reading at full size
    # run_day: both sides trade as scalps at half risk on a neutral week; "skip" trades nothing
    tr0, *_ = _run_rows(Params(**BASE, htf_bias="combo"), bias=BR(combo=0))
    tr1, *_ = _run_rows(p, bias=BR(combo=0))
    assert not tr0 and tr1
    assert all("scalp_bias_neutral" in (t.lv_tags or "") and "size_scalp_week" in (t.lv_tags or "") for t in tr1)
    full, *_ = _run_rows(Params(**BASE, htf_bias="combo", bias_neutral="both"), bias=BR(combo=0))
    assert full and tr1[0].shares * 2 <= full[0].shares + 1 and len(tr1[0].exits) == 1       # half the size; one exit (no runners)


# --- item 86: the daily SIBI / BISI ----------------------------------------------------------------------------------------------------

def _sibi_ctx(p, price_rows, d_=-1, top=110.0, bot=100.0):
    return ctx_at(p, rows=price_rows, bias_row=BR(sibi_dir=d_, sibi_top=top, sibi_bot=bot, combo=0))


def test_sibi_gate():
    p = Params(**BASE, sibi_gate=True)
    # the zone 100-110 (CE 105): below the CE = only shorts
    c1 = _sibi_ctx(p, [(103.0, 103.2, 102.8, 103.0)] * 8)
    i = at(c1, "09:55")
    assert B2.side_ok(c1, p, 1, "AM", i) == "x_bh2_sibi" and B2.side_ok(c1, p, -1, "AM", i) is None
    assert B2.scalp_now(c1, p, "AM", i, -1) == ""
    # above the CE inside the zone: only longs, as scalps
    c2 = _sibi_ctx(p, [(107.0, 107.2, 106.8, 107.0)] * 8)
    assert B2.side_ok(c2, p, -1, "AM", i) == "x_bh2_sibi" and B2.side_ok(c2, p, 1, "AM", i) is None
    assert B2.scalp_now(c2, p, "AM", i, 1) == "bh2_sibi" and B2.scalp_now(c2, p, "AM", i, -1) == ""
    # above its high but no bar has held above it yet: still a scalp
    c3 = _sibi_ctx(p, [(108.0, 108.2, 107.8, 108.0)] * 3 + [(108.0, 111.5, 107.9, 111.2)] + [(111.2, 112.0, 108.0, 111.4)] * 4)
    assert B2.scalp_now(c3, p, "AM", at(c3, "09:55"), 1) == "bh2_sibi"
    # above its high with a following bar whose low holds above it: longs toward the buy-side pool, no scalp
    c4 = _sibi_ctx(p, [(108.0, 108.2, 107.8, 108.0)] * 3 + [(108.0, 111.5, 107.9, 111.2)] + [(111.2, 112.5, 111.1, 112.0)] * 4)
    assert B2.scalp_now(c4, p, "AM", at(c4, "09:55"), 1) == "" and B2.side_ok(c4, p, 1, "AM", at(c4, "09:55")) is None
    # the BISI mirror (a buy-side sweep): above the CE only longs; inside below the CE = shorts as scalps
    c5 = _sibi_ctx(p, [(107.0, 107.2, 106.8, 107.0)] * 8, d_=1)
    assert B2.side_ok(c5, p, -1, "AM", i) == "x_bh2_sibi" and B2.side_ok(c5, p, 1, "AM", i) is None
    c6 = _sibi_ctx(p, [(103.0, 103.2, 102.8, 103.0)] * 8, d_=1)
    assert B2.side_ok(c6, p, 1, "AM", i) == "x_bh2_sibi" and B2.scalp_now(c6, p, "AM", i, -1) == "bh2_sibi"
    # no zone: nothing
    c7 = ctx_at(p, bias_row=BR())
    assert B2.side_ok(c7, p, 1, "AM", i) is None and B2.sibi_state(c7, p, BR(), i) is None
    assert B2.side_ok(c1, Params(**BASE), 1, "AM", i) is None                            # switch off


# --- item 87: the 60m close beyond the wick CE; the 15m FVG's CE -------------------------------------------------------------------------

def _hours(last, n_flat=9):
    return [FLAT] * n_flat + [last]


def test_wick_ce_60m():
    p = Params(**BASE, wick_ce_60m=True)
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    # yesterday: open 100, high 108, low 90, close 100: the upper wick (100-108) has its CE at 104, the lower wick's at 95
    ctx = mk(D0, history(D0), p, rows=blocks(_hours((103.0, 104.3, 102.8, 103.8)), 12), start="00:00", bias_row=BR())
    assert ctx.wick["upper"] == 104.0 and ctx.wick["lower"] == 95.0
    i = at(ctx, "09:55")
    lk = lk_of(-1, 90.0, marked)
    assert B2.lock_bar(ctx, p, "AM", dict(lk), i, {"AM": False}, []) is None            # a wick to 104.3 with the close at 103.8: the lock stays
    ctx2 = mk(D0, history(D0), p, rows=blocks(_hours((103.0, 104.3, 102.8, 104.2)), 12), start="00:00", bias_row=BR())
    r = B2.lock_bar(ctx2, p, "AM", dict(lk), at(ctx2, "09:55"), {"AM": False}, [])
    assert r is not None and r[0]["side"] == 0 and r[0]["w60_done"] and r[1] is True    # a 60m close at 104.2 cancels the short lock (and a pending short)
    assert "wick_ce_60m" in r[0]["bh1"]
    # a long lock: the mirror (a 60m close under the lower-wick CE 95)
    ctx3 = mk(D0, history(D0), p, rows=blocks(_hours((96.0, 96.5, 94.5, 94.8)), 12), start="00:00", bias_row=BR())
    r3 = B2.lock_bar(ctx3, p, "AM", lk_of(1, 110.0, marked), at(ctx3, "09:55"), {"AM": False}, [])
    assert r3 is not None and r3[0]["side"] == 0
    assert B2.lock_bar(ctx2, Params(**BASE), "AM", dict(lk), at(ctx2, "09:55"), {"AM": False}, []) is None      # switch off
    assert B2.lock_bar(ctx2, p, "AM", dict(lk, delivered=True, delivered_i=at(ctx2, "09:30")), at(ctx2, "09:55"), {"AM": True}, []) is None      # a delivered lock is done
    # through the engine hook (_lock_step): the lock becomes neutral
    assert B2.lock_on(p) and not B2.lock_on(Params(**BASE))


def test_sibi15_ce_cancel():
    p = Params(**BASE, sibi15_ce_cancel=True)
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    spec = [FLAT] * 36 + [(104.0, 104.2, 103.5, 103.6), (103.6, 103.7, 101.5, 101.8), (101.8, 102.0, 101.0, 101.6)]            # a bear FVG 102.0-103.5 (CE 102.75) forms by 09:44
    ctx = mk(D0, history(D0), p, rows=blocks(spec, 3), start="00:00", bias_row=BR())
    i = at(ctx, "09:40")
    lk = lk_of(-1, 90.0, marked)
    assert B2.lock_bar(ctx, p, "AM", dict(lk), i, {"AM": False}, []) is None            # no trade above the CE since the gap formed
    spec2 = spec + [(101.6, 103.0, 101.5, 102.5)]                                         # a 4th 15m bar trades to 103.0, above the CE
    ctx2 = mk(D0, history(D0), p, rows=blocks(spec2, 3), start="00:00", bias_row=BR())
    r = B2.lock_bar(ctx2, p, "AM", dict(lk), at(ctx2, "09:55"), {"AM": False}, [])
    assert r is not None and r[0]["side"] == 0 and "sibi15_ce" in r[0]["bh1"]


# --- item 88: the reversal after the target ----------------------------------------------------------------------------------------------

def test_reversal_after_target(monkeypatch):
    p = Params(**BASE, allow_reversal_after_target=True, no_trade_after_win=True)
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    rows = pad_to_0930([(100.0, 100.1, 99.9, 100.0)] * 3) + [(99.5, 99.6, 90.0, 91.0),             # 09:30 delivers the sell-side draw (90)
                                                           (91.0, 92.5, 89.5, 92.0),                 # 09:35 wicks to 89.5 into the bullish breaker (top 90.5)
                                                           (92.0, 93.0, 91.5, 92.8), (92.8, 93.2, 92.0, 93.0), (93.0, 93.5, 92.6, 93.3), (93.3, 93.6, 93.0, 93.5)]
    ctx = mk(D0, history(D0), p, rows=rows, start="00:00", bias_row=BR())
    ctx.state7 = {}
    d0 = at(ctx, "09:30")
    zone = L.Zone("bull", 90.5, 88.0, 3, src=2)
    monkeypatch.setattr(L, "breakers", lambda *a, **k: [L.Zone("bull", 90.5, 88.0, 1, src=0)])
    fake_mark(monkeypatch, marked, side=1, target=110.0)
    lk = lk_of(-1, 90.0, marked, delivered=True, delivered_i=d0)
    state = {"day_done": True, "stops": {"day": "win"}}
    done = {"AM": True}
    assert B2.lock_bar(ctx, p, "AM", dict(lk), at(ctx, "09:35") + 1, done, [], state) is None       # the 3 bars after the wick have not closed yet
    r = B2.lock_bar(ctx, p, "AM", dict(lk), at(ctx, "09:35") + 3, done, [], state)
    assert r is not None and r[0]["side"] == 1 and r[0]["rev_after_target"] and "reversal_after_target" in r[0]["bh2"] and done["AM"] is False
    # a body back under the wick low (89.5) inside the 3 bars: no reversal
    rows2 = list(rows)
    rows2[len(rows2) - 4] = (92.0, 93.0, 88.0, 89.0)
    ctx2 = mk(D0, history(D0), p, rows=rows2, start="00:00", bias_row=BR())
    ctx2.state7 = {}
    assert B2.lock_bar(ctx2, p, "AM", dict(lk), at(ctx2, "09:35") + 3, {"AM": True}, [], state) is None
    # a day closed by something other than the winner (a drange / loss stop) is not reopened
    assert B2.lock_bar(ctx, p, "AM", dict(lk), at(ctx, "09:35") + 3, {"AM": True}, [], {"day_done": True, "stops": {"day": "done_target"}}) is None
    assert B2.lock_bar(ctx, Params(**BASE), "AM", dict(lk), at(ctx, "09:35") + 3, {"AM": True}, [], state) is None
    # the PM Silver Bullet after a winning AM trade whose lock reversed
    win = SimpleNamespace(exits=[(pd.Timestamp("2026-06-23 10:00", tz="America/New_York"), 91.0, 1, "t1")], session="AM", stop_day=None, slow_chop=False, date=D0, pnl=lambda c: (5.0, 0.0))
    cx = SimpleNamespace(day=D0, risk_view={"trades": [win], "rs0": None}, lock={"AM": dict(side=1, rev_after_target=True)})
    ts = pd.Timestamp("2026-06-23 14:00", tz="America/New_York")
    assert MG.extras_blocked(cx, Params(**BASE, no_trade_after_win=True), "SB_PM", ts) is True              # the X14d day stop ("any winner ends the day")
    assert MG.extras_blocked(cx, p, "SB_PM", ts) is False                                                   # the reversal lock lifts it for the PM family
    assert MG.extras_blocked(cx, p, "SB_AM", ts) is True                                                    # ... not the morning
    cx2 = SimpleNamespace(day=D0, risk_view={"trades": [win], "rs0": None}, lock={"AM": dict(side=-1)})
    assert MG.extras_blocked(cx2, p, "SB_PM", ts) is True                                                   # no reversal: the day stays stopped


# --- item 90: the soft carry -------------------------------------------------------------------------------------------------------------

def _carry_ctx(p, rows=None, prior=None, row=None):
    ctx = mk(D0, history(D0), p, rows=rows or pad_to_0930([(100.0, 100.1, 99.9, 100.0)] * 3), start="00:00", bias_row=row or BR(flip=1))
    prev = D0 - timedelta(days=1)
    ctx.prior_locks = [dict(day=prev, session="PM", side=1, target=110.0, kind="pool", name="pdh1", delivered=False, flip=1)] if prior is None else prior
    return ctx


def test_soft_carry():
    p = Params(**BASE, soft_carry=True)
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    ctx = _carry_ctx(p)
    kl = S._idx_at(ctx, 570)
    out = B2.lock_post(ctx, p, BR(flip=1), 570, "AM", kl, 100.0, lk_of(0, None, marked))
    assert out["side"] == 1 and out["target"] == 110.0 and out["name"] == "soft_carry" and "soft_carry" in out["bh2"] and out["flip"] == 1
    # an own (non-neutral) lock is kept
    keep = B2.lock_post(ctx, p, BR(flip=1), 570, "AM", kl, 100.0, lk_of(-1, 90.0, marked))
    assert keep["side"] == -1 and "soft_carry" not in keep.get("bh2", [])
    # dropped: the flip state changed / the carried lock was delivered / its target traded overnight / the opposing pool was taken overnight
    assert B2.lock_post(ctx, p, BR(flip=-1), 570, "AM", kl, 100.0, lk_of(0, None, marked))["side"] == 0
    gone = _carry_ctx(p, prior=[dict(day=D0 - timedelta(days=1), session="PM", side=1, target=110.0, delivered=True, flip=1)])
    assert B2.lock_post(gone, p, BR(flip=1), 570, "AM", kl, 100.0, lk_of(0, None, marked))["side"] == 0
    hi = _carry_ctx(p, rows=pad_to_0930([(100.0, 111.0, 99.9, 100.0)] * 3))
    assert B2.lock_post(hi, p, BR(flip=1), 570, "AM", kl, 100.0, lk_of(0, None, marked))["side"] == 0
    lo = _carry_ctx(p, rows=pad_to_0930([(100.0, 100.1, 89.0, 100.0)] * 3))
    assert B2.lock_post(lo, p, BR(flip=1), 570, "AM", kl, 100.0, lk_of(0, None, marked))["side"] == 0
    assert B2.lock_post(_carry_ctx(p, prior=[]), p, BR(flip=1), 570, "AM", kl, 100.0, lk_of(0, None, marked))["side"] == 0
    assert B2.lock_post(ctx, Params(**BASE), BR(flip=1), 570, "AM", kl, 100.0, lk_of(0, None, marked))["side"] == 0     # switch off
    # a carry from a week ago is no carry
    old = _carry_ctx(p, prior=[dict(day=D0 - timedelta(days=9), session="PM", side=1, target=110.0, delivered=False, flip=1)])
    assert B2.lock_post(old, p, BR(flip=1), 570, "AM", kl, 100.0, lk_of(0, None, marked))["side"] == 0
    # half the size, no adds, the tag
    ctx.lock = {"AM": out}
    i = at(ctx, "09:55")
    lvt: list = []
    assert BD.size_mult(ctx, sd_of(ctx), i, p, lvt) == 0.5 and "size_soft_carry" in lvt
    o = order()
    assert B2.order_ok(ctx, sd_of(ctx), o, "AM", i, p) is None and "soft_carry" in o["lv_tags"] and o["no_adds"] is True
    assert BD.size_mult(ctx, sd_of(ctx, -1), i, p, []) == 1.0


# --- item 91: the inside-BISI release ---------------------------------------------------------------------------------------------------

def test_inside_bisi_release(monkeypatch):
    p = Params(**BASE, inside_bisi_release=True, sloppy_tests=("inside_bisi",))
    h = _bisi_hist()
    assert B2.inside_zone(h) == (110.0, 100.0)
    assert B2.inside_zone(h[:3]) is None
    ctx = ctx_at(p, rows=[(105.0, 110.5, 104.0, 108.0)] * 3)
    ctx.inside_zone, ctx.inside_side = (110.0, 100.0), 0
    i = at(ctx, "09:40")
    assert B2.sloppy_release(ctx, p, {"inside_bisi"}, i) == {"inside_bisi"}               # 110.5 is not 1 point beyond the high
    assert B2.side_ok(ctx, p, 1, "AM", i) is None
    ctx2 = ctx_at(p, rows=[(105.0, 110.5, 104.0, 108.0), (108.0, 111.25, 107.0, 111.0), (111.0, 111.5, 109.0, 110.0)])
    ctx2.inside_zone, ctx2.inside_side = (110.0, 100.0), 0
    i2 = at(ctx2, "09:40")
    assert B2.sloppy_release(ctx2, p, {"inside_bisi", "big_prev"}, i2) == {"big_prev"}    # a trade at 111.25: released (other reasons stay)
    assert ctx2.inside_side == 1 and B2.side_ok(ctx2, p, -1, "AM", i2) == "x_bh2_inside_release" and B2.side_ok(ctx2, p, 1, "AM", i2) is None
    ctx3 = ctx_at(p, rows=[(105.0, 106.0, 98.5, 100.5)])
    ctx3.inside_zone, ctx3.inside_side = (110.0, 100.0), 0
    B2.sloppy_release(ctx3, p, {"inside_bisi"}, at(ctx3, "09:30"))
    assert ctx3.inside_side == -1                                                          # beyond the low: shorts only
    # run_day (the day is an inside_bisi day by fiat; its zone top 99 is already beaten by the flat overnight highs of 100.2): the stand-aside stops the day; released, only longs trade
    monkeypatch.setattr(S, "sloppy_day", lambda hist, day_, p_, open_px=None: {"inside_bisi"})
    monkeypatch.setattr(B2, "inside_zone", lambda hist: (99.0, 90.0))
    from test_review_fixes import A_LOCK
    sk0, sk1 = [], []
    t0 = S.run_day(day(A_ROWS, d=D0, start="09:50", spike=True), history(D0), "ES", Params(**BASE, sloppy_tests=("inside_bisi",)), 5, locks=[], log=[], skips=sk0, bias_by_cut=A_LOCK)
    assert t0 == [] and sk0 and sk0[0][2] == "sloppy"                                    # the built stand-aside: nothing
    t1 = S.run_day(day(A_ROWS, d=D0, start="09:50", spike=True), history(D0), "ES", p, 5, locks=[], log=[], skips=sk1, bias_by_cut=A_LOCK)
    assert not any(x[2] == "sloppy" for x in sk1) and t1 and all(t.side == "long" for t in t1)


# --- the bias readings (bias_value / want_at) --------------------------------------------------------------------------------------------

def test_bias_value_adjust():
    p = Params(**BASE, htf_bias="combo", htf_bias_tf="M")
    assert BD.bias_value(BR(combo=-1, bias_m=1, bias_w=-1), p) == 1                     # monthly first
    assert BD.bias_value(BR(combo=1, bias_m=0, bias_w=-1), p) == -1                     # monthly unclear: the weekly
    assert BD.bias_value(BR(combo=1, bias_m=0, bias_w=0), p) == 0                       # both unclear: no HTF bias
    w = Params(**BASE, htf_bias="combo", htf_bias_tf="W")
    assert BD.bias_value(BR(combo=1, bias_m=1, bias_w=-1), w) == -1                     # the weekly draw: -1 under "W"
    assert BD.bias_value(BR(combo=1, bias_m=1, bias_w=-1), Params(**BASE, htf_bias="combo")) == 1
    # the 75 % quadrant confirmation
    q = Params(**BASE, htf_bias="flip", wk_q75_confirm=True)
    assert BD.bias_value(BR(flip=1, wk_q75=0), q) == 0 and BD.bias_value(BR(flip=1, wk_q75=1), q) == 1 and BD.bias_value(BR(flip=1, wk_q75=-1), q) == 0
    assert BD.bias_value(BR(flip=-1, wk_q75=-1), q) == -1
    # B17.3 neutral vs reverse after the draw
    n = Params(**BASE, htf_bias="combo", objective_neutral="both")
    r = Params(**BASE, htf_bias="combo", objective_neutral="both", htf_after_draw="reverse")
    row = BR(combo=1, obj_week=1, after_draw_w=-1)
    assert BD.bias_value(row, n) == 0 and BD.bias_value(row, r) == -1                    # a weekly draw hit at a weekly array: 0 under "neutral", the opposite state under "reverse"
    assert BD.bias_value(BR(combo=1, obj_day=1, after_draw_d=-1), r) == -1 and BD.bias_value(BR(combo=1, obj_day=1, after_draw_d=0), r) == 0
    assert BD.bias_value(BR(combo=1, obj_week=1), r) == 0                                 # a pool draw: neutral
    # a fast weekly draw keeps the bias
    f = Params(**BASE, htf_bias="combo", objective_neutral="week", fast_draw_extend=True)
    assert BD.bias_value(BR(combo=1, obj_week=1, fast_draw=1, fast_next=120.0), f) == 1
    assert BD.bias_value(BR(combo=1, obj_week=1, fast_draw=0), f) == 0


def test_want_adjust_fallbacks():
    ctx_row = BR(combo=0, qshift=-1, qs_form="retrace", eq_near=1, last_break=1, raid_profile=1, q_window=0)
    p = Params(**BASE, htf_bias="combo", qshift_bias=True)
    ctx = ctx_at(p, bias_row=ctx_row)
    i = at(ctx, "09:55")
    assert BD.want_at(ctx, p, "AM", i) == -1                                             # a neutral bias takes the quarterly shift
    c2 = ctx_at(p, bias_row=dict(ctx_row, combo=1, react=1))
    assert BD.want_at(c2, p, "AM", i) == 1                                                # a bias that exists is kept
    s = Params(**BASE, htf_bias="combo", qshift_bias=True, qshift_strong_consol=True)
    c3 = ctx_at(s, bias_row=dict(ctx_row, qs_form="consol"))
    assert BD.want_at(c3, s, "AM", i) == 0                                                # a consolidation-form shift does not change the bias
    # the daily SMT
    d = Params(**BASE, htf_bias="combo", dsmt_bias=True)
    c4 = ctx_at(d, bias_row=BR(combo=0))
    c4.intermarket = {"dsmt": 1}
    assert BD.want_at(c4, d, "AM", i) == 1
    g = Params(**BASE, htf_bias="combo", dsmt_bias=True, q_window_gate=True)
    c5 = ctx_at(g, bias_row=BR(combo=0, q_window=0))
    c5.intermarket = {"dsmt": 1}
    assert BD.want_at(c5, g, "AM", i) == 0                                                # a time filter: only inside the window
    c6 = ctx_at(g, bias_row=BR(combo=0, q_window=1))
    c6.intermarket = {"dsmt": 1}
    assert BD.want_at(c6, g, "AM", i) == 1
    # the raid profile, the EQ tie-break
    rp = Params(**BASE, htf_bias="combo", raid_profile_bias=True)
    assert BD.want_at(ctx_at(rp, bias_row=BR(combo=0, raid_profile=1)), rp, "AM", i) == 1
    eq = Params(**BASE, htf_bias="combo", eq_tiebreak=True)
    assert BD.want_at(ctx_at(eq, bias_row=BR(combo=0, eq_near=1, last_break=1)), eq, "AM", i) == 1       # price at the EQ, the last structure break a high: long
    assert BD.want_at(ctx_at(eq, bias_row=BR(combo=0, eq_near=0, last_break=1)), eq, "AM", i) == 0
    assert BD.want_at(ctx_at(eq, bias_row=BR(combo=0, eq_near=0, last_break=1, eq_near_m=1, last_break_m=-1)), eq, "AM", i) == -1       # the monthly EQ: the monthly structure
    assert BD.want_at(ctx_at(eq, bias_row=BR(combo=0, eq_near=1, last_break=0)), eq, "AM", i) == 0       # no break: no bias
    off = Params(**BASE, htf_bias="combo")
    assert BD.want_at(ctx_at(off, bias_row=ctx_row), off, "AM", i) == 0


# --- side gates and order rules -----------------------------------------------------------------------------------------------------------

def test_raid_side_and_extreme_pause_gates():
    p = Params(**BASE, raid_side_gate=True, ipda_extreme_pause=True)
    ctx = ctx_at(p, bias_row=BR(raid_side60=1, ipda_pause=0))
    i = at(ctx, "09:55")
    assert B2.side_ok(ctx, p, -1, "AM", i) == "x_bh2_raid_side" and B2.side_ok(ctx, p, 1, "AM", i) is None       # buy stops taken repeatedly: no shorts
    c2 = ctx_at(p, bias_row=BR(raid_side60=-1))
    assert B2.side_ok(c2, p, 1, "AM", i) == "x_bh2_raid_side" and B2.side_ok(c2, p, -1, "AM", i) is None
    c3 = ctx_at(p, bias_row=BR(ipda_pause=-1))
    assert B2.side_ok(c3, p, -1, "AM", i) == "x_bh2_ipda_pause" and B2.side_ok(c3, p, 1, "AM", i) is None     # the prior low at the 60-day low: no shorts
    c4 = ctx_at(p, bias_row=BR(ipda_pause=1))
    assert B2.side_ok(c4, p, 1, "AM", i) == "x_bh2_ipda_pause"
    assert B2.side_ok(ctx, Params(**BASE), -1, "AM", i) is None


def test_pd_two_level():
    p = Params(**BASE, pd_two_level=True)
    ctx = ctx_at(p, bias_row=BR(eq20_body=102.0))
    i = at(ctx, "09:55")
    sd = sd_of(ctx)
    o = order(entry=101.0)
    assert B2.order_ok(ctx, sd, o, "AM", i, p) is None and "htf_discount" in o["lv_tags"]      # below the 20-session body-range EQ
    assert B2.order_ok(ctx, sd, order(entry=103.0), "AM", i, p) == "x_bh2_pd_two_level"        # a leg-discount long above the EQ is rejected
    sh = sd_of(ctx, -1)
    assert B2.order_ok(ctx, sh, order(entry=-103.0), "AM", i, p) is None                         # side space: the short at 103 is above the EQ
    assert B2.order_ok(ctx, sh, order(entry=-101.0), "AM", i, p) == "x_bh2_pd_two_level"
    nan_ctx = ctx_at(p, bias_row=BR())
    assert B2.order_ok(nan_ctx, sd, order(entry=103.0), "AM", i, p) is None                      # no range known: no filter


def test_tier_regime_gate():
    p = Params(**BASE, tier_regime_gate=True)
    ctx = ctx_at(p, bias_row=BR(tier_regime=-1, tier_ith=104.0))
    i = at(ctx, "09:55")
    sd = sd_of(ctx)
    assert B2.order_ok(ctx, sd, order(entry=100.0, t1=106.0), "AM", i, p) == "x_bh2_tier_regime"   # a long targeting above the defended ITH
    o = order(entry=100.0, t1=103.0)
    assert B2.order_ok(ctx, sd, o, "AM", i, p) is None and "tier_regime" in o["lv_tags"]
    assert B2.order_ok(ctx, sd_of(ctx, -1), order(entry=-100.0, t1=-95.0), "AM", i, p) is None      # shorts are the regime's trade
    assert B2.targets_post(ctx, sd, i, p, 100.0, [(102.0, "pool"), (106.0, "pool")]) == [(102.0, "pool")]      # no target above the ITH
    t = Params(**BASE, tier_regime_gate=True, tug_required=True)
    assert B2.order_ok(ctx, sd, order(entry=100.0, t1=106.0), "AM", i, t) is None                  # the regime needs the tug of war too
    c2 = ctx_at(t, bias_row=BR(tier_regime=-1, tier_ith=104.0, tug_spec=-1))
    assert B2.order_ok(c2, sd, order(entry=100.0, t1=106.0), "AM", i, t) == "x_bh2_tier_regime"
    c3 = ctx_at(p, bias_row=BR(tier_regime=0))
    assert B2.order_ok(c3, sd, order(entry=100.0, t1=106.0), "AM", i, p) is None
    # a neutral lock goes to the regime's side
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    kl = S._idx_at(ctx, 570)
    lk = B2.lock_post(ctx, p, BR(tier_regime=-1, tier_ith=104.0), 570, "AM", kl, 100.0, lk_of(0, None, marked))
    assert lk["side"] == -1 and lk["target"] == 90.0 and "tier_regime" in lk["bh2"]


def test_consol_dir():
    f = Params(**BASE, consol_dir="first_expansion")
    rng = dict(drange_hi=110.0, drange_lo=100.0)
    ctx = ctx_at(f, bias_row=BR(drange_in=1, drange=0, **rng))
    i = at(ctx, "09:55")
    assert B2.side_ok(ctx, f, 1, "AM", i) == "x_bh2_consol_wait" and B2.side_ok(ctx, f, -1, "AM", i) == "x_bh2_consol_wait"      # no trades inside the range
    c2 = ctx_at(f, bias_row=BR(drange_in=0, drange=1, **rng))
    assert B2.side_ok(c2, f, -1, "AM", i) == "x_bh2_consol_side" and B2.side_ok(c2, f, 1, "AM", i) is None                       # after the breakout: its side only
    sd = sd_of(c2)
    assert B2.order_ok(c2, sd, order(entry=107.0), "AM", i, f) is None                                                           # at / below EQ + 25 % of the range (107.5)
    assert B2.order_ok(c2, sd, order(entry=108.0), "AM", i, f) == "x_bh2_consol_chase"                                           # a chase
    c3 = ctx_at(f, bias_row=BR(drange_in=0, drange=-1, **rng))
    assert B2.order_ok(c3, sd_of(c3, -1), order(entry=-103.0), "AM", i, f) is None and B2.order_ok(c3, sd_of(c3, -1), order(entry=-102.0), "AM", i, f) == "x_bh2_consol_chase"
    c4 = ctx_at(f, bias_row=BR())
    assert B2.side_ok(c4, f, 1, "AM", i) is None                                                                                 # no range at all
    s = Params(**BASE, consol_dir="prior_strongest")
    c5 = ctx_at(s, bias_row=BR(drange_in=1, consol_prior=1, **rng))
    assert B2.side_ok(c5, s, -1, "AM", i) == "x_bh2_consol_prior" and B2.side_ok(c5, s, 1, "AM", i) is None
    assert B2.order_ok(c5, sd_of(c5), order(entry=104.0), "AM", i, s) is None and B2.order_ok(c5, sd_of(c5), order(entry=106.0), "AM", i, s) == "x_bh2_consol_discount"      # buy in the discount below EQ
    c6 = ctx_at(s, bias_row=BR(drange_in=0, consol_prior=1, **rng))
    assert B2.side_ok(c6, s, -1, "AM", i) is None                                                                                # outside a range nothing applies


def _swing_ctx(p, bias_row=None):
    spec = [(100.0, 101.0, 99.0, 100.5), (100.5, 105.0, 100.0, 104.0), (104.0, 105.0, 101.0, 102.0), (102.0, 103.0, 100.0, 101.0), (101.0, 102.0, 95.0, 96.0), (96.0, 99.0, 95.5, 98.0),
            (98.0, 100.0, 97.0, 99.0), (99.0, 99.5, 98.0, 98.5), (98.5, 99.0, 98.0, 98.4)]
    return mk(D0, history(D0), p, rows=blocks(spec, 12), start="00:00", bias_row=bias_row if bias_row is not None else BR())


def test_range_no_bias():
    p = Params(**BASE, range_no_bias=True)
    ctx = _swing_ctx(p)
    i = at(ctx, "09:55")
    rng = B2.swing60(ctx, i)
    assert rng is not None and rng[0] > rng[1]
    hi, lo = rng
    pos = lo + 0.62 * (hi - lo)
    sh = sd_of(ctx, -1)
    assert B2.order_ok(ctx, sh, order(entry=-(pos + 0.5)), "AM", i, p) is None                      # a short in the premium of the swing range
    assert B2.order_ok(ctx, sh, order(entry=-(pos - 1.0)), "AM", i, p) == "x_bh2_range_loc"          # a short at 50 %: rejected
    neg = lo + 0.38 * (hi - lo)
    sl = sd_of(ctx, 1)
    assert B2.order_ok(ctx, sl, order(entry=neg - 0.5), "AM", i, p) is None and B2.order_ok(ctx, sl, order(entry=neg + 1.0), "AM", i, p) == "x_bh2_range_loc"
    assert B2.scalp_now(ctx, p, "AM", i, -1) == "bh2_range"
    cap = B2.scalp_cap(ctx, sh, i, p, "bh2_range", -(pos + 0.5), -(lo))
    assert cap == pytest.approx(sh.x(lo - 0.25))                                                      # a single target one tick beyond the opposite swing extreme
    assert B2.scalp_cap(ctx, sl, i, p, "bh2_range", neg - 0.5, 200.0) == pytest.approx(hi + 0.25)
    # a biased session is not a range trade
    pb = Params(**BASE, range_no_bias=True, htf_bias="combo")
    cb = _swing_ctx(pb, bias_row=BR(combo=1, react=1))
    assert B2.order_ok(cb, sd_of(cb, 1), order(entry=neg + 1.0), "AM", i, pb) is None and B2.scalp_now(cb, pb, "AM", i, 1) == ""
    assert B2.scalp_now(ctx, Params(**BASE), "AM", i, -1) == ""


def test_pd3_and_qshift_scalps():
    p = Params(**BASE, pd3_first_caution=True, qshift_strong_consol=True)
    ctx = ctx_at(p, bias_row=BR(flip=-1, pd3_n=1))
    i = at(ctx, "09:55")
    assert B2.scalp_now(ctx, p, "AM", i, -1) == "bh2_pd3"                                          # the first adverse array is closed through: shorts are scalps
    assert B2.scalp_now(ctx, p, "AM", i, 1) == ""
    assert B2.scalp_now(ctx_at(p, bias_row=BR(flip=-1, pd3_n=0)), p, "AM", i, -1) == ""
    assert B2.scalp_now(ctx_at(p, bias_row=BR(flip=-1, pd3_n=3)), p, "AM", i, -1) == ""
    c2 = ctx_at(p, bias_row=BR(qs_scalp=1))
    assert B2.scalp_now(c2, p, "AM", i, 1) == "bh2_qshift_consol" and B2.scalp_now(c2, p, "AM", i, -1) == "bh2_qshift_consol"


def test_decoupled_scalp():
    p = Params(**BASE, decoupled_scalp=True)
    ctx = ctx_at(p, bias_row=BR())
    ctx.intermarket = {"dxy": 1, "spx20": 1}                                                         # the index up with the dollar up: not in harmony
    i = at(ctx, "09:55")
    assert B2.decoupled(ctx, p) is True and B2.scalp_now(ctx, p, "AM", i, 1) == "bh2_decoupled"
    ctx.intermarket = {"dxy": -1, "spx20": 1}
    assert B2.decoupled(ctx, p) is False and B2.scalp_now(ctx, p, "AM", i, 1) == ""
    ctx.intermarket = {"dxy": -1, "spx20": 1, "crb": -1}                                              # a commodity leg that disagrees
    assert B2.decoupled(ctx, p) is True
    ctx.intermarket = {"spx20": 1}
    assert B2.decoupled(ctx, p) is None                                                              # a leg missing: nothing
    o = order()
    ctx.intermarket = {"dxy": 1, "spx20": 1}
    B2.order_ok(ctx, sd_of(ctx), o, "AM", i, p)
    assert "decoupled" in o["lv_tags"]


def test_iof_weekly_size_and_tags():
    p = Params(**BASE, iof_weekly_weight=True)
    ctx = ctx_at(p, bias_row=BR(iof_w=1))
    i = at(ctx, "09:55")
    lvt: list = []
    assert B2.size_mult(ctx, sd_of(ctx, 1), i, p, lvt) == 1.0                                        # agrees: full size
    assert B2.size_mult(ctx, sd_of(ctx, -1), i, p, lvt) == 0.5 and "size_iof_w" in lvt               # against the weekly order flow: half
    o1, o2 = order(), order(entry=-100.0, t1=-96.0)
    B2.order_ok(ctx, sd_of(ctx, 1), o1, "AM", i, p)
    B2.order_ok(ctx, sd_of(ctx, -1), o2, "AM", i, p)
    assert "iof_w_agree" in o1["lv_tags"] and "iof_w_oppose" in o2["lv_tags"]
    assert B2.size_mult(ctx_at(p, bias_row=BR(iof_w=0)), sd_of(ctx, -1), i, p, []) == 1.0


def test_order_tags_from_the_table_and_intermarket():
    p = Params(**BASE, q_days_tag=True, shift_due_tag=True, qshift_bias=True, dsmt_bias=True, dxy_needs_rates=True, im_regime_tag=True, htf_after_draw="reverse", fast_draw_extend=True,
               objective_neutral="week", sibi_gate=True, htf_bias="combo")
    ctx = ctx_at(p, bias_row=BR(q_window=1, shift_due=1, qshift=-1, qs_form="retrace", obj_week=1, after_draw_w=-1, fast_draw=0, sibi_dir=-1, sibi_top=110.0, sibi_bot=100.0))
    ctx.intermarket = {"dsmt": 1, "rates_dxy_agree": -1, "im_regime": "bwith_dagainst"}
    i = at(ctx, "09:55")
    o = order()
    assert B2.order_ok(ctx, sd_of(ctx), o, "AM", i, p) is None
    tags = set(o["lv_tags"].split("|"))
    pg = Params(**BASE, dsmt_bias=True, q_window_gate=True, htf_bias="combo")                 # q_window_gate: the daily-SMT tag counts only inside the q_window
    cg = ctx_at(pg, bias_row=BR(q_window=0))
    cg.intermarket = {"dsmt": 1}
    og = order()
    B2.order_ok(cg, sd_of(cg), og, "AM", at(cg, "09:55"), pg)
    assert not any(t.startswith("dsmt_") for t in (og.get("lv_tags") or "").split("|"))
    cg2 = ctx_at(pg, bias_row=BR(q_window=1))
    cg2.intermarket = {"dsmt": 1}
    og2 = order()
    B2.order_ok(cg2, sd_of(cg2), og2, "AM", at(cg2, "09:55"), pg)
    assert any(t.startswith("dsmt_") for t in og2["lv_tags"].split("|"))
    assert {"q_window", "shift_due", "qshift_retrace", "after_draw_reverse", "dsmt_" + B2.season(D0, 1), "rates_diverge", "im_bwith_dagainst"} <= tags
    assert any(t.startswith("sibi_") for t in tags)
    assert B2.season(date(2026, 7, 1)) == "short" and B2.season(date(2026, 11, 3)) == "trend" and B2.season(date(2026, 2, 3)) == "trend"           # a bullish SMT: trend change in the bullish windows, short-term in summer
    assert B2.season(date(2026, 1, 12), -1) == "trend" and B2.season(date(2026, 7, 1), -1) == "trend" and B2.season(date(2026, 11, 3), -1) == "short"   # a bearish SMT: strongest in January / May-Jul, short-term in a bullish window
    o2 = order()
    ctx.intermarket = {"rates_dxy_agree": 1}
    B2.order_ok(ctx, sd_of(ctx), o2, "AM", i, p)
    assert "rates_agree" in o2["lv_tags"]


def test_dxy_needs_rates():
    p = Params(**BASE, dxy_filter="tag", dxy_needs_rates=True)
    ctx = ctx_at(p, bias_row=BR())
    i = at(ctx, "09:55")
    ctx.intermarket = {"dxy": 1, "rates_dxy_agree": -1}                                               # the yields disagree with the dollar: it does not count
    BE.side_ok(ctx, p, 1, "AM", i)
    assert "counter_dxy" not in BE.flags(ctx, 1, i)
    ctx.intermarket = {"dxy": 1, "rates_dxy_agree": 1}
    BE.side_ok(ctx, p, 1, "AM", i)
    assert "counter_dxy" in BE.flags(ctx, 1, i)
    q = Params(**BASE, dxy_filter="tag")
    ctx.intermarket = {"dxy": 1, "rates_dxy_agree": -1}
    BE.side_ok(ctx, q, 1, "AM", i)
    assert "counter_dxy" in BE.flags(ctx, 1, i)                                                       # without the switch the dollar counts as before


# --- lock candidates and adjustments ------------------------------------------------------------------------------------------------------

def test_lock_cands_and_lock_post_adjustments():
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1), (95.0, "pool", "ipda20l", -1), (120.0, "pool", "ipda20h", 1)]
    # the next weekly array beyond a fast weekly draw
    p = Params(**BASE, fast_draw_extend=True)
    assert B2.lock_cands(None, p, BR(fast_draw=1, fast_next=130.0), 570, 0) == [(130.0, "array", "fast_draw_next", 0, 0)]
    assert B2.lock_cands(None, p, BR(fast_draw=0, fast_next=130.0), 570, 0) == [] and B2.lock_cands(None, Params(**BASE), BR(fast_draw=1, fast_next=130.0), 570, 0) == []
    ctx = ctx_at(p, rows=pad_to_0930([(100.0, 100.1, 99.9, 100.0)] * 3), start="00:00")
    kl = S._idx_at(ctx, 570)
    # item 93: the next weekly array is FORCED as the target when the weekly draw was reached fast (not only offered as a candidate that a nearer pool beats)
    f1 = B2.lock_post(ctx, p, BR(fast_draw=1, fast_next=130.0), 570, "AM", kl, 100.0, lk_of(1, 110.0, marked))
    assert f1["side"] == 1 and f1["target"] == 130.0 and f1["name"] == "fast_draw_next"
    assert B2.lock_post(ctx, p, BR(fast_draw=1, fast_next=130.0), 570, "AM", kl, 100.0, lk_of(0, None, marked))["target"] == 130.0
    assert B2.lock_post(ctx, p, BR(fast_draw=1, fast_next=130.0), 570, "AM", kl, 100.0, lk_of(-1, 90.0, marked))["target"] == 90.0     # an opposite lock is left alone
    assert B2.lock_post(ctx, p, BR(fast_draw=1, fast_next=NAN), 570, "AM", kl, 100.0, lk_of(1, 110.0, marked))["target"] == 110.0       # no next array: the ordinary lock stands
    # q_obj_lean: a neutral lock leans to the weekly array
    q = Params(**BASE, q_obj_lean=True)
    out = B2.lock_post(ctx, q, BR(q_obj=70.0), 570, "AM", kl, 100.0, lk_of(0, None, marked))
    assert out["side"] == -1 and out["target"] == 70.0 and out["name"] == "q_obj"
    assert B2.lock_post(ctx, q, BR(q_obj=70.0), 570, "AM", kl, 100.0, lk_of(1, 110.0, marked))["side"] == 1
    assert B2.lock_post(ctx, q, BR(), 570, "AM", kl, 100.0, lk_of(0, None, marked))["side"] == 0
    # ipda_draw_side: the next 20-day extreme on the side of the last daily MSS
    i_ = Params(**BASE, ipda_draw_side=True)
    o2 = B2.lock_post(ctx, i_, BR(last_break=-1), 570, "AM", kl, 100.0, lk_of(1, 110.0, marked))
    assert o2["side"] == -1 and o2["target"] == 95.0 and o2["name"] == "ipda20l"
    o3 = B2.lock_post(ctx, i_, BR(last_break=1), 570, "AM", kl, 100.0, lk_of(-1, 90.0, marked))
    assert o3["side"] == 1 and o3["target"] == 120.0
    assert B2.lock_post(ctx, i_, BR(last_break=0), 570, "AM", kl, 100.0, lk_of(1, 110.0, marked))["side"] == 1
    # the PM lock reverses an AM draw hit at an HTF array
    r = Params(**BASE, htf_after_draw="reverse")
    ctx.lock = {"AM": dict(side=1, name="htf_ce", delivered=True)}
    o4 = B2.lock_post(ctx, r, BR(), 810, "PM", kl, 100.0, lk_of(1, 110.0, marked, session="PM"))
    assert o4["side"] == -1 and "after_draw_reverse" in o4["bh2"]
    ctx.lock = {"AM": dict(side=1, name="pdh1", delivered=True)}
    assert B2.lock_post(ctx, r, BR(), 810, "PM", kl, 100.0, lk_of(1, 110.0, marked, session="PM"))["side"] == 1       # a pool is not an array
    ctx.lock = {"AM": dict(side=1, name="htf_ce", delivered=False)}
    assert B2.lock_post(ctx, r, BR(), 810, "PM", kl, 100.0, lk_of(1, 110.0, marked, session="PM"))["side"] == 1       # not delivered


def test_htf_rank_tf_rungs():
    p = Params(**BASE, htf_rank_tf=True)
    sd = None
    ctx = ctx_at(p, bias_row=BR(rk_W_up=106.0, rk_D_dn=94.0))
    i = at(ctx, "09:55")
    sd = sd_of(ctx)
    lv = B2.targets_post(ctx, sd, i, p, 100.0, [(102.0, "array"), (106.2, "array"), (108.0, "pool")])
    assert (106.0, "array") in lv and (106.2, "array") not in lv and [v for v, _ in lv] == sorted(v for v, _ in lv)      # the weekly rung replaces the daily array rung at (nearly) the same level
    assert B2.rung_tf(ctx)[106.0] == "W"
    assert B2.targets_post(ctx, sd, i, Params(**BASE), 100.0, [(102.0, "array")]) == [(102.0, "array")]
    # equal-distance rungs of D, W and M: ONE rung, labelled with the highest timeframe (M > W > D)
    c3 = ctx_at(p, bias_row=BR(rk_D_up=106.0, rk_W_up=106.0, rk_M_up=106.0))
    lv3 = B2.targets_post(c3, sd, i, p, 100.0, [(102.0, "array"), (106.0, "array")])
    assert lv3 == [(102.0, "array"), (106.0, "array")] and B2.rung_tf(c3) == {106.0: "M"}
    # W and M a hair apart: the monthly level is the one kept, the weekly one dropped
    c4 = ctx_at(p, bias_row=BR(rk_D_up=106.2, rk_W_up=106.1, rk_M_up=105.9))
    lv4 = B2.targets_post(c4, sd, i, p, 100.0, [])
    assert lv4 == [(105.9, "array")] and B2.rung_tf(c4) == {105.9: "M"}
    # a daily-only level that matches an existing daily array rung only labels it
    c5 = ctx_at(p, bias_row=BR(rk_D_up=102.0))
    assert B2.targets_post(c5, sd, i, p, 100.0, [(102.0, "array")]) == [(102.0, "array")] and B2.rung_tf(c5) == {102.0: "D"}
    # a pool at the same level is not an array: it stays
    c6 = ctx_at(p, bias_row=BR(rk_W_up=108.0))
    assert (108.0, "pool") in B2.targets_post(c6, sd, i, p, 100.0, [(108.0, "pool")])


# --- full run_day paths with the switches on (the hooks are wired into the engine) ---------------------------------------------------------------

def test_run_day_paths_with_switches_on():
    base, *_ = _run_rows(Params(**BASE, htf_bias="combo", bias_neutral="both"), bias=BR(combo=0))
    assert base
    for kw, row in ((dict(raid_side_gate=True), BR(combo=0, raid_side60=-1)), (dict(ipda_extreme_pause=True), BR(combo=0, ipda_pause=1)),
                    (dict(sibi_gate=True), BR(combo=0, sibi_dir=-1, sibi_top=130.0, sibi_bot=120.0))):
        tr, *_ = _run_rows(Params(**BASE, htf_bias="combo", bias_neutral="both", **kw), bias=row)
        assert not [t for t in tr if t.side == "long"], kw                                              # the blocked side does not trade
    tr, *_ = _run_rows(Params(**BASE, htf_bias="combo", bias_neutral="both", pd_two_level=True), bias=BR(combo=0, eq20_body=50.0))
    assert not [t for t in tr if t.side == "long"]
    tr2, *_ = _run_rows(Params(**BASE, htf_bias="combo", bias_neutral="both", pd_two_level=True), bias=BR(combo=0, eq20_body=500.0))
    assert tr2 and all("htf_discount" in (t.lv_tags or "") for t in tr2)


def test_q_window_size_and_b19_report():
    p = Params(**BASE, q_window_size=1.5, htf_bias="combo")
    row = BR(combo=-1, react=-1, q_window=1)
    ctx = ctx_at(p, bias_row=row)                                                    # 23 June: the summer-short calendar window (-1)
    i = at(ctx, "09:55")
    from mentorship.bh2e import season_side
    assert season_side(D0) == -1 and season_side(date(2026, 11, 3)) == 1
    lvt: list = []
    assert B2.size_mult(ctx, sd_of(ctx, -1), i, p, lvt) == 1.5 and "size_q_window" in lvt         # window + bias + season agree with the short
    assert B2.size_mult(ctx, sd_of(ctx, 1), i, p, []) == 1.0                                       # a long is against all three
    assert B2.size_mult(ctx_at(p, bias_row=dict(row, q_window=0)), sd_of(ctx, -1), i, p, []) == 1.0     # outside the window
    assert B2.size_mult(ctx_at(p, bias_row=dict(row, combo=1, react=1)), sd_of(ctx, -1), i, p, []) == 1.0     # the bias does not agree
    # item 121's report: trades by sign regime
    from mentorship import report_decisions as RD
    t = pd.DataFrame(dict(lv_tags=["a|im_bwith_dagainst", "im_bwith_dagainst", "x", None], R=[1.0, -1.0, 2.0, 0.5], net=[100.0, -90.0, 200.0, 40.0]))
    r = RD.b19_sign(t)
    assert r.loc["im_bwith_dagainst", "trades"] == 2 and r.loc["none", "trades"] == 2 and r.loc["im_bwith_dagainst", "win_rate"] == 0.5
    assert len(RD.b19_sign(t.iloc[:0])) == 0


# --- review round 2 ----------------------------------------------------------------------------------------------------------------------------

def test_htf_array_lock_names():
    for nm in ("htf_D_fvg", "htf_W_ob", "htf_M_vi", "htf_ce", "htf_vi", "ext_htf_4h", "ext_htf_D"):
        assert B2.htf_array_name(nm), nm
    for nm in ("htf_PDH", "htf_D_swing_high", "htf_PWL", "pdh1", "org", "ext_htf_15m", "", None, "htf_D_swing_low"):
        assert not B2.htf_array_name(nm), nm
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    r = Params(**BASE, htf_after_draw="reverse")
    ctx = ctx_at(r, rows=pad_to_0930([(100.0, 100.1, 99.9, 100.0)] * 3), start="00:00")
    kl = S._idx_at(ctx, 570)
    for nm, want in (("htf_D_fvg", -1), ("htf_PDH", 1)):                                    # the real names mark_levels gives: an array reverses, a pool does not
        ctx.lock = {"AM": dict(side=1, name=nm, delivered=True)}
        assert B2.lock_post(ctx, r, BR(), 810, "PM", kl, 100.0, lk_of(1, 110.0, marked, session="PM"))["side"] == want, nm


def test_scalp_week_when_the_weekly_draw_is_unset():
    p = Params(**BASE, htf_bias="combo", bias_neutral="scalp_week")
    assert B2.wk_unset(BR(wk_draw_up=NAN, wk_draw_dn=NAN)) and not B2.wk_unset(BR(wk_draw_up=120.0, wk_draw_dn=NAN)) and not B2.wk_unset(BR()) and not B2.wk_unset(None)
    c = ctx_at(p, bias_row=BR(combo=1, wk_draw_up=NAN, wk_draw_dn=NAN))
    i = at(c, "09:55")
    lvt: list = []
    assert B2.size_mult(c, sd_of(c), i, p, lvt) == p.scalp_week_risk and "size_scalp_week" in lvt          # a daily bias but no weekly draw: a scalp week
    assert BD.row_state(c, p, "AM", i).scalp == "bias_neutral"                                                # ... and the day's orders are scalps
    c2 = ctx_at(p, bias_row=BR(combo=1, wk_draw_up=120.0, wk_draw_dn=NAN))
    assert B2.size_mult(c2, sd_of(c2), i, p, []) == 1.0                                                    # a bias and a weekly draw: normal
    assert BD.row_state(c2, p, "AM", i).scalp != "bias_neutral"
