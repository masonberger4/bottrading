"""Caption-gap pass, package management_exits #3/3, review-fix round: unit tests of the fixes (day mode exempt by default, trader_mode "new" implies the day stops, the runner-stop refusal with the
win / trail-win re-entry switches, the session-fail flatten enforcement, the cc_ob limit under the market, the order_block lift for setups without an MSS bar, the independent London partials, the
two_session explosive branch, the combine-level laggard tag, the paper stop-acknowledgement wiring, the AM-window bound of am_idea_fail). Hand-made books on the stub context of
test_caption_gap_me1a.py; nothing here needs market data and nothing is platform specific."""
from types import SimpleNamespace

import pandas as pd

from mentorship import backtest as B, manage as MG, me3, paper, setups as ST, strategy as S
from mentorship.strategy import Params

from test_caption_gap_me1a import flatrows, mkctx, mkpos, pk, reasons
from test_caption_gap_me3a import fill3, step3, _am_step
from test_caption_gap_me3b import mk_closed

NY = "America/New_York"
D = pd.Timestamp("2026-04-07").date()                                                       # (a day with no FOMC release)


def test_day_mode_is_exempt_by_default():
    """116: a day-mode position is not closed at 12:00 with the default Params (day mode itself is the exemption); day_mode_no_am_exit=False restores the old close."""
    assert Params().day_mode_no_am_exit is True and me3.noon_exempt({"day_trade": True}, Params()) is True
    rows = [(4000, 4001, 3999, 4000)] * 200
    ctx = mkctx(rows, t0=715)
    p = pk()
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,), day_trade=True)
    fill3(ctx, sd, pos, tr, p)
    _am_step(ctx, sd, pos, tr, p, 1, 150)
    assert pos["left"] == 10 and not tr.exits
    ctx = mkctx(rows, t0=715)
    q = pk(day_mode_no_am_exit=False)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,), day_trade=True)
    fill3(ctx, sd, pos, tr, q)
    _am_step(ctx, sd, pos, tr, q, 1, 20)
    assert reasons(tr) == ["am_exit"]


def test_trader_mode_new_implies_the_day_stops():
    """15: trader_mode "new" alone (new_day_stops defaults on) closes the day after a positive AM, and a losing AM gets no PM; pm_recover_loss no longer exists (recovery is experienced-only)."""
    assert Params().new_day_stops is True and "pm_recover_loss" not in Params.__dataclass_fields__
    ctx = mkctx(flatrows(30))
    done = {"AM": False, "PM": False, "SB_AM": False, "SB_PM": False}
    pos, tr, sd = mk_closed(ctx, exits=[(575, 4010.0, 10, "t1")])
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": 50.0}, pk(trader_mode="new"), 10, None, 50.0, False)
    assert all(done.values())
    done = {"AM": False, "PM": False}
    pos, tr, sd = mk_closed(ctx, exits=[(575, 3990.0, 10, "stop")])
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": -50.0}, pk(trader_mode="new"), 10, "long", -50.0, False)
    assert done["PM"] is True
    done = {"AM": False, "PM": False}
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": -50.0}, pk(trader_mode="experienced"), 10, "long", -50.0, False)
    assert done["PM"] is False                                                                 # experienced: a losing AM may be recovered in the PM


def test_draw_open_does_not_reopen_a_stopped_pm():
    """15: pm_after_am_win draw_open re-opens a PM that only no_pm_after_am_win closed, never one a stop / the day cap closed in the same close."""
    ctx = mkctx([(4000, 4005, 3999, 4004)] * 12)
    pos, tr, sd = mk_closed(ctx, exits=[(575, 4010.0, 10, "t1")])
    pos["draw"] = 4050.0
    q = pk(pm_after_am_win="draw_open")
    done = {"AM": False, "PM": True}
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": 50.0}, q, 10, None, 50.0, False)
    assert done["PM"] is False
    done = {"AM": False, "PM": True}
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": 50.0, "stops": {"day": None, "PM": "x"}}, q, 10, None, 50.0, False)
    assert done["PM"] is True
    done = {"AM": False, "PM": True}
    me3.after_close(ctx, pos, tr, done, "AM", {"reentered": {}, "day_net": 50.0, "day_done": True}, q, 10, None, 50.0, False)
    assert done["PM"] is True


def test_runner_stop_refusal_follows_the_reentry_switches():
    """9: a runner stopped after >= 75 % banked refuses the win / trail-win re-entry whenever one of those switches is on (no separate runner_stop_no_reentry needed)."""
    assert me3.runner_stop_on(Params()) is False
    assert me3.runner_stop_on(Params(reentry_after_trail_win=True, trail=True)) and me3.runner_stop_on(Params(reentry_after_win=True))
    ctx = mkctx(flatrows(20))
    p = pk(reentry_after_trail_win=True, trail=True)
    state = {"reentered": {}}
    pos, tr, sd = mk_closed(ctx, exits=[(572, 4010.0, 8, "t1"), (575, 4001.0, 2, "stop")])
    assert me3.pre_close(pos, tr, state, p, 10) is True and state["no_win_reentry"] and pos["runner_stop"]
    state = {"reentered": {}}
    pos, tr, sd = mk_closed(ctx, exits=[(572, 4010.0, 4, "t1"), (575, 3995.0, 6, "stop")])
    assert me3.pre_close(pos, tr, state, p, 10) is False and not state.get("no_win_reentry")


def test_session_fail_flatten_is_enforced_and_does_not_double_count():
    """13: the flatten's stop is enforced without session_stop_after_fails (manage.any_stop_switch), and the open trade is not counted among the closed failures."""
    base = dict(session_stop_after_fails=0, loss_ends_morning=False, no_trade_after_win=False, chop_one_win=False, obj_stop=False, done_if_target=False)
    assert MG.any_stop_switch(Params(session_fail_flatten=True, **base), D) and not MG.any_stop_switch(Params(**base), D)
    ctx = mkctx(flatrows(10))
    p = pk(session_fail_flatten=True)
    a, ta, _ = mk_closed(ctx, exits=[(572, 3990.0, 10, "stop")])
    b, tb, _ = mk_closed(ctx, exits=[(574, 3990.0, 5, "t1"), (575, 3985.0, 5, "stop")])
    tb.exits = [(tb.exits[0][0], 3990.0, 10, "stop")]
    assert me3._fails_in_family([ta, tb], "AM", p) == 2
    assert me3._fails_in_family([ta, tb], "AM", p, skip=tb) == 1
    # a state flatten sticks through apply_stops
    state = {"stops": {"day": None, "AM": "pd3_session"}}
    done = {"AM": False, "PRE9": False, "PM": False}
    p = Params(session_fail_flatten=True, **base)
    ta.stop_day, ta.slow_chop, ta.date = False, False, D
    MG.apply_stops([ta], p, done, state)
    assert done["AM"] and done["PRE9"] and not done["PM"]


def test_cc_ob_limit_stays_under_the_market():
    """128: the re-entry limit at the candle's high is armed only under the close (never a marketable buy)."""
    from mentorship import es3
    rows = [(4000, 4001, 3999, 4000), (4001, 4002, 3996, 3997), (3997, 4005, 3997, 4000), (4000, 4001, 3999, 4000)]
    ctx = mkctx(rows)
    sd = ctx.sides_map[1]
    ctx.re_ctx_now = dict(pending=True, side="long", stop_i=0)
    p = pk(reentry_mode="cc_ob", reentry_cc_entry="high", reentry_half=True, reentry_stop="ob_low")
    # the candle 1 (down close, high 4002) was traded above on bar 2, but bar 2 closed at 4000 < 4002: a limit at 4002 would be marketable - no order
    assert es3.ob_low_order(ctx, sd, 2, p, "AM", 0.5) is None
    assert "armed_ob" not in ctx.re_ctx_now


def test_order_block_lifts_for_a_setup_without_an_mss_bar():
    """130: a setup carrying no 'broke' key is dated by its sweep extreme bar; formed after the close it lifts the block, before it stays blocked."""
    ctx = mkctx(flatrows(20))
    p = pk(abort_blocks_side=True)
    ctx.state7 = {"blocked_side": {"AM": dict(side="long", i=10)}}
    sd = ctx.sides_map[1]
    assert me3.order_block(ctx, sd, {"ext_i": 8}, 13, p, "AM", 4000.0, {}) == "x_abort_blocks_side"
    assert me3.order_block(ctx, sd, {"ext_i": 12}, 13, p, "AM", 4000.0, {}) is None


def test_london_partials_are_independent():
    """124: a position that sat through a gap in the bars (04:55 and 06:55 both passed in one step) takes both partials."""
    rows = [(4000, 4001, 3999, 4000)] * 3
    ctx = mkctx(rows, t0=3 * 60 + 10)
    ctx.t = ctx.t.copy()
    ctx.t[2] = 7 * 60 + 5                                                                     # the next bar is 07:05: both thresholds passed
    p = pk(london_tod_partials=True, london_tod_frac=0.25)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,), n=16)
    tr.session = "LON"
    fill3(ctx, sd, pos, tr, p)
    step3(ctx, sd, pos, tr, p, 2)
    assert reasons(tr) == ["lon_0500", "lon_0700"]


def test_explosive_two_session_branch(monkeypatch):
    """117: on a 25-pt day (not explosive by range) a two_session profile in the trade direction still keeps the runner past 12:00; the opposite direction / another profile does not."""
    n = 600
    rows = [(4000, 4001, 3999, 4000)] * n
    rows[0] = (4000, 4025, 4000, 4024)
    rows[145] = (4000, 4028, 4000, 4027)
    monkeypatch.setattr(S, "adr5", lambda days: 40.0)
    for prof, expl in ((("two_session_up", 1), True), (("two_session_down", -1), False), (("am_rally_pm_reversal", -1), False)):
        monkeypatch.setattr(ST, "cc_profile", lambda ctx, i, p, at=810, _p=prof: _p)
        ctx = mkctx(rows)
        ctx.hist = [SimpleNamespace()] * 5
        p = pk(explosive_runner=True)
        pos, tr, sd = mkpos(ctx, 1, 100, 4000.0, 3990.0, levels=(4200.0,))
        fill3(ctx, sd, pos, tr, p)
        for i in range(146, 160):
            if not pos["left"]:
                break
            if int(ctx.t[i]) + ctx.tf >= 720 and not me3.am_skip(ctx, sd, pos, tr, i, ctx.idx[i], p, 720):
                tr.exits.append((ctx.idx[i], float(ctx.c[i]), pos["left"], "am_exit")); pos["left"] = 0
        assert (pos["left"] == 10) == expl, prof


def test_cc_profile_noon_variant_is_cached_separately():
    """117: setups.cc_profile(at=720) classifies from the bars closed by 12:00 and caches under its own attribute (the 13:30 call is unaffected)."""
    import inspect
    src = inspect.getsource(ST.cc_profile)
    assert "at: int = 810" in inspect.signature(ST.cc_profile).__str__() or "at" in inspect.signature(ST.cc_profile).parameters
    assert "_cc_prof_%d" in src


def test_laggard_draw_tag_in_combine():
    """111: combine(laggard_tag=True) marks a fill taken at or after another instrument's met draw (the real-draw map, or the final_hit read of hand-made books)."""
    t = lambda s: pd.Timestamp(f"2026-04-06 {s}", tz=NY)
    es = pd.DataFrame(dict(date=[pd.Timestamp("2026-04-06").date()], symbol=["ES"], entry_time=[t("09:40")], exit_time=[t("10:10")], final_hit=[True], net=[10.0]))
    nq = pd.DataFrame(dict(date=[pd.Timestamp("2026-04-06").date()] * 2, symbol=["NQ", "NQ"], entry_time=[t("09:35"), t("10:20")], exit_time=[t("09:50"), t("10:40")], final_hit=[False, False], net=[1.0, 2.0]))
    both = pd.concat([es, nq], ignore_index=True)
    out = B.laggard_draw_tag(both)
    assert list(out.sort_values("entry_time").laggard_draw) == [False, False, True]                  # only the NQ fill at 10:20 (ES met its draw at 10:10)
    out2 = B.laggard_draw_tag(both, {(es.date[0], "ES"): t("10:10")})
    assert list(out2.sort_values("entry_time").laggard_draw) == [False, False, True]
    assert "laggard_draw" in B.combine.__doc__ and "laggard_tag" in B.combine.__code__.co_varnames


def test_paper_stop_ack_watch_is_wired():
    """131: paper.watch_open_trades creates one StopAckWatch per open trade; no ack within stop_ack_sec -> 'unprotected' (one 100 % rung), then a bar close against the entry -> 'exit_market'; inert at 0."""
    t0 = pd.Timestamp("2026-04-06 09:40", tz=NY)
    tr = SimpleNamespace(exits=[], entry_time=t0, side="long", entry=4000.0, t1=4010.0, t2=4020.0)
    w = {}
    p = Params(stop_ack_sec=10)
    assert paper.watch_open_trades(w, [tr], t0 + pd.Timedelta(seconds=5), p, acked=lambda x: False) == []
    acts = paper.watch_open_trades(w, [tr], t0 + pd.Timedelta(seconds=11), p, acked=lambda x: False)
    assert acts and acts[0][0] == "unprotected" and acts[0][2] == ([4010.0], [1.0])
    acts = paper.watch_open_trades(w, [tr], t0 + pd.Timedelta(seconds=70), p, acked=lambda x: False, last_close=3999.0)
    assert [a[0] for a in acts] == ["exit_market"]
    assert paper.watch_open_trades({}, [tr], t0 + pd.Timedelta(seconds=70), Params(), acked=lambda x: False) == []
    assert paper.watch_open_trades({}, [tr], t0 + pd.Timedelta(seconds=70), p) == []                  # the simulated paper layer: acknowledged at once


def test_am_idea_fail_is_bound_to_the_am_window():
    """1: me3.bar does not run the AM-idea check at or after the AM exit (12:00)."""
    import inspect
    assert "p.am_exit or 720" in inspect.getsource(me3.bar)


# --- forced look-ahead scenarios (the paths random books never reach): scenario-C books run through run_day, full vs every truncation -------------------------------------------------------------

def _forced_la(rows, need, **kw):
    """Run the book in full and cut after every bar: every trade of the truncated run must be the full run's trade (side, kind, entry, stop, units, entry time), and the full run must have bumped `need`."""
    from mentorship import sm2
    from test_caption_gap_me3b import _c
    h0 = dict(sm2.HITS)
    full = _c(rows, **kw)
    added = {k: v - h0.get(k, 0) for k, v in sm2.HITS.items() if v - h0.get(k, 0)}
    assert full and all(added.get(k) for k in need), (need, sorted(added))
    key = lambda t: (t.side, t.entry_kind, round(float(t.entry), 6), round(float(t.stop), 6), t.shares, t.entry_time)
    fk = {t.entry_time: key(t) for t in full}
    for n in range(6, len(rows)):
        for t in _c(rows[:n], **kw):
            assert t.entry_time in fk and key(t) == fk[t.entry_time], (n, key(t))                    # (every trade the truncated book entered is the full run's trade: nothing of the future was used)
    return full


def test_forced_look_ahead_offside_flip():
    from test_caption_gap_me3b import OFFSIDE_ROWS
    full = _forced_la(OFFSIDE_ROWS, ("eval_offside_flip", "offside_flip"), offside_exit=True, offside_flip=True)
    assert len(full) == 2 and full[1].entry_kind == "offside_flip"


def test_forced_look_ahead_cc_ob_reentry_count():
    from test_caption_gap_me3b import COUNT_ROWS
    full = _forced_la(COUNT_ROWS, ("reentry_count", "reentry_ob_low"), reentry_half=True, reentry_mode="cc_ob", reentry_count_max=2, sloppy_mode="off")
    assert len(full) == 3
