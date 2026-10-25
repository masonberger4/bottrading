"""Caption-gap pass, package management_exits #2/3, review round 1: tests of the review fixes (management_partials_trailing_exits.md 20, 24, 28, 29, 36, 50, 52, 55, 68, 87, 90, 93, 94, 95, 98, 100,
103, 107, 108) and the short (side -1) mirrors of the long unit books of me2a / me2b / me2c. Same harness as test_caption_gap_me2a.py (hand-made one-minute books, the me2.py hooks called bar by
bar). The short mirror of a book is the same book at K - price (o, h, l, c -> K - o, K - l, K - h, K - c) on the Side(-1); every assertion is made in SIDE space. No platform-specific paths; nothing
here needs market data."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import manage as MG, me1, me2, strategy as S
from mentorship.strategy import Params

from test_caption_gap_me1a import NY, flatrows, mkctx, mkpos, pk, reasons
from test_caption_gap_me2a import fill2, rung, step2
from test_caption_gap_me2b import HH, MARG, PEEL
from test_caption_gap_me2c import A, PD3

K = 0.0                                                            # the Side(-1) mirrors by plain negation: the short book is the long book at -price


def M(v):
    return K - v


def mrows(rows):
    return [(M(o), M(l), M(h), M(c)) for o, h, l, c in rows]


def both(rows, entry, stop, levels=(), sign=1, **kw):
    """(ctx, pos, tr, sd) for a book given in LONG prices; sign -1 runs its mirror on the short Side."""
    if sign < 0:
        ctx = mkctx(mrows(rows), **{k: v for k, v in kw.pop("ctx_kw", {}).items()})
        pos, tr, sd = mkpos(ctx, -1, kw.pop("fill_i", 0), M(entry), M(stop), levels=tuple(M(v) for v in levels), **kw)
    else:
        ctx = mkctx(rows, **kw.pop("ctx_kw", {}))
        pos, tr, sd = mkpos(ctx, 1, kw.pop("fill_i", 0), entry, stop, levels=tuple(levels), **kw)
    return ctx, pos, tr, sd


def sx(sd, tr, n=0):
    """The n-th exit price in side space."""
    return float(sd.x(tr.exits[n][1]))


# --- review fix: the stop-lifting central place (28 / 107) -------------------------------------------------------------------------------------------

def test_raise_stop_central_gate_and_cap():
    pos = dict(stop=100.0, day_trade=False)
    MG.raise_stop(pos, 101.0)
    assert pos["stop"] == 101.0
    pos["wgate"] = 120.0                                                                  # the overhead-wick gate: a TRAIL waits, a BE-like lock does not
    MG.raise_stop(pos, 102.0, trail=True)
    assert pos["stop"] == 101.0
    MG.raise_stop(pos, 102.0)
    assert pos["stop"] == 102.0
    pos2 = dict(stop=100.0, day_trade=False, stop_cap=105.0)                              # the stop cap refuses a level above it for every caller
    MG.raise_stop(pos2, 106.0)
    MG.raise_stop(pos2, 106.0, trail=True)
    assert pos2["stop"] == 100.0
    MG.raise_stop(pos2, 104.0, trail=True)
    assert pos2["stop"] == 104.0
    pos3 = dict(stop=100.0, day_trade=False, freeze=True)
    MG.raise_stop(pos3, 103.0, trail=True)
    assert pos3["stop"] == 100.0


@pytest.mark.parametrize("what", ["cap", "wgate", "free"])
def test_trail_first_fvg_site_honours_cap_and_gate(what):
    rows = [(4000, 4001, 3999, 4000.5), (4000.5, 4003, 4000.5, 4002.5), (4002.5, 4010, 4002, 4009), (4009, 4012, 4008, 4011)]
    ctx = mkctx(rows)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4040.0,))
    pos["ext_i"] = 0
    if what == "cap":
        pos["stop_cap"] = 3995.0
    if what == "wgate":
        pos["wgate"] = 4020.0
    MG.trail_extra(sd, pos, 3, pk(trail_first_fvg=True))
    assert (pos["stop"] > 3990.0) == (what == "free")


# --- 20 pool lock ---------------------------------------------------------------------------------------------------------------------------------

def test_pool_lock_default_and_flags():
    assert Params().pool_lock_pts == 1.5 and me2.any_on(Params()) and not me2.any_on(Params(pool_lock_pts=0.0))
    ctx = mkctx(flatrows(3, 4080.0, 1.0) + [(4085, 4090.5, 4084, 4090), (4090, 4100, 4089.9, 4099)])
    p = pk(pool_lock_pts=1.5, pool_lock_day_done=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4080.0, 4070.0, levels=(4085.0, 4089.75, 4108.0), fracs=(0.4, 0.4, 0.2), kinds=["pool", "pool", "pool"])
    pos["stop_cap"] = 4075.0                                                              # the raise itself is refused (above the stop cap) ...
    fill2(ctx, sd, pos, tr, p)
    rung(ctx, sd, pos, tr, p, 0, 3)
    rung(ctx, sd, pos, tr, p, 1, 3)
    assert pos["stop"] == 4070.0 and pos.get("no_reentry") and pos.get("pool_locked")      # ... the no-re-entry and the day-done markers are set all the same
    done = {"AM": False, "PM": False}
    tr.exits.append((ctx.idx[4], 4108.0, 2, "t3"))
    tr.final_hit = True
    pos["left"] = 0
    me2.after_close(pos, tr, done, "AM", {}, p)
    assert done == {"AM": True, "PM": True}


# --- 24 swing low since the fill ------------------------------------------------------------------------------------------------------------------

def test_swing_at_array_ignores_prefill_lows():
    rows = [(4090, 4092, 4086, 4091), (4091, 4096, 4094, 4095), (4095, 4097, 4091, 4096.8), (4096.8, 4098, 4095, 4097.5), (4097.5, 4101, 4097, 4100.5), (4100.5, 4102, 4100, 4101.5)]
    ctx = mkctx(rows)
    p = pk(trail_swing_at_array=True)
    pos, tr, sd = mkpos(ctx, 1, 3, 4097.0, 4080.0, levels=(4101.0, 4120.0), fracs=(0.8, 0.2), kinds=["array", "pool"])
    fill2(ctx, sd, pos, tr, p)
    rung(ctx, sd, pos, tr, p, 0, 5)
    assert pos["stop"] == 4080.0                                                          # the pivot low 4091 (bar 2) formed before the fill at bar 3 is no swing "since the fill"


# --- 29 OB MT only for an OB entry ----------------------------------------------------------------------------------------------------------------

def test_ob_mt_run_only_for_ob_entries():
    rows = [(4004, 4005, 3998, 4000), (4000, 4004.5, 3999.5, 4004), (4004, 4006, 4003.5, 4005), (4005, 4012.5, 4004.5, 4012), (4012, 4013, 4011, 4012.5)]
    ctx = mkctx(rows)
    p = pk(ob_stop_to_mt_after_run=True)
    pos, tr, sd = mkpos(ctx, 1, 2, 4004.0, 3998.0, levels=(4040.0,), kind="fvg")
    fill2(ctx, sd, pos, tr, p)
    assert pos["me2"].get("ob_mt") is None                                                 # an FVG entry: the rule is an OB-entry rule
    pos, tr, sd = mkpos(ctx, 1, 2, 4002.0, 3998.0, levels=(4040.0,), kind="ob", fvg_ce=4001.5)
    pr = pk(ob_stop_to_mt_after_run=True, mt_mode="range")                                # the range MT (3998 + 4005) / 2 = 4001.5 is not inside the body: the candle is still found by its MT
    fill2(ctx, sd, pos, tr, pr)
    assert pos["me2"]["ob_mt"] == pytest.approx(4001.5)


# --- 36 HTF bank: the bias draw array, a rung printing at the array --------------------------------------------------------------------------------

def test_htf_bank_rung_at_the_array():
    rows = flatrows(2, 4100.0, 1.0) + [(4100, 4149, 4099, 4148), (4148, 4152, 4147, 4151)]
    ctx = mkctx(rows)
    p = pk(htf_bank=0.5, be_pad_pts=1.0)
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4150.0, 4170.0), fracs=(0.3, 0.7), kinds=["array", "pool"], n=6)
    fill2(ctx, sd, pos, tr, p, htf_draw=(4150.0, 4160.0))
    rung(ctx, sd, pos, tr, p, 0, 3)                                                       # the planned rung prints at the HTF array: the bank goes with it
    assert reasons(tr)[0] == "t1" and "htf_bank" in reasons(tr) and pos["no_adds"]


def test_htf_draw_prefers_the_bias_draw_array():
    rows = flatrows(4, 4100.0, 1.0)
    z1 = dict(top=4130.0, bottom=4120.0, tf="D", src=0, known=0.0, dead=1e30)               # the nearest array
    z2 = dict(top=4160.0, bottom=4150.0, tf="D", src=0, known=0.0, dead=1e30)               # the array the bias frames the trade with
    ctx = mkctx(rows, conf=SimpleNamespace(opposing_ext=lambda *a, **k: [dict(z1), dict(z2)]), bias_row={"draw_ord": 1, "draw_ord_lvl": 4155.0})
    sd = ctx.sides_map[1]
    pos, tr, _ = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4170.0,))
    from mentorship import targets as TP, tp3 as T3
    old = (T3._now, T3._zone_edges, TP.extreme_since)
    T3._now = lambda ctx_, i_: pd.Timestamp(ctx_.idx[i_]) + pd.Timedelta(minutes=1)
    T3._zone_edges = lambda sd_, r: (float(r["bottom"]), float(r["top"]))
    TP.extreme_since = lambda *a, **k: None
    try:
        assert me2._htf_draw(ctx, sd, pos, 4100.0, 3, pk(htf_bank=0.5)) == (4150.0, 4160.0)
        ctx.bias_row = {"draw_ord": -1, "draw_ord_lvl": 4155.0}
        assert me2._htf_draw(ctx, sd, pos, 4100.0, 3, pk(htf_bank=0.5)) == (4120.0, 4130.0)      # no bias draw this way: the nearest untouched array
    finally:
        T3._now, T3._zone_edges, TP.extreme_since = old


# --- 50 peel: armed by the target NWOG only ---------------------------------------------------------------------------------------------------------

def test_peel_needs_the_nwog_to_be_the_target():
    ctx = mkctx(PEEL)
    p = pk(peel_singles=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4098.0, 4090.0, levels=(4120.0,), n=16)
    pos["left"] = 4
    fill2(ctx, sd, pos, tr, p, nwog=(4000.0, 4010.0))                                       # an NWOG far below the trade: price is over its CE but it is nobody's target
    step2(ctx, sd, pos, tr, p, 1, 11)
    assert not tr.exits and not pos["me2"]["peel_armed"]
    # a rung that filled at the NWOG CE arms it
    pos, tr, sd = mkpos(ctx, 1, 0, 4098.0, 4090.0, levels=(4105.0, 4150.0), fracs=(0.5, 0.5), kinds=["array", "pool"], n=16)
    fill2(ctx, sd, pos, tr, p, nwog=(3000.0, 3010.0))
    assert not pos["me2"]["peel_armed"]
    pos["me2"]["nwog"] = (4100.0, 4110.0)                                                   # the rung (4105) is the NWOG CE
    rung(ctx, sd, pos, tr, p, 0, 3)
    assert pos["me2"]["peel_armed"]


# --- 52 PM macro runner -----------------------------------------------------------------------------------------------------------------------------

def test_pm_macro_retarget_and_pending_stop():
    t0 = 15 * 60 + 40
    rows = [(4000, 4001, 3999, 4000)] + [(4000, 4001, 3999.5, 4000.5)] * 4 + [(4000.5, 4010.5, 4000, 4000.8)] + [(4001, 4001.5, 4000.6, 4001.2)] * 3 + [(4001.2, 4004, 4001, 4003)]
    ctx = mkctx(rows, t0=t0)
    p = pk(pm_macro_runner=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4010.0, 4020.0, 4030.0, 4040.0), fracs=(0.25,) * 4, kinds=["pool", "array", "pool", "pool"], n=4)
    tr.session = "PM"
    fill2(ctx, sd, pos, tr, p)
    assert pos["runner"] and len(pos["levels"]) == 3
    rung(ctx, sd, pos, tr, p, 0, 5)                                                       # the first partial closes at 4000.8: under avg + 1 -> the stop cannot lift yet
    assert pos["stop"] == pytest.approx(4000.55) and pos["me2"]["pm_stop_pending"]                # clamped one tick under the close, +1 pt still pending
    assert pos["level_kinds"][1] == "pool" and pos["levels"][1] == 4030.0                  # the next rung is the next untaken pool rung (not the array)
    step2(ctx, sd, pos, tr, p, 6, 8)
    assert pos["stop"] < 4001.0 and pos["me2"]["pm_stop_pending"]
    step2(ctx, sd, pos, tr, p, 9)                                                         # the close 4003 allows avg + 1 = 4001
    assert pos["stop"] == pytest.approx(4001.0) and not pos["me2"]["pm_stop_pending"]


# --- 55 stall exits ---------------------------------------------------------------------------------------------------------------------------------

def test_stall_resets_on_a_new_high_and_against_reading():
    rows = [(4000, 4001, 3999, 4000), (4000, 4020, 3999.5, 4019), (4019, 4019.2, 4017, 4017.5)] + [(4019.2, 4019.8, 4019.1, 4019.7)] * 4 + [(4019.7, 4021, 4019.5, 4020.5)] + [(4020.5, 4020.8, 4020.2, 4020.6)] * 2
    ctx = mkctx(rows)
    p = pk(stall_exits=True, stall_bars=3)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4030.0,), n=10)
    pos["left"] = 2
    fill2(ctx, sd, pos, tr, p)
    pos["me2"]["rebal_done"] = True
    step2(ctx, sd, pos, tr, p, 1, 6)
    assert pos["me2"]["stall_on"]
    step2(ctx, sd, pos, tr, p, 7)                                                         # a new high (4021): the stall is over
    assert not pos["me2"]["stall_on"]
    step2(ctx, sd, pos, tr, p, 8, 9)
    assert not pos["me2"]["stall_on"]                                                      # two quiet bars are not enough again
    # the 'against the trade' reading: a poke under a relative equal low that closes back above it closes the rest
    rows2 = [(4000, 4001, 3999, 4000), (4000, 4020, 3999.5, 4019), (4013, 4013.2, 4012, 4012.5), (4012.5, 4014, 4010.0, 4013), (4013, 4013.5, 4012.2, 4013.2), (4013.2, 4014, 4010.25, 4013.6),
             (4013.6, 4014.0, 4012.8, 4013.4), (4013.4, 4014.0, 4009.0, 4012.5)]
    ctx2 = mkctx(rows2)
    pa = pk(stall_exits=True, stall_bars=3, stall_reh_against=True)
    pos, tr, sd = mkpos(ctx2, 1, 0, 4000.0, 3990.0, levels=(4030.0,), n=10)
    pos["left"] = 2
    fill2(ctx2, sd, pos, tr, pa)
    pos["me2"]["rebal_done"] = True
    step2(ctx2, sd, pos, tr, pa, 1, 7)
    assert reasons(tr) == ["stall_rel"] and pos["left"] == 0
    pos, tr, sd = mkpos(ctx2, 1, 0, 4000.0, 3990.0, levels=(4030.0,), n=10)
    pos["left"] = 2
    pk3 = pk(stall_exits=True, stall_bars=3)
    fill2(ctx2, sd, pos, tr, pk3)
    pos["me2"]["rebal_done"] = True
    step2(ctx2, sd, pos, tr, pk3, 1, 7)
    assert reasons(tr) == []                                                              # the default reading (a poke over equal highs) does not see it


# --- 68 / 87 -------------------------------------------------------------------------------------------------------------------------------------

def test_ote_leave_for_an_fvg_path_ote_limit():
    inside = [(4030, 4036, 4028, 4034)] * 3
    ctx = mkctx([(4030, 4031, 4025, 4030)] + inside)
    p = pk(ote_leave_bars=3)
    pos, tr, sd = mkpos(ctx, 1, 0, 4030.0, 4015.0, levels=(4100.0,), kind="fvg", leg=(4000.0, 4100.0))
    fill2(ctx, sd, pos, tr, p, ote_fill=True)                                              # the order tag of an ote="limit" fill through ote_adjust
    assert pos["me2"]["ote62"] == pytest.approx(4038.0)
    step2(ctx, sd, pos, tr, p, 1, 3)
    assert reasons(tr) == ["ote_slow"] and pos["left"] == 5


# --- 90 three arrays: wick CE array, entry array excluded, the spec's numbers ----------------------------------------------------------------------

def test_pd3_wick_array_and_entry_excluded():
    # bar 1 has a long lower wick: low 4090, body 4096 .. 4098 -> the wick CE is (4096 + 4090) / 2 = 4093
    rows = [(4100, 4101, 4099, 4100)] * 3 + [(4098, 4098.5, 4090, 4096)] + [(4096, 4103, 4095.5, 4102), (4102, 4106, 4101, 4105)]
    ctx = mkctx(rows)
    pos, tr, sd = mkpos(ctx, 1, 5, 4105.0, 4085.0, levels=(4140.0,))
    out = me2._pd3_arrays(sd, pos, 4, pk(rip_wick_mult=1.5), 4105.0, ctx)
    assert any(a.kind == "wick" and a.level == pytest.approx(4093.0) for a in out)
    assert [a.level for a in out] == sorted([a.level for a in out], reverse=True)
    # the entry FVG itself (bottom == pos["fvg_bottom"]) is not an array against the trade
    pos["fvg_bottom"] = 4093.0                                                             # the order's FVG bottom coincides with the wick CE level: that row is the entry array
    out2 = me2._pd3_arrays(sd, pos, 4, pk(rip_wick_mult=1.5), 4105.0, ctx)
    assert all(abs(a.level - 4093.0) > 0.25 for a in out2)


# --- 93 a failed reference is not judged again ------------------------------------------------------------------------------------------------------

def test_ref_speed_failed_reference_is_remembered():
    # a near miss: the high comes within 1 pt of the reference 4020 three bars in a row with lower closes without touching it
    rows = [(4000, 4001, 3999, 4000), (4000, 4019.5, 3999.5, 4019), (4019, 4019.4, 4018, 4018.5), (4018.5, 4019.2, 4017.5, 4018), (4018, 4019.1, 4016.5, 4017.5), (4017.5, 4019.0, 4016, 4017), (4017, 4019.0, 4016, 4016.5)]
    ctx = mkctx(rows)
    p = pk(ref_speed_check=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4020.0, 4060.0), fracs=(0.5, 0.5))
    fill2(ctx, sd, pos, tr, p)
    pos["me2"]["hi"] = 4000.0
    step2(ctx, sd, pos, tr, p, 1, 6)
    assert reasons(tr).count("slow_ref_pare") <= 1                                         # the pare happens once for the reference 4020, not again on the next bar
    assert 4020.0 in pos["me2"]["rs_failed"]


# --- 94 opposing array: the window is the touch bar and the next --------------------------------------------------------------------------------------

def test_opp_tear_confirmation_is_not_accepted_two_bars_later():
    rows = [(4100, 4101, 4099, 4100), (4100, 4105.5, 4101, 4104), (4104, 4105, 4102, 4103), (4103, 4107, 4102.5, 4106), (4106, 4107, 4105, 4106)]
    ctx = mkctx(rows)
    p = pk(opp_tear_check=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4130.0,))
    fill2(ctx, sd, pos, tr, p, opp=[dict(near=4105.0, ce=4106.5, far=4108.0)], opp_done=set(), opp_win=None)
    step2(ctx, sd, pos, tr, p, 1, 3)                                                       # touch at bar 1, no CE on bar 2: the warning stands even though bar 3 reaches the CE
    assert pos["no_adds"] and pos["warn"] == 1
    # a bar T+1 that undercuts the touch low while reaching the CE is a warning too (the order inside the bar is unknown)
    rows2 = [(4100, 4101, 4099, 4100), (4100, 4105.5, 4101, 4104), (4104, 4107, 4100.5, 4106)]
    ctx2 = mkctx(rows2)
    pos, tr, sd = mkpos(ctx2, 1, 0, 4100.0, 4090.0, levels=(4130.0,))
    fill2(ctx2, sd, pos, tr, p, opp=[dict(near=4105.0, ce=4106.5, far=4108.0)], opp_done=set(), opp_win=None)
    step2(ctx2, sd, pos, tr, p, 1, 2)
    assert pos["no_adds"] and pos["warn"] == 1


def test_opp_tear_orders_blocks_are_rows():
    # the other Side's bullish OB (a bearish OB for the long): a gap at bars 6-8 after the down-close candle at bar 4 .. 5 (side space of the other Side)
    rows = [(4100, 4101, 4099, 4100)] * 4 + [(4101, 4102, 4100, 4100.5), (4100.5, 4101, 4099, 4099.2), (4099.2, 4099.5, 4094, 4094.5), (4094.5, 4095, 4092, 4093), (4093, 4093.5, 4090, 4091)]
    ctx = mkctx(rows)
    sd = ctx.sides_map[1]
    out = me2._opp_obs(ctx, sd, 8, pk(), 4085.0)
    assert all(r["near"] <= r["ce"] <= r["far"] and r["near"] > 4085.0 for r in out)


# --- 95 the broken edge ---------------------------------------------------------------------------------------------------------------------------

def test_edge_bump_picks_the_gap_the_leg_broke():
    # a bearish gap 4397-4398 (bars 0-2) that the entry leg trades over (bar 3 high 4404), entry at 4402; a second bearish gap far above (never broken) is no candidate
    rows = [(4400, 4401, 4398, 4399), (4399, 4399, 4394, 4395), (4395, 4397, 4393, 4396.5), (4396.5, 4404, 4396, 4403.5), (4403.5, 4404, 4401.5, 4402)]
    ctx = mkctx(rows)
    ctx.equity = 100000.0
    p = pk(edge_bump_add=True)
    pos, tr, sd = mkpos(ctx, 1, 4, 4402.0, 4390.0, levels=(4440.0,))
    pos["ext_i"] = 2
    fill2(ctx, sd, pos, tr, p)
    assert pos["me2"]["edge"] == pytest.approx(4398.0)
    rows2 = [(4400, 4401, 4398, 4399), (4399, 4399, 4394, 4395), (4395, 4397, 4393, 4396.5), (4396.5, 4397.5, 4396, 4397), (4397, 4398, 4396.5, 4397.5)]     # price never traded over the gap: no broken edge
    ctx2 = mkctx(rows2)
    pos, tr, sd = mkpos(ctx2, 1, 4, 4402.0, 4390.0, levels=(4440.0,))
    pos["ext_i"] = 2
    fill2(ctx2, sd, pos, tr, p)
    assert pos["me2"]["edge"] is None


# --- 98 sister counter -----------------------------------------------------------------------------------------------------------------------------

def test_sister_uses_its_own_counter_and_runs():
    es = [(4100, 4101, 4099, 4100.5), (4100.5, 4102, 4100, 4101), (4101, 4102, 4100.5, 4101.5)]
    ctx = mkctx(es)
    nq = [(15020, 15025, 15015, 15022), (15022, 15030, 15018, 15025), (15025, 15028, 15012, 14999.0)]
    o, h, l, c = [np.array(x, float) for x in zip(*nq)]
    ps = S.Side(1, o, h, l, c, 1, 0.0)
    pctx = SimpleNamespace(start=0)
    ppos = pd.DataFrame({"x": 0}, index=ctx.idx)
    p = pk(sister_breaker_hold=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4130.0,))
    fill2(ctx, sd, pos, tr, p, sis=(15000.0, 15010.0), sis_below=False)
    before = me2.HITS.get("eval_sister", 0)
    step2(ctx, sd, pos, tr, p, 1, 2, pctx=pctx, psides={1: ps}, ppos=ppos)
    assert pos.get("sis_warn") == 1 and pos.get("warn") == 1 and me2.HITS.get("eval_sister", 0) > before


# --- 100 chop close: the reentry_half block is not suppressed ----------------------------------------------------------------------------------------

def test_chop_reentry_flag_leaves_reentry_half_alone():
    ctx = mkctx(flatrows(3, 4000.0, 1.0))
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4040.0,))
    p = pk(chop_close=True, after_chop_exit="reentry_allowed", reentry_half=True)
    fill2(ctx, sd, pos, tr, p)
    pos["me2"]["chop_closed"] = True
    tr.exits.append((ctx.idx[2], 3998.0, 10, "chop_close"))                                # a loss
    pos["left"] = 0
    state = {"reentered": {}}
    me2.after_close(pos, tr, {"AM": False, "PM": False}, "AM", state, p)
    assert not state["reentered"].get("AM")                                                # the engine's own block follows and sets it
    tr.exits[-1] = (ctx.idx[2], 4002.0, 10, "chop_close")                                  # a win: the flag (half risk of the next try) is set here
    me2.after_close(pos, tr, {"AM": False, "PM": False}, "AM", state, p)
    assert state["reentered"].get("AM")


# --- 103 fulcrum scope ----------------------------------------------------------------------------------------------------------------------------

def test_fulcrum_speed_only_for_fulcrum_anchored_trades():
    slow = [(4010, 4011, 4009, 4010), (4010, 4021, 4009.5, 4020.5), (4020.5, 4024, 4020, 4023), (4023, 4025, 4022, 4024), (4024, 4026, 4023, 4025), (4025, 4027, 4024, 4026), (4026, 4028, 4025, 4026.5)]
    for anchor, exits in (("fulcrum", True), ("leg", False)):
        ctx = mkctx(slow)
        p = pk(fulcrum_speed_bars=5, sd_anchor=anchor)
        pos, tr, sd = mkpos(ctx, 1, 0, 4010.0, 4000.0, levels=(4020.0, 4030.0, 4050.0), fracs=(0.3, 0.4, 0.3), kinds=["pool", "sd_half", "sd_mm"])
        fill2(ctx, sd, pos, tr, p)
        step2(ctx, sd, pos, tr, p, 1, len(slow) - 1)
        assert (reasons(tr) == ["fulcrum_slow"]) == exits
    # with fulcrum_exit on, only the fulcrum_ladder shape counts (the 'trail' mode has one -1 SD rung and no pool)
    ctx = mkctx(slow)
    p = pk(fulcrum_speed_bars=5, sd_anchor="fulcrum", fulcrum_exit="ladder")
    pos, tr, sd = mkpos(ctx, 1, 0, 4010.0, 4000.0, levels=(4050.0,), fracs=(1.0,), kinds=["sd"])
    tr.lv_tags = "fulcrum_trail"
    fill2(ctx, sd, pos, tr, p)
    assert pos["me2"]["fp_pool"] is None
    pos, tr, sd = mkpos(ctx, 1, 0, 4010.0, 4000.0, levels=(4020.0, 4030.0, 4050.0), fracs=(0.33, 0.33, 0.34), kinds=["pool", "sd", "sd"])
    tr.lv_tags = "fulcrum_ladder"
    fill2(ctx, sd, pos, tr, p)
    assert pos["me2"]["fp_pool"] == 4020.0 and pos["me2"]["fp_sd"] == 4030.0


# --- the short mirrors of the long unit books ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("sign", [1, -1])
@pytest.mark.parametrize("low,exits", [(4097.75, True), (4098.25, False)])
def test_hh_low_hold_both_sides(sign, low, exits):
    rows = HH + [(4101, 4102, low, 4101.5)]
    ctx, pos, tr, sd = both(rows, 4090.0, 4080.0, (4140.0,), sign, n=6)
    pos["t1_done"] = True
    p = pk(hh_low_hold=True)
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 6)
    assert (reasons(tr) == ["hh_low"] and pos["left"] == 0) == exits
    if exits:
        assert sx(sd, tr) == pytest.approx(4098.0)


@pytest.mark.parametrize("sign", [1, -1])
def test_marginal_and_peel_both_sides(sign):
    ctx, pos, tr, sd = both(MARG, 4000.0, 3990.0, (4030.0, 4040.0), sign, fracs=(0.5, 0.5))
    p = pk(marginal_ext_warn=True, marginal_exit=True)
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 3)
    assert reasons(tr) == ["marginal"] and pos["left"] == 0
    ctx, pos, tr, sd = both(PEEL, 4098.0, 4090.0, (4120.0,), sign, n=16)
    pos["left"] = 4
    pp = pk(peel_singles=True)
    fill2(ctx, sd, pos, tr, pp, nwog=(4100.0, 4120.0))
    step2(ctx, sd, pos, tr, pp, 6, 10)
    assert reasons(tr)[:3] == ["peel"] * 3 and pos["left"] == 1 and sx(sd, tr) == pytest.approx(4114.5)


@pytest.mark.parametrize("sign", [1, -1])
def test_stall_exits_reh_both_sides(sign):
    rows = [(4000, 4001, 3999, 4000), (4000, 4020, 3999.5, 4019), (4013, 4013.2, 4012, 4012.5), (4012.5, 4015.0, 4012, 4013), (4013, 4013.5, 4012.2, 4013.2), (4013.2, 4015.25, 4012.6, 4013.6),
            (4013.6, 4014.0, 4012.8, 4013.4), (4013.4, 4016.0, 4013, 4014.5)]
    ctx, pos, tr, sd = both(rows, 4000.0, 3990.0, (4030.0,), sign, n=10)
    pos["left"] = 2
    p = pk(stall_exits=True, stall_bars=3)
    fill2(ctx, sd, pos, tr, p)
    pos["me2"]["rebal_done"] = True
    step2(ctx, sd, pos, tr, p, 1, 7)
    assert reasons(tr) == ["stall_reh"] and pos["left"] == 0


@pytest.mark.parametrize("sign", [1, -1])
def test_three_arrays_both_sides(sign):
    rows = [(4104, 4105, 4103, 4104), (4104, 4104.5, 4094.0, 4095.5)]
    ctx, pos, tr, sd = both(rows, 4104.0, 4090.0, (4140.0,), sign)
    arrays = [SimpleNamespace(level=a.level, top=a.top, bottom=a.bottom, kind=a.kind) for a in PD3]
    p = pk(three_array_mode="trade")
    fill2(ctx, sd, pos, tr, p, pd3=arrays)
    step2(ctx, sd, pos, tr, p, 1)
    assert reasons(tr) == ["pd3_trade"]
    assert sx(sd, tr) == pytest.approx(4094.5)


@pytest.mark.parametrize("sign", [1, -1])
def test_opp_tear_and_fulcrum_both_sides(sign):
    rows = [(4100, 4101, 4099, 4100), (4100, 4105.5, 4101, 4104), (4104, 4105, 4100.5, 4101), (4106, 4107, 4105, 4106)]
    ctx, pos, tr, sd = both(rows, 4100.0, 4090.0, (4130.0,), sign)
    p = pk(opp_tear_check=True)
    fill2(ctx, sd, pos, tr, p, opp=[dict(near=4105.0, ce=4106.5, far=4108.0)], opp_done=set(), opp_win=None)
    step2(ctx, sd, pos, tr, p, 1, 2)
    assert pos["no_adds"] and pos["warn"] == 1
    slow = [(4010, 4011, 4009, 4010), (4010, 4021, 4009.5, 4020.5), (4020.5, 4024, 4020, 4023), (4023, 4025, 4022, 4024), (4024, 4026, 4023, 4025), (4025, 4027, 4024, 4026), (4026, 4028, 4025, 4026.5)]
    ctx, pos, tr, sd = both(slow, 4010.0, 4000.0, (4020.0, 4030.0, 4050.0), sign, fracs=(0.3, 0.4, 0.3), kinds=["pool", "sd_half", "sd_mm"])
    pf = pk(fulcrum_speed_bars=5, sd_anchor="fulcrum")
    fill2(ctx, sd, pos, tr, pf)
    step2(ctx, sd, pos, tr, pf, 1, len(slow) - 1)
    assert reasons(tr) == ["fulcrum_slow"] and tr.exits[0][2] == 3
    assert pos["stop"] == pytest.approx(4009.5 - pf.pad)


@pytest.mark.parametrize("sign", [1, -1])
def test_held_hi_ref_speed_rde_both_sides(sign):
    rows = [(4000, 4001, 3999, 4000), (4000, 4010, 3999.5, 4009), (4009, 4020, 4008, 4019), (4014, 4015, 4012, 4013), (4013, 4030, 4012.5, 4029), (4029, 4029.5, 4027, 4028), (4028, 4032, 4027.5, 4031),
            (4031, 4031.5, 4029, 4030), (4030, 4035, 4029.5, 4034), (4034, 4034.5, 4031, 4032), (4032, 4036, 4031.5, 4035.5)]
    ctx, pos, tr, sd = both(rows, 4000.0, 3990.0, (4040.0,), sign)
    p = pk(rde_partials=True)
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 10)
    assert reasons(tr) == ["rde", "rde"] and sx(sd, tr, 0) == pytest.approx(4032.25) and pos["left"] == 6
