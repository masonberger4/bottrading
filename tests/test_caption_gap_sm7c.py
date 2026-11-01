"""Caption-gap pass, package setups_models #7/7, review-fix tests (part C): the findings of the chunk-7 review - missed_5m target / kill zone / London lunch / runner, YM and the two-market cap in the dual
combine, the breaker add size, the sibi_return trigger on its own, the bias gate of the special setups, re-entry order kinds and armed flags, the propulsion-MT reversal, the London-close stop / exit, the
OR / AM array invalidation, the PM nesting edge, the state tag. Hand-made 5-minute days (see test_caption_gap_sm7a.py); nothing needs market data. The reversal-day premium FVG test and the five-minute rung
weights are in test_caption_gap_sm7a.py (test_m0950_branches, test_adv_breaker_rungs)."""
from types import SimpleNamespace

import pandas as pd
import pytest

from mentorship import backtest as B, levels as L, sm4, sm7, strategy as S
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_levels_detectors import BASE, D0, NY, history
from test_caption_gap_sm1a import sd_of
from test_caption_gap_sm5a import _dual_book
from test_caption_gap_sm4a import cap  # noqa: F401  (cap: the order recorder fixture)
from test_caption_gap_sm7a import (Conf7, _am_rally_over, _missed_over, _orref_over, am_trade, bar, fake_pos, fake_tr, mk7, st0, sweep_dict)


# --- E5 missed_5m: the 60m / 4h array target, the kill zone, the London lunch, the runner -----------------------------------------------------------------

def _missed(p, over=None, conf=None, sess="AM", sweep_at="09:30", broke_at="09:45", at="10:05"):
    ctx, (sl, ss) = mk7(over or _missed_over(), p, conf=conf)
    sw = sweep_dict(ctx, sl, sweep_at, 98.0, key="pdl1", broke=bar(ctx, broke_at), session=sess)
    sm7.note_sweep(ctx, sl, sw, 101.0, bar(ctx, broke_at))
    return ctx, sl, bar(ctx, at)


def test_missed_target_is_the_nearer_of_adr5_and_the_first_60m_array(cap):
    """E5 (review fix): the target is the nearer of the ADR5 extreme (98 + 18 = 116) and the first 1h / 4h OPPOSING array above the entry from the Confluence object; no runner then."""
    p = Params(**BASE, missed_5m=True)
    ctx, sl, i = _missed(p, conf=Conf7({}, opp={1: [(103.0, 103.5, 104.0, "1h", 0)]}))
    assert sm7.missed_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["fixed"] == [(pytest.approx(S._exit_px(103.0, "pool", p)), "pool")] and "fracs" not in cap["tags"] and "sm7" not in cap["tags"]
    # an array farther than the ADR5 extreme (or only a D one) leaves the ADR5 target with its 80 / 20 split and the runner rule
    ctx2, sl2, i2 = _missed(p, conf=Conf7({}, opp={1: [(120.0, 121.0, 122.0, "4h", 0), (103.0, 103.5, 104.0, "D", 0)]}))
    sm7.missed_order(ctx2, sl2, i2, p, "AM", 1.0)
    assert cap["fixed"][0][0] == pytest.approx(S._exit_px(116.0, "pool", p)) and len(cap["fixed"]) == 2
    assert cap["tags"]["fracs"] == (0.8, 0.2) and cap["tags"]["sm7"] == dict(runner_before=600)
    ctx3, sl3, i3 = _missed(p)                                    # no Confluence object: a base-timeframe opposing FVG is NOT an HTF array
    sm7.missed_order(ctx3, sl3, i3, p, "AM", 1.0)
    assert cap["fixed"][0][0] == pytest.approx(S._exit_px(116.0, "pool", p))


def test_missed_only_inside_a_kill_zone(cap):
    """E5 (review fix): the order exists only inside the NY kill zone (missed_kz, default 08:20-11:00): the same setup judged at 12:30, or with another zone configured, is no order."""
    p = Params(**BASE, missed_5m=True)
    ctx, sl, i = _missed(p, at="12:30")
    assert sm7.missed_order(ctx, sl, i, p, "AM", 1.0) is None
    p2 = Params(**BASE, missed_5m=True, missed_kz=((700, 800),))
    ctx2, sl2, i2 = _missed(p2)
    assert sm7.missed_order(ctx2, sl2, i2, p2, "AM", 1.0) is None
    ctx3, sl3, i3 = _missed(p)
    assert sm7.missed_order(ctx3, sl3, i3, p, "AM", 1.0) is not None


def _london_over(quiet_early=True):
    """The missed-entry day moved to 05:15-05:50 (a London-lunch order), with a wide 03:45 bar (the active second London half) when `quiet_early`, else a wide 02:15 bar."""
    over = {k - 255: v for k, v in _missed_over().items()}
    over[225 if quiet_early else 135] = (100.0, 104.0, 96.0, 100.0)
    return over


def test_missed_london_lunch_variant(cap):
    """E5 (cc09_006 ~00:17:03): with missed_lon the London lunch 05:00-07:00 qualifies when London was quiet early (02:00-03:30) and active late (03:30-05:00); off, or an early-active London, no order."""
    kw = dict(sess="LON", sweep_at="05:15", broke_at="05:30", at="05:50")
    p = Params(**BASE, missed_5m=True, missed_lon=True)
    ctx, sl, i = _missed(p, over=_london_over(), **kw)
    assert sm7.missed_order(ctx, sl, i, p, "LON", 1.0) is not None and cap["tags"]["entry_kind"] == "missed_5m"
    p_off = Params(**BASE, missed_5m=True)
    ctx2, sl2, i2 = _missed(p_off, over=_london_over(), **kw)
    assert sm7.missed_order(ctx2, sl2, i2, p_off, "LON", 1.0) is None
    ctx3, sl3, i3 = _missed(p, over=_london_over(False), **kw)
    assert sm7.missed_order(ctx3, sl3, i3, p, "LON", 1.0) is None


def test_missed_runner_only_when_the_adr5_extreme_is_hit_before_1000():
    """E5: the quarter-ADR5 runner (20 %) stays only when the first rung (the ADR5 extreme) was hit before 10:00; hit later, the rest leaves with it (manage: runner_before)."""
    p = Params(**BASE, missed_5m=True)
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, p)
    for hhmm, kept in (("09:40", True), ("10:05", False)):
        pos = fake_pos(sl, bar(ctx, "09:30"), st=dict(runner_before=600), t1_done=True)
        pos["left"] = 2
        tr = fake_tr()
        tr.exits = [(pd.Timestamp("2026-06-23 " + hhmm, tz=NY), 116.0, 8, "t1")]
        sm7.manage(ctx, sl, pos, tr, bar(ctx, "10:10"), pd.Timestamp("2026-06-23 10:10", tz=NY), p)
        assert (pos["left"] == 2) is kept
        if not kept:
            assert tr.exits[-1][3] == "no_runner" and tr.exits[-1][1] == 116.0


# --- OT-D15 / OT-max-two: the dual combine --------------------------------------------------------------------------------------------------------

def test_dual_combine_never_executes_ym_and_caps_the_markets():
    """Review fix: dual_deal builds its rows from the raw runs, so YM (never executed) must not make a second market of a dual slot, and the two-market cap sees those rows too."""
    es, nq, ym = _dual_book("ES"), _dual_book("NQ", entry="09:41", exit_="10:01"), _dual_book("YM", entry="09:42", exit_="10:02")
    for mode in ("split", "full"):
        out = B.combine(es, ym, dual_deal=mode)
        assert list(out.symbol) == ["ES"]                                                              # ES + YM on the same slot is NOT a dual: YM is dropped
        out2 = B.combine(es, nq, ym, dual_deal=mode)
        assert sorted(out2.symbol) == ["ES", "NQ"]                                                     # the real dual (ES + NQ) is kept, YM never
    rty = _dual_book("RTY", entry="09:43", exit_="10:03")
    with pytest.raises(ValueError, match="at most 2"):
        B.combine(es, nq, rty, dual_deal="split")
    assert len(B.combine(es, ym, dual_deal="full", exec_exclude=(), max_exec=0)) == 2                  # switch off: the Dow executes again
    assert B.combine(ym, dual_deal="split").empty


# --- the special setups pass through the bias gate -------------------------------------------------------------------------------------------------

def test_special7_bias_gate(monkeypatch):
    """Review fix (cc09_003 / 022 / 046 'pass through use_bias like every setup'): the NY expansion, the 10:50 macro and the lunch macro are tried only on the bias side; the London-close scalp (counter-trend on
    purpose) is not gated; a neutral bias tries both sides."""
    seen = []
    for name in ("nyx_order", "m1050_order", "lunch_macro_order", "lc_order"):
        monkeypatch.setattr(sm7, name, lambda ctx, sd, i, p, *a, _n=name, **k: seen.append((_n, sd.sign)))
    p = Params(**BASE, nyx_model=True, m1050=True, lunch_macro_entry=True, lc_scalp=True, htf_bias="combo")
    ctx, sides = mk7({0: (100.0, 100.1, 99.9, 100.0)}, p)

    def run(bias, hhmm, name):
        seen.clear()
        monkeypatch.setattr(sm7, "bias_now", lambda c, p_, s_, i_: bias)
        sm7.special7(ctx, list(sides), bar(ctx, hhmm), p, {}, None, None, 1.0, {})
        return sorted(x[1] for x in seen if x[0] == name)

    assert run(1, "10:55", "m1050_order") == [1] and run(-1, "10:55", "m1050_order") == [-1]       # the other side is never tried
    assert run(0, "10:55", "m1050_order") == [-1, 1]                                                 # neutral / off: both
    assert run(1, "09:50", "nyx_order") == [1] and run(-1, "09:50", "nyx_order") == [-1]
    assert run(1, "11:55", "lunch_macro_order") == [1] and run(-1, "11:55", "lunch_macro_order") == [-1]
    assert run(1, "10:55", "lc_order") == [-1, 1]                                                    # the counter-trend scalp is not bias-gated


# --- sibi_return alone -----------------------------------------------------------------------------------------------------------------------------

def test_sibi_return_trigger_works_without_the_idea_gate(cap):
    """Review fix: reentry_trigger="sibi_return" with reentry_idea_gate OFF used to hit the old restored-sweep test, which the return order (ext_i == stop_i) can never pass. loss_reentry_ok routes it
    through the idea-intact test; any other order is rejected while the sibi return is awaited."""
    p = Params(**BASE, reentry_half=True, reentry_trigger="sibi_return")
    assert not p.reentry_idea_gate
    ctx, (sl, ss) = mk7({600: (100.0, 100.5, 98.8, 99.2), 605: (99.2, 101.6, 99.1, 101.4)}, p)
    fi, si, i = bar(ctx, "09:40"), bar(ctx, "10:00"), bar(ctx, "10:05")
    rc = dict(side="long", z=(99.0, 101.0), ext=98.0, low_stop=98.7, draw=110.0, fill_i=fi, stop_i=si, pending=True)
    ctx.re_ctx_now = dict(rc, armed=False)
    assert sm7.re_order(ctx, sl, i, p, "AM", 1.0) is not None
    sibi = dict(entry_kind="sibi_return", ext_i=si, i=i, sm7=dict(kind="sibi_return"))
    assert sm7.loss_reentry_ok(ctx, sl, i, p, sibi, rc) is True
    assert sm7.loss_reentry_ok(ctx, sl, i, p, dict(entry_kind="fvg", ext_i=si + 1, i=si + 1, fvg_i=si + 1), rc) is False
    import inspect
    assert "loss_reentry_ok" in inspect.getsource(S._run_day_once)                                    # the engine really routes through it


# --- re-entry kinds: limit orders only, armed only once the order passed ---------------------------------------------------------------------------

def test_win_reentry_never_a_market_chase():
    p = Params(**BASE, reentry_after_win=True, reentry_after_trail_win=True)
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, p)
    r7 = dict(kind="win", side="long", exit_i=bar(ctx, "10:00"), fill_i=bar(ctx, "09:40"), draw=110.0, pending=True)
    i = bar(ctx, "10:10")
    o = dict(fvg_i=bar(ctx, "10:05"), i=bar(ctx, "10:05"), entry_kind="fvg")
    assert sm7.reentry_ok(ctx, sl, i, p, o, r7) is True
    assert sm7.reentry_ok(ctx, sl, i, p, dict(o, market=True), r7) is False                              # ifvg_061 / release_ob_entry style chases
    r7t = dict(r7, kind="trail_win")
    assert sm7.reentry_ok(ctx, sl, i, p, dict(o, sm7=dict(kind="trail_win")), r7t) is True
    assert sm7.reentry_ok(ctx, sl, i, p, dict(o, sm7=dict(kind="trail_win"), market=True), r7t) is False


def test_armed_flag_only_after_the_order_passed(monkeypatch):
    """Review fix: re_order marks the context armed only when the order tail returned an order - a rejected one may be tried again on a later bar."""
    p = Params(**BASE, reverse_after_failure="at_stop")
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0), 580: (100.0, 100.1, 97.9, 98.0), 585: (98.0, 98.6, 97.8, 98.5)}, p)
    ctx.re7 = dict(kind="reverse", variant="at_stop", side="short", exit_i=bar(ctx, "09:40"), fill_i=bar(ctx, "09:35"), pending=True, old_stop=98.25, adv_ext=101.2,
                   zone=(99.0, 101.0), ext=98.0, stop_i=bar(ctx, "09:40"))
    monkeypatch.setattr(sm4, "_order", lambda *a, **k: None)
    assert sm7.re_order(ctx, ss, bar(ctx, "09:45"), p, "AM", 1.0) is None
    assert not ctx.re7.get("armed")                                                                    # rejected: not armed
    monkeypatch.setattr(sm4, "_order", lambda *a, **k: dict(entry=1.0))
    assert sm7.re_order(ctx, ss, bar(ctx, "09:45"), p, "AM", 1.0) is not None
    assert ctx.re7["armed"] is True


# --- the propulsion-MT condition of prop_fail -------------------------------------------------------------------------------------------------------

def test_prop_fail_needs_a_body_close_through_the_propulsion_mt():
    pc = Params(**BASE, reverse_after_failure="prop_fail", prop_mt_exit=True)
    ctx, (sl, ss) = mk7({570: (100.0, 100.4, 99.6, 99.9), 575: (99.9, 100.2, 99.7, 100.0)}, pc)
    fi, i0 = bar(ctx, "09:30"), bar(ctx, "09:40")
    pos = fake_pos(sl, fi)
    pos["lvx"] = {"prop_mt": (99.95, False)}                                                           # a body closed at 99.9 (09:30) under the MT 99.95
    s1 = st0()
    assert sm7.after_close(ctx, pos, fake_tr(reason="stop", entry_kind="arr_propulsion"), "long", -400.0, {"AM": True}, "AM", s1, i0, pc, False) is False   # ... but that bar is the FILL bar: only later bars count
    pos_b = fake_pos(sl, bar(ctx, "09:25"))
    pos_b["lvx"] = {"prop_mt": (99.95, False)}
    s1b = st0()
    assert sm7.after_close(ctx, pos_b, fake_tr(reason="stop", entry_kind="arr_propulsion"), "long", -400.0, {"AM": True}, "AM", s1b, i0, pc, False) is True and s1b["re7"]["AM"]["variant"] == "prop_fail"
    pos2 = fake_pos(sl, fi)
    pos2["lvx"] = {"prop_mt": (99.0, False)}                                                           # no body ever closed under 99.0: the propulsion block held
    s2 = st0()
    assert sm7.after_close(ctx, pos2, fake_tr(reason="stop", entry_kind="arr_propulsion"), "long", -400.0, {"AM": True}, "AM", s2, i0, pc, False) is False


# --- ts_breaker_add_mult unset keeps the old sizing ---------------------------------------------------------------------------------------------------

def test_ts_adds_breakers_keep_the_add_fractions(monkeypatch):
    """Review fix: with ts_breaker_add_mult unset (None) the breaker add of M12.2_ts_adds_breakers / M4.4_ts_breaker_pyramid is _arm_add's own sized add (adds[k]: 0.33, 0.17 ...), exactly as before."""
    got = []
    monkeypatch.setattr(S, "_arm_add", lambda pos, tr, px, i, p, eq, **k: got.append(k.get("size", "default")))
    monkeypatch.setattr(S._SM, "add_ok", lambda *a, **k: True)
    sd = sd_of([(100.0, 101.0, 99.0, 100.5)] * 13, 1, 1)
    z = L.Zone("bull", 105.0, 103.0, 12, 8)
    pos, tr, ctx = dict(plan_shares=10, fill_i=6), SimpleNamespace(shares=10), SimpleNamespace(equity=1e6)
    sm7.breaker_add(ctx, sd, pos, tr, 12, Params(**{**BASE, "adds": (0.33, 0.17)}, ts_adds_breakers=True), z)
    assert got == ["default"]                                                                           # the standard sized add (no explicit size)
    sm7.breaker_add(ctx, sd, pos, tr, 12, Params(**{**BASE, "adds": (0.33, 0.17)}, ts_adds_breakers=True, ts_breaker_add_mult=0.5), z)
    assert got[-1] == 5


# --- state tag / London-close exit / OR and AM arrays / SMT window / PM nesting edge -----------------------------------------------------------------

def test_state_tag_without_pairing():
    """Review fix: state_tag stamps the session state on every order (so the report can split by it) while pairing stays "all"."""
    p = Params(**BASE, state_tag=True)
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, p)
    o = {}
    assert sm7.late7(ctx, sl, dict(), bar(ctx, "09:40"), p, o, {}, "AM") is None
    assert o["state"] in ("consolidation", "expansion", "retracement", "reversal")
    o2 = {}
    sm7.late7(ctx, sl, dict(), bar(ctx, "09:40"), Params(**BASE), o2, {}, "AM")
    assert "state" not in o2 and sm7.any_late7(p) and not sm7.any_late7(Params(**BASE))


def test_lc_mss_order_exits_at_the_am_exit(cap):
    """Review fix: the mss-mode London-close scalp carries a forced exit at the AM exit (exit_at 720)."""
    over = {0: (100.0, 100.1, 99.9, 100.0), 540: (100.0, 111.0, 99.95, 110.8), 575: (110.8, 111.2, 110.7, 111.1), 585: (111.1, 111.3, 110.5, 110.7), 590: (110.7, 112.3, 110.6, 112.2),
            600: (112.2, 113.0, 112.1, 112.9), 605: (112.9, 112.95, 111.6, 111.7), 610: (111.7, 111.8, 110.2, 110.3), 615: (110.3, 110.9, 110.1, 110.5)}
    p = Params(**BASE, lc_scalp=True, lc_mode="mss")
    ctx, (sl, ss) = mk7(over, p, hist=history(D0, hi=105.0, lo=95.0))
    assert sm7.lc_order(ctx, ss, bar(ctx, "10:15"), p, 1.0) is not None
    assert cap["tags"]["exit_at"] == 720 and cap["tags"]["entry_kind"] == "lc_scalp"
    p0 = Params(**BASE, lc_scalp=True, lc_mode="mss", am_exit=0)
    ctx0, (sl0, ss0) = mk7(over, p0, hist=history(D0, hi=105.0, lo=95.0))
    assert sm7.lc_order(ctx0, ss0, bar(ctx0, "10:15"), p0, 1.0) is not None
    assert cap["tags"]["exit_at"] is None


def test_or_ref_array_dies_when_a_body_closes_through_it_inside_the_or(cap):
    """Review fix: a body that closed through an OR60 reference array inside the OR (an up-close bar at 10:05 closing under the OB low 100.9) kills it, not only closes after 10:30."""
    p = Params(**BASE, entry_arrays=("or_ref",))
    ctx, (sl, ss) = mk7(_orref_over(), p, bias=1)
    assert sm7.or_ref_order(ctx, sl, bar(ctx, "10:35"), p, "AM", 1.0) is not None
    ctx2, (sl2, _) = mk7({**_orref_over(), 605: (99.8, 100.6, 99.7, 100.5)}, p, bias=1)
    assert sm7.or_ref_order(ctx2, sl2, bar(ctx2, "10:35"), p, "AM", 1.0) is None


def test_am_open_array_must_be_fresh_since_it_formed(cap):
    """Review fix: a London FVG that price traded into (or closed through) between 05:00 and 09:30 is not a first touch at 09:35."""
    over = {180: (100.0, 100.5, 99.9, 100.4), 185: (100.4, 103.0, 100.3, 102.9), 190: (102.9, 103.2, 102.0, 103.1), 575: (103.1, 103.2, 103.0, 103.1)}
    p = Params(**BASE, am_array_open=True)
    ctx, (sl, ss) = mk7(over, p, base=100.0, bias=1)
    assert sm7.am_open_order(ctx, sl, bar(ctx, "09:35"), p, "AM", 1.0) is not None
    ctx2, (sl2, _) = mk7({**over, 400: (103.1, 103.2, 101.5, 103.0)}, p, base=100.0, bias=1)             # 06:40 trades into the 100.5-102.0 gap, closes above it
    assert sm7.am_open_order(ctx2, sl2, bar(ctx2, "09:35"), p, "AM", 1.0) is None
    ctx3, (sl3, _) = mk7({**over, 400: (103.1, 103.2, 99.0, 99.5)}, p, base=100.0, bias=1)               # ... or closes through it
    assert sm7.am_open_order(ctx3, sl3, bar(ctx3, "09:35"), p, "AM", 1.0) is None


def test_trail_ref_recorded_only_when_the_stop_rises():
    """Review fix: pos["trail_ref"] is the structure the stop SITS under - written only when the trail raised the stop (the guard precedes the assignment in the position loop)."""
    import inspect
    src = inspect.getsource(S._run_day_once)
    k = src.index('pos["trail_ref"] = (float(g.bottom)')
    assert 'if ref_ - p.trail_pad > pos["stop"]:' in src[k - 200:k]


def test_two_session_smt_window_and_hold():
    """Review fix: two_session_smt adds the 12:00-13:30 SMT pair to a non-empty smt_windows (empty = SMT at any time already); the held PM position is skipped by the PM time exits."""
    assert Params(two_session_smt=True).smt_windows == ()
    assert Params(two_session_smt=True, smt_windows=((570, 660),)).smt_windows == ((570, 660), (720, 810))
    assert Params(two_session_smt=True, smt_windows=((700, 900),)).smt_windows == ((700, 900),)
    assert sm7.held(dict(sm7=dict(hold_pm=True))) and not sm7.held(dict(sm7=dict())) and not sm7.held(dict())


def test_pm_nest_target_is_the_near_edge_of_the_am_entry_array():
    """Review fix: the PM reversal's single target is the NEAR EDGE of the HTF array holding the AM entry (the top of a long's array, 103), not the AM entry price (101) inside it."""
    p = Params(**BASE, pm_nest_reversal=True)
    arrs = {-1: [(114.0, 112.0, "D", 0, 0), (113.5, 111.5, "4h", 0, 0), (113.0, 111.0, "1h", 0, 0)], 1: [(103.0, 100.0, "4h", 0, 0)]}
    ctx, (sl, ss) = mk7(_am_rally_over(), p, conf=Conf7(arrs, at_tfs={1: ["4h"]}))
    ctx.risk_view = dict(trades=[am_trade("long", entry=101.0)])
    i = bar(ctx, "14:00")
    sw = dict(smt=None, ext=-112.5, ext_i=i, sweep_i=i, session="PM")
    tags = {}
    assert sm7.order_gate7(ctx, ss, sw, i, p, -112.0, -114.0, "PM", [], {}, tags) is None
    assert tags["fixed4"][0][0] == pytest.approx(S._exit_px(-103.0, "array", p)) and tags["single_exit"]


def test_lunch_program_long_only_inside_the_macro():
    """times#12: the program's long is armed in 710-730 (11:50-12:10); the same setup at 12:15 (the 12:30 extension) is x_lunch_program_window."""
    from test_caption_gap_sm7a import _lunch_over
    p = Params(**BASE, htf_bias="combo", lunch_htf_program=True)
    ctx, (sl, ss) = mk7(_lunch_over(), p)
    ctx.bias_row = {"combo": 1, "draw_up": 120.0}
    ev = dict(ext_i=bar(ctx, "11:55"), sweep_i=bar(ctx, "11:55"))
    assert sm7.order_gate7(ctx, sl, ev, bar(ctx, "11:55"), p, 105.0, 103.0, "LUNCH", [], {}, {}) is None
    assert sm7.order_gate7(ctx, sl, ev, bar(ctx, "12:15"), p, 105.0, 103.0, "LUNCH", [], {}, {}) == "x_lunch_program_window"
    assert Params(**BASE, lunch_long_win=(710, 750)).lunch_long_win == (710, 750)
    with pytest.raises(ValueError):
        Params(**BASE, lunch_long_win=(750, 710))
