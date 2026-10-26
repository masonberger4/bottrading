"""Caption-gap pass, package management_exits #3/3, part A: the unit tests of the position-loop specs (management_partials_trailing_exits.md 109, 110, 111, 112, 116, 117, 119, 120, 123, 124, 127, 132;
models_setups_entries.md 57; stops_sizing_scaling_in.md 41; times_sessions_macros.md 8, 16, 25; session_day_week_stops_frequency.md 13, 30). Hand-made one-minute bar books with the me3.py hooks
called bar by bar (the position dict and the Side are real, the context is a stub: the harness of test_caption_gap_me1a.py). No platform-specific paths; nothing here needs market data. The close /
re-entry / order specs are in test_caption_gap_me3b.py, the study variants and the no-look-ahead runs in test_caption_gap_me3c.py."""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pytest

from mentorship import manage as MG, me3, paper, sm2, strategy as S
from mentorship.strategy import Params

from test_caption_gap_me1a import flatrows, mkctx, mkpos, pk, reasons


def fill3(ctx, sd, pos, tr, p, state=None, done=None, **data):
    """me3.on_fill for the stub position; `data` = explicit me3 values (the order's o["me3"]), the order flags (scalp, ...) come in `o`."""
    o = dict(ext_i=pos["ext_i"], me3=dict(data))
    o.update(pos.pop("_o", {}))
    me3.on_fill(ctx, sd, pos, tr, o, pos["fill_i"], p, pos["basis"] / pos["n"], state, done)


def step3(ctx, sd, pos, tr, p, i0, i1=None, state=None, done=None, trades=None):
    """me3.manage for bars i0 .. i1 (inclusive); stops when the position is flat."""
    for i in range(i0, (i0 if i1 is None else i1) + 1):
        if not pos["left"]:
            break
        pos["best"] = max(pos["best"], float(sd.h[i]))
        me3.manage(ctx, sd, pos, tr, i, ctx.idx[i], p, state, done, trades if trades is not None else [])


def rung3(ctx, sd, pos, tr, p, k, i, px=None, q=None):
    """Take the ladder rung k on bar i as the ladder loop does (an exit t<k+1>, pos["k"] = k+1, the rung_taken hook)."""
    from mentorship import me1
    lv = me1._lv(pos)
    px = lv[k] if px is None else px
    q = q if q is not None else pos["left"] if k == len(lv) - 1 else max(p.lot, int(pos["n"] * pos["fracs"][k]))
    tr.exits.append((ctx.idx[i], sd.x(px), q, f"t{k + 1}"))
    pos["left"] -= q
    pos["k"] = k + 1
    me3.rung_taken(ctx, sd, pos, tr, k, lv[k], i, p)


# --- new-implied-range-behaviour (109) ------------------------------------------------------------------------------------------------------------

def _ir_book(rows):
    ctx = mkctx(rows)
    p = pk(implied_range=True, time_stop_min=10, time_stop_pts=5.0)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3950.0, levels=(4040.0,), ext=3960.0)
    fill3(ctx, sd, pos, tr, p)
    return ctx, sd, pos, tr, p


def test_implied_range_time_stop_waits_at_50_percent():
    """L 3960 .. T 4040: the 25 % / 75 % lines 3980 / 4020; price sits at 4000 (50 %) for 14 bars with time_stop_min 10 and no 5-pt progress - the time stop does not fire; without the switch it does."""
    rows = [(4000, 4000.5, 3999.5, 4000)] * 16
    ctx, sd, pos, tr, p = _ir_book(rows)
    for i in range(1, 15):
        pos["best"] = max(pos["best"], float(sd.h[i]))
        me3.manage(ctx, sd, pos, tr, i, ctx.idx[i], p, {}, {}, [])
        MG.exits(ctx, sd, pos, tr, i, ctx.idx[i], p, {})
    assert pos["left"] == 10 and not tr.exits and pos.get("ts_off")
    ctx = mkctx(rows)
    q = pk(time_stop_min=10, time_stop_pts=5.0)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3950.0, levels=(4040.0,), ext=3960.0)
    fill3(ctx, sd, pos, tr, q)
    for i in range(1, 15):
        pos["best"] = max(pos["best"], float(sd.h[i]))
        me3.manage(ctx, sd, pos, tr, i, ctx.idx[i], q, {}, {}, [])
        MG.exits(ctx, sd, pos, tr, i, ctx.idx[i], q, {})
    assert reasons(tr) and reasons(tr)[0] in ("time", "time_cut")                          # (the unchanged time stop)


def test_implied_range_top_quarter_raid_halves():
    """Price runs into the top quarter (>= 4020), prints a pivot low 4021 above the 75 % line, then trades under it: half off (ir_top_raid)."""
    rows = [(4000, 4001, 3999, 4000), (4000, 4012, 3999.5, 4011), (4011, 4024, 4022, 4023), (4023, 4024.5, 4021, 4024), (4024, 4027, 4023, 4026), (4026, 4026.5, 4020.5, 4022)]
    ctx, sd, pos, tr, p = _ir_book(rows)
    step3(ctx, sd, pos, tr, p, 1, 4)
    assert not tr.exits and pos["me3"].get("ir_top")
    step3(ctx, sd, pos, tr, p, 5)
    assert reasons(tr) == ["ir_top_raid"] and pos["left"] == 5 and tr.exits[0][1] == pytest.approx(4021.0)
    # a plain pullback that holds the pivot low does nothing
    rows2 = rows[:5] + [(4026, 4026.5, 4021.5, 4022)]
    ctx, sd, pos, tr, p = _ir_book(rows2)
    step3(ctx, sd, pos, tr, p, 1, 5)
    assert not tr.exits


# --- new-rolling-bpr-ceiling (110) ----------------------------------------------------------------------------------------------------------------

def test_rolling_bpr_ceiling_mirrors_the_spec():
    """The spec's short, mirrored to a long: highs 4100 -> 4110 with a retrace low of 4104 between them -> the stop to 4103.75; the next retrace to 4106 and a new high of 4115 -> 4105.75."""
    rows = [(4100, 4100.5, 4099, 4100), (4100, 4100, 4096, 4097), (4097, 4098, 4094, 4096), (4096, 4101, 4095, 4100), (4100, 4110, 4099, 4109), (4109, 4109.5, 4106.5, 4107), (4107, 4108, 4106, 4107.5),
            (4107.5, 4115, 4106.8, 4114), (4114, 4114.5, 4112, 4113)]
    ctx = mkctx(rows)
    p = pk(ladder_trail="rolling_bpr")
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4080.0, levels=(4200.0,))
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 1, 4)
    assert pos["stop"] == pytest.approx(4094 - p.tick)                                                    # the retrace low 4094 between the highs 4100 (the fill bar) and 4110
    assert pos["stop_log"][-1][0] == "bpr_roll" and "bpr_mt" in pos["me3"]
    step3(ctx, sd, pos, tr, p, 5, 7)
    assert pos["stop"] == pytest.approx(4106 - p.tick)                                                    # the next retrace's low 4106 under the new high 4115
    step3(ctx, sd, pos, tr, p, 8)
    assert pos["stop"] == pytest.approx(4106 - p.tick)                                                    # no new high: the stop stays
    # off: the stop does not move
    ctx = mkctx(rows)
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4080.0, levels=(4200.0,))
    fill3(ctx, sd, pos, tr, pk())
    step3(ctx, sd, pos, tr, pk(), 1, 8)
    assert pos["stop"] == 4080.0


# --- new-laggard-slow-delivery (111) --------------------------------------------------------------------------------------------------------------

def test_laggard_time_stop():
    """time_stop_min 10, laggard_mult 2: a laggard trade is still open at minute 15 (its window is 20), a normal one is closed."""
    rows = [(4000, 4000.5, 3999.5, 4000)] * 22
    out = {}
    for name, lag in (("laggard", True), ("normal", False)):
        ctx = mkctx(rows)
        p = pk(time_stop_min=10, time_stop_pts=5.0, laggard_mult=2.0)
        pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4040.0,))
        tr.laggard = False
        fill3(ctx, sd, pos, tr, p, laggard=lag)
        if lag:
            tr.laggard = True
        for i in range(1, 16):
            pos["best"] = max(pos["best"], float(sd.h[i]))
            MG.exits(ctx, sd, pos, tr, i, ctx.idx[i], me3.eff_p(pos, p), {})
        out[name] = pos["left"]
    assert out == {"laggard": 10, "normal": 0}
    assert me3.eff_p({"me3": {"laggard": True}}, pk(time_stop_min=10, laggard_mult=2.0)).time_stop_min == 20


def test_laggard_flag_reads_the_partner_only_up_to_the_fill():
    """The leader (the partner) traded through its previous-day high before the fill bar while this index has not: laggard; a later partner high does not count."""
    import pandas as pd
    rows = [(4000, 4001, 3999, 4000)] * 6
    prow = [(100, 100.5, 99.5, 100), (100, 103, 99.8, 102.9)] + [(102.9, 103, 102.5, 102.8)] * 4
    ctx = mkctx(rows)
    pctx = mkctx(prow)
    pctx.pd = {"pdh1": 102.0, "pdl1": 95.0}
    ctx.pd = {"pdh1": 4010.0, "pdl1": 3990.0}
    ctx.pside = (pctx, {1: pctx.sides_map[1], -1: pctx.sides_map[-1]}, __import__("pandas").Series(np.arange(len(pctx.idx)), index=pctx.idx))
    sd = ctx.sides_map[1]
    p = pk(laggard_mult=2.0)
    assert me3.laggard_flag(ctx, sd, 4, p) is True
    assert me3.laggard_flag(ctx, sd, 1, p) is False                                       # at bar 1 the partner's spike (bar 1) is not closed before the fill
    ctx.pd["pdh1"] = 4000.5                                                              # this index already traded through its own
    assert me3.laggard_flag(ctx, sd, 4, p) is False


# --- new-volume-divergence-exit (112) -------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("vol,halves", [(500.0, True), (1000.0, False)])
def test_vol_div_exit(vol, halves):
    rows = [(4000, 4005, 3999, 4004), (4004, 4010, 4003, 4009), (4009, 4008, 4004, 4005), (4005, 4012, 4004, 4011)]
    ctx = mkctx(rows)
    ctx.v = np.array([300.0, 900.0, 400.0, vol])
    p = pk(vol_div_exit=True, vol_div_ratio=1.0)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 1, 3)
    assert (reasons(tr) == ["vol_div"] and pos["left"] == 5) == halves
    # no volume column: inert
    ctx = mkctx(rows)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 1, 3)
    assert not tr.exits


def test_vol_div_waits_while_the_htf_draw_is_untouched():
    rows = [(4000, 4005, 3999, 4004), (4004, 4010, 4003, 4009), (4009, 4008, 4004, 4005), (4005, 4012, 4004, 4011)]
    ctx = mkctx(rows)
    ctx.v = np.array([300.0, 900.0, 400.0, 500.0])
    p = pk(vol_div_exit=True, no_collapse_htf=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,), draw=4100.0)
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 1, 3)
    assert not tr.exits


# --- D16-am-trade-held-into-pm (116) / D16-big-range-day-runner-past-noon (117) ------------------------------------------------------------------

def _noon_book(extra=()):
    """Bars from 11:55 (t0 715): 5 bars to 12:00, then more."""
    return [(4000, 4001, 3999, 4000)] * 5 + list(extra)


def _am_step(ctx, sd, pos, tr, p, i0, i1, am_x=720):
    """The am_exit block of run_day: skip when am_skip says so, else close at the 12:00 bar."""
    for i in range(i0, i1 + 1):
        if not pos["left"]:
            break
        t, tf = int(ctx.t[i]), ctx.tf
        if t + tf >= am_x and not me3.am_skip(ctx, sd, pos, tr, i, ctx.idx[i], p, am_x):
            tr.exits.append((ctx.idx[i], float(ctx.c[i]), pos["left"], "am_exit")); pos["left"] = 0


def test_day_mode_am_exit_and_the_runner():
    rows = _noon_book([(4000, 4001, 3999, 4000)] * 200)
    # day mode: open at 12:05, flat only by the session flat time
    ctx = mkctx(rows, t0=715)
    p = pk(day_mode_no_am_exit=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,), day_trade=True)
    fill3(ctx, sd, pos, tr, p)
    _am_step(ctx, sd, pos, tr, p, 1, 150)
    assert pos["left"] == 10 and not tr.exits
    # a session-mode long without the switch closes at 12:00
    ctx = mkctx(rows, t0=715)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    fill3(ctx, sd, pos, tr, pk(day_mode_no_am_exit=True))
    _am_step(ctx, sd, pos, tr, pk(day_mode_no_am_exit=True), 1, 20)
    assert reasons(tr) == ["am_exit"]
    # 90 % off at 11:30 with am_runner_hold_to=900: 2 lots stay past 12:00 and close at 15:00; with 50 % off the AM exit closes everything
    p = pk(am_runner_hold_to=900)
    for closed, ok in ((9, True), (5, False)):
        ctx = mkctx(rows, t0=715)
        pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,), n=10)
        fill3(ctx, sd, pos, tr, p)
        tr.exits.append((ctx.idx[0], 4020.0, closed, "t1")); pos["left"] -= closed; pos["t1_done"] = True
        _am_step(ctx, sd, pos, tr, p, 1, 5)
        if ok:
            assert pos["left"] == 1 and pos["me3"]["am_hold"] == "runner"                                      # 1 lot is all that is left (<= 2 lots)
            _am_step(ctx, sd, pos, tr, p, 6, 200)
            assert reasons(tr)[-1] == "am_runner_hold" and ctx.idx[len(tr.exits) and 0].hour == 11 and tr.exits[-1][0].hour * 60 + tr.exits[-1][0].minute == 899
        else:
            assert reasons(tr)[-1] == "am_exit" and pos["left"] == 0
    # 2 lots kept out of 4 left (97.5 % is not needed: the 85 % rule): n=40, 36 closed -> 4 left -> 2 kept
    ctx = mkctx(rows, t0=715)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,), n=40)
    fill3(ctx, sd, pos, tr, p)
    tr.exits.append((ctx.idx[0], 4020.0, 36, "t1")); pos["left"] -= 36; pos["t1_done"] = True
    _am_step(ctx, sd, pos, tr, p, 1, 5)
    assert pos["left"] == 2 and "am_exit" in reasons(tr)


def test_noon_guard_exempts_a_day_mode_order():
    assert me3.noon_exempt({"day_trade": True}, pk(day_mode_no_am_exit=True)) is True
    assert me3.noon_exempt({"day_trade": True}, pk(day_mode_no_am_exit=False)) is False
    assert me3.noon_exempt({}, pk(day_mode_no_am_exit=True)) is False


def test_explosive_runner(monkeypatch):
    """ADR5 = 40: a 45-pt range by 10:00 and a new high at 11:55 -> the runner is open at 12:01 and closed at 15:00; on a 25-pt day it is closed at 12:00."""
    n = 600
    wide = [(4000, 4001, 3999, 4000)] * n
    def ctx_for(rng):
        rows = list(wide)
        rows[0] = (4000, 4000 + rng, 4000, 4000 + rng - 1)                        # the 09:30 bar sets the range
        rows[145] = (4000, 4000 + rng + 3, 4000, 4000 + rng + 2)                 # a new high at 11:55 (bar 145 from 09:30)
        return mkctx(rows)
    for rng, expl in ((45.0, True), (25.0, False)):
        ctx = ctx_for(rng)
        ctx.hist = [SimpleNamespace()] * 5
        monkeypatch.setattr(S, "adr5", lambda days: 40.0)
        p = pk(explosive_runner=True)
        pos, tr, sd = mkpos(ctx, 1, 100, 4000.0, 3990.0, levels=(4200.0,))
        fill3(ctx, sd, pos, tr, p)
        for i in range(146, 160):
            if not pos["left"]:
                break
            t, tf = int(ctx.t[i]), ctx.tf
            if t + tf >= 720 and not me3.am_skip(ctx, sd, pos, tr, i, ctx.idx[i], p, 720):
                tr.exits.append((ctx.idx[i], float(ctx.c[i]), pos["left"], "am_exit")); pos["left"] = 0
        assert (pos["left"] == 10) == expl
        if expl:
            for i in range(160, 400):
                if not pos["left"]:
                    break
                t, tf = int(ctx.t[i]), ctx.tf
                if t + tf >= 720 and not me3.am_skip(ctx, sd, pos, tr, i, ctx.idx[i], p, 720):
                    tr.exits.append((ctx.idx[i], float(ctx.c[i]), pos["left"], "am_exit")); pos["left"] = 0
            assert reasons(tr) == ["explosive_exit"] and tr.exits[0][0].hour * 60 + tr.exits[0][0].minute == 899
        else:
            assert reasons(tr) == ["am_exit"]


# --- X11-last-hour-target-hit-done (119) ---------------------------------------------------------------------------------------------------------

def test_last_hour_target_done():
    """3 rungs: rung 1 hit at 14:40 closes its fraction only; rung 2 hit at 15:05 closes everything (the ladder loop's lh_all)."""
    p = pk(last_hour_target_done=True)
    assert me3.lh_all({}, 14 * 60 + 40, p) is False and me3.lh_all({}, 15 * 60 + 5, p) is True
    assert me3.lh_all({}, 15 * 60 + 5, pk()) is False
    import inspect
    src = inspect.getsource(S._run_day_once)
    assert "_ME3.lh_all(pos, t, p)" in src and '"lh_target" if lh3_' in src


# --- X11-two-stage-pm-delivery (120) -------------------------------------------------------------------------------------------------------------

def test_pm_two_stage(monkeypatch):
    """A PM long on a two-session day stalls and retraces without touching its entry array: the time stop (20 min) is suspended until 15:00 while the far rung is unhit; from 15:00 it applies."""
    from mentorship import setups
    monkeypatch.setattr(setups, "cc_profile", lambda ctx, i, p: ("two_session_up", 1))
    rows = [(4000, 4001, 3999, 4000)] * 120
    ctx = mkctx(rows, t0=14 * 60 + 0)                                                      # bars from 14:00
    p = pk(pm_two_stage=True, time_stop_min=20, time_stop_pts=5.0)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3985.0, levels=(4010.0, 4060.0), fracs=(0.5, 0.5), kinds=["pool", "array"], fvg_bottom=3995.0)
    tr.session = "PM"
    fill3(ctx, sd, pos, tr, p)
    assert pos["me3"]["two_stage"]
    for i in range(1, 50):
        pos["best"] = max(pos["best"], float(sd.h[i]))
        me3.manage(ctx, sd, pos, tr, i, ctx.idx[i], p, {}, {}, [])
        MG.exits(ctx, sd, pos, tr, i, ctx.idx[i], p, {})
    assert pos["left"] == 10 and not tr.exits                                              # open at 14:50 (49 bars)
    for i in range(50, 70):
        pos["best"] = max(pos["best"], float(sd.h[i]))
        me3.manage(ctx, sd, pos, tr, i, ctx.idx[i], p, {}, {}, [])
        MG.exits(ctx, sd, pos, tr, i, ctx.idx[i], p, {})
    assert tr.exits and reasons(tr)[0] in ("time", "time_cut")                              # from 15:00 the normal rules
    # a close under the entry array's far edge ends the suspension
    ctx = mkctx([(4000, 4001, 3999, 4000)] * 5 + [(3996, 3996.5, 3993, 3994)] * 40, t0=14 * 60)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3985.0, levels=(4010.0, 4060.0), fracs=(0.5, 0.5), kinds=["pool", "array"], fvg_bottom=3995.0)
    tr.session = "PM"
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 1, 20)
    assert not pos.get("ts_off")


# --- X10-cc-day-trade-exit-1400 (123) -------------------------------------------------------------------------------------------------------------

def test_cc_day_exit():
    rows = [(4000, 4001, 3999, 4000)] * 30
    ctx = mkctx(rows, t0=13 * 60 + 40)                                                      # bars from 13:40; bar 19 is 13:59 (closes at 14:00)
    p = pk(cc_day_exit=840)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    tr.entry_kind = "ts_cc_limit"
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 1, 18)
    assert pos["left"] == 10
    step3(ctx, sd, pos, tr, p, 19)
    assert reasons(tr) == ["cc_1400"] and tr.exits[0][0].hour * 60 + tr.exits[0][0].minute == 13 * 60 + 59
    # a 2023-model PM trade is unaffected
    ctx = mkctx(rows, t0=13 * 60 + 40)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    tr.entry_kind = "fvg"
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 1, 29)
    assert pos["left"] == 10
    assert me3.is_cc(SimpleNamespace(entry_kind="fvg", setup="pm", swept="pdl", lv_tags="x|cc_common")) is False        # an entry-location tag, not the model
    assert me3.is_cc(SimpleNamespace(entry_kind="x", setup="pm", swept="", lv_tags="a|cc_limit")) is True


# --- X10-london-time-of-day-scaleouts (124) -------------------------------------------------------------------------------------------------------

def test_london_tod():
    """A London long filled at 03:10 is reduced at 04:55, at 06:55 and on a 10:20 new high (each once, 25 % of the units left)."""
    n = 440
    rows = [(4000, 4001, 3999, 4000)] * n
    rows[430] = (4000, 4005, 3999.5, 4004)                                                  # a new extreme at 10:20 (bar 430 from 03:10)
    ctx = mkctx(rows, t0=3 * 60 + 10)
    p = pk(london_tod_partials=True, london_tod_frac=0.25)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,), n=16)
    tr.session = "LON"
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 1, 439)
    assert reasons(tr) == ["lon_0500", "lon_0700", "lon_1000"]
    assert [e[0].hour * 60 + e[0].minute for e in tr.exits] == [295, 415, 10 * 60 + 20]
    assert [e[2] for e in tr.exits] == [4, 3, 2]                                            # 25 % of 16, 25 % of 12 (3), 25 % of 9 (2)
    # a fill after 04:55 skips the first partial
    ctx = mkctx(rows, t0=5 * 60 + 10)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,), n=16)
    tr.session = "LON"
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 1, 150)
    assert "lon_0500" not in reasons(tr) and "lon_0700" in reasons(tr)


# --- new-scalp-fixed-1to1-2h (127) ---------------------------------------------------------------------------------------------------------------

def test_scalp_mode():
    """A scalp long with risk 3 has a single rung at avg + 3 (kind fixed), no adds, no trail, and closes at fill + 120 min when neither the target nor the stop hits."""
    rows = [(4000, 4000.5, 3999.5, 4000)] * 130
    ctx = mkctx(rows)
    p = pk(scalp_mode="fixed_1to1", scalp_max_min=120)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3997.0, levels=(4005.0,), n=10)
    pos["_o"] = {"scalp": True}
    fill3(ctx, sd, pos, tr, p)
    assert pos["levels"] == [4003.0] and pos["level_kinds"] == ["fixed"] and pos["fracs"] == (1.0,) and pos["no_adds"] and pos["no_trail"] and pos["trade_mode"] == "scalp"
    assert pos["exit_at"] == pos["fill_t"] + 120                                            # the ladder loop's time_exit closes at the bar that ends fill + 120 min
    # a non-scalp order is untouched
    ctx = mkctx(rows)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3997.0, levels=(4005.0,), n=10)
    fill3(ctx, sd, pos, tr, p)
    assert pos["levels"] == [4005.0] and "trade_mode" not in pos


# --- T13-reclaim-0930-open-expansion (57) --------------------------------------------------------------------------------------------------------

def test_open_reclaim_keeps_runner():
    """The session low formed under the 09:30 open (the Judas), then a close over it: the day is expanding - the ladder's last fraction is a runner and the breakeven waits for the next rung."""
    rows = [(4000, 4001, 3995, 3997), (3997, 3999, 3994, 3998), (3998, 4003, 3997, 4002), (4002, 4010, 4001, 4009), (4009, 4020, 4008, 4019)]
    ctx = mkctx(rows)
    p = pk(open_reclaim_runner=True, be_on="t1")
    pos, tr, sd = mkpos(ctx, 1, 1, 3998.0, 3990.0, levels=(4010.0, 4030.0, 4060.0), fracs=(0.4, 0.3, 0.3))
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 2, 3)
    assert pos["me3"].get("expanding") and pos["runner"] is True and len(pos["levels"]) == 2           # the third fraction has no target
    rung3(ctx, sd, pos, tr, p, 0, 3)
    assert pos["t1_done"] and pos["stop"] == 3990.0 and pos["me3"]["be_wait"]                         # the first partial made, the breakeven waits
    rung3(ctx, sd, pos, tr, p, 1, 4, q=3)
    assert pos["stop"] > 3990.0                                                                      # ... for the next rung
    # not expanding: the ladder is untouched
    ctx = mkctx([(4000, 4001, 3995, 3997), (3997, 3999, 3994, 3998), (3998, 3999, 3996, 3997)])
    pos, tr, sd = mkpos(ctx, 1, 1, 3998.0, 3990.0, levels=(4010.0, 4030.0, 4060.0), fracs=(0.4, 0.3, 0.3))
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 2)
    assert not pos["runner"] and len(pos["levels"]) == 3


# --- T10-1550-pool-timing (8) --------------------------------------------------------------------------------------------------------------------

def _lh_pos(t0):
    ctx = mkctx([(4000, 4001, 3999, 4000)] * 30, t0=t0)
    p = pk(lh_pool_timing=True, lh_keep_frac=0.1, lh_late_ext_pts=3.0)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4010.0,), fracs=(1.0,), kinds=["pool"], n=20)
    tr.setup, tr.session = "pm_last_hour", "PM"
    fill3(ctx, sd, pos, tr, p)
    return ctx, sd, pos, tr, p


def test_lh_pool_timing():
    # a pool hit at 15:46: 90 % exits, the runner's stop at breakeven
    ctx, sd, pos, tr, p = _lh_pos(15 * 60 + 40)
    assert me3.rung_pre(ctx, sd, pos, tr, 0, [4010.0], 6, p, int(ctx.t[6])) is None
    q = pos["left"]
    rung3(ctx, sd, pos, tr, p, 0, 6, q=10)                                                           # the rung's own fraction first
    assert pos["left"] == 2 and "lh_early" in reasons(tr) and pos["stop"] >= 4000.0
    # a pool hit at 15:52: the runner is held to the extension (3 pts beyond the pool)
    ctx, sd, pos, tr, p = _lh_pos(15 * 60 + 45)
    r = me3.rung_pre(ctx, sd, pos, tr, 0, [4010.0], 7, p, int(ctx.t[7]))
    assert r == "reload" and pos["levels"] == [4010.0, 4013.0] and pos["fracs"] == pytest.approx((0.9, 0.1)) and pos["level_kinds"][-1] == "lh_ext"
    # not a last-hour trade / switch off: nothing
    ctx, sd, pos, tr, p = _lh_pos(15 * 60 + 45)
    tr.setup = "pm"
    assert me3.rung_pre(ctx, sd, pos, tr, 0, [4010.0], 7, p, int(ctx.t[7])) is None


# --- T8-lunch-trending-days (16) -----------------------------------------------------------------------------------------------------------------

def test_am_exit_trend_hold(monkeypatch):
    """A trend-day long open at 11:59 is still open at 12:30 with the switch; without it the 12:00 am_exit closes it."""
    from mentorship import sm4
    monkeypatch.setattr(sm4, "trend_day", lambda ctx, sd, i, p: True)
    rows = [(4000, 4001, 3999, 4000)] * 60
    for sw_on in (True, False):
        ctx = mkctx(rows, t0=11 * 60 + 55)
        ctx.lock = {}
        p = pk(am_exit_trend_hold=sw_on, day_mode_no_am_exit=False)
        pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
        fill3(ctx, sd, pos, tr, p)
        if sw_on:
            _am_step(ctx, sd, pos, tr, p, 1, 40)
            assert pos["left"] == 10 and not tr.exits
        else:
            assert me3.am_on(p) is False                                                       # the engine never calls am_skip: the plain am_exit closes
    monkeypatch.setattr(sm4, "trend_day", lambda ctx, sd, i, p: False)
    ctx = mkctx(rows, t0=11 * 60 + 55)
    ctx.lock = {}
    p = pk(am_exit_trend_hold=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    fill3(ctx, sd, pos, tr, p)
    _am_step(ctx, sd, pos, tr, p, 1, 10)
    assert reasons(tr) == ["am_exit"]


# --- new-hold-pre0930-through-open (25) ----------------------------------------------------------------------------------------------------------

def _pre_book(drift):
    """A PRE9 long filled at 09:00; its range 3990 .. 4010; the last 20 minutes either drift into the lower third (3991-3993 closes) or hold the upper part."""
    rows = [(4000, 4010, 3990, 4005)] + [(4005, 4006, 4004, 4005)] * 35
    px = 3992.0 if drift else 4006.0
    for k in range(10, 31):
        rows[k] = (px, px + 0.5, px - 0.5, px)
    return mkctx(rows, t0=9 * 60)


@pytest.mark.parametrize("drift,funded,closed", [(True, False, True), (True, True, False), (False, False, False)])
def test_pre_hold_open(drift, funded, closed):
    ctx = _pre_book(drift)
    p = pk(pre_hold_open=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4003.0, 3980.0, levels=(4100.0, 4200.0), fracs=(0.5, 0.5), kinds=["pool", "pool"])
    tr.session = "PRE9"
    fill3(ctx, sd, pos, tr, p)
    if funded:
        tr.exits.append((ctx.idx[0], 4010.0, 5, "t1")); pos["left"] -= 5; pos["t1_done"] = True
    step3(ctx, sd, pos, tr, p, 1, 34)
    assert (reasons(tr)[-1:] == ["pre_open_unfunded"]) == closed
    if drift:
        assert "risk_0930_sweep" in tr.mgmt_tags
    if closed:
        assert tr.exits[-1][0].hour * 60 + tr.exits[-1][0].minute == 569


# --- X7-three-failures-flatten-open-trade (13) ---------------------------------------------------------------------------------------------------

def _loss(session, hour, minute, side="long"):
    ts = __import__("pandas").Timestamp(f"2026-06-23 {hour:02d}:{minute:02d}", tz="America/New_York")
    t = SimpleNamespace(session=session, exits=[(ts, 3990.0, 10, "stop")], entry=4000.0, shares=10, adds=[], side=side)
    t.pnl = lambda cps=0.0: (-100.0, 0.0)
    return t


def test_three_fails_flatten():
    """Two failed AM trades, then an open long whose array fails (a close under its far edge) = the third: closed at that close, the AM and its SB key done, the PM window 13:45-14:30."""
    ctx = mkctx([(4000, 4001, 3999, 4000), (4000, 4000.5, 3993, 3994)])
    p = pk(session_fail_flatten=True, session_stop_after_fails=3, pd3_pm_window=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3985.0, levels=(4100.0,), fvg_bottom=3996.0)
    fill3(ctx, sd, pos, tr, p)
    state, done = {}, {"AM": False, "PM": False, "SB_AM": False, "PRE7": False}
    step3(ctx, sd, pos, tr, p, 1, state=state, done=done, trades=[_loss("AM", 9, 31), _loss("AM", 9, 45)])
    assert reasons(tr) == ["pd3_session"] and done["AM"] and done["SB_AM"] and done["PRE7"] and not done["PM"]
    assert state["stops"]["AM"] == "pd3_session" and state["pm_window"] == (825, 870)
    assert MG.blocked_now(state, "AM") and not MG.blocked_now(state, "PM")
    # only one prior fail: nothing
    ctx = mkctx([(4000, 4001, 3999, 4000), (4000, 4000.5, 3993, 3994)])
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3985.0, levels=(4100.0,), fvg_bottom=3996.0)
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 1, state={}, done={"AM": False}, trades=[_loss("AM", 9, 31)])
    assert not tr.exits
    # the PM window blocks a 14:45 PM order (the order stage reads ctx.state7)
    ctx = mkctx([(4000, 4001, 3999, 4000)] * 3, t0=14 * 60 + 45)
    ctx.state7 = {"pm_window": (825, 870)}
    tags = {}
    assert me3.order_block(ctx, ctx.sides_map[1], {"broke": 1}, 1, p, "PM", 4000.0, tags) == "x_pd3_pm_window"
    ctx = mkctx([(4000, 4001, 3999, 4000)] * 3, t0=13 * 60 + 50)
    ctx.state7 = {"pm_window": (825, 870)}
    assert me3.order_block(ctx, ctx.sides_map[1], {"broke": 1}, 1, p, "PM", 4000.0, tags) is None


# --- new-late-week-close-flat (30) ----------------------------------------------------------------------------------------------------------------

def _recov(day, rows, week_net, p, t0=570):
    ctx = mkctx(rows, t0=t0, d=day)
    ctx.week = {"net": week_net}
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,), n=5)
    pos["reentry"] = True
    fill3(ctx, sd, pos, tr, p, state={"reentered": {"AM": True}}, done={"AM": False})
    return ctx, sd, pos, tr


def test_late_week_close_flat():
    """Thursday: a 1R loss (-50 on the week), then a half-size re-entry reaching +2R open (the week back at 0) -> closed there, everything done; Tuesday morning: not closed, the stop trails to the break-even-week price."""
    thu, tue = date(2026, 6, 25), date(2026, 6, 23)
    rows = [(4000, 4001, 3999, 4000), (4000, 4012, 3999.5, 4011)]                           # +11 pts x 5 units = +55 on the week of -50
    p = pk(late_week_flat=True, recover_trail=True, cost_per_share=0.0)
    ctx, sd, pos, tr = _recov(thu, rows, -50.0, p)
    done, state = {"AM": False, "PM": False}, {}
    step3(ctx, sd, pos, tr, p, 1, state=state, done=done, trades=[])
    assert reasons(tr) == ["flat_week"] and all(done.values()) and state["day_done"]
    ctx, sd, pos, tr = _recov(tue, rows, -50.0, p)
    done, state = {"AM": False, "PM": False}, {}
    step3(ctx, sd, pos, tr, p, 1, state=state, done=done, trades=[])
    assert not tr.exits and not any(done.values())
    assert pos["stop_log"][-1][0] == "week_trail" and pos["stop"] == pytest.approx(4010.0)        # 4011 - 5/5: the price where the week's P&L is 0 (the clamp keeps it under the close)
    # late in the session on a Tuesday (t >= late_flat_t) closes too
    ctx, sd, pos, tr = _recov(tue, [(4000, 4001, 3999, 4000), (4000, 4012, 3999.5, 4011)], -50.0, p, t0=15 * 60)
    done, state = {"AM": False, "PM": False}, {}
    step3(ctx, sd, pos, tr, p, 1, state=state, done=done, trades=[])
    assert reasons(tr) == ["flat_week"]
    # not a re-entry: nothing
    ctx = mkctx(rows, d=thu)
    ctx.week = {"net": -50.0}
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,), n=5)
    fill3(ctx, sd, pos, tr, p, state={"reentered": {}}, done={"AM": False})
    step3(ctx, sd, pos, tr, p, 1, state={}, done={"AM": False}, trades=[])
    assert not tr.exits
    assert S.Params(late_week_flat=True).dw_needs_week


# --- new-drawdown-recovery-exit (132) -------------------------------------------------------------------------------------------------------------

def test_recovery_exit():
    """A $1,000 loss, then a re-entry at half risk ($500 = 1R, 100 units, a 5-pt stop): "new" closes at +$1,000 open profit and ends the session; "experienced" locks +2R - tick and works one rung at +3R."""
    rows = [(4000, 4001, 3999, 4000), (4000, 4008.5, 3999.5, 4008), (4008, 4012, 4007, 4011), (4011, 4011.5, 4009, 4010)]
    p = pk(recovery_exit="new", cost_per_share=0.0)
    ctx = mkctx(rows)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3995.0, levels=(4100.0,), n=100, reentry=True)
    done = {"AM": False}
    fill3(ctx, sd, pos, tr, p, state={"reentered": {"AM": True}, "unrecovered": {"AM": 1000.0}}, done=done)
    assert pos["me3"]["recover"] == 1000.0
    step3(ctx, sd, pos, tr, p, 1, state={}, done=done, trades=[])
    assert not tr.exits                                                                      # +800 at the close 4008
    step3(ctx, sd, pos, tr, p, 2, state={}, done=done, trades=[])
    assert reasons(tr) == ["recovered"] and done["AM"] and pos["left"] == 0                  # +1100
    # without a loss to recover (not a re-entry): nothing
    ctx = mkctx(rows)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3995.0, levels=(4100.0,), n=100)
    fill3(ctx, sd, pos, tr, p, state={"reentered": {}}, done={"AM": False})
    step3(ctx, sd, pos, tr, p, 1, 3, state={}, done={"AM": False}, trades=[])
    assert not tr.exits
    # experienced: a single rung at +3R, the stop to +2R - tick at +2R
    q = pk(recovery_exit="experienced", cost_per_share=0.0)
    ctx = mkctx(rows)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3995.0, levels=(4100.0,), n=100, reentry=True)
    fill3(ctx, sd, pos, tr, q, state={"reentered": {"AM": True}, "unrecovered": {"AM": 1000.0}}, done={"AM": False})
    assert pos["levels"] == [4015.0] and pos["fracs"] == (1.0,)
    step3(ctx, sd, pos, tr, q, 1, 2, state={}, done={"AM": False}, trades=[])
    assert pos["stop"] == pytest.approx(4009.75) and pos["stop_log"][-1][0] == "recovery_lock"       # 4010 - 1 tick (clamped under the 4011 close: not needed)


# --- E7-reduce-size (41) -------------------------------------------------------------------------------------------------------------------------

def test_abort_half():
    """Long 10, X6 rule mode, abort_mode "half": a 5m candle closing below the entry FVG exits 5 at its close (stop unchanged, no adds); the second one exits the rest."""
    rows = [(4000, 4001, 3999, 4000)] * 3 + [(3997, 3997.5, 3995, 3996)] + [(3996, 3996.5, 3994, 3995)] + [(3995, 3995.5, 3993, 3994)]
    p = pk(fvg_abort=True, abort_mode="half", abort_frac=0.5, fvg_abort_tf=1)
    ctx = mkctx(rows)
    pos, tr, sd = mkpos(ctx, 1, 1, 4000.0, 3985.0, levels=(4100.0,), fvg_bottom=3998.0)
    out = []
    for i in (3, 4):
        out.append(MG._abort(ctx, sd, pos, tr, i, ctx.idx[i], p))
    assert reasons(tr) == ["abort_half", "abort"] and [e[2] for e in tr.exits] == [5, 5] and out == [False, True]
    assert pos["stop"] == 3985.0 and pos["no_adds"]
    # full mode (the default) keeps the confirmation rule: nothing at the first close
    ctx = mkctx(rows)
    pos, tr, sd = mkpos(ctx, 1, 1, 4000.0, 3985.0, levels=(4100.0,), fvg_bottom=3998.0)
    MG._abort(ctx, sd, pos, tr, 3, ctx.idx[3], pk(fvg_abort=True, fvg_abort_tf=1))
    assert not tr.exits


# --- new-no-working-stop-close-exit (131) --------------------------------------------------------------------------------------------------------

def test_unprotected_exit():
    """paper-broker mock: no stop acknowledgement within stop_ack_sec marks the position unprotected - the ladder is ONE 100 % rung at rung 1; an adverse close (> 1 tick against the entry) exits at market."""
    import pandas as pd
    p = pk(stop_ack_sec=10)
    t0 = pd.Timestamp("2026-06-23 09:45:00", tz="America/New_York")
    w = paper.StopAckWatch(p, "long", 4000.0, [4005.0, 4020.0], [0.5, 0.5], t0)
    assert w.ladder() == ([4005.0, 4020.0], [0.5, 0.5]) and not w.tick(t0 + pd.Timedelta(seconds=5), False)
    assert w.tick(t0 + pd.Timedelta(seconds=10), False) is True
    assert w.ladder() == ([4005.0], [1.0])
    assert w.adverse_close(3999.0) and not w.adverse_close(3999.9) and not w.adverse_close(4001.0)
    w2 = paper.StopAckWatch(p, "short", 4000.0, [3995.0], [1.0], t0)                          # an acknowledged stop: never unprotected
    assert not w2.tick(t0 + pd.Timedelta(seconds=60), True) and not w2.adverse_close(4010.0)
    w3 = paper.StopAckWatch(pk(stop_ack_sec=0), "long", 4000.0, [4005.0], [1.0], t0)          # off
    assert not w3.tick(t0 + pd.Timedelta(seconds=600), False)
    w4 = paper.StopAckWatch(p, "short", 4000.0, [3995.0, 3980.0], [0.5, 0.5], t0)
    w4.tick(t0 + pd.Timedelta(seconds=11), False)
    assert w4.adverse_close(4000.5) and w4.ladder() == ([3995.0], [1.0])
