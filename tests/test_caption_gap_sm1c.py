"""Caption-gap pass, package setups_models #1/7, review fixes: the corrections of the first build (look-ahead on the open bar, the lc_reentry slot, the engine-level
objective for smt_pick "laggard_objective", the SMT reference window, the N6 pool targets, the release setups' done flags, the DS2 / A13 / A15 sub-cases) and the
executed-path no-look-ahead runs on real ES days. Tests that need local market data (ES) skip cleanly when it is absent; no platform-specific paths."""
import warnings
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, sm2, strategy as S, study
from mentorship.strategy import Params

from test_levels_detectors import BASE, D0, ES, NY, day, history
from test_review_fixes import B_POST, B_ROWS
from test_caption_gap_sm1a import StubConf, hist_close, ib, mkctx
from test_caption_gap_sm1b import RUN_P, BIAS_UP, SYN_BASE, run_day
from test_caption_gap_ld1 import ENTRY, SYN

JOBS = date(2026, 6, 5)


# --- gap premium: a bar AFTER the 09:30 bar -----------------------------------------------------------------------------------

def test_gap_premium_wait_ignores_the_open_bar():
    """The 09:30 bar's own low is below its own open almost always: it does not count as 'a trade below the 09:30 open' (gap up -> shorts wait for a LATER bar)."""
    rows = [(4098.0, 4099.0, 4097.0, 4098.5), (4098.5, 4099.5, 4098.2, 4099.0), (4099.0, 4099.2, 4098.4, 4098.8), (4098.8, 4098.9, 4096.5, 4097.0)]
    conf = SimpleNamespace(valid=lambda t, side, tfs, src, known_by=None: [(4101.0, 4095.0, "W", 2, 0.0)] if side == -1 else [])
    ctx, (sl, ss) = mkctx(rows, base=4098.0, hist=hist_close(close=4080.0, hi=4110.0, lo=4070.0), conf=conf)
    p = Params(**BASE, gap_premium_arm=True)
    k0 = ib(ctx, "09:30")
    assert sm2.gap_premium_gate(ctx, ss, dict(smt=None), k0 + 2, p, []) == "x_gap_premium_wait"      # only the open bar (low 4097) is under 4098
    assert sm2.gap_premium_gate(ctx, ss, dict(smt=None), k0 + 3, p, []) is None                      # bar 4 (low 4096.5) traded under it
    # the mirror: a gap down into a bullish HTF array; longs wait for a later bar above the open
    rows_d = [(4098.0, 4099.0, 4097.0, 4097.5), (4097.5, 4097.9, 4096.5, 4097.0), (4097.0, 4097.8, 4096.0, 4096.5), (4096.5, 4099.5, 4096.4, 4099.0)]
    conf_d = SimpleNamespace(valid=lambda t, side, tfs, src, known_by=None: [(4101.0, 4095.0, "W", 2, 0.0)] if side == 1 else [])
    ctx2, (sl2, ss2) = mkctx(rows_d, base=4098.0, hist=hist_close(close=4120.0, hi=4130.0, lo=4090.0), conf=conf_d)
    assert sm2.gap_premium_gate(ctx2, sl2, dict(smt=None), k0 + 2, p, []) == "x_gap_premium_wait"    # the open bar's high (4099) is above 4098 but is not a later bar
    assert sm2.gap_premium_gate(ctx2, sl2, dict(smt=None), k0 + 3, p, []) is None


# --- B12: the open bar is not the Judas ---------------------------------------------------------------------------------------

def test_judas_scan_skips_the_open_bar():
    """A flat day whose only 'trade beyond the midnight open' is the open bar itself: the tolerance does not apply and the PO3 sequence is False."""
    rows = [(101.0, 101.5, 100.5, 101.2)] * 12
    ctx, (sl, ss) = mkctx(rows, base=100.0, w=0.0)
    ctx.l[ctx.start] = 99.8                                                                          # the 00:00 bar's low is under its own open (the filler is flat otherwise)
    assert ctx.opens["midnight"] == 100.0 and sl.l[ctx.start] < 100.0 - 1e-9 and sl.l[ctx.start + 1:ib(ctx, "09:30")].min() >= 100.0
    assert sm2.judas_from(ctx, ctx.start, 100.0) == ctx.start + 1
    assert sm2.judas_from(ctx, ctx.start, 123.0) == ctx.start                                       # not an open of the day
    p = Params(**BASE, open_tol_pts=2.0)
    sw = dict(broke=ib(ctx, "10:05"), ext=100.5, ext_i=ib(ctx, "09:45"))
    assert not sm2.open_tol_ok(ctx, sl, sw, ib(ctx, "10:10"), p, "AM", 101.3, 100.0)                  # strict
    pp = replace(Params(**BASE), po3_seq="tag", bias_open="midnight")
    assert sm2.po3_seq_state(ctx, sl, dict(sw), ib(ctx, "10:10"), pp, "AM", 100.5) is False
    # a real Judas later in the day (a bar trades under the open after 00:00) turns both on again
    rows2 = [(101.0, 101.5, 100.5, 101.2), (101.2, 101.3, 99.0, 99.5), (99.5, 102.0, 99.4, 101.8)] + [(101.8, 102.0, 101.5, 101.9)] * 9
    ctx2, (sl2, _) = mkctx(rows2, base=100.0, w=0.0)
    sw2 = dict(broke=ib(ctx2, "10:05"), ext=99.0, ext_i=ib(ctx2, "09:35"))
    assert sm2.open_tol_ok(ctx2, sl2, sw2, ib(ctx2, "10:10"), p, "AM", 101.3, 100.0)
    assert sm2.po3_seq_state(ctx2, sl2, dict(sw2), ib(ctx2, "10:10"), pp, "AM", 100.5) is True


# --- T3 lc_reentry: the slot, the array, the morning --------------------------------------------------------------------------

def _lc_ctx(morning_up: bool, conf=None):
    up = [(100.0 + 0.2 * k, 100.3 + 0.2 * k, 99.9 + 0.2 * k, 100.2 + 0.2 * k) for k in range(6)]          # 09:30-10:00 rises to ~101.2
    dn = [(100.0 - 0.2 * k, 100.1 - 0.2 * k, 99.7 - 0.2 * k, 99.8 - 0.2 * k) for k in range(6)]            # ... or falls to ~98.8
    rows = (up if morning_up else dn) + [(99.0, 99.2, 98.0, 98.4)] * 8
    return mkctx(rows, base=100.0, conf=conf, w=0.0)


def test_lc_reversal_is_against_the_morning_and_inside_an_array():
    arr = StubConf({1: [(98.5, 97.5, "D", 0, 0.0)]})
    ctx, (sl, ss) = _lc_ctx(False, arr)
    p = Params(**BASE, lc_tag=True)
    k = ib(ctx, "10:20")
    assert sm2.morning_dir(ctx, k) == -1
    assert sm2.lc_reversal(ctx, sl, dict(ext=98.0, ext_i=k - 1), k, p, [], False) is True               # a long off the D array after a morning decline
    assert sm2.lc_reversal(ctx, sl, dict(ext=96.0, ext_i=k - 1), k, p, ["D"], True) is False             # the sweep extreme is OUTSIDE the array (the order's cf list says D: not asked)
    ctx2, (sl2, _) = _lc_ctx(True, arr)
    assert sm2.morning_dir(ctx2, k) == 1
    assert sm2.lc_reversal(ctx2, sl2, dict(ext=98.0, ext_i=k - 1), k, p, [], False) is False             # the morning already went the long's way
    assert sm2.lc_array(ctx, sl, dict(ext=98.0, ext_i=k - 1), k, p) == (98.5, 97.5, "D")


def test_lc_retry_gate_is_the_slot_only():
    """After a stopped-out lc_reversal the re-opened AM slot needs the retry; a PM order, an order of another done key and everything after the retry's trade closed are
    not touched; the retry must sit in the SAME HTF array."""
    arrA, arrB = (98.5, 97.5, "D", 0, 0.0), (97.4, 96.0, "D", 0, 0.0)
    ctx, (sl, ss) = _lc_ctx(False, StubConf({1: [arrA, arrB]}))
    p = Params(**BASE, lc_reentry=True)
    k = ib(ctx, "10:20")
    first = SimpleNamespace(side="long", ext_px=98.2, session="AM")
    assert sm2.lc_reversal(ctx, sl, dict(ext=98.2, ext_i=k - 2), k, p, [], False)            # records the first trade's array
    done, state = {"AM": True}, {}
    sm2.lc_reopen(ctx, first, done, "AM", state)
    assert done["AM"] is False and ctx.lc_retry["arr"] == (98.5, 97.5, "D")

    def gate(sd, ext, sess="AM", tags=None):
        return sm2.order_gate(ctx, sd, dict(ext=ext, ext_i=k - 1, smt=None), k, p, 99.0, 97.0, sess, None, None, [], {}, tags if tags is not None else {})

    assert gate(sl, 98.0) is None                                  # deeper than the first extreme 98.2, inside the same D array
    assert gate(sl, 96.5) == "x_lc_retry"                          # deeper, but in the OTHER array
    assert gate(sl, 98.4) == "x_lc_retry"                          # not beyond the first extreme
    assert gate(sl, 96.5, "PM") is None                            # the PM is not the re-opened slot
    assert gate(sl, 96.5, "AM", {"done_key": "SB_AM"}) is None     # another done key neither
    sm2.lc_clear(ctx)
    assert gate(sl, 98.4) is None                                  # the retry's trade closed: no gate left


# --- D15 laggard_objective: the instrument's OWN draw met (engine level) -------------------------------------------------------

def _obook(rows):
    """Like sm1a._book but keeps every key of the rows (obj_met_t)."""
    df = pd.DataFrame(rows)
    for c in ("entry_time", "exit_time"):
        df[c] = pd.to_datetime(df[c]).dt.tz_localize(NY)
    return df


def test_objective_record_is_the_own_draw():
    rows = [(100.0, 100.5, 99.5, 100.2), (100.2, 101.0, 100.0, 100.8), (100.8, 103.2, 100.7, 103.0), (103.0, 103.5, 102.5, 103.1)]
    ctx, (sl, ss) = mkctx(rows, base=100.0)
    p = Params(**BASE, smt_pick="laggard_objective", htf_bias="combo")
    ctx.bias_row = dict(combo=1, draw_up=103.0, draw_dn=float("nan"))
    rec = sm2.objective_record(ctx, p, "ES")
    k0 = ib(ctx, "09:30")
    assert rec["side"] == 1 and rec["draw"] == 103.0 and rec["t"] == ctx.idx[k0 + 2] + pd.Timedelta(minutes=5)         # the bar that traded 103.2, known at ITS close
    ctx.bias_row = dict(combo=1, draw_up=104.0, draw_dn=float("nan"))
    assert sm2.objective_record(ctx, p, "ES")["t"] is None                                                           # never traded: not met
    ctx.bias_row = dict(combo=0, draw_up=103.0, draw_dn=99.0)
    assert sm2.objective_record(ctx, p, "ES") is None                                                                # no bias, no objective
    ctx.bias_row = dict(combo=-1, draw_up=105.0, draw_dn=99.6)
    assert sm2.objective_record(ctx, p, "ES")["t"] == ctx.idx[k0] + pd.Timedelta(minutes=5)                          # the draw below was traded on the first bar
    # off: nothing is stamped
    trades, out = [SimpleNamespace(obj_met_t=None)], []
    sm2.objective_stamp(ctx, replace(p, smt_pick="first"), "ES", trades, out)
    assert trades[0].obj_met_t is None and out == []
    ctx.bias_row = dict(combo=1, draw_up=103.0, draw_dn=float("nan"))
    sm2.objective_stamp(ctx, p, "ES", trades, out)
    assert trades[0].obj_met_t == ctx.idx[k0 + 2] + pd.Timedelta(minutes=5) and out[0]["symbol"] == "ES"


def test_combine_laggard_objective_from_the_engine_tag():
    """ES met its own draw at 10:00 WITHOUT any ladder level of a trade being hit (final_hit False): its later fills go, NQ's stay. A leader trade that reached its last
    ladder rung but never met the draw does not count."""
    from test_caption_gap_sm1a import _row
    t10 = pd.Timestamp("2026-06-23 10:00", tz=NY)
    es = _obook([_row("ES", "09:40", "09:50", obj_met_t=t10), _row("ES", "13:40", "14:10", session="PM", obj_met_t=t10)])
    nq = _obook([_row("NQ", "13:45", "14:20", session="PM", obj_met_t=pd.NaT)])
    out = B.combine(es, nq, pick="laggard_objective").sort_values("entry_time")
    assert list(out.symbol) == ["ES", "NQ"]                                                      # ES's 13:40 fill (after its objective) is gone; the unmet NQ's stays
    es2 = _obook([_row("ES", "09:40", "09:50", final_hit=True, obj_met_t=pd.NaT), _row("ES", "13:40", "14:10", session="PM", obj_met_t=pd.NaT)])
    out = B.combine(es2, nq, pick="laggard_objective").sort_values("entry_time")
    assert list(out.symbol) == ["ES", "ES"]                                                      # a last-rung hit is not the objective: no filter
    # the met moment of an instrument WITHOUT any trade that day is read from the run's attrs
    es3 = _obook([_row("ES", "13:40", "14:10", session="PM")])
    nq3 = _obook([_row("NQ", "09:40", "09:50", session="AM"), _row("NQ", "13:35", "14:00", session="PM")])
    nq3.attrs["objective_met"] = {("2026-06-23", "NQ"): t10}
    out = B.combine(nq3, es3, pick="laggard_objective").sort_values("entry_time")
    assert list(out.symbol) == ["NQ", "ES"]
    es3 = _obook([_row("ES", "13:40", "14:10", session="PM")])


def test_run_day_reports_the_objective_per_instrument():
    d = D0
    hs = hist_close(d=d, close=5000.0, hi=5030.0, lo=4980.0)
    rows = [(5000.0, 5001.0, 4999.0, 5000.5), (5000.5, 5007.0, 5000.0, 5006.0), (5006.0, 5012.0, 5005.0, 5011.0)]
    df = day(rows, d=d, start="09:30", base=5000.0, w=0.0)
    p = Params(**{**BASE, **RUN_P, "smt_pick": "laggard_objective", "htf_bias": "combo"})
    obj = []
    run_day(df, hs, p, bias=dict(BIAS_UP, draw_up=5010.0), objective=obj)
    assert len(obj) == 1 and obj[0]["symbol"] == "ES" and obj[0]["draw"] == 5010.0 and obj[0]["t"] == pd.Timestamp(f"{d} 09:45", tz=NY)
    obj2 = []
    run_day(df, hs, replace(p, smt_pick="first"), bias=dict(BIAS_UP, draw_up=5010.0), objective=obj2)
    assert obj2 == []                                                                              # nothing is computed for the other picks
    # through backtest.run: attrs carry the moments, the trade rows carry obj_met_t
    out = B.run(B.synthetic(start="2026-04-06", end="2026-04-17", tf=5, seed=3)[0], 5, "RW", Params(**{**BASE, "smt_pick": "laggard_objective", "htf_bias": "combo",
                                                                                                    "ob_entry": "post_mss", "draw_lock": "off", "leg_pd": 0, "min_draw_pts": 0}))
    assert "obj_met_t" in out.columns or not len(out)
    assert isinstance(out.attrs.get("objective_met", {}), dict)


# --- B18-am-smt-window-points: the COMPARED extremes -----------------------------------------------------------------------------

def test_smt_ref_window_checks_the_compared_extreme():
    """A 02:00 low vs a 10:50 low counts only with the window 120 / 660: with smt_ref_window the swept level's own extreme time must lie inside [smt_win_a, smt_win_b]."""
    from test_levels_detectors import ctx_for
    bars = [(100.0, 100.4, 99.8, 100.2)] * 6
    ctx, (sl, ss) = mkctx(bars)
    # the lows of the day: put a 02:00 low (bar 24) of 98.0 and a 06:30 low (bar 78) of 97.5 into the overnight filler
    k2, k65 = ib(ctx, "02:00"), ib(ctx, "06:30")
    ctx.l[k2], ctx.l[k65] = 98.0, 96.0
    sl.l[k2], sl.l[k65] = 98.0, 96.0
    i = min(ib(ctx, "10:50"), len(ctx.t) - 1)
    p = Params(**BASE, smt_ref_window=True)
    assert sm2.smt_ref_ok(ctx, sl, i, "london", 96.0, p) is True                          # 06:30 is inside 05:00-09:30
    assert sm2.smt_ref_ok(ctx, sl, i, "london", 98.0, p) is False                         # 02:00 is outside the default window
    assert sm2.smt_ref_ok(ctx, sl, i, "london", 98.0, replace(p, smt_win_a=120, smt_win_b=660)) is True
    assert sm2.smt_ref_ok(ctx, sl, i, "pdl1", 80.0, replace(p, smt_win_a=0, smt_win_b=1440)) is False   # a level with no bar today (a prior day's pool)
    assert sm2.smt_ref_ok(ctx, sl, i, "open_0930", 100.0, p) is True and sm2.smt_ref_ok(ctx, sl, i, "open_0830", 100.0, replace(p, smt_win_a=520)) is False
    # wired in _smt: the switch cuts the comparison; without it the same call is unaffected by the window bounds
    ppos = pd.Series(np.arange(len(ctx.idx)), index=ctx.idx)
    ps = ctx.sides_map
    key, lv = "rel_eq_x", 98.0
    q = replace(p, smt_rel_eq=True)
    assert S._smt(ctx, sl, i, key, lv, "AM", ctx, ps, ppos, q) is None


# --- N5 release setups: the done flags, the continue / scalp decision, the projections --------------------------------------------

def _release_day():
    d = date(2024, 2, 9)
    hs = hist_close(d=d, close=5010.0, hi=5030.0, lo=4990.0)
    x0, x1, x2, x3 = ((5010.0, 5011.0, 5006.0, 5007.0), (5007.0, 5016.5, 5006.8, 5016.0), (5016.0, 5020.0, 5013.0, 5019.0), (5019.0, 5019.5, 5008.0, 5009.0))
    rows = [(5010.0, 5010.5, 5009.5, 5010.0)] * 2 + [x0, x1, x2, x3] + [(5009.0, 5021.0, 5008.5, 5020.5), (5020.5, 5022.0, 5019.0, 5021.0)]
    return day(rows, d=d, start="09:30", base=5010.0, w=0.0), hs


def test_release_ob_continues_only_with_support(monkeypatch):
    df, hs = _release_day()
    p = Params(**{**BASE, **RUN_P, "release_ob_entry": True})
    scalp = run_day(df, hs, p, conf=StubConf(), bias=BIAS_UP)
    assert len(scalp) == 1 and [e[3] for e in scalp[0].exits] == ["t1"] and "release_ob_continue" not in scalp[0].lv_tags            # no SMT / sick sister: the scalp
    from mentorship import setups as SM
    monkeypatch.setattr(SM, "sick_sister", lambda *a, **k: [(5040.0, "array")])
    cont = run_day(df, hs, p, conf=StubConf(), bias=BIAS_UP)
    assert len(cont) == 1 and "release_ob_continue" in cont[0].lv_tags and len(cont[0].exits) >= 1       # the draw (5060) joins the nearest swing as a second exit


def test_release_setups_respect_the_done_flags_and_the_day_stop(monkeypatch):
    p = Params(**{**BASE, **RUN_P, "release_ob_entry": True})
    boom = RuntimeError("reached the release OB")

    def fire(*a, **k):
        raise boom

    monkeypatch.setattr(sm2, "release_ob_order", fire)
    mk, (sl, ss) = mkctx([(5010.0, 5010.5, 5009.5, 5010.0)] * 8, base=5010.0, hist=hist_close(d=date(2024, 2, 9), close=5010.0), d=date(2024, 2, 9), w=0.0)
    i = ib(mk, "09:55")
    with pytest.raises(RuntimeError):
        sm2.release_setups(mk, (sl, ss), i, p, {}, None, None, 1.0, {})                                   # the 10:00 release fires
    assert sm2.release_setups(mk, (sl, ss), i, p, {}, None, None, 1.0, {"AM": True}) is None             # an AM trade was taken already
    assert sm2.release_setups(mk, (sl, ss), i, p, {"day_done": True}, None, None, 1.0, {}) is None        # the day stop
    assert sm2.release_setups(mk, (sl, ss), i, p, {}, None, "pending", 1.0, {}) is None


def test_release_support_reads_the_sick_sister_and_the_smt(monkeypatch):
    from mentorship import setups as SM
    mk, (sl, ss) = mkctx([(5010.0, 5010.5, 5000.0, 5001.0)] * 8, base=5010.0, hist=hist_close(d=D0, close=5010.0, hi=5030.0, lo=5002.0), w=0.0)
    p = Params(**BASE)
    i = ib(mk, "09:55")
    mk.pside = (SimpleNamespace(), {}, None)
    monkeypatch.setattr(SM, "sick_sister", lambda *a, **k: None)
    monkeypatch.setattr(S, "_smt", lambda *a, **k: False)
    assert sm2.release_support(mk, sl, i, p, 5001.0) is False
    monkeypatch.setattr(S, "_smt", lambda *a, **k: True)
    assert sm2.release_support(mk, sl, i, p, 5001.0) is True                                              # the day low went through a pool and the partner did not
    mk.pside = None
    assert sm2.release_support(mk, sl, i, p, 5001.0) is False
    monkeypatch.setattr(SM, "sick_sister", lambda *a, **k: [(5040.0, "array")])
    assert sm2.release_support(mk, sl, i, p, 5001.0) is True


# --- DS2: validity over the whole leg, the measured move, the catalyst, the AM variants -----------------------------------------

def _pm_day(d=D0, conf=None, bias=0):
    rows = [(100.0 + 0.2 * k, 100.3 + 0.2 * k, 99.9 + 0.2 * k, 100.2 + 0.2 * k) for k in range(30)] + [(105.9, 106.0, 105.0, 105.5)] * 18 + [(105.5, 105.8, 105.2, 105.4)] * 6
    return mkctx(rows, base=100.0, hist=hist_close(d=d, close=100.0, hi=108.0, lo=90.0), bias=bias, conf=conf, d=d, w=0.0)


def test_two_session_validity_is_the_whole_leg_and_has_a_measured_move():
    p = Params(**BASE, profile_two_session=True)
    i = ib(_pm_day()[0], "13:40")
    ctx, (sl, ss) = _pm_day(conf=StubConf({-1: [(102.5, 102.0, "4h", 0, 0.0)]}), bias=1)             # a bearish 4h array the AM rally traded INTO on the way up
    assert sm2.pm_profile_gate(ctx, sl, dict(key="lunch"), i, p, "PM", 105.4, []) is None             # the profile no longer holds (no two_session tag, the other profiles apply)
    lvt = []
    ctx, (sl, ss) = _pm_day(conf=StubConf({-1: [(112.0, 110.0, "4h", 0, 0.0)]}), bias=1)             # one ABOVE the AM high, never reached
    assert sm2.pm_profile_gate(ctx, sl, dict(key="lunch"), i, p, "PM", 105.4, lvt) is None and lvt == ["two_session_up"]
    leg = float(ctx.h[ib(ctx, "09:30"):ib(ctx, "13:30")].max() - ctx.l[ib(ctx, "09:30"):ib(ctx, "13:30")].min())
    assert (105.4 + leg, "array") in sm2.pm_extra_targets(ctx, sl, i, p, "PM", 105.4)                 # PM leg ~= AM leg, from the entry
    assert sm2.pm_extra_targets(ctx, ss, i, p, "PM", -105.4) == []


def test_two_session_catalyst_drops_the_lunch_trigger():
    p = Params(**BASE, profile_two_session=True, two_session_catalyst=True)
    ctx, (sl, ss) = _pm_day(d=JOBS, bias=1)                                                          # an NFP day (a release in the day)
    i = ib(ctx, "13:40")
    lvt = []
    assert sm2.pm_profile_gate(ctx, sl, dict(key="other"), i, p, "PM", 105.8, lvt) is None and "two_session_catalyst" in lvt           # no lunch sweep / discount tap asked for
    assert sm2.pm_profile_gate(ctx, sl, dict(key="other"), i, replace(p, two_session_catalyst=False), "PM", 105.8, []) == "x_two_session_trigger"


def test_two_session_am_and_consol_am():
    # two_session_am: bias up, nothing opposing reached -> AM longs only, at a same-side 1h+ array
    p = Params(**BASE, two_session_am=True)
    ctx, (sl, ss) = mkctx([(100.0, 100.5, 99.5, 100.2)] * 6, bias=1, conf=StubConf(at_tfs={1: ["1h"]}))
    i = ib(ctx, "09:50")
    lvt = []
    assert sm2.pm_profile_gate(ctx, sl, dict(key="x"), i, p, "AM", 100.0, lvt) is None and lvt == ["two_session_am_up"]
    assert sm2.pm_profile_gate(ctx, ss, dict(key="x"), i, p, "AM", -100.0, []) == "x_two_session_am_counter"
    ctx.conf = StubConf()
    assert sm2.pm_profile_gate(ctx, sl, dict(key="x"), i, p, "AM", 100.0, []) == "x_two_session_am_array"      # not at a discount array
    ctx.conf = StubConf({-1: [(100.2, 99.9, "4h", 0, 0.0)]}, at_tfs={1: ["1h"]})
    assert sm2.pm_profile_gate(ctx, ss, dict(key="x"), i, p, "AM", -100.0, []) is None                         # an opposing 4h array was traded into: the profile has ended
    # profile_consol_am: neutral bias, no release from 10:00 - at an array, or from the opening-range EQ's expansion side
    q = Params(**BASE, profile_consol_am=True)
    ctx, (sl, ss) = mkctx([(100.0, 100.5, 99.5, 100.2)] * 12, bias=0, conf=StubConf(at_tfs={1: ["1h"], -1: ["1h"]}))
    j = ib(ctx, "10:20")
    lvt = []
    assert sm2.pm_profile_gate(ctx, sl, dict(key="x"), j, q, "AM", 100.0, lvt) is None and lvt == ["consol_am_up"]
    ctx.conf = StubConf()
    ctx.or_hl = None
    assert sm2.pm_profile_gate(ctx, sl, dict(key="x"), j, q, "AM", 100.0, []) == "x_consol_am"                  # neither an array nor an opening range yet
    ctx.or_hl = (101.0, 99.0)
    ctx.or_end = 600
    assert sm2.pm_profile_gate(ctx, sl, dict(key="x"), j, q, "AM", 100.2, []) is None                           # above the OR EQ (100.0)
    assert sm2.pm_profile_gate(ctx, sl, dict(key="x"), j, q, "AM", 99.0, []) == "x_consol_am"                   # below it
    assert sm2.pm_profile_gate(ctx, sl, dict(key="x"), j, replace(q, profile_consol_am=False), "AM", 99.0, []) is None
    tg = sm2.pm_extra_targets(ctx, sl, j, q, "AM", 99.0)
    assert tg and all(k == "pool" for _, k in tg)


# --- A13: no return into the rebalanced range, accumulation, the late retest at run_day level ---------------------------------------

def _brk(rows, mirror=False, **kw):
    rr = [(200.0 - o, 200.0 - l, 200.0 - h, 200.0 - c) for o, h, l, c in rows] if mirror else rows
    ctx, (sl, ss) = mkctx(rr, base=100.0, hist=history(hi=112.0, lo=88.0))
    k0 = ib(ctx, "09:30")
    sd = ss if mirror else sl
    sw = dict(session="AM", ext=-102.0 if mirror else 98.0, ext_i=k0 + 5, broke=k0 + 7, name="x", key="pdl1", level=-101.5 if mirror else 98.5, smt=None)
    p = replace(Params(**B_POST), breaker_ll=False, breaker_mt_respect=False, breaker_needs_disp=True, **kw)
    return ctx, sd, sw, k0, p


@pytest.mark.parametrize("mirror", [False, True])
def test_breaker_needs_disp_ends_when_price_returns_through_the_rebalanced_range(mirror):
    """The displacement FVG 100.0-101.3 of the break leg confirms the breaker; a CLOSE back under its bottom (above its top for a short) undoes the repricing."""
    stay = B_ROWS + [(102.3, 102.4, 101.5, 102.0), (102.0, 102.2, 101.0, 101.5)]
    back = B_ROWS + [(102.3, 102.4, 101.5, 102.0), (102.0, 102.1, 99.0, 99.5)]
    ctx, sd, sw, k0, p = _brk(stay, mirror)
    assert S._breaker(ctx, sd, sw, k0 + 3, True, k0 + 10, p) is not None
    ctx, sd, sw, k0, p = _brk(back, mirror)
    assert S._breaker(ctx, sd, sw, k0 + 3, True, k0 + 9, p) is not None                           # not yet back
    assert S._breaker(ctx, sd, sw, k0 + 3, True, k0 + 10, p) is None                              # the close at 99.5 is through the gap: no confirmation
    assert S._breaker(ctx, sd, dict(sw), k0 + 3, True, k0 + 10, replace(p, breaker_needs_disp=False)) is not None


def test_breaker_accumulate_inside_without_a_retest(monkeypatch):
    rows = list(B_ROWS) + [(102.3, 102.6, 101.5, 102.0)] * 3 + [(102.0, 102.1, 100.5, 100.8)]            # 10:15: a close INSIDE the zone (100.1-101.0), never left and retested
    ctx, (sl, ss) = mkctx(rows, base=100.0, hist=history(hi=112.0, lo=88.0))
    k0 = ib(ctx, "09:30")
    p = replace(Params(**B_POST), breaker_day_life=True, breaker_accumulate=True)
    sw = dict(session="AM", ext=98.0, ext_i=k0 + 5, broke=k0 + 7, name="x", key="pdl1", level=98.5, smt=None)
    assert S._breaker(ctx, sl, sw, k0 + 3, True, k0 + 8, p) is not None
    got = []
    monkeypatch.setattr(S, "_breaker_order", lambda ctx_, sd_, sw_, bz_, i_, p_, session, risk_mult: got.append((i_, bz_.top, bz_.bottom)) or "order")
    j = k0 + 12
    assert sm2.breaker_retest_order(ctx, sl, j - 1, replace(p, breaker_accumulate=False), "AM", 1.0) is None       # as before: only a retest after leaving arms
    assert sm2.breaker_retest_order(ctx, sl, j, p, "AM", 1.0) == "order"
    assert got == [(j, pytest.approx((101.0 + 100.1) / 2), 100.1)]                                                # a limit at the zone's CE
    assert sm2.breaker_retest_order(ctx, sl, j, p, "AM", 1.0) is None                                              # once per breaker


def test_breaker_late_retest_arms_in_the_pm_last_hour_at_run_day_level():
    """An AM breaker (scenario B) that price never came back to in the morning and that is retested at 15:05 / left at 15:10 arms a PM-last-hour order through run_day
    (breaker_day_life): a limit at the zone top, armed once no sweep is active (15:20) and filled at 15:25; without the switch there is no trade at all."""
    hs = history(hi=112.0, lo=88.0)
    rows = list(B_ROWS) + [(102.3, 102.6, 101.5, 102.3)] * 58                                            # flat above the zone to 15:00
    rows += [(102.0, 102.1, 100.5, 100.8), (100.8, 101.8, 100.7, 101.6), (101.6, 102.0, 101.5, 101.9), (101.9, 104.0, 101.8, 103.5), (103.5, 103.6, 100.9, 101.2)]      # 15:05 dip into the zone, 15:10 back out, 15:20 armed, 15:25 retest
    df = day(rows)
    p = Params(**{**B_POST, "breaker_ll": False, "adds": (0.5,)})
    sm2.HITS.clear()
    on = run_day(df, hs, replace(p, breaker_day_life=True))
    assert sm2.HITS.get("breaker_register") and sm2.HITS.get("breaker_retest")
    assert run_day(df, hs, p) == []
    assert len(on) == 1 and on[0].entry_kind == "breaker" and on[0].entry == 101.0 and on[0].entry_time == pd.Timestamp(f"{D0} 15:25", tz=NY)


# --- A15: the pre-open block, untapped daily levels ---------------------------------------------------------------------------

def _preopen_rows():
    pre = [(100.0, 100.4, 99.8, 100.3), (100.3, 100.5, 100.0, 100.1), (100.1, 100.6, 99.9, 100.5), (100.5, 100.6, 100.1, 100.2), (100.2, 100.6, 100.0, 100.4), (100.4, 100.6, 100.2, 100.5)]
    return pre + [(100.5, 103.0, 100.4, 102.8), (102.8, 104.0, 102.6, 103.9), (103.9, 104.0, 100.6, 100.9), (100.9, 101.0, 100.5, 100.7)]


def test_preopen_block():
    rows = _preopen_rows()
    ctx, (sl, ss) = mkctx(rows, base=100.0, start="09:00", hist=hist_close(close=100.0, hi=110.0, lo=90.0), w=0.0)
    p = Params(**BASE, mitigation_entry=True, mit_preopen=True)
    j = ib(ctx, "09:55")
    z = sm2.preopen_block(ctx, sl, j, p)
    assert z is not None and z.kind == "bull" and z.top == 100.6 and z.bottom == 99.8 and z.i == ib(ctx, "09:30") - 1       # the up-close candles' full range, known at 09:30
    assert sm2.preopen_block(ctx, sl, ib(ctx, "09:20"), p) is None                                                       # not before the window has closed
    wide = [(100.0, 105.0, 95.0, 104.0)] * 6 + rows[6:]
    ctx2, (sl2, _) = mkctx(wide, base=100.0, start="09:00", hist=hist_close(close=100.0, hi=110.0, lo=90.0), w=0.0)
    assert sm2.preopen_block(ctx2, sl2, j, p) is None                                                                     # not a consolidation


def test_daily_beyond_skips_levels_already_traded():
    ctx, (sl, ss) = mkctx([(100.0, 102.0, 99.5, 101.0)] * 6, base=100.0, w=0.0)
    ctx.pd = {"pdh1": 101.5, "pdh2": 105.0}
    i = ib(ctx, "09:50")
    p = Params(**BASE)
    assert sm2.daily_beyond(ctx, sl, i, p, 100.5) == 105.0                                                                  # pdh1 (101.5) was traded today (high 102): not a draw
    ctx.pd = {"pdh1": 103.0}
    assert sm2.daily_beyond(ctx, sl, i, p, 100.5) == 103.0


# --- BH-compressed-higher-highs: the leg low is the FIRST target ------------------------------------------------------------------

def test_compressed_first_drops_the_nearer_targets(monkeypatch):
    p = Params(**BASE, compressed_hh=True)
    lv = [(101.0, "pool"), (102.0, "array"), (104.0, "pool")]
    monkeypatch.setattr(sm2, "compressed_leg_low", lambda *a, **k: 103.0)
    out = sm2.compressed_first(None, None, None, 0, p, 100.0, lv)
    assert out == [(103.0, "pool"), (104.0, "pool")]
    monkeypatch.setattr(sm2, "compressed_leg_low", lambda *a, **k: None)
    assert sm2.compressed_first(None, None, None, 0, p, 100.0, lv) == lv
    monkeypatch.setattr(sm2, "compressed_leg_low", lambda *a, **k: 99.0)
    assert sm2.compressed_first(None, None, None, 0, p, 100.0, lv) == lv                                                    # not above the entry


# --- study variants of the review-fix switches ----------------------------------------------------------------------------------

def test_review_fix_switches_have_study_variants():
    new = ("smt_ref_window", "breaker_accumulate", "mit_preopen", "judas_depth_tag", "two_session_am", "two_session_catalyst", "profile_consol_am")
    on = set()
    for v, kw in study.DECISIONS.items():
        on |= set(kw)
    assert set(new) <= on and set(new) <= set(Params.__dataclass_fields__)
    assert all(not getattr(Params(), s) for s in new)                                                                        # all off by default
    for v in ("DS2-two-session-close-templates_am", "DS2-consolidation-profiles_am", "A13-breaker-lifetime_accumulate", "A15-mitigation-block-entry_preopen",
              "B12-judas-depth-adr_tag"):
        Params(**study.DECISIONS[v])


# --- identity: every new switch at its default leaves the trades as they were before the package -------------------------------------

GOLDEN_COLS = ["date", "session", "setup", "side", "entry_time", "entry", "stop", "t1", "t2", "shares", "exit_time", "exit_reason", "gross", "lv_tags", "entry_kind"]
# digests of the trades of the tree BEFORE this package (commit 0067553) on the synthetic windows below, one per (seed, configuration): `digest` of B.run(...)
GOLDEN = {
    (3, "post_mss"): "58e73338d477:2", (3, "both"): "10428f7d3c8a:11", (3, "plain"): "0d690fc834b8:10", (3, "pm"): "f9f61e772729:1",
    (5, "post_mss"): "e0a2b91b1fdc:3", (5, "both"): "23aa0e7222b8:11", (5, "plain"): "cb76682b13f0:12", (5, "pm"): "558d3d780ed6:1",
}
GOLDEN_CFG = {
    "post_mss": dict(use_bias=True, bias_open="0930", ob_entry="post_mss", draw_lock="off"),
    "both": dict(use_bias=True, bias_open="0930", ob_entry="both", draw_lock_neutral="both"),
    "plain": dict(ob_entry="both"),
    "pm": dict(use_bias=True, bias_open="0930", ob_entry="both", draw_lock_neutral="both", pm_reversal=True, lunch=True, extra_pools=True, sick_sister=True),
}


def digest(t) -> str:
    import hashlib
    if not len(t):
        return "empty"
    t = t.sort_values(["entry_time", "setup"], kind="stable")
    s = ["|".join(f"{v:.4f}" if isinstance(v, float) else str(v) for v in r) for r in t[GOLDEN_COLS].itertuples(index=False)]
    return hashlib.sha1("\n".join(s).encode()).hexdigest()[:12] + f":{len(t)}"


@pytest.mark.parametrize("seed", [3, 5])
def test_default_switches_leave_the_trades_unchanged(seed):
    """With every new switch at its default the trades equal those of the tree before this package (digests taken at commit 0067553 with the same function)."""
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    syn = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0, min_draw_pts=0, htf_resist_cap=False)
    for name, kw in GOLDEN_CFG.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t = B.run(x, 5, "RW", Params(**{**syn, **kw}), partner=y)
        assert digest(t) == GOLDEN[(seed, name)], (seed, name)


# --- no look-ahead, executed paths: full run vs runs truncated at every entry / exit, on real ES days and synthetic days with a partner --------
# Every case names the sm2.HITS counters (the functions that carry its switches) that must have RUN in the full run, and the run must have trades: a switch that never
# ran, or a window without a trade, fails the case instead of passing vacuously. The windows hold an NFP Friday (2024-03-08, case "news_nfp"), 10:00 release days
# (case "release_ob": 2024-07-08 .. 07-29) and the long-history pieces; they were chosen by scanning the 2023-10 .. 2024-09 months.

ES_BASE = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, ob_entry="post_mss", leg_pd=0, min_draw_pts=0, htf_resist_cap=False, draw_lock="off", htf_bias="combo")
W_A, W_B, W_C, W_D, W_E, W_F = (("2023-10-02", "2023-10-23"), ("2023-11-27", "2023-12-18"), ("2024-02-19", "2024-03-11"), ("2024-05-13", "2024-06-03"),
                                ("2024-07-08", "2024-07-29"), ("2024-01-01", "2024-01-08"))
ES_CASES = {
    "gates": (W_A, dict(open_tol_pts=3.0, po3_seq="tag", wk_open_side=True, ifvg_narrative="block", gap_premium_arm=True, compressed_hh=True, pool_runs_max=3,
                        mature_flag_block=True, touch_tag=True, judas_depth_tag=True, lod_zone_first=True, smt_open_points=True),
              ("sunday_open", "touch_count", "judas_depth", "po3_seq", "ifvg_narrative", "gap_premium", "open_tol", "lod_zone", "compressed", "pool_runs",
               "mature_flag", "compressed_first", "open_pools")),
    "ifvg_require": (W_C, dict(ifvg_narrative="require", po3_seq="filter"), ("ifvg_narrative", "po3_seq")),
    "arrays": (W_A, dict(breaker_needs_disp=True, breaker_break_ref="body_high", breaker_by_close=True, breaker_day_life=True, breaker_keep_original=True, breaker_accumulate=True,
                         mitigation_entry=True, mit_needs_bias=True, mit_preopen=True),
               ("breaker_by_close", "breaker_disp", "breaker_body_high", "breaker_register", "breaker_retest", "mit_order", "mit_preopen")),
    "lc": (W_A, dict(lc_tag=True, lc_reentry=True, am=(570, 720)), ("lc_reopen",)),
    "profiles": (W_A, dict(two_session_am=True, pm_reversal=True, pm_reversal_pool="lunch_or_am", pm_reversal_ltf_only=True), ("two_session_am", "pm_reversal_lunch", "pm_reversal_ltf")),
    "two_session": (W_D, dict(profile_two_session=True, two_session_catalyst=True, extra_pools=True), ("two_session",)),
    "consol_pm": (("2023-12-25", "2024-01-15"), dict(profile_consol_pm=True, htf_bias="off"), ("consol_pm",)),
    "consol_am": (W_E, dict(profile_consol_am=True, htf_bias="off"), ("consol_am",)),
    "stoprun": (W_A, dict(mss_requires_htf_agreement=True, stoprun_rearm=True), ("stoprun_rearm",)),
    "far_edge": (W_D, dict(far_edge_trap=True), ("far_edge",)),
    "sibi": (W_D, dict(htf_sibi_short_zone=True, htf_sibi_need_smt=True), ("htf_sibi",)),
    "news_nfp": (W_C, dict(nfp_release_fvg=True, post_news_continuation=True), ("nfp_release_fvg", "post_news")),
    "release_ob": (W_E, dict(release_ob_entry=True), ("release_ob",)),
    "post_news": (W_F, dict(post_news_continuation=True), ("post_news",)),
}
_ES = {}


def _es_slice(a, b):
    if "raw" not in _ES:
        _ES["raw"] = B.load("ES", 5, source="databento")
        _ES["meta"] = B.load_meta("ES", 5)
    raw = _ES["raw"]
    return raw[(raw.index >= pd.Timestamp(a, tz=NY)) & (raw.index < pd.Timestamp(b, tz=NY))], _ES["meta"]


TAG_COLS = ["lv_tags", "open_grade", "po3_seq", "wk_open_side", "touch_n", "judas_depth", "array_depth", "clean_swing", "lc_reversal", "setup", "side"]
EX_COLS = ["entry_time", "exit_time", "exit_reason"]


def _check_la(full, added, need, name):
    assert len(full) >= 1, f"{name}: the window made no trade"
    missing = [h for h in need if not added.get(h)]
    assert not missing, f"{name}: these paths did not run: {missing} (ran: {sorted(added)})"


def _truncated(df, tf, sym, p, full, cols, every=1, meta=None, lag=2, max_cuts=5, **kw):
    """Cut at entry AND exit times (the cut bar + lag): the entries up to a cut and the exits of the trades closed by it match the full run. At most `max_cuts`
    cuts, spread over the run (the first and the last included)."""
    cuts = sorted(set(full.entry_time.iloc[::every]) | set(full.exit_time.dropna().iloc[::every]))
    if len(cuts) > max_cuts:
        cuts = [cuts[round(k * (len(cuts) - 1) / (max_cuts - 1))] for k in range(max_cuts)]
    for cut_t in cuts:
        c = cut_t + pd.Timedelta(minutes=lag)
        pk = {k: (v[v.index <= c] if isinstance(v, pd.DataFrame) else v) for k, v in kw.items()}
        part = B.run(df[df.index <= c], tf, sym, p, partial_last=True, meta=meta, **pk)
        a = full[full.entry_time <= cut_t][cols].reset_index(drop=True)
        b = part[part.entry_time <= cut_t][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False)
        done = full.exit_time.notna() & (full.exit_time <= cut_t)
        a = full[done][EX_COLS].reset_index(drop=True)
        b = part[part.entry_time.isin(full[done].entry_time)][EX_COLS].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es_executed_paths(case):
    (a, b), kw, need = ES_CASES[case]
    df, meta = _es_slice(a, b)
    p = Params(**{**ES_BASE, **kw})
    h0 = dict(sm2.HITS)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(df, 5, "ES", p, meta=meta)
        added = {k: v - h0.get(k, 0) for k, v in sm2.HITS.items() if v - h0.get(k, 0)}
        _check_la(full, added, need, case)
        _truncated(df, 5, "ES", p, full, ENTRY + TAG_COLS, meta=meta)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_laggard_objective():
    """smt_pick "laggard_objective": the engine tags every trade of the day with the moment its own draw was met. A truncated run must show the same entries; its tag
    equals the full run's wherever the full run's moment is not after the cut (a later moment is unknown at the cut), and attrs carry the days' moments."""
    (a, b) = W_A
    df, meta = _es_slice(a, b)
    p = Params(**{**ES_BASE, "smt_pick": "laggard_objective"})
    h0 = dict(sm2.HITS)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(df, 5, "ES", p, meta=meta)
    _check_la(full, {k: v - h0.get(k, 0) for k, v in sm2.HITS.items() if v - h0.get(k, 0)}, ("objective_met",), "objective")
    assert "obj_met_t" in full.columns and full.attrs.get("objective_met")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _truncated(df, 5, "ES", p, full, ENTRY + TAG_COLS, meta=meta)
        for cut_t in sorted(set(full.entry_time.iloc[::2])):
            c = cut_t + pd.Timedelta(minutes=2)
            part = B.run(df[df.index <= c], 5, "ES", p, partial_last=True, meta=meta)
            for _, r in full[full.entry_time <= cut_t].iterrows():
                q = part[part.entry_time == r.entry_time].iloc[0]
                if pd.notna(r.obj_met_t) and r.obj_met_t <= cut_t:
                    assert q.obj_met_t == r.obj_met_t                      # a moment already past at the cut is the same in the cut run
                elif pd.notna(q.obj_met_t):
                    assert q.obj_met_t <= c                                  # whatever a cut run knows lies at or before its last bar


SYN_S = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0, min_draw_pts=0, htf_resist_cap=False)
SYN_CASES = {
    "smt": (3, dict(smt_pre=True, smt_windows=((570, 660),), smt_win_a=120, smt_win_b=660, smt_ref_window=True, smt_min=0, news_profile="pool_test"),
            ("smt_ref_window", "news_pool_test")),
    "smt_pm": (3, dict(smt_pm_points=True, smt_min=0), ("pm_points",)),
    "lc_syn": (5, dict(lc_tag=True, lc_reentry=True, am=(570, 720)), ("lc_retry",)),
    "judas_news": (4, dict(judas_news_tag=True, require_judas=True, judas_window=600), ("judas_news",)),
    "profiles_syn": (3, dict(profile_two_session=True, two_session_am=True, pm_reversal=True, pm_reversal_pool="lunch_or_am", pm_reversal_ltf_only=True),
                     ("two_session", "pm_reversal_lunch")),
    "obj_syn": (5, dict(smt_pick="laggard_objective"), ("objective_met",)),
    "arrays_syn": (4, dict(breaker_day_life=True, breaker_accumulate=True, mitigation_entry=True, mit_preopen=True, lod_zone_first=True), ("breaker_accumulate", "mit_order")),
}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic_executed_paths(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN_S, **SYN_BASE, **kw})
    h0 = dict(sm2.HITS)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(x, 5, "RW", p, partner=y)
        added = {k: v - h0.get(k, 0) for k, v in sm2.HITS.items() if v - h0.get(k, 0)}
        _check_la(full, added, need, case)
        _truncated(x, 5, "RW", p, full, ENTRY + TAG_COLS, partner=y)


# --- A19 in the main loop: the break of the side AGAINST the bias --------------------------------------------------------------

def test_against_bias_break_arms_the_bias_side():
    """Bias up: the short Side is never scanned, so its break (a close under the newest swing low 99.0) is looked for in the main loop; with stoprun_rearm it arms the
    long Side's sweep once (level 99.0, extreme = the lowest low since that swing formed); without the switch nothing happens."""
    rows = [(100.0, 100.6, 99.4, 100.4), (100.4, 100.8, 99.0, 99.2), (99.2, 100.4, 99.1, 100.2), (100.2, 100.3, 98.0, 98.2), (98.2, 98.6, 97.5, 97.8)]
    ctx, (sl, ss) = mkctx(rows, base=100.0, w=0.0)
    k0 = ib(ctx, "09:30")
    p = Params(**BASE, mss_requires_htf_agreement=True, stoprun_rearm=True)
    sm2.against_bias_break(ctx, ss, k0 + 2, p, "AM", 1)
    assert sl.sweep is None                                                    # no close under 99.0 yet
    sm2.against_bias_break(ctx, ss, k0 + 3, p, "AM", 1)
    assert sl.sweep is not None and sl.sweep["key"] == "stoprun" and sl.sweep["level"] == 99.0 and sl.sweep["ext"] == 98.0
    first = sl.sweep
    sl.sweep = None
    sm2.against_bias_break(ctx, ss, k0 + 3, p, "AM", 1)
    assert sl.sweep is None and first["ext_i"] == k0 + 3                       # armed once per swing
    ctx2, (sl2, ss2) = mkctx(rows, base=100.0, w=0.0)
    sm2.against_bias_break(ctx2, ss2, k0 + 4, replace(p, stoprun_rearm=False), "AM", 1)
    assert sl2.sweep is None


def test_every_switch_of_the_chunk_has_an_executed_path_case():
    """Every behaviour switch of the chunk is on in an executed-path no-look-ahead case of this file, in the synthetic groups of test_caption_gap_sm1b, or is listed here
    with the reason it cannot be reached by data."""
    from test_caption_gap_sm1a import NEW_SWITCHES as NEW_A
    from test_caption_gap_sm1b import NEW_B, GROUPS
    cover = set()
    for _, kw, _ in list(ES_CASES.values()):
        cover |= set(kw)
    for _, kw, _ in SYN_CASES.values():
        cover |= set(kw)
    for kw in GROUPS.values():
        cover |= set(kw)
    tuning = {"po3_seq_below_pts", "compressed_k", "compressed_n", "mature_pd", "nfp_release_fvg_min", "nfp_release_fvg_add", "post_news_run_pts", "judas_news_min",
              "breaker_disp_bars", "mit_entry_px", "laggard_consol_only", "markets", "smt_win_a", "smt_win_b", "judas_max_adr"}
    # no data window reaches these with a trade (their gates are unit-tested): smt_with_bias needs an SMT-qualified sweep on a day without bias; X5 judas_max_adr / the
    # D15 picks other than laggard_objective are combine-level (test_caption_gap_sm1a); require_judas_news is the rare-window study variant
    by_hand = {"smt_with_bias", "require_judas_news", "mit_needs_bias", "mitigation_entry"}
    missing = [s_ for s_ in NEW_A + NEW_B + ("smt_ref_window", "breaker_accumulate", "mit_preopen", "judas_depth_tag", "two_session_am", "two_session_catalyst",
                                             "profile_consol_am") if s_ not in cover and s_ not in tuning and s_ not in by_hand]
    assert not missing, missing
    assert {"mitigation_entry", "mit_needs_bias"} <= cover
