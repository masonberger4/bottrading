"""Caption-gap pass, package bias_htf#3/7: the ENGINE hooks (bh3e.py) on hand-made days built with the real DayCtx and DayPlan - side gates, per-order rules and tags, scalps, sizes, targets, the bias
composers, the AM lock, the counter-trend exception, the seasonal qualifiers (second file of tests/test_caption_gap_bh3.py). Nothing here needs market data; no file outside the repo is written."""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import bh3e as E3, bias_day as BD, cot, daycontext as DW, dwc1, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, history, rth_day  # noqa: E402
from test_caption_gap_dwc1 import mk, at  # noqa: E402
from test_caption_gap_bh1 import BR  # noqa: E402
from test_caption_gap_bh1e import pad_to_0930, lk_of  # noqa: E402

@pytest.fixture(autouse=True)
def _no_cot_files(monkeypatch):
    """Hermetic: no CFTC files are read from data/mentorship/cot unless a test puts a table in the cache."""
    monkeypatch.setitem(cot._CACHE, ("E-MINI S&P 500", str(cot.COT_DIR)), None)


D1 = date(2026, 3, 10)                       # a Tuesday in the Feb-May bullish window (win_long_spring)
FLAT = [(100.0, 100.3, 99.8, 100.1)] * 12


def hist_closes(d, closes, hi_pad=1.0):
    """Prior regular sessions with the given closes (oldest first)."""
    from mentorship import calendar as C
    out, x = [], pd.Timestamp(d)
    while len(out) < len(closes):
        x -= pd.Timedelta(days=1)
        if C.is_trading_day(x.date()):
            out.append(x.date())
    out = out[::-1]
    return [rth_day(x, c + hi_pad, c - hi_pad, c) for x, c in zip(out, closes)]


def cx(p, rows=FLAT, bias=None, im=None, hist=None, d=D1, start="09:30", **kw):
    ctx = mk(d, hist if hist is not None else history(d), p, rows=rows, bias_row=bias, start=start, **kw)
    ctx.intermarket = im or {}
    return ctx


def order(entry=105.0, t1=108.0, ext=None, tags=""):
    return dict(entry=entry, t1=t1, lv_tags=tags, levels=[t1], ext=entry - 1.0 if ext is None else ext)


def put_cot(monkeypatch, nets, last_report=date(2026, 3, 3)):
    """Weekly reports (Tuesdays) ending `last_report` with the given nets, as the CFTC table the loader would build."""
    reps = pd.date_range(end=pd.Timestamp(last_report), periods=len(nets), freq="7D")
    df = pd.DataFrame({"report_date": reps, "comm_long": [float(x) for x in nets], "comm_short": 0.0, "net": [float(x) for x in nets]})
    monkeypatch.setitem(cot._CACHE, ("E-MINI S&P 500", str(cot.COT_DIR)), cot.table(df))


# --- item 147: program and hedging; the hedge + iof gate ---------------------------------------------------------------------

def test_cot_gate_and_tags(monkeypatch):
    nets = [-60000 if k % 2 else -10000 for k in range(59)] + [-20000]               # net -20k in a -60k..-10k range: program -1, hedge +1
    put_cot(monkeypatch, nets)
    p = Params(**BASE, htf_bias="combo", cot_gate="hedge_iof")
    ctx = cx(p, bias=BR(iof=1))
    i = at(ctx, "09:50")
    assert E3.cot_states(ctx, p) == (-1, 1)
    assert E3.side_ok(ctx, p, 1, "AM", i) is None                                     # the hedge agrees with the long and so does the daily iof: allowed whatever the program says
    assert E3.side_ok(ctx, p, -1, "AM", i) == "x_bh3_cot_gate"                        # the program is short but the hedge is not
    ctx2 = cx(p, bias=BR(iof=0))
    assert E3.side_ok(ctx2, p, 1, "AM", i) == "x_bh3_cot_gate"                        # the daily iof does not agree
    o = order()
    assert E3.order_ok(ctx, ctx.sides_map[1], o, "AM", i, p) is None and "cot_program_-1" in o["lv_tags"] and "cot_hedge_+1" in o["lv_tags"]
    monkeypatch.setitem(cot._CACHE, ("E-MINI S&P 500", str(cot.COT_DIR)), None)        # no COT data: no gate, no tag
    ctx3 = cx(p, bias=BR(iof=0))
    assert E3.side_ok(ctx3, p, 1, "AM", i) is None
    o3 = order()
    E3.order_ok(ctx3, ctx3.sides_map[1], o3, "AM", i, p)
    assert "cot_" not in o3["lv_tags"]


# --- items 152 / 168 / 172 / 186 / 222: tags and the tandem scalp ---------------------------------------------------------------

def test_tags_and_tandem_scalp():
    p = Params(**BASE, htf_bias="combo", tandem_scalp=True, bond_lt_tag=True, wpr_daily_tag=True, mw_bookkeeping=True, q_dir_tag=True)
    row = BR(wpr_d=1, mo_pd=0.35, wk_pd=0.62, wk_expand=2, q_dir=-1)
    ctx = cx(p, bias=row, im={"notes_dxy": "tandem", "bond_lt": 1})
    i = at(ctx, "09:50")
    assert E3.scalp_now(ctx, p, "AM", i, 1) == "bh3_tandem"                            # orders on tandem days are scalps
    o = order()
    assert E3.order_ok(ctx, ctx.sides_map[1], o, "AM", i, p) is None
    tags = o["lv_tags"].split("|")
    assert {"notes_tandem", "bond_lt_+1", "wprd_+1", "mo_pd_0.35", "wk_pd_0.62", "wk_expand_2", "q_dir_oppose"} <= set(tags)
    ctx2 = cx(p, bias=row, im={"notes_dxy": "opposed"})
    assert E3.scalp_now(ctx2, p, "AM", i, 1) == ""
    assert not E3.on(Params(**BASE)) and E3.scalp_now(cx(Params(**BASE)), Params(**BASE), "AM", i, 1) == ""


# --- item 164: the full confluence stack -----------------------------------------------------------------------------------------

def test_stack_count():
    p = Params(**BASE, htf_bias="flip", stack_tag=True, stack_min=5)
    ctx = cx(p, bias=BR(flip=1), im={"tnx": -1, "dxy": -1})
    i = at(ctx, "09:50")
    sd = ctx.sides_map[1]
    assert E3.stack_count(ctx, p, 1, ctx.bias_row, i) == 5                              # spring window + flip +1 + AM kill zone + falling yields + falling dollar
    o = order()
    assert E3.order_ok(ctx, sd, o, "AM", i, p) is None and "stack_5" in o["lv_tags"]
    ctx2 = cx(p, bias=BR(flip=1), im={"tnx": -1, "dxy": 1})
    assert E3.stack_count(ctx2, p, 1, ctx2.bias_row, i) == 4
    assert E3.order_ok(ctx2, ctx2.sides_map[1], order(), "AM", i, p) == "x_bh3_stack"   # below stack_min
    assert E3.stack_count(ctx, p, -1, ctx.bias_row, i) == 1                              # a short agrees only with the kill-zone timing
    ctx3 = cx(p, bias=BR(flip=1), im={"tnx": -1, "dxy": -1}, d=date(2026, 6, 23))       # a summer (bearish) window
    assert E3.stack_count(ctx3, p, 1, ctx3.bias_row, i) == 4
    ctx4 = cx(p, bias=BR(flip=1), im={"tnx": -1, "dxy": -1}, rows=pad_to_0930(FLAT, 100.0) + FLAT, start="00:00")
    assert E3.stack_count(ctx4, p, 1, ctx4.bias_row, at(ctx4, "03:00")) == 4              # outside the AM / PM entry windows


# --- items 167 / 173: the swing gate on runners, the hallmarks -----------------------------------------------------------------------

def test_swing_gate_runners_and_hallmarks():
    up = hist_closes(D1, [100 + q for q in range(24)])
    p = Params(**BASE, htf_bias="combo", swing_gate_runners=True, hallmarks_tag=True, trend_slope_min=0.5)
    flat = cx(p, bias=BR(iof=1, draw_up=110.0), im={"tr_tnx": 0.1, "tr_dxy": 0.1, "tnx": -1}, hist=up)
    i = at(flat, "09:50")
    assert E3.trend_ok(flat, p) is False
    assert E3.scalp_now(flat, p, "AM", i, 1) == "bh3_notrend"                           # flat TNX and DXY: runners dropped
    on = cx(p, bias=BR(iof=1, draw_up=110.0), im={"tr_tnx": 0.8, "tr_dxy": 0.1, "tnx": -1}, hist=up)
    assert E3.trend_ok(on, p) is True and E3.scalp_now(on, p, "AM", i, 1) == ""
    o = order()
    assert E3.order_ok(on, on.sides_map[1], o, "AM", i, p) is None
    assert "hallmarks_5" in o["lv_tags"]                                                  # trend + iof + rates + the spring window + an opposing array (draw_up)
    o2 = order()
    on2 = cx(p, bias=BR(iof=0, draw_up=110.0), im={"tr_tnx": 0.8, "tr_dxy": 0.1}, hist=up)
    E3.order_ok(on2, on2.sides_map[1], o2, "AM", i, p)
    assert "hallmarks_3" in o2["lv_tags"]                                                 # trend, the window and the draw: 3 of the 5
    none = cx(p, bias=BR(), im={}, hist=up)
    assert E3.trend_ok(none, p) is None and E3.scalp_now(none, p, "AM", i, 1) == ""        # no intermarket data: no verdict, no scalp


# --- item 174: the profile gate --------------------------------------------------------------------------------------------------

def test_profile_gate():
    p = Params(**BASE, htf_bias="combo", profile_gate=True)
    trend = cx(p, bias=BR(profile="trend", profile_dir=1))
    i = at(trend, "09:50")
    assert E3.side_ok(trend, p, -1, "AM", i) == "x_bh3_profile_trend" and E3.side_ok(trend, p, 1, "AM", i) is None      # trend: counter-trend orders blocked
    cons = cx(p, bias=BR(profile="consol", profile_dir=0))
    assert E3.scalp_now(cons, p, "AM", i, 1) == "bh3_profile_consol"                    # consol: runners off and scalp
    ret = cx(p, bias=BR(profile="retrace", profile_dir=1, wm_zones=((100.0, 106.0, 1),)))
    o_in, o_out = order(entry=104.0), order(entry=112.0)
    assert E3.order_ok(ret, ret.sides_map[1], o_in, "AM", i, p) is None and "profile_in_array" in o_in["lv_tags"]
    assert E3.order_ok(ret, ret.sides_map[1], o_out, "AM", i, p) == "x_bh3_profile_retrace"      # with-trend orders need the entry inside a weekly / monthly array
    assert E3.side_ok(ret, p, -1, "AM", i) is None                                       # in a retrace the counter side is not blocked


# --- item 195: in play ------------------------------------------------------------------------------------------------------------

def test_in_play_gate_engine():
    p = Params(**BASE, htf_bias="combo", in_play_gate=True)
    ctx = cx(p, bias=BR(in_play=1))
    i = at(ctx, "09:50")
    assert E3.side_ok(ctx, p, 1, "AM", i) is None and E3.side_ok(ctx, p, -1, "AM", i) == "x_bh3_in_play"
    assert E3.side_ok(cx(p, bias=BR(in_play=0)), p, 1, "AM", i) == "x_bh3_in_play"        # no daily / 4h array in play: longs are rejected
    ctx.conf = SimpleNamespace(opposing=lambda now, beyond, side, tfs, src: [(beyond + 3.0, 0, 0, "D", 0)])          # an opposing array 3 points above the entry
    assert E3.order_ok(ctx, ctx.sides_map[1], order(), "AM", i, p) == "x_bh3_in_play_room"      # under the 5-point minimum room
    ctx.conf = SimpleNamespace(opposing=lambda now, beyond, side, tfs, src: [(beyond + 9.0, 0, 0, "D", 0)])
    o = order()
    assert E3.order_ok(ctx, ctx.sides_map[1], o, "AM", i, p) is None and "in_play" in o["lv_tags"]


# --- item 198: daily and 4h -------------------------------------------------------------------------------------------------------

def test_bias_dh(monkeypatch):
    row = BR(iof=1)
    for mode in ("both", "either"):
        p = Params(**BASE, htf_bias="combo", bias_dh=mode)
        ctx = cx(p, bias=row)
        i = at(ctx, "09:50")
        monkeypatch.setattr(E3, "iof_4h", lambda c, k: -1)
        assert E3.dh_state(ctx, row, 1, i) == "conflict" and E3.side_ok(ctx, p, 1, "AM", i) == "x_bh3_bias_dh"       # daily +1 and 4h -1: rejected under both modes
    pb = Params(**BASE, htf_bias="combo", bias_dh="both")
    pe = Params(**BASE, htf_bias="combo", bias_dh="either")
    ctx = cx(pb, bias=row)
    i = at(ctx, "09:50")
    monkeypatch.setattr(E3, "iof_4h", lambda c, k: 1)
    assert E3.dh_state(ctx, row, 1, i) == "both" and E3.side_ok(ctx, pb, 1, "AM", i) is None
    monkeypatch.setattr(E3, "iof_4h", lambda c, k: 0)
    assert E3.dh_state(ctx, row, 1, i) == "daily_only"
    assert E3.side_ok(ctx, pb, 1, "AM", i) == "x_bh3_bias_dh" and E3.side_ok(cx(pe, bias=row), pe, 1, "AM", i) is None      # 'either' needs one agreeing and none opposing
    assert E3.dh_state(ctx, BR(iof=0), 1, i) == "none"
    monkeypatch.setattr(E3, "iof_4h", lambda c, k: 1)
    assert E3.dh_state(ctx, BR(iof=0), 1, i) == "4h_only"
    pt = Params(**BASE, htf_bias="combo", bias_dh="tag")
    o = order()
    c0 = cx(pt, bias=BR(iof=0))
    E3.order_ok(c0, c0.sides_map[1], o, "AM", i, pt)
    assert "bias_dh_4h_only" in o["lv_tags"] and E3.side_ok(c0, pt, 1, "AM", i) is None            # the tag mode never blocks


# --- item 203: a bullish iof at a premium waits --------------------------------------------------------------------------------------

def test_iof_premium_wait():
    p = Params(**BASE, htf_bias="combo", iof_premium_wait=True)
    row = BR(iof=1, px=108.0, pd20_lo=90.0, pd20_hi=110.0)                              # the prior close is at 90 % of the 20-day range
    ctx = cx(p, bias=row)
    i = at(ctx, "09:50")
    ctx.conf = SimpleNamespace(at=lambda now, price, side: [])
    assert E3.order_ok(ctx, ctx.sides_map[1], order(ext=104.0), "AM", i, p) == "x_iof_premium_wait"
    ctx.conf = SimpleNamespace(at=lambda now, price, side: ["4h"])                       # the sweep low sits inside a 4h bull OB
    assert E3.order_ok(ctx, ctx.sides_map[1], order(ext=104.0), "AM", i, p) is None
    ctx.conf = SimpleNamespace(at=lambda now, price, side: ["15m", "1h"])               # only intraday arrays: not a daily / 4h array
    assert E3.order_ok(ctx, ctx.sides_map[1], order(ext=104.0), "AM", i, p) == "x_iof_premium_wait"
    low = cx(p, bias=BR(iof=1, px=95.0, pd20_lo=90.0, pd20_hi=110.0))
    low.conf = SimpleNamespace(at=lambda now, price, side: [])
    assert E3.order_ok(low, low.sides_map[1], order(ext=104.0), "AM", i, p) is None      # at 25 % of the range the rule does not apply
    short_ctx = cx(p, bias=BR(iof=-1, px=92.0, pd20_lo=90.0, pd20_hi=110.0))            # bearish iof at a discount: the mirror
    short_ctx.conf = SimpleNamespace(at=lambda now, price, side: [])
    assert E3.order_ok(short_ctx, short_ctx.sides_map[-1], order(ext=-96.0), "AM", i, p) == "x_iof_premium_wait"


# --- items 201 / 185: the bias readings -----------------------------------------------------------------------------------------------

def test_pd_needs_iof_and_pause():
    p = Params(**BASE, htf_bias="pd", pd_needs_iof=True)
    assert BD.bias_value(BR(pd=1, iof=-1), p) == 0                                      # a discount reading with a bearish iof: bias 0
    assert BD.bias_value(BR(pd=1, iof=1), p) == 1 and BD.bias_value(BR(pd=-1, iof=-1), p) == -1
    pc = Params(**BASE, htf_bias="combo", pd_needs_iof=True)
    assert BD.bias_value(BR(react=0, pd=1, combo=1, iof=-1), pc) == 0                   # combo modes inherit it when the reading came from the P/D part
    assert BD.bias_value(BR(react=1, pd=1, combo=1, iof=-1), pc) == 1                   # a reaction-sourced bias is not a P/D bias
    assert BD.bias_value(BR(pd=1, iof=-1), Params(**BASE, htf_bias="pd")) == 1           # off: unchanged
    pp = Params(**BASE, htf_bias="flip", pause_on_hold=True)
    assert BD.bias_value(BR(flip=-1, held_pause=1), pp) == 0 and BD.bias_value(BR(flip=-1, held_pause=0), pp) == -1       # a holding array pauses the next session


def test_fall_low_bias_fills_a_neutral_bias():
    p = Params(**BASE, htf_bias="combo", fall_low_bias=True)
    ctx = cx(p, bias=BR(combo=0), im={"fall_low": 1})
    i = at(ctx, "09:50")
    assert BD.want_at(ctx, p, "AM", i) == 1                                              # October with the daily SMT under the 60-day EQ: want +1
    assert BD.want_at(cx(p, bias=BR(combo=-1), im={"fall_low": 1}), p, "AM", i) == -1     # an existing bias stays
    assert BD.want_at(cx(p, bias=BR(combo=0), im={}), p, "AM", i) == 0


# --- items 224 / 227 / 226: the composers --------------------------------------------------------------------------------------------

def test_week_check_order():
    p = Params(**BASE, htf_bias="week_check")
    i0 = None

    def want(row, im=None):
        ctx = cx(p, bias=row, im=im)
        return BD.want_at(ctx, p, "AM", at(ctx, "09:50"))
    assert want(BR(wk_consol=1, wk_chk_tail=1)) == 0                                    # a consolidating profile gives 0 regardless of the later components
    assert want(BR(wk_consol=0, wk_chk_tail=1)) == 1                                    # a trend with the weekly iof +1 gives +1
    assert want(BR(wk_consol=0, wk_chk_tail=1), {"dsmt": -1}) == -1                      # relative strength (the SMT) comes first
    assert want(BR(wk_consol=1, wk_chk_tail=0), {"dsmt": -1}) == -1                      # ... even before the profile
    assert want(BR(wk_consol=0, wk_chk_tail=0), {"dsmt": 0, "dxy": 1, "spx20": 1}) == 0
    assert want(BR(wk_consol=0, wk_chk_tail=-1), {"dxy": -1, "spx20": 1}) == 1           # intermarket harmony (the instrument rising against a falling dollar) before the weekly iof / draw
    assert want(BR(wk_consol=1, wk_chk_tail=0), {"dxy": -1, "spx20": 1}) == 0            # ... but the profile stops the cascade first
    assert i0 is None


def test_wd_check_fallback():
    p = Params(**BASE, htf_bias="wd_check")

    def want(tail_w, head_d, tail_d, im=None):
        ctx = cx(p, bias=BR(wk_consol=0, wk_chk_tail=tail_w, d_head=head_d, d_tail=tail_d), im=im)
        return BD.want_at(ctx, p, "AM", at(ctx, "09:50")), ctx
    assert want(0, -1, 0)[0] == -1                                                       # the weekly bias 0: the daily alone
    assert want(1, -1, 0)[0] == 0                                                        # the weekly +1 and the daily -1: no bias
    w, ctx = want(1, 0, 0)
    assert w == 1 and ctx.__dict__["_bh3e"]["daily_unconfirmed"] is True                  # the daily is flat: the weekly stands, orders are tagged daily_unconfirmed
    o = order()
    assert E3.order_ok(ctx, ctx.sides_map[1], o, "AM", at(ctx, "09:50"), p) is None and "daily_unconfirmed" in o["lv_tags"]
    assert want(1, 0, -1)[0] == 0 and want(1, 1, 0)[0] == 1 and want(0, 0, 0, {"dsmt": -1})[0] == -1      # the daily order: iof, the SMT, the flip / draw tail


def test_iof_sponsor_gate():
    row = BR(iof=0, wk_consol=0, wk_chk_tail=-1)
    p = Params(**BASE, htf_bias="week_check", iof_sponsor_gate="skip")
    ctx = cx(p, bias=row)
    i = at(ctx, "09:50")
    assert E3.side_ok(ctx, p, -1, "AM", i) == "x_bh3_iof_sponsor"                         # the weekly -1 and the daily iof 0: skipped
    ok = cx(p, bias=BR(iof=-1, wk_consol=0, wk_chk_tail=-1))
    assert E3.side_ok(ok, p, -1, "AM", i) is None
    zero = cx(p, bias=BR(iof=0, wk_consol=0, wk_chk_tail=0, flip=0))
    assert E3.side_ok(zero, p, -1, "AM", i) is None                                       # a neutral weekly bias: nothing to sponsor
    flip_only = cx(Params(**BASE, htf_bias="flip", iof_sponsor_gate="skip"), bias=BR(iof=0, flip=-1, wk_consol=0, wk_chk_tail=0))
    assert E3.side_ok(flip_only, Params(**BASE, htf_bias="flip", iof_sponsor_gate="skip"), -1, "AM", i) == "x_bh3_iof_sponsor"       # else the flip state
    pt = Params(**BASE, htf_bias="week_check", iof_sponsor_gate="tag")
    o = order()
    E3.order_ok(ctx, ctx.sides_map[-1], o, "AM", i, pt)
    assert "iof_no_sponsor" in o["lv_tags"] and E3.side_ok(ctx, pt, -1, "AM", i) is None


# --- items 221 / 225: the monthly bias and the weekly structure -----------------------------------------------------------------------------

def test_mo_bias_gate():
    p = Params(**BASE, htf_bias="combo", mo_bias_gate=True)
    row = BR(mo_bias=1, px=100.0, q_obj=110.0, last_break=1)
    aligned = cx(p, bias=row, im={"tnx": -1, "dsmt": 1})
    i = at(aligned, "09:50")
    assert E3.mo_aligned(aligned, p, row, 1) is True
    assert E3.side_ok(aligned, p, -1, "AM", i) == "x_bh3_mo_bias" and E3.side_ok(aligned, p, 1, "AM", i) is None       # all four components +1: shorts are blocked
    dis = cx(p, bias=row, im={"tnx": 1, "dsmt": 1})
    assert E3.mo_aligned(dis, p, row, 1) is False and E3.side_ok(dis, p, -1, "AM", i) is None                          # the rates disagree: no block
    assert E3.mo_aligned(cx(p, bias=row, im={"tnx": -1}, d=date(2026, 6, 23)), p, row, 1) is False                     # a bearish window disagrees
    assert E3.mo_aligned(aligned, p, BR(mo_bias=1, px=100.0, q_obj=90.0, last_break=1), 1) is False                     # the quarterly objective lies below
    qd = BR(mo_bias=1, px=100.0, q_obj=float("nan"), q_obj_dir=112.0, last_break=0)
    assert E3.mo_aligned(aligned, p, qd, 1) is True                                                                      # q_obj_dir stands in; the SMT carries the structure part
    o = order()
    E3.order_ok(aligned, aligned.sides_map[1], o, "AM", i, p)
    assert "mo_aligned" in o["lv_tags"]


def test_wk_struct_weight():
    p = Params(**BASE, htf_bias="combo", wk_struct_weight=True)
    ctx = cx(p, bias=BR(wk_control=1, mo_bias=1))
    i = at(ctx, "09:50")
    lvt: list = []
    assert E3.size_mult(ctx, ctx.sides_map[1], i, p, lvt) == 1.0 and not lvt
    assert E3.size_mult(ctx, ctx.sides_map[-1], i, p, lvt) == 0.5 and lvt == ["size_wk_struct"]       # does not agree with wk_control and mo_bias: half risk
    ctx2 = cx(p, bias=BR(wk_control=1, mo_bias=-1))
    assert E3.size_mult(ctx2, ctx2.sides_map[1], i, p, []) == 0.5
    o = order()
    E3.order_ok(ctx, ctx.sides_map[1], o, "AM", i, p)
    assert "wk_struct_agree" in o["lv_tags"]
    assert BD.size_mult(ctx, ctx.sides_map[-1], i, p, []) == 0.5


# --- item 45: chop days ---------------------------------------------------------------------------------------------------------------

CHOP_ROWS = [(100.0, 102.0, 99.0, 101.0), (101.0, 103.0, 100.0, 102.0), (102.0, 104.0, 101.0, 103.0)] + [(103.0, 104.0, 102.0, 103.0)] * 6 + [(103.0, 104.0, 102.5, 103.5)]


def test_chop_lean_and_baseline():
    p = Params(**BASE, htf_bias="combo", chop_lean=True, chop_target_baseline=True, sloppy_tests=("chop",), sloppy_mode="scalp")
    ctx = cx(p, rows=CHOP_ROWS, start="08:30", bias=BR())
    ctx.cur_sloppy = "chop"
    i = at(ctx, "09:30")
    base = E3.chop_baseline(ctx, i)
    assert base == pytest.approx((104.0 + 99.0) / 2)                                    # the midpoint of the range since 08:30
    assert E3.side_ok(ctx, p, 1, "AM", i) is None and E3.side_ok(ctx, p, -1, "AM", i) == "x_bh3_chop_lean"       # above the baseline: the buy-side pool is next
    assert E3.scalp_now(ctx, p, "AM", i, -1) == "bh3_chop_baseline" and E3.scalp_now(ctx, p, "AM", i, 1) == ""    # a counter-move is a single-target scalp
    sd = ctx.sides_map[-1]
    lv = E3.targets_post(ctx, sd, i, p, sd.x(float(ctx.c[i])) - 20.0, [(sd.x(90.0), "pool")])
    assert lv[0] == (sd.x(base), "pool") and len(lv) == 2                                 # the baseline is the first rung of the counter-move
    ctx.cur_sloppy = ""
    ctx.dplan.info.pop("drr_ng", None)
    assert E3.side_ok(ctx, p, -1, "AM", i) is None and E3.targets_post(ctx, sd, i, p, 0.0, [(1.0, "pool")]) == [(1.0, "pool")]       # not a chop day
    ctx.dplan.info["drr_ng"] = True
    assert E3.chop_day(ctx) is True                                                      # the B17.4 range-market reading counts as well
    early = cx(p, rows=CHOP_ROWS, start="08:30", bias=BR())
    early.cur_sloppy = "chop"
    assert E3.chop_baseline(early, at(early, "08:30") - 1) is None                       # before 08:30 there is no baseline


# --- item 200: NY continues London ---------------------------------------------------------------------------------------------------------

def london_rows(high_at=190, high=104.0):
    rows = pad_to_0930([(100.0, 100.2, 99.8, 100.0)] * 5, price=100.0)
    j = high_at // 5
    rows[j] = (100.0, high, 99.9, 100.1)
    return rows


def test_ny_continue_london():
    p = Params(**BASE, htf_bias="combo", ny_continue_london=True)
    ctx = cx(p, rows=london_rows(), start="00:00", bias=BR(iof=-1))
    kl = S._idx_at(ctx, 570)
    lock = dict(side=0, target=None, kind="", name="", marked=[])
    out = E3.lock_post(ctx, p, BR(iof=-1), 570, "AM", kl, 100.0, dict(lock))
    assert out["side"] == -1 and out["name"] == "adr5" and out["target"] == pytest.approx(104.0 - 18.0)     # the London high at 03:10, bearish iof: lock short toward high - ADR5
    assert E3.lock_post(ctx, p, BR(iof=0), 570, "AM", kl, 100.0, dict(lock))["side"] == 0                      # no bearish iof
    late = cx(p, rows=london_rows(high_at=330), start="00:00", bias=BR(iof=-1))                                # the high came at 05:30: not London
    assert E3.lock_post(late, p, BR(iof=-1), 570, "AM", kl, 100.0, dict(lock))["side"] == 0
    ctx.conf = SimpleNamespace(valid=lambda now, side, tfs, src: [(101.0, 99.0, "D", 0, 0)] if side > 0 else [])   # a daily bull array was touched since 00:00
    assert E3.lock_post(ctx, p, BR(iof=-1), 570, "AM", kl, 100.0, dict(lock))["side"] == 0
    lowdone = cx(p, rows=pad_to_0930([(100.0, 100.2, 99.8, 100.0)] * 5), start="00:00", bias=BR(iof=-1))
    rows2 = london_rows()
    rows2[60] = (99.0, 99.1, 85.0, 86.0)                                                                       # the ADR5 low (86) was already reached
    reached = cx(p, rows=rows2, start="00:00", bias=BR(iof=-1))
    assert E3.lock_post(reached, p, BR(iof=-1), 570, "AM", kl, 86.0, dict(lock))["side"] == 0
    assert E3.lock_post(lowdone, p, BR(iof=-1), 570, "AM", kl, 100.0, dict(lock))["side"] == 0                 # no London high (flat night)
    mirror = london_rows()
    mirror[38] = (100.0, 100.2, 96.0, 99.9)
    mc = cx(p, rows=[(o, h if k != 38 else 100.2, l, c) for k, (o, h, l, c) in enumerate(mirror)], start="00:00", bias=BR(iof=1))
    mo = E3.lock_post(mc, p, BR(iof=1), 570, "AM", kl, 100.0, dict(lock))
    assert mo["side"] == 1 and mo["target"] == pytest.approx(96.0 + 18.0)                                       # the mirror: a London low with bullish iof


def test_q_obj_dir_fallback():
    p = Params(**BASE, htf_bias="combo", q_obj_lean=True, q_dir_tag=True)
    ctx = cx(p, rows=pad_to_0930(FLAT), start="00:00", bias=BR())
    kl = S._idx_at(ctx, 570)
    lock = dict(side=0, target=None, kind="", name="", marked=[])
    out = E3.lock_post(ctx, p, BR(q_obj=float("nan"), q_obj_dir=112.0), 570, "AM", kl, 100.0, dict(lock))
    assert out["side"] == 1 and out["target"] == 112.0 and out["name"] == "q_obj_dir"
    assert E3.lock_post(ctx, p, BR(q_obj=120.0, q_obj_dir=112.0), 570, "AM", kl, 100.0, dict(lock))["side"] == 0     # a real quarterly objective is item 83 (bh2e)


# --- item 202: the counter-trend exception ----------------------------------------------------------------------------------------------------

def counter_hist(d):
    from mentorship import calendar as C
    out, x = [], pd.Timestamp(d)
    while len(out) < 22:
        x -= pd.Timedelta(days=1)
        if C.is_trading_day(x.date()):
            out.append(x.date())
    out = out[::-1]
    return [rth_day(x, 108.0, 88.0 if k == 10 else 90.0, 100.0) for k, x in enumerate(out)]


def test_counter_trend_range_extreme():
    p = Params(**BASE, htf_bias="combo", counter_range_extreme=True, pd_body_multiday=False)
    rows = [(100.0, 100.2, 99.0, 99.2), (99.2, 99.3, 90.0, 90.5), (90.5, 90.6, 87.0, 87.6), (87.6, 88.4, 87.4, 88.0)]
    ctx = cx(p, rows=rows, bias=BR(), hist=counter_hist(D1))
    i = at(ctx, "09:45")
    sd = ctx.sides_map[1]
    assert E3.counter_kind(ctx, sd, i, p, -1, "AM") == "ctr"                             # want -1, a long at the bottom of the 20-day range after a sweep of the old daily low
    assert E3.counter_kind(ctx, sd, i, p, 1, "AM") == "" and E3.counter_kind(ctx, sd, i, p, 0, "AM") == ""     # with or without a bias: nothing
    assert E3.counter_kind(ctx, ctx.sides_map[-1], i, p, 1, "AM") == ""                   # a counter-trend SHORT needs a premium extreme
    mid = cx(p, rows=[(100.0, 100.2, 99.0, 99.2)] * 4, bias=BR(), hist=counter_hist(D1))
    assert E3.counter_kind(mid, mid.sides_map[1], at(mid, "09:45"), p, -1, "AM") == ""     # mid-range and no sweep
    ctx.conf = SimpleNamespace(opposing=lambda now, beyond, side, tfs, src: [(120.0, 0, 0, "D", 0), (95.0, 0, 0, "4h", 0)])
    assert E3.ctr_target(ctx, sd, i, p) == 95.0                                           # the nearest opposing array INSIDE the range
    ctx.conf = SimpleNamespace(opposing=lambda now, beyond, side, tfs, src: [(120.0, 0, 0, "D", 0)])
    assert E3.ctr_target(ctx, sd, i, p) is None
    assert E3.ctr_target(cx(p, rows=rows, bias=BR(), hist=counter_hist(D1)), sd, i, p) is None       # no confluence table


# --- items 154 / 216: the seasonal qualifiers ------------------------------------------------------------------------------------------------

def test_season_qualified_and_poised():
    p = Params(**BASE, htf_bias="combo", season_windows="tag", season_qualified=True)
    h = history(D1, n=60)
    ctx = cx(p, bias=BR(), hist=h, im={"dsmt": 1})
    info = dwc1.season_info(ctx, D1, p, h, 10.0)
    assert info["prim"] == "win_long_spring" and info["wdir"] == 1 and info["qualified"] is True and "season_qualified" in info["tags"]
    ctx.dplan = DW.plan(ctx, h, p, None, None, None)
    assert ctx.dplan.sides.get("season_qualified") == (-1,)                              # a spring long window with dsmt +1: qualified, shorts are blocked
    no = cx(p, bias=BR(), hist=h, im={"dsmt": 0})
    assert dwc1.season_info(no, D1, p, h, 10.0)["qualified"] is False
    opp = cx(p, bias=BR(), hist=h, im={"dsmt": -1, "notes_dxy": "opposed"})
    assert dwc1.season_info(opp, D1, p, h, 10.0)["qualified"] is True                      # any ONE qualifier: the notes / dollar regime
    off = Params(**BASE, htf_bias="combo", season_windows="tag")
    assert dwc1.season_info(ctx, D1, off, h, 10.0)["qualified"] is False
    pp = Params(**BASE, htf_bias="combo", season_windows="tag", season_poised=True, season_gate=True)
    bad = cx(pp, bias=BR(), hist=h, im={"poised": -1})                                    # ES and NQ both falling: the long window is inactive
    inf = dwc1.season_info(bad, D1, pp, h, 10.0)
    assert inf["prim"] is None and inf["wdir"] == 0 and inf["acts"] is False and "season_not_poised" in inf["tags"]
    good = cx(pp, bias=BR(), hist=h, im={"poised": 1})
    assert dwc1.season_info(good, D1, pp, h, 10.0)["prim"] == "win_long_spring"
    assert dwc1.season_info(cx(pp, bias=BR(), hist=h, im={}), D1, pp, h, 10.0)["prim"] == "win_long_spring"      # no map (no partner frame): the window is left alone


# --- item 180: the daily down-candle levels as entry arrays -------------------------------------------------------------------------------------

def test_dcandle_rows():
    p = Params(**BASE, htf_bias="mwd", mwd_upgrade=True, mwd_levels_entries=True)
    ctx = cx(p, bias=BR(mwd=1, mwd_levels=(99.0, 99.5, 97.0, 98.0, 120.0, 121.0)))
    i = at(ctx, "09:50")
    rows = E3.dcandle_rows(ctx, ctx.sides_map[1], i)
    assert [r[0] for r in rows] == [99.0, 99.5, 97.0, 98.0] and all(r[0] == r[1] for r in rows)     # levels below the price, zero-height
    assert E3.dcandle_rows(ctx, ctx.sides_map[-1], i) == []                                  # the other side
    assert E3.dcandle_rows(cx(p, bias=BR(mwd=0, mwd_levels=(99.0,))), cx(p).sides_map[1], i) == []
