"""Caption-gap pass, package management_exits #3/3, part B: the unit tests of the close / re-entry / order-stage specs (management_partials_trailing_exits.md 130; models_setups_entries.md 65, 118, 128,
199; session_day_week_stops_frequency.md 1, 5, 9, 10, 15, 16, 17; stops_sizing_scaling_in.md 42) - the me3.py hooks called with hand-made positions, trades and states (the position dict and the Side are
real, the context is a stub: the harness of test_caption_gap_me1a.py) - plus scenario-C runs through run_day for the hooks of the engine's own loop (the flip order, the OTE turtle soup, the cc_ob
re-entry, the count, the AM idea failure). No platform-specific paths; nothing here needs market data."""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import manage as MG, me3, sm2, strategy as S
from mentorship.strategy import Params

from test_caption_gap_me1a import flatrows, mkctx, mkpos, pk, reasons
from test_caption_gap_me3a import fill3

NY = "America/New_York"


def mk_closed(ctx, sign=1, exits=(), entry=4000.0, **kw):
    """A closed position: a stub trade with the given exits [(hhmm minutes, price, qty, reason)] (real prices) and the side-space position dict."""
    pos, tr, sd = mkpos(ctx, sign, 0, entry, entry - 10.0, levels=(entry + 100.0,), **kw)
    tr.ext_px = None
    for m, px, q, why in exits:
        tr.exits.append((pd.Timestamp(f"{ctx.day} {m // 60:02d}:{m % 60:02d}", tz=NY), px, q, why))
    pos["left"] = 0
    tr.entry_kind, tr.setup = kw.get("entry_kind", "fvg"), "am_mm"
    return pos, tr, sd


# --- new-no-close-to-reenter (130) ---------------------------------------------------------------------------------------------------------------

def test_abort_blocks_side():
    """A long closed by an abort-set exit blocks a long setup 3 bars later on the same leg (no new MSS); a long stopped out is not blocked; a short after the abort is allowed; a new MSS after the close lifts it."""
    ctx = mkctx(flatrows(20))
    p = pk(abort_blocks_side=True, reentry_half=True)
    state = {"reentered": {}}
    pos, tr, sd = mk_closed(ctx, exits=[(572, 3995.0, 10, "abort")])
    assert me3.pre_close(pos, tr, state, p, 10) is True and state["blocked_side"]["AM"] == dict(side="long", i=10) and "abort_blocks_side" in tr.mgmt_tags
    ctx.state7 = state
    long_sd, short_sd = ctx.sides_map[1], ctx.sides_map[-1]
    assert me3.order_block(ctx, long_sd, {"broke": 8}, 13, p, "AM", 4000.0, {}) == "x_abort_blocks_side"           # the same leg: the MSS came before the close
    assert me3.order_block(ctx, long_sd, {"broke": None}, 13, p, "AM", 4000.0, {}) == "x_abort_blocks_side"
    assert me3.order_block(ctx, short_sd, {"broke": 8}, 13, p, "AM", 4000.0, {}) is None                            # the other direction is free
    assert me3.order_block(ctx, long_sd, {"broke": 12}, 13, p, "AM", 4000.0, {}) is None                            # a new structure shift after the close
    # a stop-out is no abort: nothing is blocked (the X13b half-risk re-entry stays available)
    state2 = {"reentered": {}}
    pos, tr, sd = mk_closed(ctx, exits=[(572, 3990.0, 10, "stop")])
    assert me3.pre_close(pos, tr, state2, p, 10) is False and "blocked_side" not in state2
    # every listed reason and the pd3* family
    for why in ("abort", "ce_close", "breaker_mt", "pd3", "pd3_close", "chop_close", "htf_stall", "time", "slow_ref", "lost_hi", "hh_low", "stall_reh"):
        st = {}
        pos, tr, sd = mk_closed(ctx, exits=[(572, 3995.0, 10, why)])
        assert me3.pre_close(pos, tr, st, p, 10) is True, why
    # off: inert
    st = {}
    pos, tr, sd = mk_closed(ctx, exits=[(572, 3995.0, 10, "abort")])
    assert me3.pre_close(pos, tr, st, pk(), 10) is False and not st


# --- D18-reentry-count-max-2 (5) -----------------------------------------------------------------------------------------------------------------

def test_reentry_count():
    """reentry_count_max 1 keeps the old flag; 2 counts the attempts (the third try is armed after the second stop), the risk of attempt n is 0.5 ** n."""
    one = pk(reentry_half=True)
    st = {"reentered": {}}
    me3.count_reentry(st, "AM", one)
    assert st["reentered"]["AM"] is True and me3.more_reentries(st, "AM", one) is False
    two = pk(reentry_half=True, reentry_count_max=2, reentry_risk="budget")
    st = {"reentered": {}}
    assert me3.more_reentries(st, "AM", two) is False
    me3.count_reentry(st, "AM", two)
    assert st["reentered"]["AM"] == 1 and me3.more_reentries(st, "AM", two) is True
    assert me3.risk_count(st, "AM", two, 0.5) == pytest.approx(0.5)
    me3.count_reentry(st, "AM", two)
    assert st["reentered"]["AM"] == 2 and me3.more_reentries(st, "AM", two) is False
    assert me3.risk_count(st, "AM", two, 0.5) == pytest.approx(0.25)
    assert me3.risk_count({"reentered": {"AM": True}}, "AM", one, 0.5) == 0.5                      # the old flag: the engine's own 0.5
    # with the losing trade's own risk (reentry_risk "loss") each attempt already halves the previous: the multiplier is left to the engine
    assert me3.risk_count(st, "AM", pk(reentry_count_max=2, reentry_risk="loss"), 0.25) == 0.25


def test_reentry_count_through_the_engine():
    """The engine: two consecutive stops with reentry_count_max 2 re-open the session twice (state['reentered'] counts 1 then 2) - _risk_mult gives 0.5 then 0.25."""
    p = Params(reentry_half=True, reentry_count_max=2, reentry_risk="budget")
    st = {"reentered": {"AM": 1}, "re_ctx": {}, "re7": {}, "day_loss": False}
    assert S._risk_mult(st, "AM", p) == pytest.approx(0.5)
    st["reentered"]["AM"] = 2
    assert S._risk_mult(st, "AM", p) == pytest.approx(0.25)
    assert S._risk_mult({"reentered": {}, "re_ctx": {}, "re7": {}, "day_loss": False}, "AM", p) == 1.0
    assert Params().reentry_count_max == 1 and Params().reentry_ob_stop == "mt" and Params().reentry_max == 2         # the turtle-soup cap keeps its name and default


# --- N3-021-citation-misread (9) -----------------------------------------------------------------------------------------------------------------

def test_runner_stop_no_reentry():
    """80 % closed at partials and the rest stopped = a runner stop (no win / trail-win re-entry, tag runner_stop); with 30 % closed the re-entry path stays open."""
    ctx = mkctx(flatrows(10))
    p = pk(runner_stop_no_reentry=True, reentry_after_trail_win=True, trail=True)
    st = {"reentered": {}}
    pos, tr, sd = mk_closed(ctx, exits=[(575, 4020.0, 8, "t1"), (580, 4010.0, 2, "stop")])
    assert me3.pre_close(pos, tr, st, p, 10) is True and pos["runner_stop"] and st["no_win_reentry"] and "runner_stop" in tr.mgmt_tags
    st = {"reentered": {}}
    pos, tr, sd = mk_closed(ctx, exits=[(575, 4020.0, 3, "t1"), (580, 4010.0, 7, "stop")])
    assert me3.pre_close(pos, tr, st, p, 10) is False and "no_win_reentry" not in st
    # the final rung ends the session and its Silver Bullet key
    done = {"AM": False, "SB_AM": False, "PM": False}
    pos, tr, sd = mk_closed(ctx, exits=[(575, 4020.0, 5, "t1"), (580, 4100.0, 5, "t2")])
    tr.final_hit = True
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": 0.0}, p, 10, None, 100.0, False)
    assert done == {"AM": True, "SB_AM": True, "PM": False}
    # the sm7 win re-entries read the flag (source guard)
    import inspect
    from mentorship import sm7
    assert 'state.get("no_win_reentry")' in inspect.getsource(sm7.after_close)


# --- X14-new-trader-stop-when-day-positive (15) ---------------------------------------------------------------------------------------------------

def _closed_trade(ctx, net, session="AM", mins=(575, 580)):
    pos, tr, sd = mk_closed(ctx, exits=[(mins[1], 4010.0 if net > 0 else 3990.0, 10, "t1" if net > 0 else "stop")])
    tr.session = session
    return pos, tr, sd


def test_trader_mode_day_positive():
    """"new": an AM +0.5R closes -> the whole day is done (SB_PM included); an AM loss -> no PM either (recovery is experienced-only); "experienced" + draw_open: an AM win with the draw untouched keeps the PM, the draw hit ends it."""
    ctx = mkctx(flatrows(30))
    p = pk(trader_mode="new", new_day_stops=True)
    keys = lambda: {"AM": False, "PM": False, "SB_AM": False, "SB_PM": False, "PRE9": False}
    done = keys()
    pos, tr, sd = _closed_trade(ctx, 50.0)
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": 50.0}, p, 10, None, 50.0, False)
    assert all(done.values())
    done = keys()
    pos, tr, sd = _closed_trade(ctx, -50.0)
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": -50.0}, p, 10, "long", -50.0, False)
    assert done["PM"] and done["SB_PM"] is False and not done["AM"]                                # (the AM family's own flags are the session stops' business; the PM is the AM-or-PM rule)
    # pm_recover_loss cannot lift it in "new"
    done = keys()
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": -50.0}, pk(trader_mode="new", new_day_stops=True, pm_recover_loss=True), 10, "long", -50.0, False)
    assert done["PM"]
    # the switch off: trader_mode "new" keeps its old meaning
    done = keys()
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": 50.0}, pk(trader_mode="new"), 10, None, 50.0, False)
    assert not any(done.values())
    # experienced + draw_open
    q = pk(pm_after_am_win="draw_open")
    ctx = mkctx([(4000, 4005, 3999, 4004)] * 12)
    pos, tr, sd = _closed_trade(ctx, 50.0)
    pos["draw"] = 4050.0
    done = {"AM": False, "PM": True}                                                              # (no_pm_after_am_win had closed the PM)
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": 50.0}, q, 10, None, 50.0, False)
    assert done["PM"] is False                                                                    # the draw is untouched
    pos["draw"] = 4004.0
    done = {"AM": False, "PM": False}
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": 50.0}, q, 10, None, 50.0, False)
    assert done["PM"] is True


# --- X14-beginner-template-numbers (16) ----------------------------------------------------------------------------------------------------------

def test_beginner_template():
    p = Params(beginner_template=True, beginner_target_pts=15.0)
    assert (p.fixed_units, p.t1_fixed_pts, p.t1_fixed_all, p.max_stop_pts, p.trader_mode, p.new_day_stops) == (1, 15.0, True, 12.0, "new", True)
    assert Params(beginner_template=True, max_stop_pts=10.0).max_stop_pts == 10.0                     # a stop cap the user set stays
    q = Params()
    assert (q.fixed_units, q.t1_fixed_pts, q.t1_fixed_all, q.max_stop_pts, q.trader_mode) == (0, 0.0, False, 0.0, "")
    # a 14-pt structural stop is wider than the 12-handle cap (the order is dropped), an 8-pt stop trades; the exit is the single 12.5-pt target
    assert 14.0 > p.max_stop_pts > 8.0 and Params(beginner_template=True).t1_fixed_pts == 12.5
    # the day stop after the target: a +12.5 winner in "new" mode ends the day
    ctx = mkctx(flatrows(30))
    done = {"AM": False, "PM": False}
    pos, tr, sd = _closed_trade(ctx, 125.0)
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": 125.0}, Params(beginner_template=True), 10, None, 125.0, False)
    assert all(done.values())


# --- X14-conflicted-htf-one-entry (17) -----------------------------------------------------------------------------------------------------------

def test_conflicted_one_entry(monkeypatch):
    p = pk(conflicted_mode="one")
    monkeypatch.setattr(S, "_inside_daily_fvg", lambda hist: False)
    assert me3.conflicted_day([], {"fifty": 1}, p) is True and me3.conflicted_day([], {"fifty": 0}, p) is False and me3.conflicted_day([], None, p) is False
    monkeypatch.setattr(S, "_inside_daily_fvg", lambda hist: True)
    assert me3.conflicted_day([], None, p) is True
    # "one": after the first fill every key is done, win or loss; an untagged day is untouched
    ctx = mkctx(flatrows(6))
    ctx.conflicted = True
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    done = {"AM": False, "PM": False}
    fill3(ctx, sd, pos, tr, p, state={"reentered": {}}, done=done)
    assert all(done.values())
    ctx.conflicted = False
    done = {"AM": False, "PM": False}
    fill3(ctx, sd, pos, tr, p, state={"reentered": {}}, done=done)
    assert not any(done.values())
    # "one_win": done after a win only
    ctx.conflicted = True
    q = pk(conflicted_mode="one_win")
    pos, tr, sd = _closed_trade(ctx, 50.0)
    done = {"AM": False, "PM": False}
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": 50.0}, q, 10, None, 50.0, False)
    assert all(done.values())
    pos, tr, sd = _closed_trade(ctx, -50.0)
    done = {"AM": False, "PM": False}
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": -50.0}, q, 10, "long", -50.0, False)
    assert not any(done.values())


# --- L15-chop-micro-scalps (10) ------------------------------------------------------------------------------------------------------------------

def test_chop_scalp_cap():
    """Two scalps of +2.5 end the day (chop_scalp_max 2); one scalp does not; the day's 5 net pts end it too."""
    ctx = mkctx(flatrows(30))
    p = pk(chop_scalp_pts=2.5, sloppy_mode="scalp", es_pt=1.0)
    st = {"reentered": {}}
    done = {"AM": False, "PM": False}
    for k in range(2):
        pos, tr, sd = _closed_trade(ctx, 25.0)
        pos["scalp_chop"] = True
        tr.shares = 10
        tr.pnl = lambda cps=0.0: (25.0, 0.0)
        me3.after_close(ctx, pos, tr, done, "AM", st, p, 10, None, 25.0, False)
        assert (k == 0 and not any(done.values())) or (k == 1 and all(done.values()))
    assert st["chop_scalps"] == 2
    # a normal (non-scalp) trade does not count
    st = {"reentered": {}}
    done = {"AM": False}
    pos, tr, sd = _closed_trade(ctx, 25.0)
    me3.after_close(ctx, pos, tr, done, "AM", st, p, 10, None, 25.0, False)
    assert "chop_scalps" not in st
    # the day's points: one 5-pt scalp ends the day
    st = {"reentered": {}}
    done = {"AM": False}
    pos, tr, sd = _closed_trade(ctx, 50.0)
    pos["scalp_chop"] = True
    tr.shares = 10
    me3.after_close(ctx, pos, tr, done, "AM", st, p, 10, None, 50.0, False)
    assert done["AM"] and st["chop_pts"] == pytest.approx(5.0)
    # off the chop day: the order stage lets only the gap-retrace entries through
    ctx.cur_sloppy = "chop"
    assert me3.order_block(ctx, ctx.sides_map[1], {"broke": 1}, 1, p, "AM", 4000.0, {"entry_kind": "ob"}) == "x_chop_scalp_not_fvg"
    assert me3.order_block(ctx, ctx.sides_map[1], {"broke": 1}, 1, p, "AM", 4000.0, {"entry_kind": "fvg"}) is None


# --- X13-am-fail-no-reverse-pm-reset (1) ---------------------------------------------------------------------------------------------------------

def test_am_fail_pm_reset():
    """With reverse_after_loss off an AM long loses: "day" keeps the PM short blocked, "session" lets it arm from the reset time (13:30, or 14:00 with pm_reset_t 840)."""
    day, ses = pk(), pk(lost_side_scope="session")
    st = {"lost_fam": "AM"}
    assert me3.lost_side_holds(st, "AM", 600, ses) is True and me3.lost_side_holds(st, "PM", 820, ses) is False
    assert me3.lost_side_holds(st, "PM", 820, pk(lost_side_scope="session", pm_reset_t=840)) is True            # before 14:00 the block still holds
    assert me3.lost_side_holds(st, "PM", 845, pk(lost_side_scope="session", pm_reset_t=840)) is False
    import inspect
    assert "_ME3.lost_side_holds(state, session, t, p)" in inspect.getsource(S._run_day_once)
    assert Params().lost_side_scope == "day" and Params().pm_reset_t == 810


def _idea_book(down_run):
    """A bullish AM idea (want +1): the 09:30 session so far above 4000; bar 6 either breaks the AM low with a big down-close bar or just dips."""
    rows = [(4000, 4002, 3999, 4001)] * 6 + ([(4001, 4001.5, 3990, 3991)] if down_run else [(4001, 4001.5, 3998.5, 4000.5)])
    ctx = mkctx(rows)
    ctx.pd = {"pml": 3980.0, "pmh": 4010.0}
    return ctx


@pytest.mark.parametrize("run,fails", [(True, True), (False, False)])
def test_am_idea_fail_no_fill_run(run, fails):
    """No AM fill yet and the session's low (3999) is traded under, with a displacement down-close candle: the AM idea failed - done["AM"], a pending AM order is cancelled; the PM stays free."""
    ctx = _idea_book(run)
    p = pk(am_idea_fail=True)
    state, done = {}, {"AM": False, "PM": False}
    out = me3.bar(ctx, 6, p, state, done, [], None, 1)
    assert (out == "cancel_am") == fails and done["AM"] == fails and (state.get("idea_fail") == "no_fill_run") == fails and done["PM"] is False
    # an AM trade already filled: the rule is for the no-fill case only
    st2, d2 = {}, {"AM": False}
    done_tr = [SimpleNamespace(session="AM")]
    assert me3.bar(ctx, 6, p, st2, d2, done_tr, None, 1) is None and not d2["AM"]
    # no expected direction: nothing
    assert me3.bar(ctx, 6, p, {}, {"AM": False}, [], None, 0) is None


# --- new-london-close-second-swipe-reentry (199) -------------------------------------------------------------------------------------------------

def test_london_close_second_swipe():
    """A stopped AM long (stopped 10:30) whose sweep sat in an HTF array (no Confluence object here: the array test is skipped): the AM slot re-opens through the T3 lc_retry gate, risk x0.5; a winner or a stop at 09:50 does not."""
    ctx = mkctx(flatrows(80), t0=600)
    p = pk(lc_second_swipe=True)
    pos, tr, sd = mk_closed(ctx, exits=[(630, 3990.0, 10, "stop")])
    st = {"reentered": {}}
    done = {"AM": True}
    r = me3.after_close(ctx, pos, tr, done, "AM", st, p, 30, "long", -100.0, False)
    assert r is True and done["AM"] is False and st["lc_done"] and st["reentered"]["AM"] is True and ctx.lc_retry["side"] == 1 and ctx.lc_retry["session"] == "AM"
    # once only
    st["reentered"] = {}
    done = {"AM": True}
    assert me3.after_close(ctx, pos, tr, done, "AM", st, p, 30, "long", -100.0, False) is False and done["AM"]
    # a stop at 09:50 (before 10:00) or a winner: no second swipe
    for exits, lost in (([(590, 3990.0, 10, "stop")], "long"), ([(630, 4020.0, 10, "t1")], None)):
        ctx = mkctx(flatrows(80), t0=570)
        pos, tr, sd = mk_closed(ctx, exits=exits)
        done = {"AM": True}
        assert me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}}, p, 30, lost, -100.0 if lost else 100.0, False) is False and done["AM"]
    # the gate widening: the retry gate / lc tag also run for lc_second_swipe
    import inspect
    assert "p.lc_tag or p.lc_reentry or p.lc_second_swipe" in inspect.getsource(sm2.order_gate)


# --- new-reentry-after-breakaway-fill (65) -------------------------------------------------------------------------------------------------------

def test_reentry_after_breakaway_fill():
    """A breakaway entry stopped when its gap filled completely: the context is armed; no same-direction order until price reached the HTF level, then a new MSS + gap after that."""
    rows = [(4010, 4011, 4009, 4010)] * 4 + [(4010, 4010.5, 3996, 3997)] + [(3997, 3998, 3995, 3996)] * 3 + [(3996, 4008, 3995.5, 4007)] * 3
    ctx = mkctx(rows)
    ctx.state7 = {}
    p = pk(reentry_breakaway=True, reentry_half=True)
    pos, tr, sd = mk_closed(ctx, exits=[(575, 3990.0, 10, "stop")], fvg_bottom=4005.0)
    pos["fill_i"] = 2
    tr.lv_tags = "breakaway"
    sd2 = pos["side"]
    st = {"reentered": {}, "re3": {}}
    done = {"AM": True}
    r = me3.after_close(ctx, pos, tr, done, "AM", st, p, 4, "long", -100.0, False)
    arm = st["re3"]["AM"]
    assert r is True and done["AM"] is False and arm["kind"] == "breakaway" and arm["side"] == "long" and arm["pending"] and st["reentered"]["AM"] is True
    ctx.state7 = st
    long_sd = ctx.sides_map[1]
    assert arm["a_i"] is not None or arm["lvl"] is not None
    # not yet at the HTF level: blocked
    arm["a_i"], arm["lvl"] = None, 3994.0
    assert me3.order_block(ctx, long_sd, {"broke": 9}, 9, p, "AM", 4000.0, {}) == "x_reentry_breakaway_wait"
    me3.bar(ctx, 5, p, st, {"AM": False}, [], None)                                          # bar 5 traded to 3995 (> 3994): not there
    assert arm["a_i"] is None
    arm["lvl"] = 3995.5
    me3.bar(ctx, 6, p, st, {"AM": False}, [], None)                                          # bar 6's low 3995 <= 3995.5: stage (a) done
    assert arm["a_i"] == 6
    # stage (b): a new MSS (broke > a_i) and a gap formed after it
    assert me3.order_block(ctx, long_sd, {"broke": 5}, 9, p, "AM", 4000.0, {}) == "x_reentry_breakaway_mss"
    assert me3.order_block(ctx, long_sd, {"broke": 8}, 9, p, "AM", 4000.0, {}) in (None, "x_reentry_breakaway_mss")
    # the other direction is not gated
    assert me3.order_block(ctx, ctx.sides_map[-1], {"broke": 5}, 9, p, "AM", 4000.0, {}) is None
    # a loss whose gap did NOT fill completely is no breakaway failure
    pos, tr, sd = mk_closed(ctx, exits=[(575, 3990.0, 10, "stop")], fvg_bottom=3900.0)
    pos["fill_i"] = 2
    tr.lv_tags = "breakaway"
    st = {"reentered": {}, "re3": {}}
    assert me3.after_close(ctx, pos, tr, {"AM": True}, "AM", st, p, 4, "long", -100.0, False) is False and not st["re3"]


# --- M12-ote-failure-turtle-soup (118) -----------------------------------------------------------------------------------------------------------

def test_ote_stop_then_turtle_soup_arms():
    """An OTE-tagged long stopped under a prior low (the pivot low it ran) arms the turtle-soup context at that low and re-opens the slot at half risk; a non-OTE entry does not."""
    rows = [(4010, 4011, 4009, 4010), (4010, 4010.5, 4000, 4001), (4001, 4008, 4001.5, 4007), (4007, 4009, 4004, 4005), (4005, 4006, 4003, 4004), (4004, 4004.5, 3990, 3991), (3991, 3994, 3989, 3993)]
    ctx = mkctx(rows)
    p = pk(ote_fail_ts=True)
    pos, tr, sd = mk_closed(ctx, exits=[(576, 3992.0, 10, "stop")], entry=4004.0)
    pos["fill_i"] = 4
    tr.entry_kind = "ote"
    st = {"reentered": {}, "re3": {}}
    done = {"AM": True}
    r = me3.after_close(ctx, pos, tr, done, "AM", st, p, 5, "long", -100.0, False)
    arm = st["re3"].get("AM")
    assert r is True and arm and arm["kind"] == "ote_ts" and arm["side"] == "long" and arm["lvl"] == pytest.approx(4000.0) and done["AM"] is False and st["reentered"]["AM"] is True
    ctx.re3_now = arm
    assert me3.any_re_orders(ctx, p) is True and me3.any_re_orders(ctx, pk()) is False
    pos, tr, sd = mk_closed(ctx, exits=[(576, 3992.0, 10, "stop")], entry=4004.0)
    pos["fill_i"] = 4
    tr.entry_kind = "fvg"
    st = {"reentered": {}, "re3": {}}
    assert me3.after_close(ctx, pos, tr, {"AM": True}, "AM", st, p, 5, "long", -100.0, False) is False and not st["re3"]


def test_ote_turtle_soup_order(monkeypatch):
    """The re-entry order: price traded under the old low 4000 by 3 pts (<= ts_max_pts) and a candle closed back above within ts_back_bars: a limit AT the old low, the stop under the false-break extreme."""
    from mentorship import sm4
    got = {}
    monkeypatch.setattr(sm4, "_order", lambda ctx, sd, i, p, session, rm, name, entry, stop, **kw: got.update(name=name, entry=entry, stop=stop, ext_i=kw["ext_i"], rm=rm) or dict(entry=entry, stop=stop))
    rows = [(4010, 4011, 4009, 4010)] * 4 + [(4005, 4006, 3997, 3998), (3998, 4003, 3996.5, 4002), (4002, 4004, 4001, 4003)]
    ctx = mkctx(rows)
    p = pk(ote_fail_ts=True, ts_back_bars=3)
    ctx.re3_now = dict(kind="ote_ts", side="long", stop_i=4, lvl=4000.0, pending=True)
    sd = ctx.sides_map[1]
    o = me3.re_order(ctx, sd, 6, p, "AM", 0.5)
    assert o is not None and got["name"] == "ote_ts" and got["entry"] == 4000.0 and got["stop"] == pytest.approx(3996.5 - p.pad) and got["ext_i"] == 5 and got["rm"] == 0.5
    assert ctx.re3_now["armed"] is True and me3.re_order(ctx, sd, 6, p, "AM", 0.5) is None                       # once
    # too deep a break (> ts_max_pts) / no close back above: nothing
    deep = [(4010, 4011, 4009, 4010)] * 4 + [(4005, 4006, 3990, 3992), (3992, 3995, 3991, 3994), (3994, 3996, 3993, 3995)]
    ctx = mkctx(deep)
    ctx.re3_now = dict(kind="ote_ts", side="long", stop_i=4, lvl=4000.0, pending=True)
    assert me3.re_order(ctx, ctx.sides_map[1], 6, p, "AM", 0.5) is None
    ctx = mkctx(rows)
    ctx.re3_now = dict(kind="ote_ts", side="short", stop_i=4, lvl=4000.0, pending=True)
    assert me3.re_order(ctx, ctx.sides_map[1], 6, p, "AM", 0.5) is None                                           # the other direction


# --- engine runs (scenario C through run_day) -------------------------------------------------------------------------------------------------------

from test_review_fixes import BASE, day, history, run as rf_run
from test_caption_gap_es1a import C_ROWS, POST


def _c(rows=None, **kw):
    tr, locks, log, skips = rf_run(day(rows or C_ROWS), history(), Params(**{**BASE, **POST, **kw}), {})
    return tr


def test_engine_defaults_do_not_change_scenario_c():
    base = _c()
    assert len(base) == 1
    same = _c(abort_mode="full", lost_side_scope="day", reentry_count_max=1, scalp_mode="", recovery_exit="", conflicted_mode="off")
    assert [(t.entry, t.stop, [e[3] for e in t.exits]) for t in same] == [(t.entry, t.stop, [e[3] for e in t.exits]) for t in base]


def test_engine_laggard_tag_and_params_flow():
    """laggard_mult leaves a trade without a partner as a normal trade (no tag); the Trade carries the laggard column."""
    tr = _c(laggard_mult=2.0, time_stop_min=10)
    assert len(tr) == 1 and tr[0].laggard is False and "laggard" not in (tr[0].mgmt_tags or "")


def test_engine_conflicted_skip_and_one(monkeypatch):
    monkeypatch.setattr(S, "_inside_daily_fvg", lambda hist: True)
    assert _c(conflicted_mode="skip") == []
    one = _c(conflicted_mode="one")
    assert len(one) == 1                                                                         # one entry, then the day is done
    monkeypatch.setattr(S, "_inside_daily_fvg", lambda hist: False)
    assert len(_c(conflicted_mode="skip")) == 1                                                  # an untagged day is unchanged


# --- X8-offside-flip (42): scenario C, an up-close candle (09:50, open 101.0) above the 100.4 fill; price reaches it, respects it, then closes under the fill ---------------------------------------

OFFSIDE_ROWS = list(C_ROWS[:5]) + [(101.6, 101.7, 100.3, 100.5), (100.5, 101.2, 100.3, 100.7), (100.7, 100.8, 99.9, 100.0), (100.0, 100.1, 99.8, 99.9), (99.9, 100.0, 99.7, 99.8)]


def test_offside_flip():
    off = _c(OFFSIDE_ROWS, offside_exit=True)
    assert len(off) == 1 and [e[3] for e in off[0].exits] == ["offside"]
    on = _c(OFFSIDE_ROWS, offside_exit=True, offside_flip=True)
    assert len(on) == 2 and [e[3] for e in on[0].exits] == ["offside"]
    flip = on[1]
    assert flip.side == "short" and flip.entry_kind == "offside_flip" and flip.shares == on[0].shares              # the same units, the opposite side, at the next open
    assert flip.entry == pytest.approx(on[0].exits[0][1]) and flip.entry_time > on[0].exits[0][0]
    assert flip.stop > 101.0                                                                                      # above the reaction candles' bodies / the defending wick CE


def test_offside_flip_off_is_the_old_run():
    assert len(_c(OFFSIDE_ROWS, offside_exit=True, offside_flip=False)) == 1


# --- X13-reentry-mechanics (128) / D18-reentry-count-max-2 (5): a stop-out at 10:00, the next CC-validated down-close candle ------------------------------------------------------------------------------

CC_ROWS = list(C_ROWS[:5]) + [(101.6, 101.7, 100.3, 100.5), (100.5, 100.6, 98.9, 99.0), (99.0, 99.6, 98.8, 99.5), (99.5, 99.6, 99.0, 99.1), (99.1, 100.2, 99.0, 100.1), (100.1, 100.3, 99.9, 100.0), (100.0, 100.1, 99.5, 99.8),
                              (99.8, 101.0, 99.7, 100.9), (100.9, 103.0, 100.5, 102.9), (102.9, 108.5, 102.8, 108.4)]


def test_reentry_cc_ob_mechanics():
    """After the 10:00 stop-out: the down-close candle (09:55... 10:10 bar: high 99.6, low 99.0) is validated by a later bar trading above its high; the limit sits at that HIGH (99.6), the stop under its LOW, half risk."""
    base = _c(CC_ROWS, reentry_half=True)
    assert len(base) == 1                                                                                           # the built re-entry finds nothing in this book
    tr = _c(CC_ROWS, reentry_half=True, reentry_mode="cc_ob")
    assert len(tr) == 2 and tr[1].reentry and tr[1].entry == pytest.approx(99.6) and tr[1].stop < 99.0 and tr[1].entry_kind == "ob_low"
    assert tr[1].shares < tr[0].shares                                                                              # half the risk
    op = _c(CC_ROWS, reentry_half=True, reentry_mode="cc_ob", reentry_cc_entry="open")
    assert all(t.entry != pytest.approx(99.6) for t in op)                                                          # the variant's limit is the candle's open (99.5): the book never trades through it


COUNT_ROWS = CC_ROWS[:12] + [(99.8, 99.9, 98.5, 98.6), (98.6, 99.0, 97.9, 98.9), (98.9, 99.4, 98.2, 98.4), (98.4, 99.9, 98.3, 99.8), (99.8, 99.9, 99.2, 99.5), (99.5, 99.6, 99.0, 99.3), (99.3, 101.0, 99.1, 100.9),
                             (100.9, 103.0, 100.5, 102.9), (102.9, 108.5, 102.8, 108.4)]


def test_reentry_count_two_attempts():
    """Two consecutive stop-outs: reentry_count_max 1 re-arms once (the second loss ends the tries); 2 arms a third try at a quarter of the risk."""
    one = _c(COUNT_ROWS, reentry_half=True, reentry_mode="cc_ob", sloppy_mode="off")
    two = _c(COUNT_ROWS, reentry_half=True, reentry_mode="cc_ob", reentry_count_max=2, sloppy_mode="off")
    assert len(one) == 2 and len(two) == 3 and two[2].reentry
    assert [e[3] for e in two[1].exits] == ["stop"] and two[2].shares < two[1].shares
