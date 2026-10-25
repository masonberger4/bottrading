"""Caption-gap pass, package management_exits #2/3, part A: the unit tests of the stop-move specs (management_partials_trailing_exits.md 20, 21, 23, 24, 25, 26, 27, 28, 29). Hand-made one-minute
bar books with the me2.py hooks called bar by bar (the position dict and the Side are real, the context is a stub: the harness of test_caption_gap_me1a.py). No platform-specific paths; nothing
here needs market data. The other specs are in test_caption_gap_me2b.py / me2c.py, the study variants and the no-look-ahead runs in test_caption_gap_me2d.py."""
import numpy as np
import pytest

from mentorship import me1, me2, strategy as S
from mentorship.strategy import Params

from test_caption_gap_me1a import flatrows, mkctx, mkpos, pk, reasons


def fill2(ctx, sd, pos, tr, p, **data):
    """me2.on_fill for the stub position; `data` = explicit me2 values (the order's o["me2"])."""
    o = dict(ext_i=pos["ext_i"], me2=dict(data))
    me2.on_fill(ctx, sd, pos, tr, o, pos["fill_i"], p, pos["basis"] / pos["n"])


def rung(ctx, sd, pos, tr, p, k, i, px=None, q=None):
    """Take the ladder rung k on bar i as the ladder loop does (an exit t<k+1>, pos["k"] = k+1, the rung_taken hook)."""
    lv = me1._lv(pos)
    px = lv[k] if px is None else px
    q = q if q is not None else pos["left"] if k == len(lv) - 1 else max(p.lot, int(pos["n"] * pos["fracs"][k]))
    tr.exits.append((ctx.idx[i], sd.x(px), q, f"t{k + 1}"))
    pos["left"] -= q
    pos["k"] = k + 1
    me2.rung_taken(ctx, sd, pos, tr, k, lv[k], i, p)
    pos["t1_done"] = True


def step2(ctx, sd, pos, tr, p, i0, i1=None, **kw):
    """me2.manage for bars i0 .. i1; stops when the position is flat."""
    for i in range(i0, (i0 if i1 is None else i1) + 1):
        if not pos["left"]:
            break
        pos["best"] = max(pos["best"], float(sd.h[i]))
        me2.manage(ctx, sd, pos, tr, i, ctx.idx[i], p, **kw)


# --- X5-tight-stop-under-swept-pool-near-target (20) -------------------------------------------------------------------------------------------------

def test_pool_lock():
    # rungs 4085 (pool) / 4089.75 (pool) / 4108 (final); 80 % closed at 4089.75
    ctx = mkctx(flatrows(3, 4080.0, 1.0) + [(4085, 4090.5, 4084, 4090), (4090, 4100, 4089.9, 4099)])
    p = pk(pool_lock_pts=1.5)
    pos, tr, sd = mkpos(ctx, 1, 0, 4080.0, 4070.0, levels=(4085.0, 4089.75, 4108.0), fracs=(0.4, 0.4, 0.2), kinds=["pool", "pool", "pool"])
    fill2(ctx, sd, pos, tr, p)
    rung(ctx, sd, pos, tr, p, 0, 3)
    assert pos["stop"] == 4070.0 and pos["left"] == 6                                          # 40 % closed < 80 %: the first pool does not lock (and it is not the last pool before the final)
    rung(ctx, sd, pos, tr, p, 1, 3)
    assert pos["left"] == 2 and pos["stop"] == pytest.approx(4088.25) and pos.get("no_reentry")        # 80 % closed at the last pool before the final rung: 1.5 pts under it
    assert pos["stop_log"][-1][0] == "pool_lock"
    # a stop exit blocks the re-entry of the session; a final-rung fill ends the day (pool_lock_day_done)
    done = {"AM": False, "PM": False}
    tr.exits.append((ctx.idx[4], 4088.25, 2, "stop"))
    pos["left"] = 0
    me2.after_close(pos, tr, done, "AM", {}, p)
    assert done == {"AM": True, "PM": False}
    done = {"AM": False, "PM": False}
    p2 = pk(pool_lock_pts=1.5, pool_lock_day_done=True)
    tr.exits[-1] = (ctx.idx[4], 4108.0, 2, "t3")
    tr.final_hit = True
    me2.after_close(pos, tr, done, "AM", {}, p2)
    assert done == {"AM": True, "PM": True}
    # off: nothing
    pos2, tr2, sd2 = mkpos(ctx, 1, 0, 4080.0, 4070.0, levels=(4085.0, 4089.75, 4108.0), fracs=(0.4, 0.4, 0.2), kinds=["pool", "pool", "pool"])
    fill2(ctx, sd2, pos2, tr2, pk())
    rung(ctx, sd2, pos2, tr2, pk(), 1, 3)
    assert pos2["stop"] == 4070.0


# --- X5-no-trail-into-new-inefficiency (21) ------------------------------------------------------------------------------------------------------------

def test_trail_after_pool():
    # a long with an array rung filled first and a pool still ahead: a new FVG does not trail until the pool rung fills
    rows = [(4000, 4001, 3999, 4000.5), (4000.5, 4002, 4000, 4001.5), (4001.5, 4010, 4001, 4009), (4009, 4012, 4008, 4011), (4011, 4020, 4010.5, 4019), (4019, 4025, 4018.5, 4024)]
    ctx = mkctx(rows)
    p = pk(trail_after_pool=True, ladder_trail="fvg")
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4011.0, 4030.0, 4040.0), fracs=(0.3, 0.3, 0.4), kinds=["array", "pool", "pool"], leg=(3995.0, 4003.0))
    fill2(ctx, sd, pos, tr, p)
    assert pos["me2"]["pool_hit"] is False
    step2(ctx, sd, pos, tr, p, 1, 3)
    assert not me1.trail_ok(pos) and pos["me2"]["block_pool"]                              # the leg's 50 % line (3999) is passed: the FVG trail is off
    rung(ctx, sd, pos, tr, p, 0, 3)                                                       # the array rung: still no trail
    me2.manage(ctx, sd, pos, tr, 4, ctx.idx[4], p)
    assert not me1.trail_ok(pos)
    rung(ctx, sd, pos, tr, p, 1, 4, px=4030.0)                                            # the pool rung fills: the next FVG may move the stop
    me2.manage(ctx, sd, pos, tr, 5, ctx.idx[5], p)
    assert me1.trail_ok(pos) and not pos["me2"]["block_pool"]
    pos2, tr2, sd2 = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4011.0, 4030.0), kinds=["array", "pool"], leg=(3995.0, 4003.0))
    fill2(ctx, sd2, pos2, tr2, pk())
    assert me1.trail_ok(pos2)
    # a ladder with no pool has nothing to wait for
    pos3, tr3, sd3 = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4011.0, 4030.0), kinds=["array", "array"], leg=(3995.0, 4003.0))
    fill2(ctx, sd3, pos3, tr3, p)
    step2(ctx, sd3, pos3, tr3, p, 1, 3)
    assert me1.trail_ok(pos3)


# --- X5-raise-stop-conditional-structure (23) ----------------------------------------------------------------------------------------------------------

def test_raise_conditional():
    rows = [(4012, 4013, 4011.5, 4012.5), (4012.5, 4014, 4012, 4013.5), (4013.5, 4014, 4010.5, 4012), (4012, 4012.5, 4010.2, 4010.75), (4010.75, 4012, 4010.5, 4011.5)]
    ctx = mkctx(rows)
    p = pk(raise_on_vi=True)
    # VI 4010-4011 under the entry: a bar with low 4010.5 and close 4012 moves the stop to 4009.75
    pos, tr, sd = mkpos(ctx, 1, 1, 4013.0, 4005.0, levels=(4030.0,))
    fill2(ctx, sd, pos, tr, p, vi=(4010.0, 4011.0))
    step2(ctx, sd, pos, tr, p, 2)
    assert pos["stop"] == pytest.approx(4009.75) and pos["stop_log"][-1][0] == "vi_react"
    # a close at 4010.75 (inside the VI) does not
    pos, tr, sd = mkpos(ctx, 1, 1, 4013.0, 4005.0, levels=(4030.0,))
    fill2(ctx, sd, pos, tr, p, vi=(4010.0, 4011.0))
    step2(ctx, sd, pos, tr, p, 3)
    assert pos["stop"] == 4005.0
    # a break of the short-term high moves the stop to the breaker bottom - tick (4004 - 0.25)
    rows2 = [(4000, 4001, 3999, 4000.5), (4000.5, 4002, 4000, 4001.5), (4001.5, 4003, 4001, 4002.5), (4002.5, 4006.5, 4002, 4006)]
    ctx2 = mkctx(rows2)
    p2 = pk(raise_on_sth_break=True)
    pos, tr, sd = mkpos(ctx2, 1, 1, 4001.5, 3995.0, levels=(4030.0,))
    fill2(ctx2, sd, pos, tr, p2, sth=4005.0, bz_bot=4000.0)
    step2(ctx2, sd, pos, tr, p2, 2)
    assert pos["stop"] == 3995.0
    step2(ctx2, sd, pos, tr, p2, 3)
    assert pos["stop"] == pytest.approx(3999.75) and pos["stop_log"][-1][0] == "sth_break"
    # the 5m-gap requirement (5m engine bars): the break bar alone does not move the stop; the gap its break leaves (the next bar's low over the high two bars back) does
    r5 = [(4001, 4002, 4000.5, 4001.5), (4001.5, 4003, 4001, 4002.5), (4002.5, 4007, 4002.2, 4006.5), (4006.5, 4009, 4005, 4008)]
    ctx5 = mkctx(r5, tf=5)
    p5 = pk(raise_on_sth_break=True, raise_need_5m_fvg=True)
    pos, tr, sd = mkpos(ctx5, 1, 0, 4001.0, 3995.0, levels=(4030.0,))
    fill2(ctx5, sd, pos, tr, p5, sth=4005.0, bz_bot=4000.0)
    step2(ctx5, sd, pos, tr, p5, 1, 2)
    assert pos["stop"] == 3995.0 and pos["me2"]["sth_b"] == 2
    step2(ctx5, sd, pos, tr, p5, 3)
    assert pos["stop"] == pytest.approx(3999.75)


# --- X5-trail-swing-low-at-intermediate-level (24) -------------------------------------------------------------------------------------------------

def test_trail_swing_at_array():
    rows = [(4090, 4092, 4089, 4091), (4091, 4093, 4090.5, 4092), (4092, 4097, 4096, 4096.8), (4096.8, 4098, 4095, 4097.5), (4097.5, 4101, 4097, 4100.5), (4100.5, 4102, 4100, 4101.5)]
    ctx = mkctx(rows)
    p = pk(trail_swing_at_array=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4090.0, 4080.0, levels=(4101.0, 4120.0), fracs=(0.8, 0.2), kinds=["array", "pool"])
    fill2(ctx, sd, pos, tr, p)
    rung(ctx, sd, pos, tr, p, 0, 5)                                                       # the ORG-level array rung: the stop under the latest 1m swing low (4095)
    assert pos["stop"] == pytest.approx(4094.75) and pos["left"] == 2
    assert reasons(tr) == ["t1"]                                                          # the last units stay open
    # a final rung, a pool rung, or the switch off: nothing
    pos, tr, sd = mkpos(ctx, 1, 0, 4090.0, 4080.0, levels=(4101.0, 4120.0), fracs=(0.8, 0.2), kinds=["pool", "pool"])
    fill2(ctx, sd, pos, tr, p)
    rung(ctx, sd, pos, tr, p, 0, 5)
    assert pos["stop"] == 4080.0


# --- X5-071-trail-anchors (25) ---------------------------------------------------------------------------------------------------------------------

def test_trail_071():
    # a long (side space; a short is the mirror): bar 2 is the last down-close candle before the leg, its body MT is (4004 + 4002)/2 = 4003
    rows = [(4000, 4001, 3999, 4000.5), (4000.5, 4005, 4000, 4004.5), (4004, 4004.5, 4001.5, 4002), (4002, 4010, 4001.8, 4009), (4009, 4012, 4008, 4011), (4011, 4013, 4009.5, 4012)]
    ctx = mkctx(rows)
    p = pk(ladder_trail="candle_mt")
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.5, 3990.0, levels=(4030.0,))
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 3)
    assert pos["stop"] == pytest.approx(4003.0 - 0.25) and pos["stop_log"][-1][0] == "candle_mt"        # 1 tick beyond the MT of the last opposite-close candle before the leg
    # two equal pivot lows between the stop and the price move it under them
    rows2 = [(4010, 4012, 4008, 4011), (4011, 4013, 4007.0, 4012), (4012, 4014, 4009, 4013), (4013, 4014.5, 4007.2, 4013.5), (4013.5, 4016, 4010, 4015), (4015, 4017, 4011, 4016), (4016, 4018, 4012, 4017)]
    ctx2 = mkctx(rows2)
    p2 = pk(ladder_trail="eq_pause", eq_tol_pts=0.5)
    pos, tr, sd = mkpos(ctx2, 1, 0, 4010.0, 3990.0, levels=(4040.0,))
    fill2(ctx2, sd, pos, tr, p2)
    step2(ctx2, sd, pos, tr, p2, 1, 5)
    assert pos["stop"] == pytest.approx(4007.0 - 0.25) and pos["stop_log"][-1][0] == "eq_pause"
    # after the penultimate rung the stop sits beyond the last bar's wick
    rows3 = flatrows(2, 4100.0, 1.0) + [(4100, 4112, 4098, 4111), (4111, 4113, 4108.5, 4112)]
    ctx3 = mkctx(rows3)
    p3 = pk(ladder_trail="rej_block")
    pos, tr, sd = mkpos(ctx3, 1, 0, 4100.0, 4090.0, levels=(4110.0, 4125.0, 4140.0), fracs=(0.4, 0.4, 0.2), kinds=["pool", "pool", "pool"])
    fill2(ctx3, sd, pos, tr, p3)
    rung(ctx3, sd, pos, tr, p3, 0, 3)
    assert pos["stop"] == 4090.0                                                           # not yet the penultimate rung
    rung(ctx3, sd, pos, tr, p3, 1, 3, px=4125.0)
    assert pos["stop"] == pytest.approx(4098.0 - 0.25)                                    # beyond the wicks (the lows) of the last two closed bars
    # the combined value runs all three
    assert Params(ladder_trail="071").ladder_trail == "071"
    with pytest.raises(ValueError):
        Params(ladder_trail="nope")


# --- X5-ob-open-after-retests (26) -----------------------------------------------------------------------------------------------------------------

def test_ob_open_retests():
    # OB open 4400; touches at 4400 / 4400.25 / 4399.75, each followed by a higher bar: the stop to 4399.75 on the third
    rows = [(4402, 4403, 4401, 4402.5), (4402.5, 4405, 4402, 4404), (4404, 4404.5, 4400.0, 4402), (4402, 4406, 4401.5, 4405), (4405, 4405.5, 4400.25, 4403), (4403, 4407, 4402.5, 4406),
            (4406, 4406.5, 4399.75, 4404), (4404, 4408, 4403.5, 4407), (4407, 4409, 4406, 4408)]
    ctx = mkctx(rows)
    p = pk(ob_retests=3)
    pos, tr, sd = mkpos(ctx, 1, 0, 4402.0, 4392.0, levels=(4440.0,))
    fill2(ctx, sd, pos, tr, p, ob_open=4400.0)
    step2(ctx, sd, pos, tr, p, 1, 6)
    assert pos["stop"] == 4392.0 and pos["me2"]["ob_n"] == 2                              # two touches do nothing
    step2(ctx, sd, pos, tr, p, 7)
    assert pos["stop"] == pytest.approx(4399.75) and pos.get("freeze") and pos["stop_log"][-1][0] == "ob_open"
    assert not me1.trail_ok(pos)                                                           # frozen until new structure (item 27)
    assert me2.raise_to(pos, 4405.0, "x", 4408.0, p) is False                              # a trail is refused while frozen
    pos2, tr2, sd2 = mkpos(ctx, 1, 0, 4402.0, 4392.0, levels=(4440.0,))
    fill2(ctx, sd2, pos2, tr2, pk(ob_retests=2), ob_open=4400.0)
    step2(ctx, sd2, pos2, tr2, pk(ob_retests=2), 1, 5)
    assert pos2["stop"] == pytest.approx(4399.75)                                          # the count is a parameter


# --- X5-structure-trail-and-cap (27) ---------------------------------------------------------------------------------------------------------------

def test_structure_trail():
    # entry 4100, retrace low 4097, sth 4104: a break of 4104 moves the stop to 4096.75; later bars without new structure leave it there
    rows = [(4100, 4101, 4097.5, 4100.5), (4100.5, 4102, 4099.5, 4101.5), (4101.5, 4105, 4101, 4104.5), (4104.5, 4105, 4103.5, 4104), (4104, 4104.5, 4103.2, 4103.8), (4103.8, 4105.5, 4103.0, 4105),
            (4105, 4106.5, 4104.5, 4106), (4106, 4108, 4105.5, 4107.5), (4107.5, 4107.8, 4106, 4107), (4107, 4109.5, 4106.5, 4109)]
    ctx = mkctx(rows)
    p = pk(ladder_trail="structure")
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4140.0,), retr_low=4097.0)
    fill2(ctx, sd, pos, tr, p, sth=4104.0)
    step2(ctx, sd, pos, tr, p, 1, 1)
    assert pos["stop"] == 4090.0                                                           # sth not yet cleared
    step2(ctx, sd, pos, tr, p, 2, 4)
    assert pos["stop"] == pytest.approx(4096.75) and pos.get("freeze") and pos["me2"]["st_phase"] == 2        # frozen after the break
    # a new pivot low at 4103 (bar 5) and a break of the high that followed it (the pivot high 4108 of bar 7, broken by bar 9) move it to 4102.75
    step2(ctx, sd, pos, tr, p, 5, 8)
    assert pos["stop"] == pytest.approx(4096.75)                                           # the high that followed the low is not yet exceeded
    step2(ctx, sd, pos, tr, p, 9)
    assert pos["stop"] == pytest.approx(4102.75)
    # a day trade keeps its stop
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4140.0,), retr_low=4097.0, day_trade=True)
    fill2(ctx, sd, pos, tr, p, sth=4104.0)
    step2(ctx, sd, pos, tr, p, 1, 9)
    assert pos["stop"] == 4090.0


# --- X5-roll-after-wick-ce-cleared (28) ------------------------------------------------------------------------------------------------------------

def test_trail_wick_gate():
    # an overhead bar 4110-4120 with body top 4114 has the upper-wick CE (4114 + 4120) / 2 = 4117
    rows = [(4112, 4120, 4110, 4114), (4108, 4109, 4105, 4106), (4106, 4107, 4104, 4105.5), (4105.5, 4109, 4105, 4108.5), (4108.5, 4116.5, 4108, 4116), (4116, 4117.25, 4115.5, 4117), (4117, 4119, 4116.5, 4118.5)]
    ctx = mkctx(rows)
    p = pk(trail_wick_gate="trade", ladder_trail="fvg")
    pos, tr, sd = mkpos(ctx, 1, 2, 4105.0, 4095.0, levels=(4140.0,))
    fill2(ctx, sd, pos, tr, p)
    assert pos["wgate"] == pytest.approx(4117.0)
    step2(ctx, sd, pos, tr, p, 3, 4)                                                       # the high is still under 4117: a new FVG leaves the stop unchanged
    assert pos["wgate"] == pytest.approx(4117.0) and not me1.trail_ok(pos)
    step2(ctx, sd, pos, tr, p, 5)                                                          # a bar to 4117.25 opens the gate
    assert pos["wgate"] is None and me1.trail_ok(pos)
    # "close": a high through the CE is not enough
    pos2, tr2, sd2 = mkpos(ctx, 1, 2, 4105.0, 4095.0, levels=(4140.0,))
    pc = pk(trail_wick_gate="close")
    fill2(ctx, sd2, pos2, tr2, pc)
    step2(ctx, sd2, pos2, tr2, pc, 3, 4)
    assert pos2["wgate"] is not None
    step2(ctx, sd2, pos2, tr2, pc, 5)
    assert pos2["wgate"] is not None                                                       # the close (4117) is not above the CE: still shut
    step2(ctx, sd2, pos2, tr2, pc, 6)
    assert pos2["wgate"] is None                                                           # a close at 4118.5 opens it


# --- X5-stop-to-ob-mt-after-run (29) ---------------------------------------------------------------------------------------------------------------

def test_ob_stop_to_mt():
    # an OB with body 4000-4004 (down-close candle: open 4004, close 4000) and range 3998-4005; entry 4004, the stop under 3998
    rows = [(4004, 4005, 3998, 4000), (4000, 4004.5, 3999.5, 4004), (4004, 4006, 4003.5, 4005), (4005, 4012.5, 4004.5, 4012), (4012, 4013, 4011, 4012.5)]
    ctx = mkctx(rows)
    for mode, mt in (("body", 4002.0), ("range", 4001.5)):
        p = pk(ob_stop_to_mt_after_run=True, mt_mode=mode)
        pos, tr, sd = mkpos(ctx, 1, 1, 4004.0, 3997.0, levels=(4040.0,), kind="ob", fvg_ce=4002.0)
        fill2(ctx, sd, pos, tr, p, ob_mt=mt, ob_body=4.0)
        step2(ctx, sd, pos, tr, p, 2)                                                       # a run to 4006 (best - avg = 2 < 8): nothing
        assert pos["stop"] == 3997.0
        step2(ctx, sd, pos, tr, p, 3)                                                       # a run to 4012: 8 >= 2 x the body
        assert pos["stop"] == pytest.approx(mt - p.pad) and pos["stop_log"][-1][0] == "ob_mt_run"
    # the OB found from the bars by the fill hook: body mean / range mean by mt_mode
    p = pk(ob_stop_to_mt_after_run=True)
    pos, tr, sd = mkpos(ctx, 1, 1, 4004.0, 3997.0, levels=(4040.0,), kind="ob", fvg_ce=4002.0)
    me2.on_fill(ctx, sd, pos, tr, dict(ext_i=0), 1, p, 4004.0)
    assert pos["me2"]["ob_mt"] == 4002.0 and pos["me2"]["ob_body"] == 4.0 and pos["me2"]["ob_valid_hi"] == 4004.5
    p = pk(ob_stop_to_mt_after_run=True, mt_mode="range")
    pos, tr, sd = mkpos(ctx, 1, 1, 4004.0, 3997.0, levels=(4040.0,), kind="ob", fvg_ce=4002.0)
    me2.on_fill(ctx, sd, pos, tr, dict(ext_i=0), 1, p, 4004.0)
    assert pos["me2"]["ob_mt"] == 4001.5
