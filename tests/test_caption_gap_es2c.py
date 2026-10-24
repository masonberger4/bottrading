"""Caption-gap pass, package entries_stops_sizing #2/3, part C: the tests of the REVIEW FIXES of the chunk - the fill-time look-ahead of the OB grade / market-on-touch / wick redelivery, the direct breakaway chase,
the post-break stop raise of the far-edge entry, the higher-array stop and the zone ladder on every breaker path, the one-shot add flags, the OB add-cutoff formation price, and the forced-path look-ahead books
(a full run vs runs truncated at every bar of a hand-made day: the switches whose code path no ES data window reaches). Hand-made days and hand-made Sides only; nothing here needs market data or a
platform-specific path."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import es2, levels as L, setups as SM, sm2, sm4, sm7, strategy as S
from mentorship.strategy import Params

from test_review_fixes import A_LOCK, A_ROWS, BASE, D0, day, history, run as rf_run
from test_caption_gap_sm1a import sd_of
from test_caption_gap_es2a import ADD_ROWS, VI_EARLY, VI_OB


def _added(h0):
    return {k: v - h0.get(k, 0) for k, v in sm2.HITS.items() if v - h0.get(k, 0)}


# --- models#92 / models#52: a market order never fills under its stop -------------------------------------------------------------------

def test_convert_pending_drops_an_order_whose_stop_was_pierced_or_gapped():
    rows = [(100.0, 100.4, 99.6, 100.3), (100.3, 100.5, 98.6, 99.0), (99.0, 99.2, 98.6, 99.1), (99.1, 99.3, 98.9, 99.2)]
    sd = sd_of(rows)
    o = dict(i=0, entry=99.0, stop=98.0, mot=True)
    assert es2.convert_pending(o, sd, 2).get("market") is True and not es2.convert_pending(o, sd, 2).get("es2_dead")      # the touch bar (low 98.6) stayed over the stop 98.0
    assert es2.convert_pending(dict(o, stop=98.7), sd, 2).get("es2_dead") is True                                          # ... the touch bar traded through a stop at 98.7: a market fill would sit under it
    sd2 = sd_of([rows[0], rows[1], (97.9, 98.5, 97.5, 98.2), rows[3]])
    r = es2.convert_pending(dict(o, stop=98.0), sd2, 2)
    assert r.get("es2_dead") is True and not r.get("market")                                                               # bar 2 OPENS under the stop (97.9)
    sd3 = sd_of([rows[0], rows[1], (101.5, 101.8, 101.0, 101.6), rows[3]])
    assert es2.convert_pending(dict(o, stop=98.5), sd3, 2).get("es2_dead") is True                                         # the open (101.5) is farther over the entry than the planned risk (0.5)
    # a chase order (unfilled for N bars) is judged the same way, over every bar since the arming
    c = dict(i=0, entry=99.5, stop=98.0, chase_bars=2)
    assert es2.convert_pending(c, sd, 3).get("market") is True
    assert es2.convert_pending(dict(c, stop=98.7), sd, 3).get("es2_dead") is True                                          # bar 1 traded through 98.7 while the order waited
    s0 = dict(sm2.HITS)
    es2.convert_pending(dict(o, stop=98.7), sd, 2)
    assert sm2.HITS.get("market_dead_stop", 0) > s0.get("market_dead_stop", 0)


def test_the_engine_cancels_a_dead_market_order():
    """run_day's cancel chain honours es2_dead: a pending order carrying it is dropped (it never fills at the open)."""
    src = open(S.__file__, encoding="utf-8").read()
    assert 'pending.get("es2_dead") or t >= cut' in src


# --- definitions#151: the grade uses only what is known at the fill ---------------------------------------------------------------------

def test_grade_inputs_never_read_the_fill_bar():
    st = dict(ob_mt=99.4, arm_i=2)
    sd = sd_of([(100.0, 100.5, 99.9, 100.2)] * 3 + [(100.2, 100.5, 99.6, 100.1)] * 2 + [(100.1, 100.2, 90.0, 90.5)])
    low, close = es2.grade_inputs(sd, st, 5, 100.0)
    assert low == pytest.approx(99.6) and close == pytest.approx(100.1)                    # bars 3, 4 (closed) and the fill price - not bar 5 (its low 90.0 / close 90.5 are unknown at the fill)
    assert es2.grade_inputs(sd, st, 3, 100.0) == (100.0, 100.0)                           # no closed bar between the arming and the fill: the fill price alone
    assert es2.grade_inputs(sd, st, 5, 99.0)[0] == pytest.approx(99.0)                    # a fill price under the closed lows lowers the retest low


def test_grade_update_regrades_after_the_close_and_sizes_later_adds():
    p = Params(es_pt=1.0, ob_grade_mult=(1.0, 0.5))
    st = dict(ob_mt=99.4, ob_body=1.2, arm_i=1)
    rows = [(100.0, 100.5, 99.9, 100.2), (100.2, 100.6, 100.0, 100.4), (100.4, 100.6, 100.0, 100.5), (100.5, 100.6, 99.3, 100.3), (100.3, 100.4, 98.9, 99.0)]
    sd = sd_of(rows)
    tr = SimpleNamespace(lv_tags="x|ob_grade_A")
    pos = dict(es2=st, es2_grade="A", fill_i=2, t1_done=False)
    es2.grade_update(sd, pos, tr, 2, p)
    assert pos["es2_grade"] == "A"                                                         # the fill bar itself: nothing new
    es2.grade_update(sd, pos, tr, 3, p)
    assert pos["es2_grade"] == "B" and tr.lv_tags == "x|ob_grade_A" and pos["es2_add_mult"] == 0.5     # bar 3 stabbed 0.1 under the MT and closed over it (the tag keeps the fill-time grade)
    es2.grade_update(sd, pos, tr, 4, p)
    assert pos["es2_grade"] == "X" and pos["es2_add_mult"] == 1.0                                       # bar 4 closed under it: invalid - no multiplier
    es2.grade_update(sd, pos, tr, 3, p)
    assert pos["es2_grade"] == "X"                                                         # the worst grade stands
    pos2 = dict(es2=st, es2_grade="A", fill_i=2, t1_done=False)
    es2.grade_update(sd, pos2, SimpleNamespace(lv_tags=""), 3, Params(es_pt=1.0))
    assert pos2["es2_grade"] == "A"                                                        # ob_grade_mult off: nothing graded
    # the multiplier applies to the size of a later add (_arm_add)
    q = dict(basis=1000.0, n=10, stop=99.0, add=None, plan_shares=10)
    trq = SimpleNamespace(shares=10, adds=[], rungs="")
    pa = Params(es_pt=1.0, adds=(1.0,), lot=1)
    S._arm_add(dict(q), trq, 101.0, 4, pa, 1e9)
    full = dict(q)
    S._arm_add(full, trq, 101.0, 4, pa, 1e9)
    half = dict(q, es2_add_mult=0.5)
    S._arm_add(half, trq, 101.0, 4, pa, 1e9)
    assert full["add"]["q"] == 10 and half["add"]["q"] == 5


def test_grade_regrade_through_the_engine_and_no_fill_bar_look_ahead():
    """The A scenario with a stab 0.1 under the OB MT on the FILL bar: the fill is graded A at full size (the stab is not known at the fill); the stab regrades it to B once the bar has closed (a later add is scaled)."""
    hist = history()
    rows = list(A_ROWS)
    rows[4] = (100.7, 100.8, 99.3, 100.3)
    p = Params(**{**BASE, "min_risk_pts": 0.5, "ob_grade_mult": (1.0, 0.5)})
    base, *_ = rf_run(day(rows, spike=True), hist, Params(**{**BASE, "min_risk_pts": 0.5}), A_LOCK)
    tr, *_ = rf_run(day(rows, spike=True), hist, p, A_LOCK)
    assert len(tr) == 1 and tr[0].shares == base[0].shares and "ob_grade_A" in tr[0].lv_tags and "ob_grade_B" not in tr[0].lv_tags         # fill-time grade on the trade


# --- models#30: the wick redelivery reads the fill price and closed bars only ---------------------------------------------------------

def test_wick_redelivery_ignores_the_fill_bars_own_low():
    sd = sd_of([(100.0, 100.4, 99.6, 100.3), (100.3, 100.6, 100.2, 100.5), (100.3, 100.5, 90.0, 91.0)])
    assert es2.wick_redelivery(sd, 2, 100.4) is False                                      # the fill bar's low (90.0) must not decide
    assert es2.wick_redelivery(sd, 2, 100.2) is True                                       # the fill price itself reached the low of the last up-close candle (100.2)
    p = Params(es_pt=1.0, retrace_candle="intrabar", e4_wick_ok=True)
    o = dict(i=0, entry=100.4)
    assert S._retrace_ok(sd, o, 2, p) is False                                              # entry 100.4 over the up candle's low, the fill bar opens at 100.5 > 100.4 ... but see below
    o2 = dict(i=0, entry=100.15)
    assert S._retrace_ok(sd, o2, 2, p) is True                                              # the limit 100.15 is under bar 1's low: redelivered at the fill


# --- models#18: the post-break stop raise of the far-edge entry ----------------------------------------------------------------------------

def _far_book():
    # a breaker candle (bar 1 body 100.2-101.0), a 5m gap over it, a short-term high at 103.0 (bar 6), a run over it at bar 8
    return sd_of([(101.0, 101.2, 99.0, 99.2), (99.2, 101.0, 98.9, 100.2), (100.2, 100.4, 99.6, 100.0), (100.0, 102.0, 99.9, 101.9), (101.9, 102.6, 101.5, 102.4),
                  (102.4, 103.0, 102.2, 102.5), (102.5, 102.8, 102.0, 102.2), (102.2, 102.4, 101.0, 101.2), (101.2, 104.0, 101.1, 103.8)])


def test_far_raise_tags_and_update():
    sd = _far_book()
    bz = L.Zone("bull", 101.0, 100.2, 2, 1, 100.6)
    g = L.Zone("bull", 100.6, 99.8, 3, 1, float("nan"))
    p = Params(es_pt=1.0)
    tg = es2.far_raise_tags(sd, g, bz, 7, p, 98.0)
    assert tg is not None and tg["ph"] > g.top and tg["level"] == pytest.approx(min(100.2 - p.pad, 100.6 - p.tick))      # the breaker bottom (under its MT)
    assert es2.far_raise_tags(sd, g, bz, 7, p, 100.0) is None                                                         # the stop is already there: nothing to raise
    assert es2.far_raise_tags(sd, g, None, 7, p, 98.0) is None and es2.far_raise_tags(sd, L.Zone("bull", 90.0, 89.0, 3, 1, float("nan")), bz, 7, p, 98.0) is None      # no breaker overlap
    pos = dict(es2=dict(far_raise=dict(ph=103.0, level=100.0)), fill_i=3, stop=98.0)
    s0 = dict(sm2.HITS)
    es2.far_raise_update(sd, pos, 5, p)
    assert pos["stop"] == 98.0                                                                                          # no close over the short-term high yet
    S_raise = S._MG.raise_stop
    es2.far_raise_update(sd, pos, 8, p)
    assert pos["stop"] == pytest.approx(100.0) and pos["far_raised"] and sm2.HITS.get("far_on_breaker_raise", 0) > s0.get("far_on_breaker_raise", 0)
    pos["stop"] = 99.0
    es2.far_raise_update(sd, pos, 8, p)
    assert pos["stop"] == 99.0                                                                                          # once only
    assert S_raise is S._MG.raise_stop


def test_far_on_breaker_carries_the_5m_edges_to_the_1m_chart():
    sd = _far_book()
    bz = L.Zone("bull", 101.0, 100.2, 2, 1, 100.6)
    g = L.Zone("bull", 100.6, 99.8, 3, 1, float("nan"))
    p = Params(es_pt=1.0, entry="far_on_breaker")
    s0 = dict(sm2.HITS)
    r = es2.far_on_breaker_stop(SimpleNamespace(tf=1), sd, dict(ext_i=0), g, bz, True, 7, p)
    assert r is not None and r[0] == pytest.approx(99.8 + p.tick)                          # the same absolute 5m edge rests on the 1m chart
    assert sm2.HITS.get("far_on_breaker_1m", 0) > s0.get("far_on_breaker_1m", 0)


# --- management#105 / stops#4: every breaker path --------------------------------------------------------------------------------------

def test_intraday_obs_and_the_higher_array_search():
    # bar 1: a down candle (body 100.4 -> 99.9) whose high 100.5 bar 2 closes over: an intraday bullish OB with a body 99.9 - 100.4
    sd = sd_of([(100.0, 100.2, 99.8, 100.1), (100.4, 100.5, 99.8, 99.9), (99.9, 101.0, 99.9, 100.9), (100.9, 101.2, 100.4, 101.0), (101.0, 101.3, 100.8, 101.1)])
    ctx = SimpleNamespace(start=0, conf=None)
    obs = es2.intraday_obs(ctx, sd, 4)
    assert (100.4, 99.9) in [(round(a, 2), round(b, 2)) for a, b in obs]
    assert es2.intraday_obs(ctx, sd, 1) == []                                              # bar 2 (the confirming close) is not known at bar 1
    bz = SimpleNamespace(bottom=103.0)
    p = Params(es_pt=1.0, bz_higher_array=True, bz_higher_pts=5.0)
    assert es2.higher_array(ctx, sd, bz, 4, p) == pytest.approx(99.9)                      # the OB body bottom 99.9 is the far edge (its top 100.4 is within 5 pts under 103.0 - 5 = 98.0 .. 103.0)
    assert es2.higher_array(ctx, sd, SimpleNamespace(bottom=120.0), 4, p) is None          # farther than bz_higher_pts


def test_breaker_tail_serves_the_unicorn_cc_and_advanced_breaker_paths(monkeypatch):
    cap = {}

    def fin(ctx, sd, i, p, session, sw, entry, stop, risk_mult, lh, tags, **kw):
        cap.update(entry=entry, stop=stop, tags=tags)
        return dict(entry=entry, stop=stop)

    monkeypatch.setattr(S, "_finish_order", fin)
    monkeypatch.setattr(es2, "higher_array", lambda ctx, sd, zone, i, p: 97.0)
    sd = sd_of([(100.0, 100.5, 99.0, 100.2)] * 12)
    ctx = SimpleNamespace(start=0, conf=None)
    p = Params(es_pt=1.0, bz_higher_array=True, in_zone_ladder=True)
    sw = dict(ext=98.0, ext_i=2, session="AM")
    SM.cc_breaker_order(ctx, sd, sw, 10, p, "AM", 1.0, 102.0)
    assert cap["stop"] == pytest.approx(97.0 - p.pad) and cap["tags"]["lvx"]["bz_higher"][0] == 97.0 and cap["tags"]["bz_mt"] is None        # the cc breaker swing: the stop beyond the higher array
    assert cap["tags"]["zone_ladder"] and cap["tags"]["ladder"] == [102.0, pytest.approx(100.0)]                                          # 1/3 at the retest level, 2/3 at the zone MT (new low .. retest)
    cap.clear()
    monkeypatch.setattr(SM, "_l1", lambda sd_, ref_i, i: SimpleNamespace(price=99.0))
    SM.adv_breaker_order(ctx, sd, dict(ext=98.0, ext_i=2), 10, p, "AM", 1.0, 5, 103.0, True)
    assert cap["stop"] == pytest.approx(97.0 - p.pad) and "ladder" not in cap["tags"] and cap["tags"]["lvx"]["bz_higher"][0] == 97.0     # the advanced breaker: the stop only (the entry IS the A-B MT)
    off = Params(es_pt=1.0)
    cap.clear()
    SM.cc_breaker_order(ctx, sd, sw, 10, off, "AM", 1.0, 102.0)
    assert cap["stop"] == pytest.approx(98.0 - off.pad) and "ladder" not in cap["tags"]


def test_breaker_tail_helper_alone():
    zone = es2._Z(98.0, 100.0)
    tags = {}
    p = Params(es_pt=1.0, in_zone_ladder=True)
    assert es2.breaker_tail(SimpleNamespace(start=0, conf=None), sd_of([(100.0, 100.5, 99.0, 100.2)] * 4), 3, p, zone, 102.0, 97.0, tags) == 97.0
    assert tags["ladder_fracs"] == pytest.approx((1 / 3, 2 / 3)) and tags["zone_ladder"]
    t2 = {}
    es2.breaker_tail(SimpleNamespace(start=0, conf=None), sd_of([(100.0, 100.5, 99.0, 100.2)] * 4), 3, p, zone, 100.1, 97.0, t2)
    assert "ladder" not in t2                                                              # the entry is not over the MT


# --- models#52: the direct breakaway chase ------------------------------------------------------------------------------------------------

def _chase_book():
    # the winner filled at bar 1, exited at bar 4 (r7 exit_i = 4); a pivot high at bar 6 (103.0) confirmed at 7; bar 9 closes over it with a gap [bar 8 high 103.1 < bar 10 low 103.9]
    return sd_of([(100.0, 100.4, 99.8, 100.2), (100.2, 101.0, 100.0, 100.9), (100.9, 102.0, 100.8, 101.9), (101.9, 102.6, 101.5, 102.4), (102.4, 102.8, 102.2, 102.5),
                  (102.5, 102.9, 102.1, 102.7), (102.7, 103.0, 102.3, 102.5), (102.5, 102.6, 102.0, 102.2), (102.2, 103.1, 102.1, 102.9), (102.9, 104.6, 102.8, 104.4),
                  (104.4, 105.0, 103.9, 104.8), (104.8, 105.0, 104.0, 104.3), (104.3, 104.5, 104.0, 104.2)])


def test_chase_pick_takes_the_breakaway_gap_directly():
    sd = _chase_book()
    p = Params(es_pt=1.0, breakaway_chase=True, min_risk_pts=0.5)
    r7 = dict(kind="win", side="long", exit_i=4, fill_i=1, draw=110.0, pending=True)
    pk = sm7.chase_pick(sd, 11, p, r7)
    assert pk is not None
    g, entry, stop = pk
    assert g.i == 10 and entry == pytest.approx(g.top) and stop == pytest.approx(g.bottom - p.pad)      # the first gap after the exit whose middle candle closed over the pivot high 103.0 (bar 9 close 104.4)
    assert sm7.chase_pick(sd, 8, p, r7) is None                                                         # not yet formed
    assert sm7.chase_pick(sd, 11, p, dict(r7, draw=104.0)) is None                                      # the draw was traded: the idea is spent
    assert sm7.chase_pick(sd, 11, p, dict(r7, exit_i=9)) is None                                        # a gap formed BEFORE the exit is no new array
    # no look-ahead: the pick at bar i is the same on a book cut at i
    rows = [tuple(map(float, (sd.o[k], sd.h[k], sd.l[k], sd.c[k]))) for k in range(len(sd.c))]
    for i in range(6, 13):
        a, b = sm7.chase_pick(sd, i, p, r7), sm7.chase_pick(sd_of(rows[:i + 1]), i, p, r7)
        assert (a is None) == (b is None) and (a is None or a[1:] == pytest.approx(b[1:]))


def test_chase_order_arms_once_and_carries_the_chase_bars(monkeypatch):
    cap = {}
    monkeypatch.setattr(sm4, "_order", lambda ctx, sd, i, p, session, rm, name, entry, stop, **kw: cap.update(name=name, entry=entry, stop=stop, **kw) or dict(entry=entry))
    monkeypatch.setattr(S, "_exit_px", lambda v, kind, p: v)
    sd = _chase_book()
    p = Params(es_pt=1.0, breakaway_chase=True, breakaway_chase_bars=4, min_risk_pts=0.5)
    r7 = dict(kind="win", side="long", exit_i=4, fill_i=1, draw=110.0, pending=True)
    s0 = dict(sm2.HITS)
    o = sm7.chase_order(SimpleNamespace(), sd, 11, p, "AM", 1.0, r7)
    assert o is not None and cap["name"] == "breakaway_chase" and cap["chase_bars"] == 4 and cap["fvg_i"] == 10 and cap["entry"] == pytest.approx(sd.gaps[-1].top) and r7["armed"]
    assert sm2.HITS.get("breakaway_chase_direct", 0) > s0.get("breakaway_chase_direct", 0)
    assert sm7.chase_order(SimpleNamespace(), sd, 11, p, "AM", 1.0, r7) is None                         # once per win
    ctx = SimpleNamespace(re7=dict(r7, armed=False), re_ctx_now=None)
    assert sm7.any_re_orders(ctx, p) is True and sm7.any_re_orders(ctx, Params(es_pt=1.0)) is False     # the win state routes to re_order only with the switch


# --- one-shot flags are spent only by an armed add ----------------------------------------------------------------------------------------

def test_post_partial_add_is_not_spent_when_the_arm_fails():
    p = Params(es_pt=1.0, add_after_partial="inv_fvg")
    rows = [(100.0, 100.4, 99.8, 100.3), (100.3, 101.0, 100.2, 100.9), (100.9, 101.2, 100.8, 101.1), (101.1, 102.0, 101.0, 101.9), (101.9, 102.2, 101.6, 102.0), (102.0, 102.3, 101.9, 102.2)]
    sd = sd_of(rows)
    z = L.Zone("bear", 101.5, 101.0, 3, 2, float("nan"))
    sd2 = SimpleNamespace(opposing=lambda: [z], c=sd.c, gaps=[])
    tr = SimpleNamespace(shares=4, adds=[], exits=[(None, 101.0, 1, "t1")])
    pos = dict(post_partial_adds=0, add=None, t1_done=True, left=3, fill_i=0, stop=99.0, rung_fills=0)
    es2.post_partial_add(SimpleNamespace(), sd2, pos, tr, 5, p, lambda px, size, fl: False)
    assert pos["post_partial_adds"] == 0                                                   # the add was not armed: still available
    es2.post_partial_add(SimpleNamespace(), sd2, pos, tr, 5, p, lambda px, size, fl: pos.__setitem__("add", {}) or True)
    assert pos["post_partial_adds"] == 1


def test_add_locations_one_shot_sets_are_spent_only_when_armed():
    p = Params(es_pt=1.0, add_on_ifvg=True)
    z = L.Zone("bull", 101.0, 100.6, 4, 3, float("nan"))
    sd = SimpleNamespace(ifvgs=lambda: [z], c=np.array([102.0] * 8), l=np.array([100.0] * 8))
    pos = dict(fill_i=1, stop=99.0, t1_done=False, add=None)
    es2.add_locations(SimpleNamespace(conf=None), sd, pos, SimpleNamespace(), 6, p, lambda px, floor=None, form=None: False)
    assert not pos.get("es2_ifvg_used")
    es2.add_locations(SimpleNamespace(conf=None), sd, pos, SimpleNamespace(), 6, p, lambda px, floor=None, form=None: True)
    assert 4 in pos["es2_ifvg_used"]


# --- stops#8: the OB add-cutoff test reads the OB body bottom -----------------------------------------------------------------------------

def test_ob_add_paths_pass_the_body_bottom_as_the_formation_price(monkeypatch):
    seen = []
    monkeypatch.setattr(SM, "add_ok", lambda sd, pos, px, i, p, form=None: seen.append((px, form)) or False)
    # S._ob_add: a down-close run (bars 3, 4: bodies 101.0 -> 100.6 and 100.7 -> 100.4) after the fill, then the arming close
    rows = [(100.0, 100.4, 99.8, 100.3), (100.3, 101.0, 100.2, 100.9), (100.9, 101.2, 100.8, 101.1), (101.1, 101.2, 100.5, 100.7), (100.7, 100.8, 100.2, 100.4), (100.4, 101.5, 100.3, 101.4)]
    sd = sd_of(rows)
    pos = dict(fill_i=1, stop=99.0, ob_add_used=set(), add=None)
    S._SM = SM
    S._ob_add(sd, pos, SimpleNamespace(), 5, Params(es_pt=1.0), 1e6)
    assert seen and seen[0][0] == pytest.approx(101.1) and seen[0][1] == pytest.approx(100.4)          # the add price = the run's body top 101.1; the formation price = its body bottom 100.4


def test_ob_in_vi_add_returns_the_body_bottom():
    from mentorship import es1
    rows = [(100.0, 100.3, 99.9, 100.2), (100.2, 100.9, 100.1, 100.8), (100.8, 101.5, 100.7, 101.4), (101.4, 101.5, 100.9, 101.0), (101.0, 101.1, 100.4, 100.5), (100.5, 100.9, 100.3, 100.8)]
    sd = sd_of(rows)
    r = es1.ob_in_vi_add(sd, dict(fill_i=0), 5, Params(es_pt=1.0))
    assert r is None or (len(r) == 3 and r[2] <= r[0])                                       # (mt, floor, body bottom): the body bottom never lies over the MT


# --- models#24 / management#129: the near edge, under the market ---------------------------------------------------------------------------

def test_fri_shallow_pick_takes_a_gap_under_the_market_and_the_edge_is_forced():
    rows = [(100.0, 100.5, 99.5, 100.2), (100.2, 100.4, 99.0, 99.1), (99.1, 100.9, 99.0, 100.8), (100.8, 102.0, 100.7, 101.9), (101.9, 103.0, 101.8, 102.9)]
    sd = sd_of(rows)
    g_old = L.Zone("bull", 100.0, 99.2, 2, 1, float("nan"))
    above = L.Zone("bull", 105.0, 104.0, 0, 1, float("nan"))
    fri = SimpleNamespace(day=pd.Timestamp("2026-06-26").date(), cur_lock=dict(side=1, target=104.0))
    pf = Params(es_pt=1.0, fri_shallow=True)
    assert es2.fri_shallow_pick(fri, sd, dict(ext_i=1, ext=99.0), [above], 3, pf) is None                 # a gap over the market is no limit
    assert es2.fri_shallow_pick(fri, sd, dict(ext_i=1, ext=99.0), [above, g_old], 3, pf) is None             # the FIRST gap (bar 0) lies over the market: the normal pick stands
    assert es2.fri_shallow_pick(fri, sd, dict(ext_i=1, ext=99.0), [g_old, L.Zone("bull", 105.0, 104.0, 3, 1, float("nan"))], 3, pf) is g_old
    src = open(S.__file__, encoding="utf-8").read()
    assert 'if cp_:' in src and 'em_ = "edge"                                   # review fix (E1-close-proximity' in src                                                          # close_proximity / fri_shallow enter at the NEAR EDGE whatever p.entry says


# --- forced-path look-ahead books (hand-made days) -----------------------------------------------------------------------------------------

def _cmp_trades(full, part, tj):
    """Everything the full run decided BEFORE bar tj (fills, adds and exits strictly before it) must be what a run on the data through bar tj also decided."""
    for t in full:
        if t.entry_time >= tj:
            continue
        m = [q for q in part if q.entry_time == t.entry_time]
        assert len(m) == 1, (t.entry_time, tj)
        q = m[0]
        assert (q.entry, q.stop, q.shares, q.side) == pytest.approx((t.entry, t.stop, t.shares, t.side)), (t.entry_time, tj)
        assert [(a[0], a[1], a[2]) for a in q.adds if a[0] < tj] == [(a[0], a[1], a[2]) for a in t.adds if a[0] < tj]
        assert [(e[0], e[1], e[2], e[3]) for e in q.exits if e[0] < tj] == [(e[0], e[1], e[2], e[3]) for e in t.exits if e[0] < tj]


def _day_la(rows, p, need, lock=A_LOCK, hist=None, spike=True, d=D0):
    """A full run of a hand-made day vs runs on the data truncated at EVERY bar of the book; the full run must have executed the code path (the sm2.HITS counters in `need`)."""
    df = day(rows, d=d, spike=spike)
    hist = hist if hist is not None else history(d)
    h0 = dict(sm2.HITS)
    full, *_ = rf_run(df, hist, p, lock)
    added = _added(h0)
    assert len(full) >= 1, "the book made no trade"
    missing = [h for h in need if not added.get(h)]
    assert not missing, (missing, sorted(added))
    k0 = int(np.flatnonzero(df.index.hour * 60 + df.index.minute == 570)[0])
    for j in range(k0, min(len(df), k0 + len(rows) + 3)):
        part, *_ = rf_run(df.iloc[:j + 1], hist, p, lock)
        _cmp_trades(full, part, df.index[j])
    return full


def _vi_params(**kw):
    return Params(**{**BASE, "adds": (0.5, 0.33, 0.17), "ob_adds": False, "draw_lock_partials": False, "min_risk_pts": 0.5, "risk_pct": 0.003, **kw})


def test_look_ahead_forced_vi_ob_add():
    tr = _day_la(VI_OB, _vi_params(vi_ob_add=True), ("vi_ob_add",))
    assert len(tr[0].adds) == 1


def test_look_ahead_forced_vi_add_early():
    tr = _day_la(VI_EARLY, _vi_params(vi_add_early_pts=0.3), ("vi_add_early",))
    assert len(tr[0].adds) == 1


def test_look_ahead_forced_trend_day_adds_real_classifier():
    """The REAL trend-day classifier on hand-made books (no forcing): its verdict at bar k is the same whatever the bars after k do (they are replaced by a crash / a spike)."""
    from test_caption_gap_sm1a import mkctx
    rows = [(100.0, 100.8, 100.0, 100.6), (100.6, 102.4, 100.5, 102.2), (102.2, 104.0, 102.0, 103.8), (103.8, 106.6, 103.6, 106.2), (106.2, 107.4, 106.0, 107.2), (107.2, 107.9, 106.8, 107.5)]
    p = Params(es_pt=1.0, add_day_mode="trend_day", trend_day_adr=0.2)
    h0 = dict(sm2.HITS)
    k0 = None
    got = []
    for cut in range(len(rows)):
        wild = rows[:cut + 1] + [(60.0, 150.0, 40.0, 55.0)] * (len(rows) - cut - 1)
        for variant in (rows, wild):
            ctx, (sl, ss) = mkctx(variant, base=100.0, hist=history(D0, hi=108.0, lo=90.0))
            k0 = S._idx_at(ctx, 570)
            pos = {}
            es2.trend_day_update(ctx, sl, pos, k0 + cut, p)
            got.append((cut, variant is rows, pos["td_ok"], pos["td_block"]))
    by = {}
    for cut, is_full, ok, blk in got:
        by.setdefault(cut, set()).add((ok, blk))
    assert all(len(v) == 1 for v in by.values()), by                                         # the verdict at bar k never depends on the bars after it
    assert {True} == {ok for v in by.values() for ok, _ in v if ok} and any(blk for v in by.values() for _, blk in v)      # the trend-day verdict and the far-extreme block both occurred
    assert _added(h0).get("trend_day_adds") and _added(h0).get("trend_day_far")


def test_look_ahead_forced_rb_ctx_mult(monkeypatch):
    """A rejection-block sweep key is forced onto scenario A's sweep (the daily rejection-block arrays are not in the hand-made history): the order gate halves the size (counter-bias / no HTF array)."""
    from mentorship import ld4
    monkeypatch.setattr(ld4, "is_rb_key", lambda k: str(k) == "premarket")
    base = rf_run(day(A_ROWS, spike=True), history(), Params(**{**BASE, "min_risk_pts": 0.5}), A_LOCK)[0]
    tr = _day_la(A_ROWS, Params(**{**BASE, "min_risk_pts": 0.5, "rb_ctx_mult": 0.5}), ("rb_ctx_lower",))
    assert tr[0].shares <= base[0].shares / 2 + 1 and "rb_ctx_lower" in tr[0].lv_tags


def test_look_ahead_forced_e4_colour_and_market_on_touch():
    tr = _day_la(A_ROWS, Params(**{**BASE, "min_risk_pts": 0.5, "e4_color": True}), ("retrace_intrabar_ok",))
    assert tr[0].entry == pytest.approx(100.0)
    _day_la(A_ROWS, Params(**{**BASE, "min_risk_pts": 0.5, "entry_order": "market_on_touch"}), ("mot_order",))


def test_look_ahead_forced_ob_regrade():
    rows = list(A_ROWS)
    rows[4] = (100.7, 100.8, 99.3, 100.3)
    tr = _day_la(rows, Params(**{**BASE, "min_risk_pts": 0.5, "ob_grade_mult": (1.0, 0.5)}), ("ob_grade_A", "ob_grade_regrade_B"))
    assert "ob_grade_A" in tr[0].lv_tags
