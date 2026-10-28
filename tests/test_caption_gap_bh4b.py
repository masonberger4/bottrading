"""Caption-gap pass, package bias_htf#4/7: the ENGINE hooks (bh4e.py) on hand-made days built with the real DayCtx and DayPlan - side gates, per-order rules and tags, scalps, the neutral-bias
fallbacks, the AM-draw carry, the ladder level, the leg_pd waiver and the IFVG add (second file of tests/test_caption_gap_bh4.py). Nothing here needs market data; no file outside the repo is written."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import bh1e as B1, bh4e as E4, bias_day as BD, daycontext as DW, newscal as NC, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, history, rth_day  # noqa: E402
from test_caption_gap_dwc1 import mk, at, Conf  # noqa: E402
from test_caption_gap_bh1 import BR  # noqa: E402
from test_caption_gap_bh3b import cx, order, D1, hist_closes  # noqa: E402


def P(**kw):
    return Params(**BASE, htf_bias="combo", bias_neutral="both", **kw)


def short_order(entry_raw=102.0):
    return dict(entry=-entry_raw, t1=-entry_raw + 3, lv_tags="", levels=[-entry_raw + 3], ext=-entry_raw - 1.0)


# --- item 46: the range day ---------------------------------------------------------------------------------------------------

def test_range_day_pm_only_blocks_the_morning_and_carries_the_draw():
    p = P(range_day_mode="pm_only")
    ctx = cx(p, bias=BR(rng_day=1))
    am, pm = at(ctx, "09:50"), at(ctx, "13:45")
    assert E4.side_ok(ctx, p, 1, "AM", am) == "x_bh4_range_day" and E4.side_ok(ctx, p, -1, "AM", am) == "x_bh4_range_day"
    assert E4.side_ok(ctx, p, 1, "PM", pm) is None                                   # the PM trades
    ctx2 = cx(p, bias=BR(rng_day=0))
    assert E4.side_ok(ctx2, p, 1, "AM", am) is None                                  # not a range day
    assert DW.side_ok(ctx, p, 1, "AM", am) == "x_bh4_range_day"                      # reached through the shared side_ok chain
    ctx.lock = {"AM": dict(side=1, target=120.0, kind="pool", name="x")}
    lk = NC.carry_lock(ctx, p, "PM", dict(px=100.0, side=-1, target=90.0, kind="pool", name="y"))
    assert lk["side"] == 1 and lk["target"] == 120.0 and lk.get("carried")           # the AM's undelivered draw is the PM's draw on a range day
    ctx2.lock = dict(ctx.lock)
    assert NC.carry_lock(ctx2, p, "PM", dict(px=100.0, side=-1, target=90.0, kind="pool", name="y"))["side"] == -1      # an ordinary day: no carry (pm_carry_draw off)
    assert NC.carry_lock(ctx2, P(range_day_mode="pm_only", pm_carry_draw=True), "PM", dict(px=100.0, side=-1, target=90.0, kind="pool", name="y"))["side"] == 1


def test_range_day_scalp_mode():
    p = P(range_day_mode="scalp")
    ctx = cx(p, bias=BR(rng_day=1))
    i = at(ctx, "09:50")
    assert E4.scalp_now(ctx, p, "AM", i, 1) == "bh4_range_day" and DW.scalp_now(ctx, p, "AM", i, 1) == "bh4_range_day"
    assert E4.side_ok(ctx, p, 1, "AM", i) is None                                    # scalp mode never blocks
    assert E4.scalp_now(cx(p, bias=BR(rng_day=0)), p, "AM", i, 1) == ""


# --- item 51: the middle of the 60-session range -------------------------------------------------------------------------------

def test_ipda_mid_skip_and_the_quadrant_sides():
    p = P(ipda_mid_skip=True)
    i = at(cx(p, bias=BR()), "09:50")
    mid_neutral = cx(p, bias=BR(combo=0, ipda_pos=0.5))
    assert E4.side_ok(mid_neutral, p, 1, "AM", i) == "x_bh4_ipda_mid" and E4.side_ok(mid_neutral, p, -1, "AM", i) == "x_bh4_ipda_mid"
    assert E4.side_ok(cx(p, bias=BR(combo=1, ipda_pos=0.5)), p, 1, "AM", i) == "x_bh4_ipda_mid"                    # a bias but no locked draw: skipped
    ok = cx(p, bias=BR(combo=1, ipda_pos=0.5), lock={"AM": dict(side=1, target=110.0)})
    assert E4.side_ok(ok, p, 1, "AM", i) is None                                                                    # bias and locked draw defined: the middle trades
    low = cx(p, bias=BR(combo=1, ipda_pos=0.2), lock={"AM": dict(side=1, target=110.0)})
    assert E4.side_ok(low, p, -1, "AM", i) == "x_bh4_ipda_quadrant" and E4.side_ok(low, p, 1, "AM", i) is None      # only longs in the lower region
    high = cx(p, bias=BR(combo=-1, ipda_pos=0.8), lock={"AM": dict(side=-1, target=90.0)})
    assert E4.side_ok(high, p, 1, "AM", i) == "x_bh4_ipda_quadrant" and E4.side_ok(high, p, -1, "AM", i) is None
    assert E4.side_ok(cx(p, bias=BR(combo=0)), p, 1, "AM", i) is None                                               # no column (no 60 sessions): nothing


# --- item 74: the buy-day checklist ----------------------------------------------------------------------------------------------

def test_htf_checklist_gate():
    p = P(htf_checklist=True)
    i = at(cx(p, bias=BR()), "09:50")
    good = cx(p, bias=BR(chk_q=1, chk_react_up=1, chk_react_dn=0, chk_path_up=0, chk_path_dn=0))
    assert E4.side_ok(good, p, 1, "AM", i) is None and E4.side_ok(good, p, -1, "AM", i) == "x_bh4_htf_checklist"
    for kw in (dict(chk_q=0), dict(chk_react_up=0), dict(chk_path_up=1)):
        row = dict(chk_q=1, chk_react_up=1, chk_react_dn=0, chk_path_up=0, chk_path_dn=0)
        row.update(kw)
        assert E4.side_ok(cx(p, bias=BR(**row)), p, 1, "AM", i) == "x_bh4_htf_checklist", kw          # any one failing item blocks the long
    sh = cx(p, bias=BR(chk_q=-1, chk_react_up=0, chk_react_dn=1, chk_path_up=0, chk_path_dn=0))
    assert E4.side_ok(sh, p, -1, "AM", i) is None                                                   # the mirror
    from types import SimpleNamespace
    row = dict(chk_q=1, chk_react_up=1, chk_react_dn=0, chk_path_up=0, chk_path_dn=0)
    lock = {"AM": dict(side=1, target=112.0)}
    blocked = cx(p, bias=BR(**row), lock=lock, conf=SimpleNamespace(opposing=lambda now, beyond, side, tfs, src: [(106.0, 0, 0, "4h", 0)]))
    assert E4.side_ok(blocked, p, 1, "AM", i) == "x_bh4_htf_checklist"                              # a 4h array between the price and the locked draw (the daily table cannot see it)
    clear = cx(p, bias=BR(**row), lock=lock, conf=SimpleNamespace(opposing=lambda now, beyond, side, tfs, src: [(112.0, 0, 0, "4h", 0)]))
    assert E4.side_ok(clear, p, 1, "AM", i) is None                                                 # the array IS the draw: nothing in the way
    beyond = cx(p, bias=BR(**row), lock=lock, conf=SimpleNamespace(opposing=lambda now, beyond, side, tfs, src: [(120.0, 0, 0, "D", 0)]))
    assert E4.side_ok(beyond, p, 1, "AM", i) is None


# --- items 27 / 28: the daily BISI ---------------------------------------------------------------------------------------------------

def _bars(rows, ctx):
    a = np.array(rows, float)
    n = len(a)
    return dict(o=a[:, 0], h=a[:, 1], l=a[:, 2], c=a[:, 3], first=np.arange(n) + ctx.start, last=np.arange(n) + ctx.start)


def test_dbisi_lower_half_fill_blocks_longs(monkeypatch):
    p = P(dbisi_lower_half=True)
    row = BR(dz_dir=1, dz_lo=100.0, dz_hi=110.0, dz_ce=105.0)
    ctx = cx(p, bias=row)
    i = at(ctx, "10:10")
    lower = [(100.0, 102.0, 100.0, 101.5), (101.5, 104.0, 101.5, 103.8), (103.8, 105.0, 103.0, 104.5)]          # bull FVG [102, 103] inside the lower half (top 103 <= CE 105)
    upper = [(105.0, 106.0, 105.0, 105.8), (105.8, 108.0, 105.8, 107.8), (107.8, 109.0, 107.0, 108.5)]          # bull FVG [106, 107] in the upper half
    state = {}

    def tfc(c_, m, i_):
        return _bars(state["rows"], c_)
    monkeypatch.setattr(B1, "tf_complete", tfc)
    state["rows"] = lower + [(104.5, 104.6, 101.0, 101.5)]                       # a later close under 102: the lower-half gap is filled by a body
    assert E4.dbisi_lower_filled(ctx, row, 1, i) is True
    assert E4.side_ok(ctx, p, 1, "AM", i) == "x_bh4_dbisi_lower_filled" and E4.side_ok(ctx, p, -1, "AM", i) is None
    state["rows"] = lower + [(104.5, 105.0, 103.0, 104.0)]                       # the gap still open
    assert E4.dbisi_lower_filled(ctx, row, 1, i) is False and E4.side_ok(ctx, p, 1, "AM", i) is None
    state["rows"] = upper + [(108.5, 108.6, 105.5, 105.9)]                       # an UPPER-half gap filled: acceptable
    assert E4.dbisi_lower_filled(ctx, row, 1, i) is False
    sr = BR(dz_dir=-1, dz_lo=100.0, dz_hi=110.0, dz_ce=105.0)                    # the mirror: a SIBI, bear FVG in its upper half filled by a close above it
    state["rows"] = [(110.0, 110.0, 108.0, 108.5), (108.5, 108.5, 106.0, 106.2), (106.2, 107.0, 106.0, 106.8), (106.8, 109.5, 106.8, 109.2)]     # SIBI [107, 108]: high[2] 107 < low[0] 108
    assert E4.dbisi_lower_filled(ctx, sr, -1, i) is True
    assert E4.dbisi_lower_filled(ctx, BR(dz_dir=0), 1, i) is False


def test_dbisi_upper_and_discount_location():
    p = P(dbisi_upper_and_discount=True)
    row = dict(dz_dir=1, dz_ce=105.0, pd20_lo=90.0, pd20_hi=130.0)                # the multi-day EQ is 110
    ctx = cx(p, bias=BR(**row))
    i = at(ctx, "09:50")
    sd = ctx.sides_map[1]
    assert E4.order_ok(ctx, sd, order(entry=107.0), "AM", i, p) is None            # at or above the CE and below the multi-day EQ
    assert E4.order_ok(ctx, sd, order(entry=104.0), "AM", i, p) == "x_bh4_dbisi_location"      # lower half of the gap
    assert E4.order_ok(ctx, sd, order(entry=112.0), "AM", i, p) == "x_bh4_dbisi_location"      # above the multi-day EQ
    sctx = cx(p, bias=BR(dz_dir=-1, dz_ce=105.0, pd20_lo=80.0, pd20_hi=120.0))     # EQ 100: a short at or below the SIBI CE and above the EQ
    ssd = sctx.sides_map[-1]
    assert E4.order_ok(sctx, ssd, short_order(103.0), "AM", i, p) is None
    assert E4.order_ok(sctx, ssd, short_order(98.0), "AM", i, p) == "x_bh4_dbisi_location"
    assert E4.order_ok(cx(p, bias=BR(dz_dir=0)), cx(p, bias=BR()).sides_map[1], order(entry=104.0), "AM", i, p) is None      # no active gap: the filter has nothing to test


# --- item 61: the CE line ------------------------------------------------------------------------------------------------------------

def test_ce_line_blocks_longs_below_the_ce_and_shorts_after_two_closes_above(monkeypatch):
    p = P(ce_line_bias=True)
    row = BR(cel_kind=1, cel_ce=100.0, cel_top=104.0, cel_bot=96.0)
    ctx = cx(p, bias=row)
    i = at(ctx, "10:10")
    state = {}
    monkeypatch.setattr(B1, "tf_complete", lambda c_, m, i_: _bars(state["rows"], c_))
    state["rows"] = [(99.0, 99.5, 98.0, 99.0), (99.0, 99.8, 98.5, 99.4)]                 # below the CE
    assert E4.cel_state(ctx, row, i) == -1
    assert E4.side_ok(ctx, p, 1, "AM", i) == "x_bh4_ce_line" and E4.side_ok(ctx, p, -1, "AM", i) is None
    state["rows"] = [(99.0, 101.5, 99.0, 101.0), (101.0, 102.0, 100.5, 101.5)]            # two closes above: it holds
    assert E4.cel_state(ctx, row, i) == 1
    assert E4.side_ok(ctx, p, 1, "AM", i) is None and E4.side_ok(ctx, p, -1, "AM", i) == "x_bh4_ce_line"
    state["rows"] = [(99.0, 101.5, 99.0, 101.0), (101.0, 102.0, 98.0, 99.0)]              # one close above, then back under: still bearish
    assert E4.cel_state(ctx, row, i) == -1
    state["rows"] = [(101.0, 102.0, 100.5, 101.0), (101.0, 101.2, 100.2, 100.8), (100.8, 101.0, 98.0, 99.0)]       # two closes above, then a close under: bearish again
    assert E4.cel_state(ctx, row, i) == -1
    bear = BR(cel_kind=-1, cel_ce=100.0, cel_top=104.0, cel_bot=96.0)                    # the bearish gap mirror: above the CE stay bullish
    state["rows"] = [(101.0, 102.0, 100.5, 101.0)]
    assert E4.cel_state(ctx, bear, i) == 1
    state["rows"] = [(99.0, 99.5, 98.0, 99.0), (99.0, 99.4, 98.0, 98.5)]
    assert E4.cel_state(ctx, bear, i) == -1
    assert E4.cel_state(ctx, BR(cel_kind=0), i) == 0


# --- item 110: the salient ranges --------------------------------------------------------------------------------------------------

def _zigzag(points, wick=0.1):
    return [(x, x + wick, x - wick, x) for x in points]                            # one bar per turning point: strict swing highs / lows


def test_salient_eq_and_gate(monkeypatch):
    p = P(salient_pd=(60,))
    ctx = cx(p, bias=BR())
    i = at(ctx, "10:10")
    state = {}
    monkeypatch.setattr(B1, "tf_complete", lambda c_, m, i_: _bars(state["rows"], c_))
    state["rows"] = _zigzag([100, 110, 95, 112, 93, 108, 96, 111, 94, 100])
    eq = E4.salient_eq(ctx, 60, i)
    assert eq == pytest.approx(102.5, abs=0.3)                                    # the intermediate high 112 and low 93
    sd = ctx.sides_map[1]
    assert E4.order_ok(ctx, sd, order(entry=101.0), "AM", i, p) is None            # a long below the 1h EQ
    assert E4.order_ok(ctx, sd, order(entry=104.0), "AM", i, p) == "x_bh4_salient_pd"      # a long above it
    ssd = ctx.sides_map[-1]
    assert E4.order_ok(ctx, ssd, short_order(104.0), "AM", i, p) is None and E4.order_ok(ctx, ssd, short_order(101.0), "AM", i, p) == "x_bh4_salient_pd"
    state["rows"] = _zigzag([100, 101, 100])
    assert E4.salient_eq(ctx, 60, i) is None and E4.order_ok(ctx, sd, order(entry=140.0), "AM", i, p) is None      # no range: no gate
    pd_ = P(salient_pd=(1440,))
    h = hist_closes(D1, [100, 110, 95, 112, 93, 108, 96, 111, 94, 100], hi_pad=0.1)            # the completed daily sessions as the same zigzag
    assert E4.salient_eq(cx(pd_, hist=h), 1440, i) == pytest.approx(102.5, abs=0.3)
    cd = cx(pd_, hist=h, bias=BR())
    assert E4.order_ok(cd, cd.sides_map[1], order(entry=104.0), "AM", i, pd_) == "x_bh4_salient_pd" and E4.order_ok(cd, cd.sides_map[1], order(entry=101.0), "AM", i, pd_) is None


# --- items 169 / 177 / 178 / 179: the htf range, the grid ---------------------------------------------------------------------------

def test_swing_extreme_block():
    p = P(swing_extreme_block=True)
    ctx = cx(p, bias=BR(htf_rng_lo=100.0, htf_rng_hi=110.0, htf_rng_dir=1))
    i = at(ctx, "09:50")
    sd, ssd = ctx.sides_map[1], ctx.sides_map[-1]
    assert E4.order_ok(ctx, sd, order(entry=108.5), "AM", i, p) == "x_bh4_swing_extreme"        # 0.85: no new longs at 0.8 and above
    assert E4.order_ok(ctx, sd, order(entry=107.9), "AM", i, p) is None
    assert E4.order_ok(ctx, sd, order(entry=111.0), "AM", i, p) == "x_bh4_swing_extreme"        # beyond the range
    assert E4.order_ok(ctx, ssd, short_order(102.5), "AM", i, p) == "x_bh4_swing_extreme"       # 0.25: no new shorts at 0.3 and below
    assert E4.order_ok(ctx, ssd, short_order(106.0), "AM", i, p) is None
    assert E4.order_ok(cx(p, bias=BR()), sd, order(entry=108.5), "AM", i, p) is None            # no range column: nothing


def test_grid_tags_grade_confluence_and_pd_need_array():
    p = P(pd_grid=True, grade_confluence=True)
    ctx = cx(p, bias=BR(grid_lo=100.0, grid_hi=200.0))
    i = at(ctx, "09:50")
    sd = ctx.sides_map[1]
    o = order(entry=130.0)                                                          # 30 %: the second quadrant (1-based), discount half, eighth 2
    assert E4.order_ok(ctx, sd, o, "AM", i, p) is None
    assert "grid_q2_disc_k2" in o["lv_tags"] and "grade_confluence" not in o["lv_tags"]
    o2 = order(entry=137.9)                                                         # within 10 % of a grid spacing (12.5) of the k=3 line at 137.5
    E4.order_ok(ctx, sd, o2, "AM", i, p)
    assert "grade_confluence" in o2["lv_tags"]
    o3 = order(entry=160.0)                                                         # premium: a long at a line in premium is not graded
    E4.order_ok(ctx, sd, o3, "AM", i, p)
    assert "grade_confluence" not in o3["lv_tags"]
    ssd = ctx.sides_map[-1]
    o4 = short_order(162.6)                                                         # a short near the 5/8 line (162.5) in premium
    E4.order_ok(ctx, ssd, o4, "AM", i, p)
    assert "grade_confluence" in o4["lv_tags"]
    pn = P(pd_need_array=True)
    arr_ctx = cx(pn, bias=BR(grid_lo=100.0, grid_hi=200.0), conf=Conf(at_tfs=("D",)))
    none_ctx = cx(pn, bias=BR(grid_lo=100.0, grid_hi=200.0), conf=Conf(at_tfs=()))
    assert E4.order_ok(arr_ctx, arr_ctx.sides_map[1], order(entry=110.0), "AM", i, pn) is None                   # k=0: the discount of its quadrant, inside a daily array
    assert E4.order_ok(none_ctx, none_ctx.sides_map[1], order(entry=110.0), "AM", i, pn) == "x_bh4_pd_need_array"      # range position alone is no signal
    assert E4.order_ok(arr_ctx, arr_ctx.sides_map[1], order(entry=120.0), "AM", i, pn) == "x_bh4_pd_need_array"       # k=1: the premium of its quadrant
    assert E4.order_ok(arr_ctx, arr_ctx.sides_map[-1], short_order(120.0), "AM", i, pn) is None                   # the mirror: odd eighth = the premium of the quadrant


def test_matrix_monthly_range_program_and_failed_break_tags():
    p = P(matrix_tfs=("D", "W"), monthly_range=True, program_tag=True, failed_consol_break=True, htf_range_arrays=True)
    row = BR(mx_W_eq=105.0, m_rng_dir=1, m_rng_lo=95.0, m_rng_hi=125.0, program=1, failed_break=-1, htf_rng_lo=90.0, htf_rng_hi=130.0)
    ctx = cx(p, bias=row)
    i = at(ctx, "09:50")
    o = order(entry=102.0)
    assert E4.order_ok(ctx, ctx.sides_map[1], o, "AM", i, p) is None
    tags = o["lv_tags"].split("|")
    assert {"mx_W_disc", "mrng_in", "program_agree", "failed_break_oppose"} <= set(tags) and any(t.startswith("htfrng_") for t in tags)


# --- items 51..: the monthly flow, the breaker regime ----------------------------------------------------------------------------

def test_monthly_flow_and_breaker_regime_gates():
    p = P(monthly_flow_gate=True, breaker_regime=True)
    i = at(cx(p, bias=BR()), "09:50")
    ctx = cx(p, bias=BR(m_flow=-1, brk_regime=0))
    assert E4.side_ok(ctx, p, 1, "AM", i) == "x_bh4_monthly_flow" and E4.side_ok(ctx, p, -1, "AM", i) is None
    ctx2 = cx(p, bias=BR(m_flow=0, brk_regime=-1))
    assert E4.side_ok(ctx2, p, 1, "AM", i) == "x_bh4_breaker_regime" and E4.side_ok(ctx2, p, -1, "AM", i) is None         # longs blocked until a bullish breaker forms
    ctx3 = cx(p, bias=BR(m_flow=1, brk_regime=1))
    assert E4.side_ok(ctx3, p, 1, "AM", i) is None and E4.side_ok(ctx3, p, -1, "AM", i) == "x_bh4_monthly_flow"


# --- the neutral-bias fallbacks and the EQ-violated neutral -------------------------------------------------------------------------

def test_want_adjust_fallbacks_and_eq_invalid():
    p = P(nested_pd_bias=True, trapped_bpr_bias=True, failed_consol_break=True, ifvg_bias=True, htf_eq_invalid=True)
    i = at(cx(p, bias=BR()), "09:50")
    assert BD.want_at(cx(p, bias=BR(combo=0)), p, "AM", i) == 0                                                  # nothing set
    assert BD.want_at(cx(p, bias=BR(combo=0, ifvg_bias=-1)), p, "AM", i) == -1                                    # a neutral bias takes the IFVG
    assert BD.want_at(cx(p, bias=BR(combo=0, ifvg_bias=-1, failed_break=1)), p, "AM", i) == 1                      # ... the failed break first
    assert BD.want_at(cx(p, bias=BR(combo=0, ifvg_bias=-1, failed_break=1, trapped_bpr=-1)), p, "AM", i) == -1     # ... the trapped BPR before it
    assert BD.want_at(cx(p, bias=BR(combo=0, nested_bias=1, trapped_bpr=-1)), p, "AM", i) == 1                     # ... and the nested ranges before that
    assert BD.want_at(cx(p, bias=BR(combo=1, ifvg_bias=-1)), p, "AM", i) == 1                                      # a bias is never overridden
    assert BD.want_at(cx(p, bias=BR(combo=1, eq_invalid=1, htf_rng_dir=1)), p, "AM", i) == 0                         # a weekly close under the EQ: the long bias turns neutral
    assert BD.want_at(cx(p, bias=BR(combo=-1, eq_invalid=1, htf_rng_dir=1)), p, "AM", i) == -1
    assert BD.want_at(cx(P(), bias=BR(combo=0, ifvg_bias=-1)), P(), "AM", i) == 0                                 # switches off


# --- item 150: the ladder level as an entry array ---------------------------------------------------------------------------------

def test_ladder_rows():
    p = P(ob_ladder=True)
    ctx = cx(p, bias=BR(obl=(104.0, 99.0), obl_dir=1))
    i = at(ctx, "09:50")
    sd = ctx.sides_map[1]
    rows = E4.ladder_rows(ctx, sd, i)
    assert len(rows) == 1 and rows[0][0] == 99.0 and rows[0][1] == 99.0               # the highest level at or under the price (100.1); 104 lies above
    assert E4.ladder_rows(ctx, ctx.sides_map[-1], i) == []                           # the bearish side has no ladder here
    assert E4.ladder_rows(cx(p, bias=BR(obl=(), obl_dir=1)), sd, i) == []
    assert E4.ladder_rows(cx(p, bias=BR(obl=(104.0,), obl_dir=1)), sd, i) == []      # every level above the price


# --- item 170: the leg_pd waiver ------------------------------------------------------------------------------------------------------

def _down_hist(d):
    h = history(d)
    last = h[-1].copy()
    last.iloc[0, last.columns.get_loc("open")] = 106.0                               # a down-close candle: open 106, close 100
    return h[:-1] + [last]


def test_leg_pd_exempt():
    p = P(swing_ignore_eq=True, htf_range_arrays=True)
    ctx = cx(p, bias=BR(htf_rng_dir=1, htf_rng_lo=90.0, htf_rng_hi=130.0), hist=_down_hist(D1))
    i = at(ctx, "09:50")
    sd = ctx.sides_map[1]
    assert E4.leg_pd_exempt(ctx, sd, 99.0, i, p) is True                              # (a) below the close of the last down-close daily candle (100)
    assert E4.leg_pd_exempt(ctx, sd, 105.0, i, p) is False                            # above it, no HTF array
    ctx_arr = cx(p, bias=BR(htf_rng_dir=1, htf_rng_lo=90.0, htf_rng_hi=130.0), hist=_down_hist(D1), conf=Conf(at_tfs=("D",)))
    assert E4.leg_pd_exempt(ctx_arr, ctx_arr.sides_map[1], 105.0, i, p) is True       # (b) inside a daily array between the origin low and the high
    assert E4.leg_pd_exempt(ctx_arr, ctx_arr.sides_map[1], 122.0, i, p) is False      # the 0.8 cap: 0.8 of 90..130 = 122
    assert E4.leg_pd_exempt(cx(p, bias=BR(htf_rng_dir=-1, htf_rng_lo=90.0, htf_rng_hi=130.0), hist=_down_hist(D1)), ctx.sides_map[1], 99.0, i, p) is False      # the range direction is not intact
    assert E4.leg_pd_exempt(cx(p, bias=BR(), hist=_down_hist(D1)), sd, 99.0, i, p) is False


# --- item 80: the IFVG edge add -----------------------------------------------------------------------------------------------------------

def test_ifvg_add_zone():
    p = P(ifvg_edge_add=True)
    ctx = cx(p, bias=BR(ifvg_bias=1, ifvg_top=99.5, ifvg_bot=97.0))
    i = at(ctx, "09:50")
    sd = ctx.sides_map[1]
    pos = dict(fill_i=i - 5, stop=95.0)
    z = E4.ifvg_add_zone(ctx, sd, pos, i, p)
    assert z == (99.5, 97.0)                                                         # bodies held above the edge (the bar's body 100-100.1 >= 99.5): one add at the edge
    assert E4.ifvg_add_zone(ctx, sd, dict(fill_i=i + 1, stop=95.0), i, p) is None    # not after the fill
    assert E4.ifvg_add_zone(ctx, sd, dict(fill_i=i - 5, stop=99.9), i, p) is None    # the edge is not above the stop
    assert E4.ifvg_add_zone(cx(p, bias=BR(ifvg_bias=-1, ifvg_top=99.5, ifvg_bot=97.0)), sd, pos, i, p) is None      # the IFVG is the other side's
    assert E4.ifvg_add_zone(cx(p, bias=BR(ifvg_bias=1, ifvg_top=103.0, ifvg_bot=101.0)), sd, pos, i, p) is None    # the body has not held beyond the edge
    assert S._BH4E is E4


def test_hooks_are_inert_with_everything_off():
    p = Params(**BASE, htf_bias="combo", bias_neutral="both")
    ctx = cx(p, bias=BR(rng_day=1, ipda_pos=0.5, chk_q=-1, m_flow=-1, brk_regime=-1))
    i = at(ctx, "09:50")
    assert not E4.on(p) and not E4.want_on(p)
    assert E4.side_ok(ctx, p, 1, "AM", i) is None and E4.scalp_now(ctx, p, "AM", i, 1) == ""
    o = order()
    assert E4.order_ok(ctx, ctx.sides_map[1], o, "AM", i, p) is None and o["lv_tags"] == ""
    assert E4.want_adjust(ctx, p, "AM", i, 0) == 0
